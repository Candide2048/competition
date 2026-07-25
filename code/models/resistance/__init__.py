# -*- coding: utf-8 -*-
"""阻力计算子包

包含:
- ittc1957: ITTC 1957 摩擦阻力系数
- holtrop_mennen: Holtrop-Mennen 1982 静水阻力方法
"""
from .ittc1957 import friction_coefficient, reynolds_number
from .holtrop_mennen import (
    HoltropMennenInput,
    compute_wet_surface,
    compute_resistance,
    load_kvlcc2_from_config,
)

__all__ = [
    "friction_coefficient",
    "reynolds_number",
    "HoltropMennenInput",
    "compute_wet_surface",
    "compute_resistance",
    "load_kvlcc2_from_config",
]
