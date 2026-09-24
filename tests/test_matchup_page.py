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
from cfb_system_maker.matchup.stats import ALL, SOURCES, UNITS, Stat, edge

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
create table stg.teams as select * from (values (1, 2026, '#0a254e', '#b72025'), (2, 2025, '#006f71', null))
  t("teamId", season, color, "alternateColor");
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
  (99, 1, '2026-08-22 19:00:00-04', true, 2, 4, 'Beta', 'Delta', 40, 0),
  (100, 1, '2026-08-29 19:00:00-04', true, 2, 3, 'Beta', 'Gamma', 14, 10),
  (101, 1, '2026-09-05 19:00:00-04', true, 1, 4, 'Alpha', 'Delta', 30, 10),
  (102, 2, '2026-09-12 19:00:00-04', true, 1, 3, 'Alpha', 'Gamma', 17, 20),
  (103, 3, '2026-09-19 19:00:00-04', true, 2, 1, 'Beta', 'Alpha', 21, 24),
  (104, 4, '2026-09-26 19:30:00-04', false, 1, 2, 'Alpha', 'Beta', null, null))
  t(game_id, week, start, completed, home_team_id, away_team_id, home_team, away_team, home_points, away_points);
create table core.fact_game_historical as select 9 as game_id, 1999 as season, 5 as week,
  'regular' as season_type, '1999-10-02 13:00:00-04'::timestamptz as start_date, false as neutral_site,
  1 as home_team_id, 2 as away_team_id, 'Alpha' as home_team, 'Beta' as away_team, 7 as home_points,
  14 as away_points;
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
  1 as poll_type_id, team_id, rank from (values (3, 1, 20), (4, 1, 15), (5, 1, 10), (3, 2, 22), (4, 3, 5))
  t(week, team_id, rank);
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


# Game-grain rows: (game, week, team, opponent, offense_successRate, offense_plays).
# Alpha as of wk4 with FCS excluded: games 102 and 103 -> pooled (0.4*100 + 0.5*50) / 150.
GAME_ROWS = [
    (101, 1, "Alpha", "Delta", 0.9, 50), (101, 1, "Delta", "Alpha", 0.2, 50),
    (102, 2, "Alpha", "Gamma", 0.4, 100), (102, 2, "Gamma", "Alpha", 0.35, 70),
    (103, 3, "Beta", "Alpha", 0.3, 60), (103, 3, "Alpha", "Beta", 0.5, 50),
]


def _game_table(con, name: str, source: str, max_week: int = 99) -> None:
    """A stg game table with every offense_/defense_ column the registry reads for `source`."""
    units = [u for u in UNITS if u.source == source]
    cols = sorted({f"{side}_{x}" for u in units for side in ("offense", "defense")
                   for x in (u.stem, u.weight) if x})
    con.execute(f'create table {name} ("gameId" int, season int, week int, "seasonType" varchar, '
                f'team varchar, opponent varchar, {", ".join(f"{c} double" for c in cols)})')
    for gid, week, team, opp, sr, plays in GAME_ROWS:
        if week > max_week:
            continue
        vals = {c: 0.5 for c in cols}
        vals.update({c: 60.0 for c in cols if c.endswith(("_plays", "_totalPlays"))})
        vals.update(offense_successRate=sr, offense_plays=plays)
        con.execute(f"insert into {name} values (?, 2026, ?, 'regular', ?, ?, {', '.join('?' * len(cols))})",
                    [gid, week, team, opp, *[vals.get(c) for c in cols]])


DRIVES_SQL = """
create table core.fact_drive_postgame as select game_id, 2026 as season, offense_team_id, defense_team_id,
  scoring, plays, start_yards_to_goal, end_yards_to_goal, 0 as start_offense_score, pts as end_offense_score,
  2 as elapsed_minutes, 0 as elapsed_seconds from (values
  (102, 1, 3, true, 8, 75, 0, 7), (102, 1, 3, false, 3, 80, 70, 0), (103, 1, 2, true, 6, 60, 20, 3),
  (102, 3, 1, false, 5, 75, 60, 0), (103, 2, 1, false, 4, 75, 65, 0))
  t(game_id, offense_team_id, defense_team_id, scoring, plays, start_yards_to_goal, end_yards_to_goal, pts);
"""


# PFF player-weeks: (table, week, franchise, player, {column: value}). Franchises 11/12/13 are
# Alpha/Beta/Gamma. Beta's PFF week 0 is its Aug 22 game vs FCS Delta, week 1 the Aug 29 game.
PFF_ROWS = [
    ("stg.pff_offense_summary", 1, 11, 501, {"grades_offense": 90, "snap_counts_total": 10}),
    ("stg.pff_offense_summary", 2, 11, 501, {"grades_offense": 60, "snap_counts_total": 30}),
    ("stg.pff_offense_summary", 3, 11, 501, {"grades_offense": 70, "snap_counts_total": 10}),
    ("stg.pff_offense_summary", 0, 12, 601, {"grades_offense": 50, "snap_counts_total": 10}),
    ("stg.pff_offense_summary", 1, 12, 601, {"grades_offense": 80, "snap_counts_total": 10}),
    ("stg.pff_passing", 2, 11, 501, {"grades_pass": 75, "dropbacks": 30, "epa": 6}),
    ("stg.pff_passing", 3, 11, 502, {"grades_pass": 55, "dropbacks": 5, "epa": 0}),
    ("stg.pff_field_goal", 2, 11, 503, {"grades_fgep_kicker": 70, "total_attempts": 2, "total_made": 1}),
]


def _pff_tables(con) -> None:
    from cfb_system_maker.matchup.stats import PFF_METRICS, PFF_PLAYERS, SPECIAL_TEAMS
    cols: dict[str, set] = {}
    for m in PFF_METRICS + SPECIAL_TEAMS:
        cols.setdefault(m.table, set()).update({m.column, m.weight})
    for _, table, grade, volume, (_, xnum, xden), _, _ in PFF_PLAYERS:
        cols.setdefault(table, set()).update(c for c in (grade, volume, xnum, xden) if c)
    split_tables = {m.table for m in PFF_METRICS if m.split} | {t for _, t, *_, s in PFF_PLAYERS if s}
    for table, cs in cols.items():
        cs = sorted(cs)
        extra = ", split varchar" if table in split_tables else ""
        con.execute(f"create table {table} (season int, week int, player_id int, franchise_id int{extra}, "
                    + ", ".join(f"{c} double" for c in cs) + ")")
        for t, week, fr, pid, vals in PFF_ROWS:
            if t == table:
                names = ["season", "week", "player_id", "franchise_id", *(["split"] if extra else []), *vals]
                con.execute(f"insert into {table} ({', '.join(names)}) values ({', '.join('?' * len(names))})",
                            [2026, week, pid, fr, *(["all"] if extra else []), *vals.values()])
    con.execute("""create table stg.pff_franchise as select * from (values (11, 'team', 1), (12, 'team', 2),
                   (13, 'team', 3)) t(franchise_id, kind, cfbd_team_id)""")
    con.execute("""create table stg.pff_player_season as select * from (values (2026, 501, 'Al QB', 'QB'),
                   (2026, 502, 'Backup QB', 'QB')) t(season, player_id, player, position)""")
    con.execute("""create table stg.kicker_paar as select * from (values (2025, 'Alpha', 1.5, 20),
                   (2025, 'Beta', -0.5, 18), (2026, 'Alpha', 3.0, 4)) t(season, team, paar, attempts)""")
    con.execute("""create table stg.ppa_players_games as select * from (values
                   ('9', 2026, 2, 'regular', 'Alpha', 'Al QB', 'Gamma', 0.4, 0.5, 0.1, 'QB'),
                   ('9', 2026, 1, 'regular', 'Alpha', 'Al QB', 'Delta', 0.9, 0.9, 0.9, 'QB'))
                   t("athleteId", season, week, "seasonType", team, name, opponent, "averagePPA_all",
                     "averagePPA_pass", "averagePPA_rush", position)""")
    con.execute("create table stg.ppa_players_games_ngt as select * from stg.ppa_players_games")


@pytest.fixture()
def warehouse(tmp_path) -> Path:
    db = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db))
    con.execute(FIXTURE_SQL)
    _pff_tables(con)
    _game_table(con, "stg.advanced_game_stats", "advanced")
    _game_table(con, "stg.advanced_game_stats_ngt", "advanced", max_week=2)  # lags a week
    _game_table(con, "stg.ppa_games", "ppa")
    _game_table(con, "stg.ppa_games_ngt", "ppa")
    _game_table(con, "stg.game_havoc_stats", "havoc")
    con.execute(DRIVES_SQL)
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


def test_poll_rank_is_the_latest_poll_not_the_teams_last_ranked_week(warehouse):
    with q.warehouse(warehouse) as con:
        cutoff = q.first_kickoff(con, 2026, 4)
        beta = q.profile(con, 2, 2026, 4, cutoff, full=False)["polls"]
        gamma = q.profile(con, 3, 2026, 4, cutoff, full=False)["polls"]
    assert [(p["week"], p["rank"]) for p in beta] == [(4, None)]  # ranked in wk3, dropped out of wk4
    assert [(p["week"], p["rank"]) for p in gamma] == [(4, 5)]


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
    assert body["meta"]["b"]["color"] == "#0a254e"
    assert body["meta"]["a"]["color"] == "#006f71"  # no 2026 record: falls back to the latest season
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
    assert r.status_code == 503 and r.get_json()["error"] == "warehouse_busy"
    assert "rebuilt" in r.get_json()["message"]


def test_a_failed_query_answers_json_not_a_traceback(client, monkeypatch):
    def oom(*args, **kwargs):
        raise duckdb.OutOfMemoryException("Out of Memory Error: failed to allocate")
    monkeypatch.setattr(q, "profile", oom)
    r = client.get("/api/matchup?a=1&b=2&season=2026&week=4")
    body = r.get_json()
    assert r.status_code == 503 and body["error"] == "warehouse_busy"
    assert "Out of Memory Error" not in body["message"]  # exception text stays in the log


def test_api_errors_are_json_with_a_message(client):
    r = client.get("/api/matchup?a=1&b=999&season=2026&week=4")
    assert r.status_code == 404 and r.get_json()["message"] == "unknown team id"
    r = client.get("/api/matchup?a=1&b=2&week=x")
    assert r.status_code == 400 and "integer" in r.get_json()["message"]


def test_overlapping_requests_wait_at_the_gate_then_answer_busy(client, monkeypatch):
    monkeypatch.setattr(q, "GATE_TIMEOUT_S", 0.05)
    held = [q._GATE.acquire(), q._GATE.acquire()]  # two requests already reading the warehouse
    try:
        r = client.get("/api/slate")
        assert r.status_code == 503 and "still loading" in r.get_json()["message"]
    finally:
        for _ in held:
            q._GATE.release()
    assert client.get("/api/slate").status_code == 200  # the gate frees up again


def test_connection_is_closed_after_each_request(client, warehouse, tmp_path):
    """The nightly rebuild swaps a new file over cfb.duckdb; an open reader blocks that on Windows."""
    assert client.get("/api/matchup?a=1&b=2&season=2026&week=4").status_code == 200
    staged = tmp_path / "cfb.duckdb.building"
    duckdb.connect(str(staged)).close()
    os.replace(staged, warehouse)


def _win(con, rollup="pooled", fcs=True, week=4, table="stg.advanced_game_stats", source="advanced"):
    units = [u for u in UNITS if u.source == source]
    return q.windowed(con, SOURCES[source], units, table, 2026, week, full=False, rollup=rollup, fcs=fcs)


def test_pooled_is_play_weighted_and_mean_counts_games_once(warehouse):
    with q.warehouse(warehouse) as con:
        pooled, mean = _win(con)[1], _win(con, rollup="mean")[1]
    assert pooled["n"] == 2 and pooled["offense_successRate"] == pytest.approx(65 / 150)
    assert mean["offense_successRate"] == pytest.approx(0.45)


def test_fcs_toggle_and_week_window(warehouse):
    with q.warehouse(warehouse) as con:
        with_fcs = _win(con, fcs=False)[1]
        wk3 = _win(con, week=3)[1]
        last3 = _win(con, rollup="last3", fcs=False, week=4)[1]
    assert with_fcs["n"] == 3 and with_fcs["offense_successRate"] == pytest.approx(110 / 200)
    assert wk3["n"] == 1 and wk3["offense_successRate"] == pytest.approx(0.4)  # the wk3 game is out
    assert last3["n"] == 3


def test_drives_roll_up_per_game_then_pool_by_drives(warehouse):
    with q.warehouse(warehouse) as con:
        pooled = _win(con, table="core.fact_drive_postgame", source="drives")[1]
        mean = _win(con, rollup="mean", table="core.fact_drive_postgame", source="drives")[1]
    assert pooled["offense_ppd"] == pytest.approx(10 / 3)  # 7 + 0 + 3 points on 3 drives
    assert mean["offense_ppd"] == pytest.approx((3.5 + 3) / 2)
    assert pooled["offense_so_rate"] == pytest.approx(2 / 3)


def test_lagging_garbage_time_twin_falls_back_to_all_plays(warehouse):
    with q.warehouse(warehouse) as con:
        assert q.pick_table(con, SOURCES["advanced"], 2026, True) == ("stg.advanced_game_stats", False, 1)
        assert q.pick_table(con, SOURCES["ppa"], 2026, True) == ("stg.ppa_games_ngt", True, None)
        assert q.pick_table(con, SOURCES["havoc"], 2026, True) == ("stg.game_havoc_stats", False, None)


def test_unit_rows_flip_defense_direction_and_rank_within_the_window(client):
    units = client.get("/api/matchup?a=1&b=2&season=2026&week=4").get_json()["sections"]["units"]
    assert units["sources"]["advanced"]["ngt_lag"] == 1
    a_off = units["blocks"][0]
    assert (a_off["off"], a_off["def"]) == (1, 2)
    stuff = next(r for g in a_off["groups"] for r in g["rows"] if r["concept"] == "stuff")["options"][0]
    sr = next(r for g in a_off["groups"] for r in g["rows"] if r["concept"] == "sr")
    assert [o["key"] for o in sr["options"]] == ["sr", "sr_std", "sr_pass_downs"]
    assert sr["options"][0]["a"]["games"] == 2 and sr["options"][0]["a"]["n"] == 3  # 3 FBS teams played
    assert stuff["estimate"] is None and "prior" in stuff


def test_snapshot_needs_a_kickoff_within_three_days():
    lines = {"games": {frozenset({"Alpha", "Beta"}): {"commence_time": "2026-09-26T23:30:00Z", "books": {}}}}
    assert q.snap_game(lines, "Alpha", "Beta", "2026-09-26T19:30:00-04:00")
    assert q.snap_game(lines, "Beta", "Alpha", "2025-10-11T12:00:00-04:00") is None  # same pair, other season


def test_game_card_is_the_next_meeting_not_one_inside_the_window(warehouse):
    with q.warehouse(warehouse) as con:
        assert q.find_game(con, 2026, 1, 2, q.first_kickoff(con, 2026, 4)) == 104
        assert q.find_game(con, 2026, 1, 3, q.first_kickoff(con, 2026, 4)) is None  # met in wk2
        assert q.find_game(con, 2026, 1, 2, None) == 104  # full season: the last meeting


def _pff_off(con, week, fcs=True, full=False):
    from cfb_system_maker.matchup.stats import PFF_OVERALL_O
    cutoff = None if full else q.first_kickoff(con, 2026, week)
    return q.pff_team(con, [PFF_OVERALL_O], 2026, cutoff, full=full, rollup="pooled", fcs=fcs)


def test_pff_weeks_map_to_games_and_cut_on_kickoff(warehouse):
    with q.warehouse(warehouse) as con:
        wk4, wk4_fcs = _pff_off(con, 4), _pff_off(con, 4, fcs=False)
        wk1, wk2 = _pff_off(con, 1, fcs=False), _pff_off(con, 2)
        wk2_fcs = _pff_off(con, 2, fcs=False)
    assert wk4[1]["pff_off"] == pytest.approx((60 * 30 + 70 * 10) / 40)  # wk1 vs FCS Delta out
    assert wk4_fcs[1]["pff_off"] == pytest.approx((900 + 1800 + 700) / 50)
    assert 2 not in wk1  # Beta's PFF week 0 is CFBD week 1: nothing before week 1's first kickoff
    assert wk2[2] == {"n": 1, "pff_off": 80.0}  # week 0 was the FCS game
    assert wk2_fcs[2]["pff_off"] == pytest.approx(65.0)


def test_players_are_windowed_and_named(warehouse):
    with q.warehouse(warehouse) as con:
        pl = q.players(con, 2026, 4, q.first_kickoff(con, 2026, 4), 1, 2, full=False, fcs=True, ngt=True)
    (qb,) = pl["1"]["pff"]["QB"]["players"]
    assert (qb["player"], qb["volume"], qb["grade"]) == ("Al QB", 30.0, 75.0)
    assert qb["extra"] == pytest.approx(0.2)  # EPA per dropback
    (cf,) = pl["1"]["cfbd"]["QB"]
    assert cf["games"] == 1 and cf["ppa_pass"] == pytest.approx(0.5)  # the FCS game is out


def test_special_teams_paar_is_prior_season_as_of(warehouse):
    with q.warehouse(warehouse) as con:
        cutoff = q.first_kickoff(con, 2026, 4)
        st = q.special_teams(con, 2026, 4, cutoff, 1, 2, full=False, rollup="pooled", fcs=True,
                             show_postgame=True)
    fg = next(r for r in st["rows"] if r["key"] == "st_fg")
    assert fg["a"]["value"] == pytest.approx(70.0) and fg["a"]["games"] == 1
    assert st["paar_basis"] == "prior_season" and st["paar"][0]["a"]["value"] == 1.5
    assert st["postgame"][0]["a"]["value"] == 3.0


def test_schedule_blanks_games_at_or_after_the_cutoff(warehouse):
    with q.warehouse(warehouse) as con:
        games = q.schedule(con, 1, 2026, q.first_kickoff(con, 2026, 3), full=False)
    by_id = {g["game_id"]: g for g in games}
    assert by_id[102]["past"] and by_id[102]["result"]["su"] == "L"
    assert not by_id[103]["past"] and by_id[103]["pts"] is None and by_id[103]["spread"] is None


def test_betting_profile_against_the_closing_consensus(warehouse):
    # Closing home spread is -3.25 and total 51.25 on every fixture game.
    with q.warehouse(warehouse) as con:
        prof = q.betting_profile(q.schedule(con, 1, 2026, q.first_kickoff(con, 2026, 4), full=False))
    assert prof["all"]["su"] == [2, 1, 0] and prof["all"]["ats"] == [2, 1, 0] and prof["all"]["ou"] == [0, 3, 0]
    splits = dict(prof["splits"])
    assert splits["Underdog"]["n"] == 1  # the wk3 road game at +3.25
    assert splits["vs FBS"]["n"] == 2


def test_common_opponents_and_head_to_head(warehouse):
    with q.warehouse(warehouse) as con:
        cutoff = q.first_kickoff(con, 2026, 4)
        sa, sb = q.schedule(con, 1, 2026, cutoff, full=False), q.schedule(con, 2, 2026, cutoff, full=False)
        h = q.head_to_head(con, 1, 2, cutoff, full=False, season=2026)
    assert [c["opp"] for c in q.common_opponents(sa, sb, 1, 2)] == ["Delta", "Gamma"]
    assert h["n"] == 2 and h["series"] == {"a": 1, "b": 1, "t": 0} and h["first"] == 1999
    latest = h["games"][0]
    assert (latest["season"], latest["a_points"], latest["b_points"], latest["a_ats"]) == (2026, 24, 21, "W")
    assert h["games"][1]["a_spread"] is None  # no lines before 2012


SECTIONS = {"game", "profile", "ratings", "units", "pff", "special_teams", "players", "h2h", "trends",
            "schedule", "betting"}


def _lookahead_rows(node, in_postgame=False):
    """Every stat row with a lookahead_only verdict, flagged by whether it sits in a postgame panel."""
    if isinstance(node, dict):
        if node.get("verdict") == "lookahead_only" and "a" in node:
            yield node, in_postgame
        for k, v in node.items():
            yield from _lookahead_rows(v, in_postgame or k == "postgame")
    elif isinstance(node, list):
        for v in node:
            yield from _lookahead_rows(v, in_postgame)


def test_every_section_arrives_and_lookahead_stays_in_postgame_panels(client):
    body = client.get("/api/matchup?a=1&b=2&season=2026&week=4&postgame=1").get_json()
    assert set(body["sections"]) == SECTIONS and body["model_signals"] is None
    found = list(_lookahead_rows(body["sections"]))
    assert found
    for row, in_postgame in found:
        assert in_postgame or row["season"] == 2025, f"{row['key']} shows {row['season']} outside a postgame panel"
    assert any(p for _, p in found)  # postgame=1 did add panels


def test_trends_stop_at_the_window(client):
    tr = client.get("/api/matchup?a=1&b=2&season=2026&week=3").get_json()["sections"]["trends"]
    assert [r["week"] for r in tr["teams"]["1"]["cfbd"]] == [2]  # wk1 vs FCS out, wk3 not yet played
    assert [r["week"] for r in tr["teams"]["1"]["pff"]["pff_offense"]] == [2]


def test_registry_verdicts_match_the_eligibility_audit():
    audit = Path(os.environ.get("CFB_DATA_ROOT", "")) / "processed" / "pregame_feature_eligibility.csv"
    if not audit.is_file():
        pytest.skip("eligibility audit CSV not built")
    with audit.open(newline="", encoding="utf-8") as fh:
        verdicts = {(r["table"], r["column"]): r["verdict"] for r in csv.DictReader(fh)}
    checks = [(s.key, s.table, s.column, s.verdict, s.reason) for s in ALL]
    checks += [(u.key, u.table, f"{side}_{u.stem}", u.verdict, u.reason)
               for u in UNITS for side in ("offense", "defense")]
    from cfb_system_maker.matchup.stats import KICKER_PAAR, PFF_METRICS, SPECIAL_TEAMS
    checks += [(m.key, m.table, m.column, m.verdict, m.reason) for m in PFF_METRICS + SPECIAL_TEAMS]
    checks += [(KICKER_PAAR.key, KICKER_PAAR.table, KICKER_PAAR.column, KICKER_PAAR.verdict, KICKER_PAAR.reason)]
    for key, table, column, verdict, reason in checks:
        audited = verdicts.get((table, column))
        if audited is None:
            assert reason, f"{key}: the audit does not cover {table}.{column}; say why"
        else:
            assert verdict == audited, f"{key}: registry {verdict}, audit {audited} for {table}.{column}"
