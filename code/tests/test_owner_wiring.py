# -*- coding: utf-8 -*-
"""OwnerInputs 接线、双船型加载与 SFOC 口径一致性测试

覆盖（均为轻量单元测试，不依赖 ERA5；§8.3 全矩阵复现由回归脚本负责）:
- SFOC 不变量：节油率(%)对 SFOC 数值不敏感，绝对油耗按比例线性缩放
- 多船型加载：kvlcc2/kamsarmax/mr_tanker/container 均可加载并跑通阻力，DWT/CII 船型正确
- OwnerInputs ship_type 单选项：默认、校验、to_dict 纳入
- 实船几何覆盖（第②层）：L/B/吃水/C_B/DWT 覆盖自洽、派生量重算、校验
- evaluate_cell 接线：排放因子驱动 CO₂/CII、油价流入年节省、CII 走对应参考线
"""
import os
import sys

import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from core.owner_inputs import OwnerInputs, VALID_SHIP_TYPES
from core.ship_params import (
    load_ship_params_by_type,
    apply_geometry_overrides,
    to_holtrop_input,
)
from models.thrust_balance import solve_balance
from models.resistance import compute_resistance
from analytics.cii import CIIBaseline
from pipelines.phase_b_matrix import evaluate_cell


# ═══════════════════════════════════════════════════════════
# SFOC 不变量（变更三）
# ═══════════════════════════════════════════════════════════

class TestSFOCInvariant:
    """SFOC 同时出现在基线与有帆油耗两侧 → 节油率(%)对 SFOC 不敏感"""

    # 一组具代表性的推力平衡输入（含转子电力负荷，验证 rotor 项也满足不变量）
    _R_TOTAL = 1.5e6      # N
    _V = 7.2              # m/s
    _T_SAIL = 2.0e5       # N
    _P_ROTOR = 4.0e5      # W

    def _solve(self, sfoc):
        return solve_balance(self._R_TOTAL, self._V, self._T_SAIL,
                             self._P_ROTOR, SFOC=sfoc)

    def test_saving_rate_invariant_to_sfoc(self):
        """节油率(%)在 SFOC=0.160 与 0.180 下应完全相等"""
        r160 = self._solve(0.160)
        r180 = self._solve(0.180)
        assert abs(r160.saving_rate_pct - r180.saving_rate_pct) < 1e-6

    def test_absolute_fuel_scales_linearly(self):
        """绝对节油量应按 SFOC 比例线性缩放（180/160 = 1.125）"""
        r160 = self._solve(0.160)
        r180 = self._solve(0.180)
        assert r160.fuel_saved_kg_per_h > 0
        ratio = r180.fuel_saved_kg_per_h / r160.fuel_saved_kg_per_h
        assert abs(ratio - 1.125) < 1e-6

    def test_baseline_fuel_scales_linearly(self):
        """基线油耗率同样按 SFOC 比例缩放"""
        r160 = self._solve(0.160)
        r180 = self._solve(0.180)
        ratio = r180.fuel_baseline_kg_per_h / r160.fuel_baseline_kg_per_h
        assert abs(ratio - 1.125) < 1e-6

    def test_default_sfoc_is_180(self):
        """solve_balance 默认 SFOC 应对齐数据表/ schema 的 180"""
        r_default = solve_balance(self._R_TOTAL, self._V, self._T_SAIL, self._P_ROTOR)
        r_180 = self._solve(0.180)
        assert abs(r_default.fuel_baseline_kg_per_h
                   - r_180.fuel_baseline_kg_per_h) < 1e-9


# ═══════════════════════════════════════════════════════════
# 双船型加载（变更二）
# ═══════════════════════════════════════════════════════════

class TestShipLoading:

    _EXPECTED = {
        "kvlcc2": ("tanker", 300000.0),
        "kamsarmax": ("bulk_carrier", 82000.0),
        "mr_tanker": ("tanker", 50000.0),
        "container": ("container_ship", 40000.0),
    }

    def test_all_ship_types_load(self):
        """四个 ship_type 均应加载成功且 DWT / CII 船型正确"""
        for st, (imo, dwt) in self._EXPECTED.items():
            ship = load_ship_params_by_type(st)
            assert ship.ship_type_imo == imo
            assert abs(ship.DWT - dwt) < 1.0

    def test_all_ship_types_run_resistance(self):
        """四个 ship_type 均应跑通阻力模型且有效功率为正、量级合理"""
        for st in VALID_SHIP_TYPES:
            ship = load_ship_params_by_type(st)
            res = compute_resistance(to_holtrop_input(ship), ship.V_design_ms)
            assert res["R_total"] > 0
            assert res["P_E"] > 0
            # 服务航速有效功率应在 1~30 MW 量级（散货/油轮/集装箱上游筛选合理区间）
            assert 1e6 < res["P_E"] < 3e7

    def test_bad_ship_type_raises(self):
        with pytest.raises(ValueError):
            load_ship_params_by_type("frigate")


# ═══════════════════════════════════════════════════════════
# OwnerInputs ship_type 单选项（变更一）
# ═══════════════════════════════════════════════════════════

class TestOwnerShipType:

    def test_default_ship_type(self):
        assert OwnerInputs().ship_type == "kvlcc2"

    def test_from_defaults_reads_ship_type(self):
        assert OwnerInputs.from_defaults().ship_type in VALID_SHIP_TYPES

    def test_validate_rejects_bad_ship_type(self):
        with pytest.raises(ValueError):
            OwnerInputs(ship_type="submarine").validate()

    def test_to_dict_includes_ship_type(self):
        assert OwnerInputs(ship_type="kamsarmax").to_dict()["ship_type"] == "kamsarmax"


# ═══════════════════════════════════════════════════════════
# evaluate_cell 接线（变更四）
# ═══════════════════════════════════════════════════════════

class TestEvaluateCellWiring:

    def _sim(self):
        """构造一份最小单航次仿真结果（不经 ERA5）"""
        return {
            "fuel_baseline_kg": 200000.0,
            "fuel_with_sail_kg": 185000.0,
            "fuel_saved_kg": 15000.0,
            "saving_rate_pct": 7.5,
            "mean_thrust_kN": 120.0,
            "mean_power_kW": 300.0,
            "mean_wind_ms": 8.0,
        }

    def test_emission_factor_drives_co2(self):
        """CO₂ 减排量应随排放因子线性变化（VLSFO 3.114 vs LNG 2.750）"""
        ship = load_ship_params_by_type("kvlcc2")
        common = dict(total_nm=6500.0, unit_cost=1.5e6, n_sails=8, trips_per_year=6.0)
        hfo = evaluate_cell(self._sim(), ship, emission_factor=3.114,
                            cii_ship_type="tanker", **common)
        lng = evaluate_cell(self._sim(), ship, emission_factor=2.750,
                            cii_ship_type="tanker", **common)
        ratio = hfo["co2_reduced_t"] / lng["co2_reduced_t"]
        assert abs(ratio - 3.114 / 2.750) < 1e-3

    def test_fuel_price_flows_into_savings(self):
        """更高油价应带来更高年节省"""
        ship = load_ship_params_by_type("kvlcc2")
        common = dict(total_nm=6500.0, unit_cost=1.5e6, n_sails=8,
                      trips_per_year=6.0, emission_factor=3.114,
                      cii_ship_type="tanker")
        cheap = evaluate_cell(self._sim(), ship, fuel_price=0.4, **common)
        pricey = evaluate_cell(self._sim(), ship, fuel_price=0.9, **common)
        assert pricey["annual_savings_usd"] > cheap["annual_savings_usd"]

    def test_bulk_carrier_cii_reference_differs_from_tanker(self):
        """散货船应走 bulk_carrier 参考线，required CII 与 tanker 不同"""
        ship = load_ship_params_by_type("kamsarmax")
        tanker_bl = CIIBaseline(ship_type="tanker", capacity=ship.DWT, year=2024)
        bulk_bl = CIIBaseline(ship_type="bulk_carrier", capacity=ship.DWT, year=2024)
        assert abs(bulk_bl.required_cii - tanker_bl.required_cii) > 1e-6


# ═══════════════════════════════════════════════════════
# 实船几何覆盖（第②层）
# ═══════════════════════════════════════════════════════

class TestGeometryOverride:

    def test_no_override_returns_unchanged(self):
        """空覆盖（均为 None）应不改变任何字段"""
        base = load_ship_params_by_type("kvlcc2")
        same = apply_geometry_overrides(base, {"DWT": None, "L": None})
        assert same.V_disp == base.V_disp
        assert same.C_P == base.C_P
        assert same.DWT == base.DWT

    def test_dwt_only_does_not_touch_geometry(self):
        """仅覆盖 DWT 时几何/排水体积/形状系数均不变（仅影响 CII 基数）"""
        base = load_ship_params_by_type("kvlcc2")
        ov = apply_geometry_overrides(base, {"DWT": 280000.0})
        assert ov.DWT == 280000.0
        assert ov.V_disp == base.V_disp
        assert ov.C_P == base.C_P
        assert ov.C_WP == base.C_WP
        assert ov.L == base.L

    def test_dimension_override_recomputes_displacement(self):
        """主尺度覆盖应按 V_disp = L·B·T·C_B 重算"""
        base = load_ship_params_by_type("mr_tanker")
        ov = apply_geometry_overrides(base, {"L": 180.0, "B": 32.0})
        assert ov.L == 180.0 and ov.B == 32.0
        assert abs(ov.V_disp - 180.0 * 32.0 * base.T * base.C_B) < 1e-6

    def test_cb_override_recomputes_shape_coeffs(self):
        """C_B 覆盖应重算 C_P=C_B/C_M 与 C_WP=(1+2C_B)/3"""
        base = load_ship_params_by_type("kvlcc2")
        ov = apply_geometry_overrides(base, {"C_B": 0.80})
        assert abs(ov.C_P - 0.80 / base.C_M) < 1e-9
        assert abs(ov.C_WP - (1.0 + 2.0 * 0.80) / 3.0) < 1e-9

    def test_larger_ship_has_larger_resistance(self):
        """放大主尺度后静水阻力应增大（物理单调性）"""
        base = load_ship_params_by_type("mr_tanker")
        big = apply_geometry_overrides(base, {"L": base.L * 1.2, "B": base.B * 1.1})
        r0 = compute_resistance(to_holtrop_input(base), base.V_design_ms)
        r1 = compute_resistance(to_holtrop_input(big), base.V_design_ms)
        assert r1["R_total"] > r0["R_total"]

    def test_validate_rejects_bad_override_key(self):
        with pytest.raises(ValueError):
            OwnerInputs(ship_overrides={"length": 200.0}).validate()

    def test_validate_rejects_nonpositive(self):
        with pytest.raises(ValueError):
            OwnerInputs(ship_overrides={"L": -5.0}).validate()

    def test_validate_rejects_cb_out_of_range(self):
        with pytest.raises(ValueError):
            OwnerInputs(ship_overrides={"C_B": 1.5}).validate()

    def test_resolved_strips_none(self):
        o = OwnerInputs(ship_overrides={"DWT": 90000.0, "L": None})
        assert o.resolved_ship_overrides() == {"DWT": 90000.0}
        assert OwnerInputs(ship_overrides={"L": None}).resolved_ship_overrides() is None

    def test_to_dict_includes_overrides(self):
        o = OwnerInputs(ship_type="kamsarmax", ship_overrides={"DWT": 85000.0})
        assert o.to_dict()["ship_overrides"] == {"DWT": 85000.0}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
