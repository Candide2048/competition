# -*- coding: utf-8 -*-
"""智能分析层

包含:
- fuel_saving: 节油量与碳减排（高级封装）
- cii: CII 评级与改善率
- economics: NPV/回收期/敏感性
"""
from .fuel_saving import (
    compute_fuel_saving,
    compute_carbon_reduction,
    FuelSavingResult,
)
from .cii import (
    compute_cii,
    cii_rating,
    cii_improvement,
    CIIBaseline,
)
from .economics import (
    initial_cost,
    annual_savings,
    npv,
    payback_period,
    sensitivity,
)

__all__ = [
    "compute_fuel_saving",
    "compute_carbon_reduction",
    "FuelSavingResult",
    "compute_cii",
    "cii_rating",
    "cii_improvement",
    "CIIBaseline",
    "initial_cost",
    "annual_savings",
    "npv",
    "payback_period",
    "sensitivity",
]
