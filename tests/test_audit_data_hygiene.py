"""`scripts/audit_data_hygiene.py`: the pure classification helpers, and each warehouse
check against a fixture-built database so a real defect produces the finding it should."""

import json

import duckdb

from scripts.audit_data_hygiene import (
    Report,
    check_catalog,
    check_folder,
    check_grains,
    check_joins,
    check_nulls_and_nan,
    classify_empty,
    diff_schemas,
    find_duplicates,
    group_raw_stems,
    main,
    season_gaps,
    stray_entries,
)
from datetime import datetime, timezone

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


# ----------------------------------------------------------------------------- pure logic


def test_stray_entries_ignores_pipeline_owned_names():
    names = ["cfb.duckdb", "raw", "graphql", "drop_cols.sql", "schema_columns.csv", "backups"]
    assert stray_entries(names) == ["drop_cols.sql", "schema_columns.csv"]


def test_group_raw_stems_follows_the_loader_and_skips_what_it_skips():
    groups = group_raw_stems([
        "games_2024", "games_2025", "plays_2024_wk1", "plays_2024_post_wk1",
        "lines_2026_week1_20260903", "user_info", "_abs_backfill",
    ])
    assert groups == {
        "games": [("games_2024", 2024), ("games_2025", 2025)],
        "plays": [("plays_2024_wk1", 2024), ("plays_2024_post_wk1", 2024)],
        # A dated snapshot is not a parseable stem, so it mints its own table.
        "lines_2026_week1_20260903": [("lines_2026_week1_20260903", None)],
    }


def test_classify_empty_knows_the_documented_floors():
    assert classify_empty("transfer_portal", 2015) == "floor"
    assert classify_empty("transfer_portal", 2021) == "unexpected"
    assert classify_empty("win_probability", 2013) == "floor"
    assert classify_empty("srs_expanded", 2020) == "floor"
    assert classify_empty("srs_expanded", 2019) == "unexpected"
    assert classify_empty("elo", 2026) == "floor"
    assert classify_empty("talent", 2026) == "floor"
    assert classify_empty("talent", 2025) == "unexpected"
    assert classify_empty("elo", 2027) == "unexpected"  # only the pending season is a floor
    assert classify_empty("games", None) == "unexpected"


def test_season_gaps():
    assert season_gaps([2012, 2013, 2015, 2018]) == [2014, 2016, 2017]
    assert season_gaps([2020]) == []
    assert season_gaps([]) == []


def test_find_duplicates_groups_by_content_hash():
    hashes = {"a.csv": "h1", "b.csv": "h1", "c.csv": "h2", "d.csv": "h3", "e.csv": "h3", "f.csv": "h3"}
    assert find_duplicates(hashes) == [["d.csv", "e.csv", "f.csv"], ["a.csv", "b.csv"]]


def test_diff_schemas_reports_every_kind_of_drift():
    old = {"stg.a": {"x": "INTEGER", "y": "JSON"}, "stg.gone": {"z": "VARCHAR"}}
    new = {"stg.a": {"x": "INTEGER", "y": "DOUBLE", "w": "BOOLEAN"}, "stg.new": {"q": "INTEGER"}}
    assert diff_schemas(old, new) == {
        "tables_added": ["stg.new"],
        "tables_removed": ["stg.gone"],
        "columns_added": ["stg.a.w BOOLEAN"],
        "columns_removed": [],
        "types_changed": ["stg.a.y JSON -> DOUBLE"],
    }


# ----------------------------------------------------------------------------- warehouse


def _con():
    con = duckdb.connect(":memory:")
    for schema in ("raw", "stg", "core", "meta"):
        con.execute(f"CREATE SCHEMA {schema}")
    return con


def _codes(rep, severity=None):
    return [f.code for f in rep.findings if severity is None or f.severity == severity]


def test_check_grains_fails_on_a_duplicate_key():
    con = _con()
    con.execute("CREATE TABLE stg.games AS SELECT * FROM (VALUES (1), (1), (2)) t(gameId)")
    rep = Report()
    check_grains(rep, con)
    fails = [f for f in rep.findings if f.severity == "FAIL"]
    assert len(fails) == 1
    assert "stg.games" in fails[0].message and "1 duplicate" in fails[0].message
    # A table that is absent is listed, not counted as a failure.
    assert any("missing" in line for line in rep.lines)


def test_check_nulls_and_nan_flags_nan_json_and_null_rates():
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.game_lines AS SELECT * FROM (VALUES
          (1, 1, '"NaN"'::JSON, 40.5::DOUBLE),
          (2, 1, '-3'::JSON, 'NaN'::DOUBLE),
          (3, NULL, '2'::JSON, 44.0::DOUBLE)
        ) t(gameId, linesProviderId, spread, "overUnder")
        """
    )
    rep = Report()
    check_nulls_and_nan(rep, con)
    warns = {f.code: f.message for f in rep.findings if f.severity == "WARN"}
    assert "json-typed-columns" in warns and "game_lines.spread" in warns["json-typed-columns"]
    assert "nan-values" in warns and "stg.game_lines.overUnder" in warns["nan-values"]
    assert "key-null-rate" in warns and "linesProviderId" in warns["key-null-rate"]


def test_check_joins_fails_a_must_be_zero_orphan_and_only_notes_a_known_one():
    con = _con()
    con.execute("CREATE TABLE stg.games AS SELECT * FROM (VALUES (1), (2)) t(gameId)")
    con.execute(
        "CREATE TABLE core.fact_game AS SELECT * FROM (VALUES (1, 10, 11), (3, 10, 99))"
        " t(game_id, home_team_id, away_team_id)"
    )
    con.execute("CREATE TABLE core.dim_team AS SELECT * FROM (VALUES (10), (11)) t(team_id)")
    rep = Report()
    check_joins(rep, con)
    fails = [f.message for f in rep.findings if f.severity == "FAIL"]
    infos = [f.message for f in rep.findings if f.severity == "INFO"]
    assert any("core.fact_game.game_id -> stg.games: 1 orphan" in m for m in fails)
    assert any("away_team_id -> core.dim_team: 1 of 2" in m for m in infos)
    assert not any("home_team_id" in m for m in fails + infos)


def test_check_catalog_reports_missing_expected_tables_columns_and_load_errors():
    con = _con()
    con.execute(
        "CREATE TABLE meta.load_report AS SELECT * FROM (VALUES"
        " ('raw', 'games', 1, 5, NULL::VARCHAR, TIMESTAMP '2026-09-11 11:00:00'),"
        " ('stg', 'game_lines', 0, 0, 'stg.an_market absent', TIMESTAMP '2026-09-11 11:00:00'))"
        " t(schema, name, files, rows, error, loaded_at)"
    )
    con.execute("CREATE TABLE stg.game_lines AS SELECT 1 AS gameId, 1 AS linesProviderId")
    rep = Report()
    loaded_at = check_catalog(rep, con, None)
    assert loaded_at == datetime(2026, 9, 11, 11, 0, tzinfo=timezone.utc)
    codes = _codes(rep, "FAIL")
    assert "load-error" in codes
    assert codes.count("expected-table-missing") >= 30
    assert codes.count("expected-column-missing") == 2


# ----------------------------------------------------------------------------- folder


def _seed_root(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2026.json").write_text('[{"id": 1}]', encoding="utf-8")
    (raw / "lines_2026.json").write_text('[{"id": 1}]', encoding="utf-8")
    (raw / "calendar_2026.json").write_text("[]", encoding="utf-8")  # empty, not a floor
    (raw / "transfer_portal_2015.json").write_text("[]", encoding="utf-8")  # documented floor
    (raw / "lines_2026_week1_20260903.json").write_text('[{"id": 1}]', encoding="utf-8")  # unregistered
    (raw / "user_info.json").write_text("{}", encoding="utf-8")
    (tmp_path / "graphql").mkdir()
    (tmp_path / "graphql" / "gamePlayerStat.json").write_text("[]", encoding="utf-8")
    (tmp_path / "graphql" / "gamePlayerStat_2024.json").write_text("[]", encoding="utf-8")
    (tmp_path / "processed").mkdir()
    (tmp_path / "drop_cols.sql").write_text("ALTER TABLE x DROP COLUMN y;", encoding="utf-8")
    (tmp_path / "schema_a.csv").write_text("same,content\n", encoding="utf-8")
    (tmp_path / "schema_b.csv").write_text("same,content\n", encoding="utf-8")
    return tmp_path


def test_check_folder_finds_strays_orphans_undocumented_empties_and_duplicates(tmp_path):
    root = _seed_root(tmp_path)
    rep = Report()
    check_folder(rep, root, NOW, 30, None)
    by_code = {}
    for f in rep.findings:
        by_code.setdefault(f.code, []).append(f.message)

    assert sorted(m.split("`")[1] for m in by_code["stray-root-file"]) == [
        "drop_cols.sql", "schema_a.csv", "schema_b.csv",
    ]
    assert "lines_2026_week1_20260903" in by_code["unregistered-raw-stem"][0]
    assert by_code["empty-payload-undocumented"] == [
        "`raw/calendar_2026.json` is empty and is not a documented floor"
    ]
    assert "gamePlayerStat.json" in by_code["gql-shadow-dump"][0]
    assert "schema_a.csv" in by_code["duplicate-file"][0]
    # Of the daily-refresh endpoints only the per-season ones need a `<name>_2026` file
    # (`conferences`/`venues` are whole-corpus); calendar is present but empty.
    assert by_code["refresh-endpoint-missing"] == [
        "`raw/calendar_2026.json` missing or empty; refresh_cfbd.py re-scrapes it daily"
    ]


def test_main_writes_a_folder_only_report_and_json(tmp_path):
    root = _seed_root(tmp_path)
    out = tmp_path / "report.md"
    js = tmp_path / "findings.json"
    rc = main(["--data-root", str(root), "--db", str(tmp_path / "nope.duckdb"),
               "--checks", "folder", "--out", str(out), "--json", str(js)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Data hygiene audit")
    assert "## Data folder inventory" in text and "## Duplicate files" in text
    findings = json.loads(js.read_text(encoding="utf-8"))
    assert {f["severity"] for f in findings} <= {"FAIL", "WARN", "INFO"}
    assert any(f["code"] == "stray-root-file" for f in findings)


def test_strict_exits_nonzero_when_the_warehouse_is_missing(tmp_path):
    root = _seed_root(tmp_path)
    rc = main(["--data-root", str(root), "--db", str(tmp_path / "nope.duckdb"),
               "--checks", "warehouse", "--out", str(tmp_path / "r.md"), "--strict"])
    assert rc == 1
