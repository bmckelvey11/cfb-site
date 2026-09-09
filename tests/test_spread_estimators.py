"""The estimator core every spread result rests on, checked on synthetic data.

Anchor (Frisch-Waugh nesting of R0), gamma_fit (one slope on a consensus deviation),
wild_cluster_boot (season-cluster inference), holm (multiplicity correction) and pick_1se
(the walk-forward hyperparameter rule). None of these had a test outside the scripts' own
``_check()`` blocks before 2026-09-08.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402


def _panel(n=3000, gamma=0.3, noise=1.0, seed=0):
    """Archive-convention frame: `line` negative = home favoured, `y` in margin space."""
    rng = np.random.default_rng(seed)
    mkt = rng.normal(0, 14, n)
    dev = rng.normal(0, 3, n)
    y = 0.5 + 1.02 * mkt + gamma * dev + rng.normal(0, noise, n)
    season = np.repeat(np.arange(2006, 2026), n // 20)
    df = pd.DataFrame({"line": -mkt, "y": y, "dev": dev, "season": season})
    return df.iloc[: n - 500], df.iloc[n - 500:]


def test_anchor_nests_r0_when_correction_is_zero():
    tr, te = _panel()
    a = sweep.Anchor(tr, te, "line")
    zero_tr, zero_te = np.zeros(len(tr)), np.zeros(len(te))
    pred, g = sweep.gamma_fit(a, zero_tr, zero_te)
    assert np.allclose(pred, a.r0_te, atol=1e-8)
    assert g == 0.0
    # R0 is the plain OLS of y on [1, mkt]
    X = np.column_stack([np.ones(len(tr)), -tr["line"].to_numpy()])
    b = np.linalg.lstsq(X, tr["y"].to_numpy(), rcond=None)[0]
    assert np.allclose(a.r0_te, b[0] + b[1] * -te["line"].to_numpy(), atol=1e-8)


def test_gamma_fit_recovers_the_planted_slope():
    tr, te = _panel(gamma=0.3)
    a = sweep.Anchor(tr, te, "line")
    pred, g = sweep.gamma_fit(a, tr["dev"].to_numpy(), te["dev"].to_numpy())
    assert abs(g - 0.3) < 0.03
    resid = te["y"].to_numpy() - pred
    assert resid.std() < 1.2  # the planted noise is 1.0; the fit should be near it


def test_wild_cluster_boot_null_and_signal():
    rng = np.random.default_rng(1)
    clusters = np.repeat(np.arange(20), 100)
    null = rng.normal(0, 1, 2000)
    mean, (lo, hi), p = base.wild_cluster_boot(null, clusters, n_boot=400)
    assert lo < 0 < hi and p > 0.01
    signal = null + 0.5
    mean, (lo, hi), p = base.wild_cluster_boot(signal, clusters, n_boot=400)
    assert lo > 0 and p < 0.01
    assert abs(mean - signal.mean()) < 1e-12


def test_wild_cluster_boot_calibration_under_the_null():
    """A single null draw (above) can't catch a miscalibrated bootstrap -- it could pass
    by luck. Run many independent null draws instead and check the rejection rate at
    alpha=0.1 lands within binomial sampling error of 0.1 (draw/boot counts kept small so
    this stays off the slow-test list)."""
    rng = np.random.default_rng(7)
    n_clusters, per_cluster, n_boot, n_draws, alpha = 20, 30, 200, 300, 0.1
    clusters = np.repeat(np.arange(n_clusters), per_cluster)
    rejections = 0
    for _ in range(n_draws):
        d = rng.normal(0, 1, n_clusters * per_cluster)
        _, _, p = base.wild_cluster_boot(d, clusters, n_boot=n_boot)
        rejections += p < alpha
    rate = rejections / n_draws
    se_binom = np.sqrt(alpha * (1 - alpha) / n_draws)  # binomial SE of the rejection rate
    assert abs(rate - alpha) < 4 * se_binom


def test_holm_ties_and_monotonicity_step():
    """Hand-computed Holm step-down. Sorted ascending, multipliers are m..1:
    raw products .005*5=.025, .01*4=.04, .01*3=.03, .04*2=.08, .20*1=.20.
    p[1] and p[2] tie at 0.01 -- their raw products differ (.04 vs .03) but the
    running-max (monotonicity) step forces the smaller one up to .04, so both land on
    the same adjusted value. That is Holm's step-down guarantee, exercised by a tie."""
    p = np.array([0.005, 0.01, 0.01, 0.04, 0.20])
    expected = np.array([0.025, 0.04, 0.04, 0.08, 0.20])
    got = sweep.holm(p)
    assert np.allclose(got, expected)
    assert got[1] == got[2]


def test_pick_1se_known_curve():
    """Grid ordered least -> most conservative: params 0.0, 1.0 (best), 2.0, 3.0.
    Candidate 2.0 sits just inside one SE of the best mean; 3.0 sits just outside.
    The rule should return 2.0 -- the most-shrunk point still within tolerance, not the
    best point itself and not the one that misses."""
    best = np.array([0.0] * 20 + [2.0] * 20)  # mean 1.0, std(ddof=1) ~1.0127
    se = best.std(ddof=1) / np.sqrt(len(best))  # ~0.1601
    cands = [
        (0.0, np.full(40, 5.0)),
        (1.0, best),
        (2.0, np.full(40, 1.0 + se - 0.001)),  # just inside best + 1SE
        (3.0, np.full(40, 1.0 + se + 0.001)),  # just outside
    ]
    assert sweep.pick_1se(cands) == 2.0

    # Edge hit: when the best validation error sits at the most conservative grid point,
    # the rule must return that point -- the live sweep's diagnostic
    # (`v == str(grids[m][-1])` in eval_combination_sweep.sweep) flags this as the rule
    # running to the grid edge.
    edge_cands = [
        (0.0, np.full(40, 5.0)),
        (1.0, np.full(40, 3.0)),
        (2.0, np.array([1.0] * 20 + [3.0] * 20)),  # best, and the last (most conservative) param
    ]
    assert sweep.pick_1se(edge_cands) == 2.0
