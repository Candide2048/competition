# -*- coding: utf-8 -*-
"""Phase A MVP 端到端流水线

执行 ④ 计明军 2023 场景2:
    航线: 波斯湾 (29°N, 49°E) → (24°N, 60°E), 70h, 14 kn
    船型: KVLCC2 (L=320m, B=58m, T=20.8m, DWT=300000t)
    风帆: 4× Flettner 转子帆 (H=24m, D=4m, AR=6, D_e/D=3)
    实船对照: 油耗 89.2 t

数据流:
    [ERA5 加载] → [航线采样] → [逐点风帆推力]
                → [Holtrop 阻力] → [推力平衡]
                → [油耗/CII/NPV]

运行方式:
    cd shipping_wasp/code
    python pipelines/phase_a_mvp.py
    # 或
    python -m pipelines.phase_a_mvp

输出:
    - 控制台打印关键指标表
    - results/phase_a_mvp_result.json 详细结果
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta

import numpy as np

# 把 code/ 加入 sys.path，使脚本可独立运行
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)

from core.era5_loader import load_era5_from_config
from core.route_definition import (
    Waypoint,
    haversine_distance,
    interpolate_route,
    initial_bearing,
    ship_velocity_components,
    route_duration_hours,
    JI_SCENARIO_2_START,
    JI_SCENARIO_2_END,
    JI_SCENARIO_2_DISTANCE_KM,
    JI_SCENARIO_2_DURATION_H,
    JI_SCENARIO_2_FUEL_T,
    KN_TO_MS,
)
from core.ship_params import load_ship_params, to_holtrop_input
from models.atmosphere import rho_air, relative_wind, wind_speed
from models.aerodynamics.flettner import FlettnerSail, FlettnerConfig
from models.resistance import compute_resistance
from models.thrust_balance import solve_balance
from analytics.fuel_saving import compute_fuel_saving
from analytics.cii import compute_cii, cii_rating, cii_improvement, CIIBaseline
from analytics.economics import (
    initial_cost, annual_savings, npv, payback_period, sensitivity,
    DEFAULT_FUEL_PRICE, DEFAULT_CO2_PRICE, DEFAULT_WORK_RATE,
    DEFAULT_DISCOUNT_RATE, DEFAULT_MAINTENANCE_RATE,
)


# ---------- 输出目录 ----------

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "results"
)


def run_phase_a_mvp(
    start_lat: float = 29.0,
    start_lon: float = 49.0,
    end_lat: float = 24.0,
    end_lon: float = 60.0,
    duration_h: float = JI_SCENARIO_2_DURATION_H,
    V_ship_kn: float = 14.0,
    sail_H: float = 24.0,
    sail_D: float = 4.0,
    sail_AR: float = 6.0,
    sail_DeD: float = 3.0,
    n_sails: int = 4,
    # 年航次数: 3 (VLCC 中东-中国航线中位数, 2025 市场数据)
    # 单程 ~60d × 2 = 100 天往返 × 3 = 300 天/年 (utilization ≈ 82%)
    # 来源: Web research 2025-07 VLCC fleet utilization (中位 3-4 航次/年)
    # 反例: Norsepower 商业案例 20-50 航次/年是商业宣传口径, 不应作为工程默认值
    trips_per_year: int = 3,
    verbose: bool = True,
) -> dict:
    """运行 Phase A MVP 端到端流水线

    验证场景: ④ 计明军 2023 场景2 (波斯湾 70h 单段, 实船油耗 89.2 t)
    年化方法: 节油率 × trips_per_year (VLCC 中东-中国中位 3 航次/年)
    方法论警告:
        - 70h 波斯湾单段为低风况区域 (mean wind ~3.6 m/s)
        - 实际中东-中国往返 ~100 天 (2400h) 跨印度洋/南海高风况区
        - 当前年化结果 (70h × 3) 偏保守, Phase B 需用完整往返航次仿真

    Args:
        start_lat, start_lon: 起点经纬度
        end_lat, end_lon: 终点经纬度
        duration_h: 航程时长 (h)
        V_ship_kn: 船速 (kn)
        sail_H, sail_D, sail_AR, sail_DeD: Flettner 风帆参数
        trips_per_year: 年航次数（用于经济性计算）
        verbose: 是否打印进度

    Returns:
        dict: 完整结果
    """
    if verbose:
        print("=" * 72)
        print("Phase A MVP — 风帆辅助推进效益预测")
        print("=" * 72)
        print(f"航线: ({start_lat}°N, {start_lon}°E) → ({end_lat}°N, {end_lon}°E)")
        print(f"航程: {duration_h} h @ {V_ship_kn} kn")
        print(f"对照: ④ 计明军场景2 实船油耗 {JI_SCENARIO_2_FUEL_T} t")
        print()

    # ---------- Step 0: 几何与时间 ----------
    V_ship_ms = V_ship_kn * KN_TO_MS
    distance_km = haversine_distance(start_lat, start_lon, end_lat, end_lon)
    distance_nm = distance_km * 0.539957
    heading = initial_bearing(start_lat, start_lon, end_lat, end_lon)
    V_east, V_north = ship_velocity_components(V_ship_ms, heading)

    # 生成航路点（按 1h 间隔）
    n_steps = int(np.ceil(duration_h)) + 1
    start_wp = Waypoint(lat=start_lat, lon=start_lon,
                        time=np.datetime64("2025-06-15T00:00"))  # 夏季季风期
    end_wp = Waypoint(lat=end_lat, lon=end_lon,
                      time=start_wp.time + np.timedelta64(int(duration_h * 60), "m"))
    waypoints = interpolate_route(start_wp, end_wp, n_steps)

    if verbose:
        print(f"[几何] 距离 {distance_km:.1f} km = {distance_nm:.1f} nm")
        print(f"[几何] 航向 {np.degrees(heading):.1f}°, 船速 {V_ship_ms:.2f} m/s")
        print(f"[几何] 航路点 {len(waypoints)} 个 (1h 间隔)")
        print()

    # ---------- Step 1: 加载 ERA5 ----------
    if verbose:
        print("[Step 1] 加载 ERA5 数据集...")
    t0 = time.time()
    era5 = load_era5_from_config()
    if verbose:
        print(f"        ERA5 加载耗时 {time.time() - t0:.1f} s")

    # ---------- Step 2: 沿航线采样 ERA5 ----------
    if verbose:
        print("[Step 2] 沿航线采样 ERA5...")

    lats = [wp.lat for wp in waypoints]
    lons = [wp.lon for wp in waypoints]
    times = [wp.time for wp in waypoints]

    route_ds = era5.sample_route(list(zip(lats, lons)), times)
    era5.close()

    u10_arr = np.array(route_ds["u10"].values, dtype=float)
    v10_arr = np.array(route_ds["v10"].values, dtype=float)
    msl_arr = np.array(route_ds["msl"].values, dtype=float)
    sst_arr = np.array(route_ds["sst"].values, dtype=float)

    # ---------- NaN 容错处理 ----------
    # ERA5 SST 在陆地/海岸网格点为 NaN（波斯湾、阿曼湾沿岸），
    # 需对 u10/v10/msl/sst 沿航线 step 维度做线性插值填补，
    # 若整条航线均为 NaN 则 fallback 到物理合理值。
    def _fill_nan(arr: np.ndarray, fallback: float, name: str) -> np.ndarray:
        """沿 1D 数组用前后有效值线性插值填补 NaN；全 NaN 时用 fallback"""
        n_nan = int(np.isnan(arr).sum())
        if n_nan == 0:
            return arr
        if n_nan == arr.size:
            if verbose:
                print(f"        [警告] {name} 全部 NaN，用 fallback={fallback} 填补")
            return np.full_like(arr, fallback)
        # 线性插值
        idx = np.arange(arr.size)
        valid = ~np.isnan(arr)
        arr_filled = np.interp(idx, idx[valid], arr[valid])
        if verbose:
            print(f"        [NaN 填补] {name}: {n_nan}/{arr.size} 个 NaN 已线性插值")
        return arr_filled

    sst_arr = _fill_nan(sst_arr, fallback=302.15, name="sst")  # 29°C 热带海域夏季
    msl_arr = _fill_nan(msl_arr, fallback=101325.0, name="msl")  # 标准大气压
    u10_arr = _fill_nan(u10_arr, fallback=0.0, name="u10")
    v10_arr = _fill_nan(v10_arr, fallback=0.0, name="v10")

    if verbose:
        print(f"        采样点 {len(u10_arr)} 个")
        print(f"        风速均值 {np.mean(np.sqrt(u10_arr**2 + v10_arr**2)):.2f} m/s")
        print(f"        气压均值 {np.mean(msl_arr):.0f} Pa")
        print(f"        SST 均值 {np.mean(sst_arr) - 273.15:.1f} °C")
        print()

    # ---------- Step 3: 加载船型与风帆 ----------
    ship = load_ship_params()
    holtrop_inp = to_holtrop_input(ship)
    sail = FlettnerSail(FlettnerConfig(H=sail_H, D=sail_D, AR=sail_AR, D_e_D=sail_DeD))

    if verbose:
        print(f"[Step 3] 船型: KVLCC2 (L={ship.L}m, B={ship.B}m, DWT={ship.DWT}t)")
        print(f"        风帆: {n_sails}× Flettner H={sail_H}m, D={sail_D}m, AR={sail_AR}, D_e/D={sail_DeD}")
        print(f"        单帆投影面积 S = {sail.projected_area:.1f} m², 总面积 = {sail.projected_area * n_sails:.1f} m²")
        print()

    # ---------- Step 4: 逐点风帆推力 ----------
    if verbose:
        print("[Step 4] 逐点计算风帆推力...")

    T_sail_list = []
    P_rotor_list = []
    rho_air_list = []
    V_apparent_list = []
    SR_opt_list = []

    for i in range(len(waypoints)):
        u, v = float(u10_arr[i]), float(v10_arr[i])
        msl, sst = float(msl_arr[i]), float(sst_arr[i])

        # 空气密度
        rho = rho_air(msl, sst)

        # 相对风（地理坐标系：east=x, north=y）
        u_app, v_app, V_app = relative_wind(u, v, V_north, V_east)

        # 相对风向角 beta（相对船首，0=顶风，π/2=横风，π=顺风）
        # 步骤:
        #   1. 视风在地理坐标系的方向（从北顺时针，0=北风/风从北来）
        #      注意: atan2(u_app, v_app) 返回弧度，0=北，π/2=东
        #   2. 减去船首航向角 heading（同样从北顺时针），得到相对船首角度
        #   3. 对称化到 [0, π]（左/右舷对称，Flettner 旋转方向可调）
        wind_dir_geo = np.arctan2(u_app, v_app) % (2 * np.pi)
        beta = (wind_dir_geo - heading) % (2 * np.pi)
        # beta=0: 视风从船首方向来（顶风）
        # beta=π: 视风从船尾方向来（顺风）
        # 对称化：beta ∈ [π, 2π] 等价于 2π - beta（右舷↔左舷对称）
        if beta > np.pi:
            beta = 2 * np.pi - beta

        # Flettner 最优控制
        if V_app < 0.5:  # 极小风速时跳过
            T_sail_list.append(0.0)
            P_rotor_list.append(0.0)
            rho_air_list.append(rho)
            V_apparent_list.append(V_app)
            SR_opt_list.append(0.0)
            continue

        opt = sail.optimal_control(V_app, rho, beta)
        T_sail_list.append(opt["thrust"])
        P_rotor_list.append(opt["power_rotor"])
        rho_air_list.append(rho)
        V_apparent_list.append(V_app)
        SR_opt_list.append(opt["SR_opt"])

    T_sail_mean_single = float(np.mean(T_sail_list))
    P_rotor_mean_single = float(np.mean(P_rotor_list))
    V_app_mean = float(np.mean(V_apparent_list))
    SR_opt_mean = float(np.mean(SR_opt_list))

    # 多转子汇总：n_sails 台并联，推力/功耗线性叠加
    T_sail_mean = T_sail_mean_single * n_sails
    P_rotor_mean = P_rotor_mean_single * n_sails

    if verbose:
        print(f"        平均视风风速 {V_app_mean:.2f} m/s")
        print(f"        平均最优 SR {SR_opt_mean:.2f}")
        print(f"        单帆推力 {T_sail_mean_single/1000:.1f} kN × {n_sails} = {T_sail_mean/1000:.1f} kN")
        print(f"        单帆功耗 {P_rotor_mean_single/1000:.1f} kW × {n_sails} = {P_rotor_mean/1000:.1f} kW")
        print()

    # ---------- Step 5: Holtrop 阻力 ----------
    if verbose:
        print("[Step 5] Holtrop-Mennen 阻力计算...")
    res = compute_resistance(holtrop_inp, V_ship_ms)
    R_total = res["R_total"]
    if verbose:
        print(f"        R_total = {R_total/1000:.1f} kN")
        print(f"        P_E = {res['P_E']/1e6:.2f} MW")
        print()

    # ---------- Step 6: 推力平衡与油耗 ----------
    if verbose:
        print("[Step 6] 推力平衡与油耗计算...")
    balance = solve_balance(
        R_total_N=R_total, V_ship_ms=V_ship_ms,
        T_sail_N=T_sail_mean, P_rotor_W=P_rotor_mean,
    )
    fs = compute_fuel_saving(balance, duration_h=duration_h)

    if verbose:
        print(f"        无帆基线油耗 {fs.fuel_baseline_t:.2f} t (对照实船 {JI_SCENARIO_2_FUEL_T} t)")
        print(f"        有帆油耗 {fs.fuel_with_sail_t:.2f} t")
        print(f"        节油量 {fs.fuel_saved_t:.2f} t ({fs.saving_rate_pct:.2f}%)")
        print(f"        CO2 减排 {fs.co2_reduced_t:.2f} t")
        print()

    # ---------- Step 7: CII 评级 ----------
    if verbose:
        print("[Step 7] CII 评级...")
    cii_baseline = compute_cii(fs.fuel_baseline_t, ship.DWT, distance_nm)
    cii_with_sail = compute_cii(fs.fuel_with_sail_t, ship.DWT, distance_nm)
    bl = CIIBaseline()
    rating_baseline = cii_rating(cii_baseline, bl.required_cii_2024)
    rating_with_sail = cii_rating(cii_with_sail, bl.required_cii_2024)
    cii_imp_pct = cii_improvement(cii_baseline, cii_with_sail)

    if verbose:
        print(f"        基线 CII = {cii_baseline:.3f} gCO2/dwt·nm 评级 {rating_baseline}")
        print(f"        有帆 CII = {cii_with_sail:.3f} gCO2/dwt·nm 评级 {rating_with_sail}")
        print(f"        CII 改善率 {cii_imp_pct:.2f}%")
        print(f"        (基准占位 PH-01: required={bl.required_cii_2024})")
        print()

    # ---------- Step 8: 经济性 ----------
    if verbose:
        print("[Step 8] 经济性评估...")
    # Flettner 几何（单台）
    A_top = np.pi * (sail_D / 2) ** 2
    A_lateral = sail_H * sail_D
    V_rotor = np.pi * (sail_D / 2) ** 2 * sail_H
    cost = initial_cost(A_top, A_lateral, V_rotor) * n_sails

    annual_fuel_saved = fs.fuel_saved_t * trips_per_year
    annual_co2_reduced = fs.co2_reduced_t * trips_per_year
    savings = annual_savings(annual_fuel_saved, annual_co2_reduced)
    pb = payback_period(cost, savings["total_savings_usd"])
    npv_dict = npv(savings["total_savings_usd"], cost, years=[5, 10, 15, 20])
    sens = sensitivity(annual_fuel_saved, annual_co2_reduced, cost, years=10)

    if verbose:
        print(f"        初始投资 ${cost:,.0f}")
        print(f"        年节省 ${savings['total_savings_usd']:,.0f} ({trips_per_year} 航次/年)")
        print(f"        回收期 {pb:.1f} 年")
        print(f"        NPV 10y = ${npv_dict[10]:,.0f}")
        print(f"        NPV 20y = ${npv_dict[20]:,.0f}")
        print()

    # ---------- 汇总 ----------
    result = {
        "metadata": {
            "pipeline": "Phase A MVP",
            "timestamp": datetime.now().isoformat(),
            "scenario": "Ji 2023 Scenario 2 (Persian Gulf → Arabian Sea)",
        },
        "inputs": {
            "route": {
                "start": {"lat": start_lat, "lon": start_lon},
                "end": {"lat": end_lat, "lon": end_lon},
                "distance_km": float(distance_km),
                "distance_nm": float(distance_nm),
                "duration_h": float(duration_h),
                "V_ship_kn": float(V_ship_kn),
                "V_ship_ms": float(V_ship_ms),
                "n_waypoints": len(waypoints),
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
                "projected_area_per_sail": sail.projected_area,
                "projected_area_total": sail.projected_area * n_sails,
            },
        },
        "era5_samples": {
            "mean_wind_speed_ms": float(np.mean(np.sqrt(u10_arr**2 + v10_arr**2))),
            "mean_msl_pa": float(np.mean(msl_arr)),
            "mean_sst_k": float(np.mean(sst_arr)),
            "mean_rho_air": float(np.mean(rho_air_list)),
            "mean_V_apparent_ms": V_app_mean,
            "mean_SR_opt": SR_opt_mean,
        },
        "sail_performance": {
            "mean_thrust_kN": T_sail_mean / 1000,
            "mean_rotor_power_kW": P_rotor_mean / 1000,
            "mean_net_power_kW": (T_sail_mean * V_ship_ms - P_rotor_mean) / 1000,
        },
        "resistance": {
            "R_total_kN": R_total / 1000,
            "P_E_MW": res["P_E"] / 1e6,
            "1+k1": res["1+k1"],
            "C_F": res["C_F"],
            "C_R": res["C_R"],
        },
        "fuel_saving": {
            "fuel_baseline_t": fs.fuel_baseline_t,
            "fuel_with_sail_t": fs.fuel_with_sail_t,
            "fuel_saved_t": fs.fuel_saved_t,
            "saving_rate_pct": fs.saving_rate_pct,
            "co2_reduced_t": fs.co2_reduced_t,
            "co2_reduction_pct": fs.co2_reduction_pct,
            "target_fuel_t": JI_SCENARIO_2_FUEL_T,
            "baseline_error_pct": abs(fs.fuel_baseline_t - JI_SCENARIO_2_FUEL_T) / JI_SCENARIO_2_FUEL_T * 100,
        },
        "cii": {
            "baseline_cii": cii_baseline,
            "with_sail_cii": cii_with_sail,
            "rating_baseline": rating_baseline,
            "rating_with_sail": rating_with_sail,
            "improvement_pct": cii_imp_pct,
            "required_cii_placeholder": bl.required_cii_2024,
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
    print("Phase A MVP 结果汇总")
    print("=" * 72)
    print(f"{'指标':<30} {'值':>20} {'对照/单位':<20}")
    print("-" * 72)

    fs = result["fuel_saving"]
    print(f"{'基线油耗':<30} {fs['fuel_baseline_t']:>20.2f} {'t (实船 89.2 t)':<20}")
    print(f"{'基线误差':<30} {fs['baseline_error_pct']:>20.1f} {'% (容差 30%)':<20}")
    print(f"{'有帆油耗':<30} {fs['fuel_with_sail_t']:>20.2f} {'t':<20}")
    print(f"{'节油量':<30} {fs['fuel_saved_t']:>20.2f} {'t':<20}")
    print(f"{'节油率':<30} {fs['saving_rate_pct']:>20.2f} {'% (WASP 5-30%)':<20}")
    print(f"{'CO2 减排':<30} {fs['co2_reduced_t']:>20.2f} {'t':<20}")

    cii = result["cii"]
    rating_bl = cii["rating_baseline"]
    rating_sail = cii["rating_with_sail"]
    print(f"{'基线 CII':<30} {cii['baseline_cii']:>20.3f} {f'gCO2/dwt·nm ({rating_bl})':<20}")
    print(f"{'有帆 CII':<30} {cii['with_sail_cii']:>20.3f} {f'gCO2/dwt·nm ({rating_sail})':<20}")
    print(f"{'CII 改善率':<30} {cii['improvement_pct']:>20.2f} {'%':<20}")

    econ = result["economics"]
    print(f"{'初始投资':<30} {econ['initial_cost_usd']:>20,.0f} {'USD':<20}")
    print(f"{'年节省':<30} {econ['annual_savings_usd']:>20,.0f} {'USD':<20}")
    print(f"{'回收期':<30} {econ['payback_years']:>20.1f} {'年':<20}")
    print(f"{'NPV 10 年':<30} {econ['npv_10y']:>20,.0f} {'USD':<20}")
    print(f"{'NPV 20 年':<30} {econ['npv_20y']:>20,.0f} {'USD':<20}")
    print("=" * 72)


def save_result(result: dict, output_path: str | None = None) -> str:
    """保存结果到 JSON"""
    if output_path is None:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(RESULTS_DIR, f"phase_a_mvp_result_{ts}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    return output_path


def main():
    """主入口"""
    result = run_phase_a_mvp()
    print_summary(result)
    out = save_result(result)
    print(f"\n详细结果已保存: {out}")


if __name__ == "__main__":
    main()
