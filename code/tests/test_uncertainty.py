# -*- coding: utf-8 -*-
"""不确定性 / 风资源 analytics 与 data_access 后处理单元测试

覆盖:
- uncertainty: bootstrap 索引可复现、分位数摘要单调、越阈概率插值
- wind_resource: 分箱占比归一、适配判级边界
- data_access: scenario_key / pick_insight 最近邻回退 / postprocess_uncertainty 口径

运行:
    cd shipping_wasp/code
    python -m pytest tests/test_uncertainty.py -v
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.uncertainty import (  # noqa: E402
    QUANTILE_GRID, block_bootstrap_indices, summarize_bootstrap_hourly,
    prob_exceed_threshold,
)
from analytics.wind_resource import summarize_wind_resource  # noqa: E402
import app.data_access as da  # noqa: E402


def _synthetic_hourly(n=240, seed=7):
    rng = np.random.default_rng(seed)
    wind = np.abs(rng.normal(8.0, 3.0, n))
    effective = wind >= 3.0
    thrust = np.where(effective, rng.uniform(0.0, 60.0, n), 0.0)
    return {
        "fuel_baseline_kg_h": rng.uniform(800.0, 1200.0, n),
        "fuel_saved_kg_h": np.where(effective, rng.uniform(0.0, 80.0, n), 0.0),
        "thrust_kN": thrust,
        "power_kW": thrust * 5.0,
        "true_wind_ms": wind,
        "apparent_wind_ms": wind + 2.0,
        "relative_wind_angle_deg": rng.uniform(0.0, 180.0, n),
        "effective": effective,
    }


# ── uncertainty ──────────────────────────────────────────────

class TestBlockBootstrap:
    def test_reproducible_with_same_seed(self):
        a = block_bootstrap_indices(100, 24, 5, seed=42)
        b = block_bootstrap_indices(100, 24, 5, seed=42)
        for x, y in zip(a, b):
            assert np.array_equal(x, y)

    def test_shapes_and_bounds(self):
        samples = block_bootstrap_indices(100, 24, 8, seed=1)
        assert len(samples) == 8
        for idx in samples:
            assert idx.shape == (100,)
            assert idx.min() >= 0 and idx.max() < 100

    def test_invalid_args_raise(self):
        with pytest.raises(ValueError):
            block_bootstrap_indices(0, 24, 3, seed=1)
        with pytest.raises(ValueError):
            block_bootstrap_indices(100, 0, 3, seed=1)


class TestSummarizeBootstrap:
    def test_quantile_grid_monotone_and_complete(self):
        s = summarize_bootstrap_hourly(_synthetic_hourly(), n_samples=200)
        g = s["quantile_grid"]
        assert g["q"] == [float(q) for q in QUANTILE_GRID]
        for key in ("fuel_baseline_kg", "fuel_saved_kg", "saving_rate_pct"):
            arr = g[key]
            assert len(arr) == len(QUANTILE_GRID)
            assert all(arr[i] <= arr[i + 1] + 1e-9 for i in range(len(arr) - 1))

    def test_p10_le_p50_le_p90(self):
        s = summarize_bootstrap_hourly(_synthetic_hourly(), n_samples=200)
        q = s["quantiles"]
        assert (q["p10"]["saving_rate_pct"] <= q["p50"]["saving_rate_pct"]
                <= q["p90"]["saving_rate_pct"])

    def test_seed_reproducible(self):
        h = _synthetic_hourly()
        s1 = summarize_bootstrap_hourly(h, n_samples=100, seed=9)
        s2 = summarize_bootstrap_hourly(h, n_samples=100, seed=9)
        assert s1["quantile_grid"] == s2["quantile_grid"]

    def test_risk_probability_in_unit_interval(self):
        s = summarize_bootstrap_hourly(_synthetic_hourly(), n_samples=100)
        p = s["risk"]["prob_positive_fuel_saving"]
        assert 0.0 <= p <= 1.0


class TestProbExceed:
    def test_extremes(self):
        q = [float(v) for v in QUANTILE_GRID]
        vals = list(np.linspace(10.0, 100.0, len(q)))
        assert prob_exceed_threshold(q, vals, 5.0) == 1.0
        assert prob_exceed_threshold(q, vals, 200.0) == pytest.approx(0.05)

    def test_median_threshold(self):
        q = [float(v) for v in QUANTILE_GRID]
        vals = list(np.linspace(10.0, 100.0, len(q)))
        # 中位数处 P(X>median) ≈ 0.5
        assert prob_exceed_threshold(q, vals, 55.0) == pytest.approx(0.5, abs=0.01)


# ── wind_resource ────────────────────────────────────────────

class TestWindResource:
    def test_histograms_normalized(self):
        s = summarize_wind_resource(_synthetic_hourly())
        assert sum(s["wind_speed_hist"]["pct"]) == pytest.approx(100.0, abs=0.1)
        assert sum(s["relative_angle_hist"]["pct"]) == pytest.approx(100.0, abs=0.1)
        assert (s["headwind_hours_pct"] + s["beam_reach_hours_pct"]
                + s["tailwind_hours_pct"]) == pytest.approx(100.0, abs=0.1)

    def test_all_calm_is_poor_low_wind(self):
        n = 100
        h = {
            "true_wind_ms": np.zeros(n),
            "apparent_wind_ms": np.zeros(n),
            "relative_wind_angle_deg": np.zeros(n),
            "fuel_baseline_kg_h": np.full(n, 3000.0),
            "fuel_saved_kg_h": np.zeros(n),
        }
        s = summarize_wind_resource(h)
        assert s["interpretation"]["fit_level"] == "poor"
        assert s["interpretation"]["main_reason_key"] == "low_wind_dominant"

    def test_empty_raises(self):
        h = {k: np.array([]) for k in (
            "true_wind_ms", "apparent_wind_ms", "relative_wind_angle_deg",
            "fuel_baseline_kg_h", "fuel_saved_kg_h")}
        with pytest.raises(ValueError):
            summarize_wind_resource(h)

    def test_fit_level_thresholds(self):
        # 判级边界：净节油贡献占比 39/40/69/70 → poor/medium/medium/good
        def _fit(contrib_pct):
            n = 100
            saved = np.zeros(n)
            saved[:contrib_pct] = 150.0  # 节油率 5%，> 2% 阈值
            h = {
                "true_wind_ms": np.full(n, 8.0),  # 避开 low_wind 主因
                "apparent_wind_ms": np.full(n, 10.0),
                "relative_wind_angle_deg": np.full(n, 90.0),
                "fuel_baseline_kg_h": np.full(n, 3000.0),
                "fuel_saved_kg_h": saved,
            }
            return summarize_wind_resource(h)["interpretation"]["fit_level"]

        assert _fit(39) == "poor"
        assert _fit(40) == "medium"
        assert _fit(69) == "medium"
        assert _fit(70) == "good"


# ── data_access: insights 查表 + 不确定性后处理 ─────────────

def _fake_insight(ship, sail, speed=11.5):
    q = [float(v) for v in QUANTILE_GRID]
    n = len(q)
    fs = np.linspace(4000.0, 12000.0, n)          # kg，单调增
    fb = np.linspace(190000.0, 210000.0, n)
    sr = fs / fb * 100.0
    return {
        "ship": ship, "speed_kn": speed, "route": "r1", "season": "spring",
        "sail": sail, "duration_h": 300,
        "uncertainty": {
            "method": "24h circular block bootstrap over hourly route samples",
            "n_samples": 500, "block_h": 24, "seed": 20260727, "n_hours": 300,
            "quantile_grid": {
                "q": q,
                "fuel_baseline_kg": [round(float(v), 3) for v in fb],
                "fuel_saved_kg": [round(float(v), 3) for v in fs],
                "saving_rate_pct": [round(float(v), 4) for v in sr],
            },
            "risk": {"prob_positive_fuel_saving": 1.0},
        },
    }


class TestInsightLookup:
    def test_scenario_key_format(self):
        assert da.scenario_key("s", 11, "r", "spring", "flettner") == \
            "s|11.0|r|spring|flettner"

    def test_pick_insight_exact_and_nearest(self):
        rec = _fake_insight("shipA", "flettner", speed=11.5)
        index = {da.scenario_key("shipA", 11.5, "r1", "spring", "flettner"): rec}
        assert da.pick_insight(index, "shipA", 11.5, "r1", "spring",
                               "flettner") is rec
        # 非网格航速 → 最近邻回退
        assert da.pick_insight(index, "shipA", 11.7, "r1", "spring",
                               "flettner", grid_speeds=[10.0, 11.5]) is rec
        # 空索引 → None
        assert da.pick_insight({}, "shipA", 11.5, "r1", "spring",
                               "flettner") is None


@pytest.fixture(scope="module")
def grid_meta():
    meta, _df = da.load_grid()
    return meta


class TestPostprocessUncertainty:
    def test_band_monotone_and_risk(self, grid_meta):
        ship = next(iter(grid_meta["ship_meta"]))
        sail = next(s for s in grid_meta["sail_types"]
                    if da.get_compatibility(ship, s) > 0)
        band = da.postprocess_uncertainty(
            _fake_insight(ship, sail), ship=ship, sail=sail,
            bench_lo=6.0, bench_hi=8.2)
        for key in ("saving_rate_pct", "fuel_saved_t", "co2_reduced_t",
                    "annual_savings_usd", "npv_20y_usd"):
            b = band[key]
            assert b["p10"] <= b["p50"] <= b["p90"], key
        assert 0.0 <= band["risk"]["prob_positive_npv_20y"] <= 1.0
        assert 0.0 <= band["risk"]["prob_within_benchmark"] <= 1.0
        assert band["risk"]["prob_positive_fuel_saving"] == 1.0

    def test_guardrail_caps_saving_rate(self, grid_meta):
        ship = next(iter(grid_meta["ship_meta"]))
        sail = next(s for s in grid_meta["sail_types"]
                    if da.get_compatibility(ship, s) > 0)
        rec = _fake_insight(ship, sail)
        # 人为放大节油率触发 guardrail
        g = rec["uncertainty"]["quantile_grid"]
        g["saving_rate_pct"] = [v * 20.0 for v in g["saving_rate_pct"]]
        band = da.postprocess_uncertainty(rec, ship=ship, sail=sail)
        cap = da.get_screening_saving_cap()
        assert band["saving_rate_pct"]["p90"] <= cap + 1e-6
