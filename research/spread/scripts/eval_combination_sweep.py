"""Market-anchored combination sweep -- E6 through E14.

Estimator core for the spread tree, imported by the live scripts; main() reproduces the
archived margin-era tables (archive/spread-margin-era/).

Implements archive/spread-margin-era/prediction-tracker-model-eval-plan-addendum.md. Read that first: the
repair/exploratory split, the hyperparameter grids, the nested selection rule, the
stability gate and the multiplicity budget are all fixed there, before any of this ran.

    python research/spread/scripts/eval_combination_sweep.py            # full run
    python research/spread/scripts/eval_combination_sweep.py --quick    # fewer bootstrap draws

Everything below works in RESIDUAL space. For each game:

    mkt   = benchmark predicted margin (= -spread)
    d_i   = f_i - mkt                 model i's deviation from the line
    r     = y - mkt                   what any correction has to predict

and every prediction is `mkt + correction`. That centring is the whole point of the
addendum -- E5 shrank raw forecasts toward zero, which encodes "no forecast is
informative, including the line". Here the market is the origin.

MISSINGNESS. Consensus methods average the deviations actually present. Regression
methods zero-fill scattered gaps in the residual design, which says "this model has no
opinion, so it does not move us off the line" -- it is NOT imputation from co-forecasters
(parent plan section 2), because a zero fill is a function of the benchmark alone and
carries no information from the other columns in the row.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", r"Mean of empty slice", RuntimeWarning)
warnings.filterwarnings("ignore", r"All-NaN slice", RuntimeWarning)
warnings.filterwarnings("ignore", module="sklearn")

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))

import cfb_paths  # noqa: E402
import eval_prediction_tracker_models as base  # noqa: E402

OUT_DIR = cfb_paths.PROCESSED
INNER_VAL_SEASONS = 3   # last N training seasons are held out to pick hyperparameters
MIN_TRAIN_ROWS = 500
COL_COVERAGE = 0.8      # a model needs this much training coverage to be a regressor
STABILITY_FLOOR = 0.60  # addendum section 5: beat R0 in fewer seasons than this -> not viable
DEGENERATE_CORR = 0.01  # mean |correction| below this = the method IS the line, not a method

# ---- grids (addendum section 3). Each list runs LEAST -> MOST conservative, and the
# 1-SE rule takes the last entry that is within one SE of the best. The ordering is the
# pre-registration: it is what stops "conservative" being chosen after seeing the fits.
GRIDS = {
    "E6": [0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0],                 # ridge lambda
    "E7": [5, 10, 20, 40, 80, "all"],                               # screen K
    "E8": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0],  # shrink psi
    "E9": [3, 2, 1],                                                # n components
    "E10": [0.001, 0.01, 0.1, 1.0],                                 # lasso lambda
    "E11": [0.0, 0.1, 0.2, 0.3, 0.4],                               # trim per tail
    "E12": [(a, l) for a in (0.1, 1.0, 10.0, 100.0, 1000.0) for l in (0.1, 0.5, 0.9)],
    "E13": [0.1, 0.01, 0.001],                                      # learning rate eta
    "E14": [3, 2, 1],                                               # subset size k
}
METHODS = ["E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14"]
EXPLORATORY = ["E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14"]
CSR_SCREEN = 10  # CSR screens to this many models first; C(10,3)=120 is tractable

# For these the conservative endpoint is the edge of the PARAMETER SPACE, not of the grid:
# psi=0 is "apply no correction", r=1 is one component, k=1 is one regressor, K=all is the
# whole active set. Landing there is a result about the data, not evidence of a short grid.
SATURATED = {"E7", "E8", "E9", "E14"}

# Post-hoc widened grids (--wide). The addendum's stop rule forbids widening the registered
# search space, so this is EXPLORATORY ONLY: it exists to show whether a clipped selection
# would have gone further, and is excluded from every gate.
WIDE_GRIDS = dict(
    GRIDS,
    E6=GRIDS["E6"] + [1e5, 1e6, 1e7],
    E10=GRIDS["E10"] + [10.0, 100.0],
    E11=GRIDS["E11"] + [0.45],
    E12=GRIDS["E12"] + [(a, l) for a in (1e4, 1e5) for l in (0.1, 0.5, 0.9)],
    E13=GRIDS["E13"] + [1e-4, 1e-5],
)


# --------------------------------------------------------------- residual-space design


def deviations(frame, cols, bench_col):
    """d_i = f_i - mkt in margin space. NaN preserved where a model is absent."""
    mkt = -frame[bench_col].to_numpy(float)
    if not cols:
        return np.zeros((len(frame), 0)), mkt
    fcast = -frame[cols].to_numpy(float)
    return fcast - mkt[:, None], mkt


def regressor_cols(tr, te, models, legacy=False):
    """Models active this season with enough training coverage to carry a coefficient.

    Coverage is measured over the seasons the model actually PUBLISHED IN, not over the whole
    training history. Measuring it over the whole history silently demands that a model have
    existed since 2001: a strong forecaster that launched in 2015 covers well under 80% of
    all prior games no matter how complete its record is, so it never becomes a regressor.
    That is not a coverage test, it is a tenure test, and the parent plan specifies "the
    model set active in that season".

    `legacy=True` reproduces the original whole-history filter for the correction check in
    `archive/spread-margin-era/scripts/diag_eligibility_tenure.py`.
    """
    active = [m for m in models if te[m].notna().mean() >= 0.5]
    if legacy:
        return [m for m in active if tr[m].notna().mean() > COL_COVERAGE], active
    cols = []
    for m in active:
        seasons = tr.loc[tr[m].notna(), "season"].unique()
        if len(seasons) == 0:
            continue
        sub = tr.loc[tr["season"].isin(seasons), m]
        if len(sub) and sub.notna().mean() > COL_COVERAGE:
            cols.append(m)
    return cols, active


def screened(skill, active, k):
    """Top-k models by prior skill (lower ΔMSE is better), restricted to the active set."""
    if k == "all":
        return list(active)
    ranked = [m for m in sorted(skill, key=skill.get) if m in active]
    return ranked[:k] or list(active)[:k]


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


class Anchor:
    """R0 as the origin of every method, by Frisch-Waugh.

    The addendum benchmarks each method against R0 (`b0 + b1*mkt`), not the raw line, so
    that "the models add information" is not bundled with "the line is mildly
    under-extrapolated". For that comparison to be clean -- and for Clark-West, which
    requires the big model to NEST the small one -- every method must be able to reproduce
    R0 exactly by setting its correction to zero.

    Fitting `y - mkt ~ deviations` does NOT do that: it pins the market coefficient at 1
    and so cannot nest a free b1. Instead partial `[1, mkt]` out of both the target and
    every deviation column on the TRAINING data, fit the method on what is left, and add
    the correction back onto R0. By Frisch-Waugh the fitted values are identical to a
    joint fit of `y ~ b0 + b1*mkt + correction` with the first two terms unpenalised --
    which is exactly the specification the parent plan used for E4.
    """

    def __init__(self, tr, te, bench_col):
        mkt_tr = -tr[bench_col].to_numpy(float)
        y_tr = tr["y"].to_numpy()
        self.mkt_te = -te[bench_col].to_numpy(float)
        self.Xtr = np.column_stack([np.ones(len(mkt_tr)), np.nan_to_num(mkt_tr)])
        self.Xte = np.column_stack([np.ones(len(self.mkt_te)), np.nan_to_num(self.mkt_te)])
        self.ok = np.isfinite(mkt_tr) & np.isfinite(y_tr)
        self.usable = self.ok.sum() >= MIN_TRAIN_ROWS
        if not self.usable:
            return
        b = ols(self.Xtr[self.ok], y_tr[self.ok])
        self.r0_te = self.Xte @ b
        self.u = y_tr - self.Xtr @ b  # target with R0 already removed

    def strip(self, v_tr, v_te):
        """Project a deviation series (1-D or 2-D) off [1, mkt], train-estimated."""
        v_tr = np.nan_to_num(np.asarray(v_tr, float))
        v_te = np.nan_to_num(np.asarray(v_te, float))
        proj = np.linalg.lstsq(self.Xtr[self.ok], v_tr[self.ok], rcond=None)[0]
        return v_tr - self.Xtr @ proj, v_te - self.Xte @ proj


def gamma_fit(a, dev_tr, dev_te):
    """One free slope on a single consensus direction, on top of R0.

    The cheapest possible correction, which is the point: the diagnostic says estimation
    variance is what kills this, so every parameter has to earn its place.
    """
    g_tr, g_te = a.strip(dev_tr, dev_te)
    beta = ols(np.column_stack([np.ones(a.ok.sum()), g_tr[a.ok]]), a.u[a.ok])
    return a.r0_te + beta[0] + beta[1] * g_te, float(beta[1])


def trimmed_mean(dev, tau):
    """Row-wise quantile-trimmed mean of the available deviations."""
    if tau <= 0:
        return np.nanmean(dev, axis=1)
    lo = np.nanquantile(dev, tau, axis=1, keepdims=True)
    hi = np.nanquantile(dev, 1 - tau, axis=1, keepdims=True)
    return np.nanmean(np.where((dev >= lo) & (dev <= hi), dev, np.nan), axis=1)


# ------------------------------------------------------------------------- estimators
# Every estimator has the same signature and returns (prediction, correction_coefficient).
# `correction_coefficient` is the scalar the stability gate watches: gamma, psi, or the
# summed loading on the residual design (addendum section 5).
#
# All of them build on an Anchor, so setting the correction to zero reproduces R0 exactly.


def fit_E6(a, tr, te, cols, active, skill, bench_col, param):
    """Market-residual ridge. Penalty on the deviations only; R0 is the origin."""
    from sklearn.linear_model import Ridge

    if not cols:
        return None, np.nan
    d_tr, _ = deviations(tr, cols, bench_col)
    d_te, _ = deviations(te, cols, bench_col)
    g_tr, g_te = a.strip(d_tr, d_te)
    rg = Ridge(alpha=param).fit(g_tr[a.ok], a.u[a.ok])
    return a.r0_te + rg.predict(g_te), float(rg.coef_.sum())


def fit_E7(a, tr, te, cols, active, skill, bench_col, param):
    """E4's form with K chosen by rule instead of frozen at 20."""
    keep = screened(skill, active, param)
    if not keep:
        return None, np.nan
    d_tr, _ = deviations(tr, keep, bench_col)
    d_te, _ = deviations(te, keep, bench_col)
    return gamma_fit(a, np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1))


def fit_E8(a, tr, te, cols, active, skill, bench_col, param):
    """Stock-Watson generalized shrinkage: fit the unrestricted correction, then scale it."""
    if not cols:
        return None, np.nan
    d_tr, _ = deviations(tr, cols, bench_col)
    d_te, _ = deviations(te, cols, bench_col)
    g_tr, g_te = a.strip(d_tr, d_te)
    beta = ols(g_tr[a.ok], a.u[a.ok])
    return a.r0_te + param * (g_te @ beta), float(param)


def fit_E9(a, tr, te, cols, active, skill, bench_col, param):
    """Principal components of the DEVIATIONS (not the raw spreads), then a small regression."""
    from sklearn.decomposition import PCA

    if len(cols) <= param:
        return None, np.nan
    d_tr, _ = deviations(tr, cols, bench_col)
    d_te, _ = deviations(te, cols, bench_col)
    g_tr, g_te = a.strip(d_tr, d_te)
    pca = PCA(n_components=param).fit(g_tr[a.ok])
    s_tr, s_te = pca.transform(g_tr[a.ok]), pca.transform(g_te)
    beta = ols(np.column_stack([np.ones(len(s_tr)), s_tr]), a.u[a.ok])
    return a.r0_te + beta[0] + s_te @ beta[1:], float(beta[1:].sum())


def fit_E10(a, tr, te, cols, active, skill, bench_col, param):
    """Market-anchored peLASSO: LASSO picks the subset, survivors are equal-weighted."""
    from sklearn.linear_model import Lasso

    if not cols:
        return None, np.nan
    d_tr, _ = deviations(tr, cols, bench_col)
    d_te, _ = deviations(te, cols, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    las = Lasso(alpha=param, max_iter=5000).fit(g_tr[a.ok], a.u[a.ok])
    keep = [c for c, w in zip(cols, las.coef_) if w != 0]
    if not keep:
        return None, np.nan
    # the egalitarian half: survivors get equal weight, one scalar scales the consensus
    dk_tr, _ = deviations(tr, keep, bench_col)
    dk_te, _ = deviations(te, keep, bench_col)
    return gamma_fit(a, np.nanmean(dk_tr, axis=1), np.nanmean(dk_te, axis=1))


def fit_E11(a, tr, te, cols, active, skill, bench_col, param):
    """Trimmed residual consensus -- robust to per-game outliers, not to bad models."""
    if not active:
        return None, np.nan
    d_tr, _ = deviations(tr, active, bench_col)
    d_te, _ = deviations(te, active, bench_col)
    return gamma_fit(a, trimmed_mean(d_tr, param), trimmed_mean(d_te, param))


def fit_E12(a, tr, te, cols, active, skill, bench_col, param):
    """Combination elastic net: L1 drops redundant models, L2 stabilises the survivors."""
    from sklearn.linear_model import ElasticNet

    alpha, l1_ratio = param
    if not cols:
        return None, np.nan
    d_tr, _ = deviations(tr, cols, bench_col)
    d_te, _ = deviations(te, cols, bench_col)
    g_tr, g_te = a.strip(d_tr, d_te)
    en = ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=5000).fit(g_tr[a.ok], a.u[a.ok])
    return a.r0_te + en.predict(g_te), float(en.coef_.sum())


def fit_E13(a, tr, te, cols, active, skill, bench_col, param, ewa=None):
    """Online exponentially-weighted aggregation. `ewa` is precomputed chronologically."""
    if ewa is None:
        return None, np.nan
    return gamma_fit(a, ewa[param][tr.index.to_numpy()], ewa[param][te.index.to_numpy()])


def fit_E14(a, tr, te, cols, active, skill, bench_col, param):
    """Complete subset regression, AFTER screening to 10. Bounded check, not literal CSR."""
    keep = [m for m in screened(skill, active, CSR_SCREEN) if m in cols]
    if len(keep) <= param:
        return None, np.nan
    d_tr, _ = deviations(tr, keep, bench_col)
    d_te, _ = deviations(te, keep, bench_col)
    g_tr, g_te = a.strip(d_tr, d_te)
    acc = np.zeros(len(te))
    loading = 0.0
    combos = list(itertools.combinations(range(len(keep)), param))
    for idx in combos:
        cidx = list(idx)
        beta = ols(np.column_stack([np.ones(a.ok.sum()), g_tr[a.ok][:, cidx]]), a.u[a.ok])
        acc += beta[0] + g_te[:, cidx] @ beta[1:]
        loading += float(beta[1:].sum())
    return a.r0_te + acc / len(combos), loading / len(combos)


FITTERS = {
    "E6": fit_E6, "E7": fit_E7, "E8": fit_E8, "E9": fit_E9, "E10": fit_E10,
    "E11": fit_E11, "E12": fit_E12, "E13": fit_E13, "E14": fit_E14,
}


# --------------------------------------------------------------- online pre-computation


def precompute_ewa(df, models, bench_col, etas):
    """Chronological Hedge weights over model deviations, one pass per learning rate.

    Weights at week w use only games strictly before w, so this is walk-forward by
    construction and needs no per-season refit.
    """
    order = np.argsort(df["wk"].to_numpy(), kind="stable")
    blocks = []
    wk = df["wk"].to_numpy()[order]
    start = 0
    for i in range(1, len(order) + 1):
        if i == len(order) or wk[i] != wk[start]:
            blocks.append(order[start:i])
            start = i

    dev_all, _ = deviations(df, models, bench_col)
    y = df["y"].to_numpy()
    mkt = -df[bench_col].to_numpy(float)
    loss = (y[:, None] - (mkt[:, None] + dev_all)) ** 2  # per-model squared error

    out = {}
    for eta in etas:
        cum = np.zeros(len(models))
        seen = np.zeros(len(models), bool)
        cons = np.full(len(df), np.nan)
        for blk in blocks:
            d = dev_all[blk]
            avail = np.isfinite(d) & seen[None, :]
            if avail.any():
                # exponentiate only over models with a track record -- an unseen model has
                # cum=0, which sits below the seen minimum and overflows exp()
                w = np.zeros(len(models))
                w[seen] = np.exp(-eta * (cum[seen] - cum[seen].min()))
                wm = np.where(avail, w[None, :], 0.0)
                tot = wm.sum(axis=1)
                with np.errstate(invalid="ignore", divide="ignore"):
                    cons[blk] = np.where(tot > 0, (wm * np.nan_to_num(d)).sum(axis=1) / tot, np.nan)
            blk_loss = loss[blk]
            got = np.isfinite(blk_loss)
            cum += np.where(got, blk_loss, 0.0).sum(axis=0)
            seen |= got.any(axis=0)
        out[eta] = cons
    return out


# ------------------------------------------------------------------------ walk-forward


CURVE_LOG = None   # amendment A7: set to a list to record each (season, method) tuning curve


def _curve_row(season, method, cands, chosen):
    """The tuning curve behind one pick_1se call: mean validation error per grid point, the
    SE the rule compares against, the argmin, and what the 1-SE rule actually chose.

    A flat curve makes the 1-SE rule a tie-breaker that runs to the top of whatever grid it is
    given, which is indistinguishable from "the data want more shrinkage" unless the curve is
    reported. Amendment A7 exists to tell those apart.
    """
    scored = [(p, e) for p, e in cands if e is not None and len(e) > 30]
    if not scored:
        return None
    means = [float(e.mean()) for _, e in scored]
    best = int(np.argmin(means))
    se = float(scored[best][1].std(ddof=1) / np.sqrt(len(scored[best][1])))
    return {"season": int(season), "method": method,
            "params": [str(p) for p, _ in scored], "val_mse": means,
            "se_at_best": se, "argmin": str(scored[best][0]),
            "chosen_1se": str(chosen), "n_val": int(len(scored[best][1]))}


def pick_1se(cands):
    """1-SE rule. `cands` is [(param, val_sq_errors)] ordered least -> most conservative."""
    scored = [(p, e) for p, e in cands if e is not None and len(e) > 30]
    if not scored:
        return None
    means = np.array([e.mean() for _, e in scored])
    best = int(np.argmin(means))
    se = scored[best][1].std(ddof=1) / np.sqrt(len(scored[best][1]))
    ok = [i for i, m in enumerate(means) if m <= means[best] + se]
    return scored[max(ok)][0]  # last qualifying = most conservative, per the grid order


def sweep(df, models, bench_col, verbose=True, grids=None, only=None):
    """Every method's out-of-sample prediction, hyperparameters chosen inside the loop."""
    grids = grids or GRIDS
    wanted = METHODS if only is None else [m for m in METHODS if m in only]
    seasons = sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique())
    keys = METHODS + ["R0", "E4"]
    preds = {k: np.full(len(df), np.nan) for k in keys}
    chosen, coefs = [], []
    ewa = precompute_ewa(df, models, bench_col, grids["E13"])

    for s in seasons:
        tr = df[df["season"] < s]
        te_idx = df.index[df["season"] == s].to_numpy()
        te = df.loc[te_idx]
        cols, active = regressor_cols(tr, te, models)
        skill = base.prior_skill(df, models, bench_col, s - 1)

        # --- R0 and E4 rebuilt here so the whole table shares one common support. Under
        # Frisch-Waugh this E4 is numerically the parent script's joint three-parameter
        # fit, so the sweep's E4 row is the published estimator, re-scored, not a variant.
        a = Anchor(tr, te, bench_col)
        if not a.usable:
            continue
        preds["R0"][te_idx] = a.r0_te
        keep20 = screened(skill, active, base.SCREEN_K)
        d20_tr, _ = deviations(tr, keep20, bench_col)
        d20_te, _ = deviations(te, keep20, bench_col)
        p4, g4 = gamma_fit(a, np.nanmean(d20_tr, axis=1), np.nanmean(d20_te, axis=1))
        preds["E4"][te_idx] = p4
        coefs.append({"season": int(s), "method": "E4", "coef": float(g4)})

        # --- inner split: hyperparameters never see season s, nor the last 3 train seasons
        tr_seasons = sorted(tr["season"].unique())
        if len(tr_seasons) <= INNER_VAL_SEASONS + 1:
            continue
        val_seasons = tr_seasons[-INNER_VAL_SEASONS:]
        inner_tr = tr[~tr["season"].isin(val_seasons)]
        inner_va = tr[tr["season"].isin(val_seasons)]
        i_cols, i_active = regressor_cols(inner_tr, inner_va, models)
        i_skill = base.prior_skill(df, models, bench_col, val_seasons[0] - 1)
        y_va = inner_va["y"].to_numpy()
        ia = Anchor(inner_tr, inner_va, bench_col)  # the inner fold gets its own R0 base
        if not ia.usable:
            continue

        for m in wanted:
            fitter = FITTERS[m]
            cands = []
            for p in grids[m]:
                kw = {"ewa": ewa} if m == "E13" else {}
                try:
                    pv, _ = fitter(ia, inner_tr, inner_va, i_cols, i_active, i_skill,
                                   bench_col, p, **kw)
                except Exception:
                    pv = None
                if pv is None:
                    cands.append((p, None))
                    continue
                e = (y_va - pv) ** 2
                cands.append((p, e[np.isfinite(e)]))
            param = pick_1se(cands)
            if CURVE_LOG is not None:
                row = _curve_row(s, m, cands, param)
                if row is not None:
                    CURVE_LOG.append(row)
            if param is None:
                continue
            kw = {"ewa": ewa} if m == "E13" else {}
            try:
                pred, coef = fitter(a, tr, te, cols, active, skill, bench_col, param, **kw)
            except Exception:
                pred, coef = None, np.nan
            if pred is None:
                continue
            preds[m][te_idx] = pred
            chosen.append({"season": int(s), "method": m, "param": str(param)})
            coefs.append({"season": int(s), "method": m, "coef": float(coef)})
        if verbose:
            print(f"  season {s} done", flush=True)

    return preds, pd.DataFrame(chosen), pd.DataFrame(coefs), seasons


# ------------------------------------------------------------------------- diagnostics


def holm(p):
    """Holm step-down adjusted p-values."""
    p = np.asarray(p, float)
    ok = ~np.isnan(p)
    out = np.full_like(p, np.nan)
    ps = p[ok]
    order = np.argsort(ps)
    m = len(ps)
    adj = np.maximum.accumulate(ps[order] * (m - np.arange(m)))
    res = np.empty(m)
    res[order] = np.clip(adj, 0, 1)
    out[ok] = res
    return out


def season_win_rate(y, pred, ref, season, mask):
    """Fraction of evaluated seasons where the method's MSE beats R0's."""
    wins = tot = 0
    for s in np.unique(season[mask]):
        sel = mask & (season == s)
        if sel.sum() < 50:
            continue
        tot += 1
        wins += ((y[sel] - pred[sel]) ** 2).mean() < ((y[sel] - ref[sel]) ** 2).mean()
    return wins / tot if tot else np.nan


def sign_stability(coefs, method):
    c = coefs.loc[coefs.method == method, "coef"].to_numpy()
    c = c[np.isfinite(c)]
    if len(c) < 3:
        return np.nan
    pos = (c > 0).sum()
    return max(pos, len(c) - pos) / len(c)


def harvey_newbold(df, preds, models, bench_col, y, r0, season, mask, n_boot, n_pcs=3):
    """Joint encompassing: does the line encompass the panel as a SET?

    IN-SAMPLE by construction (the PCA and the screen both use the whole panel).
    That is the standard framing for an encompassing test -- it asks about the
    population, not about out-of-sample deployability, which the table answers.

    Five pre-specified directions (addendum section 8), not a 154-dim Wald that would have
    no power. Null imposed by centring; season-clustered wild bootstrap calibrates it.
    """
    from sklearn.decomposition import PCA

    cols = [m for m in models if df[m].notna().mean() > 0.5]
    d_all, mkt = deviations(df, cols, bench_col)

    skill = base.prior_skill(df, models, bench_col, base.BURN_IN_THROUGH)
    top20 = [m for m in screened(skill, cols, 20)]
    top5 = [m for m in screened(skill, cols, 5)]
    d20, _ = deviations(df, top20, bench_col)
    d5, _ = deviations(df, top5, bench_col)

    parts = [np.nan_to_num(np.nanmean(d20, axis=1)), np.nan_to_num(np.nanmean(d5, axis=1))]
    if n_pcs:  # n_pcs=0 drops the components -- the only full-sample piece of this test
        dz = np.nan_to_num(d_all)
        parts.append(PCA(n_components=n_pcs).fit_transform(dz - dz.mean(axis=0)))
    X = np.column_stack(parts)
    resid = y - r0
    sel = mask & np.isfinite(resid) & np.isfinite(X).all(axis=1)
    Xs, rs, cl = X[sel], resid[sel], season[sel]
    Xd = np.column_stack([np.ones(len(Xs)), Xs])

    beta = ols(Xd, rs)
    fitted = Xd @ beta
    e = rs - fitted
    codes, idx = np.unique(cl, return_inverse=True)
    g = len(codes)

    def wald(bh, ev):
        # season-clustered sandwich on the 5 slopes
        XtX_inv = np.linalg.pinv(Xd.T @ Xd)
        meat = np.zeros((Xd.shape[1], Xd.shape[1]))
        for j in range(g):
            Xg = Xd[idx == j]
            ug = Xg.T @ ev[idx == j]
            meat += np.outer(ug, ug)
        V = XtX_inv @ meat @ XtX_inv
        b, Vs = bh[1:], V[1:, 1:]
        return float(b @ np.linalg.pinv(Vs) @ b)

    w_obs = wald(beta, e)
    # null: slopes are zero -> resample around the intercept-only fit
    r_null = rs - rs.mean()
    stats = np.empty(n_boot)
    for b_i in range(n_boot):
        w = base.RNG.choice([-1.0, 1.0], size=g)[idx]
        yb = rs.mean() + r_null * w
        bb = ols(Xd, yb)
        stats[b_i] = wald(bb, yb - Xd @ bb)
    return w_obs, float((stats >= w_obs).mean()), int(sel.sum()), beta[1:]


# ------------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--wide", action="store_true",
                    help="post-hoc widened grids. EXPLORATORY: outside the addendum's "
                         "registered search space, excluded from every gate.")
    args = ap.parse_args()
    n_boot = 300 if args.quick else base.N_BOOT
    base.N_BOOT = n_boot
    grids = WIDE_GRIDS if args.wide else GRIDS
    suffix = "_wide" if args.wide else ""

    df, models = base.load()
    print(f"{len(df)} games, {len(models)} models, "
          f"seasons {df.season.min()}-{df.season.max()}, bootstrap draws {n_boot}")
    if args.wide:
        print("\n*** POST-HOC WIDENED GRIDS -- EXPLORATORY ONLY ***\n"
              "The addendum's stop rule fixes the registered search space; this run is\n"
              "outside it and is excluded from every gate. It answers one question only:\n"
              "would a clipped selection have gone further if the grid had let it?")

    results = {}
    for bench_col, label in (("lineopen", "opening"), ("line", "closing")):
        print(f"\n{'='*78}\nBENCHMARK: {label} line ({bench_col})\n{'='*78}")
        preds, chosen, coefs, seasons = sweep(df, models, bench_col, grids=grids)

        y = df["y"].to_numpy()
        season = df["season"].to_numpy()
        mkt = -df[bench_col].to_numpy(float)
        ev = df["season"] > base.BURN_IN_THROUGH

        # Sweep common support: every reported method on the SAME games (addendum s.6).
        # E5 is deliberately absent -- it needs complete rows and would collapse n for
        # everyone. The E6-vs-E5 repair check below gets its own paired support.
        #
        # Same hazard from inside the sweep: a method that cannot fit in EVERY evaluated
        # season would silently delete those seasons for all the others. Methods with full
        # season coverage define `common`; the rest are scored on their own paired subset
        # of it, with n printed so the difference is visible rather than implied.
        base_sup = ev & np.isfinite(mkt) & np.isfinite(preds["R0"]) & np.isfinite(preds["E4"])
        cover = {k: {int(t) for t in np.unique(season[base_sup & np.isfinite(preds[k])])}
                 for k in METHODS}
        full = [k for k in METHODS if len(cover[k]) == len(seasons)]
        short = [k for k in METHODS if k not in full]
        common = base_sup.copy()
        for k in full:
            common &= np.isfinite(preds[k])
        n = int(common.sum())
        r0 = preds["R0"]
        print(f"\n-- sweep common support n={n}, seasons {seasons[0]}-{seasons[-1]} --")
        print("   (NOT comparable to the parent run's n=12,803 -- different support)")
        for k in short:
            print(f"   {k} covers only {len(cover[k])}/{len(seasons)} seasons -- held out "
                  f"of the shared support, scored on its own subset")

        rows = []
        for k in ["E4"] + METHODS:
            p = preds[k]
            sup = common if (k in full or k == "E4") else (common & np.isfinite(p))
            d_r0 = base.sq_err(y[sup], -p[sup]) - base.sq_err(y[sup], -r0[sup])
            dm, ci, pv = base.wild_cluster_boot(d_r0, season[sup])
            d_mkt = base.sq_err(y[sup], -p[sup]) - base.sq_err(y[sup], -mkt[sup])
            rows.append({
                "method": k,
                "n": int(sup.sum()),
                "rmse": float(np.sqrt(base.sq_err(y[sup], -p[sup]).mean())),
                # The market's RMSE on THIS method's games. A method scored on a reduced
                # support has a reduced-support RMSE, and putting it next to the shared
                # market RMSE reproduces the coverage-difficulty confound the parent plan
                # names as threat #1 -- easier games, better raw RMSE, no more skill.
                "rmse_mkt_same_games": float(np.sqrt(base.sq_err(y[sup], -mkt[sup]).mean())),
                "d_vs_r0": dm, "ci_lo": ci[0], "ci_hi": ci[1], "p": pv,
                "d_vs_mkt": float(np.nanmean(d_mkt)),
                "frac_seasons": season_win_rate(y, p, r0, season, sup),
                "sign_stab": sign_stability(coefs, k),
                # How far the method actually moves off its own reference. Measured
                # against R0, not the raw line: a method whose selected hyperparameter
                # switches the correction off IS R0, and would otherwise score a free
                # "beats R0 in 60% of seasons" while doing nothing at all.
                "mean_abs_corr": float(np.mean(np.abs(p[sup] - r0[sup]))),
            })
        tab = pd.DataFrame(rows)
        expl = tab.method.isin(EXPLORATORY)
        tab["p_holm"] = np.nan
        tab.loc[expl, "p_holm"] = holm(tab.loc[expl, "p"].to_numpy())
        tab["viable"] = np.where(
            (tab.frac_seasons >= STABILITY_FLOOR) & (tab.sign_stab >= STABILITY_FLOOR)
            & (tab.mean_abs_corr > DEGENERATE_CORR),
            "yes", np.where(tab.mean_abs_corr <= DEGENERATE_CORR, "none", "NO"))

        mkt_rmse = float(np.sqrt(base.sq_err(y[common], -mkt[common]).mean()))
        r0_rmse = float(np.sqrt(base.sq_err(y[common], -r0[common]).mean()))
        print(f"\n{'':5s} {'n':>6s} {'RMSE':>8s} {'mktRMSE':>8s} {'ΔvsR0':>8s} "
              f"{'95% CI':>19s} {'p':>7s} {'pHolm':>7s} {'|corr|':>7s} {'seas':>5s} "
              f"{'ok':>5s}")
        print(f"{'mkt':5s} {n:6d} {mkt_rmse:8.4f} {mkt_rmse:8.4f}")
        print(f"{'R0':5s} {n:6d} {r0_rmse:8.4f} {mkt_rmse:8.4f} {0.0:+8.3f} "
              f"{'(reference)':>19s}")
        for _, r in tab.iterrows():
            ph = f"{r.p_holm:7.4f}" if np.isfinite(r.p_holm) else f"{'-':>7s}"
            flag = "" if int(r.n) == n else "  <- own support, RMSE not comparable to the rest"
            print(f"{r.method:5s} {int(r.n):6d} {r.rmse:8.4f} "
                  f"{r.rmse_mkt_same_games:8.4f} {r.d_vs_r0:+8.3f} "
                  f"[{r.ci_lo:+8.3f},{r.ci_hi:+7.3f}] {r.p:7.4f} {ph} "
                  f"{r.mean_abs_corr:7.3f} {r.frac_seasons:5.2f} {r.viable:>5s}{flag}")
        tab.to_csv(OUT_DIR / f"pt_sweep_{label}{suffix}.csv", index=False)

        # --- Clark-West for the two nested single-direction correctors
        print(f"\nClark-West vs R0 (does the direction carry population signal?):")
        for k in ("E4", "E7", "E10", "E11", "E13"):
            # clark_west takes MARGINS (sq_err takes spreads) -- do not negate here
            cw, cwci, cwp = base.clark_west(y[common], r0[common], preds[k][common],
                                            season[common])
            print(f"  {k:4s} adj mean {cw:+.3f} [{cwci[0]:+.3f},{cwci[1]:+.3f}] "
                  f"one-sided p={cwp:.4f}")

        # --- the repair: E6 vs E5 on their own paired support
        e5 = rebuild_e5(df, models, bench_col)
        pair = ev & np.isfinite(e5) & np.isfinite(preds["E6"]) & np.isfinite(r0)
        d56 = (base.sq_err(y[pair], -preds["E6"][pair])
               - base.sq_err(y[pair], -e5[pair]))
        dm, ci, pv = base.wild_cluster_boot(d56, season[pair])
        print(f"\nREPAIR, E6 vs E5 (paired support n={int(pair.sum())}):")
        print(f"  E5 RMSE {np.sqrt(base.sq_err(y[pair], -e5[pair]).mean()):.4f}   "
              f"E6 RMSE {np.sqrt(base.sq_err(y[pair], -preds['E6'][pair]).mean()):.4f}")
        print(f"  ΔMSE(E6-E5) {dm:+.3f} [{ci[0]:+.3f},{ci[1]:+.3f}] p={pv:.4f}")

        # --- joint encompassing
        w, wp, wn, wb = harvey_newbold(df, preds, models, bench_col, y, r0, season,
                                       common, n_boot)
        print(f"\nHarvey-Newbold joint encompassing (5 directions, n={wn}):")
        print(f"  Wald {w:.2f}  bootstrap p={wp:.4f}  "
              f"({'line does NOT encompass the panel' if wp < 0.05 else 'line encompasses the panel'})")
        print(f"  slopes: top20 {wb[0]:+.4f}  top5 {wb[1]:+.4f}  "
              f"PC1 {wb[2]:+.4f}  PC2 {wb[3]:+.4f}  PC3 {wb[4]:+.4f}")

        # --- which grid values the rule actually picked. Distinguish two very different
        # things: clipping on a grid I chose (an artifact) from running to the edge of the
        # parameter space itself (a result -- "the data want no correction at all").
        if not chosen.empty:
            print("\nhyperparameters selected by the 1-SE rule:")
            for m in METHODS:
                v = chosen.loc[chosen.method == m, "param"]
                if v.empty:
                    continue
                share = (v == str(grids[m][-1])).mean()
                note = ""
                if share > 0.5:
                    note = ("   <- SATURATED: most conservative value in the parameter space"
                            if m in SATURATED else "   <- CLIPPED on the grid edge")
                print(f"  {m:4s} mode={v.mode().iloc[0]:>14s}  n={len(v):3d}  "
                      f"most-conservative {share:.0%}{note}")
            chosen.to_csv(OUT_DIR / f"pt_sweep_params_{label}{suffix}.csv", index=False)

        # --- decision value for anything that cleared the stability gate
        close = -df["line"].to_numpy(float)
        for _, r in tab[tab.viable == "yes"].iterrows():
            ats(y, preds[r.method], close, common & np.isfinite(close), r.method)

        results[label] = {
            "n_common": n, "mkt_rmse": mkt_rmse, "r0_rmse": r0_rmse,
            "table": tab.to_dict("records"),
            "e6_vs_e5": {"mean": dm, "ci": list(ci), "p": pv, "n": int(pair.sum())},
            "harvey_newbold": {"wald": w, "p": wp, "n": wn, "slopes": list(map(float, wb))},
        }

    (OUT_DIR / f"pt_combination_sweep{suffix}.json").write_text(
        json.dumps(results, indent=2, default=float))
    print(f"\nwrote {OUT_DIR}/pt_combination_sweep{suffix}.json and per-benchmark CSVs")
    return 0


def rebuild_e5(df, models, bench_col):
    """E5 exactly as the parent script fits it -- raw forecasts, market penalised too.

    `legacy=True` deliberately: the parent script used the whole-history coverage filter, and
    the point of this comparison is E6's CENTRING against E5's, not E6's larger regressor set.
    Handing E5 the corrected filter would make it worse -- more columns under a complete-row
    requirement means fewer usable rows -- and the repair would be measured against a strawman.
    """
    from sklearn.linear_model import Ridge

    out = np.full(len(df), np.nan)
    for s in sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique()):
        tr = df[df["season"] < s]
        te_idx = df.index[df["season"] == s].to_numpy()
        te = df.loc[te_idx]
        cols, _ = regressor_cols(tr, te, models, legacy=True)
        if not cols:
            continue
        sub = tr[cols + [bench_col, "y"]].dropna()
        if len(sub) <= MIN_TRAIN_ROWS:
            continue
        rg = Ridge(alpha=base.RIDGE_ALPHA).fit(
            -sub[cols + [bench_col]].to_numpy(float), sub["y"].to_numpy())
        Xte = -te[cols + [bench_col]].to_numpy(float)
        ok = ~np.isnan(Xte).any(axis=1)
        if ok.any():
            p = np.full(len(te_idx), np.nan)
            p[ok] = rg.predict(Xte[ok])
            out[te_idx] = p
    return out


def ats(y, pred, close, mask, name):
    """Against-the-spread record of a method's disagreements with the closing line."""
    edge = pred[mask] - close[mask]
    actual = y[mask] - close[mask]
    print(f"\nATS, {name} vs closing line:")
    for thr in (0.0, 1.0, 2.0, 3.0):
        sel = np.abs(edge) > thr
        if sel.sum() < 50:
            continue
        win = (np.sign(edge[sel]) == np.sign(actual[sel])) & (actual[sel] != 0)
        dec = int(sel.sum() - (actual[sel] == 0).sum())
        if not dec:
            continue
        roi = (win.sum() * (100 / 110) - (dec - win.sum())) / dec
        print(f"  |edge|>{thr:.0f}: {dec:5d} bets  {win.sum()/dec:.4f} hit  "
              f"{roi:+.4f} ROI/unit   (break-even .5238)")


if __name__ == "__main__":
    raise SystemExit(main())
