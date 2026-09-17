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
    """A committed doc must not carry whoever built it's absolute paths."""
    data = bwc.parse_data(bwc.CATALOG.read_text(encoding="utf-8"))
    root = str(bwc.cfb_paths.DATA_ROOT)
    needles = {root.lower(), root.replace("\\", "/").lower()}
    for key, d in data["detail"].items():
        for row in d["s"]:
            for cell in row:
                if isinstance(cell, str):
                    low = cell.lower()
                    assert not any(n in low for n in needles), f"{key}: {cell}"
                    assert len(cell) <= bwc.CELL_CHARS, f"{key}: {cell}"


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
                "c": [["team_id", "INTEGER"], ["school", "VARCHAR"]],
                # A quote, a non-ASCII ellipsis, a null and a bool in one row.
                "s": [[1, 'He said "hi"…'], [2, None], [3, True]],
            }
        },
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
        # Column lists are schema; sample rows are data, and move with the data.
        "detail": {k: v["c"] for k, v in data["detail"].items()},
        "domainOrder": data["domainOrder"],
        "coreNote": data["coreNote"],
    }


def test_sampling_is_deterministic():
    """Two builds of the same data must sample the same rows.

    Without a total order the sample drifts between runs, which makes `--check`
    cry wolf after a reload that changed nothing.
    """
    db = Path(os.environ.get("CFB_DATA_ROOT", "")) / "cfb.duckdb"
    if not db.exists():
        pytest.skip("no live CFB_DATA_ROOT warehouse")
    con = bwc.connect()
    try:
        # The tables that tie on every scalar column, so only a total order fixes them.
        for schema, name in (
            ("raw", "gamePlayerStat"),
            ("raw", "win_probability"),
            ("stg", "pff_defense_pass_rush"),
        ):
            first = bwc.sample_rows(con, schema, name)
            assert first == bwc.sample_rows(con, schema, name), f"{schema}.{name}"
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
