# -*- coding: utf-8 -*-
"""推力—阻力—功率平衡模块

风帆辅助推进下的功率平衡:
    无帆: R_total × V = P_E_baseline → P_B_baseline → 油耗_baseline
    有帆: (R_total - T_sail) × V = P_E_with_sail → P_B_with_sail → 油耗_with_sail

风帆净贡献:
    P_net_sail = T_sail × V_ship - P_rotor   (W)
                ↑ 推力做功       ↑ 转子驱动功耗

若 P_net_sail > 0: 风帆有效减功；否则风帆反消耗功率。

注: T_sail 是沿船首方向的推力分量（已分解）。
"""
from dataclasses import dataclass

from .propulsion import (
    PropulsionResult,
    brake_power,
    compute_propulsion,
    effective_power,
    fuel_consumption,
)


@dataclass
class ThrustBalanceResult:
    """推力平衡计算结果

    Attributes:
        R_total_N:        总阻力 (N)
        T_sail_N:         风帆推力 (N)，沿船首方向
        R_effective_N:    有效阻力 = R_total - T_sail (N)
        P_E_baseline_W:   无帆有效功率 (W)
        P_E_with_sail_W:  有帆有效功率 (W)
        P_B_baseline_W:   无帆制动功率 (W)
        P_B_with_sail_W:  有帆制动功率 (W)
        P_net_sail_W:     风帆净功率贡献 (W) = T_sail·V - P_rotor
        P_rotor_W:        转子驱动功耗 (W)
        fuel_baseline_kg_per_h: 无帆油耗率 (kg/h)
        fuel_with_sail_kg_per_h: 有帆油耗率 (kg/h)
        fuel_saved_kg_per_h:     节油率 (kg/h)
        saving_rate_pct:         节油率 (%)
        propulsion_baseline:     无帆 PropulsionResult
        propulsion_with_sail:    有帆 PropulsionResult
    """
    R_total_N: float
    T_sail_N: float
    R_effective_N: float
    P_E_baseline_W: float
    P_E_with_sail_W: float
    P_B_baseline_W: float
    P_B_with_sail_W: float
    P_net_sail_W: float
    P_rotor_W: float
    fuel_baseline_kg_per_h: float
    fuel_with_sail_kg_per_h: float
    fuel_saved_kg_per_h: float
    saving_rate_pct: float
    propulsion_baseline: PropulsionResult
    propulsion_with_sail: PropulsionResult


def solve_balance(R_total_N: float, V_ship_ms: float,
                  T_sail_N: float = 0.0, P_rotor_W: float = 0.0,
                  eta_shaft: float = 0.98,
                  eta_propulsive: float = 0.97,
                  eta_electrical: float = 0.90,
                  SFOC: float = 0.180) -> ThrustBalanceResult:
    """求解推力—阻力—功率平衡

    风帆推力降低推进阻力，从而减少主机推进功率；但转子/吸力风扇的驱动
    功耗 P_rotor 是主机额外承担的电力负荷，必须计入有帆油耗，否则会高估
    节油率（尤其 Flettner 50 kW/台、吸力帆 15 kW/台，刚性翼帆为 0）。

        P_B_有帆 = P_E(R_effective)/(η_S·η_D) + P_rotor/η_elec
        燃油_有帆 = P_B_有帆 × SFOC

    其中 η_elec 为「主机→发电机→电机→转子」电力驱动链综合效率。

    Args:
        R_total_N:    船体总阻力 (N，含风浪附加)
        V_ship_ms:    船速 (m/s)
        T_sail_N:     风帆推力 (N，沿船首方向)
        P_rotor_W:    转子/吸力驱动功耗 (W)，刚性翼帆为 0
        eta_shaft:    轴传递效率
        eta_propulsive: 推进效率
        eta_electrical: 电力驱动链效率（转子电力负荷折算到主机）
        SFOC:         比油耗 (kg/kWh)

    Returns:
        ThrustBalanceResult
    """
    # 有效阻力 = 总阻力 - 风帆推力
    R_effective = max(R_total_N - T_sail_N, 0.0)

    # 无帆基线
    prop_baseline = compute_propulsion(
        R_total_N, V_ship_ms, eta_shaft, eta_propulsive, SFOC
    )

    # 有帆推进（用有效阻力）
    prop_with_sail = compute_propulsion(
        R_effective, V_ship_ms, eta_shaft, eta_propulsive, SFOC
    )

    # 转子/吸力电力负荷折算到主机制动功率与油耗
    P_B_rotor = P_rotor_W / eta_electrical if P_rotor_W > 0 else 0.0
    fuel_rotor_kg_per_h = (P_B_rotor / 1000.0) * SFOC

    # 有帆制动功率与油耗 = 推进部分 + 转子电力部分
    P_B_with_sail = prop_with_sail.P_B_W + P_B_rotor
    fuel_with_sail_kg_per_h = prop_with_sail.fuel_kg_per_h + fuel_rotor_kg_per_h

    # 风帆净功率贡献 = 推力做功 - 转子功耗
    P_net_sail = T_sail_N * V_ship_ms - P_rotor_W

    # 节油（已扣除转子电力油耗）
    fuel_saved_kg_per_h = prop_baseline.fuel_kg_per_h - fuel_with_sail_kg_per_h
    saving_rate_pct = (
        fuel_saved_kg_per_h / prop_baseline.fuel_kg_per_h * 100.0
        if prop_baseline.fuel_kg_per_h > 0 else 0.0
    )

    return ThrustBalanceResult(
        R_total_N=R_total_N,
        T_sail_N=T_sail_N,
        R_effective_N=R_effective,
        P_E_baseline_W=prop_baseline.P_E_W,
        P_E_with_sail_W=prop_with_sail.P_E_W,
        P_B_baseline_W=prop_baseline.P_B_W,
        P_B_with_sail_W=P_B_with_sail,
        P_net_sail_W=P_net_sail,
        P_rotor_W=P_rotor_W,
        fuel_baseline_kg_per_h=prop_baseline.fuel_kg_per_h,
        fuel_with_sail_kg_per_h=fuel_with_sail_kg_per_h,
        fuel_saved_kg_per_h=fuel_saved_kg_per_h,
        saving_rate_pct=saving_rate_pct,
        propulsion_baseline=prop_baseline,
        propulsion_with_sail=prop_with_sail,
    )


def total_fuel_saving(balance: ThrustBalanceResult, duration_h: float) -> dict:
    """从平衡结果计算总节油量与碳减排

    Args:
        balance: 推力平衡结果
        duration_h: 航程时长 (h)

    Returns:
        dict: fuel_baseline_kg, fuel_with_sail_kg, fuel_saved_kg,
              saving_rate_pct, co2_reduced_kg
    """
    fuel_baseline_kg = fuel_consumption(
        balance.fuel_baseline_kg_per_h, duration_h
    )
    fuel_with_sail_kg = fuel_consumption(
        balance.fuel_with_sail_kg_per_h, duration_h
    )
    fuel_saved_kg = fuel_baseline_kg - fuel_with_sail_kg

    # HFO 排放因子 3.114 tCO2/tFuel (IMO MEPC.245(66)/MEPC.364(79) C_F)
    co2_reduced_kg = fuel_saved_kg * 3.114  # = fuel_saved × 3.114

    return {
        "fuel_baseline_kg": fuel_baseline_kg,
        "fuel_with_sail_kg": fuel_with_sail_kg,
        "fuel_saved_kg": fuel_saved_kg,
        "fuel_baseline_t": fuel_baseline_kg / 1000.0,
        "fuel_with_sail_t": fuel_with_sail_kg / 1000.0,
        "fuel_saved_t": fuel_saved_kg / 1000.0,
        "saving_rate_pct": balance.saving_rate_pct,
        "co2_reduced_kg": co2_reduced_kg,
        "co2_reduced_t": co2_reduced_kg / 1000.0,
        "duration_h": duration_h,
    }
