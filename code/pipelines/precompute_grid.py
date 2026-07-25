# -*- coding: utf-8 -*-
"""物理层离线预计算 — 船型 × 航速 × 航线 × 季节 × 帆型

把 ERA5 逐小时积分的「物理层」（simulate_voyage 产出）离线扫描成矩阵缓存，
供交互仪表盘（app/dashboard.py）以 st.cache_data 秒级加载。经济性 / CII
后处理（evaluate_cell）为纯算术，留待前端按油价/碳价/成本滑杆实时重算，
不落盘（见 app/data_access.py）。

计算分层（架构核心）
    物理层（慢，ERA5 逐小时）  船型×航速×航线×季节×帆型  → 本脚本离线预计算
    后处理层（快，纯算术）      油价/碳价/成本/年运营小时/排放因子/CII船型 → 前端实时

只落物理层字段（与 simulate_voyage 返回一致 + 航次几何）:
    fuel_baseline_kg / fuel_with_sail_kg / fuel_saved_kg / saving_rate_pct
    mean_thrust_kN / mean_power_kW / mean_wind_ms / distance_nm / duration_h

固定量（写入 metadata，便于溯源）:
    代表船标准几何（无实船覆盖）、标准航速集、SFOC=0.180 kg/kWh、
    帆型实船典型台数 SAIL_INSTALL、Flettner 默认 24×4 规格。
    实船几何覆盖 / 非标准航速 / 非标准 SFOC → 前端 live 缓存重算，不进网格。

用法:
    python code/pipelines/precompute_grid.py               # 全网格
    python code/pipelines/precompute_grid.py --speeds 12 14 16
    python code/pipelines/precompute_grid.py --ships kvlcc2 container
    python code/pipelines/precompute_grid.py --out results/precomputed/physics_grid.json
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime

import numpy as np
import yaml

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.era5_loader import load_era5_from_config
from core.route_definition import haversine_distance, KM_TO_NM, KN_TO_MS
from core.ship_params import (
    load_ship_params_by_type,
    to_holtrop_input,
)
from core.owner_inputs import VALID_SHIP_TYPES, VALID_SAIL_TYPES
from models.resistance.holtrop_mennen import compute_resistance
from pipelines.phase_b_matrix import (
    build_sail,
    sample_route_weather,
    simulate_voyage,
    SAIL_INSTALL,
    ROUTES_CONFIG,
)
from pipelines.phase_b_full_voyage import generate_hourly_waypoints

# 标准航速集（不在集内的航速由前端 live 重算）
DEFAULT_SPEEDS_KN = [12.0, 14.0, 16.0]
# 物理层固定 SFOC（Norsepower 数据表标称 180 g/kWh VLSFO）
GRID_SFOC_KG_PER_KWH = 0.180
# Flettner 默认规格（几何标准化）
GRID_FLETTNER_SPEC = "24x4"

DEFAULT_OUTPUT = os.path.join(
    CODE_DIR, "results", "precomputed", "physics_grid.json"
)


def _load_routes_seasons():
    """读取 routes.yaml 的航线与季节定义"""
    with open(ROUTES_CONFIG, "r", encoding="utf-8") as f:
        rcfg = yaml.safe_load(f)
    return rcfg["routes"], rcfg["seasons"]


def compute_physics_grid(ships=VALID_SHIP_TYPES,
                         speeds=DEFAULT_SPEEDS_KN,
                         sail_types=VALID_SAIL_TYPES,
                         verbose: bool = True) -> dict:
    """扫描 船型×航速×航线×季节×帆型，只落物理层字段

    ERA5 只加载一次；船型阻力按 (船型, 航速) 复用；逐 (航线, 季节, 航速)
    采样一次天气后对 3 帆型复用。

    Returns:
        dict: {"metadata": {...}, "records": [ {ship, speed_kn, route,
               season, sail, + 物理字段} ... ]}
    """
    routes, seasons = _load_routes_seasons()

    # 预构造帆型对象（每类一次；Flettner 用标准规格）
    sails = {
        st: build_sail(st, GRID_FLETTNER_SPEC if st == "flettner" else None)
        for st in sail_types
    }

    # 船型标准几何摘要（供前端后处理还原 ship.DWT / ship_type_imo）
    ship_meta = {}
    ship_objs = {}
    for stype in ships:
        ship = load_ship_params_by_type(stype)
        ship_objs[stype] = ship
        ship_meta[stype] = {
            "DWT": ship.DWT,
            "ship_type_imo": ship.ship_type_imo,
            "GT": ship.GT,
            "L": ship.L, "B": ship.B, "T": ship.T, "C_B": ship.C_B,
            "V_design_kn": ship.V_design_kn,
        }

    n_cells = (len(ships) * len(speeds) * len(routes)
               * len(seasons) * len(sail_types))
    if verbose:
        print("=" * 72)
        print("物理层预计算 — 船型 × 航速 × 航线 × 季节 × 帆型")
        print(f"{len(ships)} 船型 × {len(speeds)} 航速 × {len(routes)} 航线 "
              f"× {len(seasons)} 季节 × {len(sail_types)} 帆型 = {n_cells} 格")
        print("=" * 72)

    if verbose:
        print("[加载 ERA5]...")
    t0 = time.time()
    era5 = load_era5_from_config()
    if verbose:
        print(f"        ERA5 加载耗时 {time.time() - t0:.1f} s\n")

    records = []
    t_start = time.time()
    try:
        for stype in ships:
            ship = ship_objs[stype]
            holtrop_inp = to_holtrop_input(ship)
            for speed in speeds:
                V_ship_ms = speed * KN_TO_MS
                # 船型阻力按 (船型, 航速) 复用
                R_total = compute_resistance(holtrop_inp, V_ship_ms)["R_total"]
                for rkey, rinfo in routes.items():
                    route_wps_def = [tuple(wp) for wp in rinfo["waypoints"]]
                    for skey, start_time in seasons.items():
                        waypoints = generate_hourly_waypoints(
                            route_wps_def, start_time, speed)
                        total_km = sum(
                            haversine_distance(
                                waypoints[i].lat, waypoints[i].lon,
                                waypoints[i + 1].lat, waypoints[i + 1].lon)
                            for i in range(len(waypoints) - 1)
                        )
                        total_nm = total_km * KM_TO_NM
                        duration_h = len(waypoints) - 1
                        weather = sample_route_weather(era5, waypoints)

                        for st in sail_types:
                            sail, n, uc, area, label = sails[st]
                            sim = simulate_voyage(
                                sail, n, waypoints, weather,
                                R_total, V_ship_ms, GRID_SFOC_KG_PER_KWH)
                            records.append({
                                "ship": stype,
                                "speed_kn": float(speed),
                                "route": rkey,
                                "season": skey,
                                "sail": st,
                                "distance_nm": round(total_nm, 1),
                                "duration_h": duration_h,
                                "fuel_baseline_kg": round(sim["fuel_baseline_kg"], 3),
                                "fuel_with_sail_kg": round(sim["fuel_with_sail_kg"], 3),
                                "fuel_saved_kg": round(sim["fuel_saved_kg"], 3),
                                "saving_rate_pct": round(sim["saving_rate_pct"], 4),
                                "mean_thrust_kN": round(sim["mean_thrust_kN"], 3),
                                "mean_power_kW": round(sim["mean_power_kW"], 3),
                                "mean_wind_ms": round(sim["mean_wind_ms"], 3),
                            })
                        if verbose:
                            done = len(records)
                            print(f"  [{stype:>9} {speed:>4.0f}kn | {rkey:>20} "
                                  f"| {skey:>6}] {total_nm:>5.0f}nm  "
                                  f"({done}/{n_cells})")
    finally:
        era5.close()

    result = {
        "metadata": {
            "pipeline": "Physics Grid (ship × speed × route × season × sail)",
            "generated_at": datetime.now().isoformat(),
            "era5_year": 2025,
            "sfoc_kg_per_kwh": GRID_SFOC_KG_PER_KWH,
            "flettner_spec": GRID_FLETTNER_SPEC,
            "speeds_kn": [float(s) for s in speeds],
            "ships": list(ships),
            "sail_types": list(sail_types),
            "sail_install": {st: SAIL_INSTALL[st] for st in sail_types},
            "ship_meta": ship_meta,
            "routes": {
                rkey: {"name": rinfo["name"],
                       "cargo": rinfo.get("cargo"),
                       "waypoints": [list(wp) for wp in rinfo["waypoints"]]}
                for rkey, rinfo in routes.items()
            },
            "seasons": dict(seasons),
            "n_records": len(records),
            "elapsed_s": round(time.time() - t_start, 1),
            "note": ("物理层字段来自 simulate_voyage，SFOC 固定；经济性/CII "
                     "由前端 evaluate_cell 后处理。代表船标准几何，实船覆盖走 "
                     "live 重算。"),
        },
        "records": records,
    }
    return result


def save_grid(result: dict, output_path: str = DEFAULT_OUTPUT) -> str:
    """写出 physics_grid.json（自动创建目录）"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return output_path


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="物理层离线预计算（船型×航速×航线×季节×帆型）")
    p.add_argument("--speeds", type=float, nargs="+", default=DEFAULT_SPEEDS_KN,
                   help="标准航速集 (kn)，默认 12 14 16")
    p.add_argument("--ships", type=str, nargs="+", default=list(VALID_SHIP_TYPES),
                   choices=list(VALID_SHIP_TYPES),
                   help="船型子集，默认全部 5 船型")
    p.add_argument("--sails", type=str, nargs="+", default=list(VALID_SAIL_TYPES),
                   choices=list(VALID_SAIL_TYPES),
                   help="帆型子集，默认全部 3 帆型")
    p.add_argument("--out", type=str, default=DEFAULT_OUTPUT,
                   help="输出 JSON 路径")
    p.add_argument("--quiet", action="store_true", help="静默模式")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    result = compute_physics_grid(
        ships=tuple(args.ships),
        speeds=list(args.speeds),
        sail_types=tuple(args.sails),
        verbose=not args.quiet,
    )
    out = save_grid(result, args.out)
    meta = result["metadata"]
    print(f"\n物理层网格已保存: {out}")
    print(f"  {meta['n_records']} 条记录，耗时 {meta['elapsed_s']} s")


if __name__ == "__main__":
    main()
