# -*- coding: utf-8 -*-
"""船东输入参数 schema、情景分析与 Flettner 规格选型测试

覆盖:
- OwnerInputs 默认构造、校验、派生量（年运营小时、单台成本解析）
- economics.scenario_analysis 情景扫描（含单台成本维度）
- phase_b_matrix.build_sail 的 Flettner 5 规格选型（几何落在模型有效域）
"""
import os
import sys

import numpy as np
import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import (
    OwnerInputs, HOURS_PER_YEAR, VALID_FLETTNER_SPECS,
)
from analytics.economics import scenario_analysis
from pipelines.phase_b_matrix import build_sail


# ═══════════════════════════════════════════════════════════
# 船东输入参数 schema
# ═══════════════════════════════════════════════════════════

class TestOwnerInputs:

    def test_from_defaults(self):
        """应能从 economics.yaml 构造默认输入"""
        inp = OwnerInputs.from_defaults()
        assert inp.sail_type in ("flettner", "rigid_wing", "suction_wing")
        assert inp.ship_speed_kn > 0

    def test_annual_operating_hours(self):
        """年运营小时 = 比例 × 8765"""
        inp = OwnerInputs(sea_operating_ratio=0.5)
        assert abs(inp.annual_operating_hours() - 0.5 * HOURS_PER_YEAR) < 1e-6

    def test_resolved_cost_uses_spec_price(self):
        """未覆盖时 Flettner 应取所选规格单价（35x5 > 20x4）"""
        small = OwnerInputs(sail_type="flettner", flettner_spec="20x4")
        large = OwnerInputs(sail_type="flettner", flettner_spec="35x5")
        assert large.resolved_unit_cost_usd() > small.resolved_unit_cost_usd()

    def test_resolved_cost_override(self):
        """给定 unit_cost_usd 时应优先使用覆盖值"""
        inp = OwnerInputs(sail_type="flettner", unit_cost_usd=2000000.0)
        assert inp.resolved_unit_cost_usd() == 2000000.0

    def test_validate_rejects_bad_sail_type(self):
        with pytest.raises(ValueError):
            OwnerInputs(sail_type="kite").validate()

    def test_validate_rejects_bad_spec(self):
        with pytest.raises(ValueError):
            OwnerInputs(sail_type="flettner", flettner_spec="99x9").validate()

    def test_validate_rejects_bad_ratio(self):
        with pytest.raises(ValueError):
            OwnerInputs(sea_operating_ratio=1.5).validate()

    def test_soft_warning_out_of_range(self):
        """超出建议区间应记录告警但不抛异常"""
        inp = OwnerInputs(ship_speed_kn=25.0)  # 超出 [8,18]
        inp.validate()
        assert any("ship_speed_kn" in w for w in inp._warnings)

    def test_to_dict_serializable(self):
        d = OwnerInputs.from_defaults().to_dict()
        assert "annual_operating_hours" in d
        assert "unit_cost_usd" in d
        assert "routes" in d
        assert "emission_factor" in d

    # ---------- 燃料类型 → 排放因子 ----------

    def test_fuel_type_default_vlsfo_factor(self):
        """默认 VLSFO 排放因子应为 3.114"""
        inp = OwnerInputs()
        assert abs(inp.resolved_emission_factor() - 3.114) < 1e-6

    def test_fuel_type_lng_factor(self):
        """LNG 排放因子应为 2.750"""
        inp = OwnerInputs(fuel_type="LNG")
        assert abs(inp.resolved_emission_factor() - 2.750) < 1e-6

    def test_validate_rejects_bad_fuel_type(self):
        with pytest.raises(ValueError):
            OwnerInputs(fuel_type="nuclear").validate()

    # ---------- 比油耗 ----------

    def test_sfoc_default(self):
        assert OwnerInputs().sfoc_g_per_kwh == 180.0

    def test_validate_rejects_nonpositive_sfoc(self):
        with pytest.raises(ValueError):
            OwnerInputs(sfoc_g_per_kwh=0.0).validate()

    # ---------- 多航线加权 ----------

    def test_resolved_routes_single_default(self):
        """未给 route_weights 时应回退单航线 @100%"""
        inp = OwnerInputs(route="south_china_sea")
        assert inp.resolved_routes() == [("south_china_sea", 1.0)]

    def test_resolved_routes_normalized(self):
        """多航线权重应归一化到和为 1"""
        inp = OwnerInputs(route_weights={"middle_east_china": 60, "south_china_sea": 40})
        routes = dict(inp.resolved_routes())
        assert abs(routes["middle_east_china"] - 0.6) < 1e-6
        assert abs(routes["south_china_sea"] - 0.4) < 1e-6
        assert abs(sum(routes.values()) - 1.0) < 1e-6

    def test_validate_rejects_empty_route_weights(self):
        with pytest.raises(ValueError):
            OwnerInputs(route_weights={}).validate()

    def test_validate_rejects_negative_route_weight(self):
        with pytest.raises(ValueError):
            OwnerInputs(route_weights={"middle_east_china": -1.0}).validate()

    def test_route_weights_sum_not_100_warns(self):
        """权重和既非 1 也非 100 时应软告警但不抛异常"""
        inp = OwnerInputs(route_weights={"middle_east_china": 3, "south_china_sea": 2})
        inp.validate()
        assert any("route_weights" in w for w in inp._warnings)


# ═══════════════════════════════════════════════════════════
# 情景分析（含单台成本维度）
# ═══════════════════════════════════════════════════════════

class TestScenarioAnalysis:

    @pytest.fixture
    def result(self):
        return scenario_analysis(
            annual_fuel_saved_t=1500.0,
            annual_co2_reduced_t=4671.0,
            unit_cost_usd=1500000.0,
            n_sails=8,
            years=20,
        )

    def test_has_base_and_scenarios(self, result):
        assert "base" in result and "scenarios" in result
        expected = {
            "cost_-30%", "cost_+30%",
            "fuel_-30%", "fuel_+30%",
            "co2_-50%", "co2_+50%",
            "eff_-20%", "eff_+20%",
        }
        assert set(result["scenarios"].keys()) == expected

    def test_cost_direction(self, result):
        """成本越低 NPV 越高、回收期越短"""
        low = result["scenarios"]["cost_-30%"]
        high = result["scenarios"]["cost_+30%"]
        assert low["npv_20y_usd"] > high["npv_20y_usd"]

    def test_base_cost_scales_with_n_sails(self, result):
        assert result["base"]["initial_cost_usd"] == 1500000.0 * 8

    def test_fuel_price_direction(self, result):
        assert (result["scenarios"]["fuel_+30%"]["npv_20y_usd"]
                > result["scenarios"]["fuel_-30%"]["npv_20y_usd"])


# ═══════════════════════════════════════════════════════════
# Flettner 5 规格选型
# ═══════════════════════════════════════════════════════════

class TestFlettnerSpecs:

    def test_all_specs_build(self):
        """5 种 Norsepower 标准规格均应能构造（几何落在模型有效域）"""
        for spec in VALID_FLETTNER_SPECS:
            sail, n, cost, area, label = build_sail("flettner", flettner_spec=spec)
            assert area > 0
            assert cost > 0
            assert spec in label

    def test_default_is_24x4(self):
        """不指定规格时默认 24×4（96 m²）"""
        sail, n, cost, area, label = build_sail("flettner")
        assert abs(area - 96.0) < 1e-6

    def test_larger_spec_more_area(self):
        """35×5 投影面积应大于 20×4"""
        _, _, _, area_small, _ = build_sail("flettner", flettner_spec="20x4")
        _, _, _, area_large, _ = build_sail("flettner", flettner_spec="35x5")
        assert area_large > area_small

    def test_bad_spec_raises(self):
        with pytest.raises(ValueError):
            build_sail("flettner", flettner_spec="12x3")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
