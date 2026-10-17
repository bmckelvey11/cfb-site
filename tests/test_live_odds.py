"""Live odds page: game state, main-line pick, moneyline orientation, and the cached API.

Event and market fields are copied from a live pull of cfb-chsou-clmsn-2026-10-17 at
18:45Z on 2026-10-17 (Q4, Clemson 37-0): score is "away-home", `outcomes` is a JSON string,
`bestBid` is absent when nobody bids, placeholder rungs carry $5 and a 0.495/0.505 price.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cfb_system_maker.live import board as b
from cfb_system_maker.live.app import create_app

NOW = datetime(2026, 10, 17, 18, 45, tzinfo=timezone.utc)

ML = {"id": "5349154", "sportsMarketType": "moneyline",
      "outcomes": "[\"Charleston Southern\", \"Clemson\"]", "outcomePrices": "[\"0.0005\", \"0.9995\"]",
      "bestAsk": 0.001, "liquidityNum": 258598.99, "volumeNum": 130916.37}
PLACEHOLDER_SPREAD = {"id": "5349155", "sportsMarketType": "spreads", "line": -20.5,
                      "question": "Spread: Charleston Southern (-20.5)",
                      "outcomes": "[\"Charleston Southern\", \"Clemson\"]",
                      "outcomePrices": "[\"0.495\", \"0.505\"]", "bestBid": 0.01, "bestAsk": 0.99,
                      "liquidityNum": 5, "volumeNum": 10}


def total(line, bid, ask, liq, **kw):
    return {"id": f"t{line}", "slug": f"cfb-chsou-clmsn-2026-10-17-total-{line}",
            "sportsMarketType": "totals", "line": line, "outcomes": "[\"Over\", \"Under\"]",
            "bestBid": bid, "bestAsk": ask, "liquidityNum": liq, "volumeNum": 100, **kw}


TOTALS = [
    total(39.5, 0.838, 0.86, 11643.13),
    total(45.5, 0.39, 0.43, 9400),
    total(35.5, 0.055, 1.0, 222.18, outcomePrices="[\"0.5275\", \"0.4725\"]"),   # wide: stale price
    total(65.5, 0.01, 0.99, 5),                                                   # placeholder
    total(59.5, 0.03, 0.09, 29400),
]
TEAMS = [{"alias": "Charleston Southern", "ordering": "away"}, {"alias": "Clemson", "ordering": "home"}]
LIVE = {"id": "1139609", "slug": "cfb-chsou-clmsn-2026-10-17", "title": "Charleston Southern vs. Clemson",
        "startTime": "2026-10-17T16:00:00Z", "score": "0-37", "period": "Q4", "elapsed": "12:09",
        "live": True, "ended": False, "teams": TEAMS, "markets": [ML, PLACEHOLDER_SPREAD, *TOTALS]}
UPCOMING = {"id": "2", "slug": "cfb-wisc-ucla-2026-10-17", "title": "Wisconsin vs. UCLA",
            "startTime": "2026-10-17T20:30:00Z", "teams": [], "markets": []}
FINAL = {"id": "3", "slug": "cfb-applst-coast-2026-10-16", "title": "App State vs. Coastal Carolina",
         "startTime": "2026-10-16T23:30:00Z", "score": "35-32", "period": "VFT", "elapsed": "",
         "live": False, "ended": True, "markets": []}


@pytest.mark.parametrize("event, expected", [
    (LIVE, "live"),
    (UPCOMING, "upcoming"),
    (FINAL, "final"),
    (dict(UPCOMING, period="CAN", ended=False, score=""), "other"),
    (dict(UPCOMING, startTime="2026-10-17T16:00:00Z"), "other"),   # started, not flagged live
])
def test_state(event, expected):
    assert b.state(event, NOW) == expected


def test_live_game_reads_score_away_home_and_the_clock():
    g = b.game(LIVE, "live")
    assert (g["away"], g["home"]) == ("Charleston Southern", "Clemson")
    assert (g["away_score"], g["home_score"]) == (0, 37)
    assert (g["period"], g["clock"]) == ("Q4", "12:09")


def test_main_total_skips_wide_and_placeholder_rungs():
    # 35.5's displayed 0.5275 is nearer 50% than 45.5's 0.41 midpoint, but its book is 0.055/1.0.
    t = b.main_line(TOTALS, "totals")
    assert t["line"] == 45.5 and t["mid"] == 0.41 and t["first"] == "Over"


def test_no_tradable_spread_shows_no_line():
    assert b.main_line([PLACEHOLDER_SPREAD], "spreads") is None


def test_moneyline_with_no_bid_is_oriented_to_home():
    ml = b.moneyline([ML], "Charleston Southern", "Clemson")
    assert ml["home"] == pytest.approx(0.9995) and ml["away"] == pytest.approx(0.0005)


def test_moneyline_flips_when_home_is_listed_first():
    market = dict(ML, outcomes="[\"Clemson\", \"Charleston Southern\"]", bestBid=0.60, bestAsk=0.62)
    assert b.moneyline([market], "Charleston Southern", "Clemson")["home"] == pytest.approx(0.61)


def test_board_keeps_live_and_soon_and_drops_the_rest():
    later = dict(UPCOMING, id="4", slug="cfb-x-y", startTime=(NOW + timedelta(hours=5)).isoformat())
    margin = dict(LIVE, slug="cfb-chsou-clmsn-2026-10-17-exact-margin")
    out = b.board([LIVE, UPCOMING, FINAL, later, margin], NOW)
    assert [g["slug"] for g in out["live"]] == ["cfb-chsou-clmsn-2026-10-17"]
    assert [g["slug"] for g in out["upcoming"]] == ["cfb-wisc-ucla-2026-10-17"]


def fake_gamma(calls):
    def fetch(url, params):
        calls.append(url)
        if url.endswith("/sports"):
            return [{"sport": "cfb", "series": "12756"}]
        return {"events": [LIVE, UPCOMING, FINAL]}
    return fetch


def test_api_serves_the_board_and_caches_polymarket():
    calls = []
    client = create_app(fetch_fn=fake_gamma(calls), clock=lambda: NOW, cache_seconds=60).test_client()
    first = client.get("/api/live").get_json()
    client.get("/api/live")
    assert first["pulled_at"] == "2026-10-17T18:45:00Z"
    assert first["live"][0]["total"]["line"] == 45.5
    assert [g["slug"] for g in first["upcoming"]] == ["cfb-wisc-ucla-2026-10-17"]
    assert sum(u.endswith("/events/keyset") for u in calls) == 1     # second request hit the cache


def test_api_reports_a_failed_pull_as_json():
    def broken(url, params):
        raise RuntimeError("HTTP 403")
    res = create_app(fetch_fn=broken, clock=lambda: NOW).test_client().get("/api/live")
    assert res.status_code == 503 and res.get_json()["error"] == "polymarket_unavailable"


def test_page_renders():
    res = create_app(fetch_fn=fake_gamma([]), clock=lambda: NOW).test_client().get("/")
    assert res.status_code == 200 and b"Live odds" in res.data
