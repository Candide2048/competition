# -*- coding: utf-8 -*-
"""航线定义模块

提供:
- 航路点 (Waypoint) 数据结构
- 大圆距离计算 (Haversine 公式)
- 航线分段 (按时间或距离插值)
- 航向角计算 (initial bearing)

参考:
    ④ 计明军 2023 场景2: (29°N, 49°E) → (24°N, 60°E), 70h, 14kn
    KVLCC2 设计航速 14 kn
"""
import math
from dataclasses import dataclass

import numpy as np


# 地球半径
EARTH_RADIUS_NM = 3440.065  # 海里
EARTH_RADIUS_KM = 6371.0    # 公里
EARTH_RADIUS_M = 6371000.0  # 米

# 单位换算
KN_TO_MS = 0.51444         # 1 kn = 0.51444 m/s
MS_TO_KN = 1.0 / KN_TO_MS  # 1 m/s = 1.94384 kn
KM_TO_NM = 0.539957        # 1 km = 0.539957 nm


@dataclass
class Waypoint:
    """地理航路点

    Attributes:
        lat: 纬度 (度，北正南负)
        lon: 经度 (度，东正西负)
        time: 到达时间 (np.datetime64 或 None)
    """
    lat: float
    lon: float
    time: object = None  # np.datetime64 或 None


def haversine_distance(lat1: float, lon1: float,
                       lat2: float, lon2: float,
                       radius: float = EARTH_RADIUS_KM) -> float:
    """Haversine 大圆距离

    Args:
        lat1, lon1: 起点 (度)
        lat2, lon2: 终点 (度)
        radius: 地球半径 (km 默认)

    Returns:
        距离 (与 radius 单位一致)
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(a))


def initial_bearing(lat1: float, lon1: float,
                    lat2: float, lon2: float) -> float:
    """初始航向角 (大圆航向)

    Args:
        lat1, lon1: 起点 (度)
        lat2, lon2: 终点 (度)

    Returns:
        bearing: 航向角 (rad，0=正北，顺时针)
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(dlam))
    return math.atan2(y, x) % (2 * math.pi)


def ship_velocity_components(V_ship_ms: float, heading_rad: float) -> tuple[float, float]:
    """将船速分解为东西/南北分量

    Args:
        V_ship_ms: 船速 (m/s)
        heading_rad: 航向 (rad，0=正北，顺时针)

    Returns:
        (V_east, V_north): 东西/南北分量 (m/s)
    """
    V_east = V_ship_ms * np.sin(heading_rad)
    V_north = V_ship_ms * np.cos(heading_rad)
    return (float(V_east), float(V_north))


def interpolate_route(start: Waypoint, end: Waypoint,
                      n_steps: int) -> list[Waypoint]:
    """沿大圆航线插值航路点（球面插值）

    使用球面线性插值 (Slerp 近似)：对经纬度做大圆弧插值，
    避免线性 lat/lon 插值在长航线 (>1000nm) 上的纬度偏差。

    Args:
        start: 起点航路点
        end: 终点航路点
        n_steps: 插值点数（含起终点）

    Returns:
        list[Waypoint]: 插值航路点列表
    """
    if n_steps < 2:
        raise ValueError("n_steps 必须 ≥ 2")

    lat1, lon1 = np.radians(start.lat), np.radians(start.lon)
    lat2, lon2 = np.radians(end.lat), np.radians(end.lon)

    # 大圆角距 d
    d_lon = lon2 - lon1
    cos_d = (np.sin(lat1) * np.sin(lat2) +
             np.cos(lat1) * np.cos(lat2) * np.cos(d_lon))
    d = np.arccos(np.clip(cos_d, -1.0, 1.0))  # clip 防止浮点误差

    waypoints = []
    for i in range(n_steps):
        f = i / (n_steps - 1)

        if d < 1e-10:
            # 起终点几乎重合，线性回退
            lat = start.lat + f * (end.lat - start.lat)
            lon = start.lon + f * (end.lon - start.lon)
        else:
            # 大圆弧插值（Vincenty-like intermediate point）
            a = np.sin((1 - f) * d) / np.sin(d)
            b = np.sin(f * d) / np.sin(d)
            x = a * np.cos(lat1) * np.cos(lon1) + b * np.cos(lat2) * np.cos(lon2)
            y = a * np.cos(lat1) * np.sin(lon1) + b * np.cos(lat2) * np.sin(lon2)
            z = a * np.sin(lat1) + b * np.sin(lat2)
            lat = np.degrees(np.arctan2(z, np.sqrt(x**2 + y**2)))
            lon = np.degrees(np.arctan2(y, x))

        # 时间插值（若起终点都有时间）
        wp_time = None
        if start.time is not None and end.time is not None:
            dt = (end.time - start.time) / (n_steps - 1)
            wp_time = start.time + int(i) * dt
        waypoints.append(Waypoint(lat=lat, lon=lon, time=wp_time))
    return waypoints


def route_total_distance(waypoints: list[Waypoint]) -> float:
    """航路点序列总距离 (km)

    Args:
        waypoints: 航路点列表

    Returns:
        总距离 (km)
    """
    if len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        total += haversine_distance(
            waypoints[i].lat, waypoints[i].lon,
            waypoints[i + 1].lat, waypoints[i + 1].lon
        )
    return total


def route_duration_hours(distance_km: float, V_ship_ms: float) -> float:
    """航程时长 (小时)

    Args:
        distance_km: 距离 (km)
        V_ship_ms: 船速 (m/s)

    Returns:
        时长 (h)
    """
    if V_ship_ms <= 0:
        raise ValueError("船速必须为正")
    return (distance_km * 1000.0 / V_ship_ms) / 3600.0


def estimate_route_steps(distance_km: float, V_ship_ms: float,
                         dt_hours: float = 1.0) -> int:
    """估算航路点数（按时间间隔）

    Args:
        distance_km: 距离 (km)
        V_ship_ms: 船速 (m/s)
        dt_hours: 时间间隔 (h)，默认 1h（ERA5 时间分辨率）

    Returns:
        n_steps: 航路点数（含起终点）
    """
    duration = route_duration_hours(distance_km, V_ship_ms)
    n = int(np.ceil(duration / dt_hours)) + 1
    return max(n, 2)


# 计明军场景2 锚点
JI_SCENARIO_2_START = Waypoint(lat=29.0, lon=49.0)
JI_SCENARIO_2_END = Waypoint(lat=24.0, lon=60.0)
JI_SCENARIO_2_DISTANCE_KM = haversine_distance(29.0, 49.0, 24.0, 60.0)
JI_SCENARIO_2_DURATION_H = 70.0
JI_SCENARIO_2_FUEL_T = 89.2
