# -*- coding: utf-8 -*-
"""WASP 交互仪表盘 — 极薄 FastAPI 后端（复用现有 Python 计算，数值唯一真源）

设计原则:
    本服务不重写任何 CII / 经济性 / 物理公式。所有数值一律经 app.data_access
    调用现有 Python（与 Streamlit 仪表盘 100% 同源），前端只负责呈现与交互。

计算分层（与 dashboard.py 完全一致）:
    ① 经济性 / CII 后处理为纯算术，跑在预计算物理网格上 → da.pick_physics + da.postprocess
    ② 实船几何覆盖 / 非标准航速 / 非标准 SFOC → da.run_single_scenario（live 物理重算，
       首次数秒，functools.lru_cache 包裹后重复命中瞬时）

接口:
    GET  /api/health    健康检查
    GET  /api/options   一次性返回全部下拉/滑杆选项与默认值
    POST /api/scenario  单场景：复刻 dashboard live/grid 判定 → postprocess → 报告
    POST /api/recommendation  同一组用户参数下比较兼容帆型并生成推荐报告
    GET  /api/matrix    效益矩阵：固定船型/航线/季节，遍历 帆型 × 网格航速

运行:
    开发: uvicorn app.api:app --reload --port 8600   （前端 vite 5173 proxy /api）
    演示: npm run build 后 uvicorn app.api:app --port 8600（单端口同时供 /api 与前端 dist）
"""
import os
import sys
import json
import math
import functools
import glob
import threading
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(CODE_DIR)
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import (  # noqa: E402
    VALID_SHIP_TYPES, VALID_SAIL_TYPES, VALID_FLETTNER_SPECS, VALID_FUEL_TYPES,
    HOURS_PER_YEAR,
)
from core.realtime_prices import get_market_prices  # noqa: E402
import app.data_access as da  # noqa: E402
from app.report import (  # noqa: E402
    generate_report, generate_recommendation_report,
    SAIL_LABELS, SHIP_LABELS, SEASON_LABELS,
)
from analytics.cii import DEFAULT_CII_YEAR  # noqa: E402
from analytics.economics import discounted_cashflow_series  # noqa: E402

SPEED_TOL = 1e-6
STD_SFOC = 180.0

# 帆型实船报道节油率区间（%）— 与 dashboard.py SAIL_BENCH_RANGE 同源
# （dashboard.py 于模块顶层 import streamlit，无法直接复用，此处按同一常量重述）
SAIL_BENCH_RANGE = {
    "flettner": (6.0, 8.2, "Norsepower Estraden 6.1% / Pelican 8.2%"),
    "rigid_wing": (7.0, 14.0, "Oceanbird 7-10% / Pyxis Ocean ~14% (DNV)"),
    "suction_wing": (5.5, 8.0, "bound4blue Pacific Sentinel ~8%"),
}


# ═══════════════════════════════════════════════════════════
# 进程启动：加载物理网格一次
# ═══════════════════════════════════════════════════════════

META, DF = da.load_grid()
GRID_SPEEDS = [float(s) for s in META["speeds_kn"]]
SAIL_INSTALL = META["sail_install"]
ROUTES_META = META["routes"]
SEASONS_META = META["seasons"]
SHIP_META = META["ship_meta"]
SAIL_TYPES = list(META["sail_types"])
GRID_FLETTNER_SPEC = str(META.get("flettner_spec", "24x4"))
LIVE_DATA_AVAILABLE = bool(glob.glob(os.path.join(PROJECT_ROOT, "data", "*.nc")))
_LIVE_SEMAPHORE = threading.BoundedSemaphore(value=1)


@functools.lru_cache(maxsize=256)
def _cached_run_single(ship, speed_kn, route, season, sail,
                       flettner_spec, sfoc_g_per_kwh, overrides_key):
    """第②层 live 物理重算（按参数缓存，重复命中瞬时）。

    overrides_key: ship_overrides 的 JSON 串（保证可哈希）。
    """
    overrides = json.loads(overrides_key) if overrides_key else None
    return da.run_single_scenario(
        ship=ship, speed_kn=speed_kn, route=route, season=season, sail=sail,
        flettner_spec=flettner_spec, sfoc_g_per_kwh=sfoc_g_per_kwh,
        ship_overrides=overrides,
    )


def _to_jsonable(obj):
    """把 numpy 标量 / pandas 值转为原生 Python，供 JSON 序列化。"""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    # numpy 标量都实现 .item()
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return _to_jsonable(obj.item())
        except (ValueError, AttributeError):
            return obj
    return obj


# ═══════════════════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════════════════

app = FastAPI(title="WASP 风帆辅助推进效益 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ShipOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    DWT: Optional[float] = Field(None, gt=0)
    L: Optional[float] = Field(None, gt=0)
    B: Optional[float] = Field(None, gt=0)
    draft: Optional[float] = Field(None, gt=0)
    C_B: Optional[float] = Field(None, gt=0, lt=1)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ship: str
    speed: float = Field(14.0, ge=8.0, le=18.0)
    route: str
    season: str
    sail: str
    flettner_spec: str = "24x4"
    fuel_type: str = "VLSFO"
    fuel_price: float = Field(0.60, gt=0, le=10.0)       # USD/kg
    co2_price: float = Field(74.0, ge=0, le=1000.0)      # EUR/tCO2
    unit_cost: Optional[float] = Field(None, gt=0)       # USD/台
    sea_ratio: float = Field(0.742, gt=0, le=1)
    sfoc: float = Field(180.0, ge=100.0, le=400.0)       # g/kWh
    overrides: Optional[ShipOverrides] = None
    locale: Literal["zh", "en"] = "zh"
    cii_year: int = Field(DEFAULT_CII_YEAR, ge=2023, le=2026)


@app.get("/api/health")
def health():
    return {"status": "ok", "records": int(len(DF)), "speeds_kn": GRID_SPEEDS}


@app.get("/api/prices")
def prices(timezone: str = Query("Asia/Shanghai", min_length=1, max_length=64)):
    """根据浏览器时区自动匹配区域油价、碳价和汇率。

    客户端通过 ``Intl.DateTimeFormat().resolvedOptions().timeZone`` 获取
    IANA 时区并传入；响应同时返回实际采用的报价中心和显示时区。
    """
    return get_market_prices(timezone)


@app.get("/api/options")
def options():
    """一次性返回全部下拉/滑杆选项与默认值（前端首屏拉取一次）。"""
    ships = [s for s in VALID_SHIP_TYPES if s in SHIP_META]
    ship_options = [{
        "value": s,
        "label": SHIP_LABELS.get(s, s),
        "meta": _to_jsonable(SHIP_META[s]),
    } for s in ships]

    sail_options = [{
        "value": s,
        "label": SAIL_LABELS.get(s, s),
        "n_sails": SAIL_INSTALL[s],
        "bench": {
            "lo": SAIL_BENCH_RANGE.get(s, (0.0, 10.0, ""))[0],
            "hi": SAIL_BENCH_RANGE.get(s, (0.0, 10.0, ""))[1],
            "refs": SAIL_BENCH_RANGE.get(s, (0.0, 10.0, ""))[2],
        },
        "default_unit_cost": da.resolve_unit_cost(s),
    } for s in SAIL_TYPES]

    route_options = [{
        "value": r,
        "label": ROUTES_META[r]["name"],
        "waypoints": _to_jsonable(ROUTES_META[r]["waypoints"]),
    } for r in ROUTES_META]

    season_options = [{
        "value": s,
        "label": SEASON_LABELS.get(s, s),
    } for s in SEASONS_META]

    flettner_costs = {spec: da.resolve_unit_cost("flettner", spec)
                      for spec in VALID_FLETTNER_SPECS}

    return {
        "ships": ship_options,
        "sails": sail_options,
        "routes": route_options,
        "seasons": season_options,
        "speeds_kn": GRID_SPEEDS,
        "flettner_specs": (list(VALID_FLETTNER_SPECS) if LIVE_DATA_AVAILABLE
                            else [GRID_FLETTNER_SPEC]),
        "flettner_unit_costs": flettner_costs,
        "fuel_types": list(VALID_FUEL_TYPES),
        "ranges": {
            "speed": {
                "min": 8.0 if LIVE_DATA_AVAILABLE else min(GRID_SPEEDS),
                "max": 18.0 if LIVE_DATA_AVAILABLE else max(GRID_SPEEDS),
                "step": 0.5 if LIVE_DATA_AVAILABLE else min(
                    (b - a for a, b in zip(GRID_SPEEDS, GRID_SPEEDS[1:])),
                    default=1.0),
                "default": 14.0,
            },
            "fuel_price": {"min": 0.30, "max": 1.00, "step": 0.01, "default": 0.60},
            "co2_price": {"min": 0.0, "max": 150.0, "step": 1.0, "default": 74.0},
            "sea_ratio": {"min": 0.40, "max": 0.95, "step": 0.001, "default": 0.742},
            "unit_cost": {"min": 100000.0, "step": 50000.0},
            "sfoc": {"min": 140.0, "max": 220.0, "step": 1.0, "default": 180.0},
        },
        "defaults": {
            "ship": ships[0] if ships else None,
            "sail": SAIL_TYPES[0] if SAIL_TYPES else None,
            "route": next(iter(ROUTES_META), None),
            "season": next(iter(SEASONS_META), None),
            "fuel_type": VALID_FUEL_TYPES[0],
            "cii_year": DEFAULT_CII_YEAR,
        },
        "capabilities": {
            "live_physics": LIVE_DATA_AVAILABLE,
            "grid_flettner_spec": GRID_FLETTNER_SPEC,
        },
        "compatibility": {
            ship: {sail: da.get_compatibility(ship, sail) for sail in SAIL_TYPES}
            for ship in ships
        },
    }


def _validate_scenario(req: ScenarioRequest):
    if req.ship not in SHIP_META:
        raise HTTPException(400, f"未知船型: {req.ship}")
    if req.sail not in SAIL_TYPES:
        raise HTTPException(400, f"未知帆型: {req.sail}")
    if req.route not in ROUTES_META:
        raise HTTPException(400, f"未知航线: {req.route}")
    if req.season not in SEASONS_META:
        raise HTTPException(400, f"未知季节: {req.season}")
    if req.flettner_spec not in VALID_FLETTNER_SPECS:
        raise HTTPException(400, f"未知旋筒帆规格: {req.flettner_spec}")
    if req.fuel_type not in VALID_FUEL_TYPES:
        raise HTTPException(400, f"未知燃料类型: {req.fuel_type}")


@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    """单场景计算：完全复刻 dashboard.py L182-202 的 live/grid 判定与后处理。"""
    _validate_scenario(req)
    overrides = (req.overrides.model_dump(exclude_none=True)
                 if req.overrides is not None else None)

    speed_in_grid = any(abs(req.speed - g) < SPEED_TOL for g in GRID_SPEEDS)
    spec_requires_live = (req.sail == "flettner"
                          and req.flettner_spec != GRID_FLETTNER_SPEC)
    is_live = (bool(overrides) or (not speed_in_grid) or spec_requires_live
               or abs(req.sfoc - STD_SFOC) > SPEED_TOL)

    if is_live and not LIVE_DATA_AVAILABLE:
        raise HTTPException(
            503, "当前部署仅提供预计算网格；该输入需要 ERA5 live 物理重算")

    try:
        if is_live:
            if not _LIVE_SEMAPHORE.acquire(blocking=False):
                raise HTTPException(429, "已有 live 物理计算正在运行，请稍后重试")
            try:
                row = _cached_run_single(
                    req.ship, float(req.speed), req.route, req.season, req.sail,
                    req.flettner_spec, float(req.sfoc),
                    json.dumps(overrides, sort_keys=True) if overrides else "")
            finally:
                _LIVE_SEMAPHORE.release()
            ship_meta_for_pp = {"DWT": row["dwt"],
                                "ship_type_imo": row["ship_type_imo"],
                                "GT": row.get("GT")}
            speed_used, speed_exact = float(req.speed), True
        else:
            row = da.pick_physics(DF, req.ship, float(req.speed),
                                  req.route, req.season, req.sail)
            ship_meta_for_pp = SHIP_META[req.ship]
            speed_used, speed_exact = row["speed_used"], row["speed_exact"]
    except FileNotFoundError as e:
        raise HTTPException(503, f"live 物理重算依赖 ERA5 数据，当前不可用：{e}")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, "场景计算失败") from e

    cell = da.postprocess(
        row, ship=req.ship, sail=req.sail, sea_operating_ratio=req.sea_ratio,
        unit_cost_usd=req.unit_cost, flettner_spec=req.flettner_spec,
        fuel_type=req.fuel_type, fuel_price_usd_per_kg=req.fuel_price,
        co2_price_eur_per_t=req.co2_price, ship_meta=ship_meta_for_pp,
        cii_year=req.cii_year)

    duration_h = float(row["duration_h"])
    trips = req.sea_ratio * HOURS_PER_YEAR / duration_h if duration_h > 0 else 0.0
    unit_cost_used = (req.unit_cost if req.unit_cost is not None
                      else da.resolve_unit_cost(req.sail, req.flettner_spec))

    report_md = generate_report(
        ship=req.ship, sail=req.sail, route=req.route,
        route_name=ROUTES_META[req.route]["name"],
        season=req.season, speed_used=speed_used, speed_exact=speed_exact,
        physics=row, cell=cell, sea_operating_ratio=req.sea_ratio,
        fuel_type=req.fuel_type, fuel_price=req.fuel_price,
        co2_price=req.co2_price, unit_cost_usd=unit_cost_used,
        n_sails=SAIL_INSTALL[req.sail],
        flettner_spec=req.flettner_spec if req.sail == "flettner" else None,
        is_live=is_live, ship_overrides=overrides,
        locale=req.locale)

    lo, hi, refs = SAIL_BENCH_RANGE.get(req.sail, (0.0, 10.0, ""))
    cashflow = discounted_cashflow_series(
        float(cell["annual_savings_usd"]), float(cell["initial_cost_usd"]), 40)

    return {
        "cell": _to_jsonable(cell),
        "physics": _to_jsonable(row),
        "is_live": is_live,
        "speed_used": speed_used,
        "speed_exact": speed_exact,
        "trips_per_year": trips,
        "n_sails": SAIL_INSTALL[req.sail],
        "route_name": ROUTES_META[req.route]["name"],
        "route_waypoints": _to_jsonable(ROUTES_META[req.route]["waypoints"]),
        "unit_cost_used": unit_cost_used,
        "bench": {"lo": lo, "hi": hi, "refs": refs},
        "cashflow": _to_jsonable(cashflow),
        "quality": {
            "within_benchmark": lo <= float(cell["saving_rate_pct"]) <= hi,
            "compatibility": float(cell["compatibility"]),
            "raw_saving_rate_pct": float(cell["physics_saving_rate_pct"]),
            "saving_rate_pct_before_guardrail": float(
                cell["saving_rate_pct_before_guardrail"]),
            "screening_cap_pct": float(cell["screening_cap_pct"]),
            "guardrail_applied": bool(cell["guardrail_applied"]),
            "scenario_basis": "representative_voyage",
            "weather_years": [2025],
            "departure_samples_per_season": 1,
            "uncertainty_interval_available": False,
            "cii_year": req.cii_year,
        },
        "report_md": report_md,
    }


@app.post("/api/recommendation")
def recommendation(req: ScenarioRequest):
    """Compare every compatible sail using the exact same owner inputs.

    ``req.sail`` and ``req.unit_cost`` describe the currently inspected scenario
    and are intentionally ignored for cross-sail ranking. Each candidate uses
    its configured default unit cost so unlike technologies are compared on a
    consistent, auditable basis.
    """
    _validate_scenario(req)
    candidates = []
    for sail in SAIL_TYPES:
        if da.get_compatibility(req.ship, sail) <= 0:
            continue
        candidate_req = req.model_copy(update={"sail": sail, "unit_cost": None})
        result = scenario(candidate_req)
        cell = result["cell"]
        candidates.append({
            "sail": sail,
            "label": SAIL_LABELS.get(sail, sail),
            "n_sails": result["n_sails"],
            "saving_rate_pct": float(cell["saving_rate_pct"]),
            "annual_savings_usd": float(cell["annual_savings_usd"]),
            "initial_cost_usd": float(cell["initial_cost_usd"]),
            "payback_years": cell["payback_years"],
            "npv_10y_usd": float(cell["npv_10y_usd"]),
            "npv_20y_usd": float(cell["npv_20y_usd"]),
            "cii_rating_baseline": cell["cii_rating_baseline"],
            "cii_rating_with_sail": cell["cii_rating_with_sail"],
            "cii_improvement_pct": float(cell["cii_improvement_pct"]),
            "compatibility": float(cell["compatibility"]),
            "within_benchmark": bool(result["quality"]["within_benchmark"]),
            "guardrail_applied": bool(result["quality"]["guardrail_applied"]),
            "is_live": bool(result["is_live"]),
            "unit_cost_used": float(result["unit_cost_used"]),
        })

    if not candidates:
        raise HTTPException(422, "当前船型没有兼容的帆型候选")

    viable = [
        candidate for candidate in candidates
        if candidate["npv_20y_usd"] > 0
        and candidate["payback_years"] is not None
        and candidate["payback_years"] <= 20
    ]
    recommended = max(
        viable,
        key=lambda candidate: (
            candidate["npv_20y_usd"], -candidate["payback_years"]),
        default=None,
    )
    best_candidate = max(
        candidates,
        key=lambda candidate: (
            candidate["npv_20y_usd"],
            -(candidate["payback_years"]
              if candidate["payback_years"] is not None else float("inf"))),
    )
    decision = "install" if recommended is not None else "do_not_install"
    recommended_sail = recommended["sail"] if recommended else None

    report_md = generate_recommendation_report(
        ship=req.ship,
        route_name=ROUTES_META[req.route]["name"],
        season=req.season,
        speed=float(req.speed),
        candidates=candidates,
        decision=decision,
        recommended_sail=recommended_sail,
        best_candidate=best_candidate["sail"],
        locale=req.locale,
    )

    return {
        "decision": decision,
        "recommended_sail": recommended_sail,
        "best_candidate": best_candidate["sail"],
        "criteria": {
            "primary": "npv_20y_usd",
            "secondary": "payback_years",
            "investment_horizon_years": 20,
            "cost_basis": "default_by_sail",
        },
        "candidates": _to_jsonable(candidates),
        "report_md": report_md,
    }


@app.get("/api/matrix")
def matrix(ship: str, route: str, season: str,
           fuel_price: float = Query(0.60, gt=0, le=10.0),
           co2_price: float = Query(74.0, ge=0, le=1000.0),
           sea_ratio: float = Query(0.742, gt=0, le=1.0),
           fuel_type: str = "VLSFO",
           cii_year: int = Query(DEFAULT_CII_YEAR, ge=2023, le=2026)):
    """效益矩阵：固定 船型/航线/季节，遍历 帆型 × 网格航速（纯网格路径，快）。

    每个帆型采用其默认单台成本（保证 payback/年节省口径一致）。
    返回行=帆型、列=航速的 saving_rate_pct / annual_savings_usd / payback_years。
    """
    if ship not in SHIP_META:
        raise HTTPException(400, f"未知船型: {ship}")
    if route not in ROUTES_META:
        raise HTTPException(400, f"未知航线: {route}")
    if season not in SEASONS_META:
        raise HTTPException(400, f"未知季节: {season}")
    if fuel_type not in VALID_FUEL_TYPES:
        raise HTTPException(400, f"未知燃料类型: {fuel_type}")

    saving = []
    annual = []
    payback = []
    for sail in SAIL_TYPES:
        srow, arow, prow = [], [], []
        unit_cost = da.resolve_unit_cost(sail)
        for sp in GRID_SPEEDS:
            row = da.pick_physics(DF, ship, float(sp), route, season, sail)
            cell = da.postprocess(
                row, ship=ship, sail=sail, sea_operating_ratio=sea_ratio,
                unit_cost_usd=unit_cost, fuel_type=fuel_type,
                fuel_price_usd_per_kg=fuel_price, co2_price_eur_per_t=co2_price,
                ship_meta=SHIP_META[ship], cii_year=cii_year)
            srow.append(round(float(cell["saving_rate_pct"]), 4))
            arow.append(round(float(cell["annual_savings_usd"]), 2))
            pv = cell["payback_years"]
            prow.append(None if pv is None else round(float(pv), 2))
        saving.append(srow)
        annual.append(arow)
        payback.append(prow)

    return {
        "ship": ship,
        "route": route,
        "route_name": ROUTES_META[route]["name"],
        "season": season,
        "speeds": GRID_SPEEDS,
        "sails": SAIL_TYPES,
        "sail_labels": [SAIL_LABELS.get(s, s) for s in SAIL_TYPES],
        "saving_rate_pct": saving,
        "annual_savings_usd": annual,
        "payback_years": payback,
    }


# ═══════════════════════════════════════════════════════════
# 生产：挂载前端构建产物（dist/）；开发模式此目录不存在则跳过
# ═══════════════════════════════════════════════════════════

DIST_DIR = os.path.join(PROJECT_ROOT, "web", "frontend", "dist")
if os.path.isdir(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")
