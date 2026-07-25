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
    GET  /api/matrix    效益矩阵：固定船型/航线/季节，遍历 帆型 × 网格航速

运行:
    开发: uvicorn app.api:app --reload --port 8600   （前端 vite 5173 proxy /api）
    演示: npm run build 后 uvicorn app.api:app --port 8600（单端口同时供 /api 与前端 dist）
"""
import os
import sys
import json
import functools
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import (  # noqa: E402
    VALID_SHIP_TYPES, VALID_SAIL_TYPES, VALID_FLETTNER_SPECS, VALID_FUEL_TYPES,
    HOURS_PER_YEAR,
)
from core.realtime_prices import get_market_prices  # noqa: E402
import app.data_access as da  # noqa: E402
from app.report import (  # noqa: E402
    generate_report, SAIL_LABELS, SHIP_LABELS, SEASON_LABELS,
)

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
    # numpy 标量都实现 .item()
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return obj.item()
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


class ScenarioRequest(BaseModel):
    ship: str
    speed: float = 14.0
    route: str
    season: str
    sail: str
    flettner_spec: str = "24x4"
    fuel_type: str = "VLSFO"
    fuel_price: float = 0.60          # USD/kg
    co2_price: float = 74.0           # EUR/tCO2
    unit_cost: Optional[float] = None  # USD/台；None → 用帆型默认
    sea_ratio: float = 0.742
    sfoc: float = 180.0               # g/kWh
    overrides: Optional[dict] = None  # 实船几何覆盖 {DWT,L,B,draft,C_B}
    locale: str = "zh"                # 报告语言 zh|en


@app.get("/api/health")
def health():
    return {"status": "ok", "records": int(len(DF)), "speeds_kn": GRID_SPEEDS}


@app.get("/api/prices")
def prices(timezone: str = "Asia/Shanghai"):
    """实时市场价格：根据客户端时区自动匹配区域油价/碳价/汇率。

    前端首屏拉取一次（或用户手动刷新），返回含数据来源 + 时间戳的完整价格快照。
    客户端通过 Intl.DateTimeFormat().resolvedOptions().timeZone 获取时区传入。
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
        "flettner_specs": list(VALID_FLETTNER_SPECS),
        "flettner_unit_costs": flettner_costs,
        "fuel_types": list(VALID_FUEL_TYPES),
        "ranges": {
            "speed": {"min": 8.0, "max": 18.0, "step": 0.5, "default": 14.0},
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


@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    """单场景计算：完全复刻 dashboard.py L182-202 的 live/grid 判定与后处理。"""
    _validate_scenario(req)
    overrides = req.overrides or None

    speed_in_grid = any(abs(req.speed - g) < SPEED_TOL for g in GRID_SPEEDS)
    is_live = (bool(overrides) or (not speed_in_grid)
               or abs(req.sfoc - STD_SFOC) > SPEED_TOL)

    try:
        if is_live:
            row = _cached_run_single(
                req.ship, float(req.speed), req.route, req.season, req.sail,
                req.flettner_spec, float(req.sfoc),
                json.dumps(overrides, sort_keys=True) if overrides else "")
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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"场景计算失败：{e}")

    cell = da.postprocess(
        row, ship=req.ship, sail=req.sail, sea_operating_ratio=req.sea_ratio,
        unit_cost_usd=req.unit_cost, flettner_spec=req.flettner_spec,
        fuel_type=req.fuel_type, fuel_price_usd_per_kg=req.fuel_price,
        co2_price_eur_per_t=req.co2_price, ship_meta=ship_meta_for_pp)

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
        "report_md": report_md,
    }


@app.get("/api/matrix")
def matrix(ship: str, route: str, season: str,
           fuel_price: float = 0.60, co2_price: float = 74.0,
           sea_ratio: float = 0.742, fuel_type: str = "VLSFO"):
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
                ship_meta=SHIP_META[ship])
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

PROJECT_ROOT = os.path.dirname(CODE_DIR)
DIST_DIR = os.path.join(PROJECT_ROOT, "web", "frontend", "dist")
if os.path.isdir(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")
