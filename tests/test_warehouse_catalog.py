"""Pins for scripts/build_warehouse_catalog.py.

The catalog's `DATA` block is regenerated wholesale, so a silent rule change
rewrites 322 rows at once. These pin the three classifications that carry
information the live database cannot re-derive on its own.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "build_warehouse_catalog", REPO / "scripts" / "build_warehouse_catalog.py"
)
bwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bwc)


def test_gql_origin_survives_the_stg_gql_collapse():
    """The `graphql` schema is gone, so `o` is the only record of transport.

    A GraphQL destination must read as GraphQL in both schemas, and the three
    names REST also owns must keep their `_gql` suffix on the GraphQL side.
    """
    from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG

    assert GQL_ENTITY_TO_RAW and GQL_ENTITY_TO_STG
    for name in GQL_ENTITY_TO_RAW.values():
        assert bwc.origin_of("raw", name) == "gql"
    for name in GQL_ENTITY_TO_STG.values():
        assert bwc.origin_of("stg", name) == "gql"

    assert bwc.origin_of("stg", "calendar_gql") == "gql"
    assert bwc.origin_of("stg", "weekly_slate") == "rest"
    assert bwc.origin_of("raw", "an_history") == "an"
    assert bwc.origin_of("stg", "an_history_tick") == "an"
    assert bwc.origin_of("core", "fact_game") == "core"
    assert bwc.origin_of("meta", "load_report") == "meta"


@pytest.mark.parametrize(
    "schema,name,domain",
    [
        # Whole-token matching: `players` is not `play`, `playoff` is not `play`.
        ("stg", "play_stats", "plays"),
        ("stg", "player_season_stats", "players"),
        ("stg", "cfp_playoff", "ratings"),
        ("stg", "cfp_games", "games"),
        # An exploded child inherits the root before `__`, not its leaf tokens.
        ("stg", "advanced_box_score__teams_rushing", "games"),
        ("stg", "cfp_playoff__rounds__rounds_matchups", "ratings"),
        ("stg", "game__home_line_scores", "games"),
        # Order calls carried over from the hand-built catalog.
        ("stg", "team_stats", "games"),
        ("stg", "recruiting_teams", "personnel"),
        ("stg", "kicker_paar", "ratings"),
        ("stg", "teams_ats", "betting"),
        ("raw", "gql_game_lines", "betting"),
        ("core", "fact_game", "core"),
        ("meta", "load_report", "meta"),
    ],
)
def test_domain_rules(schema, name, domain):
    assert bwc.domain_of(schema, name) == domain


def test_keys_and_grain_are_not_measurements():
    assert bwc.measure_kind("season", "INTEGER") is None
    assert bwc.measure_kind("week", "INTEGER") is None
    assert bwc.measure_kind("homeTeamId", "UBIGINT") is None
    assert bwc.measure_kind("game_id", "BIGINT") is None
    assert bwc.measure_kind("startTimeTbd", "BOOLEAN") is None
    assert bwc.measure_kind("_source_file", "VARCHAR") is None
    assert bwc.measure_kind("school", "VARCHAR") is None
    assert bwc.measure_kind("spread_close", "DOUBLE") == "stat"
    assert bwc.measure_kind("capacity", "INTEGER") == "stat"
    assert bwc.measure_kind("dome", "BOOLEAN") == "flag"


def test_sample_cells_are_short_json_safe_and_carry_no_machine_paths():
    root = str(bwc.cfb_paths.DATA_ROOT)
    assert bwc.sample_cell(f"{root}/raw/calendar_2012.json") == "raw/calendar_2012.json"
    assert bwc.sample_cell(root.replace("\\", "/") + "/raw/x.json") == "raw/x.json"
    # Pretty-printed JSON collapses to one line before it is cut.
    assert bwc.sample_cell('{\r\n  "a":   1\r\n}') == '{ "a": 1 }'
    long = bwc.sample_cell("x" * 500)
    assert len(long) == bwc.CELL_CHARS and long.endswith("…")
    assert bwc.sample_cell(None) is None
    assert bwc.sample_cell(True) is True
    assert bwc.sample_cell(Decimal("1.5")) == 1.5
    assert bwc.sample_cell(datetime(2026, 9, 16, 13, 25, 18)) == "2026-09-16T13:25:18"
    json.dumps([bwc.sample_cell(v) for v in (None, 1, 1.5, True, "a", Decimal("2"))])


def test_the_committed_samples_leak_no_home_directory():
    """A committed doc must not carry whoever built it's absolute paths.

    Covers both sample rows (`d["s"]`) and the per-column min/max stats
    (`d["c"][i][2:4]`) -- `min(_source_file)`/`max(_source_file)` are exactly
    the kind of absolute path this guard exists for.
    """
    data = bwc.parse_data(bwc.CATALOG.read_text(encoding="utf-8"))
    root = str(bwc.cfb_paths.DATA_ROOT)
    needles = {root.lower(), root.replace("\\", "/").lower()}

    def check(key, cell):
        if isinstance(cell, str):
            low = cell.lower()
            assert not any(n in low for n in needles), f"{key}: {cell}"
            assert len(cell) <= bwc.CELL_CHARS, f"{key}: {cell}"

    for key, d in data["detail"].items():
        for row in d["s"]:
            for cell in row:
                check(key, cell)
        for c in d["c"]:
            check(key, c[2])
            check(key, c[3])


def test_every_table_has_a_detail_entry():
    data = bwc.parse_data(bwc.CATALOG.read_text(encoding="utf-8"))
    for t in data["tables"]:
        key = f"{t['s']}.{t['n']}"
        assert key in data["detail"], f"no columns/sample captured for {key}"
        d = data["detail"][key]
        assert len(d["c"]) == t["c"], f"{key}: column count disagrees with the row"
        assert len(d["s"]) <= bwc.SAMPLE_ROWS
        for row in d["s"]:
            assert len(row) == t["c"], f"{key}: sample row is not {t['c']} wide"


def test_render_round_trips_through_the_parser():
    """Write-back must not corrupt DATA: what render emits, parse_data reads."""
    data = {
        "tables": [
            {"s": "core", "n": "dim_team", "r": 703, "g": "core", "o": "core",
             "c": 5, "ns": 0, "nn": 0}
        ],
        "wstats": [
            {"s": "core", "t": "dim_team", "c": "is_fbs", "y": "BOOLEAN",
             "k": "flag", "g": "core"}
        ],
        "named": [{"src": "team_stats", "name": "games", "cat": "team box", "n": 1953}],
        "detail": {
            "core.dim_team": {
                # [name, type, min, max, ndistinct, nulls, nan] -- an extra
                # 8th slot (glossary index) is added only for pff_* columns.
                "c": [
                    ["team_id", "INTEGER", 1, 703, 703, 0, None],
                    ["school", "VARCHAR", "Air Force", "Yale", 703, 0, None],
                ],
                # A quote, a non-ASCII ellipsis, a null and a bool in one row.
                "s": [[1, 'He said "hi"…'], [2, None], [3, True]],
            }
        },
        # Empty-string grain is not emitted -- render() skips falsy values, so
        # the fixture only carries the one table that has a computed grain.
        "grain": {"core.dim_team": "One row per team_id"},
        "pffGlossary": [
            {"needle": "grade", "label": "PFF grade (0-100)",
             "def": "A 0-100 transformed grade.", "src": "PFF grades"}
        ],
        "domainOrder": ["core", "games"],
        # Quotes and a non-ASCII dash: both have to survive the string masker.
        "coreNote": {"dim_week": 'Season × week "grain"'},
        "loaded": "2026-09-16",
        "stg_tables": 184, "raw_tables": 119, "core_tables": 18, "meta_tables": 1,
        "stg_rows": 32285774, "raw_rows": 15131083, "core_rows": 441917,
        "meta_rows": 147,
    }
    html = "const DATA = {PLACEHOLDER\n      };"
    rebuilt = bwc.DATA_SPAN.sub(
        lambda m: m.group(1) + bwc.render(data) + m.group(3), html
    )
    assert bwc.parse_data(rebuilt) == data


def _structure(data: dict) -> dict:
    """The parts of DATA that only a schema change moves.

    Row counts are `count(*)`, so they drift on every `refresh_cfbd.py` and
    would turn the default `python -m pytest` gate red on work that never
    touched the catalog. `--check` stays byte-exact; this only guards the
    shape -- a table appearing or vanishing, a column set changing, an origin
    or domain shifting.
    """
    return {
        "tables": [{k: v for k, v in t.items() if k != "r"} for t in data["tables"]],
        "wstats": data["wstats"],
        # `named` is emitted count-desc, so its order drifts too -- compare unordered.
        "named": {(n["src"], n["name"], n["cat"]) for n in data["named"]},
        # Column [name, type, ...glossary_idx?] is schema; min/max/ndistinct/nulls
        # are data and move with the data (same reason row counts are stripped
        # above) -- keep name, type, and a pff column's glossary index (stable
        # given the column name), drop the five stat slots between them.
        "detail": {
            k: [[c[0], c[1], *c[7:]] for c in v["c"]] for k, v in data["detail"].items()
        },
        # Computed from row uniqueness -- data, like row counts. Structure is
        # whether a table's key-column *set* changed, not whether the current
        # data happens to be unique on it. `render()` omits empty grain
        # entries entirely (no point spelling out 150 "no key columns"
        # blanks), so drop them here too rather than comparing "absent" to
        # "present but False".
        "grain": {k for k, v in data["grain"].items() if v},
        "pffGlossary": data["pffGlossary"],
        "domainOrder": data["domainOrder"],
        "coreNote": data["coreNote"],
    }


def test_column_stats_and_grain_on_synthetic_data():
    """Unit-level check that doesn't need the live warehouse: an in-memory table
    with a known duplicate and a known-unique key column."""
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute(
        "create table t as select * from (values "
        "(1, 10, 'a'), (2, 10, 'a'), (3, NULL, 'b')"
        ") as v(game_id, week, school)"
    )
    cols = con.execute("describe t").fetchall()

    stats = bwc.column_stats(con, "main", "t", cols)
    assert stats["game_id"] == (1, 3, 3, 0, None)
    # week has a null and a repeated value.
    assert stats["week"] == (10, 10, 1, 1, None)

    # game_id and week are both key-shaped (bwc.is_key); their tuple is unique
    # here because game_id alone already is.
    assert bwc.compute_grain(con, "main", "t", cols, 3) == "One row per game_id, week"

    con.execute("create table dup as select * from (values (1), (1)) as v(game_id)")
    dup_cols = con.execute("describe dup").fetchall()
    assert bwc.compute_grain(con, "main", "dup", dup_cols, 2) == (
        "Not unique on game_id (1 duplicate rows)"
    )


def test_pff_glossary_matches_are_specific_not_guessed():
    assert bwc.pff_glossary_match("grades_pass") == 0
    assert bwc.pff_glossary_match("avg_depth_of_target") is not None
    assert bwc.pff_glossary_match("missed_tackle_rate") is not None
    # A plain box-score count with no PFF-specific meaning stays unmatched --
    # the glossary must not paraphrase a definition PFF hasn't published.
    assert bwc.pff_glossary_match("completions") is None
    # Every glossary entry that claims a formula isn't public must say so,
    # not silently assert a number PFF has not disclosed.
    war = next(g for g in bwc.PFF_GLOSSARY if g[0] == "war")
    assert "no public formula" in war[2].lower()


def test_sampling_is_deterministic():
    """Two builds of the same data must sample the same rows.

    Without a total order the sample drifts between runs, which makes `--check`
    cry wolf after a reload that changed nothing.
    """
    db = Path(os.environ.get("CFB_DATA_ROOT", "")) / "cfb.duckdb"
    if not db.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        # The tables that tie on every scalar column, so only a total order fixes them.
        for schema, name in (
            ("raw", "gamePlayerStat"),
            ("raw", "win_probability"),
            ("stg", "pff_defense_pass_rush"),
        ):
            cols = con.execute(f'describe "{schema}"."{name}"').fetchall()
            first = bwc.sample_rows(con, schema, name, cols)
            assert first == bwc.sample_rows(con, schema, name, cols), f"{schema}.{name}"
    finally:
        con.close()


def test_committed_catalog_matches_the_live_warehouse():
    db = Path(os.environ.get("CFB_DATA_ROOT", "")) / "cfb.duckdb"
    if not db.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    html = bwc.CATALOG.read_text(encoding="utf-8")
    new_html, data, _seed = bwc.build(html)

    assert _structure(bwc.parse_data(html)) == _structure(data), (
        "docs/cfb-warehouse-catalog.html is structurally stale -- run "
        "`python scripts/build_warehouse_catalog.py`"
    )
    assert "graphql" not in new_html.split("const DATA")[1][:200_000], (
        "the dead graphql schema is back in DATA"
    )
