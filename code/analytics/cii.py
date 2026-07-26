# -*- coding: utf-8 -*-
"""CII (Carbon Intensity Indicator) 评级模块

实现 IMO MEPC.352(78) CII 计算方法 + MEPC.353(78) G2 参考线 + MEPC.354(78) G4 评级。

公式:
    attained_cii = (fuel_t × EF × 1e6) / (DWT × distance_nm)   [gCO2/dwt·nm]
    CII_ref = a × Capacity^(-c)                                  [MEPC.353(78) Eq.1]
    required_cii = CII_ref × year_factor                         [年度折减]

评级边界（基于 attained/required 比值, MEPC.354(78) G4）:
    A: ratio ≤ 0.86
    B: 0.86 < ratio ≤ 0.94
    C: 0.94 < ratio ≤ 1.07
    D: 1.07 < ratio ≤ 1.19
    E: ratio > 1.19

参考:
    IMO MEPC.353(78) 2022 G2 Guidelines Table 1 (a/c 参数)
    IMO MEPC.354(78) 2022 G4 Guidelines (评级边界 d1-d4)
    ⑤ Guzelbulut 2024 §2.4
    ③ 赵大刚 2026 §3
    船舶风帆技术数据搜集表.xlsx (排放因子/年度折减系数)
"""
from dataclasses import dataclass, field
from core.constants import EMISSION_FACTORS, DEFAULT_EMISSION_FACTOR  # 单一来源

# ── CII 评级边界 (attained/required 比值, MEPC.354(78) G4) ──
RATING_BOUNDARIES = {
    "A": (0.0, 0.86),
    "B": (0.86, 0.94),
    "C": (0.94, 1.07),
    "D": (1.07, 1.19),
    "E": (1.19, float("inf")),
}

# ── 年度折减系数 (Required CII = CII_ref × factor) ──
# 来源: 船舶风帆技术数据搜集表.xlsx / IMO CII 评级导则
YEAR_REDUCTION_FACTORS = {
    2023: 1.00,
    2024: 0.97,
    2025: 0.94,
    2026: 0.89,  # 目标降低 11%
}
DEFAULT_CII_YEAR = 2026

# ── MEPC.353(78) G2 Table 1: 船型参考线参数 ──
# CII_ref = a × Capacity^(-c), Capacity 单位 DWT 或 GT
# 来源: MEPC.353(78).pdf Page 5 Table 1
SHIP_TYPE_CII_PARAMS = {
    "bulk_carrier": {"a": 4745, "c": 0.622, "capacity_type": "DWT", "cap": 279000},
    "gas_carrier_small": {"a": 8104, "c": 0.639, "capacity_type": "DWT", "cap": None},
    "tanker": {"a": 5247, "c": 0.610, "capacity_type": "DWT", "cap": None},
    "container_ship": {"a": 1984, "c": 0.489, "capacity_type": "DWT", "cap": None},
    "general_cargo_large": {"a": 31948, "c": 0.792, "capacity_type": "DWT", "cap": None},
    "general_cargo_small": {"a": 588, "c": 0.3885, "capacity_type": "DWT", "cap": None},
    "refrigerated_cargo": {"a": 4600, "c": 0.557, "capacity_type": "DWT", "cap": None},
    "combination_carrier": {"a": 5119, "c": 0.622, "capacity_type": "DWT", "cap": None},
    "lng_carrier_large": {"a": 9.827, "c": 0.000, "capacity_type": "DWT", "cap": None},
    "roro_cargo_vehicle": {"a": 3627, "c": 0.590, "capacity_type": "GT", "cap": 57700},
    "roro_cargo": {"a": 1967, "c": 0.485, "capacity_type": "GT", "cap": None},
    "roro_passenger": {"a": 2023, "c": 0.460, "capacity_type": "GT", "cap": None},
    "high_speed_craft": {"a": 4196, "c": 0.460, "capacity_type": "GT", "cap": None},
    "cruise_passenger": {"a": 930, "c": 0.383, "capacity_type": "GT", "cap": None},
}


@dataclass
class CIIBaseline:
    """CII 基准值 (MEPC.353(78) G2)

    Attributes:
        ship_type:   船型键名 (SHIP_TYPE_CII_PARAMS 的 key)
        capacity:    船舶 Capacity (DWT 或 GT, 取决于船型)
        year:        评级年份
        source:      数据来源

    计算:
        CII_ref = a × Capacity^(-c)
        required_cii = CII_ref × year_factor
    """
    ship_type: str = "tanker"
    capacity: float = 300000.0  # KVLCC2 DWT
    year: int = DEFAULT_CII_YEAR
    source: str = "MEPC.353(78) G2 Table 1 + 年度折减系数"

    @property
    def params(self) -> dict:
        return SHIP_TYPE_CII_PARAMS[self.ship_type]

    @property
    def cii_ref(self) -> float:
        """2019 年参考线值 (gCO2/dwt·nm 或 gCO2/gt·nm)"""
        p = self.params
        cap = self.capacity
        if p["cap"] is not None:
            cap = min(cap, p["cap"])  # 散货船/车辆运输船有上限
        return p["a"] * (cap ** (-p["c"]))

    @property
    def year_factor(self) -> float:
        if self.year not in YEAR_REDUCTION_FACTORS:
            raise ValueError(
                f"year={self.year} 暂无已验证的 CII 折减系数，"
                f"支持年份: {tuple(YEAR_REDUCTION_FACTORS)}")
        return YEAR_REDUCTION_FACTORS[self.year]

    @property
    def required_cii(self) -> float:
        """该年度 required CII"""
        return self.cii_ref * self.year_factor

    # 向后兼容: phase_a_mvp.py 用 bl.required_cii_2024
    @property
    def required_cii_2024(self) -> float:
        old_year = self.year
        object.__setattr__(self, "year", 2024)
        val = self.required_cii
        object.__setattr__(self, "year", old_year)
        return val


def compute_cii(fuel_t: float, DWT: float, distance_nm: float,
                emission_factor: float = DEFAULT_EMISSION_FACTOR) -> float:
    """计算 attained CII (gCO2/dwt·nm)

    CII = (fuel × EF × 1e6) / (DWT × distance)

    Args:
        fuel_t:           航次油耗 (t)
        DWT:              载重吨 (t)
        distance_nm:      航次距离 (海里)
        emission_factor:  排放因子 (tCO2/tFuel)

    Returns:
        attained_cii: gCO2/dwt·nm
    """
    if DWT <= 0:
        raise ValueError(f"DWT={DWT} 必须为正")
    if distance_nm <= 0:
        raise ValueError(f"distance_nm={distance_nm} 必须为正")
    co2_t = fuel_t * emission_factor  # tCO2
    co2_g = co2_t * 1e6              # gCO2
    return co2_g / (DWT * distance_nm)


def cii_rating(attained_cii: float, required_cii: float) -> str:
    """CII 评级 (A/B/C/D/E)

    Args:
        attained_cii: 实际 CII 值
        required_cii: 要求 CII 值

    Returns:
        rating: A/B/C/D/E
    """
    if required_cii <= 0:
        raise ValueError(f"required_cii={required_cii} 必须为正")
    ratio = attained_cii / required_cii
    for rating, (lo, hi) in RATING_BOUNDARIES.items():
        if lo <= ratio < hi:
            return rating
    return "E"  # 兜底


def cii_improvement(baseline_cii: float, with_sail_cii: float) -> float:
    """CII 改善率

    improvement = (baseline - with_sail) / baseline × 100 (%)

    Args:
        baseline_cii:   无帆基线 CII
        with_sail_cii:  有帆 CII

    Returns:
        improvement_pct: 改善率 (%)，正值表示改善
    """
    if baseline_cii <= 0:
        raise ValueError(f"baseline_cii={baseline_cii} 必须为正")
    return (baseline_cii - with_sail_cii) / baseline_cii * 100.0


def annual_cii(fuel_t_per_year: float, DWT: float, distance_nm_per_year: float,
               emission_factor: float = DEFAULT_EMISSION_FACTOR) -> float:
    """年度 CII（基于全年总油耗与航行距离）

    Args:
        fuel_t_per_year:        年度油耗 (t)
        DWT:                    载重吨 (t)
        distance_nm_per_year:   年度航行距离 (nm)
        emission_factor:        排放因子

    Returns:
        annual_attained_cii: gCO2/dwt·nm
    """
    return compute_cii(fuel_t_per_year, DWT, distance_nm_per_year, emission_factor)
