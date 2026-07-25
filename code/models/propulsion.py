# -*- coding: utf-8 -*-
"""推进与油耗模块

提供:
- effective_power: P_E = R_total × V_ship
- brake_power: P_B = P_E / (η_S × η_D)
- fuel_rate: 油耗率 = P_B × SFOC
- fuel_consumption: 总油耗

参考:
    ④ 计明军 2023 场景2: 70h × 14kn = 89.2 t (HFO, SFOC≈0.160 kg/kWh)
    ⑤ Guzelbulut 2024 §2.3
"""
from dataclasses import dataclass


# 默认效率与油耗参数
DEFAULT_ETA_SHAFT = 0.98       # 轴传递效率 η_S
DEFAULT_ETA_PROPULSIVE = 0.97  # 推进效率 η_D (open water × rot. eff.)
DEFAULT_SFOC = 0.160           # 比油耗 kg/kWh (HFO, 典型 0.155-0.175)

# 排放因子 — 统一从 core.constants 获取，避免多处定义不一致
from core.constants import DEFAULT_EMISSION_FACTOR  # noqa: E402  # 3.114 tCO2/tFuel (HFO)


@dataclass
class PropulsionResult:
    """推进计算结果

    Attributes:
        P_E_W:    有效功率 P_E = R_total × V (W)
        P_B_W:    制动功率 P_B = P_E / (η_S × η_D) (W)
        fuel_kg_per_h: 油耗率 (kg/h)
        fuel_kg_per_s: 油耗率 (kg/s)
        eta_total: 总效率 η_S × η_D
        SFOC: 比油耗 (kg/kWh)
    """
    P_E_W: float
    P_B_W: float
    fuel_kg_per_h: float
    fuel_kg_per_s: float
    eta_total: float
    SFOC: float


def effective_power(R_total_N: float, V_ship_ms: float) -> float:
    """计算有效功率 P_E = R × V

    Args:
        R_total_N: 总阻力 (N)
        V_ship_ms: 船速 (m/s)

    Returns:
        P_E: 有效功率 (W)
    """
    if R_total_N < 0:
        raise ValueError(f"R_total={R_total_N} 不能为负")
    if V_ship_ms < 0:
        raise ValueError(f"V_ship={V_ship_ms} 不能为负")
    return R_total_N * V_ship_ms


def brake_power(P_E_W: float,
                eta_shaft: float = DEFAULT_ETA_SHAFT,
                eta_propulsive: float = DEFAULT_ETA_PROPULSIVE) -> float:
    """计算制动功率（主机持续功率）

    P_B = P_E / (η_S × η_D)

    Args:
        P_E_W: 有效功率 (W)
        eta_shaft: 轴传递效率
        eta_propulsive: 推进效率

    Returns:
        P_B: 制动功率 (W)
    """
    eta_total = eta_shaft * eta_propulsive
    if not (0 < eta_total < 1):
        raise ValueError(f"η_total={eta_total} 应在 (0, 1)")
    return P_E_W / eta_total


def fuel_rate(P_B_W: float, SFOC: float = DEFAULT_SFOC) -> float:
    """计算油耗率

    Args:
        P_B_W: 制动功率 (W)
        SFOC: 比油耗 (kg/kWh)

    Returns:
        fuel_kg_per_h: 油耗率 (kg/h)
    """
    P_B_kW = P_B_W / 1000.0
    return P_B_kW * SFOC


def fuel_consumption(fuel_kg_per_h: float, duration_h: float) -> float:
    """计算总油耗

    Args:
        fuel_kg_per_h: 油耗率 (kg/h)
        duration_h: 航程时长 (h)

    Returns:
        fuel_kg: 总油耗 (kg)
    """
    return fuel_kg_per_h * duration_h


def compute_propulsion(R_total_N: float, V_ship_ms: float,
                       eta_shaft: float = DEFAULT_ETA_SHAFT,
                       eta_propulsive: float = DEFAULT_ETA_PROPULSIVE,
                       SFOC: float = DEFAULT_SFOC) -> PropulsionResult:
    """推进计算一站式接口

    链路:
        R, V → P_E → P_B → 油耗率

    Args:
        R_total_N: 总阻力 (N)
        V_ship_ms: 船速 (m/s)
        eta_shaft: 轴传递效率
        eta_propulsive: 推进效率
        SFOC: 比油耗 (kg/kWh)

    Returns:
        PropulsionResult: 含 P_E, P_B, 油耗率等
    """
    P_E = effective_power(R_total_N, V_ship_ms)
    P_B = brake_power(P_E, eta_shaft, eta_propulsive)
    fuel_h = fuel_rate(P_B, SFOC)
    fuel_s = fuel_h / 3600.0
    eta_total = eta_shaft * eta_propulsive
    return PropulsionResult(
        P_E_W=P_E,
        P_B_W=P_B,
        fuel_kg_per_h=fuel_h,
        fuel_kg_per_s=fuel_s,
        eta_total=eta_total,
        SFOC=SFOC,
    )


def fuel_to_co2(fuel_kg: float,
                emission_factor: float = DEFAULT_EMISSION_FACTOR) -> float:
    """油耗 → CO2 排放

    Args:
        fuel_kg: 油耗 (kg)
        emission_factor: 排放因子 (tCO2/tFuel)，HFO 默认 3.114

    Returns:
        co2_kg: CO2 排放 (kg)
    """
    fuel_t = fuel_kg / 1000.0
    co2_t = fuel_t * emission_factor
    return co2_t * 1000.0  # kg
