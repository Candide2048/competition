# -*- coding: utf-8 -*-
"""刚性翼帆 (Rigid Wing Sail) 气动模型

实现基于攻角 (angle of attack, AoA) 的升力型翼帆气动力计算。
CL/CD 极曲线来自 IET Song 2025 Table 2 风洞试验数据（AR=1.40, S=101.2 m²），
控制变量为攻角。与 Flettner 转子帆不同，翼帆无机械驱动功耗。

力计算（与 FlettnerSail 一致的坐标约定）:
    L = ½·ρ·V²·S·C_L(aoa)      (升力)
    D = ½·ρ·V²·S·C_D(aoa)      (阻力)
    T = L·sin(β) − D·cos(β)     (推力分量，沿船首方向)
    F_side = L·cos(β) + D·sin(β)  (侧向力)
    P_drive = 0                 (翼帆无机械驱动，仅自动转帆电机忽略不计)

数据来源:
    [1] IET Song 2025 Table 2 (风洞 CL/CD vs 攻角, config/sail_types.yaml)
    [2] 赵大刚 2026 综述 (多元素翼帆 CL_max +27%, 弧形帆)
    [3] Zhu et al. 2023 (Chalmers, 月牙形弧度翼帆 L/D)

注意:
    Song 2025 原始数据 CD@90°=0.00 物理上不合理（钝体侧风阻力不应为零），
    本模型对 CD 施加下限 CD_FLOOR 以避免非物理的"零阻力"外推。
"""
import os
import yaml
import numpy as np

from .base import SailBase


# 默认帆型参数文件
DEFAULT_SAIL_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "sail_types.yaml"
)

# CD 物理下限（修正 Song 2025 CD@90°=0.00 的非物理值）
CD_FLOOR = 0.05


class RigidWingSail(SailBase):
    """刚性翼帆气动模型（升力型，攻角控制）

    用法:
        sail = RigidWingSail.from_config()          # 从 sail_types.yaml 加载
        f = sail.forces(V_apparent=12, rho_air=1.2, beta=np.pi/2, aoa_deg=40)
        opt = sail.optimal_control(V_apparent=12, rho_air=1.2, beta=np.pi/2)
    """

    def __init__(self, S: float,
                 aoa_deg: list[float], cl: list[float], cd: list[float],
                 cl_gain: float = 1.0) -> None:
        """
        Args:
            S:        单帆投影面积 (m²)
            aoa_deg:  攻角采样点 (deg, 升序)
            cl:       对应升力系数
            cd:       对应阻力系数
            cl_gain:  升力增益系数（1.0=单翼；带襟翼≈1.27；双元素≈1.45）
        """
        self._S = float(S)
        self._aoa = np.asarray(aoa_deg, dtype=float)
        self._cl = np.asarray(cl, dtype=float) * cl_gain
        # 施加 CD 物理下限
        self._cd = np.clip(np.asarray(cd, dtype=float), CD_FLOOR, None)
        self.cl_gain = cl_gain

        if self._aoa.ndim != 1 or len(self._aoa) < 2:
            raise ValueError("攻角采样点至少需 2 个")
        if not (len(self._aoa) == len(self._cl) == len(self._cd)):
            raise ValueError("aoa/cl/cd 长度必须一致")

    @classmethod
    def from_config(cls, config_path: str | None = None,
                    cl_gain: float = 1.0) -> "RigidWingSail":
        """从 sail_types.yaml 的 rigid_wing 段构造"""
        if config_path is None:
            config_path = DEFAULT_SAIL_CONFIG
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        rw = cfg["rigid_wing"]
        polar = rw["aero"]["CL_vs_aoa"]
        return cls(
            S=rw["geometry"]["projected_area"],
            aoa_deg=polar["aoa_deg"],
            cl=polar["CL"],
            cd=polar["CD"],
            cl_gain=cl_gain,
        )

    # ---------- 系数计算 ----------

    def cl_cd(self, aoa_deg: float) -> tuple[float, float]:
        """给定攻角的 (C_L, C_D)，线性插值，范围外取端点值"""
        aoa = float(np.clip(aoa_deg, self._aoa[0], self._aoa[-1]))
        cl = float(np.interp(aoa, self._aoa, self._cl))
        cd = float(np.interp(aoa, self._aoa, self._cd))
        return cl, cd

    # ---------- 力计算 ----------

    def forces(self, V_apparent: float, rho_air: float,
               beta: float, aoa_deg: float = 0.0, **kwargs) -> dict[str, float]:
        """计算翼帆气动力

        Args:
            V_apparent: 相对风速 (m/s)
            rho_air:    空气密度 (kg/m³)
            beta:       相对风向角 (rad)，0=顶风，π/2=横风
            aoa_deg:    攻角 (deg)

        Returns:
            dict: lift, drag, thrust, side_force, power_rotor(=0), CL, CD
        """
        cl, cd = self.cl_cd(aoa_deg)
        q = 0.5 * rho_air * V_apparent ** 2
        L = q * self._S * cl
        D = q * self._S * cd
        T = L * np.sin(beta) - D * np.cos(beta)
        F_side = L * np.cos(beta) + D * np.sin(beta)
        return {
            "lift": float(L),
            "drag": float(D),
            "thrust": float(T),
            "side_force": float(F_side),
            "power_rotor": 0.0,   # 翼帆无机械驱动功耗
            "CL": float(cl),
            "CD": float(cd),
        }

    # ---------- 最优控制 ----------

    def optimal_control(self, V_apparent: float, rho_air: float,
                        beta: float) -> dict:
        """在给定风况下求使推力最大的攻角

        翼帆无驱动功耗，故直接最大化推力 T = L·sin(β) − D·cos(β)。
        在极曲线覆盖的攻角区间内网格搜索（1° 步长）。

        Returns:
            dict: aoa_opt_deg, thrust, power_rotor(=0), net_power, CL, CD, ...
        """
        aoa_grid = np.arange(self._aoa[0], self._aoa[-1] + 0.5, 1.0)
        best = None
        for aoa in aoa_grid:
            f = self.forces(V_apparent, rho_air, beta, aoa_deg=float(aoa))
            if best is None or f["thrust"] > best["thrust"]:
                best = {**f, "aoa_opt_deg": float(aoa)}

        best["net_power"] = float(best["thrust"] * V_apparent)  # 无功耗
        return best

    @property
    def projected_area(self) -> float:
        return self._S
