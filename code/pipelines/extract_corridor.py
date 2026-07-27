# -*- coding: utf-8 -*-
"""ERA5 航线走廊预抽取 CLI（生成 era5_corridor_v1.npz）

从全域 ERA5 .nc（约 4.5 GB，仅本地开发机可用）抽取 routes.yaml 全部航线的
走廊网格 × 4 季节 × 719 小时窗口，压缩为约 27 MiB 的 NPZ 随 git 分发，
供 core.corridor_era5.CorridorERA5 在无 .nc 的部署环境提供 live 物理重算。

走廊几何（超集安全）:
    独立经纬 nearest 采样下，航迹点(线性插值，恒在折线上)命中的 cell 的
    Voronoi 区域是以 cell 为中心的 0.25°×0.25° 矩形。矩形任一点到中心距离
    ≤ √2×0.125°，故收集「中心到任一航线段距离 ≤ √2×0.125°+ε」的 cell
    即覆盖全部可能命中；再用 8-18kn/0.5 全航速真实航迹扫描断言子集。

时间窗（719h = 偏移 0..718）:
    最长航线 middle_east_china 全程 ~5545 nm，8 kn 需 ~695 个逐时采样
    （偏移 0..694），719h 窗口留有 24h 余量；autumn 窗口末端偏移
    6888+718=7606 < 8760，全年数据覆盖。

用法:
    python pipelines/extract_corridor.py            # 生成/覆盖默认输出
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import yaml

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE_DIR)

from core.era5_loader import load_era5_from_config
from core.corridor_era5 import (
    SCHEMA_VERSION, EPOCH, WEATHER_VARS, DEFAULT_NPZ_PATH, nearest_index,
)
from pipelines.phase_b_full_voyage import generate_hourly_waypoints

ROUTES_CONFIG = os.path.join(CODE_DIR, "config", "routes.yaml")
WINDOW_HOURS = 719          # 偏移 0..718
CORRIDOR_RADIUS_DEG = np.sqrt(2.0) * 0.125 + 1e-6
SCAN_SPEEDS_KN = [8.0 + 0.5 * i for i in range(21)]   # 8.0..18.0
MAX_NPZ_MIB = 50.0


def _point_segment_dist_deg(px, py, ax, ay, bx, by):
    """点到线段的欧氏距离（经纬度平面近似，与航迹线性插值同一几何空间）"""
    apx, apy = px - ax, py - ay
    abx, aby = bx - ax, by - ay
    ab2 = abx * abx + aby * aby
    t = 0.0 if ab2 == 0.0 else max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    dx, dy = px - (ax + t * abx), py - (ay + t * aby)
    return float(np.hypot(dx, dy))


def collect_corridor_cells(routes: dict, lat_axis: np.ndarray,
                           lon_axis: np.ndarray) -> list[tuple[int, int]]:
    """几何法收集走廊 cell 索引（按 (lat_idx, lon_idx) 排序）"""
    segments = []
    for cfg in routes.values():
        wps = cfg["waypoints"]
        for a, b in zip(wps[:-1], wps[1:]):
            segments.append((float(a[0]), float(a[1]), float(b[0]), float(b[1])))

    cells = set()
    for li, lat in enumerate(lat_axis):
        # 剪枝：先按纬度粗筛（cell 距任一段的纬度差超半径则不可能命中）
        near = [s for s in segments
                if min(abs(lat - s[0]), abs(lat - s[2])) <= CORRIDOR_RADIUS_DEG
                or (min(s[0], s[2]) - CORRIDOR_RADIUS_DEG <= lat
                    <= max(s[0], s[2]) + CORRIDOR_RADIUS_DEG)]
        if not near:
            continue
        for oi, lon in enumerate(lon_axis):
            for ay, ax, by, bx in near:
                if _point_segment_dist_deg(float(lon), float(lat),
                                           ax, ay, bx, by) <= CORRIDOR_RADIUS_DEG:
                    cells.add((li, oi))
                    break
    return sorted(cells)


def scan_assert_subset(routes: dict, seasons: dict, lat_axis: np.ndarray,
                       lon_axis: np.ndarray, cell_set: set) -> int:
    """8-18kn 全航速真实航迹扫描：断言全部命中 cell ⊂ 走廊，返回最大时间偏移"""
    max_offset = 0
    for route_key, cfg in routes.items():
        wps = [(float(p[0]), float(p[1])) for p in cfg["waypoints"]]
        for season, start in seasons.items():
            start64 = np.datetime64(start)
            start_hour = int((start64 - EPOCH) / np.timedelta64(1, "h"))
            for spd in SCAN_SPEEDS_KN:
                voyage = generate_hourly_waypoints(wps, start, V_ship_kn=spd)
                for wp in voyage:
                    li = nearest_index(lat_axis, wp.lat)
                    oi = nearest_index(lon_axis, wp.lon)
                    if (li, oi) not in cell_set:
                        raise AssertionError(
                            f"扫描发现走廊外命中: route={route_key} season={season} "
                            f"speed={spd} wp=({wp.lat:.4f},{wp.lon:.4f}) "
                            f"cell=({li},{oi})")
                off = int((np.datetime64(voyage[-1].time) - EPOCH)
                          / np.timedelta64(1, "h")) - start_hour
                max_offset = max(max_offset, off)
    return max_offset


def main() -> None:
    t0 = time.time()
    with open(ROUTES_CONFIG, "rb") as f:
        routes_bytes = f.read()
    cfg = yaml.safe_load(routes_bytes.decode("utf-8"))
    routes, seasons = cfg["routes"], cfg["seasons"]

    era5 = load_era5_from_config()
    try:
        lat_axis = np.asarray(era5.merged["latitude"].values, dtype=np.float64)
        lon_axis = np.asarray(era5.merged["longitude"].values, dtype=np.float64)
        time_axis = np.asarray(era5.merged["valid_time"].values)
        assert lat_axis.shape == (201,) and lon_axis.shape == (401,), \
            f"网格轴形状异常: {lat_axis.shape} / {lon_axis.shape}"
        # 时间轴必须是自 EPOCH 起的连续整点（索引即小时偏移）
        hours_axis = ((time_axis - EPOCH) / np.timedelta64(1, "h")).astype(np.int64)
        assert hours_axis[0] == 0 and np.all(np.diff(hours_axis) == 1), \
            "ERA5 时间轴不是自 2025-01-01T00 起的连续整点"

        # ① 几何走廊
        cells = collect_corridor_cells(routes, lat_axis, lon_axis)
        cell_set = set(cells)
        print(f"[1/4] 几何走廊 cell 数: {len(cells)}")

        # ② 真实航迹扫描断言（空间子集 + 时间窗余量）
        max_offset = scan_assert_subset(routes, seasons, lat_axis, lon_axis,
                                        cell_set)
        assert max_offset + 24 <= WINDOW_HOURS - 1, \
            f"最大时间偏移 {max_offset} 超出窗口余量 (窗口 {WINDOW_HOURS}h)"
        print(f"[2/4] 全航速扫描通过, 最大时间偏移 {max_offset}h "
              f"(窗口 {WINDOW_HOURS}h)")

        # ③ 抽取 4 季节 × WINDOW_HOURS × cells 天气
        season_names = list(seasons.keys())
        season_start_hour = []
        for s in season_names:
            h = int((np.datetime64(seasons[s]) - EPOCH) / np.timedelta64(1, "h"))
            assert h + WINDOW_HOURS <= len(hours_axis), \
                f"季节 {s} 窗口越过数据末端: {h}+{WINDOW_HOURS} > {len(hours_axis)}"
            season_start_hour.append(h)

        lat_idx = np.array([c[0] for c in cells], dtype=np.int64)
        lon_idx = np.array([c[1] for c in cells], dtype=np.int64)
        weather = np.empty(
            (len(season_names), WINDOW_HOURS, len(cells), len(WEATHER_VARS)),
            dtype=np.float32)
        for si, (s, h0) in enumerate(zip(season_names, season_start_hour)):
            sub = era5.merged.isel(valid_time=slice(h0, h0 + WINDOW_HOURS))
            for vi, var in enumerate(WEATHER_VARS):
                arr = sub[var].values          # [W, 201, 401]
                weather[si, :, :, vi] = arr[:, lat_idx, lon_idx]
            print(f"    季节 {s}: 起点小时 {h0}, 抽取完成")
        print(f"[3/4] 天气抽取完成, NaN 占比 "
              f"{float(np.isnan(weather).mean()) * 100:.2f}% (sst 陆地格点)")
    finally:
        era5.close()

    # ④ 打包（manifest + payload 哈希 + 原子替换）
    payload_sha256 = hashlib.sha256(weather.tobytes()).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "routes_sha256": hashlib.sha256(routes_bytes).hexdigest(),
        "n_cells": len(cells),
        "window_hours": WINDOW_HOURS,
        "season_names": season_names,
        "corridor_radius_deg": CORRIDOR_RADIUS_DEG,
        "scan_speeds_kn": [SCAN_SPEEDS_KN[0], SCAN_SPEEDS_KN[-1], 0.5],
        "max_scan_offset_h": max_offset,
        "payload_sha256": payload_sha256,
    }
    manifest_arr = np.frombuffer(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        dtype=np.uint8).copy()

    out_path = DEFAULT_NPZ_PATH
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp_path = out_path + ".tmp"
    np.savez_compressed(
        tmp_path,
        manifest_json=manifest_arr,
        grid_latitude=lat_axis,
        grid_longitude=lon_axis,
        cell_lat_idx=lat_idx.astype(np.uint8),
        cell_lon_idx=lon_idx.astype(np.uint16),
        season_names=np.array(season_names),
        season_start_hour=np.array(season_start_hour, dtype=np.int32),
        hour_offset=np.arange(WINDOW_HOURS, dtype=np.uint16),
        weather=weather,
    )
    # np.savez_compressed 追加 .npz 后缀
    tmp_npz = tmp_path if tmp_path.endswith(".npz") else tmp_path + ".npz"
    size_mib = os.path.getsize(tmp_npz) / (1024 * 1024)
    assert size_mib <= MAX_NPZ_MIB, f"NPZ 体积 {size_mib:.2f} MiB 超限"
    os.replace(tmp_npz, out_path)
    print(f"[4/4] 写入 {out_path} ({size_mib:.2f} MiB), "
          f"耗时 {time.time() - t0:.1f}s")

    # 回读自校验（哈希 + schema）
    from core.corridor_era5 import CorridorERA5
    c = CorridorERA5(out_path)
    assert len(c.cell_lat_idx) == len(cells)
    print(f"回读校验通过: {len(cells)} cells, "
          f"payload_sha256={payload_sha256[:12]}...")


if __name__ == "__main__":
    main()
