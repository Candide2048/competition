# -*- coding: utf-8 -*-
"""节油量与碳减排分析模块

封装 models/thrust_balance 的结果为高级接口，
提供航线级节油量、碳减排、节油率等指标。

公式:
    节油率 = (fuel_baseline - fuel_with_sail) / fuel_baseline × 100%
    CO2 减排 = 节油量 × 排放因子 (3.114 tCO2/tFuel for HFO)

参考:
    ③ 赵大刚 2026 综述: WASP 节油率典型区间 5-30%
    ④ 计明军 2023: 场景2 实船油耗 89.2 t
    ⑤ Guzelbulut 2024: HFO 排放因子采用 IMO C_F=3.114
"""
from dataclasses import dataclass

from models.thrust_balance import ThrustBalanceResult, total_fuel_saving
from core.constants import DEFAULT_EMISSION_FACTOR  # 统一排放因子来源


@dataclass
class FuelSavingResult:
    """航线级节油与碳减排结果

    Attributes:
        fuel_baseline_t:      无帆基线油耗 (t)
        fuel_with_sail_t:     有帆油耗 (t)
        fuel_saved_t:         节油量 (t)
        saving_rate_pct:      节油率 (%)
        co2_baseline_t:       无帆 CO2 排放 (t)
        co2_with_sail_t:      有帆 CO2 排放 (t)
        co2_reduced_t:        CO2 减排 (t)
        co2_reduction_pct:    CO2 减排率 (%)
        duration_h:           航程时长 (h)
        emission_factor:      排放因子 (tCO2/tFuel)
    """
    fuel_baseline_t: float
    fuel_with_sail_t: float
    fuel_saved_t: float
    saving_rate_pct: float
    co2_baseline_t: float
    co2_with_sail_t: float
    co2_reduced_t: float
    co2_reduction_pct: float
    duration_h: float
    emission_factor: float


def compute_fuel_saving(balance: ThrustBalanceResult,
                        duration_h: float,
                        emission_factor: float = DEFAULT_EMISSION_FACTOR) -> FuelSavingResult:
    """从推力平衡结果计算航线级节油与碳减排

    Args:
        balance:          推力平衡结果（来自 models.thrust_balance.solve_balance）
        duration_h:       航程时长 (h)
        emission_factor:  排放因子 (tCO2/tFuel)

    Returns:
        FuelSavingResult
    """
    ts = total_fuel_saving(balance, duration_h)

    fuel_baseline_t = ts["fuel_baseline_t"]
    fuel_with_sail_t = ts["fuel_with_sail_t"]
    fuel_saved_t = ts["fuel_saved_t"]
    saving_rate_pct = ts["saving_rate_pct"]

    co2_baseline_t = fuel_baseline_t * emission_factor
    co2_with_sail_t = fuel_with_sail_t * emission_factor
    co2_reduced_t = co2_baseline_t - co2_with_sail_t
    co2_reduction_pct = (
        co2_reduced_t / co2_baseline_t * 100.0
        if co2_baseline_t > 0 else 0.0
    )

    return FuelSavingResult(
        fuel_baseline_t=fuel_baseline_t,
        fuel_with_sail_t=fuel_with_sail_t,
        fuel_saved_t=fuel_saved_t,
        saving_rate_pct=saving_rate_pct,
        co2_baseline_t=co2_baseline_t,
        co2_with_sail_t=co2_with_sail_t,
        co2_reduced_t=co2_reduced_t,
        co2_reduction_pct=co2_reduction_pct,
        duration_h=duration_h,
        emission_factor=emission_factor,
    )


def compute_carbon_reduction(fuel_saved_t: float,
                             emission_factor: float = DEFAULT_EMISSION_FACTOR) -> float:
    """节油量 → CO2 减排量

    Args:
        fuel_saved_t:      节油量 (t)
        emission_factor:   排放因子 (tCO2/tFuel)

    Returns:
        co2_reduced_t: CO2 减排 (t)
    """
    return fuel_saved_t * emission_factor


def in_wasp_typical_range(saving_rate_pct: float) -> bool:
    """检查节油率是否在 WASP 典型区间 5-30%（③ 综述）

    Args:
        saving_rate_pct: 节油率 (%)

    Returns:
        bool: True 如果在 [5, 30] 区间
    """
    return 5.0 <= saving_rate_pct <= 30.0
