# -*- coding: utf-8 -*-
"""前端-物理层取数适配层单元测试（app/data_access.py）

验证目标（计算分层的「取数 + 后处理」桥）:
    - load_grid：读 physics_grid.json → (metadata, DataFrame) schema 正确
    - pick_physics：航速最近邻取数、精确/近似标注、未命中报错
    - to_sim_dict：还原 evaluate_cell 所需 sim dict，键齐全
    - resolve_unit_cost / resolve_emission_factor：与单一真源一致
    - postprocess：物理 cell → evaluate_cell 桥接与 run_matrix 单元一致（1e-6）
    - run_single_scenario：第②层 live 物理重算 schema + 实船几何覆盖生效（依赖 ERA5）

大部分测试用合成网格，无需 ERA5；仅 live 重算类用 ERA5 fixture（模块级共享）。

运行方式:
    cd shipping_wasp/code
    python -m pytest tests/test_data_access.py -v
"""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.data_access as da
from core.owner_inputs import OwnerInputs, HOURS_PER_YEAR
from analytics.cii import EMISSION_FACTORS
from pipelines.phase_b_matrix import evaluate_cell, SAIL_INSTALL


# ═══════════════════════════════════════════════════════════
# 合成网格（无需 ERA5，用于取数/后处理桥测试）
# ═══════════════════════════════════════════════════════════

_SHIP = "kvlcc2"
_SAIL = "flettner"
_ROUTE = "arabian_sea_route"
_SEASON = "winter"
# 一条量级合理的合成物理 cell（数值人工设定，仅测桥接逻辑）
_PHYS = {
    "distance_nm": 3000.0,
    "duration_h": 214,
    "fuel_baseline_kg": 900000.0,
    "fuel_with_sail_kg": 837000.0,
    "fuel_saved_kg": 63000.0,
    "saving_rate_pct": 7.0,
    "mean_thrust_kN": 120.0,
    "mean_power_kW": 300.0,
    "mean_wind_ms": 9.5,
}
_SHIP_META = {"DWT": 300000.0, "ship_type_imo": "tanker"}


def _make_record(speed_kn):
    rec = {"ship": _SHIP, "speed_kn": float(speed_kn), "route": _ROUTE,
           "season": _SEASON, "sail": _SAIL}
    rec.update(_PHYS)
    return rec


@pytest.fixture(scope="module")
def synthetic_grid_path(tmp_path_factory):
    """写一个含两航速的合成 physics_grid.json，用于 load_grid/pick_physics 测试"""
    grid = {
        "metadata": {
            "pipeline": "test",
            "sfoc_kg_per_kwh": 0.180,
            "flettner_spec": "24x4",
            "speeds_kn": [12.0, 16.0],
            "ships": [_SHIP],
            "sail_types": [_SAIL],
            "sail_install": {_SAIL: SAIL_INSTALL[_SAIL]},
            "ship_meta": {_SHIP: _SHIP_META},
            "routes": {_ROUTE: {"name": "阿拉伯海航线",
                                "waypoints": [[10.0, 60.0], [20.0, 70.0]]}},
            "seasons": {_SEASON: "2025-01-15T00:00:00"},
            "n_records": 2,
        },
        "records": [_make_record(12.0), _make_record(16.0)],
    }
    p = tmp_path_factory.mktemp("grid") / "physics_grid.json"
    with open(str(p), "w", encoding="utf-8") as f:
        json.dump(grid, f, ensure_ascii=False)
    return str(p)


# ═══════════════════════════════════════════════════════════
# load_grid
# ═══════════════════════════════════════════════════════════

class TestLoadGrid:

    def test_returns_metadata_and_dataframe(self, synthetic_grid_path):
        meta, df = da.load_grid(synthetic_grid_path)
        assert isinstance(meta, dict)
        assert len(df) == 2
        for col in ("ship", "speed_kn", "route", "season", "sail"):
            assert col in df.columns
        for col in da.PHYSICS_FIELDS:
            assert col in df.columns

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            da.load_grid(os.path.join("nonexistent_dir", "physics_grid.json"))

    def test_available_speeds(self, synthetic_grid_path):
        _meta, df = da.load_grid(synthetic_grid_path)
        assert da.available_speeds(df) == [12.0, 16.0]
        assert da.available_speeds(df, ship=_SHIP) == [12.0, 16.0]


# ═══════════════════════════════════════════════════════════
# pick_physics（航速最近邻）
# ═══════════════════════════════════════════════════════════

class TestPickPhysics:

    def test_exact_speed(self, synthetic_grid_path):
        _meta, df = da.load_grid(synthetic_grid_path)
        row = da.pick_physics(df, _SHIP, 12.0, _ROUTE, _SEASON, _SAIL)
        assert row["speed_used"] == 12.0
        assert row["speed_requested"] == 12.0
        assert row["speed_exact"] is True

    def test_nearest_speed_low(self, synthetic_grid_path):
        _meta, df = da.load_grid(synthetic_grid_path)
        row = da.pick_physics(df, _SHIP, 13.0, _ROUTE, _SEASON, _SAIL)
        assert row["speed_used"] == 12.0  # 13 距 12 更近
        assert row["speed_exact"] is False

    def test_nearest_speed_high(self, synthetic_grid_path):
        _meta, df = da.load_grid(synthetic_grid_path)
        row = da.pick_physics(df, _SHIP, 15.0, _ROUTE, _SEASON, _SAIL)
        assert row["speed_used"] == 16.0  # 15 距 16 更近
        assert row["speed_exact"] is False

    def test_unknown_combo_raises(self, synthetic_grid_path):
        _meta, df = da.load_grid(synthetic_grid_path)
        with pytest.raises(KeyError):
            da.pick_physics(df, _SHIP, 12.0, "no_such_route", _SEASON, _SAIL)


# ═══════════════════════════════════════════════════════════
# to_sim_dict
# ═══════════════════════════════════════════════════════════

class TestToSimDict:

    def test_extracts_sim_keys(self):
        sim = da.to_sim_dict(_make_record(14.0))
        assert set(sim.keys()) == set(da.SIM_KEYS)
        for v in sim.values():
            assert isinstance(v, float)

    def test_values_match(self):
        row = _make_record(14.0)
        sim = da.to_sim_dict(row)
        for k in da.SIM_KEYS:
            assert sim[k] == pytest.approx(row[k])


# ═══════════════════════════════════════════════════════════
# resolve 辅助
# ═══════════════════════════════════════════════════════════

class TestResolvers:

    def test_unit_cost_matches_owner(self):
        for spec in ("20x4", "24x4", "28x4"):
            owner = OwnerInputs(sail_type="flettner", flettner_spec=spec)
            assert da.resolve_unit_cost("flettner", spec) == owner.resolved_unit_cost_usd()

    def test_emission_factor_matches_table(self):
        for fuel in ("VLSFO", "MGO", "LNG", "METHANOL"):
            assert da.resolve_emission_factor(fuel) == EMISSION_FACTORS[fuel]


# ═══════════════════════════════════════════════════════════
# postprocess 桥接与 run_matrix 单元一致（回归对齐，1e-6）
# ═══════════════════════════════════════════════════════════

class TestPostprocessBridge:
    """postprocess 应精确复现 run_matrix 的 evaluate_cell 单元"""

    _SEA_RATIO = 0.742
    _UNIT_COST = 1_500_000.0
    _FUEL_TYPE = "VLSFO"
    _FUEL_PRICE = 0.60
    _CO2_PRICE = 74.0

    def _reference_cell(self, row):
        """独立复现 run_matrix 内 evaluate_cell 的调用（同参数口径）"""
        sim = da.to_sim_dict(row)
        total_nm = float(row["distance_nm"])
        duration_h = float(row["duration_h"])
        n_sails = SAIL_INSTALL[_SAIL]
        trips = self._SEA_RATIO * HOURS_PER_YEAR / duration_h
        ship_stub = da._ShipStub(_SHIP_META["DWT"], _SHIP_META["ship_type_imo"])
        return evaluate_cell(
            sim, ship_stub, total_nm, self._UNIT_COST, n_sails, trips,
            emission_factor=EMISSION_FACTORS[self._FUEL_TYPE],
            cii_ship_type=_SHIP_META["ship_type_imo"],
            fuel_price=self._FUEL_PRICE, co2_price=self._CO2_PRICE,
        )

    def test_postprocess_matches_reference(self):
        row = _make_record(14.0)
        cell = da.postprocess(
            row, ship=_SHIP, sail=_SAIL, sea_operating_ratio=self._SEA_RATIO,
            unit_cost_usd=self._UNIT_COST, fuel_type=self._FUEL_TYPE,
            fuel_price_usd_per_kg=self._FUEL_PRICE,
            co2_price_eur_per_t=self._CO2_PRICE, ship_meta=_SHIP_META)
        ref = self._reference_cell(row)
        assert set(cell.keys()) == set(ref.keys())
        for k in ref:
            if isinstance(ref[k], (int, float)) and ref[k] is not None:
                assert cell[k] == pytest.approx(ref[k], abs=1e-6), f"字段 {k} 不一致"
            else:
                assert cell[k] == ref[k], f"字段 {k} 不一致"

    def test_postprocess_positive_and_valid(self):
        row = _make_record(14.0)
        cell = da.postprocess(
            row, ship=_SHIP, sail=_SAIL, ship_meta=_SHIP_META)
        assert cell["fuel_saved_t"] > 0
        assert cell["co2_reduced_t"] > 0
        assert cell["initial_cost_usd"] > 0
        assert cell["cii_rating_with_sail"] in ("A", "B", "C", "D", "E")

    def test_postprocess_without_ship_meta_loads_ship(self):
        """未给 ship_meta 时应回退到按船型加载（DWT/CII 船型一致）"""
        row = _make_record(14.0)
        cell_meta = da.postprocess(row, ship=_SHIP, sail=_SAIL,
                                   ship_meta=_SHIP_META)
        cell_load = da.postprocess(row, ship=_SHIP, sail=_SAIL,
                                   ship_meta=None)
        # kvlcc2 的 DWT 与 CII 船型和 _SHIP_META 一致 → CII/初始成本一致
        assert cell_load["cii_baseline"] == pytest.approx(cell_meta["cii_baseline"])


# ═══════════════════════════════════════════════════════════
# PCTC 走 GT 容量基数（MEPC.353(78)：roro/vehicle carrier 用 GT，非 DWT）
# ═══════════════════════════════════════════════════════════

_PCTC_META_GT = {"DWT": 18000.0, "ship_type_imo": "roro_cargo_vehicle",
                 "GT": 62000.0}
_PCTC_META_NOGT = {"DWT": 18000.0, "ship_type_imo": "roro_cargo_vehicle"}


def _make_pctc_record(speed_kn=14.0):
    rec = {"ship": "pctc", "speed_kn": float(speed_kn), "route": _ROUTE,
           "season": _SEASON, "sail": _SAIL}
    rec.update(_PHYS)
    return rec


class TestPctcGTCapacity:
    """PCTC(roro_cargo_vehicle) 的 CII 应以 GT 为容量基数，而非 DWT"""

    def test_pctc_uses_gt_capacity(self):
        """提供 GT 时 CII 绝对值走 GT 基数，与用 DWT 的结果不同（GT>DWT → CII 更小）"""
        row = _make_pctc_record()
        cell_gt = da.postprocess(row, ship="pctc", sail=_SAIL,
                                 ship_meta=_PCTC_META_GT)
        cell_dwt = da.postprocess(row, ship="pctc", sail=_SAIL,
                                  ship_meta=_PCTC_META_NOGT)
        assert cell_gt["cii_baseline"] < cell_dwt["cii_baseline"]
        # CII 与容量成反比 → 比例恰为 DWT/GT（cii_baseline 四舍五入到 4 位，宽容差）
        assert cell_gt["cii_baseline"] == pytest.approx(
            cell_dwt["cii_baseline"] * 18000.0 / 62000.0, abs=1e-3)

    def test_cii_improvement_capacity_independent(self):
        """CII 改善率分子分母同缩放容量 → 与容量基数无关（回归）"""
        row = _make_pctc_record()
        cell_gt = da.postprocess(row, ship="pctc", sail=_SAIL,
                                 ship_meta=_PCTC_META_GT)
        cell_dwt = da.postprocess(row, ship="pctc", sail=_SAIL,
                                  ship_meta=_PCTC_META_NOGT)
        assert cell_gt["cii_improvement_pct"] == pytest.approx(
            cell_dwt["cii_improvement_pct"], abs=1e-9)
        assert cell_gt["saving_rate_pct"] == pytest.approx(
            cell_dwt["saving_rate_pct"], abs=1e-9)


# ═══════════════════════════════════════════════════════════
# run_single_scenario（第②层 live 物理重算，依赖 ERA5）
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def era5():
    from core.era5_loader import load_era5_from_config
    ds = load_era5_from_config()
    yield ds
    ds.close()


class TestRunSingleScenario:
    """live 物理重算 schema 与实船几何覆盖生效"""

    def test_standard_scenario_schema(self, era5):
        row = da.run_single_scenario(
            ship=_SHIP, speed_kn=13.0, route="arabian_sea",
            season="winter", sail="flettner", era5=era5)
        for f in ("ship", "speed_kn", "route", "season", "sail",
                  "distance_nm", "duration_h", "dwt", "ship_type_imo"):
            assert f in row
        for f in da.PHYSICS_FIELDS:
            assert f in row
        assert row["distance_nm"] > 0
        assert row["duration_h"] > 0
        assert row["fuel_baseline_kg"] > 0
        assert 0.0 <= row["saving_rate_pct"] < 100.0

    def test_postprocess_on_live_row(self, era5):
        row = da.run_single_scenario(
            ship=_SHIP, speed_kn=13.0, route="arabian_sea",
            season="winter", sail="flettner", era5=era5)
        ship_meta = {"DWT": row["dwt"], "ship_type_imo": row["ship_type_imo"]}
        cell = da.postprocess(row, ship=_SHIP, sail="flettner",
                              ship_meta=ship_meta)
        assert cell["fuel_saved_t"] >= 0
        assert cell["cii_rating_with_sail"] in ("A", "B", "C", "D", "E")

    def test_dwt_override_changes_dwt(self, era5):
        """直接覆盖 DWT 应改变返回行的 dwt（第②层生效）"""
        base = da.run_single_scenario(
            ship=_SHIP, speed_kn=14.0, route="arabian_sea",
            season="winter", sail="flettner", era5=era5)
        overridden = da.run_single_scenario(
            ship=_SHIP, speed_kn=14.0, route="arabian_sea",
            season="winter", sail="flettner",
            ship_overrides={"DWT": base["dwt"] * 0.8}, era5=era5)
        assert overridden["ship_overrides"] is not None
        assert overridden["dwt"] == pytest.approx(base["dwt"] * 0.8)

    def test_geometry_override_changes_physics(self, era5):
        """覆盖主尺度（L/B/draft/C_B）应改变阻力 → 基线油耗变化"""
        base = da.run_single_scenario(
            ship=_SHIP, speed_kn=14.0, route="arabian_sea",
            season="winter", sail="flettner", era5=era5)
        overridden = da.run_single_scenario(
            ship=_SHIP, speed_kn=14.0, route="arabian_sea",
            season="winter", sail="flettner",
            ship_overrides={"L": 300.0, "B": 55.0,
                            "draft": 18.0, "C_B": 0.80}, era5=era5)
        assert overridden["fuel_baseline_kg"] != base["fuel_baseline_kg"]
