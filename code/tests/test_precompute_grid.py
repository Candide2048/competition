# -*- coding: utf-8 -*-
"""物理层预计算网格单元测试

验证目标（计算分层的「物理层离线预计算」）:
    - 小网格（1 船 × 1 速 × 5 航线 × 4 季节 × 1 帆）可跑通
    - 记录 schema 字段齐全、物理字段为正、量级合理
    - saving_rate_pct 与 fuel_saved/fuel_baseline 自洽
    - metadata 溯源字段（SFOC / 规格 / 船型标准几何 / 航线 / 季节）齐全
    - save_grid → JSON 往返一致

依赖 ERA5（模块级共享 fixture，只加载一次）。

运行方式:
    cd shipping_wasp/code
    python -m pytest tests/test_precompute_grid.py -v
"""
import os
import sys
import json

import pytest

# 将 code/ 目录加入 sys.path，便于 import pipelines/core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.precompute_grid import (
    compute_physics_grid,
    save_grid,
    DEFAULT_SPEEDS_KN,
    GRID_SFOC_KG_PER_KWH,
    GRID_FLETTNER_SPEC,
)
from app.data_access import PHYSICS_FIELDS


# ---------- 测试夹具 ----------

# 最小网格：1 船型 × 1 航速 × 1 帆型（航线/季节由 routes.yaml 全量扫描）
_SHIP = "kvlcc2"
_SPEED = 14.0
_SAIL = "flettner"


@pytest.fixture(scope="module")
def grid():
    """计算最小物理层网格（模块级共享，ERA5 只加载一次）"""
    return compute_physics_grid(
        ships=(_SHIP,),
        speeds=[_SPEED],
        sail_types=(_SAIL,),
        verbose=False,
    )


# ---------- 结构与元数据 ----------

class TestGridStructure:
    """网格顶层结构与 metadata 溯源"""

    def test_top_level_keys(self, grid):
        assert set(grid.keys()) == {"metadata", "records"}

    def test_record_count(self, grid):
        """1 船 × 1 速 × 5 航线 × 4 季节 × 1 帆 = 20"""
        meta = grid["metadata"]
        n_routes = len(meta["routes"])
        n_seasons = len(meta["seasons"])
        assert n_routes == 5 and n_seasons == 4
        assert len(grid["records"]) == n_routes * n_seasons
        assert meta["n_records"] == len(grid["records"])

    def test_metadata_provenance(self, grid):
        meta = grid["metadata"]
        assert meta["sfoc_kg_per_kwh"] == GRID_SFOC_KG_PER_KWH
        assert meta["flettner_spec"] == GRID_FLETTNER_SPEC
        assert meta["speeds_kn"] == [_SPEED]
        assert meta["ships"] == [_SHIP]
        assert meta["sail_types"] == [_SAIL]
        assert "generated_at" in meta

    def test_ship_meta_geometry(self, grid):
        """船型标准几何摘要，供前端后处理还原 DWT / CII 船型"""
        smeta = grid["metadata"]["ship_meta"][_SHIP]
        for key in ("DWT", "ship_type_imo", "L", "B", "T", "C_B", "V_design_kn"):
            assert key in smeta
        assert smeta["DWT"] > 0
        assert isinstance(smeta["ship_type_imo"], str)

    def test_ship_meta_has_gt_key(self, grid):
        """ship_meta 都带 GT 键（非 GT 基数船型为 None，供前端免重载判定）"""
        smeta = grid["metadata"]["ship_meta"][_SHIP]
        assert "GT" in smeta  # kvlcc2 为油轮，无 GT → None


    def test_sail_install_present(self, grid):
        install = grid["metadata"]["sail_install"]
        assert _SAIL in install
        assert install[_SAIL] >= 1

    def test_routes_metadata(self, grid):
        routes = grid["metadata"]["routes"]
        for rinfo in routes.values():
            assert "name" in rinfo
            assert "waypoints" in rinfo
            assert len(rinfo["waypoints"]) >= 2


# ---------- 记录 schema 与物理量级 ----------

class TestRecordSchema:
    """每条记录字段齐全且物理字段为正"""

    _META_FIELDS = ("ship", "speed_kn", "route", "season", "sail",
                    "distance_nm", "duration_h")

    def test_all_fields_present(self, grid):
        for rec in grid["records"]:
            for f in self._META_FIELDS:
                assert f in rec, f"缺少字段 {f}"
            for f in PHYSICS_FIELDS:
                assert f in rec, f"缺少物理字段 {f}"

    def test_dimension_labels_valid(self, grid):
        routes = set(grid["metadata"]["routes"].keys())
        seasons = set(grid["metadata"]["seasons"].keys())
        for rec in grid["records"]:
            assert rec["ship"] == _SHIP
            assert rec["speed_kn"] == _SPEED
            assert rec["sail"] == _SAIL
            assert rec["route"] in routes
            assert rec["season"] in seasons

    def test_physics_positive(self, grid):
        for rec in grid["records"]:
            assert rec["distance_nm"] > 0
            assert rec["duration_h"] > 0
            assert rec["fuel_baseline_kg"] > 0
            assert rec["fuel_with_sail_kg"] > 0
            assert rec["mean_wind_ms"] > 0
            assert rec["mean_thrust_kN"] >= 0

    def test_saving_rate_range(self, grid):
        """节油率量级合理：弱风季可能轻微为负（转子电功耗），
        强风季不超文献报道上界。宽松区间 (-30%, 30%)。"""
        for rec in grid["records"]:
            assert -30.0 < rec["saving_rate_pct"] < 30.0

    def test_saving_rate_self_consistent(self, grid):
        """saving_rate_pct ≈ fuel_saved / fuel_baseline × 100（含四舍五入容差）"""
        for rec in grid["records"]:
            expected = rec["fuel_saved_kg"] / rec["fuel_baseline_kg"] * 100.0
            assert abs(expected - rec["saving_rate_pct"]) < 0.05

    def test_fuel_balance(self, grid):
        """fuel_with_sail = fuel_baseline − fuel_saved（含四舍五入容差）"""
        for rec in grid["records"]:
            expected = rec["fuel_baseline_kg"] - rec["fuel_saved_kg"]
            assert abs(expected - rec["fuel_with_sail_kg"]) < 0.01


# ---------- 落盘往返 ----------

class TestSaveRoundTrip:
    """save_grid → JSON 往返一致"""

    def test_save_and_reload(self, grid, tmp_path):
        out = os.path.join(str(tmp_path), "physics_grid.json")
        saved_path = save_grid(grid, out)
        assert os.path.exists(saved_path)

        with open(saved_path, "r", encoding="utf-8") as f:
            reloaded = json.load(f)

        assert reloaded["metadata"]["n_records"] == grid["metadata"]["n_records"]
        assert len(reloaded["records"]) == len(grid["records"])
        # 抽查首条记录物理字段一致
        r0, g0 = reloaded["records"][0], grid["records"][0]
        for f in PHYSICS_FIELDS:
            assert r0[f] == g0[f]


# ---------- PCTC 汽车滚装船（GT 容量基数船型） ----------

@pytest.fixture(scope="module")
def pctc_grid():
    """最小 PCTC 网格（验证 PCTC 可入网 + ship_meta 带正 GT）"""
    return compute_physics_grid(
        ships=("pctc",),
        speeds=[_SPEED],
        sail_types=(_SAIL,),
        verbose=False,
    )


class TestPctcGrid:
    """PCTC 入网 + GT 容量基数写入 ship_meta"""

    def test_pctc_records_present(self, pctc_grid):
        recs = pctc_grid["records"]
        assert len(recs) > 0
        assert all(r["ship"] == "pctc" for r in recs)

    def test_pctc_ship_meta_gt_positive(self, pctc_grid):
        """PCTC 以 GT 为 CII 容量基数，ship_meta 应带正 GT 且 imo=roro"""
        smeta = pctc_grid["metadata"]["ship_meta"]["pctc"]
        assert smeta["GT"] is not None and smeta["GT"] > 0
        assert smeta["GT"] > smeta["DWT"]  # PCTC 箱体大，GT 远大于 DWT
        assert smeta["ship_type_imo"] == "roro_cargo_vehicle"
