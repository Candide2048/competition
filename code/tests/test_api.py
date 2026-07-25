# -*- coding: utf-8 -*-
"""极薄 FastAPI 后端测试（app/api.py）

核心验收（数值唯一真源）:
    - /api/scenario 对同一组输入的返回 **逐字段等于** da.pick_physics + da.postprocess
      的直接计算结果（金标准，杜绝前后端数值分歧）。
    - /api/options 字段齐全，船型/帆型/航线/季节与 metadata 一致。
    - /api/matrix 维度正确（帆型 × 网格航速），saving_rate 与逐格 postprocess 一致。

全部走网格路径（无需 ERA5）；live 物理重算另在 test_data_access.py 覆盖。

运行方式:
    cd shipping_wasp/code
    python -m pytest tests/test_api.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import app.api as api
import app.data_access as da


@pytest.fixture(scope="module")
def client():
    return TestClient(api.app)


# ═══════════════════════════════════════════════════════════
# /api/health
# ═══════════════════════════════════════════════════════════

def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["records"] == len(api.DF)
    assert body["speeds_kn"] == api.GRID_SPEEDS


# ═══════════════════════════════════════════════════════════
# /api/options
# ═══════════════════════════════════════════════════════════

def test_options_complete(client):
    o = client.get("/api/options").json()
    # 船型：与 metadata 一致
    assert [s["value"] for s in o["ships"]] == [
        s for s in api.VALID_SHIP_TYPES if s in api.SHIP_META]
    # 每个船型带 label + meta（含 DWT/ship_type_imo）
    for s in o["ships"]:
        assert s["label"]
        assert "DWT" in s["meta"] and "ship_type_imo" in s["meta"]
    # 帆型：带台数 + bench 区间 + 默认单价
    for s in o["sails"]:
        assert s["n_sails"] == api.SAIL_INSTALL[s["value"]]
        assert set(s["bench"]) == {"lo", "hi", "refs"}
        assert s["default_unit_cost"] > 0
    # 航线：带 name + waypoints
    for r in o["routes"]:
        assert r["label"]
        assert isinstance(r["waypoints"], list) and len(r["waypoints"]) >= 2
    # 季节 / 航速集 / 燃料 / 区间 / 默认
    assert [s["value"] for s in o["seasons"]] == list(api.SEASONS_META)
    assert o["speeds_kn"] == api.GRID_SPEEDS
    assert o["fuel_types"] == list(api.VALID_FUEL_TYPES)
    assert set(o["ranges"]) >= {"speed", "fuel_price", "co2_price",
                                "sea_ratio", "unit_cost", "sfoc"}
    assert o["defaults"]["ship"] in api.SHIP_META


def test_options_flettner_costs(client):
    o = client.get("/api/options").json()
    for spec in api.VALID_FLETTNER_SPECS:
        assert spec in o["flettner_unit_costs"]
        assert o["flettner_unit_costs"][spec] == da.resolve_unit_cost(
            "flettner", spec)


# ═══════════════════════════════════════════════════════════
# /api/scenario —— 金标准逐字段对齐
# ═══════════════════════════════════════════════════════════

_BASE_REQ = {
    "ship": "pctc",
    "speed": 14.0,           # 网格标准航速 → grid 路径
    "route": "middle_east_china",
    "season": "winter",
    "sail": "rigid_wing",
    "flettner_spec": "24x4",
    "fuel_type": "VLSFO",
    "fuel_price": 0.60,
    "co2_price": 74.0,
    "unit_cost": None,
    "sea_ratio": 0.742,
    "sfoc": 180.0,
    "overrides": None,
}


def _gold_cell(req):
    """直接用 data_access 计算金标准 cell（后端应逐字段等于此）。"""
    row = da.pick_physics(api.DF, req["ship"], float(req["speed"]),
                          req["route"], req["season"], req["sail"])
    cell = da.postprocess(
        row, ship=req["ship"], sail=req["sail"],
        sea_operating_ratio=req["sea_ratio"], unit_cost_usd=req["unit_cost"],
        flettner_spec=req["flettner_spec"], fuel_type=req["fuel_type"],
        fuel_price_usd_per_kg=req["fuel_price"],
        co2_price_eur_per_t=req["co2_price"],
        ship_meta=api.SHIP_META[req["ship"]])
    return row, cell


def test_scenario_matches_gold_standard(client):
    resp = client.post("/api/scenario", json=_BASE_REQ).json()
    row, gold = _gold_cell(_BASE_REQ)

    # cell 逐字段等于金标准
    assert set(resp["cell"]) == set(gold)
    for k, v in gold.items():
        rv = resp["cell"][k]
        if isinstance(v, float):
            assert rv == pytest.approx(v, rel=1e-9, abs=1e-9), f"字段 {k} 不一致"
        else:
            assert rv == v, f"字段 {k} 不一致"

    # 网格标准航速 → grid 路径
    assert resp["is_live"] is False
    assert resp["speed_exact"] is True
    assert resp["speed_used"] == pytest.approx(14.0)
    assert resp["n_sails"] == api.SAIL_INSTALL[_BASE_REQ["sail"]]


def test_scenario_physics_matches(client):
    resp = client.post("/api/scenario", json=_BASE_REQ).json()
    row, _ = _gold_cell(_BASE_REQ)
    for k in ("distance_nm", "duration_h", "fuel_baseline_kg",
              "mean_wind_ms", "saving_rate_pct"):
        assert resp["physics"][k] == pytest.approx(float(row[k]), rel=1e-9)


def test_scenario_pctc_uses_gt_capacity(client):
    """PCTC 以 GT 为 CII 容量基数：后端结果须与 postprocess(ship_meta=GT) 一致。"""
    resp = client.post("/api/scenario", json=_BASE_REQ).json()
    _, gold = _gold_cell(_BASE_REQ)
    assert resp["cell"]["cii_baseline"] == pytest.approx(
        gold["cii_baseline"], rel=1e-9)
    assert resp["cell"]["cii_rating_baseline"] == gold["cii_rating_baseline"]


def test_scenario_report_and_bench(client):
    resp = client.post("/api/scenario", json=_BASE_REQ).json()
    assert "风帆辅助推进效益分析报告" in resp["report_md"]
    assert set(resp["bench"]) == {"lo", "hi", "refs"}
    assert resp["route_name"] == api.ROUTES_META[_BASE_REQ["route"]]["name"]
    assert len(resp["route_waypoints"]) >= 2


def test_scenario_economic_sliders_change_result(client):
    """经济性滑杆改变 → 年节省应随油价变化（纯算术后处理生效）。"""
    low = dict(_BASE_REQ, fuel_price=0.40)
    high = dict(_BASE_REQ, fuel_price=0.90)
    r_low = client.post("/api/scenario", json=low).json()
    r_high = client.post("/api/scenario", json=high).json()
    assert (r_high["cell"]["annual_savings_usd"]
            > r_low["cell"]["annual_savings_usd"])
    # 物理量（节油率）不随经济性变化
    assert r_high["cell"]["saving_rate_pct"] == pytest.approx(
        r_low["cell"]["saving_rate_pct"], rel=1e-9)


def test_scenario_invalid_inputs_return_400(client):
    for bad in [
        dict(_BASE_REQ, ship="not_a_ship"),
        dict(_BASE_REQ, sail="not_a_sail"),
        dict(_BASE_REQ, route="not_a_route"),
        dict(_BASE_REQ, season="not_a_season"),
    ]:
        r = client.post("/api/scenario", json=bad)
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════
# /api/matrix
# ═══════════════════════════════════════════════════════════

def test_matrix_dimensions_and_values(client):
    r = client.get("/api/matrix", params={
        "ship": "kvlcc2", "route": "middle_east_china", "season": "summer",
        "fuel_price": 0.60, "co2_price": 74.0, "sea_ratio": 0.742})
    assert r.status_code == 200
    m = r.json()
    assert m["sails"] == api.SAIL_TYPES
    assert m["speeds"] == api.GRID_SPEEDS
    # 维度：行=帆型、列=航速
    assert len(m["saving_rate_pct"]) == len(api.SAIL_TYPES)
    assert all(len(row) == len(api.GRID_SPEEDS)
               for row in m["saving_rate_pct"])

    # 抽一格与直接 postprocess 对齐（首帆型、首航速）
    sail0 = api.SAIL_TYPES[0]
    sp0 = api.GRID_SPEEDS[0]
    row = da.pick_physics(api.DF, "kvlcc2", float(sp0),
                          "middle_east_china", "summer", sail0)
    cell = da.postprocess(
        row, ship="kvlcc2", sail=sail0, sea_operating_ratio=0.742,
        unit_cost_usd=da.resolve_unit_cost(sail0), fuel_type="VLSFO",
        fuel_price_usd_per_kg=0.60, co2_price_eur_per_t=74.0,
        ship_meta=api.SHIP_META["kvlcc2"])
    assert m["saving_rate_pct"][0][0] == pytest.approx(
        round(float(cell["saving_rate_pct"]), 4), rel=1e-9)


def test_matrix_invalid_ship_400(client):
    r = client.get("/api/matrix", params={
        "ship": "nope", "route": "middle_east_china", "season": "winter"})
    assert r.status_code == 400
