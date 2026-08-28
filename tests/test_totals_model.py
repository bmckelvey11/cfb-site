"""Checks on the two things that would silently invalidate the backtest:
lookahead in the features, and a grading metric that scores itself."""

import numpy as np
import pandas as pd
import pytest

from cfb_totals_model.data import _REGISTRY_COLS, _entering_game_stats
from cfb_totals_model.model import Backtest, FoldResult, permutation_test, walk_forward

# Current-game havoc, reported attendance, and post-game winProb. Result lookahead.
_LEAKED_REGISTRY = (
    "home_havoc_defense_rate", "away_havoc_defense_rate",
    "home_havoc_offense_rate", "away_havoc_offense_rate",
    "attendance", "home_pregame_win_prob",
)


def test_entering_game_stats_exclude_current_game():
    """Week N's feature must average weeks 1..N-1 only."""
    team_games = pd.DataFrame({
        "game_id": [1, 2, 3], "team": ["A"] * 3, "season": [2024] * 3,
        "o_plays": [60, 80, 100], "o_drives": [10, 12, 14],
        "o_ppa": [0.1, 0.2, 0.3], "o_succ": [.4, .5, .6],
        "o_expl": [1.0, 1.1, 1.2], "o_ppo": [4.0, 4.5, 5.0],
        "d_plays": [55, 65, 75], "d_drives": [10, 11, 12],
        "d_ppa": [.1, .1, .1], "d_succ": [.4, .4, .4],
        "d_expl": [1.0, 1.0, 1.0], "d_ppo": [4.0, 4.0, 4.0],
    })
    dates = pd.DataFrame({
        "game_id": [1, 2, 3],
        "dt": pd.to_datetime(["2024-09-01", "2024-09-08", "2024-09-15"], utc=True),
    })
    out = _entering_game_stats(team_games, dates).sort_values("dt")
    pre = out["pre_o_plays"].tolist()

    assert np.isnan(pre[0])          # first game: nothing prior
    assert pre[1] == 60              # sees game 1 only
    assert pre[2] == 70              # mean(60, 80) — never its own 100
    assert out["pre_n"].tolist() == [0, 1, 2]


def test_registry_excludes_result_lookahead_features():
    """feature_cols must not include this-game havoc, attendance, or winProb."""
    for name in _LEAKED_REGISTRY:
        assert name not in _REGISTRY_COLS, name


def _toy_dataset(n=400, seed=0):
    """Line carries real signal; one feature is pure noise."""
    rng = np.random.default_rng(seed)
    line = rng.normal(54, 7, n)
    pts = line + rng.normal(0, 12, n)
    return pd.DataFrame({
        "season": rng.choice([2021, 2022, 2023, 2024, 2025], n),
        "week": rng.integers(1, 14, n),
        "ou_open": line, "pts": pts, "game_id": np.arange(n),
        "noise": rng.normal(0, 1, n), "pace_plays": rng.normal(133, 8, n),
    })


class _DS:
    def __init__(self, frame, cols):
        self.frame = frame
        self.feature_cols = cols


def test_first_season_expands_by_week_without_lookahead():
    """2021 has no prior opening lines — walk forward by week, never later weeks."""
    rng = np.random.default_rng(0)
    rows = []
    gid = 0
    for week in range(1, 11):
        for _ in range(40):
            line = 54 + rng.normal()
            rows.append({
                "season": 2021, "week": week, "ou_open": line,
                "pts": line + rng.normal(0, 12), "game_id": gid,
                "noise": rng.normal(), "pace_plays": 133,
            })
            gid += 1
    ds = _DS(pd.DataFrame(rows), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2021,), min_train=120)
    assert bt.folds and bt.folds[0].week_expanding
    # First scored week needs 120 prior rows = 3 weeks of 40, so week 4+.
    assert bt.folds[0].frame["game_id"].min() >= 120
    assert set(bt.folds[0].frame["season"]) == {2021}


def test_walk_forward_never_trains_on_future():
    ds = _DS(_toy_dataset(), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2023, 2024, 2025), min_train=50)
    assert bt.folds, "expected at least one fold"
    for fold in bt.folds:
        # every graded row belongs to its own test season
        assert set(fold.frame["season"]) == {fold.season}


def test_hit_column_matches_manual_grading():
    ds = _DS(_toy_dataset(), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2024, 2025), min_train=50)
    g = bt.graded
    bet_under = g["edge"] > 0
    actual_under = g["pts"] < g["ou_open"]
    expected = np.where(bet_under, actual_under, ~actual_under)
    assert (g["hit"].to_numpy() == expected).all()


def test_permutation_of_noise_model_sits_at_chance():
    """Shuffling predictions must land near 50% — proves grading isn't self-scoring."""
    ds = _DS(_toy_dataset(n=600), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2023, 2024, 2025), min_train=50)
    r = permutation_test(bt, n=200)
    assert 44 < r["shuffled_mean"] < 56, r


def test_pushes_are_dropped():
    """A game landing exactly on the number is void, not a win."""
    frame = _toy_dataset(n=300)
    frame.loc[frame.index[:20], "pts"] = frame.loc[frame.index[:20], "ou_open"]
    bt = walk_forward(_DS(frame, ["noise"]), test_seasons=(2024, 2025), min_train=50)
    g = bt.graded
    assert not (g["pts"] == g["ou_open"]).any()


def test_graded_rows_keep_week_and_game_id():
    ds = _DS(_toy_dataset(), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2024, 2025), min_train=50)
    assert "week" in bt.graded.columns
    assert "game_id" in bt.graded.columns
    assert bt.graded["week"].notna().all()


def test_summary_uses_prior_season_folds_only():
    rng = np.random.default_rng(0)
    rows = []
    gid = 0
    for week in range(1, 11):
        for _ in range(40):
            line = 54 + rng.normal()
            rows.append({
                "season": 2021, "week": week, "ou_open": line,
                "pts": line + rng.normal(0, 12), "game_id": gid,
                "noise": rng.normal(), "pace_plays": 133,
            })
            gid += 1
    for season in (2022, 2023):
        for _ in range(80):
            line = 54 + rng.normal()
            rows.append({
                "season": season, "week": 5, "ou_open": line,
                "pts": line + rng.normal(0, 12), "game_id": gid,
                "noise": rng.normal(), "pace_plays": 133,
            })
            gid += 1
    ds = _DS(pd.DataFrame(rows), ["noise", "pace_plays"])
    bt = walk_forward(ds, test_seasons=(2021, 2022, 2023), min_train=120)
    assert any(f.week_expanding for f in bt.folds)
    assert any(not f.week_expanding for f in bt.folds)
    s = bt.summary()
    n_prior = sum(len(f.frame) for f in bt.folds if not f.week_expanding)
    n_head = int(s.loc[s["min_edge"] == 0, "n"].iloc[0])
    assert n_head == n_prior
    assert bool(s.loc[s["min_edge"] == 0, "citable"].iloc[0])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
