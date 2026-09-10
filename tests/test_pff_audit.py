"""The audit's file classification and defect detection, on files written here."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_pff_pull import (  # noqa: E402
    column_drift, duplicate_bodies, inspect, json_only, team_op, type_drift,
)

SLUGS = frozenset({"akron-zips", "air-force-falcons"})


@pytest.mark.parametrize("stem,expected", [
    ("team_report_2025_akron-zips_coverage", "team_report.coverage"),
    ("team_stats_2025_wk1_offense-passing", "team_stats.offense-passing"),
    ("team_summary_2025_103", "team_summary"),
    ("games_2025_wk7", "games"),
])
def test_team_op_drops_the_entity_and_keeps_the_qualifier(stem, expected):
    assert team_op(stem, 2025, SLUGS) == expected


def test_inspect_names_each_defect(tmp_path):
    empty = tmp_path / "a.csv"
    empty.write_text("", encoding="utf-8")
    assert inspect(empty)[2] == "empty file"

    envelope = tmp_path / "b.csv"
    envelope.write_text(json.dumps({"error": {"code": "internal_error"}}), encoding="utf-8")
    assert inspect(envelope)[2] == "error envelope: internal_error"

    header_only = tmp_path / "c.csv"
    header_only.write_text("player,grade\n", encoding="utf-8")
    assert inspect(header_only)[2] == "header only"

    ok = tmp_path / "d.csv"
    ok.write_text("player,grade\nRussell,90\n", encoding="utf-8")
    rows, cols, defect, _ = inspect(ok)
    assert (rows, cols, defect) == (1, ["player", "grade"], None)


def test_inspect_reads_a_player_report_returned_as_one_object(tmp_path):
    """Player reports answer with a dict, not a row list; that is data, not a gap."""
    report = tmp_path / "p.json"
    report.write_text(json.dumps({"passing_summary": {"attempts": 30, "grade": 88.1}}), encoding="utf-8")
    rows, _, defect, _ = inspect(report)
    assert defect is None and rows == 2


def test_inspect_separates_column_keys_from_declared_types(tmp_path):
    report = tmp_path / "t.json"
    report.write_text(json.dumps({
        "columns": [{"key": "patPercent", "label": "Pat percent", "type": "integer"}],
        "rows": [{"patPercent": 100}]}), encoding="utf-8")
    _, cols, _, types = inspect(report)
    assert cols == ["patPercent"] and types == {"patPercent": "integer"}


def test_a_full_header_over_no_rows_is_still_a_defect(tmp_path):
    """A team report's `columns` list and 4-key `team` dict are envelope, not payload."""
    report = tmp_path / "e.json"
    report.write_text(json.dumps({
        "columns": [{"key": "a", "type": "integer"}], "rows": [], "league": "ncaa",
        "season": 2025, "report": "passing", "section": "offense", "weekGroup": "regular",
        "team": {"abbreviation": "BAMA", "franchiseId": 103, "name": "Alabama",
                 "slug": "alabama-crimson-tide"}}), encoding="utf-8")
    rows, _, defect, _ = inspect(report)
    assert (rows, defect) == (0, "no rows")


def test_drift_checks_separate_membership_order_and_type():
    found = {
        "wk1.json": {"op": "r", "week": 1, "cols": ["a", "b"], "types": {"a": "integer"},
                     "defect": None, "sha": "1", "tier": "team"},
        "wk2.json": {"op": "r", "week": 2, "cols": ["b", "a"], "types": {"a": "number"},
                     "defect": None, "sha": "1", "tier": "team"},
    }
    members, reordered = column_drift(found)
    assert members == [] and reordered == ["r"]
    assert type_drift(found) == [("r", "a", ["integer", "number"])]
    assert duplicate_bodies(found) == [("r", ["wk1.json", "wk2.json"])]


def test_duplicate_bodies_compares_across_an_ops_qualifiers():
    """`table=rows` and `table=totals` are two questions; one answer means a param was ignored."""
    found = {
        "rows.json": {"op": "d.rows", "week": None, "cols": None, "types": {},
                      "defect": None, "sha": "same", "tier": "team"},
        "totals.json": {"op": "d.totals", "week": None, "cols": None, "types": {},
                        "defect": None, "sha": "same", "tier": "team"},
    }
    assert duplicate_bodies(found) == [("d", ["rows.json", "totals.json"])]


def test_json_only_names_facets_a_csv_glob_would_drop():
    found = {
        "facet_a_ncaa_2025_fbs.json": {"op": "facet-a", "tier": "leaderboard", "week": None,
                                       "cols": None, "types": {}, "defect": None, "sha": "1"},
        "facet_b_ncaa_2025_fbs.csv": {"op": "facet-b", "tier": "leaderboard", "week": None,
                                      "cols": None, "types": {}, "defect": None, "sha": "2"},
    }
    assert json_only(found) == ["facet-a"]


# ------------------------------------------------------------------ the S7 pull-plan cuts

def test_the_pull_plan_stays_trimmed():
    """S7's three cuts, pinned so a later edit has to argue with a test.

    Each is a measured decision recorded in docs/pff-ingest-plan.md, not a preference:
    the eleven dropped reports are a column-for-column re-cut of the weekly leaderboards,
    `team-rushing-direction` returns the same body for both `table` values, and
    `facet-passing-detail` is the union of the other four passing facets and hangs.
    """
    from pull_pff_modeling import SKIP_FACETS, TEAM_REPORTS

    assert set(TEAM_REPORTS) == {"offense", "passing", "passing-pressure", "receiving",
                                 "pass-blocking", "run-blocking", "pass-rush", "special-teams"}
    assert "facet-passing-detail" in SKIP_FACETS

    source = (Path(__file__).resolve().parents[1] / "scripts" / "pull_pff_modeling.py"
              ).read_text(encoding="utf-8")
    assert source.count('"team-rushing-direction"') == 1, "planned once, not per `table` value"
    assert '"table": "rows"' in source


def test_the_audit_expects_exactly_what_the_puller_writes():
    """The audit imports TEAM_REPORTS, so cut 1 follows it -- but the rushing-direction
    filenames were hardcoded, and a stale pair there reports 136 phantom gaps a season."""
    source = (Path(__file__).resolve().parents[1] / "scripts" / "audit_pff_pull.py"
              ).read_text(encoding="utf-8")
    assert '("rows", "totals")' not in source
    assert "team_rushing_direction_{season}_{slug}_rows.json" in source
