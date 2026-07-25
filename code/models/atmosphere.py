# -*- coding: utf-8 -*-
"""大气物理模块

提供空气密度、风功率密度、风剪切等基础物理计算。
所有公式与 verify_physics_fix.py 中的 sanity check 保持一致。

公式:
    rho_air = msl / (R_specific × T_kelvin)
        T 必须用开尔文
        R_specific (干空气) = 287.05 J/(kg·K)

    wind_power_density = 0.5 × rho × ws³    (W/m²)

    wind_shear (log law):
        ws_h = ws_ref × ln(h / z0) / ln(h_ref / z0)
        z0: 海面粗糙度 ≈ 1.5e-4 m (open sea)
        h_ref: 参考高度 = 10 m (ERA5 u10/v10 标准)

参考:
    ⑤ Guzelbulut 2024 §2.2
    verify_physics_fix.py (复现 rho≈1.171, wpd≈326.1)
"""
import numpy as np


# 物理常数
R_SPECIFIC_AIR = 287.05  # 干空气比气体常数 J/(kg·K)
SEA_SURFACE_ROUGHNESS = 1.5e-4  # 开阔海面粗糙度 z0 (m)
ERA5_REFERENCE_HEIGHT = 10.0  # ERA5 u10/v10 参考高度 (m)


def rho_air(msl: float, sst: float) -> float:
    """计算空气密度 (kg/m³)

    Args:
        msl: 海平面气压 (Pa)，ERA5 单位
        sst: 海表温度 (K)，ERA5 单位（开尔文）

    Returns:
        rho_air: 空气密度 (kg/m³)

    注意: SST 必须用开尔文。ERA5 sst 默认即开尔文。
    典型热带海域值 1.15-1.22 kg/m³。
    """
    if sst <= 0:
        raise ValueError(f"sst={sst} K 异常，应为开尔文（>200K）")
    return msl / (R_SPECIFIC_AIR * sst)


def wind_speed(u10: float, v10: float) -> float:
    """计算 10m 风速 (m/s)

    Args:
        u10: 10m 东西向风分量 (m/s)
        v10: 10m 南北向风分量 (m/s)

    Returns:
        ws: 标量风速 (m/s)
    """
    return float(np.sqrt(u10 ** 2 + v10 ** 2))


def wind_direction(u10: float, v10: float) -> float:
    """计算风向 (rad，0=北风，顺时针)

    气象学约定：风向 = 风来的方向。
    若 u10>0 表示东风（风从东来），v10>0 表示北风。

    Args:
        u10, v10: 10m 风分量 (m/s)

    Returns:
        wind_dir: 风向 (rad)，[0, 2π)，0=北风，π/2=东风，π=南风，3π/2=西风
    """
    # 气象风向：风来的方向
    # atan2(u, -v) 让 0=北风（v10<0 表示从北吹向南）
    return float(np.arctan2(u10, -v10) % (2 * np.pi))


def wind_power_density(rho: float, ws: float) -> float:
    """计算风功率密度 (W/m²)

    wpd = 0.5 × rho × ws³

    Args:
        rho: 空气密度 (kg/m³)
        ws: 风速 (m/s)

    Returns:
        wpd: 风功率密度 (W/m²)
    """
    return 0.5 * rho * ws ** 3


def wind_shear_log(ws_ref: float, h_ref: float, h_target: float,
                   z0: float = SEA_SURFACE_ROUGHNESS) -> float:
    """对数律风剪切（将参考高度风速外推到目标高度）

    ws_h = ws_ref × ln(h/z0) / ln(h_ref/z0)

    Args:
        ws_ref: 参考高度风速 (m/s)
        h_ref: 参考高度 (m)，ERA5 默认 10
        h_target: 目标高度 (m)，Flettner 转子典型 20-30
        z0: 海面粗糙度 (m)，默认 1.5e-4

    Returns:
        ws_target: 目标高度风速 (m/s)
    """
    if h_target <= 0 or h_ref <= 0:
        raise ValueError("高度必须为正")
    if z0 <= 0:
        raise ValueError("粗糙度必须为正")
    return ws_ref * np.log(h_target / z0) / np.log(h_ref / z0)


def relative_wind(u10: float, v10: float,
                  V_ship_north: float, V_ship_east: float) -> tuple[float, float, float]:
    """计算相对风（视风）

    V_apparent = V_wind - V_ship

    Args:
        u10, v10: 真风分量 (m/s，东西/南北)
        V_ship_north: 船速南北分量 (m/s)
        V_ship_east: 船速东西分量 (m/s)

    Returns:
        tuple: (u_apparent, v_apparent, V_apparent_magnitude)
        - u_apparent: 视风东西分量 (m/s)
        - v_apparent: 视风南北分量 (m/s)
        - V_apparent: 视风风速 (m/s)
    """
    u_app = u10 - V_ship_east
    v_app = v10 - V_ship_north
    V_app = float(np.sqrt(u_app ** 2 + v_app ** 2))
    return (float(u_app), float(v_app), V_app)
