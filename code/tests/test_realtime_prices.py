# -*- coding: utf-8 -*-
"""Market-price provenance and region-selection regression tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import realtime_prices as prices


def test_fixed_market_estimates_are_static_and_unlinked(monkeypatch):
    monkeypatch.setattr(prices, "_fetch_eia_brent_quote", lambda: (None, False))
    fuel = prices.fetch_fuel_price("Singapore")
    carbon = prices.fetch_carbon_price("EU ETS (IMO)")

    for point in (fuel, carbon):
        assert point.freshness == "static"
        assert point.source_url == ""

    assert "100% in 2026" in carbon.note


def test_eia_brent_quote_drives_delayed_regional_fuel_reference(monkeypatch):
    monkeypatch.setattr(
        prices,
        "_fetch_eia_brent_quote",
        lambda: ({"value": 86.99, "period": "2026-07-20"}, False),
    )
    singapore = prices.fetch_fuel_price("Singapore")
    rotterdam = prices.fetch_fuel_price("Rotterdam")

    assert singapore.freshness == "delayed"
    assert singapore.timestamp == "2026-07-20T00:00:00Z"
    assert singapore.source_url.startswith("https://www.eia.gov/")
    assert singapore.value == 0.758
    assert rotterdam.value == 0.738


def test_eia_payload_parser_and_cache(monkeypatch):
    prices._cache.clear()
    calls = []

    def fake_json(url):
        calls.append(url)
        return {"response": {"data": [{"period": "2026-07-20", "value": "86.99"}]}}

    monkeypatch.setattr(prices, "_fetch_json", fake_json)
    first, first_cached = prices._fetch_eia_brent_quote()
    second, second_cached = prices._fetch_eia_brent_quote()

    assert first == second == {"value": 86.99, "period": "2026-07-20"}
    assert first_cached is False and second_cached is True
    assert len(calls) == 1
    assert "api.eia.gov" in calls[0] and "RBRTE" in calls[0]


def test_browser_timezone_does_not_select_domestic_china_ets():
    region, hub, market = prices.resolve_region("Asia/Shanghai")
    assert region == "asia"
    assert hub == "Singapore"
    assert market == "EU ETS (IMO)"
