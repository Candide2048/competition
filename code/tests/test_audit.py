# -*- coding: utf-8 -*-
"""审计摘要单元 + API 测试"""
import os
import sys

import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from app.audit import build_audit_summary, MODEL_CHAIN, LIMITATIONS  # noqa: E402


class TestBuildAuditSummary:
    def test_minimal_meta(self):
        meta = {"ships": ["a"], "routes": {"r": {}}, "seasons": {"s": {}},
                "sail_types": ["f"], "speeds_kn": [12.0], "era5_year": 2025}
        out = build_audit_summary(meta, df=[1, 2, 3])
        assert out["coverage"]["records"] == 3
        assert out["coverage"]["ships"] == ["a"]
        assert out["coverage"]["weather_years"] == [2025]
        assert out["guardrails"]["screening_cap_pct"] is None
        assert out["model_chain"] is MODEL_CHAIN
        assert out["limitations"] is LIMITATIONS

    def test_with_insights_and_bench(self):
        meta = {"ships": [], "routes": {}, "seasons": {},
                "sail_types": [], "speeds_kn": []}
        insights = {"weather_years": [2025], "n_records": 900,
                    "bootstrap": {"method": "cbb", "n_samples": 500,
                                  "seed": 20260727}}
        bench = {"flettner": (6.0, 8.2, "refs")}
        out = build_audit_summary(meta, df=[], insights_meta=insights,
                                  bench_ranges=bench, screening_cap=30.0)
        assert out["coverage"]["insight_records"] == 900
        assert out["guardrails"]["screening_cap_pct"] == 30.0
        br = out["guardrails"]["benchmark_ranges"]["flettner"]
        assert br == {"lo": 6.0, "hi": 8.2, "refs": "refs"}
        rep = out["reproducibility"]
        assert rep["bootstrap_seed"] == 20260727
        assert rep["bootstrap_samples"] == 500
        assert rep["ci_tests"] > 0

    def test_model_chain_covers_key_models(self):
        text = " ".join(str(m) for m in MODEL_CHAIN)
        for kw in ("ERA5", "Holtrop", "CII", "NPV"):
            assert kw in text, f"model_chain 缺少 {kw}"

    def test_limitations_mention_single_year(self):
        assert any("2025" in s for s in LIMITATIONS)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.api import app
    return TestClient(app)


class TestAuditApi:
    def test_audit_200_and_coverage(self, client):
        r = client.get("/api/audit")
        assert r.status_code == 200
        d = r.json()
        import app.data_access as da
        _, df = da.load_grid()
        assert d["coverage"]["records"] == len(df)
        assert d["guardrails"]["screening_cap_pct"] == 30.0
        assert len(d["model_chain"]) >= 5
        assert len(d["limitations"]) >= 3
        assert d["reproducibility"]["dockerized"] is True
        # 实船区间三帆型齐全
        assert set(d["guardrails"]["benchmark_ranges"]) == {
            "flettner", "rigid_wing", "suction_wing"}
