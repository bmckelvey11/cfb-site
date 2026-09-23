"""Release D, D3: selective prediction trained only on earlier seasons."""
import numpy as np
import pandas as pd
import pytest

from models.tuning.selective import aurc, aurc_vs_full, meta_scores, risk_coverage

COVERAGES = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)


def _frame(seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for season in (2017, 2018, 2019, 2021):
        for week in range(2, 14):
            for i in range(15):
                rows.append({"game_id": season * 10_000 + week * 100 + i, "season": season,
                             "week": week})
    f = pd.DataFrame(rows)
    f["x"] = rng.uniform(0, 2, len(f))
    # Error grows linearly with x and shrinks with week: a pattern a linear model can learn.
    f["resid"] = rng.normal(0, 1, len(f)) * (0.3 + f["x"]) * (1.5 - f["week"] / 20)
    return f


def test_meta_scores_see_only_the_window_seasons():
    f = _frame()
    base = meta_scores(f, ["x"], "resid", 2021, [2018, 2019])
    moved = f.copy()
    moved.loc[moved["season"] == 2021, "resid"] *= 10          # the test season itself
    moved.loc[moved["season"] == 2017, "resid"] *= 10          # outside the window
    pd.testing.assert_series_equal(base, meta_scores(moved, ["x"], "resid", 2021, [2018, 2019]))
    shifted = f.copy()
    shifted.loc[shifted["season"] == 2019, "resid"] *= 3
    assert not base.equals(meta_scores(shifted, ["x"], "resid", 2021, [2018, 2019]))
    assert list(base.index) == list(f.index[f["season"] == 2021])


def test_an_oracle_beats_keeping_everything_and_random_order_does_not():
    f = _frame()
    loss = f["resid"].abs()
    oracle = risk_coverage(loss, loss, f["game_id"], COVERAGES)
    assert [p["coverage"] for p in oracle] == list(COVERAGES)
    risks = [p["mean_loss"] for p in oracle]
    assert risks == sorted(risks, reverse=True) and risks[0] == pytest.approx(loss.mean())
    assert aurc(oracle) < loss.mean()
    noise = pd.Series(np.random.default_rng(9).normal(size=len(f)), index=f.index)
    assert aurc(risk_coverage(loss, noise, f["game_id"], COVERAGES)) == pytest.approx(
        loss.mean(), rel=0.1)


def test_learned_scores_find_the_pattern_and_the_interval_is_reported():
    f = _frame()
    test = f[f["season"] == 2021]
    score = meta_scores(f, ["x"], "resid", 2021, [2018, 2019])
    out = aurc_vs_full(test.assign(loss=test["resid"].abs(), score=score), COVERAGES, draws=500)
    assert out["diff"] < 0 and out["ci95"][1] < 0          # abstaining on high scores helps
    assert out["n_clusters"] == 12
