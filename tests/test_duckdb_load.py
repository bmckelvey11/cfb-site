import json

from cfb_system_maker.cli import main
from cfb_system_maker.duckdb_load import build_duckdb, explode_payloads, flatten_stg_nested, parse_dump_stem


def test_parse_dump_stem_splits_season_and_week():
    assert parse_dump_stem("games_2023") == ("games", 2023, None, None)
    assert parse_dump_stem("plays_2023_wk1") == ("plays", 2023, 1, "regular")
    assert parse_dump_stem("conferences") == ("conferences", None, None, None)
    assert parse_dump_stem("gamePlayerStat_2012") == ("gamePlayerStat", 2012, None, None)


def test_parse_dump_stem_postseason_week():
    assert parse_dump_stem("game_team_stats_2024_post_wk1") == (
        "game_team_stats",
        2024,
        1,
        "postseason",
    )
    assert parse_dump_stem("ppa_players_games_ngt_2024_post_wk3") == (
        "ppa_players_games_ngt",
        2024,
        3,
        "postseason",
    )


def test_parse_dump_stem_keeps_non_year_numeric_suffix():
    assert parse_dump_stem("pff_facet_offense_summary_21580") == (
        "pff_facet_offense_summary_21580",
        None,
        None,
        None,
    )


def test_build_duckdb_loads_raw_and_graphql_payloads(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]),
        encoding="utf-8",
    )
    (raw / "plays_2023_wk1.json").write_text(
        json.dumps([{"id": 10, "playType": "rush"}]),
        encoding="utf-8",
    )
    (raw / "conferences.json").write_text(json.dumps([{"id": 9, "name": "SEC"}]), encoding="utf-8")
    (raw / "user_info.json").write_text(json.dumps([{"patronLevel": 2}]), encoding="utf-8")
    (raw / "pff_facet_offense_summary_21580.json").write_text(
        json.dumps({"gameId": 21580, "units": []}),
        encoding="utf-8",
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "game.json").write_text(json.dumps([{"id": 1, "season": 2023}]), encoding="utf-8")
    (gql / "gamePlayerStat_2012.json").write_text(
        json.dumps([{"id": 99, "athleteId": 7}]),
        encoding="utf-8",
    )

    db_path, reports = build_duckdb(tmp_path, include_actionnetwork=False)

    assert db_path == tmp_path / "cfb.duckdb"
    assert db_path.exists()
    by_name = {(r.schema, r.name): r for r in reports}
    assert "user_info" not in {r.name for r in reports}
    assert by_name[("raw", "games")].rows == 2
    assert by_name[("raw", "plays")].rows == 1
    assert by_name[("graphql", "gamePlayerStat")].rows == 1
    assert by_name[("raw", "pff_facet_offense_summary_21580")].rows == 1

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    home = con.execute("SELECT json_extract_string(payload, '$.homeTeam') FROM raw.games WHERE season = 2023 ORDER BY json_extract(payload, '$.id')").fetchall()
    assert home == [("A",), ("B",)]
    week = con.execute("SELECT week FROM raw.plays").fetchone()[0]
    assert week == 1
    assert con.execute("SELECT season_type FROM raw.plays").fetchone()[0] == "regular"
    assert con.execute("SELECT season FROM graphql.\"gamePlayerStat\"").fetchone()[0] == 2012
    assert con.execute("SELECT COUNT(*) FROM meta.load_report").fetchone()[0] == 6


def test_build_duckdb_groups_postseason_week_into_same_table(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "game_team_stats_2024_wk1.json").write_text(
        json.dumps([{"id": 1, "team": "A"}]),
        encoding="utf-8",
    )
    (raw / "game_team_stats_2024_post_wk1.json").write_text(
        json.dumps([{"id": 2, "team": "B"}]),
        encoding="utf-8",
    )

    db_path, reports = build_duckdb(tmp_path, include_actionnetwork=False)
    by_name = {(r.schema, r.name): r for r in reports}
    assert ("raw", "game_team_stats") in by_name
    assert by_name[("raw", "game_team_stats")].rows == 2
    assert not any(r.name.startswith("game_team_stats_2024") for r in reports)

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    rows = con.execute(
        "SELECT season, week, season_type, json_extract_string(payload, '$.team') "
        "FROM raw.game_team_stats ORDER BY season_type, json_extract(payload, '$.id')"
    ).fetchall()
    assert rows == [
        (2024, 1, "postseason", "B"),
        (2024, 1, "regular", "A"),
    ]
    # No season filter silent-drop of bowls:
    assert con.execute("SELECT COUNT(*) FROM raw.game_team_stats WHERE season = 2024").fetchone()[0] == 2


def test_explode_payloads_writes_stg_columns(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]),
        encoding="utf-8",
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "game.json").write_text(json.dumps([{"id": 9, "season": 2023}]), encoding="utf-8")

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    reports = explode_payloads(db_path)
    by_name = {r.name: r for r in reports if r.error is None}
    assert by_name["games"].rows == 2
    assert by_name["game"].rows == 1

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    homes = con.execute("SELECT homeTeam FROM stg.games ORDER BY id").fetchall()
    assert homes == [("A",), ("B",)]
    assert con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0] == 2
    assert con.execute("SELECT id FROM stg.game").fetchone()[0] == 9
    cols = {row[0] for row in con.execute("DESCRIBE stg.games").fetchall()}
    assert "_season" not in cols and "_week" not in cols
    assert "_source_file" in cols


def test_explode_flattens_nested_objects_with_prefixes(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "ppa_games_2023.json").write_text(
        json.dumps(
            [
                {
                    "gameId": 1,
                    "team": "Alpha",
                    "offense": {"overall": 0.5, "passing": 0.1, "havoc": {"db": 0.2, "total": 0.3}},
                    "defense": {"overall": -0.2, "passing": -0.1, "havoc": {"db": 0.05, "total": 0.08}},
                }
            ]
        ),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    explode_payloads(db_path)

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    cols = {row[0] for row in con.execute("DESCRIBE stg.ppa_games").fetchall()}
    assert "offense" not in cols
    assert "defense" not in cols
    assert "offense_overall" in cols
    assert "defense_overall" in cols
    assert "offense_havoc_db" in cols
    row = con.execute(
        "SELECT offense_overall, defense_overall, offense_havoc_db, defense_passing FROM stg.ppa_games"
    ).fetchone()
    assert row == (0.5, -0.2, 0.2, -0.1)


def test_explode_does_not_explode_arrays_into_rows(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A", "homeLineScores": [7, 14, 0, 7]}]),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    explode_payloads(db_path)

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM stg.games").fetchone()[0] == 1
    scores = con.execute("SELECT homeLineScores FROM stg.games").fetchone()[0]
    assert list(scores) == [7, 14, 0, 7]


def test_flatten_stg_nested_rewrites_existing_struct_columns(tmp_path):
    import duckdb

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.ppa_games AS
        SELECT
          'x.json' AS _source_file,
          1 AS gameId,
          {'overall': 0.5, 'passing': 0.1} AS offense,
          {'overall': -0.2, 'passing': -0.1} AS defense
        """
    )
    con.close()

    reports = flatten_stg_nested(db_path)
    by_name = {r.name: r for r in reports}
    assert by_name["ppa_games"].rows == 1
    assert by_name["ppa_games"].error is None

    con = duckdb.connect(str(db_path), read_only=True)
    cols = {row[0] for row in con.execute("DESCRIBE stg.ppa_games").fetchall()}
    assert "offense" not in cols
    assert cols >= {"_source_file", "gameId", "offense_overall", "defense_overall"}
    row = con.execute("SELECT offense_overall, defense_overall FROM stg.ppa_games").fetchone()
    assert tuple(float(v) for v in row) == (0.5, -0.2)


def test_flatten_stg_nested_keeps_walking_structs_that_contain_lists(tmp_path):
    import duckdb

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.hist AS
        SELECT
          {'firsthalf': {'moneyline': {'odds': 100, 'history': [NULL]}}} AS "15"
        """
    )
    con.close()

    flatten_stg_nested(db_path)

    con = duckdb.connect(str(db_path), read_only=True)
    cols = {row[0] for row in con.execute("DESCRIBE stg.hist").fetchall()}
    assert "15" not in cols
    assert any(name.endswith("odds") for name in cols)
    leftover_structs = [
        row[0]
        for row in con.execute("DESCRIBE stg.hist").fetchall()
        if str(row[1]).upper().startswith("STRUCT") and not str(row[1]).upper().endswith("[]")
    ]
    assert leftover_structs == []
    assert con.execute("SELECT COUNT(*) FROM stg.hist").fetchone()[0] == 1


def test_duckdb_cli_writes_db(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "venues.json").write_text(json.dumps([{"id": 1, "name": "Stadium"}]), encoding="utf-8")

    assert main(["duckdb", "--data-dir", str(tmp_path), "--skip-actionnetwork"]) == 0
    out = capsys.readouterr().out
    assert "raw.venues" in out
    assert (tmp_path / "cfb.duckdb").exists()
