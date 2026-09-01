import json

from cfb_system_maker.cli import main
from cfb_system_maker.duckdb_load import (
    backfill_gamelines_from_actionnetwork,
    build_duckdb,
    explode_payloads,
    flatten_stg_nested,
    parse_dump_stem,
    rename_stg_id_columns,
    reorder_stg_columns,
    stg_column_order,
    stg_destination,
    stg_id_renames,
)


def test_stg_destination_resolves_graphql_raw_names_to_stg_gql():
    assert stg_destination("gql_calendar") == ("stg_gql", "calendar")
    assert stg_destination("gql_game_lines") == ("stg_gql", "game_lines")
    assert stg_destination("gql_draft_picks") == ("stg_gql", "draft_picks")


def test_stg_destination_passes_rest_names_through_to_stg():
    assert stg_destination("games") == ("stg", "games")
    assert stg_destination("draft_picks") == ("stg", "draft_picks")
    assert stg_destination("advanced_box_score") == ("stg", "advanced_box_score")


def test_gql_destinations_never_collide_with_rest_destinations_in_the_same_schema():
    from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW

    rest_raw_names = {"games", "coaches", "conferences", "draft_picks", "recruits",
                       "recruiting_teams", "coach_seasons", "predicted_points", "talent",
                       "lines", "calendar", "draft_positions", "draft_teams"}
    assert not (set(GQL_ENTITY_TO_RAW.values()) & rest_raw_names)


def test_parse_dump_stem_splits_season_and_week():
    assert parse_dump_stem("games_2023") == ("games", 2023, None, None)
    assert parse_dump_stem("plays_2023_wk1") == ("plays", 2023, 1, "regular")
    assert parse_dump_stem("conferences") == ("conferences", None, None, None)
    assert parse_dump_stem("gamePlayerStat_2012") == (
        "gamePlayerStat",
        2012,
        None,
        None,
    )


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
    (raw / "conferences.json").write_text(
        json.dumps([{"id": 9, "name": "SEC"}]), encoding="utf-8"
    )
    (raw / "user_info.json").write_text(
        json.dumps([{"patronLevel": 2}]), encoding="utf-8"
    )
    (raw / "pff_facet_offense_summary_21580.json").write_text(
        json.dumps({"gameId": 21580, "units": []}),
        encoding="utf-8",
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "game.json").write_text(
        json.dumps([{"id": 1, "season": 2023}]), encoding="utf-8"
    )
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
    assert by_name[("raw", "gamePlayerStat")].rows == 1
    assert by_name[("raw", "pff_facet_offense_summary_21580")].rows == 1
    assert "graphql" not in {r.schema for r in reports}

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    home = con.execute(
        "SELECT json_extract_string(payload, '$.homeTeam') FROM raw.games WHERE season = 2023 ORDER BY json_extract(payload, '$.id')"
    ).fetchall()
    assert home == [("A",), ("B",)]
    week = con.execute("SELECT week FROM raw.plays").fetchone()[0]
    assert week == 1
    assert con.execute("SELECT season_type FROM raw.plays").fetchone()[0] == "regular"
    assert con.execute('SELECT season FROM raw."gamePlayerStat"').fetchone()[0] == 2012
    assert con.execute("SELECT COUNT(*) FROM meta.load_report").fetchone()[0] == 6
    schemas = {
        row[0]
        for row in con.execute(
            "SELECT schema_name FROM duckdb_schemas() WHERE database_name = current_database()"
        ).fetchall()
    }
    assert "graphql" not in schemas


def test_build_duckdb_names_graphql_calendar_with_explicit_prefix(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "calendar_2023.json").write_text(
        json.dumps([{"season": 2023, "week": 1}]), encoding="utf-8"
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "calendar.json").write_text(
        json.dumps([{"season": 2023, "week": 9}]), encoding="utf-8"
    )

    db_path, reports = build_duckdb(tmp_path, include_actionnetwork=False)
    by_name = {(r.schema, r.name): r for r in reports}
    assert by_name[("raw", "calendar")].rows == 1
    assert by_name[("raw", "gql_calendar")].rows == 1

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    assert (
        con.execute(
            "SELECT json_extract_string(payload, '$.week') FROM raw.calendar"
        ).fetchone()[0]
        == "1"
    )
    assert (
        con.execute(
            "SELECT json_extract_string(payload, '$.week') FROM raw.gql_calendar"
        ).fetchone()[0]
        == "9"
    )


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
    assert (
        con.execute(
            "SELECT COUNT(*) FROM raw.game_team_stats WHERE season = 2024"
        ).fetchone()[0]
        == 2
    )


def test_explode_payloads_writes_stg_columns(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]),
        encoding="utf-8",
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "game.json").write_text(
        json.dumps([{"id": 9, "season": 2023}]), encoding="utf-8"
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    reports = explode_payloads(db_path)
    by_key = {(r.schema, r.name): r for r in reports if r.error is None}
    assert by_key[("stg", "games")].rows == 2
    assert by_key[("stg_gql", "game")].rows == 1

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    homes = con.execute("SELECT homeTeam FROM stg.games ORDER BY gameId").fetchall()
    assert homes == [("A",), ("B",)]
    assert con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0] == 2
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 9
    cols = {row[0] for row in con.execute("DESCRIBE stg.games").fetchall()}
    assert "_season" not in cols and "_week" not in cols
    assert "_source_file" in cols


def test_flatten_struct_columns_renames_and_reorders_in_the_stg_gql_schema(tmp_path):
    """`_flatten_struct_columns` (pre-existing, schema-parameterized) has two internal
    calls to `_rename_stg_table_ids`/`_reorder_stg_table` that must thread its own
    `schema` argument through rather than the old 2-arg form. A payload nested one
    level deep (as in `explode_payloads`) never reaches these lines: DuckDB's
    `unnest(..., recursive := true)` already flattens simple nested objects before
    `_flatten_struct_columns` ever sees a STRUCT column, so this constructs a STRUCT
    column directly the way `test_flatten_stg_nested_rewrites_existing_struct_columns`
    does, but in `stg_gql` to prove the schema argument is actually used."""
    import duckdb

    from cfb_system_maker.duckdb_load import _flatten_struct_columns

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg_gql")
    con.execute(
        """
        CREATE TABLE stg_gql.game AS
        SELECT
          9 AS id,
          2023 AS season,
          {'id': 5, 'name': 'X'} AS venue
        """
    )

    report = _flatten_struct_columns(con, "stg_gql", "game")
    assert report is not None and report.error is None

    cols = [row[0] for row in con.execute("DESCRIBE stg_gql.game").fetchall()]
    assert "venue" not in cols
    assert "venue_id" in cols and "venue_name" in cols
    assert cols[0] == "gameId"
    con.close()


def test_explode_payloads_only_skips_other_tables(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A"}]), encoding="utf-8"
    )
    (raw / "plays_2023_wk1.json").write_text(
        json.dumps([{"id": "10", "gameId": 1, "playType": "rush"}]),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    reports = explode_payloads(db_path, only={"plays"})
    assert [r.name for r in reports] == ["plays"]

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
        ).fetchall()
    }
    assert tables == {"plays"}
    assert con.execute(
        "SELECT season, week, season_type, playId FROM stg.plays"
    ).fetchone() == (
        2023,
        1,
        "regular",
        "10",
    )


def test_explode_plays_flattens_clock_and_keeps_filename_season(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "plays_2023_wk1.json").write_text(
        json.dumps(
            [
                {
                    "id": "10",
                    "gameId": 99,
                    "clock": {"minutes": 12, "seconds": 5},
                    "playType": "rush",
                }
            ]
        ),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    explode_payloads(db_path, only={"plays"})

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    cols = [row[0] for row in con.execute("DESCRIBE stg.plays").fetchall()]
    assert cols[0] == "playId"
    assert "clock" not in cols
    assert cols[-1] == "_source_file"
    row = con.execute(
        "SELECT playId, gameId, season, week, clock_minutes, clock_seconds, playType FROM stg.plays"
    ).fetchone()
    assert row == ("10", 99, 2023, 1, 12, 5, "rush")


def test_explode_flattens_nested_objects_with_prefixes(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "ppa_games_2023.json").write_text(
        json.dumps(
            [
                {
                    "gameId": 1,
                    "team": "Alpha",
                    "offense": {
                        "overall": 0.5,
                        "passing": 0.1,
                        "havoc": {"db": 0.2, "total": 0.3},
                    },
                    "defense": {
                        "overall": -0.2,
                        "passing": -0.1,
                        "havoc": {"db": 0.05, "total": 0.08},
                    },
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
    row = con.execute(
        "SELECT offense_overall, defense_overall FROM stg.ppa_games"
    ).fetchone()
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
        if str(row[1]).upper().startswith("STRUCT")
        and not str(row[1]).upper().endswith("[]")
    ]
    assert leftover_structs == []
    assert con.execute("SELECT COUNT(*) FROM stg.hist").fetchone()[0] == 1


def test_stg_column_order_puts_keys_and_sides_before_leftover_json():
    columns = [
        ("_source_file", "VARCHAR"),
        ("attendance", "UBIGINT"),
        ("awayId", "UBIGINT"),
        ("awayLineScores", "HUGEINT[]"),
        ("awayTeam", "VARCHAR"),
        ("completed", "BOOLEAN"),
        ("homeId", "UBIGINT"),
        ("homeLineScores", "HUGEINT[]"),
        ("homeTeam", "VARCHAR"),
        ("id", "UBIGINT"),
        ("season", "UBIGINT"),
        ("seasonType", "VARCHAR"),
        ("startDate", "VARCHAR"),
        ("venue", "VARCHAR"),
        ("venueId", "UBIGINT"),
        ("week", "UBIGINT"),
    ]
    ordered = stg_column_order(columns, schema="stg")
    assert ordered[0] == "id"
    assert ordered[1:5] == ["season", "week", "seasonType", "startDate"]
    home = ordered.index("homeId")
    away = ordered.index("awayId")
    assert home < ordered.index("homeTeam") < ordered.index("homeLineScores") < away
    assert away < ordered.index("awayTeam") < ordered.index("awayLineScores")
    assert ordered.index("venueId") < ordered.index("venue")
    assert ordered[-1] == "_source_file"
    assert ordered.index("attendance") > away


def test_stg_column_order_puts_renamed_pk_before_entity_name():
    ordered = stg_column_order(
        [
            ("_source_file", "VARCHAR"),
            ("name", "VARCHAR"),
            ("venueId", "UBIGINT"),
        ],
        schema="stg",
        table="venues",
    )
    assert ordered[0] == "venueId"
    assert ordered[1] == "name"


def test_stg_column_order_groups_offense_before_defense():
    columns = [
        ("_source_file", "VARCHAR"),
        ("defense_ppa", "DOUBLE"),
        ("gameId", "UBIGINT"),
        ("offense_ppa", "DOUBLE"),
        ("season", "UBIGINT"),
        ("team", "VARCHAR"),
        ("week", "UBIGINT"),
    ]
    assert stg_column_order(columns, schema="stg") == [
        "gameId",
        "season",
        "week",
        "team",
        "offense_ppa",
        "defense_ppa",
        "_source_file",
    ]


def test_explode_payloads_orders_stg_columns_for_browsing(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps(
            [
                {
                    "attendance": 10,
                    "awayId": 20,
                    "awayTeam": "B",
                    "homeId": 10,
                    "homeTeam": "A",
                    "id": 1,
                    "season": 2023,
                    "week": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    explode_payloads(db_path)

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    cols = [row[0] for row in con.execute("DESCRIBE stg.games").fetchall()]
    assert cols[0] == "gameId"
    assert cols[1:3] == ["season", "week"]
    assert "id" not in cols
    assert cols.index("homeTeamId") < cols.index("homeTeam") < cols.index("awayTeamId")
    assert cols.index("homeTeam") < cols.index("awayTeam")
    assert cols[-1] == "_source_file"


def test_reorder_stg_columns_rewrites_existing_table_and_restores_views(tmp_path):
    import duckdb

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.games AS
        SELECT 'x.json' AS _source_file, 9000 AS attendance, 1 AS id, 2023 AS season
        """
    )
    con.execute("CREATE VIEW stg.games_ids AS SELECT id FROM stg.games")
    con.close()

    reports = reorder_stg_columns(db_path)
    by_name = {r.name: r for r in reports}
    assert by_name["games"].error is None
    assert by_name["games"].files == 1

    con = duckdb.connect(str(db_path), read_only=True)
    cols = [row[0] for row in con.execute("DESCRIBE stg.games").fetchall()]
    assert cols == ["id", "season", "attendance", "_source_file"]
    assert con.execute("SELECT id FROM stg.games_ids").fetchone()[0] == 1
    assert stg_column_order([(c, "VARCHAR") for c in cols]) == cols


def test_stg_id_renames_matches_what_the_value_is():
    assert stg_id_renames("games", schema="stg") == {
        "id": "gameId",
        "homeId": "homeTeamId",
        "awayId": "awayTeamId",
    }
    assert stg_id_renames("plays", schema="stg") == {"id": "playId"}
    assert stg_id_renames("ppa_players_games_ngt", schema="stg") == {"id": "athleteId"}
    assert stg_id_renames("cfp_games", schema="stg") == {"id": "matchupId"}
    assert stg_id_renames("win_probability", schema="stg") == {
        "homeId": "homeTeamId",
        "awayId": "awayTeamId",
    }
    assert stg_id_renames("calendar", schema="stg") == {}


def test_stg_id_renames_resolves_gql_destinations_back_to_their_entity():
    """`_BARE_ID_RENAME` is keyed by GraphQL entity name, not by the stg_gql destination.
    Without the reverse lookup, a bare `game` in stg_gql misses the table and keeps a
    bare `id` column instead of `gameId` — silently, since nothing else asserts on it."""
    assert stg_id_renames("game", schema="stg_gql") == {"id": "gameId"}
    assert stg_id_renames("coach", schema="stg_gql") == {"id": "coachId"}
    assert stg_id_renames("lines_provider", schema="stg_gql") == {"id": "linesProviderId"}
    assert stg_id_renames("historical_team", schema="stg_gql") == {"id": "teamId"}


def test_stg_id_renames_does_not_apply_graphql_renames_to_rest_tables_in_stg():
    # A bare name that exists in both schemas (draft_picks, predicted_points, calendar)
    # must not pick up a GraphQL-entity id rename when it's actually the REST table.
    assert stg_id_renames("draft_picks", schema="stg") == {}
    assert stg_id_renames("draft_picks", schema="stg_gql") == {}
    assert stg_id_renames("games", schema="stg") == {
        "id": "gameId",
        "homeId": "homeTeamId",
        "awayId": "awayTeamId",
    }


def test_rename_stg_id_columns_rewrites_bare_id_and_skips_existing_dest(tmp_path):
    import duckdb

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.games AS
        SELECT 1 AS id, 10 AS homeId, 20 AS awayId, 2023 AS season
        """
    )
    con.execute(
        """
        CREATE TABLE stg.plays AS
        SELECT '10' AS id, 99 AS gameId
        """
    )
    con.execute(
        """
        CREATE TABLE stg.lines AS
        SELECT 1 AS id, 1 AS gameId
        """
    )
    con.close()

    reports = rename_stg_id_columns(db_path)
    by_name = {r.name: r for r in reports}
    assert by_name["games"].files == 3
    assert by_name["plays"].files == 1
    assert by_name["lines"].files == 0

    con = duckdb.connect(str(db_path), read_only=True)
    games = [row[0] for row in con.execute("DESCRIBE stg.games").fetchall()]
    assert games[0] == "gameId"
    assert "id" not in games
    assert "homeTeamId" in games and "awayTeamId" in games
    plays = [row[0] for row in con.execute("DESCRIBE stg.plays").fetchall()]
    assert plays[0] == "playId"
    assert con.execute("SELECT playId, gameId FROM stg.plays").fetchone() == ("10", 99)
    line_cols = {row[0] for row in con.execute("DESCRIBE stg.lines").fetchall()}
    assert line_cols == {"id", "gameId"}


def test_duckdb_cli_writes_db(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "venues.json").write_text(
        json.dumps([{"id": 1, "name": "Stadium"}]), encoding="utf-8"
    )

    assert main(["duckdb", "--data-dir", str(tmp_path), "--skip-actionnetwork"]) == 0
    out = capsys.readouterr().out
    assert "raw.venues" in out
    assert (tmp_path / "cfb.duckdb").exists()


def test_explode_actionnetwork_unpivots_history_and_unnests_scoreboard(tmp_path):
    an = tmp_path / "raw" / "actionnetwork"
    an.mkdir(parents=True)
    (an / "history_100.json").write_text(
        json.dumps(
            {
                "15": {
                    "firsthalf": {
                        "spread": [
                            {
                                "book_id": 15,
                                "event_id": 100,
                                "odds": -110,
                                "period": "firsthalf",
                                "side": "home",
                                "team_id": 1,
                                "type": "spread",
                                "value": -3.5,
                            }
                        ],
                        "total": [
                            {
                                "book_id": 15,
                                "event_id": 100,
                                "odds": -105,
                                "period": "firsthalf",
                                "side": "over",
                                "type": "total",
                                "value": 24.5,
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (an / "history_101.json").write_text("{}", encoding="utf-8")
    (an / "scoreboard_2025_wk1.json").write_text(
        json.dumps(
            {
                "content_live_count": 0,
                "games": [
                    {
                        "away_team_id": 2,
                        "boxscore": {
                            "clock": "00:00",
                            "latest_odds": {"game": {"total": 45.5}},
                            "period": 4,
                            "total_away_points": 17,
                            "total_home_points": 21,
                        },
                        "home_team_id": 1,
                        "id": 100,
                        "league_id": 9,
                        "league_name": "ncaaf",
                        "markets": {
                            "15": {
                                "event": {
                                    "spread": [
                                        {"odds": -110, "side": "home", "value": -3.5}
                                    ]
                                }
                            }
                        },
                        "season": 2025,
                        "start_time": "2025-08-30T00:00:00Z",
                        "status": "closed",
                        "teams": [{"abbr": "AAA", "id": 1}, {"abbr": "BBB", "id": 2}],
                        "week": 1,
                    },
                    {
                        "away_team_id": 4,
                        "home_team_id": 3,
                        "id": 200,
                        "season": 2025,
                        "week": 1,
                    },
                ],
                "league": {
                    "calendar_info": {"reg": [{"week": 1}]},
                    "id": 9,
                    "name": "ncaaf",
                },
            }
        ),
        encoding="utf-8",
    )

    db_path, _ = build_duckdb(tmp_path)
    reports = explode_payloads(
        db_path, only={"actionnetwork_history", "actionnetwork_scoreboard"}
    )
    by_name = {r.name: r for r in reports}
    assert by_name["actionnetwork_history"].error is None
    assert by_name["actionnetwork_scoreboard"].error is None

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    hist_cols = [
        row[0] for row in con.execute("DESCRIBE stg.actionnetwork_history").fetchall()
    ]
    assert "15_firsthalf_spread" not in hist_cols
    assert hist_cols[0] == "event_id"
    rows = con.execute(
        """
        SELECT event_id, book_id, period, market_type, side, line, odds
        FROM stg.actionnetwork_history
        ORDER BY market_type
        """
    ).fetchall()
    assert rows == [
        (100, 15, "firsthalf", "spread", "home", -3.5, -110),
        (100, 15, "firsthalf", "total", "over", 24.5, -105),
    ]

    board_cols = [
        row[0]
        for row in con.execute("DESCRIBE stg.actionnetwork_scoreboard").fetchall()
    ]
    assert "games" not in board_cols
    assert not any(c.startswith("league_calendar") for c in board_cols)
    games = con.execute(
        """
        SELECT event_id, season, week, home_team_id, away_team_id, home_points
        FROM stg.actionnetwork_scoreboard
        ORDER BY event_id
        """
    ).fetchall()
    assert games == [(100, 2025, 1, 1, 2, 21), (200, 2025, 1, 3, 4, None)]
    total = con.execute(
        "SELECT TRY_CAST(json_extract(latest_odds, '$.game.total') AS DOUBLE) "
        "FROM stg.actionnetwork_scoreboard WHERE event_id = 100"
    ).fetchone()[0]
    assert total == 45.5


def test_backfill_gamelines_fills_nulls_and_inserts_period_rows(tmp_path):
    import duckdb

    db_path = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.games (
          id INTEGER, season INTEGER, week INTEGER,
          homeTeam VARCHAR, awayTeam VARCHAR
        )
        """
    )
    con.execute("INSERT INTO stg.games VALUES (99, 2025, 1, 'Alpha', 'Beta')")
    con.execute(
        """
        CREATE TABLE stg.gql_game_lines (
          gameId INTEGER, linesProviderId INTEGER,
          moneylineAway INTEGER, moneylineHome INTEGER,
          overUnder DOUBLE, overUnderOpen DOUBLE,
          spread DOUBLE, spreadOpen DOUBLE, _source_file VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.gql_game_lines VALUES
          (99, 888888, NULL, NULL, 45.5, NULL, -7.0, -6.5, 'cfbd.json')
        """
    )
    con.execute(
        """
        CREATE TABLE stg.gql_lines_provider (
          id INTEGER, name VARCHAR, _source_file VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO stg.gql_lines_provider VALUES (888888, 'DraftKings', 'cfbd.json')"
    )
    con.execute(
        """
        CREATE TABLE stg.actionnetwork_scoreboard (
          event_id BIGINT, season INTEGER, week INTEGER,
          home_team_id BIGINT, away_team_id BIGINT,
          teams JSON, markets JSON, _source_file VARCHAR
        )
        """
    )
    teams = json.dumps([{"id": 1, "location": "Alpha"}, {"id": 2, "location": "Beta"}])
    markets = json.dumps(
        {
            "15": {
                "event": {
                    "spread": [
                        {
                            "period": "event",
                            "type": "spread",
                            "side": "home",
                            "value": -3.5,
                            "odds": -110,
                        }
                    ],
                    "total": [
                        {
                            "period": "event",
                            "type": "total",
                            "side": "over",
                            "value": 48.5,
                            "odds": -110,
                        }
                    ],
                    "moneyline": [
                        {
                            "period": "event",
                            "type": "moneyline",
                            "side": "home",
                            "value": 0,
                            "odds": -155,
                        },
                        {
                            "period": "event",
                            "type": "moneyline",
                            "side": "away",
                            "value": 0,
                            "odds": 135,
                        },
                    ],
                }
            }
        }
    )
    con.execute(
        """
        INSERT INTO stg.actionnetwork_scoreboard
        VALUES (100, 2025, 1, 1, 2, ?::JSON, ?::JSON, 'scoreboard.json')
        """,
        [teams, markets],
    )
    con.execute(
        """
        CREATE TABLE stg.actionnetwork_history (
          event_id BIGINT, book_id INTEGER, period VARCHAR,
          market_type VARCHAR, side VARCHAR, team_id BIGINT,
          line DOUBLE, odds BIGINT, _source_file VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO stg.actionnetwork_history VALUES
          (100, 15, 'firsthalf', 'spread', 'home', 1, -3.5, -110, 'history.json'),
          (100, 15, 'firsthalf', 'total', 'over', NULL, 24.5, -105, 'history.json')
        """
    )
    con.close()

    report = backfill_gamelines_from_actionnetwork(db_path)
    assert report is not None and report.error is None

    con = duckdb.connect(str(db_path), read_only=True)
    cols = {row[0] for row in con.execute("DESCRIBE stg.gql_game_lines").fetchall()}
    assert "period" in cols and "line_source" in cols
    fg = con.execute(
        """
        SELECT spread, spreadOpen, overUnder, moneylineHome, moneylineAway, period
        FROM stg.gql_game_lines
        WHERE gameId = 99 AND linesProviderId = 888888 AND period = 'game'
        """
    ).fetchone()
    assert fg == (-7.0, -6.5, 45.5, -155, 135, "game")
    half = con.execute(
        """
        SELECT spread, overUnder, period, line_source
        FROM stg.gql_game_lines
        WHERE gameId = 99 AND period = 'firsthalf'
        """
    ).fetchone()
    assert half[0] == -3.5 and half[1] == 24.5 and half[3] == "actionnetwork"
    names = {
        row[0] for row in con.execute("SELECT name FROM stg.gql_lines_provider").fetchall()
    }
    assert "DraftKings" in names and "FanDuel" in names
