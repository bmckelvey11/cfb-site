"""Polymarket: paging, the upcoming-game filter, the spread sign, and the bid/ask flip.

Fixture fields are copied from a live pull of cfb-gast-jmad-2026-10-17 (2026-10-17).
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from cfb_system_maker.polymarket_client import (  # noqa: E402
    fetch_markets, is_upcoming_game, write_snapshot,
)
from cfb_system_maker.polymarket_schema import PM_TABLES, column_type  # noqa: E402
from polymarket_flatten import (  # noqa: E402
    SNAPSHOT_COLUMNS, TICK_COLUMNS, flatten, home_away, side_of, write,
)

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)

ML = {"id": "5349745", "slug": "cfb-gast-jmad-2026-10-17",
      "question": "Georgia State vs. James Madison", "sportsMarketType": "moneyline",
      "line": None, "outcomes": "[\"Georgia State\", \"James Madison\"]",
      "outcomePrices": "[\"0.235\", \"0.765\"]", "bestBid": 0.23, "bestAsk": 0.24,
      "lastTradePrice": 0.24, "volumeNum": 2529.68496, "liquidityNum": 171744.4067,
      "acceptingOrders": True, "updatedAt": "2026-10-17T10:11:15.391001Z",
      "clobTokenIds": "[\"1\", \"2\"]"}
SPREAD = {"id": "5625597", "slug": "cfb-gast-jmad-2026-10-17-spread-home-12pt5",
          "question": "Spread: James Madison (-12.5)", "sportsMarketType": "spreads",
          "line": -12.5, "outcomes": "[\"James Madison\", \"Georgia State\"]",
          "outcomePrices": "[\"0.415\", \"0.585\"]", "bestBid": 0.41, "bestAsk": 0.42,
          "lastTradePrice": 0.45, "volumeNum": 113010.614035, "liquidityNum": 18327.2373,
          "acceptingOrders": True, "updatedAt": "2026-10-17T10:09:16.253128Z"}
TOTAL = {"id": "5349787", "slug": "cfb-gast-jmad-2026-10-17-total-57pt5",
         "question": "Georgia State vs. James Madison: O/U 57.5", "sportsMarketType": "totals",
         "line": 57.5, "outcomes": "[\"Over\", \"Under\"]",
         "outcomePrices": "[\"0.525\", \"0.475\"]", "bestBid": 0.52, "bestAsk": 0.53,
         "lastTradePrice": 0.53, "volumeNum": 25092.376394, "liquidityNum": 137030.037,
         "acceptingOrders": True, "updatedAt": "2026-10-17T10:05:15.520322Z"}
PROP = {"id": "9", "sportsMarketType": "exact_margin", "outcomes": "[\"Yes\", \"No\"]"}

GAME = {"id": "1139615", "slug": "cfb-gast-jmad-2026-10-17",
        "title": "Georgia State vs. James Madison", "startTime": "2026-10-17T16:00:00Z",
        "gameId": 70898876, "eventWeek": 7, "ended": None, "live": None,
        "teams": [{"name": "Panthers", "alias": "Georgia State", "abbreviation": "gast",
                   "ordering": "away", "providerId": 328, "logo": "x"},
                  {"name": "Dukes", "alias": "James Madison", "abbreviation": "jmad",
                   "ordering": "home", "providerId": 126}],
        "markets": [ML, SPREAD, TOTAL, PROP]}


def fake_gamma(pages, calls=None):
    def fetch(url, params):
        if calls is not None:
            calls.append((url, dict(params)))
        if url.endswith("/sports"):
            return [{"sport": "ncaab", "series": "1"},
                    {"id": 9, "sport": "cfb", "tags": "1,100351,100639", "series": "12756"}]
        return pages[params.get("after_cursor")]
    return fetch


# ---------------------------------------------------------------------- client

def test_pages_follow_next_cursor_until_it_is_absent():
    other = dict(GAME, id="2", slug="cfb-a-b-2026-10-18", startTime="2026-10-18T16:00:00Z")
    pages = {None: {"events": [GAME], "next_cursor": "c1"},
             "c1": {"events": [other], "next_cursor": None}}
    calls = []
    payload = fetch_markets(fetch_fn=fake_gamma(pages, calls), now=NOW)

    assert payload["series_id"] == "12756"          # read from /sports, not pinned
    assert payload["pages"] == 2 and payload["events_seen"] == 2
    assert [e["id"] for e in payload["events"]] == ["1139615", "2"]
    assert calls[1][1]["series_id"] == "12756" and calls[2][1]["after_cursor"] == "c1"


def test_only_full_game_ml_spread_total_markets_are_kept_and_trimmed():
    payload = fetch_markets(fetch_fn=fake_gamma({None: {"events": [GAME]}}), now=NOW)
    markets = payload["events"][0]["markets"]
    assert [m["sportsMarketType"] for m in markets] == ["moneyline", "spreads", "totals"]
    assert "clobTokenIds" not in markets[0]
    assert "logo" not in payload["events"][0]["teams"][0]


@pytest.mark.parametrize("change", [
    {"slug": "cfb-gast-jmad-2026-10-17-exact-margin"},   # companion event
    {"ended": True},                                     # closed=false still returns these
    {"startTime": None},                                 # AP-poll futures
    {"startTime": "2026-10-17T09:00:00Z"},               # kicked off: in-play is lookahead
])
def test_non_games_and_started_games_are_dropped(change):
    assert not is_upcoming_game(dict(GAME, **change), NOW)


def test_an_upcoming_game_is_kept():
    assert is_upcoming_game(GAME, NOW)


def test_snapshot_file_is_timestamped(tmp_path):
    payload = fetch_markets(fetch_fn=fake_gamma({None: {"events": [GAME]}}), now=NOW)
    path = write_snapshot(payload, tmp_path)
    assert path.name == "pm_cfb_20261017T100000Z.json"
    assert json.loads(path.read_text())["pulled_at"] == "2026-10-17T10:00:00Z"


# ---------------------------------------------------------------------- flatten

def _rows(tmp_path):
    payload = fetch_markets(fetch_fn=fake_gamma({None: {"events": [GAME]}}), now=NOW)
    path = write_snapshot(payload, tmp_path)
    schools = {"georgia state": "Georgia State", "james madison": "James Madison"}
    return flatten([path], schools)


def test_home_and_away_come_from_team_ordering():
    assert home_away(GAME) == ("James Madison", "Georgia State")


def test_title_lists_away_first_when_teams_are_missing():
    assert home_away(dict(GAME, teams=[])) == ("James Madison", "Georgia State")


def test_an_unmatched_outcome_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="neither Over/Under"):
        side_of("JMU", "James Madison", "Georgia State")


def test_spread_line_belongs_to_first_outcome_and_flips_for_the_second(tmp_path):
    ticks, _, _ = _rows(tmp_path)
    spread = {t["side"]: t for t in ticks if t["market"] == "spreads"}
    assert spread["home"]["line"] == -12.5      # James Madison -12.5
    assert spread["away"]["line"] == 12.5       # Georgia State +12.5


def test_second_outcome_quotes_are_the_complement(tmp_path):
    ticks, _, _ = _rows(tmp_path)
    away = next(t for t in ticks if t["market"] == "spreads" and t["side"] == "away")
    assert away["price"] == 0.585
    assert away["best_bid"] == pytest.approx(0.58) and away["best_ask"] == pytest.approx(0.59)
    assert away["last_trade_price"] == pytest.approx(0.55)


def test_totals_and_moneyline_rows(tmp_path):
    ticks, snaps, names = _rows(tmp_path)
    totals = {t["side"]: t for t in ticks if t["market"] == "totals"}
    assert totals["over"]["line"] == totals["under"]["line"] == 57.5
    ml = {t["side"]: t for t in ticks if t["market"] == "moneyline"}
    assert ml["away"]["price"] == 0.235 and ml["away"]["line"] == ""
    assert ml["home"]["home_school"] == "James Madison"
    assert len(ticks) == 6 and snaps[0]["market_count"] == 3
    assert all(names.values())


def test_csv_columns_and_types_line_up(tmp_path):
    ticks, snaps, _ = _rows(tmp_path)
    write(ticks, snaps, tmp_path / "out")
    for name, columns in (("pm_market_tick", TICK_COLUMNS), ("pm_snapshot", SNAPSHOT_COLUMNS)):
        with (tmp_path / "out" / f"{name}.csv").open(newline="") as fh:
            assert next(csv.reader(fh)) == columns
    assert set(PM_TABLES) == {"pm_market_tick", "pm_snapshot"}
    assert column_type("line") == "DOUBLE" and column_type("pulled_at").startswith("TIMESTAMP")
    assert column_type("accepting_orders") == "BOOLEAN" and column_type("market_id") == "VARCHAR"


def test_the_csv_loads_into_duckdb_with_the_pinned_types(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    from cfb_system_maker.polymarket_schema import column_types
    ticks, snaps, _ = _rows(tmp_path)
    write(ticks, snaps, tmp_path / "out")
    path = tmp_path / "out" / "pm_market_tick.csv"
    con = duckdb.connect()
    rel = con.read_csv(str(path), header=True, columns=column_types(TICK_COLUMNS))
    rows = rel.filter("market = 'spreads'").order("side").fetchall()
    assert len(rows) == 2 and rel.filter("market = 'moneyline' AND line IS NULL").count("*").fetchone()[0] == 2


def test_the_loader_plans_both_tables_with_pinned_types(tmp_path):
    from cfb_system_maker.duckdb_load import _plan_loads
    ticks, snaps, _ = _rows(tmp_path)
    write(ticks, snaps, tmp_path / "root" / "processed" / "polymarket")
    jobs = {j["name"]: j for j in _plan_loads(tmp_path / "root", only=set(PM_TABLES),
                                              include_actionnetwork=False)}
    assert set(jobs) == set(PM_TABLES)
    assert jobs["pm_market_tick"]["schema"] == "stg"
    assert jobs["pm_market_tick"]["columns"]["line"] == "DOUBLE"
