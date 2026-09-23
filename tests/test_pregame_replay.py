"""A future game and a later line cannot enter a pre-kickoff replay snapshot.

In-memory only: no CFB_DATA_ROOT, no network.
"""
import pandas as pd

from scripts.pregame_replay_audit import line_clock, snapshot

T = pd.Timestamp("2024-10-05T16:00:00Z")


def _pool() -> pd.DataFrame:
    return pd.DataFrame([
        # A: the game being decided, kickoff T.
        {"game_id": 1, "week": 6, "kickoff": T, "home_points": 24, "away_points": 17,
         "vendor_open_label": 48.5},
        # B: same week, kicks off after T, has a final score and a line.
        {"game_id": 2, "week": 6, "kickoff": T + pd.Timedelta(hours=3.5),
         "home_points": 45, "away_points": 38, "vendor_open_label": 61.5},
        # C: previous week, before T.
        {"game_id": 3, "week": 5, "kickoff": T - pd.Timedelta(days=7),
         "home_points": 10, "away_points": 7, "vendor_open_label": 41.0},
        # D: same week, tied with A's kickoff -- not strictly before, so future.
        {"game_id": 4, "week": 6, "kickoff": T, "home_points": 31, "away_points": 28,
         "vendor_open_label": 55.0},
        # E: no kickoff timestamp -- cannot be placed in time, so never visible.
        {"game_id": 5, "week": 6, "kickoff": pd.NaT, "home_points": 3, "away_points": 0,
         "vendor_open_label": 40.0},
    ])


def test_snapshot_keeps_past_and_drops_future():
    seen = snapshot(_pool(), T)
    assert set(seen["game_id"]) == {3}  # C only
    # B's score and line are absent: no row carries B's values.
    assert 2 not in set(seen["game_id"])
    assert 61.5 not in set(seen["vendor_open_label"])
    assert 45 not in set(seen["home_points"])


def test_tied_kickoff_and_self_are_excluded():
    seen = set(snapshot(_pool(), T)["game_id"])
    assert 1 not in seen  # A's own result is not visible at A's kickoff
    assert 4 not in seen  # tie at T is not "strictly earlier"
    assert 5 not in seen  # NaT fails closed


def test_shifting_future_score_does_not_change_snapshot():
    pool = _pool()
    before = snapshot(pool, T)
    shifted = pool.copy()
    shifted.loc[shifted["game_id"] == 2, ["home_points", "away_points"]] = [0, 99]
    shifted.loc[shifted["game_id"] == 2, "vendor_open_label"] = 99.5
    pd.testing.assert_frame_equal(before, snapshot(shifted, T))


def test_line_clock_never_promotes_a_label_to_a_timestamp():
    keys = ["overUnder", "overUnderOpen", "provider", "spread", "spreadOpen"]
    clock, ev = line_clock(keys, {"skipped": True})
    assert clock == "vendor_open_label_only"
    assert ev["time_like_line_keys"] == []
    # A time-like key is flagged for review, not trusted as the open's clock.
    clock, ev = line_clock(keys + ["updatedAt"], {"skipped": True})
    assert clock == "vendor_open_label_only"
    assert ev["time_like_line_keys"] == ["updatedAt"]
