"""The estimator core every spread result rests on, checked on synthetic data.

Anchor (Frisch-Waugh nesting of R0), gamma_fit (one slope on a consensus deviation) and
wild_cluster_boot (season-cluster inference). None of these had a test outside the scripts'
own ``_check()`` blocks before 2026-09-08.
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
