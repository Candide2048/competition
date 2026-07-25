# -*- coding: utf-8 -*-
"""Phase B — 完整中东-中国航线风帆辅助推进效益仿真

与 Phase A MVP (70h 波斯湾单段验证) 不同，本模块仿真完整 VLCC 中东→中国
原油运输航线（霍尔木兹海峡→印度洋→马六甲海峡→南海→宁波舟山港），
逐小时 ERA5 风况积分，输出真实航次节油量、CII 改善与经济性。

航线: Ras Tanura (26.7°N, 50.2°E) → Ningbo (29.9°N, 121.9°E)
距离: ~6200 nm (大圆 ~5800 nm, 实际航线含绕行)
航速: 14 kn → 单程 ~443 h (~18.5 天)
年航次: 3 (VLCC 中东-中国中位数)

数据: ERA5 2025 全年 (30°E–130°E, 10°S–40°N, 逐小时)
出发: 默认 6 月 15 日 (夏季季风期, 印度洋西南季风 8-12 m/s)

参考:
    ④ 计明军 2023 场景2 (Phase A 验证锚点)
    ⑤ Guzelbulut 2024 (Flettner 气动 + 经济性)
    MEPC.353(78) G2 Table 1 (CII 参考线)
    船舶风帆技术数据搜集表.xlsx (实船验证数据)
"""
import os
import sys
import json
import time
from datetime import datetime

import numpy as np

# 路径设置
CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE_DIR)

from core.era5_loader import load_era5_from_config
from core.route_definition import (
    Waypoint, haversine_distance, initial_bearing,
    ship_velocity_components, KN_TO_MS, KM_TO_NM,
)
from core.ship_params import load_ship_params, to_holtrop_input
from models.aerodynamics.flettner import FlettnerSail, FlettnerConfig
from models.atmosphere import rho_air, relative_wind
from models.resistance.holtrop_mennen import compute_resistance
from models.thrust_balance import solve_balance
from analytics.cii import (
    CIIBaseline, compute_cii, cii_rating, cii_improvement,
    DEFAULT_EMISSION_FACTOR,
)
from analytics.economics import (
    initial_cost, annual_savings, payback_period, npv, sensitivity,
)
from analytics.fuel_saving import compute_fuel_saving

# ── 航线定义: 中东→中国 VLCC 原油运输航线 (经马六甲海峡) ──
# 航路点来源: 世界主要航运航线参考 + ERA5 数据覆盖范围校验
MIDDLE_EAST_CHINA_ROUTE = [
    (26.7, 50.2),   # Ras Tanura (沙特装货港)
    (26.5, 56.5),   # 霍尔木兹海峡
    (23.0, 60.0),   # 阿曼湾
    (20.0, 64.0),   # 阿拉伯海
    (14.0, 68.0),   # 阿拉伯海 (印度西海岸外)
    (10.0, 72.0),   # 印度洋 (印度南端)
    (8.0, 77.0),    # 印度洋 (斯里兰卡以南)
    (8.0, 82.0),    # 孟加拉湾
    (7.0, 88.0),    # 孟加拉湾 (安达曼海)
    (6.0, 95.0),    # 马六甲海峡西入口
    (3.0, 100.0),   # 马六甲海峡 (新加坡附近)
    (5.0, 105.0),   # 南海 (越南以南)
    (10.0, 110.0),  # 南海 (越南中部外海)
    (15.0, 114.0),  # 南海 (西沙群岛附近)
    (20.0, 117.0),  # 南海 (巴士海峡以西)
    (24.0, 119.0),  # 台湾海峡南口
    (27.0, 120.5),  # 东中国海 (温州外海)
    (29.9, 121.9),  # 宁波舟山港 (卸货港)
]

# 默认仿真参数
DEFAULT_START_DATE = "2025-06-15T00:00"  # 夏季季风期
DEFAULT_V_SHIP_KN = 14.0
DEFAULT_SAIL_H = 24.0
DEFAULT_SAIL_D = 4.0
DEFAULT_SAIL_AR = 6.0
DEFAULT_SAIL_DED = 3.0
DEFAULT_N_SAILS = 4
DEFAULT_TRIPS_PER_YEAR = 3  # VLCC 中东-中国中位数


def generate_hourly_waypoints(
    route: list[tuple[float, float]],
    start_time: str,
    V_ship_kn: float = 14.0,
) -> list[Waypoint]:
    """沿多段航线生成逐小时航路点

    按船速沿航路点序列匀速推进，每小时一个位置点。
    航向取当前所在分段的大圆航向。

    Args:
        route: 航路点列表 [(lat, lon), ...]
        start_time: 出发时间 (ISO 格式)
        V_ship_kn: 船速 (kn)

    Returns:
        list[Waypoint]: 逐小时航路点 (含时间戳)
    """
    V_ship_ms = V_ship_kn * KN_TO_MS
    dt_s = 3600.0  # 1 小时
    step_km = V_ship_ms * dt_s / 1000.0  # 每小时行进距离 (km)

    # 计算各段距离和总距离
    seg_distances = []
    for i in range(len(route) - 1):
        d = haversine_distance(route[i][0], route[i][1],
                               route[i + 1][0], route[i + 1][1])
        seg_distances.append(d)
    total_km = sum(seg_distances)

    n_steps = int(np.ceil(total_km / step_km)) + 1
    start_dt = np.datetime64(start_time)

    waypoints = []
    seg_idx = 0
    seg_remaining = seg_distances[0] if seg_distances else 0.0
    seg_start = np.array(route[0], dtype=float)
    seg_end = np.array(route[1], dtype=float) if len(route) > 1 else seg_start
    seg_heading = initial_bearing(route[0][0], route[0][1],
                                  route[1][0], route[1][1]) if len(route) > 1 else 0.0

    for i in range(n_steps):
        t = start_dt + np.timedelta64(i, "h")

        if i == 0:
            lat, lon = route[0]
        elif i == n_steps - 1:
            lat, lon = route[-1]
        else:
            # 沿当前分段插值
            dist_into_seg = step_km  # 每小时走 step_km
            while dist_into_seg > seg_remaining and seg_idx < len(seg_distances) - 1:
                dist_into_seg -= seg_remaining
                seg_idx += 1
                seg_remaining = seg_distances[seg_idx]
                seg_start = np.array(route[seg_idx], dtype=float)
                seg_end = np.array(route[seg_idx + 1], dtype=float)
                seg_heading = initial_bearing(
                    route[seg_idx][0], route[seg_idx][1],
                    route[seg_idx + 1][0], route[seg_idx + 1][1],
                )

            # 线性插值 (短分段内足够精确)
            frac = 1.0 - (seg_remaining - dist_into_seg) / seg_distances[seg_idx] if seg_distances[seg_idx] > 0 else 0.0
            frac = max(0.0, min(1.0, frac))
            lat = seg_start[0] + frac * (seg_end[0] - seg_start[0])
            lon = seg_start[1] + frac * (seg_end[1] - seg_start[1])
            seg_remaining -= dist_into_seg

        wp = Waypoint(lat=float(lat), lon=float(lon), time=t)
        wp._heading = seg_heading  # 附加航向信息
        waypoints.append(wp)

    return waypoints


def run_phase_b_full_voyage(
    route: list[tuple[float, float]] | None = None,
    start_time: str = DEFAULT_START_DATE,
    V_ship_kn: float = DEFAULT_V_SHIP_KN,
    sail_H: float = DEFAULT_SAIL_H,
    sail_D: float = DEFAULT_SAIL_D,
    sail_AR: float = DEFAULT_SAIL_AR,
    sail_DeD: float = DEFAULT_SAIL_DED,
    n_sails: int = DEFAULT_N_SAILS,
    trips_per_year: int = DEFAULT_TRIPS_PER_YEAR,
    verbose: bool = True,
) -> dict:
    """运行 Phase B 完整航线仿真

    与 Phase A 的核心区别:
    - 多航路点完整航线 (非起终点直线)
    - 逐小时推力平衡积分 (非均值近似)
    - 真实航次距离 (~6200 nm vs 594 nm)
    - 跨风况区积分 (波斯湾弱风 → 印度洋/南海强风)

    Args:
        route: 航路点列表，None 则用默认中东-中国航线
        start_time: 出发时间
        V_ship_kn: 船速 (kn)
        sail_H/D/AR/DeD: Flettner 风帆参数
        n_sails: 风帆台数
        trips_per_year: 年航次数
        verbose: 打印进度

    Returns:
        dict: 完整仿真结果
    """
    if route is None:
        route = MIDDLE_EAST_CHINA_ROUTE

    if verbose:
        print("=" * 72)
        print("Phase B — 完整中东-中国航线风帆效益仿真")
        print("=" * 72)

    # ── Step 0: 几何与航路点 ──
    V_ship_ms = V_ship_kn * KN_TO_MS
    waypoints = generate_hourly_waypoints(route, start_time, V_ship_kn)
    duration_h = len(waypoints) - 1

    # 总距离
    total_km = sum(
        haversine_distance(waypoints[i].lat, waypoints[i].lon,
                           waypoints[i + 1].lat, waypoints[i + 1].lon)
        for i in range(len(waypoints) - 1)
    )
    total_nm = total_km * KM_TO_NM

    if verbose:
        print(f"航线: {route[0]} → {route[-1]} ({len(route)} 航路点)")
        print(f"距离: {total_km:.0f} km = {total_nm:.0f} nm")
        print(f"航程: {duration_h} h ({duration_h / 24:.1f} 天) @ {V_ship_kn} kn")
        print(f"出发: {start_time}")
        print()

    # ── Step 1: 加载 ERA5 ──
    if verbose:
        print("[Step 1] 加载 ERA5 数据集...")
    t0 = time.time()
    era5 = load_era5_from_config()
    if verbose:
        print(f"        ERA5 加载耗时 {time.time() - t0:.1f} s")

    # ── Step 2: 沿航线逐小时采样 ERA5 ──
    if verbose:
        print(f"[Step 2] 沿航线采样 ERA5 ({len(waypoints)} 个时刻)...")

    lats = [wp.lat for wp in waypoints]
    lons = [wp.lon for wp in waypoints]
    times = [wp.time for wp in waypoints]

    route_ds = era5.sample_route(list(zip(lats, lons)), times)
    era5.close()

    u10_arr = np.array(route_ds["u10"].values, dtype=float)
    v10_arr = np.array(route_ds["v10"].values, dtype=float)
    msl_arr = np.array(route_ds["msl"].values, dtype=float)
    sst_arr = np.array(route_ds["sst"].values, dtype=float)

    # NaN 容错 (同 Phase A)
    def _fill_nan(arr, fallback, name):
        n_nan = int(np.isnan(arr).sum())
        if n_nan == 0:
            return arr
        if n_nan == arr.size:
            if verbose:
                print(f"        [警告] {name} 全部 NaN，用 fallback={fallback}")
            return np.full_like(arr, fallback)
        idx = np.arange(arr.size)
        valid = ~np.isnan(arr)
        arr_filled = np.interp(idx, idx[valid], arr[valid])
        if verbose and n_nan > 0:
            print(f"        [NaN 填补] {name}: {n_nan}/{arr.size} 个")
        return arr_filled

    sst_arr = _fill_nan(sst_arr, 302.15, "sst")
    msl_arr = _fill_nan(msl_arr, 101325.0, "msl")
    u10_arr = _fill_nan(u10_arr, 0.0, "u10")
    v10_arr = _fill_nan(v10_arr, 0.0, "v10")

    wind_speed = np.sqrt(u10_arr**2 + v10_arr**2)
    if verbose:
        print(f"        风速均值 {np.mean(wind_speed):.2f} m/s, "
              f"最大 {np.max(wind_speed):.2f} m/s")
        print(f"        气压均值 {np.mean(msl_arr):.0f} Pa")
        print(f"        SST 均值 {np.mean(sst_arr) - 273.15:.1f} °C")
        print()

    # ── Step 3: 船型与风帆 ──
    ship = load_ship_params()
    holtrop_inp = to_holtrop_input(ship)
    sail = FlettnerSail(FlettnerConfig(H=sail_H, D=sail_D, AR=sail_AR, D_e_D=sail_DeD))

    if verbose:
        print(f"[Step 3] 船型: KVLCC2 (L={ship.L}m, B={ship.B}m, DWT={ship.DWT}t)")
        print(f"        风帆: {n_sails}× Flettner H={sail_H}m, D={sail_D}m")
        print()

    # ── Step 4: Holtrop 阻力 (恒定, 船速不变) ──
    res = compute_resistance(holtrop_inp, V_ship_ms)
    R_total = res["R_total"]
    if verbose:
        print(f"[Step 4] R_total = {R_total / 1000:.1f} kN, P_E = {res['P_E'] / 1e6:.2f} MW")
        print()

    # ── Step 5: 逐小时推力平衡积分 ──
    if verbose:
        print(f"[Step 5] 逐小时推力平衡积分 ({len(waypoints)} 步)...")

    fuel_saved_total_kg = 0.0
    fuel_baseline_total_kg = 0.0
    T_sail_list = []
    P_rotor_list = []
    saving_rate_list = []

    for i in range(len(waypoints)):
        u, v = float(u10_arr[i]), float(v10_arr[i])
        msl_val, sst_val = float(msl_arr[i]), float(sst_arr[i])
        rho = rho_air(msl_val, sst_val)

        # 航向 (取当前分段航向)
        heading = getattr(waypoints[i], "_heading", 0.0)
        V_east, V_north = ship_velocity_components(V_ship_ms, heading)

        # 相对风
        u_app, v_app, V_app = relative_wind(u, v, V_north, V_east)

        # 相对风向角 beta
        wind_dir_geo = np.arctan2(u_app, v_app) % (2 * np.pi)
        beta = (wind_dir_geo - heading) % (2 * np.pi)
        if beta > np.pi:
            beta = 2 * np.pi - beta

        # Flettner 最优控制
        if V_app < 0.5:
            T_sail_list.append(0.0)
            P_rotor_list.append(0.0)
            saving_rate_list.append(0.0)
            # 无帆基线油耗
            bal = solve_balance(R_total, V_ship_ms, 0.0, 0.0)
            fuel_baseline_total_kg += bal.fuel_baseline_kg_per_h
            continue

        opt = sail.optimal_control(V_app, rho, beta)
        T_single = opt["thrust"]
        P_single = opt["power_rotor"]
        T_total = T_single * n_sails
        P_total = P_single * n_sails

        T_sail_list.append(T_total)
        P_rotor_list.append(P_total)

        # 逐小时推力平衡
        bal = solve_balance(R_total, V_ship_ms, T_total, P_total)
        fuel_baseline_total_kg += bal.fuel_baseline_kg_per_h
        fuel_saved_total_kg += bal.fuel_saved_kg_per_h
        saving_rate_list.append(bal.saving_rate_pct)

    fuel_with_sail_total_kg = fuel_baseline_total_kg - fuel_saved_total_kg
    overall_saving_rate = (fuel_saved_total_kg / fuel_baseline_total_kg * 100.0
                           if fuel_baseline_total_kg > 0 else 0.0)

    T_sail_mean = float(np.mean(T_sail_list))
    P_rotor_mean = float(np.mean(P_rotor_list))
    saving_rate_mean = float(np.mean(saving_rate_list))

    co2_reduced_kg = fuel_saved_total_kg * DEFAULT_EMISSION_FACTOR
    co2_reduced_t = co2_reduced_kg / 1000.0

    if verbose:
        print(f"        平均推力 {T_sail_mean / 1000:.1f} kN ({n_sails}× 合计)")
        print(f"        平均功耗 {P_rotor_mean / 1000:.1f} kW")
        print(f"        基线油耗 {fuel_baseline_total_kg / 1000:.2f} t")
        print(f"        有帆油耗 {fuel_with_sail_total_kg / 1000:.2f} t")
        print(f"        节油量 {fuel_saved_total_kg / 1000:.2f} t ({overall_saving_rate:.2f}%)")
        print(f"        CO2 减排 {co2_reduced_t:.2f} t")
        print()

    # ── Step 6: CII 评级 ──
    if verbose:
        print("[Step 6] CII 评级...")
    cii_baseline = compute_cii(fuel_baseline_total_kg / 1000.0, ship.DWT, total_nm)
    cii_with_sail = compute_cii(fuel_with_sail_total_kg / 1000.0, ship.DWT, total_nm)
    bl = CIIBaseline(ship_type="tanker", capacity=ship.DWT, year=2024)
    rating_baseline = cii_rating(cii_baseline, bl.required_cii)
    rating_with_sail = cii_rating(cii_with_sail, bl.required_cii)
    cii_imp = cii_improvement(cii_baseline, cii_with_sail)

    if verbose:
        print(f"        基线 CII = {cii_baseline:.4f} gCO2/dwt·nm 评级 {rating_baseline}")
        print(f"        有帆 CII = {cii_with_sail:.4f} gCO2/dwt·nm 评级 {rating_with_sail}")
        print(f"        CII 改善率 {cii_imp:.2f}%")
        print(f"        Required CII 2024 = {bl.required_cii:.4f}")
        print()

    # ── Step 7: 经济性 ──
    if verbose:
        print("[Step 7] 经济性评估...")
    A_top = np.pi * (sail_D / 2) ** 2
    A_lateral = sail_H * sail_D
    V_rotor = np.pi * (sail_D / 2) ** 2 * sail_H
    cost = initial_cost(A_top, A_lateral, V_rotor) * n_sails

    annual_fuel_saved_t = (fuel_saved_total_kg / 1000.0) * trips_per_year
    annual_co2_reduced_t = co2_reduced_t * trips_per_year
    # work_rate=1.0: 逐小时积分已按实际风况折减（V_app<0.5 的时段已跳过，
    # 帆不产生推力），工作率已隐含在物理仿真中，此处不再二次折减。
    savings = annual_savings(annual_fuel_saved_t, annual_co2_reduced_t,
                             work_rate=1.0)
    pb = payback_period(cost, savings["total_savings_usd"])
    npv_dict = npv(savings["total_savings_usd"], cost, years=[5, 10, 15, 20])
    sens = sensitivity(annual_fuel_saved_t, annual_co2_reduced_t, cost,
                       work_rate=1.0, years=10)

    if verbose:
        print(f"        初始投资 ${cost:,.0f}")
        print(f"        年节省 ${savings['total_savings_usd']:,.0f} ({trips_per_year} 航次/年)")
        print(f"        回收期 {pb:.1f} 年")
        print(f"        NPV 10y = ${npv_dict[10]:,.0f}")
        print(f"        NPV 20y = ${npv_dict[20]:,.0f}")
        print()

    # ── 汇总 ──
    result = {
        "metadata": {
            "pipeline": "Phase B Full Voyage",
            "timestamp": datetime.now().isoformat(),
            "route_name": "Middle East → China (VLCC crude, via Malacca)",
        },
        "inputs": {
            "route": {
                "waypoints": route,
                "n_waypoints_defined": len(route),
                "n_hourly_steps": len(waypoints),
                "distance_km": float(total_km),
                "distance_nm": float(total_nm),
                "duration_h": float(duration_h),
                "V_ship_kn": V_ship_kn,
                "start_time": start_time,
            },
            "ship": {
                "type": "KVLCC2",
                "L": ship.L, "B": ship.B, "T": ship.T,
                "DWT": ship.DWT, "C_B": ship.C_B,
            },
            "sail": {
                "type": "Flettner",
                "n_sails": n_sails,
                "H": sail_H, "D": sail_D, "AR": sail_AR, "D_e_D": sail_DeD,
            },
        },
        "era5_stats": {
            "mean_wind_speed_ms": float(np.mean(wind_speed)),
            "max_wind_speed_ms": float(np.max(wind_speed)),
            "mean_msl_pa": float(np.mean(msl_arr)),
            "mean_sst_k": float(np.mean(sst_arr)),
        },
        "sail_performance": {
            "mean_thrust_kN": T_sail_mean / 1000,
            "mean_rotor_power_kW": P_rotor_mean / 1000,
            "mean_saving_rate_pct": saving_rate_mean,
        },
        "fuel_saving": {
            "fuel_baseline_t": fuel_baseline_total_kg / 1000.0,
            "fuel_with_sail_t": fuel_with_sail_total_kg / 1000.0,
            "fuel_saved_t": fuel_saved_total_kg / 1000.0,
            "saving_rate_pct": overall_saving_rate,
            "co2_reduced_t": co2_reduced_t,
        },
        "cii": {
            "baseline_cii": cii_baseline,
            "with_sail_cii": cii_with_sail,
            "rating_baseline": rating_baseline,
            "rating_with_sail": rating_with_sail,
            "improvement_pct": cii_imp,
            "required_cii_2024": bl.required_cii,
        },
        "economics": {
            "initial_cost_usd": cost,
            "annual_savings_usd": savings["total_savings_usd"],
            "payback_years": pb,
            "npv_5y": npv_dict[5],
            "npv_10y": npv_dict[10],
            "npv_15y": npv_dict[15],
            "npv_20y": npv_dict[20],
            "trips_per_year": trips_per_year,
            "sensitivity_10y": sens,
        },
    }

    return result


def print_summary(result: dict) -> None:
    """打印结果汇总表"""
    print()
    print("=" * 72)
    print("Phase B 完整航线仿真结果汇总")
    print("=" * 72)
    print(f"{'指标':<30} {'值':>20} {'单位/备注':<20}")
    print("-" * 72)

    rt = result["inputs"]["route"]
    dur_days = rt["duration_h"] / 24
    print(f"{'航线距离':<30} {rt['distance_nm']:>20.0f} {'nm':<20}")
    print(f"{'航程时长':<30} {rt['duration_h']:>20.0f} {f'h ({dur_days:.1f} 天)':<20}")

    fs = result["fuel_saving"]
    print(f"{'基线油耗':<30} {fs['fuel_baseline_t']:>20.2f} {'t/航次':<20}")
    print(f"{'有帆油耗':<30} {fs['fuel_with_sail_t']:>20.2f} {'t/航次':<20}")
    print(f"{'节油量':<30} {fs['fuel_saved_t']:>20.2f} {'t/航次':<20}")
    print(f"{'节油率':<30} {fs['saving_rate_pct']:>20.2f} {'%':<20}")
    print(f"{'CO2 减排':<30} {fs['co2_reduced_t']:>20.2f} {'t/航次':<20}")

    cii = result["cii"]
    bl_rating = f"({cii['rating_baseline']})"
    sail_rating = f"({cii['rating_with_sail']})"
    print(f"{'基线 CII':<30} {cii['baseline_cii']:>20.4f} {bl_rating:<20}")
    print(f"{'有帆 CII':<30} {cii['with_sail_cii']:>20.4f} {sail_rating:<20}")
    print(f"{'CII 改善率':<30} {cii['improvement_pct']:>20.2f} {'%':<20}")

    econ = result["economics"]
    tp = econ["trips_per_year"]
    print(f"{'初始投资':<30} {econ['initial_cost_usd']:>20,.0f} {'USD':<20}")
    print(f"{'年节省':<30} {econ['annual_savings_usd']:>20,.0f} {f'USD ({tp} 航次)':<20}")
    print(f"{'回收期':<30} {econ['payback_years']:>20.1f} {'年':<20}")
    print(f"{'NPV 10 年':<30} {econ['npv_10y']:>20,.0f} {'USD':<20}")
    print(f"{'NPV 20 年':<30} {econ['npv_20y']:>20,.0f} {'USD':<20}")
    print("=" * 72)


def save_result(result: dict, output_path: str | None = None) -> str:
    """保存结果到 JSON"""
    results_dir = os.path.join(CODE_DIR, "results")
    if output_path is None:
        os.makedirs(results_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(results_dir, f"phase_b_full_voyage_{ts}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return output_path


def main():
    """主入口"""
    result = run_phase_b_full_voyage()
    print_summary(result)
    out = save_result(result)
    print(f"\n详细结果已保存: {out}")


if __name__ == "__main__":
    main()
