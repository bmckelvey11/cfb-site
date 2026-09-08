"""The flattener's split rules, type rule, and registry invariants.

The unpivot is where a metric goes missing silently, so the rules are asserted directly
rather than through the output. One test reads the real 2025 files when they are present:
a value has to survive the round trip from a weekly export to a `split = 'all'` row.
"""

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from pff_flatten import (  # noqa: E402
    DEPTH16, IN_DIR, OUT_DIR, RELABEL, SOURCES, Source, duckdb_type, split_of,
)

SUMMARY = next(s for s in SOURCES if s.stem == "facet_passing_summary")
DEPTH = next(s for s in SOURCES if s.stem == "facet_passing_depth")
CONCEPT = next(s for s in SOURCES if s.stem == "facet_passing_concept")
RUSH = next(s for s in SOURCES if s.stem == "signature_defense_outside_pass_rush")


def test_a_source_without_splits_never_invents_one():
    """The §5.1 regex read `pressure_to_sack_rate` as split `pressure`. This is that bug."""
    assert split_of("pressure_to_sack_rate", SUMMARY) == ("all", "pressure_to_sack_rate")
    assert split_of("attempts", SUMMARY) == ("all", "attempts")


def test_splits_match_longest_first():
    """`no_screen_x` is not split `no`, and `no_pressure_x` is not split `pressure`."""
    pressure = next(s for s in SOURCES if s.stem == "facet_passing_pressure")
    assert split_of("no_pressure_attempts", pressure) == ("no_pressure", "attempts")
    assert split_of("pressure_attempts", pressure) == ("pressure", "attempts")
    assert split_of("no_screen_attempts", CONCEPT) == ("no_screen", "attempts")
    assert split_of("screen_attempts", CONCEPT) == ("screen", "attempts")


def test_a_reports_own_total_is_not_another_reports_all():
    """Measured: these populations differ, so they must not merge onto the `all` row."""
    assert split_of("dropbacks", CONCEPT) == ("concept", "dropbacks")
    assert split_of("pressures", RUSH) == ("outside", "pressures")
    assert split_of("lhs_pressures", RUSH) == ("lhs", "pressures")


def test_denominators_and_the_spine_are_dropped():
    assert split_of("base_attempts", DEPTH) is None      # equals the `all` row's count
    assert split_of("player_game_count", SUMMARY) is None  # always 1 on a weekly row
    assert split_of("franchise_id", SUMMARY) is None       # key, not metric


def test_unprefixed_columns_of_a_split_source_are_dropped_by_declaration():
    """`base_split=''` says the unsplit leftovers duplicate another source's `all` row."""
    assert DEPTH.base_split == ""
    assert split_of("penalties", DEPTH) is None


def test_relabelled_splits_say_what_they_mean():
    ttt = next(s for s in SOURCES if s.stem == "signature_passing_time_in_pocket")
    assert split_of("less_attempts", ttt) == ("ttt_under_2_5", "attempts")
    assert split_of("more_attempts", ttt) == ("ttt_over_2_5", "attempts")
    assert set(RELABEL) == {"less", "more"}


def test_depth_vocabulary_is_the_sixteen_pff_uses():
    assert len(DEPTH16) == 16
    assert "left_behind_los" in DEPTH16 and "behind_los" in DEPTH16


@pytest.mark.parametrize("column,expected", [
    ("grades_pass", "DOUBLE"), ("accuracy_percent", "DOUBLE"), ("btt_rate", "DOUBLE"),
    ("ypa", "DOUBLE"), ("epa", "DOUBLE"), ("pbe", "DOUBLE"), ("ypa_diff", "DOUBLE"),
    ("qb_rating_against", "DOUBLE"), ("avg_time_to_throw", "DOUBLE"),
    ("attempts", "INTEGER"), ("season", "INTEGER"), ("player_id", "INTEGER"),
    ("split", "VARCHAR"), ("direction", "VARCHAR"), ("jersey_number", "VARCHAR"),
    ("pulled_at", "DATE"),
])
def test_types_come_from_the_rule_not_the_data(column, expected):
    """PFF declares one column two ways across responses, so nothing may be inferred."""
    assert duckdb_type(column) == expected


def test_every_source_maps_to_exactly_one_table_and_declares_its_splits():
    for source in SOURCES:
        assert source.table.startswith("pff_")
        if source.splits:
            assert source.base_split is not None, f"{source.stem} leaves unsplit columns undeclared"
        assert source.grain in ("player", "franchise")


@pytest.mark.skipif(not (IN_DIR / "facet_passing_summary_ncaa_2025_fbs_wk5.csv").exists(),
                    reason="the 2025 pull is not on this machine")
def test_a_real_value_survives_the_round_trip():
    """One player's week-5 attempts, from the weekly export to the `all` row."""
    src = IN_DIR / "facet_passing_summary_ncaa_2025_fbs_wk5.csv"
    with src.open(encoding="utf-8") as fh:
        wanted = max(csv.DictReader(fh), key=lambda r: int(r["attempts"] or 0))
    out = OUT_DIR / "pff_passing.csv"
    if not out.exists():
        pytest.skip("run scripts/pff_flatten.py --seasons 2025 first")
    with out.open(encoding="utf-8") as fh:
        row = next(r for r in csv.DictReader(fh)
                   if r["season"] == "2025" and r["week"] == "5"
                   and r["player_id"] == wanted["player_id"] and r["split"] == "all")
    assert row["attempts"] == wanted["attempts"]
    assert row["grades_pass"] == wanted["grades_pass"]
    # the column the greedy regex would have destroyed
    assert row["pressure_to_sack_rate"] == wanted["pressure_to_sack_rate"]
