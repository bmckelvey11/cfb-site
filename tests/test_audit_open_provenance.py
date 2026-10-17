"""Open-provenance audit helpers: which Bovada row counts, and the match summary. In-memory."""
import pandas as pd

from scripts.audit_open_provenance import _match, first_open, missing_by


def test_first_open_reads_the_first_bovada_row_only():
    g = {"lines": [{"provider": "DraftKings", "spreadOpen": -3, "overUnderOpen": 50},
                   {"provider": "Bovada", "spreadOpen": -7, "overUnderOpen": None},
                   {"provider": "Bovada", "spreadOpen": -6, "overUnderOpen": 55}]}
    assert first_open(g) == (-7, None)
    assert first_open({"lines": None}) == (None, None)


def test_match_buckets():
    m = _match(pd.Series([-7.0, -3.0, 10.0, 1.0]), pd.Series([-7.0, -3.5, 11.0, 4.0]))
    assert m == {"n": 4, "exact_pct": 25.0, "within_0_5_pct": 50.0, "within_1_pct": 75.0, "median_abs": 0.75}


def test_missing_by_conference_counts_a_game_once_per_conference():
    d = pd.DataFrame({"game_id": [1, 2], "season_type": "regular", "week": [1, 1],
                      "home_conf": ["SEC", "SEC"], "away_conf": ["SEC", "ACC"],
                      "spread_open": [-3.0, None], "total_open": [50.0, 45.0]})
    t = missing_by(d, "conference")
    assert t.loc["SEC", "games"] == 2 and t.loc["SEC", "with_open"] == 1
    assert t.loc["ACC", "missing_pct"] == 100.0
