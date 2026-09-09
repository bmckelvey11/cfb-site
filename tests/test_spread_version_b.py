import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import eval_version_b as vb  # noqa: E402


def _con():
    con = duckdb.connect()
    con.execute("create schema core")
    con.execute("""create table core.fact_game(season int, home_team varchar, away_team varchar,
                   home_points int, away_points int)""")
    con.execute("insert into core.fact_game values (2026, 'Alabama', 'East Carolina', 45, 10),"
                "(2026, 'Florida State', 'Georgia Tech', 20, 24)")
    return con


def test_fetch_scores_keys_on_unordered_pair():
    s = vb.fetch_scores(_con(), [2026])
    assert s[(2026, frozenset({"Alabama", "East Carolina"}))] == ("Alabama", 45, 10)


def test_home_margin_matches_pt_spelling_and_orientation():
    s = vb.fetch_scores(_con(), [2026])
    g = pd.DataFrame({"kick": ["2026-09-05T16:00:00+00:00", "2026-09-05T16:00:00+00:00"],
                      "home": ["Alabama", "Georgia Tech"], "road": ["East Carolina", "Florida St."]})
    m = vb.margins(g, s)
    assert m.tolist() == [35.0, 4.0]          # second game: PT home is CFBD away -> flipped sign


# Amendment B2: capture_offsets and the fixed game set ------------------------------------------

def _snap_log(event_ids, captured_utc, kick="2026-09-12T19:30:00+00:00"):
    n = len(event_ids)
    return pd.DataFrame({"event_id": event_ids, "kick": [kick] * n, "captured_utc": captured_utc,
                         "line_pt": [7.0] * n, "E4": [8.0] * n})


def test_capture_offsets_one_row_per_bucket_from_many_snapshots():
    # game 1 has two captures inside "mon" and one inside "tue" -- must collapse to 2 rows,
    # keeping the earliest capture within each bucket (10.08h, not 15.08h, for "mon").
    log = _snap_log([1, 1, 1], ["20260907T140500Z", "20260907T190500Z", "20260908T223000Z"])
    o = vb.capture_offsets(log)
    assert len(o) == 2
    assert sorted(o.offset_bucket.tolist()) == ["mon", "tue"]
    mon_row = o[o.offset_bucket == "mon"].iloc[0]
    assert mon_row.captured_utc == "20260907T140500Z"


def test_capture_offsets_fixed_game_set_drops_games_missing_a_bucket():
    # game 1: mon, tue, wed.  game 2: mon, tue only -- missing wed.
    log = _snap_log([1, 1, 1, 2, 2],
                     ["20260907T140500Z", "20260908T223000Z", "20260909T120000Z",
                      "20260907T150000Z", "20260908T230000Z"])
    per_bucket = vb.capture_offsets(log)
    kept, dropped = vb.apply_fixed_game_set(per_bucket)
    assert dropped == 1
    assert set(kept.event_id.unique()) == {1}
    assert sorted(kept.offset_bucket.tolist()) == ["mon", "tue", "wed"]


# Amendment B3: the stopping rule ----------------------------------------------------------------

def test_no_verdict_below_eight_clusters_even_with_small_mde():
    tiny_mde = {"clusters": 3, "mde_80": 0.01}   # looks "conclusive" by the retired B1 MDE gate
    assert vb.apply_stopping_rule(tiny_mde, season_ended=True) is None
    assert vb.apply_stopping_rule({"clusters": 7, "mde_80": 0.01}, season_ended=True) is None


def test_verdict_only_at_season_end_with_eight_or_more_clusters():
    assert vb.apply_stopping_rule({"clusters": 20, "mde_80": 5.0}, season_ended=False) is None
    r = vb.apply_stopping_rule({"clusters": 8, "mde_80": 5.0}, season_ended=True)
    assert r is not None and r["clusters"] == 8


# Amendment A5: conditional_on_fitted_predictor marker --------------------------------------------

def test_cluster_ols_marks_conditional_on_fitted_predictor():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.5, 40)
    y = 0.3 * x + rng.normal(0, 1, 40)
    cl = np.repeat(np.arange(4), 10)
    assert vb.cluster_ols(y, x, cl)["conditional_on_fitted_predictor"] is False
    r = vb.cluster_ols(y, x, cl, conditional_on_fitted_predictor=True)
    assert r["conditional_on_fitted_predictor"] is True
