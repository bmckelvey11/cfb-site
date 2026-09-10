"""the-odds-api flatten: the sign convention, the type pin, and the name rule."""

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from cfb_system_maker.oddsapi_schema import (  # noqa: E402
    ALIASES, OA_TABLES, candidates, column_type, norm,
)
from oddsapi_flatten import (  # noqa: E402
    OUT_DIR, SNAPSHOT_COLUMNS, TICK_COLUMNS, flatten, school_of, side_of,
)

EVENT = {"id": "e1", "commence_time": "2026-09-11T00:00:00Z",
         "home_team": "Miami Hurricanes", "away_team": "Florida A&M Rattlers"}


# ------------------------------------------------------------------ the sign convention

def test_a_spread_outcome_takes_the_side_of_the_team_it_names():
    """The whole reason `side_of` exists.

    `spreads` outcomes are named after a team, not home/away, so the side has to come from
    matching the event's own strings. Get it wrong and the handicap's sign flips on a row
    nothing downstream can audit -- the favourite becomes the dog.
    """
    assert side_of("Miami Hurricanes", EVENT) == "home"
    assert side_of("Florida A&M Rattlers", EVENT) == "away"


def test_totals_outcomes_are_over_under_whatever_the_case():
    assert side_of("Over", EVENT) == "over"
    assert side_of("under", EVENT) == "under"


def test_an_unmatched_outcome_raises_rather_than_guessing():
    """A default here would silently pick a side. Loud beats plausible."""
    with pytest.raises(ValueError, match="neither Over/Under nor a team"):
        side_of("Miami", EVENT)          # the CFBD spelling, not the vendor's


def test_the_flattened_spread_keeps_the_vendor_sign_per_side(tmp_path):
    import json

    payload = {"pulled_at": "2026-09-09T19:48:35Z", "sport": "americanfootball_ncaaf",
               "regions": ["us"], "markets": ["spreads"], "odds_format": "american",
               "requests_last": 3, "requests_used": 6, "requests_remaining": 494,
               "events": [dict(EVENT, bookmakers=[{
                   "key": "fanduel", "title": "FanDuel",
                   "last_update": "2026-09-09T19:48:31Z",
                   "markets": [{"key": "spreads", "outcomes": [
                       {"name": "Florida A&M Rattlers", "price": -110, "point": 57.5},
                       {"name": "Miami Hurricanes", "price": -110, "point": -57.5}]}]}])]}
    path = tmp_path / "odds_x.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    ticks, snapshots, names = flatten([path], {"miami": "Miami", "florida a m": "Florida A&M"})
    by_side = {t["side"]: t for t in ticks}
    assert by_side["away"]["line"] == 57.5, "the dog's handicap is positive"
    assert by_side["home"]["line"] == -57.5, "the favourite's is negative"
    assert by_side["home"]["home_school"] == "Miami"
    assert snapshots[0]["event_count"] == 1
    assert names == {"Miami Hurricanes": "Miami", "Florida A&M Rattlers": "Florida A&M"}


def test_none_reaches_the_csv_as_an_empty_field():
    """`line` is None on every h2h row and the quota fields are None when the header was
    missing, so `nullstr = ''` on the load side needs a blank, not the string "None"."""
    import json
    from oddsapi_flatten import _blank_if_none

    assert _blank_if_none(None) == ""
    assert _blank_if_none(0) == 0


# ------------------------------------------------------------------ the pin and the rule

def test_the_pinned_types_survive_a_column_that_is_empty_everywhere():
    """`line` is empty on every h2h row, so read_csv_auto would sniff it VARCHAR on a
    moneyline-only snapshot and the next load would refuse the file."""
    assert column_type("line") == "DOUBLE"
    assert column_type("odds") == "INTEGER"
    assert column_type("pulled_at") == "TIMESTAMP WITH TIME ZONE"
    assert column_type("home_school") == "VARCHAR"


def test_the_writers_columns_are_all_typed():
    for column in TICK_COLUMNS + SNAPSHOT_COLUMNS:
        assert column_type(column), column


def test_norm_folds_the_two_cfbd_spellings_that_bite():
    """Both are CFBD's own spellings and both presented as vendor gaps before they were
    understood as normalizer bugs."""
    assert norm("San José State") == "san jose state"
    assert norm("Hawai'i") == "hawaii"


def test_the_alias_list_is_reachable_through_the_mascot_strip():
    assert "app state" in candidates("Appalachian State Mountaineers")
    assert set(ALIASES) <= {norm(k) for k in ALIASES}, "alias keys must already be normed"


def test_school_of_prefers_the_longest_head():
    """Longest-first is what keeps "Miami (OH) RedHawks" off "miami"."""
    schools = {"miami": "Miami", "miami oh": "Miami (OH)"}
    assert school_of("Miami (OH) RedHawks", schools) == "Miami (OH)"
    assert school_of("Miami Hurricanes", schools) == "Miami"
    assert school_of("Nowhere State Somethings", schools) == ""


# ------------------------------------------------------------------ the loader wiring

@pytest.mark.skipif(not (OUT_DIR / "oa_odds_tick.csv").exists(),
                    reason="run scripts/oddsapi_flatten.py first")
def test_the_loader_plans_one_pinned_job_per_table():
    from cfb_system_maker.duckdb_load import _plan_loads

    jobs = {j["name"]: j for j in _plan_loads(OUT_DIR.parent.parent, only=set(OA_TABLES),
                                              include_actionnetwork=False)}
    assert set(jobs) == set(OA_TABLES)
    for name, job in jobs.items():
        assert job["schema"] == "stg" and job["format"] == "csv"
        assert job["columns"], f"{name} would be sniffed by read_csv_auto"
        # the pin maps positionally, so it has to follow the header's order
        with job["paths"][0].open(encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert list(job["columns"]) == header


def test_game_resolution_is_not_duplicated_in_sql():
    """`core` joins on the school string the flatten resolved. A second implementation of
    the mascot strip in SQL would not know about ALIASES and would drift silently."""
    source = (REPO_ROOT / "cfb_system_maker" / "duckdb_core.py").read_text(encoding="utf-8")
    block = source[source.index("def _build_fact_game_odds("):]
    block = block[:block.index("def _add_phase_1_indexes(")]
    assert "h.school = t.home_school" in block
    assert "regexp_replace" not in block, "mascot strip belongs in oddsapi_schema, not SQL"


def test_main_accepts_an_argv_list():
    """`refresh_cfbd._flatten_oddsapi` calls this in-process. A no-arg `main()` raised
    TypeError there and the refresh silently fell back to the CSVs already on disk -- the
    rebuild looked fine because they happened to be fresh."""
    import inspect
    from oddsapi_flatten import main

    assert "argv" in inspect.signature(main).parameters


def test_the_refresh_hook_calls_the_flatten_with_argv():
    source = (REPO_ROOT / "scripts" / "refresh_cfbd.py").read_text(encoding="utf-8")
    assert "_flatten_oddsapi()" in source, "the rebuild has to regenerate these CSVs"
    assert "oddsapi_flatten_main([])" in source
