# -*- coding: utf-8 -*-
"""Phase B 效益矩阵 — 航线 × 季节 × 帆型

在 Phase B 单航线仿真基础上，构建「航线 × 季节情景 × 3 帆型」三维效益矩阵，
用于对比三种风帆辅助推进技术（Flettner 旋筒帆 / 刚性翼帆 / 吸力帆）在
不同地理走廊与季风季节下的节油率、CO2 减排、CII 改善与经济性稳健性。

核心方法（与 phase_b_full_voyage 一致，已含转子功耗修正）:
    逐小时 ERA5 风况 → 相对风 → 帆最优控制 → 推力平衡（扣除转子电力油耗）
    → 节油/CO2/CII/经济性

帆型安装配置（基于实船参考，见 config/sail_types.yaml performance 段）:
    Flettner:  4 台 × 96 m²  (Maersk Pelican 2×24×4 → 放大到 4 台)
    刚性翼帆:  4 台 × 750 m² (Berge Olympus / New Aden 4×大型翼帆)
    吸力帆:    6 台 × 66 m²  (Pacific Sentinel 3-4 台 → 放大到 6 台小帆)
    → 三者「CL×S」等效力容量量级相近，构成公平对比。

数据:
    ERA5 2025 全年 (30°E–130°E, 10°S–40°N, 逐小时), 只加载一次
    config/routes.yaml (5 航线 × 4 季节)
    config/sail_types.yaml (三帆型气动 + 单台成本)

参考:
    ⑤ Guzelbulut 2024 / IET Song 2025 / 赵大刚 2026 综述 / bound4blue eSAIL
    MEPC.353(78) G2 (CII 参考线)
"""
import os
import sys
import json
import time
from datetime import datetime

import numpy as np
import yaml

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE_DIR)

from core.era5_loader import load_era5_from_config
from core.route_definition import haversine_distance, KM_TO_NM, KN_TO_MS, ship_velocity_components
from core.ship_params import (
    load_ship_params,
    load_ship_params_by_type,
    apply_geometry_overrides,
    to_holtrop_input,
)
from core.owner_inputs import OwnerInputs
from models.aerodynamics.flettner import FlettnerSail, FlettnerConfig
from models.aerodynamics.rigid_wing import RigidWingSail
from models.aerodynamics.suction_sail import SuctionSail
from models.atmosphere import rho_air, relative_wind
from models.resistance.holtrop_mennen import compute_resistance
from models.thrust_balance import solve_balance
from analytics.cii import CIIBaseline, compute_cii, cii_rating, cii_improvement, DEFAULT_EMISSION_FACTOR
from analytics.economics import initial_cost, annual_savings, payback_period, npv, sensitivity

from pipelines.phase_b_full_voyage import generate_hourly_waypoints

ROUTES_CONFIG = os.path.join(CODE_DIR, "config", "routes.yaml")
SAIL_CONFIG = os.path.join(CODE_DIR, "config", "sail_types.yaml")

DEFAULT_V_SHIP_KN = 14.0
# 年度海上运营小时数：VLCC 典型在航率约 74%（≈271 天/年），其余为港口/维护/压载。
# 按航次时长换算年航次数（trips = 年运营小时 / 航次时长），短航线→更多航次。
# 避免固定航次数在短航线上严重低估年节省、导致回收期虚高（原固定 3 航次
# 使 1430 nm 短航线回收期高达上百年，非物理）。
ANNUAL_OPERATING_HOURS = 6500.0

# 帆型安装台数 — 实船典型配置
# 基于实际安装案例而非等面积归一化，反映船东真实决策场景：
# - Flettner: 4台 (24×4)，典型大型船舶配置 (Maersk Pelican 2台, Viking Grace 1台,
#   Copenhagen 5台; 4台为大型船舶合理中值); 总面积 4×96=384 m²
# - 翼帆: 1台 (37.5×20m)，当前商用安装为 2-4台但单台即代表典型最小单元;
#   总面积 1×750=750 m²
# - 吸力帆: 6台 (22×3m)，典型安装 (Ville de Bordeaux 3台, Maersk 5船南4台/船);
#   总面积 6×66=396 m²
# 注意: 不再等面积归一化，而是反映实际安装规模和成本，
# 允许帆型间总面积差异——这正是船东需要权衡的真实因素。
SAIL_INSTALL = {
    "flettner": 4,
    "rigid_wing": 1,
    "suction_wing": 6,
}


def build_sail(sail_type: str, flettner_spec: str | None = None):
    """构造帆型对象，返回 (sail, n_sails, unit_cost_usd, total_area, label)

    Args:
        sail_type: "flettner" / "rigid_wing" / "suction_wing"
        flettner_spec: 仅对 flettner 生效。若为 Norsepower 标准规格名
            ("20x4"/"24x4"/"28x4"/"30x5"/"35x5")，则从 specifications 加载
            几何与单台成本；None 则用默认 geometry (24×4)。
    """
    with open(SAIL_CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    n = SAIL_INSTALL[sail_type]
    unit_cost = float(cfg[sail_type]["cost"]["unit_cost_usd"])
    if sail_type == "flettner":
        specs = cfg["flettner"].get("specifications", {})
        if flettner_spec is not None:
            if flettner_spec not in specs:
                raise ValueError(
                    f"未知 Flettner 规格: {flettner_spec}，可选 {list(specs)}")
            g = specs[flettner_spec]
            unit_cost = float(g.get("unit_cost_usd", unit_cost))
            spec_label = flettner_spec
        else:
            g = cfg["flettner"]["geometry"]
            spec_label = "24x4"
        sail = FlettnerSail(FlettnerConfig(H=g["H"], D=g["D"], AR=g["AR"], D_e_D=g["D_e_D"]))
        area = sail.projected_area
        label = f"Flettner 旋筒帆 ({spec_label})"
    elif sail_type == "rigid_wing":
        sail = RigidWingSail.from_config()
        area = sail.projected_area
        label = "刚性翼帆"
    elif sail_type == "suction_wing":
        sail = SuctionSail.from_config()
        area = sail.projected_area
        label = "吸力帆"
    else:
        raise ValueError(f"未知帆型: {sail_type}")
    return sail, n, unit_cost, area, label


def _fill_nan(arr, fallback):
    n_nan = int(np.isnan(arr).sum())
    if n_nan == 0:
        return arr
    if n_nan == arr.size:
        return np.full_like(arr, fallback)
    idx = np.arange(arr.size)
    valid = ~np.isnan(arr)
    return np.interp(idx, idx[valid], arr[valid])


def sample_route_weather(era5, waypoints):
    """沿航路点采样 ERA5，返回 (u10, v10, msl, sst) 数组（已填补 NaN）"""
    lats = [wp.lat for wp in waypoints]
    lons = [wp.lon for wp in waypoints]
    times = [wp.time for wp in waypoints]
    ds = era5.sample_route(list(zip(lats, lons)), times)
    u10 = _fill_nan(np.array(ds["u10"].values, dtype=float), 0.0)
    v10 = _fill_nan(np.array(ds["v10"].values, dtype=float), 0.0)
    msl = _fill_nan(np.array(ds["msl"].values, dtype=float), 101325.0)
    sst = _fill_nan(np.array(ds["sst"].values, dtype=float), 302.15)
    return u10, v10, msl, sst


def simulate_voyage(sail, n_sails, waypoints, weather, R_total, V_ship_ms,
                    sfoc_kg_per_kwh: float = 0.180):
    """单航次逐小时推力平衡积分（帆型无关，统一 SailBase 接口）

    Returns:
        dict: fuel_baseline_kg, fuel_with_sail_kg, fuel_saved_kg,
              saving_rate_pct, mean_thrust_kN, mean_power_kW, mean_wind_ms
    """
    u10, v10, msl, sst = weather
    fuel_baseline_kg = 0.0
    fuel_saved_kg = 0.0
    T_list, P_list = [], []

    for i in range(len(waypoints)):
        u, v = float(u10[i]), float(v10[i])
        rho = rho_air(float(msl[i]), float(sst[i]))
        heading = getattr(waypoints[i], "_heading", 0.0)
        V_east, V_north = ship_velocity_components(V_ship_ms, heading)
        u_app, v_app, V_app = relative_wind(u, v, V_north, V_east)

        wind_dir_geo = np.arctan2(u_app, v_app) % (2 * np.pi)
        beta = (wind_dir_geo - heading) % (2 * np.pi)
        if beta > np.pi:
            beta = 2 * np.pi - beta

        if V_app < 0.5:
            bal = solve_balance(R_total, V_ship_ms, 0.0, 0.0, SFOC=sfoc_kg_per_kwh)
            fuel_baseline_kg += bal.fuel_baseline_kg_per_h
            T_list.append(0.0)
            P_list.append(0.0)
            continue

        opt = sail.optimal_control(V_app, rho, beta)
        T_total = max(opt["thrust"], 0.0) * n_sails
        P_total = opt["power_rotor"] * n_sails
        T_list.append(T_total)
        P_list.append(P_total)

        bal = solve_balance(R_total, V_ship_ms, T_total, P_total, SFOC=sfoc_kg_per_kwh)
        fuel_baseline_kg += bal.fuel_baseline_kg_per_h
        fuel_saved_kg += bal.fuel_saved_kg_per_h

    fuel_with_sail_kg = fuel_baseline_kg - fuel_saved_kg
    saving_rate = (fuel_saved_kg / fuel_baseline_kg * 100.0
                   if fuel_baseline_kg > 0 else 0.0)
    wind = np.sqrt(u10 ** 2 + v10 ** 2)
    return {
        "fuel_baseline_kg": fuel_baseline_kg,
        "fuel_with_sail_kg": fuel_with_sail_kg,
        "fuel_saved_kg": fuel_saved_kg,
        "saving_rate_pct": saving_rate,
        "mean_thrust_kN": float(np.mean(T_list)) / 1000.0,
        "mean_power_kW": float(np.mean(P_list)) / 1000.0,
        "mean_wind_ms": float(np.mean(wind)),
    }


def evaluate_cell(sim, ship, total_nm, unit_cost, n_sails, trips_per_year,
                  emission_factor: float = DEFAULT_EMISSION_FACTOR,
                  cii_ship_type: str = "tanker",
                  fuel_price: float | None = None,
                  co2_price: float | None = None,
                  cii_capacity: float | None = None):
    """从单航次仿真结果计算 CII 与经济性，组装矩阵单元

    emission_factor: 按燃料类型的 CO₂ 排放因子（owner.fuel_type 驱动，默认 HFO/VLSFO 3.114）
    cii_ship_type:   CII 参考线船型（owner 船型的 ship_type_imo，默认 tanker）
    fuel_price/co2_price: owner 覆盖的油价/碳价（None=用 economics.yaml 默认）
    cii_capacity:    CII 容量基数（None=回退用 ship.DWT）。roro/vehicle carrier/cruise
                     等船型的 CII 参考线以 GT 为容量基数（MEPC.353(78)），需传入船的 GT；
                     默认 None 保持既有 DWT 船型行为不变。注：CII 改善率与容量无关
                     （分子分母抵消），仅绝对评级（A-E）受容量基数影响。
    """
    fuel_baseline_t = sim["fuel_baseline_kg"] / 1000.0
    fuel_with_sail_t = sim["fuel_with_sail_kg"] / 1000.0
    fuel_saved_t = sim["fuel_saved_kg"] / 1000.0
    co2_reduced_t = fuel_saved_t * emission_factor

    cap = cii_capacity if cii_capacity is not None else ship.DWT
    cii_bl = compute_cii(fuel_baseline_t, cap, total_nm, emission_factor)
    cii_ws = compute_cii(fuel_with_sail_t, cap, total_nm, emission_factor)
    bl = CIIBaseline(ship_type=cii_ship_type, capacity=cap, year=2024)
    imp = cii_improvement(cii_bl, cii_ws)

    cost = unit_cost * n_sails
    annual_fuel_saved_t = fuel_saved_t * trips_per_year
    annual_co2_t = co2_reduced_t * trips_per_year
    sav_kwargs = {"work_rate": 1.0}
    if fuel_price is not None:
        sav_kwargs["fuel_price"] = fuel_price
    if co2_price is not None:
        sav_kwargs["co2_price"] = co2_price
    sav = annual_savings(annual_fuel_saved_t, annual_co2_t, **sav_kwargs)
    pb = payback_period(cost, sav["total_savings_usd"])
    npv_d = npv(sav["total_savings_usd"], cost, years=[10, 20])

    return {
        "mean_wind_ms": round(sim["mean_wind_ms"], 2),
        "mean_thrust_kN": round(sim["mean_thrust_kN"], 1),
        "mean_power_kW": round(sim["mean_power_kW"], 1),
        "fuel_saved_t": round(fuel_saved_t, 2),
        "saving_rate_pct": round(sim["saving_rate_pct"], 2),
        "co2_reduced_t": round(co2_reduced_t, 2),
        "cii_baseline": round(cii_bl, 4),
        "cii_with_sail": round(cii_ws, 4),
        "cii_rating_baseline": cii_rating(cii_bl, bl.required_cii),
        "cii_rating_with_sail": cii_rating(cii_ws, bl.required_cii),
        "cii_improvement_pct": round(imp, 2),
        "initial_cost_usd": round(cost, 0),
        "annual_savings_usd": round(sav["total_savings_usd"], 0),
        "payback_years": round(pb, 1) if np.isfinite(pb) else None,
        "npv_10y_usd": round(npv_d[10], 0),
        "npv_20y_usd": round(npv_d[20], 0),
    }


def run_matrix(sail_types=("flettner", "rigid_wing", "suction_wing"),
               V_ship_kn: float = DEFAULT_V_SHIP_KN,
               annual_operating_hours: float = ANNUAL_OPERATING_HOURS,
               flettner_spec: str | None = None,
               owner: OwnerInputs | None = None,
               verbose: bool = True) -> dict:
    """运行完整效益矩阵

    Args:
        flettner_spec: 可选 Norsepower 标准规格 ("20x4".."35x5")，None=默认 24×4。
        owner:  船东输入 OwnerInputs。给定时由其驱动船型/航线/航速/年作业小时/
                燃料排放因子/SFOC/油价/碳价/单台成本；None=沿用硬编码默认（向后兼容）。
    """
    with open(ROUTES_CONFIG, "r", encoding="utf-8") as f:
        rcfg = yaml.safe_load(f)
    routes = rcfg["routes"]
    seasons = rcfg["seasons"]

    # ── OwnerInputs 覆盖（None 时保持原硬编码行为，向后兼容）──
    if owner is not None:
        owner.validate()
        V_ship_kn = owner.ship_speed_kn
        annual_operating_hours = owner.annual_operating_hours()
        flettner_spec = owner.flettner_spec
        ship = load_ship_params_by_type(owner.ship_type)
        owner_overrides = owner.resolved_ship_overrides()
        if owner_overrides is not None:
            ship = apply_geometry_overrides(ship, owner_overrides)
        emission_factor = owner.resolved_emission_factor()
        cii_ship_type = ship.ship_type_imo
        fuel_price = owner.fuel_price_usd_per_kg
        co2_price = owner.co2_price_eur_per_t
        sfoc_kg = owner.sfoc_g_per_kwh / 1000.0
        owner_unit_cost = owner.resolved_unit_cost_usd()
        owner_sail_type = owner.sail_type
        # 航线过滤为 owner 选定走廊（单航线或加权子集）
        owner_route_keys = [k for k, _ in owner.resolved_routes()]
        routes = {k: routes[k] for k in owner_route_keys if k in routes}
        if not routes:
            raise ValueError(
                f"owner 指定航线 {owner_route_keys} 均不在 routes.yaml 中")
    else:
        ship = load_ship_params()
        emission_factor = DEFAULT_EMISSION_FACTOR
        cii_ship_type = "tanker"
        fuel_price = None
        co2_price = None
        sfoc_kg = 0.180
        owner_unit_cost = None
        owner_sail_type = None

    V_ship_ms = V_ship_kn * KN_TO_MS

    if verbose:
        print("=" * 72)
        print("Phase B 效益矩阵 — 航线 × 季节 × 帆型")
        print(f"{len(routes)} 航线 × {len(seasons)} 季节 × {len(sail_types)} 帆型 "
              f"= {len(routes) * len(seasons) * len(sail_types)} 情景")
        print("=" * 72)

    # 船型阻力（恒定，只算一次；ship 已在上方按 owner/默认选定）
    holtrop_inp = to_holtrop_input(ship)
    res = compute_resistance(holtrop_inp, V_ship_ms)
    R_total = res["R_total"]

    # 预构造三帆型（flettner 可按规格）
    sails = {st: build_sail(st, flettner_spec if st == "flettner" else None)
             for st in sail_types}
    if verbose:
        for st in sail_types:
            s, n, uc, area, label = sails[st]
            print(f"  {label}: {n} 台 × {area:.0f} m² (单台 ${uc:,.0f})")
        ship_label = owner.ship_type if owner is not None else "kvlcc2"
        print(f"  船型 {ship_label}  R_total={R_total/1000:.1f} kN  P_E={res['P_E']/1e6:.2f} MW")
        print()

    # 加载 ERA5（只加载一次）
    if verbose:
        print("[加载 ERA5]...")
    t0 = time.time()
    era5 = load_era5_from_config()
    if verbose:
        print(f"        ERA5 加载耗时 {time.time() - t0:.1f} s\n")

    matrix = {}
    try:
        for rkey, rinfo in routes.items():
            route_wps_def = [tuple(wp) for wp in rinfo["waypoints"]]
            matrix[rkey] = {"name": rinfo["name"], "cargo": rinfo.get("cargo"), "seasons": {}}
            for skey, start_time in seasons.items():
                waypoints = generate_hourly_waypoints(route_wps_def, start_time, V_ship_kn)
                total_km = sum(
                    haversine_distance(waypoints[i].lat, waypoints[i].lon,
                                       waypoints[i + 1].lat, waypoints[i + 1].lon)
                    for i in range(len(waypoints) - 1)
                )
                total_nm = total_km * KM_TO_NM
                weather = sample_route_weather(era5, waypoints)

                duration_h = len(waypoints) - 1
                trips_per_year = (annual_operating_hours / duration_h
                                  if duration_h > 0 else 0.0)
                cell = {"distance_nm": round(total_nm, 0),
                        "duration_h": duration_h,
                        "trips_per_year": round(trips_per_year, 1), "sails": {}}
                for st in sail_types:
                    sail, n, uc, area, label = sails[st]
                    if owner_unit_cost is not None and st == owner_sail_type:
                        uc = owner_unit_cost
                    sim = simulate_voyage(sail, n, waypoints, weather,
                                          R_total, V_ship_ms, sfoc_kg)
                    cell["sails"][st] = evaluate_cell(
                        sim, ship, total_nm, uc, n, trips_per_year,
                        emission_factor, cii_ship_type, fuel_price, co2_price)
                matrix[rkey]["seasons"][skey] = cell

                if verbose:
                    rates = " ".join(
                        f"{st[:4]}={cell['sails'][st]['saving_rate_pct']:.1f}%"
                        for st in sail_types)
                    mean_wind = float(np.mean(np.sqrt(weather[0] ** 2 + weather[1] ** 2)))
                    print(f"  [{rkey:>20} | {skey:>6}] "
                          f"{total_nm:>5.0f}nm  wind={mean_wind:.1f}m/s  {rates}")
    finally:
        era5.close()

    result = {
        "metadata": {
            "pipeline": "Phase B Matrix (route × season × sail)",
            "timestamp": datetime.now().isoformat(),
            "n_routes": len(routes),
            "n_seasons": len(seasons),
            "n_sail_types": len(sail_types),
            "V_ship_kn": V_ship_kn,
            "annual_operating_hours": annual_operating_hours,
            "emission_factor_tco2_per_t": emission_factor,
            "sfoc_kg_per_kwh": sfoc_kg,
            "ship_type": owner.ship_type if owner is not None else "kvlcc2",
            "sail_install": {st: SAIL_INSTALL[st] for st in sail_types},
            "flettner_spec": flettner_spec or "24x4",
            "owner_inputs": owner.to_dict() if owner is not None else None,
            "note": "有帆油耗已扣除转子/吸力电力功耗；年航次数按航次时长从年运营小时换算；经济性用单台成本×台数。",
        },
        "matrix": matrix,
    }
    return result


def print_summary(result: dict) -> None:
    """打印各帆型跨情景节油率统计摘要"""
    matrix = result["matrix"]
    sail_types = list(result["metadata"]["sail_install"].keys())
    print()
    print("=" * 72)
    print("效益矩阵摘要 — 各帆型节油率跨情景统计 (%)")
    print("=" * 72)
    print(f"{'帆型':<14}{'均值':>8}{'最小':>8}{'最大':>8}{'情景数':>8}")
    print("-" * 72)
    for st in sail_types:
        rates = []
        for rinfo in matrix.values():
            for cell in rinfo["seasons"].values():
                rates.append(cell["sails"][st]["saving_rate_pct"])
        rates = np.array(rates)
        print(f"{st:<14}{rates.mean():>8.2f}{rates.min():>8.2f}"
              f"{rates.max():>8.2f}{len(rates):>8}")
    print("=" * 72)


def save_result(result: dict, output_path: str | None = None) -> str:
    results_dir = os.path.join(CODE_DIR, "results")
    if output_path is None:
        os.makedirs(results_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(results_dir, f"phase_b_matrix_{ts}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return output_path


def main():
    result = run_matrix()
    print_summary(result)
    out = save_result(result)
    print(f"\n矩阵结果已保存: {out}")


if __name__ == "__main__":
    main()
