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


# ---------------------------------------------------------------- the CFBD map (S4)

from pff_flatten import CFBD_RAW, OVERRIDES, cfbd_index, map_to_cfbd, norm  # noqa: E402

HAVE_TEAMS = CFBD_RAW.exists() and any(CFBD_RAW.glob("teams_2*.json"))


@pytest.mark.parametrize("raw,expected", [
    ("East Texas A&M", "east texas am"),        # PFF's slug drops the &, so both do
    ("William & Mary", "william mary"),
    ("St. Thomas (MN)", "st thomas"),           # leading St is Saint; the (MN) is cut
    ("San Jose St", "san jose state"),          # trailing St is State
    ("Bryant University Bulldogs", "bryant bulldogs"),
    ("Southern Miss Golden Eagles", "southern miss golden eagles"),   # `the` is not in
])
def test_norm_rules(raw, expected):
    assert norm(raw) == expected


@pytest.mark.skipif(not HAVE_TEAMS, reason="the CFBD teams pull is not on this machine")
def test_the_mascot_strip_cannot_eat_a_real_name_token():
    """Free suffix-stripping read `louisiana monroe warhawks` down to `louisiana`, which
    handed UL Monroe the Ragin' Cajuns' CFBD id. Only a known mascot may be removed."""
    _, _, names, mascots = cfbd_index()
    assert "warhawks" in mascots and "monroe" not in mascots
    rows = [{"franchise_id": "209", "slug": "louisiana-monroe-warhawks",
             "team_name": "", "kind": "team", "cfbd_team_id": "", "match": ""},
            {"franchise_id": "207", "slug": "louisiana-ragin-cajuns",
             "team_name": "", "kind": "team", "cfbd_team_id": "", "match": ""}]
    map_to_cfbd(rows)
    assert rows[0]["cfbd_team_id"] != rows[1]["cfbd_team_id"]
    assert names[rows[0]["cfbd_team_id"]] == "UL Monroe"


@pytest.mark.skipif(not HAVE_TEAMS, reason="the CFBD teams pull is not on this machine")
def test_an_ambiguous_school_is_never_guessed():
    """Both Miamis normalize to `miami`, so the rule must refuse and the override decide."""
    _, school, names, _ = cfbd_index()
    assert len(school["miami"]) > 1
    assert OVERRIDES["miami-fl-hurricanes"] == "Miami"
    row = [{"franchise_id": "220", "slug": "miami-fl-hurricanes", "team_name": "",
            "kind": "team", "cfbd_team_id": "", "match": ""}]
    map_to_cfbd(row)
    assert names[row[0]["cfbd_team_id"]] == "Miami" and row[0]["match"] == "override"


@pytest.mark.skipif(not (OUT_DIR / "pff_franchise.csv").exists(),
                    reason="run scripts/pff_flatten.py first")
def test_every_franchise_maps_to_a_distinct_cfbd_team():
    with (OUT_DIR / "pff_franchise.csv").open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["kind"] == "team"]
    unmapped = [r["slug"] for r in rows if not r["cfbd_team_id"]]
    assert not unmapped, f"unmapped franchises: {unmapped}"
    ids = [r["cfbd_team_id"] for r in rows]
    assert len(set(ids)) == len(ids), "two PFF franchises claim one CFBD team"


@pytest.mark.skipif(not (OUT_DIR / "pff_player_season.csv").exists(),
                    reason="run scripts/pff_flatten.py first")
def test_jersey_number_survives_the_player_spine():
    """Only the JSON-only leaderboards carry it, so it is always a later-pass backfill.

    A player's first sighting is usually a CSV leaderboard with no jersey at all. If the
    fill ever moves back to `people.setdefault`, this column silently returns to 100% NULL
    -- which is the state it spent its whole life in before 2026-09-09.
    """
    with (OUT_DIR / "pff_player_season.csv").open(encoding="utf-8") as fh:
        jerseys = [r["jersey_number"] for r in csv.DictReader(fh)]
    assert any(jerseys), "jersey_number is all-empty again -- the backfill stopped firing"
    assert any(j.startswith("0") for j in jerseys if j), "zero padding was lost to a numeric cast"
