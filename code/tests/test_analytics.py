# -*- coding: utf-8 -*-
"""analytics 模块单元测试

覆盖:
- fuel_saving: 节油率、CO2 减排量
- cii: attained CII 公式、评级、改善率
- economics: 初始成本、年节省、NPV、回收期、敏感性

运行:
    cd shipping_wasp/code
    python -m pytest tests/test_analytics.py -v
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.fuel_saving import (
    compute_fuel_saving,
    compute_carbon_reduction,
    in_wasp_typical_range,
)
from analytics.cii import (
    compute_cii,
    cii_rating,
    cii_improvement,
    CIIBaseline,
    RATING_BOUNDARIES,
)
from analytics.economics import (
    initial_cost,
    annual_savings,
    npv,
    payback_period,
    sensitivity,
    DEFAULT_FUEL_PRICE,
    DEFAULT_CO2_PRICE,
    DEFAULT_A_COST,
    DEFAULT_B_COST,
)
from models.thrust_balance import solve_balance


# ---------- fuel_saving 测试 ----------

class TestFuelSaving:
    """节油量与碳减排"""

    @pytest.fixture
    def balance_with_sail(self):
        """模拟推力平衡：100kN 推力，70h 航程"""
        return solve_balance(
            R_total_N=1098000, V_ship_ms=7.2,
            T_sail_N=100000, P_rotor_W=50000
        )

    def test_saving_rate_in_wasp_range(self, balance_with_sail):
        """节油率应在 ③ 综述 WASP 典型区间 5-30%"""
        result = compute_fuel_saving(balance_with_sail, duration_h=70.0)
        assert in_wasp_typical_range(result.saving_rate_pct), \
            f"节油率 {result.saving_rate_pct:.2f}% 应在 5-30% 区间"

    def test_co2_reduction_positive(self, balance_with_sail):
        """CO2 减排量应为正"""
        result = compute_fuel_saving(balance_with_sail, duration_h=70.0)
        assert result.co2_reduced_t > 0
        assert result.co2_reduction_pct > 0

    def test_co2_emission_factor(self, balance_with_sail):
        """CO2 减排 = 节油 × 3.114 (IMO HFO C_F)"""
        result = compute_fuel_saving(balance_with_sail, duration_h=70.0)
        expected_co2 = result.fuel_saved_t * 3.114
        assert abs(result.co2_reduced_t - expected_co2) < 1e-6

    def test_baseline_greater_than_with_sail(self, balance_with_sail):
        """无帆油耗应大于有帆油耗"""
        result = compute_fuel_saving(balance_with_sail, duration_h=70.0)
        assert result.fuel_baseline_t > result.fuel_with_sail_t

    def test_compute_carbon_reduction_standalone(self):
        """独立碳减排函数"""
        # 10 t 燃油 → 31.14 t CO2 (IMO HFO C_F=3.114)
        co2 = compute_carbon_reduction(fuel_saved_t=10.0)
        assert abs(co2 - 31.14) < 1e-6


# ---------- cii 测试 ----------

class TestCII:
    """CII 评级与改善率"""

    def test_compute_cii_formula(self):
        """CII = (fuel × EF × 1e6) / (DWT × distance)"""
        # KVLCC2: DWT=300000 t, 距离 662.5 nm, 油耗 89.2 t
        cii = compute_cii(fuel_t=89.2, DWT=300000.0, distance_nm=662.5)
        # 89.2 × 3.114 × 1e6 / (300000 × 662.5) gCO2/dwt·nm
        expected = 89.2 * 3.114 * 1e6 / (300000 * 662.5)
        assert abs(cii - expected) < 1e-6
        # 数值应在 VLCC 单航次 CII 合理范围
        assert 0.5 < cii < 5.0

    def test_cii_rating_A(self):
        """ratio ≤ 0.86 应评 A"""
        assert cii_rating(attained_cii=3.5, required_cii=4.5) == "A"  # 0.778
        assert cii_rating(attained_cii=3.8, required_cii=4.5) == "A"  # 0.844

    def test_cii_rating_C(self):
        """0.94 ≤ ratio < 1.07 应评 C"""
        assert cii_rating(attained_cii=4.0, required_cii=4.0) == "C"  # 1.0
        assert cii_rating(attained_cii=4.2, required_cii=4.0) == "C"  # 1.05

    def test_cii_rating_E(self):
        """ratio ≥ 1.19 应评 E"""
        assert cii_rating(attained_cii=5.0, required_cii=4.0) == "E"  # 1.25

    def test_cii_rating_all_levels(self):
        """所有评级 A-E 都应可触发"""
        ratings = set()
        for ratio in [0.5, 0.88, 1.0, 1.1, 1.3]:
            r = cii_rating(attained_cii=ratio, required_cii=1.0)
            ratings.add(r)
        assert ratings == {"A", "B", "C", "D", "E"}

    def test_cii_improvement_positive(self):
        """加装风帆后 CII 改善率为正"""
        imp = cii_improvement(baseline_cii=1.5, with_sail_cii=1.4)
        assert imp > 0
        assert abs(imp - 6.667) < 1e-3  # (1.5-1.4)/1.5 × 100

    def test_cii_improvement_negative_when_worse(self):
        """若 with_sail_cii > baseline_cii 则改善率为负"""
        imp = cii_improvement(baseline_cii=1.0, with_sail_cii=1.2)
        assert imp < 0

    def test_cii_invalid_DWT(self):
        """DWT ≤ 0 应抛异常"""
        with pytest.raises(ValueError):
            compute_cii(fuel_t=89.2, DWT=0, distance_nm=662.5)

    def test_cii_baseline_placeholder(self):
        """CII 基准应引用 IMO 官方来源 (MEPC.353(78))"""
        bl = CIIBaseline()
        assert "MEPC.353(78)" in bl.source
        assert bl.year == 2024


# ---------- economics 测试 ----------

class TestEconomics:
    """经济性: 初始成本/年节省/NPV/回收期/敏感性"""

    def test_initial_cost_formula(self):
        """c_initial = a·(A_top+A_lateral) + b·V_rotor"""
        # Flettner H=20m, D=4m: A_top = π·(D/2)² = 12.57, A_lateral = H×D = 80
        # V_rotor = π·(D/2)²·H = 251.3 m³/s
        cost = initial_cost(A_top=12.57, A_lateral=80.0, V_rotor=251.3)
        expected = DEFAULT_A_COST * (12.57 + 80.0) + DEFAULT_B_COST * 251.3
        assert abs(cost - expected) < 1e-2

    def test_initial_cost_positive(self):
        """初始成本应为正"""
        cost = initial_cost(A_top=10.0, A_lateral=50.0, V_rotor=100.0)
        assert cost > 0

    def test_annual_savings_positive(self):
        """正节油量与碳减排应产生正年节省"""
        s = annual_savings(
            fuel_saved_t_per_year=300.0,
            co2_reduced_t_per_year=952.2,  # 300 × 3.174
        )
        assert s["total_savings_usd"] > 0
        assert s["fuel_savings_usd"] > 0
        assert s["co2_savings_eur"] > 0

    def test_annual_savings_work_rate(self):
        """工作率 50% 应使节省减半"""
        s_full = annual_savings(300.0, 952.2, work_rate=1.0)["total_savings_usd"]
        s_half = annual_savings(300.0, 952.2, work_rate=0.5)["total_savings_usd"]
        assert abs(s_half - s_full * 0.5) < 1e-6

    def test_npv_negative_at_high_initial_cost(self):
        """初始成本远大于年节省时 NPV 应为负"""
        npv_dict = npv(
            annual_savings_usd=50000.0,
            initial_cost_usd=1e8,
            years=[10],
            discount_rate=0.08,
        )
        assert npv_dict[10] < 0

    def test_npv_positive_at_low_initial_cost(self):
        """初始成本较低时 NPV 应为正"""
        npv_dict = npv(
            annual_savings_usd=500000.0,
            initial_cost_usd=1e6,
            years=[20],
            discount_rate=0.05,
        )
        assert npv_dict[20] > 0

    def test_npv_multiple_years(self):
        """NPV 应返回多个投资期结果"""
        npv_dict = npv(
            annual_savings_usd=100000.0,
            initial_cost_usd=500000.0,
            years=[5, 10, 15, 20],
        )
        assert set(npv_dict.keys()) == {5, 10, 15, 20}
        # 投资期越长 NPV 应越大（更多年节省）
        assert npv_dict[20] > npv_dict[10] > npv_dict[5]

    def test_payback_period_simple(self):
        """回收期 = 初始成本 / 年节省"""
        pb = payback_period(initial_cost_usd=1e6, annual_savings_usd=2e5)
        assert abs(pb - 5.0) < 1e-6

    def test_payback_infinite_when_no_savings(self):
        """年节省 ≤ 0 时回收期为无穷"""
        pb = payback_period(initial_cost_usd=1e6, annual_savings_usd=0.0)
        assert pb == float("inf")

    def test_sensitivity_returns_all_scenarios(self):
        """敏感性分析应返回所有变动场景"""
        s = sensitivity(
            fuel_saved_t_per_year=300.0,
            co2_reduced_t_per_year=952.2,
            initial_cost_usd=2e6,
            years=10,
        )
        required_keys = {
            "base_npv", "base_savings_usd",
            "fuel_-30%", "fuel_+30%",
            "co2_-50%", "co2_+50%",
            "eff_-20%", "eff_+20%",
        }
        assert set(s.keys()) == required_keys

    def test_sensitivity_fuel_price_direction(self):
        """油价上涨时 NPV 应高于油价下跌"""
        s = sensitivity(
            fuel_saved_t_per_year=300.0,
            co2_reduced_t_per_year=952.2,
            initial_cost_usd=2e6,
            years=10,
        )
        assert s["fuel_+30%"] > s["fuel_-30%"]

    def test_sensitivity_efficiency_direction(self):
        """风帆效率提高时 NPV 应高于效率下降"""
        s = sensitivity(
            fuel_saved_t_per_year=300.0,
            co2_reduced_t_per_year=952.2,
            initial_cost_usd=2e6,
            years=10,
        )
        assert s["eff_+20%"] > s["eff_-20%"]


# ---------- 端到端集成测试 ----------

class TestEndToEnd:
    """analytics 模块端到端集成测试"""

    def test_full_pipeline_kvlcc2_14kn(self):
        """KVLCC2 14kn + 100kN 推力 → 节油率 + CO2 + NPV"""
        # 1. 推力平衡
        balance = solve_balance(
            R_total_N=1098000, V_ship_ms=7.2,
            T_sail_N=100000, P_rotor_W=50000
        )
        # 2. 节油与碳减排
        fs = compute_fuel_saving(balance, duration_h=70.0)
        # 3. 年化（假设每年 6 个航次，约 420h 实际航行 = 4.79 航次/年取 5）
        trips_per_year = 5
        annual_fuel_saved = fs.fuel_saved_t * trips_per_year
        annual_co2_reduced = fs.co2_reduced_t * trips_per_year
        # 4. 经济性
        cost = initial_cost(A_top=12.57, A_lateral=80.0, V_rotor=251.3)
        s = annual_savings(annual_fuel_saved, annual_co2_reduced)
        pb = payback_period(cost, s["total_savings_usd"])
        npv_dict = npv(s["total_savings_usd"], cost, years=[5, 10, 20])

        # 断言
        assert 5.0 < fs.saving_rate_pct < 30.0  # ③ 综述 WASP 区间
        assert fs.co2_reduced_t > 0
        assert cost > 0
        assert s["total_savings_usd"] > 0
        assert pb > 0
        assert npv_dict[20] > npv_dict[5]  # 长期 NPV 更高


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
