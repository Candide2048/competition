# -*- coding: utf-8 -*-
"""ITTC 1957 摩擦阻力系数

公式:
    C_F = 0.075 / (log10(Re) - 2)^2

参考:
    ITTC 1957 Model-Ship Correlation Line
    https://wwwittc.org/publications/
"""
import numpy as np


def reynolds_number(V: float, L: float, nu: float) -> float:
    """计算雷诺数 Re = V·L / ν

    Args:
        V: 船速 (m/s)
        L: 特征长度 (m)，通常为垂线间长 L_pp
        nu: 流体运动粘度 (m²/s)

    Returns:
        Re: 雷诺数（无量纲）
    """
    return V * L / nu


def friction_coefficient(Re: float) -> float:
    """ITTC 1957 摩擦阻力系数 C_F

    C_F = 0.075 / (log10(Re) - 2)^2

    Args:
        Re: 雷诺数

    Returns:
        C_F: 摩擦阻力系数（无量纲，典型 1.5e-3 ~ 2.5e-3）
    """
    if Re <= 0:
        raise ValueError(f"Re={Re} 必须为正")
    return 0.075 / (np.log10(Re) - 2.0) ** 2
