"""Matchup page: as-of windows, ranks, odds snapshot, and the per-request warehouse read.

Runs against a small fixture warehouse built in tmp_path, never the real cfb.duckdb.
Fixture teams: Alpha(1), Beta(2), Gamma(3) are FBS; Delta(4) is FCS. 2026 schedule:
  wk1 Delta @ Alpha 10-30 · wk2 Gamma @ Alpha 20-17 · wk3 Alpha @ Beta 24-21 (conference)
  wk4 Beta @ Alpha, upcoming (the matchup under test).
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from cfb_system_maker.matchup import odds, queries as q
from cfb_system_maker.matchup.app import create_app
from cfb_system_maker.matchup.stats import ALL, Stat, edge

NOW = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)

FIXTURE_SQL = """
create schema core; create schema stg;
create table core.dim_team as select * from (values
  (1, 'Alpha', 'fbs'), (2, 'Beta', 'fbs'), (3, 'Gamma', 'fbs'), (4, 'Delta', 'fcs'))
  t(team_id, school, classification);
create table stg.fbs_teams as select * from (values
  (1, 2025, 'Alpha', 'X'), (2, 2025, 'Beta', 'X'), (3, 2025, 'Gamma', 'Y'),
  (1, 2026, 'Alpha', 'X'), (2, 2026, 'Beta', 'X'), (3, 2026, 'Gamma', 'Y'))
  t(teamId, season, school, conference);
create table core.dim_week as select season, week, 'regular' as season_type,
  s::timestamptz as start_date, e::timestamptz as end_date from (values
  (2026, 1, '2026-08-29 03:00:00-04', '2026-09-08 02:59:00-04'),
  (2026, 2, '2026-09-08 03:00:00-04', '2026-09-14 02:59:00-04'),
  (2026, 3, '2026-09-14 03:00:00-04', '2026-09-21 02:59:00-04'),
  (2026, 4, '2026-09-21 03:00:00-04', '2026-09-28 02:59:00-04')) t(season, week, s, e);
create table core.fact_game as select game_id, 2026 as season, week, 'regular' as season_type,
  start::timestamptz as start_date, completed, true as has_line, 1 as venue_id,
  home_team_id, away_team_id, home_team, away_team, 'X' as home_conference, 'X' as away_conference,
  home_points, away_points from (values
  (101, 1, '2026-09-05 19:00:00-04', true, 1, 4, 'Alpha', 'Delta', 30, 10),
  (102, 2, '2026-09-12 19:00:00-04', true, 1, 3, 'Alpha', 'Gamma', 17, 20),
  (103, 3, '2026-09-19 19:00:00-04', true, 2, 1, 'Beta', 'Alpha', 21, 24),
  (104, 4, '2026-09-26 19:30:00-04', false, 1, 2, 'Alpha', 'Beta', null, null))
  t(game_id, week, start, completed, home_team_id, away_team_id, home_team, away_team, home_points, away_points);
create table stg.games as select game_id as gameId, season, week, false as startTimeTBD,
  false as neutralSite, game_id = 103 as conferenceGame, null::varchar as notes from core.fact_game;
create table core.fact_game_line as select * from (values
  (104, 'pinnacle', -2.5, -3.0, 50.5, 51.5, -150, 130),
  (104, 'bovada', -2.5, -3.5, 50.5, 51.0, -160, 140)) t(game_id, provider_key, spread_open,
  spread_close, total_open, total_close, moneyline_home, moneyline_away);
create table core.v_game_book_median as select g.*, -2.5 as median_spread_open, 2 as n_books_spread_open,
  -3.25 as median_spread_close, 2 as n_books_spread_close, 50.5 as median_total_open, 2 as n_books_total_open,
  51.25 as median_total_close, 2 as n_books_total_close from core.fact_game g;
create table core.v_game as select g.*, 'Alpha Field' as venue_name, 'Town' as venue_city,
  'ST' as venue_state, false as venue_dome from core.fact_game g;
create table core.fact_game_odds as select 104 as game_id, 'draftkings' as book, market, side,
  line, -110 as odds, t::timestamptz as pulled_at, 'Alpha' as home_school, 'Beta' as away_school from (values
  ('spreads', 'home', -2.5, '2026-09-21 10:00:00-04'), ('spreads', 'away', 2.5, '2026-09-21 10:00:00-04'),
  ('totals', 'over', 50.5, '2026-09-21 10:00:00-04'),
  ('spreads', 'home', -3.0, '2026-09-22 10:00:00-04'), ('totals', 'over', 51.5, '2026-09-22 10:00:00-04'))
  t(market, side, line, t);
create table core.fact_game_weather (game_id integer, temperature double, wind_speed double,
  weather_condition varchar, game_indoors boolean, _source varchar);
create table stg.pregame_win_prob (gameId integer, homeWinProbability double, spread double);
create table core.dim_poll_type as select * from (values (1, 'AP Top 25', 'AP Poll'),
  (2, 'Coaches Poll', 'Coaches Poll')) t(poll_type_id, name, short_name);
create table core.fact_poll_rank as select 2026 as season, week, 'regular' as season_type,
  1 as poll_type_id, 1 as team_id, rank from (values (3, 20), (4, 15), (5, 10)) t(week, rank);
create table stg.massey_editions as select d::date as date, 2026 as season, 'Alpha' as cfbd_team,
  cmp as cmp_rank, 30 as n_systems, 2 as wins, 1 as losses from (values
  ('2026-09-20', 30), ('2026-09-27', 25)) t(d, cmp);
create table stg.massey_ranks as select d::date as date, 2026 as season, team as cfbd_team,
  'SYS' as system, r as rank from (values ('2026-09-20', 'Alpha', 30), ('2026-09-20', 'Beta', 40),
  ('2026-09-27', 'Alpha', 1)) t(d, team, r);
create table core.fact_coach_season as select 7 as coach_id, 1 as team_id, season,
  'Pat' as first_name, 'Coach' as last_name from (values (2025), (2026)) t(season);
create table stg.transfer_portal as select 2026 as season, * from (values
  ('Beta', 'Alpha', 3), ('Alpha', 'Gamma', 4)) t(origin, destination, stars);
create table stg.sp as select * from (values (2025, 'Alpha', 10.0), (2025, 'Beta', 5.0),
  (2025, 'Gamma', -2.0), (2026, 'Alpha', 20.0), (2026, 'Beta', 1.0)) t(season, team, rating);
alter table stg.sp add column offense_rating double; alter table stg.sp add column defense_rating double;
alter table stg.sp add column "specialTeams_rating" double;
create table stg.fpi (season int, team varchar, fpi double, efficiencies_offense double, efficiencies_defense double);
create table stg.srs (season int, team varchar, rating double);
create table stg.elo (season int, team varchar, elo double);
create table stg.core_ratings (season int, team varchar, overall double, offense double, defense double);
create table stg.adjusted_team_season (season int, team varchar, epa_total double, "epaAllowed_total" double,
  "successRate_total" double, "successRateAllowed_total" double, explosiveness double, "explosivenessAllowed" double);
create table stg.talent (season int, team varchar, talent double);
create table stg.recruiting_teams (season int, team varchar, points double);
create table stg.returning_production (season int, team varchar, "percentPPA" double, usage double);
"""

SNAPSHOT = {
    "pulled_at": "2026-09-23T16:00:00Z",
    "events": [{
        "home_team": "Alpha Aardvarks", "away_team": "Beta Bears", "commence_time": "2026-09-26T23:30:00Z",
        "bookmakers": [{"key": "draftkings", "last_update": "2026-09-23T15:59:00Z", "markets": [
            {"key": "spreads", "outcomes": [{"name": "Alpha Aardvarks", "price": -110, "point": -3.5},
                                            {"name": "Beta Bears", "price": -110, "point": 3.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 52.5},
                                           {"name": "Under", "price": -115, "point": 52.5}]},
            {"key": "h2h", "outcomes": [{"name": "Alpha Aardvarks", "price": -160},
                                        {"name": "Beta Bears", "price": 135}]}]}]},
        {"home_team": "Nowhere Nobodies", "away_team": "Beta Bears", "commence_time": "2026-10-03T23:30:00Z",
         "bookmakers": []}],
}


@pytest.fixture()
def warehouse(tmp_path) -> Path:
    db = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db))
    con.execute(FIXTURE_SQL)
    con.close()
    return db


@pytest.fixture()
def odds_dir(tmp_path) -> Path:
    d = tmp_path / "oddsapi"
    d.mkdir()
    (d / "odds_americanfootball_ncaaf_20260923T000000Z.json").write_text(
        json.dumps({"pulled_at": "2026-09-23T00:00:00Z", "events": []}), encoding="utf-8")
    (d / "odds_americanfootball_ncaaf_20260923T160000Z.json").write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    return d


@pytest.fixture()
def client(warehouse, odds_dir):
    return create_app(db_path=warehouse, odds_dir=odds_dir, clock=lambda: NOW).test_client()


def test_edge_ties_direction_and_missing():
    assert edge(0.4521, 0.4518, True) is None  # inside the 1% band
    assert edge(0.06, 0.05, True) == "a"       # the 0.001 floor keeps small PPA gaps meaningful
    assert edge(30.0, 20.0, False) == "b"      # lower is better
    assert edge(None, 1.0, True) is None
    assert edge(3.0, 1.0, None) is None        # descriptive rows get no marker


def test_rank_respects_direction_and_conference():
    universe = {1: {"conference": "X"}, 2: {"conference": "X"}, 3: {"conference": "Y"}}
    values = {1: 10.0, 2: 5.0, 3: 12.0, 99: 50.0}  # 99 is outside the universe
    up = Stat("k", "K", "t", "c", True, "num", "pregame_direct")
    down = Stat("k", "K", "t", "c", False, "num", "pregame_direct")
    assert q._side(up, values, universe, 1) | {} == {"value": 10.0, "rank": 2, "n": 3, "conf_rank": 1, "conf_n": 2}
    assert q._side(down, values, universe, 1)["rank"] == 2
    assert q._side(down, values, universe, 2)["rank"] == 1


def test_current_week_is_the_week_containing_now(warehouse):
    with q.warehouse(warehouse) as con:
        assert q.current_week(con, NOW) == {"season": 2026, "week": 4, "season_type": "regular"}


def test_record_window_excludes_the_selected_week_and_later(warehouse):
    with q.warehouse(warehouse) as con:
        wk4 = q.profile(con, 1, 2026, 4, q.first_kickoff(con, 2026, 4), full=False)
        wk3 = q.profile(con, 1, 2026, 3, q.first_kickoff(con, 2026, 3), full=False)
    assert wk4["record"] == {"w": 2, "l": 1, "conf_w": 1, "conf_l": 0}
    assert wk3["record"] == {"w": 1, "l": 1, "conf_w": 0, "conf_l": 0}


def test_poll_and_massey_are_as_of_the_week(warehouse):
    with q.warehouse(warehouse) as con:
        pr = q.profile(con, 1, 2026, 4, q.first_kickoff(con, 2026, 4), full=False)
    assert [(p["week"], p["rank"]) for p in pr["polls"]] == [(4, 15)]  # poll 5 is after kickoff
    assert pr["massey"]["cmp_rank"] == 30  # the 09-27 edition postdates the 09-26 kickoff


def test_ratings_show_prior_season_until_postgame_is_asked_for(warehouse):
    with q.warehouse(warehouse) as con:
        cutoff = q.first_kickoff(con, 2026, 4)
        asof = q.ratings(con, 2026, cutoff, 1, 2, full=False, show_postgame=False)
        shown = q.ratings(con, 2026, cutoff, 1, 2, full=False, show_postgame=True)
    sp = next(r for r in asof["rows"] if r["key"] == "sp_rating")
    assert asof["season"] == 2025 and sp["a"]["value"] == 10.0 and sp["a"]["rank"] == 1
    assert "postgame" not in asof
    assert next(r for r in shown["postgame"] if r["key"] == "sp_rating")["a"]["value"] == 20.0
    assert asof["massey"] == [{"system": "SYS", "a": 30, "b": 40}]


def test_newest_snapshot_and_name_resolution(odds_dir):
    path = odds.newest_snapshot(odds_dir)
    assert path.name.endswith("T160000Z.json")
    lines = odds.read_lines(path, odds.school_index(["Alpha", "Beta", "Gamma"]))
    game = lines["games"][frozenset({"Alpha", "Beta"})]
    assert game["books"]["draftkings"]["spread"] == {"Alpha": [-3.5, -110], "Beta": [3.5, -110]}
    assert lines["unresolved"] == 1  # "Nowhere Nobodies" is counted, not guessed


def test_matchup_api_shape_and_reserved_slots(client):
    body = client.get("/api/matchup?a=2&b=1&season=2026&week=4").get_json()
    assert body["model_signals"] is None
    assert body["meta"]["game_id"] == 104  # the wk4 rematch, not the wk3 game
    game = body["sections"]["game"]
    assert game["home_points"] is None  # results stay hidden in as-of mode
    dk = game["main_books"]["draftkings"]
    assert dk["now"]["source"] == "snapshot" and dk["now"]["spread"]["home"] == -3.5
    assert [h["spread_home"] for h in dk["history"]] == [-2.5, -3.0, -3.5]
    rows = body["sections"]["ratings"]["rows"] + body["sections"]["profile"]["rows"]
    assert rows and all(r["estimate"] is None for r in rows)


def test_slate_marks_lined_games(client):
    body = client.get("/api/slate").get_json()
    assert (body["season"], body["week"]) == (2026, 4)
    (g,) = body["games"]
    assert g["lined"] and g["books"]["draftkings"]["spread"]["home"] == -3.5


def test_busy_warehouse_is_a_503(tmp_path, odds_dir):
    app = create_app(db_path=tmp_path / "missing" / "cfb.duckdb", odds_dir=odds_dir, clock=lambda: NOW)
    r = app.test_client().get("/api/slate")
    assert r.status_code == 503 and r.get_json()["error"] == "warehouse_rebuilding"


def test_connection_is_closed_after_each_request(client, warehouse, tmp_path):
    """The nightly rebuild swaps a new file over cfb.duckdb; an open reader blocks that on Windows."""
    assert client.get("/api/matchup?a=1&b=2&season=2026&week=4").status_code == 200
    staged = tmp_path / "cfb.duckdb.building"
    duckdb.connect(str(staged)).close()
    os.replace(staged, warehouse)


def test_registry_verdicts_match_the_eligibility_audit():
    audit = Path(os.environ.get("CFB_DATA_ROOT", "")) / "processed" / "pregame_feature_eligibility.csv"
    if not audit.is_file():
        pytest.skip("eligibility audit CSV not built")
    with audit.open(newline="", encoding="utf-8") as fh:
        verdicts = {(r["table"], r["column"]): r["verdict"] for r in csv.DictReader(fh)}
    for stat in ALL:
        audited = verdicts.get((stat.table, stat.column))
        if audited is None:
            assert stat.reason, f"{stat.key}: the audit does not cover {stat.table}.{stat.column}; say why"
        else:
            assert stat.verdict == audited, f"{stat.key}: registry {stat.verdict}, audit {audited}"
