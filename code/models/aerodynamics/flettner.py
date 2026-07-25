# -*- coding: utf-8 -*-
"""Flettner 转子帆气动模型

实现 ⑤ Guzelbulut 2024 Eq.6-8 的 CL/CD/CP 多项式回归，
数据来源 Kwon et al. (2022) CFD 仿真。

公式:
    c_L = SR × [a_0 + a_1·AR + a_2·(D_e/D) + ... + a_12·SR³]   (13 项)
    c_D = b_0 + b_1·AR + ... + b_12·SR³                          (13 项)
    c_P = exp(c_0 + c_1·SR + ... + c_7·(D_e/D)³)                 (8 项)

力计算:
    L = ½·ρ·V²·S·C_L          (升力)
    D = ½·ρ·V²·S·C_D          (阻力)
    T = L·sin(β) − D·cos(β)   (推力分量，沿船首方向)
    F_side = L·cos(β) + D·sin(β)  (侧向力)
    P_rotor = ½·ρ·V³·S·C_P    (转子驱动功耗)

边界条件: SR=0 时 (C_L, C_D, C_P) = (0, 0.5, 0)
"""
import os
import yaml
import numpy as np
from dataclasses import dataclass, field
from scipy.optimize import minimize_scalar

from .base import SailBase


# 默认系数文件路径
DEFAULT_COEF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "flettner_coefficients.yaml"
)


@dataclass
class FlettnerConfig:
    """Flettner 转子帆设计变量"""
    H: float          # 转子高度 (m), 范围 10-40
    D: float          # 转子直径 (m)
    AR: float         # 展弦比 H/D, 范围 4-8
    D_e_D: float      # 端板直径比 D_e/D, 范围 1.5-8
    S: float = 0.0    # 投影面积 = H × D (m²)，若为 0 则自动计算

    def __post_init__(self):
        if self.S == 0.0:
            self.S = self.H * self.D  # 圆柱投影面积

    def validate(self) -> None:
        """校验设计变量在允许范围内"""
        if not (10.0 <= self.H <= 40.0):
            raise ValueError(f"H={self.H} 超出 [10, 40] m")
        if not (4.0 <= self.AR <= 8.0):
            raise ValueError(f"AR={self.AR} 超出 [4, 8]")
        if not (1.5 <= self.D_e_D <= 8.0):
            raise ValueError(f"D_e/D={self.D_e_D} 超出 [1.5, 8]")


def _load_coefficients(coef_path: str) -> dict:
    """从 YAML 加载 34 个回归系数"""
    with open(coef_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 提取系数数组
    a = [cfg["lift_coefficients"][f"a_{i}"] for i in range(13)]
    b = [cfg["drag_coefficients"][f"b_{i}"] for i in range(13)]
    c = [cfg["power_coefficients"][f"c_{i}"] for i in range(8)]

    return {
        "a": np.array(a),  # CL 系数 (13,)
        "b": np.array(b),  # CD 系数 (13,)
        "c": np.array(c),  # CP 系数 (8,)
        "boundary": cfg.get("boundary_conditions", {}).get("SR_zero", {}),
    }


class FlettnerSail(SailBase):
    """Flettner 转子帆气动模型

    实现 ⑤ Guzelbulut 2024 的 CL/CD/CP 回归公式。

    用法:
        sail = FlettnerSail(FlettnerConfig(H=20, D=4, AR=5, D_e_D=3))
        cl, cd, cp = sail.cl_cd_cp(SR=2.0)
        forces = sail.forces(V_apparent=10, rho_air=1.171, SR=2.0, beta=np.pi/4)
        opt = sail.optimal_control(V_apparent=10, rho_air=1.171, beta=np.pi/4)
    """

    def __init__(self, config: FlettnerConfig,
                 coef_path: str | None = None) -> None:
        self.config = config
        config.validate()

        if coef_path is None:
            coef_path = DEFAULT_COEF_PATH

        self.coef = _load_coefficients(coef_path)
        self._a = self.coef["a"]
        self._b = self.coef["b"]
        self._c = self.coef["c"]
        self._boundary = self.coef["boundary"]

    # ---------- 系数计算 ----------

    def _compute_CL(self, SR: float) -> float:
        """计算升力系数 C_L

        c_L = SR × [a_0 + a_1·AR + a_2·(D_e/D) + a_3·SR
                   + a_4·AR·(D_e/D) + a_5·AR·SR + a_6·(D_e/D)·SR
                   + a_7·AR² + a_8·(D_e/D)² + a_9·SR²
                   + a_10·AR³ + a_11·(D_e/D)³ + a_12·SR³]
        """
        AR = self.config.AR
        DeD = self.config.D_e_D
        a = self._a

        bracket = (
            a[0]                          # a_0
            + a[1] * AR                   # a_1·AR
            + a[2] * DeD                  # a_2·(D_e/D)
            + a[3] * SR                   # a_3·SR
            + a[4] * AR * DeD             # a_4·AR·(D_e/D)
            + a[5] * AR * SR              # a_5·AR·SR
            + a[6] * DeD * SR             # a_6·(D_e/D)·SR
            + a[7] * AR**2                # a_7·AR²
            + a[8] * DeD**2               # a_8·(D_e/D)²
            + a[9] * SR**2                # a_9·SR²
            + a[10] * AR**3               # a_10·AR³
            + a[11] * DeD**3              # a_11·(D_e/D)³
            + a[12] * SR**3               # a_12·SR³
        )
        return SR * bracket

    def _compute_CD(self, SR: float) -> float:
        """计算阻力系数 C_D

        c_D = b_0 + b_1·AR + b_2·(D_e/D) + b_3·SR
            + b_4·AR·(D_e/D) + b_5·AR·SR + b_6·(D_e/D)·SR
            + b_7·AR² + b_8·(D_e/D)² + b_9·SR²
            + b_10·AR³ + b_11·(D_e/D)³ + b_12·SR³
        """
        AR = self.config.AR
        DeD = self.config.D_e_D
        b = self._b

        return (
            b[0]                          # b_0
            + b[1] * AR                   # b_1·AR
            + b[2] * DeD                  # b_2·(D_e/D)
            + b[3] * SR                   # b_3·SR
            + b[4] * AR * DeD             # b_4·AR·(D_e/D)
            + b[5] * AR * SR              # b_5·AR·SR
            + b[6] * DeD * SR             # b_6·(D_e/D)·SR
            + b[7] * AR**2                # b_7·AR²
            + b[8] * DeD**2               # b_8·(D_e/D)²
            + b[9] * SR**2                # b_9·SR²
            + b[10] * AR**3               # b_10·AR³
            + b[11] * DeD**3              # b_11·(D_e/D)³
            + b[12] * SR**3               # b_12·SR³
        )

    def _compute_CP(self, SR: float) -> float:
        """计算功率系数 C_P

        c_P = exp(c_0 + c_1·SR + c_2·SR² + c_3·AR + c_4·AR²
                  + c_5·(D_e/D) + c_6·(D_e/D)² + c_7·(D_e/D)³)
        """
        AR = self.config.AR
        DeD = self.config.D_e_D
        c = self._c

        exponent = (
            c[0]                          # c_0
            + c[1] * SR                   # c_1·SR
            + c[2] * SR**2                # c_2·SR²
            + c[3] * AR                   # c_3·AR
            + c[4] * AR**2                # c_4·AR²
            + c[5] * DeD                  # c_5·(D_e/D)
            + c[6] * DeD**2               # c_6·(D_e/D)²
            + c[7] * DeD**3               # c_7·(D_e/D)³
        )
        return float(np.exp(exponent))

    def cl_cd_cp(self, SR: float) -> tuple[float, float, float]:
        """计算给定 SR 下的 (C_L, C_D, C_P)

        边界条件: SR=0 时返回 (0, 0.5, 0)（⑤ §3 约束）
        SR 范围 ±5（顺时针/逆时针）

        Args:
            SR: 自旋比 (ω·R)/V_A

        Returns:
            (C_L, C_D, C_P) 无量纲
        """
        # SR=0 边界条件（转子停转）
        if abs(SR) < 1e-10:
            cl_zero = self._boundary.get("C_L", 0.0)
            cd_zero = self._boundary.get("C_D", 0.5)
            cp_zero = self._boundary.get("C_P", 0.0)
            return (cl_zero, cd_zero, cp_zero)

        cl = self._compute_CL(SR)
        cd = self._compute_CD(SR)
        cp = self._compute_CP(SR)
        return (cl, cd, cp)

    # ---------- 力计算 ----------

    def forces(self, V_apparent: float, rho_air: float,
               beta: float, SR: float = 0.0, **kwargs) -> dict[str, float]:
        """计算 Flettner 转子帆的气动力

        Args:
            V_apparent: 相对风速 (m/s)
            rho_air: 空气密度 (kg/m³)
            beta: 相对风向角 (rad)，0=顶风，π/2=横风
            SR: 自旋比（可选，默认 0）

        Returns:
            dict: lift, drag, thrust, side_force, power_rotor, CL, CD, CP
        """
        cl, cd, cp = self.cl_cd_cp(SR)
        S = self.config.S
        q = 0.5 * rho_air * V_apparent**2  # 动压

        L = q * S * cl           # 升力 (N)
        D = q * S * cd           # 阻力 (N)
        # 推力分解（沿船首方向）
        T = L * np.sin(beta) - D * np.cos(beta)
        # 侧向力（垂直船首方向）
        F_side = L * np.cos(beta) + D * np.sin(beta)
        # 转子驱动功耗
        P_rotor = 0.5 * rho_air * V_apparent**3 * S * cp

        return {
            "lift": float(L),
            "drag": float(D),
            "thrust": float(T),
            "side_force": float(F_side),
            "power_rotor": float(P_rotor),
            "CL": float(cl),
            "CD": float(cd),
            "CP": float(cp),
        }

    # ---------- 最优控制 ----------

    def optimal_control(self, V_apparent: float, rho_air: float,
                        beta: float) -> dict:
        """在给定风况下求使净功率最大的 SR

        净功率 = T·V − P_rotor（推力做功减去转子驱动功耗）

        Args:
            V_apparent: 相对风速 (m/s)
            rho_air: 空气密度 (kg/m³)
            beta: 相对风向角 (rad)

        Returns:
            dict: SR_opt, thrust, power_rotor, net_power, CL, CD, CP

        注意:
            Kwon 2022 原始 CFD 数据仅覆盖 SR∈[1,5]（⑤ §3 line 484 明示）。
            负 SR 区域为公式外推，回归多项式含偶次项不保证马格努斯方向反转，
            且 CP 指数外推可能产生"无功耗大推力"假象，违反能量守恒。
            故最优控制搜索范围限定为 SR∈[0, 5]（CFD 有效区间 + SR=0 物理边界）。
        """
        def neg_net_power(SR: float) -> float:
            f = self.forces(V_apparent, rho_air, beta, SR=SR)
            return -(f["thrust"] * V_apparent - f["power_rotor"])

        # 在 SR ∈ [0, 5] 上搜索（Kwon 2022 CFD 有效区间 SR∈[1,5]）
        result = minimize_scalar(
            neg_net_power,
            bounds=(0.0, 5.0),
            method="bounded",
            options={"xatol": 1e-3}
        )

        SR_opt = result.x
        f_opt = self.forces(V_apparent, rho_air, beta, SR=SR_opt)
        net_power = f_opt["thrust"] * V_apparent - f_opt["power_rotor"]

        return {
            "SR_opt": float(SR_opt),
            "thrust": f_opt["thrust"],
            "power_rotor": f_opt["power_rotor"],
            "net_power": float(net_power),
            "CL": f_opt["CL"],
            "CD": f_opt["CD"],
            "CP": f_opt["CP"],
            "lift": f_opt["lift"],
            "drag": f_opt["drag"],
            "side_force": f_opt["side_force"],
        }

    @property
    def projected_area(self) -> float:
        """投影面积 S (m²)"""
        return self.config.S
