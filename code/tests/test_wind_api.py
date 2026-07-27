# -*- coding: utf-8 -*-
"""/api/wind-resource API 测试（纯查表端点）"""
import os
import sys

import pytest

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.api import app
    return TestClient(app)


BASE_REQ = {
    "ship": "kvlcc2", "route": "middle_east_china", "season": "summer",
    "sail": "flettner", "speed": 14.0,
}


class TestWindResourceApi:
    def test_fields_complete(self, client):
        r = client.post("/api/wind-resource", json=BASE_REQ)
        assert r.status_code == 200
        d = r.json()
        assert d["available"] is True
        assert d["speed_used"] == 14.0
        s = d["summary"]
        for k in ("mean_true_wind_ms", "mean_apparent_wind_ms",
                  "net_saving_contribution_hours_pct",
                  "low_wind_hours_pct", "headwind_hours_pct",
                  "beam_reach_hours_pct", "tailwind_hours_pct",
                  "wind_speed_hist", "relative_angle_hist"):
            assert k in s, f"summary 缺少 {k}"
        assert 0.0 <= s["net_saving_contribution_hours_pct"] <= 100.0
        # 直方图占比总和约 100（全零除外）
        assert abs(sum(s["wind_speed_hist"]["pct"]) - 100.0) < 1.0
        assert abs(sum(s["relative_angle_hist"]["pct"]) - 100.0) < 1.0
        assert d["interpretation"]["fit_level"] in ("good", "medium", "poor")

    def test_nearest_speed_snap(self, client):
        r = client.post("/api/wind-resource",
                        json={**BASE_REQ, "speed": 13.4})
        assert r.status_code == 200
        d = r.json()
        assert d["available"] is True
        assert d["speed_used"] in (12.0, 14.0)

    def test_unknown_route_400(self, client):
        r = client.post("/api/wind-resource",
                        json={**BASE_REQ, "route": "no_such_route"})
        assert r.status_code == 400

    def test_missing_insight_degrades(self, client, monkeypatch):
        import app.api as api_mod
        monkeypatch.setattr(api_mod, "INSIGHTS_INDEX", {})
        r = client.post("/api/wind-resource", json=BASE_REQ)
        assert r.status_code == 200
        assert r.json() == {"available": False,
                            "reason": "no_precomputed_insight"}
