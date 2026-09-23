"""Release F1: the dynamic-ratings filter nests ridge_v1, stays as-of, and is gated."""
import json

import numpy as np
import pandas as pd
import pytest

from scripts.weekly_dynamic import confirm, fit_decay, fit_kalman, kalman_ppp
from scripts.weekly_ratings import fit_ridge, fit_set, forecast_total
from scripts.weekly_ratings_eval import week_cutoffs

TEAMS = [f"T{i}" for i in range(10)]


def _games(seed=0, weeks=7, slump=None) -> pd.DataFrame:
    """A synthetic season; `slump` = a team whose offense collapses from week 4 on."""
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, weeks + 1):
        order = rng.permutation(TEAMS)
        for i in range(5):
            home, away = order[2 * i], order[2 * i + 1]
            hp, ap = int(rng.integers(10, 15)), int(rng.integers(10, 15))
            hr, ar = int(rng.integers(10, 40)), int(rng.integers(10, 40))
            if slump is not None and week >= 4:
                hr = 3 if home == slump else hr
                ar = 3 if away == slump else ar
            if slump is not None and week < 4:
                hr = 45 if home == slump else hr
                ar = 45 if away == slump else ar
            rows.append({"game_id": week * 100 + i, "season": 2030, "week": week,
                         "kickoff": pd.Timestamp("2030-09-01T16:00Z") + pd.Timedelta(days=7 * week, hours=i),
                         "home": home, "away": away, "neutral": bool(i == 4),
                         "home_reg": hr, "away_reg": ar, "home_poss": hp, "away_poss": ap,
                         "N": (hp + ap) / 2, "ot": 0, "total": hr + ar, "gated": False})
    return pd.DataFrame(rows)


def _all_pairs(r) -> np.ndarray:
    return np.array([forecast_total(r, a, b, False) for a in TEAMS for b in TEAMS if a != b])


def test_zero_drift_is_ridge_v1_and_no_decay_is_ridge_v1():
    g = _games()
    cut = week_cutoffs(g).iloc[-1]
    fs = fit_set(g, cut)
    ridge = _all_pairs(fit_ridge(fs, 40, 8))
    np.testing.assert_allclose(_all_pairs(fit_kalman(fs, 40, 8, 0.0, 0.0)), ridge, atol=1e-6)
    np.testing.assert_allclose(_all_pairs(fit_decay(fs, 40, 8, 1.0, 1.0, 7)), ridge, atol=1e-9)


def test_drift_weighs_recent_weeks_more_than_ridge():
    g = _games(slump="T0")
    fs = fit_set(g, week_cutoffs(g).iloc[-1])
    _, _, flat = kalman_ppp(fs, 40, 0.0)
    _, _, moving = kalman_ppp(fs, 40, 1e-2)
    assert moving.at["T0", "O"] < flat.at["T0", "O"]  # the slump since week 4 counts for more


def test_a_forecast_never_sees_its_own_week_or_later():
    g = _games()
    cut = week_cutoffs(g)[5]
    before = _all_pairs(fit_kalman(fit_set(g, cut), 40, 8, 1e-3, 5e-3))
    changed = g.copy()
    changed.loc[changed["week"] >= 5, "home_reg"] += 30
    after = _all_pairs(fit_kalman(fit_set(changed, cut), 40, 8, 1e-3, 5e-3))
    np.testing.assert_array_equal(before, after)


def test_confirm_refuses_without_a_freeze_or_a_passing_gate(tmp_path):
    frozen, gate = tmp_path / "frozen.json", tmp_path / "gate.json"
    with pytest.raises(SystemExit, match="no frozen candidate"):
        confirm(2026, frozen, gate)
    frozen.write_text(json.dumps({"q_ppp": 0.0, "q_pace": 0.0}), encoding="utf-8")
    with pytest.raises(SystemExit, match="stop rule 1"):
        confirm(2026, frozen, gate)
    frozen.write_text(json.dumps({"q_ppp": 1e-3, "q_pace": 0.0}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no screen gate"):
        confirm(2026, frozen, gate)
    from scripts.pregame_replay_audit import _sha256
    gate.write_text(json.dumps({"frozen_sha256": _sha256(frozen), "gate": {"pass": False}}),
                    encoding="utf-8")
    with pytest.raises(SystemExit, match="stop rule 2"):
        confirm(2026, frozen, gate)


@pytest.mark.slow
def test_zero_drift_matches_ridge_v1_on_a_real_2021_cutoff():
    from cfb_paths import DATA_ROOT
    from scripts.weekly_ratings_eval import load

    games, _ = load(DATA_ROOT, [2021], [])
    cut = week_cutoffs(games).loc[8]
    fs = fit_set(games, cut)
    ridge, kal = fit_ridge(fs, 40, 8), fit_kalman(fs, 40, 8, 0.0, 0.0)
    wk = games[games["week"] == 8]
    a = [forecast_total(ridge, g.home, g.away, g.neutral) for g in wk.itertuples()]
    b = [forecast_total(kal, g.home, g.away, g.neutral) for g in wk.itertuples()]
    np.testing.assert_allclose(b, a, atol=1e-6)
