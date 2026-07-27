# -*- coding: utf-8 -*-
"""情景洞察离线预计算 — 900 情景的不确定性区间 + 风资源摘要

在 physics_grid.json（点估计）之外补第二份预计算产物：
    code/results/precomputed/scenario_insights.json

每条 record 对应 physics_grid 的一格（船型×航速×航线×季节×帆型），含:
    uncertainty    24h circular block bootstrap 分位数摘要
                   （analytics.uncertainty.summarize_bootstrap_hourly）
    wind_resource  风速/相对风角分布与有效推力小时占比
                   （analytics.wind_resource.summarize_wind_resource）

计算分层（与 precompute_grid 一致）:
    hourly 数组只在本脚本内存中使用，不写入 JSON（只落分位数/直方图摘要），
    线上 API 纯查表 + 经济性算术后处理，不加载 ERA5/NetCDF。

用法:
    python code/pipelines/precompute_scenario_insights.py
    python code/pipelines/precompute_scenario_insights.py --ships kvlcc2
    python code/pipelines/precompute_scenario_insights.py \
        --bootstrap-samples 500 --block-hours 24
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime

import yaml

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.era5_loader import load_era5_from_config
from core.route_definition import KN_TO_MS
from core.ship_params import load_ship_params_by_type, to_holtrop_input
from core.owner_inputs import VALID_SHIP_TYPES, VALID_SAIL_TYPES
from models.resistance.holtrop_mennen import compute_resistance
from analytics.uncertainty import (
    summarize_bootstrap_hourly,
    DEFAULT_BLOCK_H, DEFAULT_N_SAMPLES, DEFAULT_SEED,
)
from analytics.wind_resource import summarize_wind_resource
from pipelines.phase_b_matrix import (
    build_sail,
    sample_route_weather,
    simulate_voyage,
    ROUTES_CONFIG,
)
from pipelines.phase_b_full_voyage import generate_hourly_waypoints
from pipelines.precompute_grid import (
    DEFAULT_SPEEDS_KN,
    GRID_SFOC_KG_PER_KWH,
    GRID_FLETTNER_SPEC,
)

DEFAULT_OUTPUT = os.path.join(
    CODE_DIR, "results", "precomputed", "scenario_insights.json"
)


def scenario_key(ship: str, speed_kn: float, route: str,
                 season: str, sail: str) -> str:
    """record 的查表主键（与 app.data_access.pick_insight 对齐）"""
    return f"{ship}|{float(speed_kn):.1f}|{route}|{season}|{sail}"


def compute_scenario_insights(ships=VALID_SHIP_TYPES,
                              speeds=DEFAULT_SPEEDS_KN,
                              sail_types=VALID_SAIL_TYPES,
                              block_h: int = DEFAULT_BLOCK_H,
                              n_samples: int = DEFAULT_N_SAMPLES,
                              seed: int = DEFAULT_SEED,
                              verbose: bool = True) -> dict:
    """扫描 船型×航速×航线×季节×帆型，落 uncertainty + wind_resource 摘要

    ERA5 只加载一次；天气按 (航线, 季节, 航速) 缓存复用（与船型无关）；
    船型阻力按 (船型, 航速) 复用。
    """
    with open(ROUTES_CONFIG, "r", encoding="utf-8") as f:
        rcfg = yaml.safe_load(f)
    routes, seasons = rcfg["routes"], rcfg["seasons"]

    sails = {
        st: build_sail(st, GRID_FLETTNER_SPEC if st == "flettner" else None)
        for st in sail_types
    }

    n_cells = (len(ships) * len(speeds) * len(routes)
               * len(seasons) * len(sail_types))
    if verbose:
        print("=" * 72)
        print("情景洞察预计算 — uncertainty + wind_resource")
        print(f"{len(ships)} 船型 × {len(speeds)} 航速 × {len(routes)} 航线 "
              f"× {len(seasons)} 季节 × {len(sail_types)} 帆型 = {n_cells} 格")
        print(f"bootstrap: block={block_h}h × {n_samples} 样本, seed={seed}")
        print("=" * 72)

    if verbose:
        print("[加载 ERA5]...")
    t0 = time.time()
    era5 = load_era5_from_config()
    if verbose:
        print(f"        ERA5 加载耗时 {time.time() - t0:.1f} s\n")

    # (route, season, speed) → (waypoints, weather)，与船型无关
    weather_cache: dict = {}
    records = []
    t_start = time.time()
    try:
        for stype in ships:
            ship = load_ship_params_by_type(stype)
            holtrop_inp = to_holtrop_input(ship)
            for speed in speeds:
                V_ship_ms = speed * KN_TO_MS
                R_total = compute_resistance(holtrop_inp, V_ship_ms)["R_total"]
                for rkey, rinfo in routes.items():
                    route_wps_def = [tuple(wp) for wp in rinfo["waypoints"]]
                    for skey, start_time in seasons.items():
                        ck = (rkey, skey, float(speed))
                        if ck not in weather_cache:
                            wps = generate_hourly_waypoints(
                                route_wps_def, start_time, speed)
                            weather_cache[ck] = (
                                wps, sample_route_weather(era5, wps))
                        waypoints, weather = weather_cache[ck]

                        for st in sail_types:
                            sail, n, _uc, _area, _label = sails[st]
                            sim = simulate_voyage(
                                sail, n, waypoints, weather,
                                R_total, V_ship_ms, GRID_SFOC_KG_PER_KWH,
                                collect_hourly=True)
                            hourly = sim["hourly"]
                            records.append({
                                "ship": stype,
                                "speed_kn": float(speed),
                                "route": rkey,
                                "season": skey,
                                "sail": st,
                                "duration_h": int(len(waypoints) - 1),
                                "uncertainty": summarize_bootstrap_hourly(
                                    hourly, block_h=block_h,
                                    n_samples=n_samples, seed=seed),
                                "wind_resource": summarize_wind_resource(
                                    hourly),
                            })
                        if verbose:
                            done = len(records)
                            print(f"  [{stype:>9} {speed:>4.0f}kn | {rkey:>20}"
                                  f" | {skey:>6}]  ({done}/{n_cells})")
    finally:
        era5.close()

    return {
        "metadata": {
            "pipeline": ("Scenario Insights "
                         "(uncertainty + wind_resource per grid cell)"),
            "generated_at": datetime.now().isoformat(),
            "weather_years": [2025],
            "sfoc_kg_per_kwh": GRID_SFOC_KG_PER_KWH,
            "flettner_spec": GRID_FLETTNER_SPEC,
            "speeds_kn": [float(s) for s in speeds],
            "ships": list(ships),
            "sail_types": list(sail_types),
            "bootstrap": {
                "method": f"{block_h}h circular block bootstrap",
                "block_h": int(block_h),
                "n_samples": int(n_samples),
                "seed": int(seed),
            },
            "n_records": len(records),
            "elapsed_s": round(time.time() - t_start, 1),
            "note": ("摘要基于单年（2025）ERA5 沿航线逐小时采样的 bootstrap，"
                     "量化日间风场组合不确定性，不覆盖年际气候变率。"
                     "物理口径与 physics_grid.json 完全同源（simulate_voyage）。"
                     "经济性分位数由 API 按当前油价/碳价/成本实时后处理。"),
        },
        "records": records,
    }


def save_insights(result: dict, output_path: str = DEFAULT_OUTPUT) -> str:
    """写出 scenario_insights.json（自动创建目录）"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, default=str)
    return output_path


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="情景洞察预计算（uncertainty + wind_resource）")
    p.add_argument("--speeds", type=float, nargs="+", default=DEFAULT_SPEEDS_KN)
    p.add_argument("--ships", type=str, nargs="+",
                   default=list(VALID_SHIP_TYPES),
                   choices=list(VALID_SHIP_TYPES))
    p.add_argument("--sails", type=str, nargs="+",
                   default=list(VALID_SAIL_TYPES),
                   choices=list(VALID_SAIL_TYPES))
    p.add_argument("--block-hours", type=int, default=DEFAULT_BLOCK_H)
    p.add_argument("--bootstrap-samples", type=int, default=DEFAULT_N_SAMPLES)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--out", type=str, default=DEFAULT_OUTPUT)
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    result = compute_scenario_insights(
        ships=tuple(args.ships),
        speeds=list(args.speeds),
        sail_types=tuple(args.sails),
        block_h=args.block_hours,
        n_samples=args.bootstrap_samples,
        seed=args.seed,
        verbose=not args.quiet,
    )
    out = save_insights(result, args.out)
    meta = result["metadata"]
    size_mb = os.path.getsize(out) / 1e6
    print(f"\n情景洞察已保存: {out}")
    print(f"  {meta['n_records']} 条记录，耗时 {meta['elapsed_s']} s，"
          f"文件 {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
