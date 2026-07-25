# -*- coding: utf-8 -*-
"""前端-物理层取数适配层（无 Streamlit 依赖，可独立单测）

职责（计算分层的「取数 + 后处理」桥）:
    load_grid            读 physics_grid.json → (metadata, DataFrame 长表)
    pick_physics         按 船型/航速/航线/季节/帆型 取物理 cell（航速最近邻）
    to_sim_dict          还原成 evaluate_cell 所需的 sim dict
    postprocess          物理 cell + 经济性标量 → evaluate_cell 矩阵单元
    run_single_scenario  第②层实船几何覆盖 / 非标准航速 → live 物理重算

物理层字段来自 precompute_grid.py（SFOC 固定、代表船标准几何）；经济性 / CII
为纯算术后处理，由 postprocess 调 pipelines.phase_b_matrix.evaluate_cell 完成。
"""
import os
import sys
import json

import yaml
import pandas as pd

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import OwnerInputs, HOURS_PER_YEAR
from core.ship_params import (
    load_ship_params_by_type,
    apply_geometry_overrides,
    to_holtrop_input,
)
from core.route_definition import haversine_distance, KM_TO_NM, KN_TO_MS
from models.resistance.holtrop_mennen import compute_resistance
from analytics.cii import EMISSION_FACTORS, SHIP_TYPE_CII_PARAMS
from pipelines.phase_b_matrix import (
    build_sail,
    sample_route_weather,
    simulate_voyage,
    evaluate_cell,
    SAIL_INSTALL,
)
from pipelines.phase_b_full_voyage import generate_hourly_waypoints

DEFAULT_GRID_PATH = os.path.join(
    CODE_DIR, "results", "precomputed", "physics_grid.json"
)

# 物理层字段（与 precompute_grid.py 记录 schema 一致）
PHYSICS_FIELDS = (
    "fuel_baseline_kg", "fuel_with_sail_kg", "fuel_saved_kg",
    "saving_rate_pct", "mean_thrust_kN", "mean_power_kW", "mean_wind_ms",
)
# simulate_voyage 返回、evaluate_cell 读取的 sim dict 键（= PHYSICS_FIELDS）
SIM_KEYS = PHYSICS_FIELDS

# 物理层固定 SFOC（与 precompute_grid.GRID_SFOC_KG_PER_KWH 对齐）
GRID_SFOC_KG_PER_KWH = 0.180

# 船型帆型兼容性矩阵 (sail_types.yaml 加载)
_SAIL_CONFIG_PATH = os.path.join(CODE_DIR, "config", "sail_types.yaml")


def _load_compatibility_matrix() -> dict:
    """加载船型帆型兼容性矩阵 (1.0=完全兼容, 0.0=不兼容)"""
    with open(_SAIL_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("ship_sail_compatibility", {})


def get_compatibility(ship: str, sail: str) -> float:
    """查询特定船型×帆型的兼容性因子 (0.0-1.0)

    Returns:
        float: 1.0=完全兼容, 0.0=不兼容, 中间值=有条件兼容
    """
    compat = _load_compatibility_matrix()
    ship_compat = compat.get(ship, {})
    return float(ship_compat.get(sail, 1.0))


# ═══════════════════════════════════════════════════════════
# 取数
# ═══════════════════════════════════════════════════════════

def load_grid(path: str = DEFAULT_GRID_PATH) -> tuple[dict, pd.DataFrame]:
    """读 physics_grid.json → (metadata, 长表 DataFrame)

    Returns:
        (metadata, df)：df 每行一个物理 cell，列含
        ship/speed_kn/route/season/sail + 物理字段 + distance_nm/duration_h
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"物理层网格不存在: {path}\n"
            "请先运行 python code/pipelines/precompute_grid.py 生成。")
    with open(path, "r", encoding="utf-8") as f:
        grid = json.load(f)
    df = pd.DataFrame(grid["records"])
    return grid["metadata"], df


def available_speeds(df: pd.DataFrame, ship: str | None = None) -> list[float]:
    """网格中可用的标准航速集（升序）"""
    sub = df if ship is None else df[df["ship"] == ship]
    return sorted(float(s) for s in sub["speed_kn"].unique())


def pick_physics(df: pd.DataFrame, ship: str, speed: float, route: str,
                 season: str, sail: str) -> dict:
    """取单个物理 cell；航速不在标准集则取最接近并标注

    Returns:
        dict：物理字段 + distance_nm/duration_h + 元信息
              speed_requested / speed_used / speed_exact
    """
    mask = ((df["ship"] == ship) & (df["route"] == route)
            & (df["season"] == season) & (df["sail"] == sail))
    sub = df[mask]
    if sub.empty:
        raise KeyError(
            f"网格无匹配: ship={ship} route={route} season={season} sail={sail}")

    speeds = sub["speed_kn"].to_numpy(dtype=float)
    idx = int((abs(speeds - float(speed))).argmin())
    row = sub.iloc[idx].to_dict()
    used = float(row["speed_kn"])

    row["speed_requested"] = float(speed)
    row["speed_used"] = used
    row["speed_exact"] = abs(used - float(speed)) < 1e-6
    return row


def to_sim_dict(row: dict) -> dict:
    """从物理 cell 还原 evaluate_cell 所需的 sim dict"""
    return {k: float(row[k]) for k in SIM_KEYS}


# ═══════════════════════════════════════════════════════════
# 经济性 / CII 后处理（纯算术，前端实时）
# ═══════════════════════════════════════════════════════════

def resolve_unit_cost(sail: str, flettner_spec: str = "24x4") -> float:
    """帆型/规格默认单台成本（复用 OwnerInputs 单一真源）"""
    owner = OwnerInputs(sail_type=sail, flettner_spec=flettner_spec)
    return owner.resolved_unit_cost_usd()


def resolve_emission_factor(fuel_type: str) -> float:
    """燃料类型 → CO₂ 排放因子 C_F（tCO2/tFuel）"""
    return float(EMISSION_FACTORS[fuel_type])


def postprocess(row: dict, ship: str, sail: str,
                sea_operating_ratio: float = 0.742,
                unit_cost_usd: float | None = None,
                flettner_spec: str = "24x4",
                fuel_type: str = "VLSFO",
                fuel_price_usd_per_kg: float = 0.6,
                co2_price_eur_per_t: float = 74.0,
                ship_meta: dict | None = None) -> dict:
    """物理 cell + 经济性标量 → evaluate_cell 矩阵单元

    trips_per_year 由 duration_h 与 sea_operating_ratio 换算（= ratio×8765/时长），
    与 phase_b_matrix.run_matrix 口径一致。

    Args:
        row:  pick_physics / run_single_scenario 产出的物理 cell
        ship_meta: 可选 metadata["ship_meta"][ship]（含 DWT/ship_type_imo），
                   给定则免于重新加载船型（前端标准网格路径）
    """
    sim = to_sim_dict(row)
    total_nm = float(row["distance_nm"])
    duration_h = float(row["duration_h"])
    n_sails = SAIL_INSTALL[sail]

    annual_hours = sea_operating_ratio * HOURS_PER_YEAR
    trips_per_year = annual_hours / duration_h if duration_h > 0 else 0.0

    if unit_cost_usd is None:
        unit_cost_usd = resolve_unit_cost(sail, flettner_spec)
    emission_factor = resolve_emission_factor(fuel_type)

    # ship：优先用 metadata 里的标准几何摘要（免加载）；否则加载船型
    if ship_meta is not None and "DWT" in ship_meta:
        imo = ship_meta["ship_type_imo"]
        ship_dwt = ship_meta["DWT"]
        ship_gt = ship_meta.get("GT")
    else:
        loaded = load_ship_params_by_type(ship)
        imo = loaded.ship_type_imo
        ship_dwt = loaded.DWT
        ship_gt = loaded.GT

    # CII 容量基数：roro/vehicle carrier/cruise 等以 GT 为基数（MEPC.353(78)），
    # 其余船型用 DWT。GT 缺失则回退 DWT（cii_capacity=None 时 evaluate_cell 用 ship.DWT）。
    cap_type = SHIP_TYPE_CII_PARAMS.get(imo, {}).get("capacity_type", "DWT")
    cii_capacity = ship_gt if (cap_type == "GT" and ship_gt is not None) else None
    ship_obj = _ShipStub(ship_dwt, imo, cii_capacity)

    result = evaluate_cell(
        sim, ship_obj, total_nm, unit_cost_usd, n_sails, trips_per_year,
        emission_factor=emission_factor,
        cii_ship_type=ship_obj.ship_type_imo,
        fuel_price=fuel_price_usd_per_kg,
        co2_price=co2_price_eur_per_t,
        cii_capacity=ship_obj.cii_capacity,
    )

    # 添加兼容性因子（前端显示用）
    compat = get_compatibility(ship, sail)
    result["compatibility"] = compat
    result["compatible"] = compat > 0.0
    # 兼容性 < 1.0 时，按比例缩减效益并延长回收期
    if 0.0 < compat < 1.0:
        result["saving_rate_pct_adjusted"] = result.get("saving_rate_pct", 0) * compat
        if result.get("payback_years") and result["payback_years"] != float('inf'):
            result["payback_years_adjusted"] = result["payback_years"] / compat
        else:
            result["payback_years_adjusted"] = float('inf')
    elif compat == 0.0:
        result["saving_rate_pct_adjusted"] = 0.0
        result["payback_years_adjusted"] = float('inf')
    else:
        result["saving_rate_pct_adjusted"] = result.get("saving_rate_pct", 0)
        result["payback_years_adjusted"] = result.get("payback_years", float('inf'))

    return result


class _ShipStub:
    """evaluate_cell 仅访问 ship.DWT / ship.ship_type_imo，用轻量 stub 承载

    避免后处理路径每次都加载完整船型 yaml；标准几何下 DWT 恒定。
    cii_capacity 为 CII 容量基数（GT 基数船型传入船的 GT，None=回退 DWT）。
    """
    __slots__ = ("DWT", "ship_type_imo", "cii_capacity")

    def __init__(self, DWT: float, ship_type_imo: str,
                 cii_capacity: float | None = None) -> None:
        self.DWT = float(DWT)
        self.ship_type_imo = ship_type_imo
        self.cii_capacity = float(cii_capacity) if cii_capacity is not None else None


# ═══════════════════════════════════════════════════════════
# 第②层 live 物理重算（实船几何覆盖 / 非标准航速）
# ═══════════════════════════════════════════════════════════

def run_single_scenario(ship: str, speed_kn: float, route: str, season: str,
                        sail: str,
                        flettner_spec: str = "24x4",
                        sfoc_g_per_kwh: float = 180.0,
                        ship_overrides: dict | None = None,
                        routes_cfg: dict | None = None,
                        seasons_cfg: dict | None = None,
                        era5=None) -> dict:
    """单场景物理层 live 重算，返回与网格记录同 schema 的物理 cell

    用于第②层实船几何覆盖 / 非标准航速 / 非标准 SFOC（不进预计算网格）。
    ERA5 可传入复用；未传则加载并即时关闭（前端应以 st.cache_data 包裹本函数）。
    """
    if routes_cfg is None or seasons_cfg is None:
        import yaml
        from pipelines.phase_b_matrix import ROUTES_CONFIG
        with open(ROUTES_CONFIG, "r", encoding="utf-8") as f:
            rcfg = yaml.safe_load(f)
        routes_cfg = routes_cfg or rcfg["routes"]
        seasons_cfg = seasons_cfg or rcfg["seasons"]

    if route not in routes_cfg:
        raise KeyError(f"未知航线: {route}")
    if season not in seasons_cfg:
        raise KeyError(f"未知季节: {season}")

    # 船型（可叠加实船几何覆盖）
    ship_obj = load_ship_params_by_type(ship)
    if ship_overrides:
        ship_obj = apply_geometry_overrides(ship_obj, ship_overrides)

    V_ship_ms = speed_kn * KN_TO_MS
    R_total = compute_resistance(to_holtrop_input(ship_obj), V_ship_ms)["R_total"]

    sail_obj, n_sails, _uc, _area, _label = build_sail(
        sail, flettner_spec if sail == "flettner" else None)

    route_wps_def = [tuple(wp) for wp in routes_cfg[route]["waypoints"]]
    start_time = seasons_cfg[season]
    waypoints = generate_hourly_waypoints(route_wps_def, start_time, speed_kn)
    total_km = sum(
        haversine_distance(waypoints[i].lat, waypoints[i].lon,
                           waypoints[i + 1].lat, waypoints[i + 1].lon)
        for i in range(len(waypoints) - 1)
    )
    total_nm = total_km * KM_TO_NM
    duration_h = len(waypoints) - 1

    _own_era5 = era5 is None
    if _own_era5:
        from core.era5_loader import load_era5_from_config
        era5 = load_era5_from_config()
    try:
        weather = sample_route_weather(era5, waypoints)
        sim = simulate_voyage(sail_obj, n_sails, waypoints, weather,
                              R_total, V_ship_ms, sfoc_g_per_kwh / 1000.0)
    finally:
        if _own_era5:
            era5.close()

    return {
        "ship": ship,
        "speed_kn": float(speed_kn),
        "route": route,
        "season": season,
        "sail": sail,
        "distance_nm": round(total_nm, 1),
        "duration_h": duration_h,
        "fuel_baseline_kg": sim["fuel_baseline_kg"],
        "fuel_with_sail_kg": sim["fuel_with_sail_kg"],
        "fuel_saved_kg": sim["fuel_saved_kg"],
        "saving_rate_pct": sim["saving_rate_pct"],
        "mean_thrust_kN": sim["mean_thrust_kN"],
        "mean_power_kW": sim["mean_power_kW"],
        "mean_wind_ms": sim["mean_wind_ms"],
        "ship_overrides": ship_overrides,
        "dwt": ship_obj.DWT,
        "ship_type_imo": ship_obj.ship_type_imo,
        "GT": ship_obj.GT,
    }
