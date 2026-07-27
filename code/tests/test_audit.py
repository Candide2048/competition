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
class TestAuditLocale:
    """locale 双语：默认中文、英文零汉字、双语结构一致、非法值拒绝"""

    _META = {"ships": [], "routes": {}, "seasons": {},
             "sail_types": [], "speeds_kn": []}

    def test_unit_default_locale_is_zh(self):
        out = build_audit_summary(self._META, df=[])
        assert out["model_chain"] is MODEL_CHAIN
        assert out["limitations"] is LIMITATIONS

    def test_unit_invalid_locale_raises(self):
        with pytest.raises(ValueError):
            build_audit_summary(self._META, df=[], locale="fr")

    def test_api_en_has_no_cjk(self, client):
        import re
        r = client.get("/api/audit?locale=en")
        assert r.status_code == 200
        assert not re.search(r"[\u4e00-\u9fff]", r.text)

    def test_api_zh_en_structurally_consistent(self, client):
        zh = client.get("/api/audit?locale=zh").json()
        en = client.get("/api/audit?locale=en").json()
        # 数值/结构字段与语言无关
        assert zh["coverage"] == en["coverage"]
        assert (zh["guardrails"]["screening_cap_pct"]
                == en["guardrails"]["screening_cap_pct"])
        assert (zh["guardrails"]["benchmark_ranges"]
                == en["guardrails"]["benchmark_ranges"])
        assert (zh["reproducibility"]["ci_tests"]
                == en["reproducibility"]["ci_tests"])
        assert len(zh["model_chain"]) == len(en["model_chain"])
        assert len(zh["limitations"]) == len(en["limitations"])

    def test_api_invalid_locale_422(self, client):
        assert client.get("/api/audit?locale=fr").status_code == 422
