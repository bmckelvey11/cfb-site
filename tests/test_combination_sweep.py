"""Checks on the combination sweep's machinery.

The thing that would silently invalidate the whole run is a lookahead leak in the nested
hyperparameter selection, so that gets a direct test rather than an eyeball.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"
))

sweep_mod = pytest.importorskip("eval_combination_sweep")


def test_deviations_sign_convention():
    """Columns hold SPREADS; deviations must come back in MARGIN space."""
    frame = pd.DataFrame({"m1": [-7.0], "m2": [-3.0], "line": [-6.0]})
    dev, mkt = sweep_mod.deviations(frame, ["m1", "m2"], "line")
    assert mkt[0] == pytest.approx(6.0)          # market likes home by 6
    assert dev[0, 0] == pytest.approx(1.0)       # m1 likes home by 7 -> +1 vs the line
    assert dev[0, 1] == pytest.approx(-3.0)      # m2 likes home by 3 -> -3 vs the line


def test_deviations_preserves_missing():
    frame = pd.DataFrame({"m1": [-7.0, np.nan], "line": [-6.0, -2.0]})
    dev, _ = sweep_mod.deviations(frame, ["m1"], "line")
    assert np.isfinite(dev[0, 0]) and np.isnan(dev[1, 0])


def test_pick_1se_prefers_the_conservative_end():
    """A hair-worse but more conservative value must win -- that is the whole rule."""
    rng = np.random.default_rng(0)
    noise = rng.normal(size=4000)
    best = (noise + 0.00) ** 2          # marginally lowest MSE
    close = (noise + 0.01) ** 2         # within one SE of it
    far = (noise + 3.0) ** 2            # clearly worse
    # grid order is least -> most conservative
    assert sweep_mod.pick_1se([("loose", best), ("tight", close)]) == "tight"
    assert sweep_mod.pick_1se([("loose", best), ("tight", far)]) == "loose"


def test_pick_1se_ignores_failed_fits():
    e = np.ones(200)
    assert sweep_mod.pick_1se([("a", e), ("b", None)]) == "a"
    assert sweep_mod.pick_1se([("a", None), ("b", None)]) is None


def test_trimmed_mean_drops_the_tails():
    dev = np.array([[-100.0, 1.0, 2.0, 3.0, 100.0]])
    assert sweep_mod.trimmed_mean(dev, 0.0)[0] == pytest.approx(1.2)
    assert sweep_mod.trimmed_mean(dev, 0.25)[0] == pytest.approx(2.0)


def test_trimmed_mean_tolerates_missing():
    dev = np.array([[np.nan, 1.0, 2.0, 3.0, np.nan]])
    assert sweep_mod.trimmed_mean(dev, 0.2)[0] == pytest.approx(2.0)


def test_holm_is_monotone_and_bounded():
    p = np.array([0.001, 0.02, 0.5])
    adj = sweep_mod.holm(p)
    assert adj[0] == pytest.approx(0.003)
    assert np.all(np.diff(adj) >= 0) and np.all(adj <= 1)


def test_holm_passes_nan_through():
    adj = sweep_mod.holm(np.array([0.01, np.nan]))
    assert np.isfinite(adj[0]) and np.isnan(adj[1])


def _toy(seasons=10, per=300, seed=1):
    """Panel where one model is informative and the rest are the line plus noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2000, 2000 + seasons):
        for i in range(per):
            line = rng.normal(0, 10)
            y = -line + rng.normal(0, 14)
            rows.append({
                "season": s, "pt_week": i % 15, "y": y, "line": line, "lineopen": line,
                "good": line - 0.30 * (y + line) / 2, "noise": line + rng.normal(0, 6),
            })
    df = pd.DataFrame(rows)
    df["wk"] = df["season"] * 100 + df["pt_week"]
    return df.reset_index(drop=True), ["good", "noise"]


def test_selection_never_sees_the_evaluated_season():
    """Corrupting season s must not change the hyperparameter chosen FOR season s."""
    df, models = _toy()
    sweep_mod.base.BURN_IN_THROUGH = 2004

    _, chosen_a, _, _ = sweep_mod.sweep(df, models, "line", verbose=False)

    poisoned = df.copy()
    tgt = poisoned["season"] == 2008
    poisoned.loc[tgt, "good"] = poisoned.loc[tgt, "line"] - 40.0  # wreck that season only
    _, chosen_b, _, _ = sweep_mod.sweep(poisoned, models, "line", verbose=False)

    a = chosen_a[chosen_a.season == 2008].set_index("method")["param"]
    b = chosen_b[chosen_b.season == 2008].set_index("method")["param"]
    shared = a.index.intersection(b.index)
    assert len(shared) > 0
    assert (a[shared] == b[shared]).all(), "hyperparameter selection leaked season 2008"


def test_anchor_reproduces_the_parent_three_parameter_fit():
    """Frisch-Waugh claim: R0 + gamma*stripped(dev) == joint fit of y ~ b0 + b1*mkt + dev.

    If this fails the sweep is fitting a DIFFERENT estimator than the published E4, and
    every comparison against R0 -- including Clark-West, which needs nesting -- is void.
    """
    df, models = _toy(seasons=6, per=400, seed=7)
    tr, te = df[df.season < 2005], df[df.season == 2005]

    a = sweep_mod.Anchor(tr, te, "line")
    d_tr, _ = sweep_mod.deviations(tr, models, "line")
    d_te, _ = sweep_mod.deviations(te, models, "line")
    cons_tr, cons_te = np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1)
    anchored, _ = sweep_mod.gamma_fit(a, cons_tr, cons_te)

    # the parent script's specification, written out longhand
    mkt_tr = -tr["line"].to_numpy(float)
    mkt_te = -te["line"].to_numpy(float)
    ok = np.isfinite(mkt_tr) & np.isfinite(cons_tr)
    X = np.column_stack([np.ones(ok.sum()), mkt_tr[ok], cons_tr[ok]])
    beta = np.linalg.lstsq(X, tr["y"].to_numpy()[ok], rcond=None)[0]
    joint = np.column_stack([np.ones(len(te)), mkt_te, np.nan_to_num(cons_te)]) @ beta

    assert np.allclose(anchored, joint, atol=1e-8)


def test_zero_correction_returns_r0_exactly():
    """Nesting, stated directly: no correction must land on R0, not near it."""
    df, models = _toy(seasons=6, per=200, seed=3)
    tr, te = df[df.season < 2005], df[df.season == 2005]
    a = sweep_mod.Anchor(tr, te, "line")
    d_tr, _ = sweep_mod.deviations(tr, models, "line")
    d_te, _ = sweep_mod.deviations(te, models, "line")
    # psi = 0 is E8's "apply no correction" setting
    pred, _ = sweep_mod.fit_E8(a, tr, te, models, models, {}, "line", 0.0)
    assert np.allclose(pred, a.r0_te, atol=1e-10)


def test_ewa_weights_use_only_prior_weeks():
    """The first chronological block has no history, so it cannot produce a consensus."""
    df, models = _toy(seasons=3, per=50)
    ewa = sweep_mod.precompute_ewa(df, models, "line", [0.01])
    first = df.index[df["wk"] == df["wk"].min()].to_numpy()
    assert np.isnan(ewa[0.01][first]).all()
    assert np.isfinite(ewa[0.01][df.index[df["wk"] == df["wk"].max()].to_numpy()]).any()


def test_coverage_filter_is_not_a_tenure_test():
    """A complete record must qualify regardless of when the model launched.

    Measuring coverage over the whole training history silently excludes every model that
    did not exist in season one -- including, in the real panel, the two best forecasters.
    """
    rng = np.random.default_rng(11)
    rows = []
    for s in range(2000, 2010):
        for i in range(200):
            line = rng.normal(0, 10)
            rows.append({
                "season": s, "pt_week": i % 15, "y": -line + rng.normal(0, 14),
                "line": line, "lineopen": line,
                "veteran": line + rng.normal(0, 5),          # present every season
                "newcomer": line + rng.normal(0, 5) if s >= 2008 else np.nan,
            })
    df = pd.DataFrame(rows)
    tr, te = df[df.season < 2009], df[df.season == 2009]

    cols, active = sweep_mod.regressor_cols(tr, te, ["veteran", "newcomer"])
    assert set(active) == {"veteran", "newcomer"}
    assert set(cols) == {"veteran", "newcomer"}, "a complete recent record must qualify"

    legacy, _ = sweep_mod.regressor_cols(tr, te, ["veteran", "newcomer"], legacy=True)
    assert set(legacy) == {"veteran"}, "the old filter should drop the newcomer"
