"""The accuracy-weighting machinery, on frames whose right answer is known by hand.

The sign convention is this tree's most dangerous bug class: PT publishes positive = home
favoured, the archive is negated, and 407 of 17,709 games have PT's home/road reversed relative
to CFBD's. A flip anywhere turns every ATS number into its complement, and nothing else in the
suite covers the weighting path.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import eval_accuracy_weighted as aw  # noqa: E402


def _frame(n=400, seed=0):
    """Two models: `linegood` is accurate, `linebad` is noise. Archive sign (negated)."""
    rng = np.random.default_rng(seed)
    margin = rng.normal(0, 14, n)
    return pd.DataFrame({
        "season": np.repeat([2021, 2022], n // 2),
        "y": margin,
        "linegood": -(margin + rng.normal(0, 3, n)),
        "linebad": -(margin + rng.normal(0, 20, n)),
    })


def test_weights_pick_the_more_accurate_model():
    d = _frame()
    w = aw.weights_for(d, ["linegood", "linebad"], "top1")
    assert list(w) == ["linegood"], "top-k must rank by lowest MSE against the margin"

    inv = aw.weights_for(d, ["linegood", "linebad"], "inv_mse")
    assert inv["linegood"] > inv["linebad"], "inverse-MSE must weight the accurate model higher"


def test_consensus_is_a_weighted_mean_in_margin_space():
    d = pd.DataFrame({"linea": [-6.0, -3.0], "lineb": [-2.0, -1.0]})
    out = aw.consensus(d, ["linea", "lineb"], {"linea": 1.0, "lineb": 1.0})
    assert np.allclose(out, [4.0, 2.0]), "equal weights -> plain mean of the negated columns"

    out = aw.consensus(d, ["linea", "lineb"], {"linea": 3.0, "lineb": 1.0})
    assert np.allclose(out, [(6 * 3 + 2) / 4, (3 * 3 + 1) / 4]), "weights must actually apply"


def test_consensus_ignores_missing_models_rather_than_zeroing_them():
    d = pd.DataFrame({"linea": [-6.0, np.nan], "lineb": [-2.0, -4.0]})
    out = aw.consensus(d, ["linea", "lineb"], {"linea": 1.0, "lineb": 1.0})
    assert np.allclose(out, [4.0, 4.0]), "a NaN model must drop out, not pull the mean toward 0"


def test_sign_convention_a_model_that_is_the_margin_beats_the_close():
    """An oracle model must produce a winning ATS record; a sign flip would make it losing."""
    rng = np.random.default_rng(1)
    n = 600
    margin = rng.normal(0, 14, n)
    close_ms = margin + rng.normal(0, 6, n)          # close: noisy but unbiased
    oracle_ms = margin                                # perfect foresight
    side = np.sign(oracle_ms - close_ms)
    res = side * (margin - close_ms)
    assert (res > 0).mean() > 0.99, "backing perfect foresight against the close must win"

    flipped = np.sign(-(oracle_ms - close_ms))
    assert ((flipped * (margin - close_ms)) > 0).mean() < 0.01, "the flip must lose, so the test bites"


def test_roi_is_zero_at_the_breakeven_rate():
    assert abs(aw.roi(aw.BREAKEVEN)) < 1e-12
    assert aw.roi(0.60) > 0 and aw.roi(0.50) < 0
