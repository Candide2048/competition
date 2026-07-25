# -*- coding: utf-8 -*-
"""吸力帆 (Suction Sail / eSAIL) 气动模型

实现基于攻角的高升力吸力翼帆气动力计算。吸力帆通过边界层抽吸延迟气流分离，
可在小攻角获得远高于传统翼帆的升力系数（bound4blue eSAIL 优化后 CL_max≈8.3）。

⚠️ 数据缺口: 吸力帆无公开完整 CL/CD 极曲线（config/sail_types.yaml 已注明）。
本模型采用**参数化极曲线**，锚定于以下可查文献指标:
    - CL_max ≈ 7.0（保守；bound4blue 优化后可达 8.3，见 bound4blue 2024 气动优化）
    - L/D_max ≈ 12（吸力翼型典型 8-15）
    - 失速攻角 ≈ 25°（吸力延迟分离，高于普通翼型 ~15°）
    - 吸力风扇功耗 ≈ 15 kW/帆（MV Ankie 2×15 kW）

极曲线构造:
    C_L(α) = CL_max·sin(π/2 · min(α,α_stall)/α_stall)       (α≤α_stall 平滑上升到峰值)
             失速后线性缓降
    C_D(α) = CD_min + k·C_L²                                 (标准阻力极曲线)
    k 标定使 L/D_max ≈ 12

力计算:
    L = ½·ρ·V²·S·C_L,  D = ½·ρ·V²·S·C_D
    T = L·sin(β) − D·cos(β),  F_side = L·cos(β) + D·sin(β)
    P_drive = 吸力风扇功耗（近似恒定，仅在帆工作时计入）

数据来源:
    [1] config/sail_types.yaml suction_wing 段（船舶风帆技术数据搜集表.xlsx）
    [2] bound4blue 2024 "Aerodynamic optimization of the eSAIL" (CL_max 8.3, L/P +20%)
    [3] 赵大刚 2026 综述（吸力帆定性描述）
"""
import os
import yaml
import numpy as np

from .base import SailBase


DEFAULT_SAIL_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "sail_types.yaml"
)


class SuctionSail(SailBase):
    """吸力帆气动模型（高升力，攻角控制，恒定吸力功耗）

    用法:
        sail = SuctionSail.from_config()
        f = sail.forces(V_apparent=12, rho_air=1.2, beta=np.pi/2, aoa_deg=20)
        opt = sail.optimal_control(V_apparent=12, rho_air=1.2, beta=np.pi/2)
    """

    def __init__(self, S: float, CL_max: float = 7.0,
                 CD_min: float = 0.15, L_D_max: float = 12.0,
                 stall_aoa_deg: float = 25.0,
                 suction_power_kW: float = 15.0) -> None:
        """
        Args:
            S:                单帆投影面积 (m²)
            CL_max:           峰值升力系数
            CD_min:           最小阻力系数（零升阻力）
            L_D_max:          目标最大升阻比（用于标定诱导阻力系数 k）
            stall_aoa_deg:    失速攻角 (deg)
            suction_power_kW: 吸力风扇功耗 (kW/帆)
        """
        self._S = float(S)
        self.CL_max = float(CL_max)
        self.CD_min = float(CD_min)
        self.stall_aoa = float(stall_aoa_deg)
        self.suction_power_W = float(suction_power_kW) * 1000.0

        # 标定诱导阻力系数 k 使 L/D_max = 1/(2·√(CD_min·k)) = L_D_max
        #   L/D 最大处 CL* = √(CD_min/k), (L/D)_max = CL*/(2·CD_min) = 1/(2√(CD_min·k))
        # → k = CD_min / (2·CD_min·L_D_max)² = 1 / (4·CD_min·L_D_max²)
        self.k_induced = 1.0 / (4.0 * self.CD_min * L_D_max ** 2)

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "SuctionSail":
        """从 sail_types.yaml 的 suction_wing 段构造"""
        if config_path is None:
            config_path = DEFAULT_SAIL_CONFIG
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        sw = cfg["suction_wing"]
        aero = sw["aero"]
        return cls(
            S=sw["geometry"]["projected_area"],
            CL_max=aero.get("CL_max", 7.0),
            CD_min=aero.get("CD_min", 0.15),
            L_D_max=aero.get("L_D_max", 12.0),
            stall_aoa_deg=aero.get("stall_aoa_deg", 25.0),
            suction_power_kW=sw["power"].get("rotor_power_per_sail_kW", 15.0),
        )

    # ---------- 系数计算 ----------

    def cl_cd(self, aoa_deg: float) -> tuple[float, float]:
        """参数化极曲线 (C_L, C_D)

        α≤α_stall: C_L 平滑上升到 CL_max
        α>α_stall: 线性缓降（每超 1°衰减 CL_max 的 1.5%，下限 0）
        C_D = CD_min + k·C_L²
        """
        aoa = max(0.0, float(aoa_deg))
        if aoa <= self.stall_aoa:
            cl = self.CL_max * np.sin(np.pi / 2 * aoa / self.stall_aoa)
        else:
            decay = 1.0 - 0.015 * (aoa - self.stall_aoa)
            cl = self.CL_max * max(decay, 0.0)
        cd = self.CD_min + self.k_induced * cl ** 2
        return float(cl), float(cd)

    # ---------- 力计算 ----------

    def forces(self, V_apparent: float, rho_air: float,
               beta: float, aoa_deg: float = 0.0,
               operating: bool = True, **kwargs) -> dict[str, float]:
        """计算吸力帆气动力

        Args:
            V_apparent: 相对风速 (m/s)
            rho_air:    空气密度 (kg/m³)
            beta:       相对风向角 (rad)，0=顶风，π/2=横风
            aoa_deg:    攻角 (deg)
            operating:  吸力系统是否开启（False 则升阻力与功耗均为 0）

        Returns:
            dict: lift, drag, thrust, side_force, power_rotor(吸力功耗), CL, CD
        """
        if not operating:
            return {"lift": 0.0, "drag": 0.0, "thrust": 0.0,
                    "side_force": 0.0, "power_rotor": 0.0, "CL": 0.0, "CD": 0.0}

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
            "power_rotor": self.suction_power_W,  # 吸力风扇功耗 (W)
            "CL": float(cl),
            "CD": float(cd),
        }

    # ---------- 最优控制 ----------

    def optimal_control(self, V_apparent: float, rho_air: float,
                        beta: float) -> dict:
        """求使净功率最大的攻角

        净功率 = T·V − P_suction。若最大净功率 ≤ 0，则关闭吸力系统
        （净功率为 0），避免"低风时开风扇反而亏损"。

        Returns:
            dict: aoa_opt_deg, thrust, power_rotor, net_power, CL, CD, ...
        """
        aoa_grid = np.arange(0.0, 40.5, 1.0)
        best = None
        for aoa in aoa_grid:
            f = self.forces(V_apparent, rho_air, beta, aoa_deg=float(aoa))
            net = f["thrust"] * V_apparent - f["power_rotor"]
            if best is None or net > best["net_power"]:
                best = {**f, "aoa_opt_deg": float(aoa), "net_power": float(net)}

        # 若开吸力反而亏损，则关闭
        if best["net_power"] <= 0.0:
            off = self.forces(V_apparent, rho_air, beta, operating=False)
            return {**off, "aoa_opt_deg": 0.0, "net_power": 0.0}
        return best

    @property
    def projected_area(self) -> float:
        return self._S
