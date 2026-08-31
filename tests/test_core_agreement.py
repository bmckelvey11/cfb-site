"""Dual-SoT agreement: core facts vs games.csv / normalize / running_stats (Phase 1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from cfb_system_maker.cli import main
from cfb_system_maker.duckdb_core import build_core
from cfb_system_maker.enrich import _build_line_move_index
from cfb_system_maker.models import GameRecord
from cfb_system_maker.normalize import _select_line, _select_total, normalize_games
from cfb_system_maker.running_stats import compute_running_stats
from cfb_system_maker.storage import load_processed_games, save_processed_games


def _seed_phase_1a_warehouse(db: Path) -> None:
    """Minimal raw/stg so build_core can run without a full scrape."""
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    con.execute("CREATE SCHEMA raw")
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE raw.teams (
          season INTEGER, week INTEGER, season_type VARCHAR, payload JSON
        )
        """
    )
    con.execute(
        """
        CREATE TABLE raw.fbs_teams (
          season INTEGER, week INTEGER, season_type VARCHAR, payload JSON
        )
        """
    )

    teams = [
        {"id": 1, "school": "Alpha", "abbreviation": "ALP", "classification": "fbs"},
        {"id": 2, "school": "Beta", "abbreviation": "BET", "classification": "fbs"},
        {"id": 3, "school": "Gamma", "abbreviation": "GAM", "classification": "fcs"},
    ]
    for season in (2023, 2024):
        for team in teams:
            payload = json.dumps(team)
            con.execute(
                "INSERT INTO raw.teams (season, payload) VALUES (?, ?::JSON)",
                [season, payload],
            )
            if team["classification"] == "fbs":
                con.execute(
                    "INSERT INTO raw.fbs_teams (season, payload) VALUES (?, ?::JSON)",
                    [season, payload],
                )

    con.execute(
        """
        CREATE TABLE stg.conferences (
          conferenceId INTEGER, name VARCHAR, abbreviation VARCHAR,
          shortName VARCHAR, classification VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO stg.conferences VALUES (10, 'SEC', 'SEC', 'SEC', 'fbs')"
    )

    con.execute(
        """
        CREATE TABLE stg.venues (
          venueId INTEGER, name VARCHAR, city VARCHAR, state VARCHAR,
          dome BOOLEAN, grass BOOLEAN, capacity INTEGER, elevation VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO stg.venues VALUES (100, 'Stadium', 'Town', 'TX', false, true, 50000, '100.5')"
    )

    con.execute(
        """
        CREATE TABLE stg.calendar (
          season INTEGER, week INTEGER, seasonType VARCHAR,
          startDate VARCHAR, endDate VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.calendar VALUES
          (2023, 1, 'regular', '2023-08-26', '2023-09-01'),
          (2023, 1, 'postseason', '2023-12-15', '2023-12-22')
        """
    )

    line_struct = (
        "STRUCT(awayMoneyline HUGEINT, formattedSpread VARCHAR, homeMoneyline HUGEINT, "
        "overUnder DOUBLE, overUnderOpen DOUBLE, provider VARCHAR, spread DOUBLE, spreadOpen DOUBLE)[]"
    )
    con.execute(
        f"""
        CREATE TABLE stg.lines (
          gameId INTEGER,
          lines {line_struct}
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.lines VALUES (
          1,
          [
            {'awayMoneyline': NULL, 'formattedSpread': NULL, 'homeMoneyline': NULL,
             'overUnder': NULL, 'overUnderOpen': NULL, 'provider': 'teamrankings',
             'spread': -3.0, 'spreadOpen': NULL},
            {'awayMoneyline': -110, 'formattedSpread': 'Alpha -7', 'homeMoneyline': -280,
             'overUnder': 55.5, 'overUnderOpen': 54.0, 'provider': 'consensus',
             'spread': -7.0, 'spreadOpen': -6.5},
            {'awayMoneyline': NULL, 'formattedSpread': NULL, 'homeMoneyline': NULL,
             'overUnder': 54.0, 'overUnderOpen': NULL, 'provider': 'bovada',
             'spread': NULL, 'spreadOpen': NULL}
          ]
        )
        """
    )
    con.execute("INSERT INTO stg.lines VALUES (2, [])")
    con.execute(
        """
        INSERT INTO stg.lines VALUES (
          3,
          [
            {'awayMoneyline': NULL, 'formattedSpread': NULL, 'homeMoneyline': NULL,
             'overUnder': 48.0, 'overUnderOpen': NULL, 'provider': 'consensus',
             'spread': -2.5, 'spreadOpen': NULL}
          ]
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.lines VALUES (
          4,
          [
            {'awayMoneyline': NULL, 'formattedSpread': NULL, 'homeMoneyline': NULL,
             'overUnder': 50.0, 'overUnderOpen': 49.5, 'provider': 'consensus',
             'spread': -3.5, 'spreadOpen': -3.0}
          ]
        )
        """
    )

    con.execute(
        """
        CREATE TABLE stg.games (
          gameId INTEGER, season INTEGER, week INTEGER, seasonType VARCHAR,
          startDate VARCHAR, completed BOOLEAN, venueId INTEGER,
          homeTeamId INTEGER, awayTeamId INTEGER, homeTeam VARCHAR, awayTeam VARCHAR,
          homeConference VARCHAR, awayConference VARCHAR,
          homePoints INTEGER, awayPoints INTEGER
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.games VALUES
          (1, 2023, 1, 'regular', '2023-09-02T19:00:00.000Z', true, 100,
           1, 2, 'Alpha', 'Beta', 'SEC', 'SEC', 28, 14),
          (2, 2023, 1, 'regular', '2023-09-02T20:00:00.000Z', true, 100,
           1, 3, 'Alpha', 'Gamma', 'SEC', NULL, 35, 10),
          (4, 2023, 12, 'regular', '2023-11-25T17:00:00.000Z', true, 100,
           1, 2, 'Alpha', 'Beta', 'SEC', 'SEC', 31, 28),
          (3, 2023, 1, 'postseason', '2024-01-01T20:00:00.000Z', true, 100,
           1, 2, 'Alpha', 'Beta', 'SEC', 'SEC', 21, 17)
        """
    )
    con.close()


def _csv_from_same_inputs(data_dir: Path):
    games = [
        {
            "id": 1,
            "season": 2023,
            "week": 1,
            "seasonType": "regular",
            "homeTeam": "Alpha",
            "awayTeam": "Beta",
            "homeConference": "SEC",
            "awayConference": "SEC",
            "homePoints": 28,
            "awayPoints": 14,
        },
        {
            "id": 4,
            "season": 2023,
            "week": 12,
            "seasonType": "regular",
            "homeTeam": "Alpha",
            "awayTeam": "Beta",
            "homeConference": "SEC",
            "awayConference": "SEC",
            "homePoints": 31,
            "awayPoints": 28,
        },
        {
            "id": 3,
            "season": 2023,
            "week": 1,
            "seasonType": "postseason",
            "homeTeam": "Alpha",
            "awayTeam": "Beta",
            "homeConference": "SEC",
            "awayConference": "SEC",
            "homePoints": 21,
            "awayPoints": 17,
        },
    ]
    lines = [
        {
            "id": 1,
            "lines": [
                {"provider": "teamrankings", "spread": -3.0},
                {
                    "provider": "consensus",
                    "spread": -7.0,
                    "spreadOpen": -6.5,
                    "overUnder": 55.5,
                    "overUnderOpen": 54.0,
                    "homeMoneyline": -280,
                    "awayMoneyline": -110,
                    "formattedSpread": "Alpha -7",
                },
                {"provider": "bovada", "overUnder": 54.0},
            ],
        },
        {
            "id": 4,
            "lines": [
                {
                    "provider": "consensus",
                    "spread": -3.5,
                    "spreadOpen": -3.0,
                    "overUnder": 50.0,
                    "overUnderOpen": 49.5,
                }
            ],
        },
        {
            "id": 3,
            "lines": [{"provider": "consensus", "spread": -2.5, "overUnder": 48.0}],
        },
    ]
    records = normalize_games(games, lines, provider="consensus")
    save_processed_games(data_dir, records)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines), encoding="utf-8")
    return records


@pytest.fixture()
def phase_1a_env(tmp_path: Path):
    db = tmp_path / "cfb.duckdb"
    _seed_phase_1a_warehouse(db)
    records = _csv_from_same_inputs(tmp_path)
    built = build_core(db, provider="consensus")
    assert "fact_game" in built
    assert "fact_game_line" in built
    assert "fact_game_team" in built
    return tmp_path, db, records


def test_agreement_1_has_line_coverage_matches_csv(phase_1a_env):
    data_dir, db, records = phase_1a_env
    csv_ids = {g.game_id for g in load_processed_games(data_dir)}
    con = duckdb.connect(str(db), read_only=True)
    lined = {
        r[0]
        for r in con.execute(
            "SELECT game_id FROM core.fact_game WHERE has_line"
        ).fetchall()
    }
    assert lined == csv_ids
    assert len(lined) == len(records)


def test_agreement_2_identity_columns(phase_1a_env):
    data_dir, db, _records = phase_1a_env
    csv_games = {g.game_id: g for g in load_processed_games(data_dir)}
    con = duckdb.connect(str(db), read_only=True)
    rows = con.execute(
        """
        SELECT game_id, season, week, season_type, home_team, away_team,
               home_points, away_points, selected_spread_provider_key,
               selected_spread, selected_total
        FROM core.fact_game
        WHERE has_line
        """
    ).fetchall()
    assert len(rows) == len(csv_games)
    for (
        game_id,
        season,
        week,
        season_type,
        home_team,
        away_team,
        home_points,
        away_points,
        provider_key,
        spread,
        total,
    ) in rows:
        g = csv_games[game_id]
        assert season == g.season
        assert week == g.week
        assert season_type == g.season_type
        assert home_team == g.home_team
        assert away_team == g.away_team
        assert home_points == g.home_points
        assert away_points == g.away_points
        assert provider_key == (g.provider or "").strip().lower()
        assert spread == g.spread
        assert total == g.total


def test_agreement_3_provider_clone_split_book_total():
    lines = [
        {"provider": "teamrankings", "spread": -3.0},
        {"provider": "consensus", "spread": -7.0, "overUnder": 55.5},
        {"provider": "bovada", "overUnder": 54.0},
    ]
    selected = _select_line(lines, "consensus")
    assert selected is not None
    assert selected["provider"] == "consensus"
    assert selected["spread"] == -7.0
    total_row = _select_total(lines, selected)
    assert total_row["provider"] == "consensus"
    assert total_row["overUnder"] == 55.5

    lines_split = [
        {"provider": "consensus", "spread": -7.0},
        {"provider": "bovada", "overUnder": 54.0},
    ]
    selected = _select_line(lines_split, "consensus")
    total_row = _select_total(lines_split, selected)
    assert total_row["provider"] == "bovada"
    assert total_row["overUnder"] == 54.0


def test_agreement_4_line_move_matches_enrich_index(phase_1a_env):
    data_dir, db, records = phase_1a_env
    index = _build_line_move_index(data_dir, [2023], records)
    assert 1 in index
    assert index[1]["spread_open"] == -6.5
    assert index[1]["total_open"] == 54.0
    assert index[1]["spread_move"] == pytest.approx(-0.5)
    assert index[1]["total_move"] == pytest.approx(1.5)
    # Null open on game 3 → enrich still indexes the game with null opens
    assert 3 in index
    assert index[3]["spread_open"] is None
    assert index[3]["total_open"] is None

    by_id = {g.game_id: g for g in records}
    con = duckdb.connect(str(db), read_only=True)
    for game_id, moves in index.items():
        game = by_id[game_id]
        provider_key = (game.provider or "").strip().lower()
        row = con.execute(
            """
            SELECT spread_close, spread_open
            FROM core.fact_game_line
            WHERE game_id = ? AND provider_key = ?
            """,
            [game_id, provider_key],
        ).fetchone()
        assert row is not None, f"missing fact_game_line for {game_id}/{provider_key}"
        spread_close, spread_open = row
        assert spread_close == game.spread
        assert spread_open == moves["spread_open"]
        if spread_open is None:
            assert moves["spread_move"] is None
        else:
            assert moves["spread_move"] == pytest.approx(game.spread - spread_open)

        # Totals may be split-book — match selected_total_provider_key row
        total_provider = con.execute(
            """
            SELECT selected_total_provider_key FROM core.fact_game WHERE game_id = ?
            """,
            [game_id],
        ).fetchone()[0]
        assert total_provider is not None
        total_row = con.execute(
            """
            SELECT total_close, total_open
            FROM core.fact_game_line
            WHERE game_id = ? AND provider_key = ?
            """,
            [game_id, total_provider],
        ).fetchone()
        assert total_row is not None
        total_close, total_open = total_row
        assert total_close == game.total
        assert total_open == moves["total_open"]
        if total_open is None:
            assert moves["total_move"] is None
        else:
            assert moves["total_move"] == pytest.approx(game.total - total_open)

    # Full tape includes non-selected books; opens stay null (fail-closed)
    providers = {
        r[0]
        for r in con.execute(
            "SELECT provider_key FROM core.fact_game_line WHERE game_id = 1"
        ).fetchall()
    }
    assert providers == {"teamrankings", "consensus", "bovada"}
    dim = {
        r[0]
        for r in con.execute("SELECT provider_key FROM core.dim_lines_provider").fetchall()
    }
    assert providers <= dim


def test_agreement_5_entering_game_matches_running_stats(phase_1a_env):
    _data_dir, db, _records = phase_1a_env
    con = duckdb.connect(str(db), read_only=True)
    rows = con.execute(
        """
        SELECT
          game_id, season, week, season_type, start_date,
          home_team_id, away_team_id, home_team, away_team,
          home_conference, away_conference, home_points, away_points,
          selected_spread_provider_key, selected_spread, selected_total
        FROM core.fact_game
        """
    ).fetchall()
    games = []
    start_dates: dict[int, str] = {}
    for row in rows:
        gid = int(row[0])
        games.append(
            GameRecord(
                game_id=gid,
                season=int(row[1]),
                week=int(row[2]),
                home_team=str(row[7]),
                away_team=str(row[8]),
                home_conference=row[9],
                away_conference=row[10],
                home_points=int(row[11]) if row[11] is not None else None,
                away_points=int(row[12]) if row[12] is not None else None,
                provider=row[13],
                spread=row[14],
                total=row[15],
                season_type=str(row[3]),
            )
        )
        if row[4] is not None:
            start_dates[gid] = str(row[4])

    expected = compute_running_stats(games, start_dates=start_dates)
    sql_rows = con.execute(
        """
        SELECT f.game_id, t.school, f.home_away, f.games_played,
               f.win_pct, f.ats_pct, f.streak, f.ats_streak
        FROM core.fact_game_team f
        JOIN core.dim_team t ON t.team_id = f.team_id
        """
    ).fetchall()
    assert len(sql_rows) == len(expected) == 8  # 4 games × 2 teams
    for game_id, school, home_away, gp, win_pct, ats_pct, streak, ats_streak in sql_rows:
        exp = expected[(game_id, school)]
        assert gp == exp["games_played"]
        assert win_pct == exp["win_pct"]
        assert ats_pct == exp["ats_pct"]
        assert streak == exp["streak"]
        assert ats_streak == exp["ats_streak"]
        # First game of season for Alpha (earliest start_date)
        if game_id == 1 and school == "Alpha":
            assert home_away == "home"
            assert gp == 0
            assert win_pct is None
            assert ats_pct is None


def test_agreement_6_bowl_lookahead_tripwire(phase_1a_env):
    """Adding bowls must not change regular-season entering games_played."""
    _data_dir, db, _records = phase_1a_env
    con = duckdb.connect(str(db), read_only=True)
    rows = con.execute(
        """
        SELECT
          game_id, season, week, season_type, start_date,
          home_team, away_team, home_points, away_points,
          selected_spread_provider_key, selected_spread, selected_total
        FROM core.fact_game
        """
    ).fetchall()
    all_games = []
    start_dates: dict[int, str] = {}
    for row in rows:
        gid = int(row[0])
        all_games.append(
            GameRecord(
                game_id=gid,
                season=int(row[1]),
                week=int(row[2]),
                home_team=str(row[5]),
                away_team=str(row[6]),
                home_conference=None,
                away_conference=None,
                home_points=int(row[7]) if row[7] is not None else None,
                away_points=int(row[8]) if row[8] is not None else None,
                provider=row[9],
                spread=row[10],
                total=row[11],
                season_type=str(row[3]),
            )
        )
        if row[4] is not None:
            start_dates[gid] = str(row[4])

    regular = [g for g in all_games if g.season_type == "regular"]
    with_bowls = [
        g for g in all_games if g.season_type in ("regular", "postseason")
    ]
    stats_regular = compute_running_stats(regular, start_dates=start_dates)
    stats_with_bowls = compute_running_stats(with_bowls, start_dates=start_dates)
    for key, measures in stats_regular.items():
        assert stats_with_bowls[key]["games_played"] == measures["games_played"], key

    # Week-12 slate sees 2 prior regulars, not the bowl (week=1 would sort first)
    sql_gp = con.execute(
        """
        SELECT games_played FROM core.fact_game_team
        WHERE game_id = 4 AND home_away = 'home'
        """
    ).fetchone()[0]
    assert sql_gp == 2
    bowl_gp = con.execute(
        """
        SELECT games_played FROM core.fact_game_team
        WHERE game_id = 3 AND home_away = 'home'
        """
    ).fetchone()[0]
    assert bowl_gp == 3  # inherits all three regulars


def test_agreement_7_postseason_week_requires_season_type(phase_1a_env):
    _data_dir, db, _records = phase_1a_env
    con = duckdb.connect(str(db), read_only=True)
    post_w1 = con.execute(
        """
        SELECT COUNT(*) FROM core.fact_game
        WHERE week = 1 AND season_type = 'postseason' AND has_line
        """
    ).fetchone()[0]
    bare_w1 = con.execute(
        "SELECT COUNT(*) FROM core.fact_game WHERE week = 1 AND has_line"
    ).fetchone()[0]
    assert post_w1 == 1
    assert bare_w1 == 2
    assert bare_w1 != post_w1


def test_cli_core_only(tmp_path: Path):
    db = tmp_path / "cfb.duckdb"
    _seed_phase_1a_warehouse(db)
    assert main(["duckdb", "--data-dir", str(tmp_path), "--core-only"]) == 0
    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM core.fact_game").fetchone()[0] == 4
    assert con.execute("SELECT COUNT(*) FROM core.fact_game WHERE has_line").fetchone()[0] == 3
    assert con.execute("SELECT COUNT(*) FROM core.fact_game_line").fetchone()[0] == 5
    assert con.execute("SELECT COUNT(*) FROM core.fact_game_team").fetchone()[0] == 8
    providers = {
        r[0]
        for r in con.execute("SELECT provider_key FROM core.dim_lines_provider").fetchall()
    }
    assert {"consensus", "teamrankings", "bovada"} <= providers


@pytest.mark.slow
def test_live_warehouse_agreement_1_2_7():
    """Against $CFB_DATA_ROOT when core.fact_game already built.

    Scope: seasons present in games.csv. Forward-season open books (e.g. 2026)
    may sit on has_line without a CSV row — that is expected, not drift.
    """
    root = Path(os.environ.get("CFB_DATA_ROOT", ""))
    db = root / "cfb.duckdb"
    csv_path = root / "processed" / "games.csv"
    if not db.exists() or not csv_path.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    con = duckdb.connect(str(db), read_only=True)
    try:
        con.execute("SELECT 1 FROM core.fact_game LIMIT 1")
    except duckdb.CatalogException:
        pytest.skip("core.fact_game not built yet")

    games = load_processed_games(root)
    csv_ids = {g.game_id for g in games}
    csv_seasons = {g.season for g in games}
    lined = {
        r[0]
        for r in con.execute(
            """
            SELECT game_id FROM core.fact_game
            WHERE has_line AND season IN (SELECT UNNEST(?))
            """,
            [list(csv_seasons)],
        ).fetchall()
    }
    only_csv = sorted(csv_ids - lined)
    only_sql = sorted(lined - csv_ids)
    assert not only_csv and not only_sql, (
        f"coverage drift: csv_only={only_csv[:10]} sql_only={only_sql[:10]} "
        f"({len(only_csv)}/{len(only_sql)})"
    )

    by_id = {g.game_id: g for g in games}
    rows = con.execute(
        """
        SELECT game_id, season, week, season_type, home_team, away_team,
               home_points, away_points, selected_spread_provider_key,
               selected_spread, selected_total
        FROM core.fact_game
        WHERE has_line AND season IN (SELECT UNNEST(?))
        """,
        [list(csv_seasons)],
    ).fetchall()
    for row in rows:
        g = by_id[row[0]]
        assert row[1] == g.season
        assert row[2] == g.week
        assert row[3] == g.season_type
        assert row[4] == g.home_team
        assert row[5] == g.away_team
        assert row[6] == g.home_points
        assert row[7] == g.away_points
        assert row[8] == (g.provider or "").strip().lower()
        assert row[9] == g.spread
        assert row[10] == g.total

    post_sql = con.execute(
        """
        SELECT COUNT(*) FROM core.fact_game
        WHERE week = 1 AND season_type = 'postseason' AND has_line
          AND season IN (SELECT UNNEST(?))
        """,
        [list(csv_seasons)],
    ).fetchone()[0]
    post_csv = sum(1 for g in games if g.week == 1 and g.season_type == "postseason")
    assert post_sql == post_csv
    bare = con.execute(
        """
        SELECT COUNT(*) FROM core.fact_game
        WHERE week = 1 AND has_line AND season IN (SELECT UNNEST(?))
        """,
        [list(csv_seasons)],
    ).fetchone()[0]
    assert bare != post_sql


@pytest.mark.slow
def test_live_warehouse_agreement_4_5_6():
    """Line-move + entering-game agreement against live CFB_DATA_ROOT core tables."""
    root = Path(os.environ.get("CFB_DATA_ROOT", ""))
    db = root / "cfb.duckdb"
    csv_path = root / "processed" / "games.csv"
    if not db.exists() or not csv_path.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    con = duckdb.connect(str(db), read_only=True)
    try:
        con.execute("SELECT 1 FROM core.fact_game_line LIMIT 1")
        con.execute("SELECT 1 FROM core.fact_game_team LIMIT 1")
    except duckdb.CatalogException:
        pytest.skip("core.fact_game_line / fact_game_team not built yet")

    games = load_processed_games(root)
    seasons = sorted({g.season for g in games})
    index = _build_line_move_index(root, seasons, games)
    assert index, "expected some line-move rows from raw lines_*"
    checked_lines = 0
    for game in games:
        moves = index.get(game.game_id)
        if moves is None:
            continue
        provider_key = (game.provider or "").strip().lower()
        row = con.execute(
            """
            SELECT spread_close, spread_open
            FROM core.fact_game_line
            WHERE game_id = ? AND provider_key = ?
            """,
            [game.game_id, provider_key],
        ).fetchone()
        assert row is not None, f"missing line row {game.game_id}/{provider_key}"
        assert row[0] == game.spread
        assert row[1] == moves["spread_open"]
        total_provider = con.execute(
            """
            SELECT selected_total_provider_key FROM core.fact_game WHERE game_id = ?
            """,
            [game.game_id],
        ).fetchone()[0]
        total_row = con.execute(
            """
            SELECT total_close, total_open
            FROM core.fact_game_line
            WHERE game_id = ? AND provider_key = ?
            """,
            [game.game_id, total_provider],
        ).fetchone()
        assert total_row is not None, f"missing total book {game.game_id}/{total_provider}"
        assert total_row[0] == game.total
        assert total_row[1] == moves["total_open"]
        checked_lines += 1
    assert checked_lines >= 20

    # Entering-game: expected from the same universe as the loader (all fact_game)
    fact_rows = con.execute(
        """
        SELECT
          game_id, season, week, season_type, CAST(start_date AS VARCHAR),
          home_team, away_team, home_points, away_points,
          selected_spread_provider_key, selected_spread, selected_total
        FROM core.fact_game
        WHERE season IN (SELECT UNNEST(?))
        """,
        [list(seasons)],
    ).fetchall()
    fact_games: list[GameRecord] = []
    start_dates: dict[int, str] = {}
    for row in fact_rows:
        gid = int(row[0])
        fact_games.append(
            GameRecord(
                game_id=gid,
                season=int(row[1]),
                week=int(row[2]),
                home_team=str(row[5]),
                away_team=str(row[6]),
                home_conference=None,
                away_conference=None,
                home_points=int(row[7]) if row[7] is not None else None,
                away_points=int(row[8]) if row[8] is not None else None,
                provider=row[9],
                spread=row[10],
                total=row[11],
                season_type=str(row[3]),
            )
        )
        if row[4] is not None:
            start_dates[gid] = str(row[4])

    expected = compute_running_stats(fact_games, start_dates=start_dates)
    checked = 0
    for (game_id, team), measures in expected.items():
        if checked >= 300:
            break
        row = con.execute(
            """
            SELECT f.games_played, f.win_pct, f.ats_pct, f.streak, f.ats_streak
            FROM core.fact_game_team f
            JOIN core.dim_team t ON t.team_id = f.team_id
            WHERE f.game_id = ? AND t.school = ?
            """,
            [game_id, team],
        ).fetchone()
        if row is None:
            continue
        assert row[0] == measures["games_played"], (game_id, team)
        assert row[1] == measures["win_pct"]
        assert row[2] == measures["ats_pct"]
        assert row[3] == measures["streak"]
        assert row[4] == measures["ats_streak"]
        checked += 1
    assert checked >= 50

    regular = [g for g in fact_games if g.season_type == "regular"]
    with_bowls = [
        g for g in fact_games if g.season_type in ("regular", "postseason")
    ]
    stats_reg = compute_running_stats(regular, start_dates=start_dates)
    stats_bowls = compute_running_stats(with_bowls, start_dates=start_dates)
    by_id = {g.game_id: g for g in fact_games}
    # Skip team-seasons where a postseason row sorts before a regular row
    # (D3 playoff / duplicate labeling) — that is chronological, not lookahead.
    for (game_id, team), measures in stats_reg.items():
        game = by_id[game_id]
        game_sort = start_dates.get(game_id) or f"{game.season:04d}-w{game.week:02d}"
        earlier_bowl = False
        for g in with_bowls:
            if g.season_type != "postseason" or g.season != game.season:
                continue
            if team not in (g.home_team, g.away_team):
                continue
            bowl_sort = start_dates.get(g.game_id) or f"{g.season:04d}-w{g.week:02d}"
            if (bowl_sort, g.game_id) < (game_sort, game_id):
                earlier_bowl = True
                break
        if earlier_bowl:
            continue
        assert stats_bowls[(game_id, team)]["games_played"] == measures["games_played"], (
            game_id,
            team,
        )
