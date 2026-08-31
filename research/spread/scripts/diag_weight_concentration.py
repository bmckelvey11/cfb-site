"""Test a proposed contamination-blind fragility diagnostic: N_eff = 1 / sum(w_i^2).

THE CLAIM (from an outside reviewer). The inverse Herfindahl of a method's own fitted
weights predicts how exposed it is to a single anomalous column. Equal-weight top-K has
N_eff = K by construction; ridge and elastic net should "collapse toward 1-3" when one
predictor's marginal correlation dominates -- which is what a benchmark clone produces. If
true it needs no contamination measure, only training-window weights, and would have
predicted the 73%-vs-27% retention split in research/spread/docs/prediction-tracker-findings.md BEFORE that
split was measured.

WHAT ACTUALLY DISCRIMINATES. That E4/E7/E10/E11 score high is a tautology -- they are
equal-weighting schemes, so N_eff = k by definition and predicts nothing. Two tests carry
real content:

  1. across-lambda, within ridge: N_eff on the SAME columns as the penalty varies. This is
     the only place the diagnostic can be wrong rather than circular.
  2. the numeric prediction itself: does ridge collapse to 1-3?

Note before running: ridge selected lambda=10000 -- the most conservative grid point -- in
all 20 seasons on both benchmarks. Heavy L2 pulls coefficients toward each other, which
raises N_eff. The prediction may fail on its own terms.

NORMALISATION. Ridge coefficients are signed and do not sum to 1, so raw weights are not
comparable to 1/k. Weights are normalised by their absolute sum, w~_i = |w_i| / sum|w_j|,
the standard concentration measure for signed weightings. Stated because it is a choice:
normalising by the signed sum would blow up whenever the coefficients nearly cancel.

Replays the OUTER fits using hyperparameters already chosen and persisted by the sweep, so
the expensive inner-validation loop is not repeated and the nine tested fitters are not
touched.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402

OUT = base.OUT_DIR if hasattr(base, "OUT_DIR") else Path(r"C:/Users/mckel/data/cfb/processed")

# Retention under decontamination, from the findings doc. The four methods for which the
# market-proxy check was run. These are what any real diagnostic has to line up against.
RETENTION = {"E4": 0.73, "E11": 0.75, "E14": 0.49, "E6": 0.27}


def n_eff(w):
    """Inverse Herfindahl of |w| normalised to sum 1. Returns NaN for an all-zero vector."""
    w = np.abs(np.asarray(w, float))
    w = w[np.isfinite(w)]
    tot = w.sum()
    if tot <= 0:
        return np.nan
    p = w / tot
    return float(1.0 / (p**2).sum())


# ------------------------------------------------------------------ weight extraction
# One per method, mirroring the corresponding fitter in eval_combination_sweep. Each
# returns (weight vector, names) in MODEL space, or (None, None) where undefined.


def w_equal(names):
    return np.full(len(names), 1.0 / len(names)), list(names)


def w_E6(a, tr, te, cols, active, skill, bench_col, param):
    from sklearn.linear_model import Ridge

    if not cols:
        return None, None
    d_tr, _ = sweep.deviations(tr, cols, bench_col)
    d_te, _ = sweep.deviations(te, cols, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    return Ridge(alpha=param).fit(g_tr[a.ok], a.u[a.ok]).coef_, list(cols)


def w_E7(a, tr, te, cols, active, skill, bench_col, param):
    keep = sweep.screened(skill, active, param)
    return w_equal(keep) if keep else (None, None)


def w_E8(a, tr, te, cols, active, skill, bench_col, param):
    if not cols:
        return None, None
    d_tr, _ = sweep.deviations(tr, cols, bench_col)
    d_te, _ = sweep.deviations(te, cols, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    # psi scales every coefficient equally, so it cancels in the normalisation -- N_eff for
    # E8 is the unrestricted OLS concentration regardless of the shrinkage actually applied.
    return sweep.ols(g_tr[a.ok], a.u[a.ok]) * param, list(cols)


def w_E10(a, tr, te, cols, active, skill, bench_col, param):
    from sklearn.linear_model import Lasso

    if not cols:
        return None, None
    d_tr, _ = sweep.deviations(tr, cols, bench_col)
    d_te, _ = sweep.deviations(te, cols, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    las = Lasso(alpha=param, max_iter=5000).fit(g_tr[a.ok], a.u[a.ok])
    keep = [c for c, w in zip(cols, las.coef_) if w != 0]
    return w_equal(keep) if keep else (None, None)


def w_E11(a, tr, te, cols, active, skill, bench_col, param):
    """Trimming is per game, so a model's weight is how often it survived, averaged."""
    if not active:
        return None, None
    d_tr, _ = sweep.deviations(tr, active, bench_col)
    lo = np.nanquantile(d_tr, param, axis=1, keepdims=True) if param > 0 else -np.inf
    hi = np.nanquantile(d_tr, 1 - param, axis=1, keepdims=True) if param > 0 else np.inf
    kept = np.isfinite(d_tr) & (d_tr >= lo) & (d_tr <= hi)
    per_game = kept / np.where(kept.sum(axis=1, keepdims=True) > 0,
                               kept.sum(axis=1, keepdims=True), np.nan)
    return np.nanmean(per_game, axis=0), list(active)


def w_E12(a, tr, te, cols, active, skill, bench_col, param):
    from sklearn.linear_model import ElasticNet

    alpha, l1_ratio = param
    if not cols:
        return None, None
    d_tr, _ = sweep.deviations(tr, cols, bench_col)
    d_te, _ = sweep.deviations(te, cols, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    en = ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=5000).fit(g_tr[a.ok], a.u[a.ok])
    return en.coef_, list(cols)


def w_E14(a, tr, te, cols, active, skill, bench_col, param):
    """CSR averages over subsets; a model's effective weight is its mean coefficient."""
    import itertools

    keep = [m for m in sweep.screened(skill, active, sweep.CSR_SCREEN) if m in cols]
    if len(keep) <= param:
        return None, None
    d_tr, _ = sweep.deviations(tr, keep, bench_col)
    d_te, _ = sweep.deviations(te, keep, bench_col)
    g_tr, _ = a.strip(d_tr, d_te)
    acc = np.zeros(len(keep))
    combos = list(itertools.combinations(range(len(keep)), param))
    for idx in combos:
        cidx = list(idx)
        beta = sweep.ols(np.column_stack([np.ones(a.ok.sum()), g_tr[a.ok][:, cidx]]),
                         a.u[a.ok])
        acc[cidx] += beta[1:]
    return acc / len(combos), keep


WEIGHTERS = {"E6": w_E6, "E7": w_E7, "E8": w_E8, "E10": w_E10, "E11": w_E11,
             "E12": w_E12, "E14": w_E14}

# E9 is deliberately absent. Mapping beta through pca.components_ does yield a model-space
# vector, but its concentration reflects the eigenstructure of the deviation matrix rather
# than a weighting decision, so it is not commensurable with the rest.
# E13 is handled separately: its weights are per game and depend on cumulative loss over
# the whole history, so what is reported is an average of per-game weight vectors, not a
# fitted per-season one.


def ewa_neff(df, models, bench_col, eta, season):
    """Average N_eff of the Hedge weight vector over one season's games."""
    dev_all, _ = sweep.deviations(df, models, bench_col)
    y, mkt = df["y"].to_numpy(), -df[bench_col].to_numpy(float)
    loss = (y[:, None] - (mkt[:, None] + dev_all)) ** 2
    order = np.argsort(df["wk"].to_numpy(), kind="stable")
    wk = df["wk"].to_numpy()[order]
    blocks, start = [], 0
    for i in range(1, len(order) + 1):
        if i == len(order) or wk[i] != wk[start]:
            blocks.append(order[start:i])
            start = i
    seasons = df["season"].to_numpy()
    cum, seen, vals = np.zeros(len(models)), np.zeros(len(models), bool), []
    for blk in blocks:
        if seasons[blk][0] == season and seen.any():
            w = np.zeros(len(models))
            w[seen] = np.exp(-eta * (cum[seen] - cum[seen].min()))
            avail = np.isfinite(dev_all[blk]) & seen[None, :]
            for row in avail:
                if row.any():
                    vals.append(n_eff(np.where(row, w, 0.0)))
        blk_loss = loss[blk]
        got = np.isfinite(blk_loss)
        cum += np.where(got, blk_loss, 0.0).sum(axis=0)
        seen |= got.any(axis=0)
    return float(np.nanmean(vals)) if vals else np.nan


def run(df, models, bench_col, label):
    params = pd.read_csv(OUT / f"pt_sweep_params_{label}.csv")
    params["param"] = params["param"].map(lambda s: s if s == "all" else _lit(s))
    rows, lam_rows = [], []

    for s in sorted(df.loc[df.season > base.BURN_IN_THROUGH, "season"].unique()):
        tr, te = df[df.season < s], df[df.season == s]
        cols, active = sweep.regressor_cols(tr, te, models)
        skill = base.prior_skill(df, models, bench_col, s - 1)
        a = sweep.Anchor(tr, te, bench_col)
        if not a.usable:
            continue

        keep20 = sweep.screened(skill, active, base.SCREEN_K)
        if keep20:
            w, nm = w_equal(keep20)
            rows.append({"season": int(s), "method": "E4", "n_eligible": len(cols),
                         "n_weighted": len(nm), "n_eff": n_eff(w)})

        sel = params[params.season == s].set_index("method")["param"]
        for m, fn in WEIGHTERS.items():
            if m not in sel.index:
                continue
            try:
                w, nm = fn(a, tr, te, cols, active, skill, bench_col, sel[m])
            except Exception:
                w, nm = None, None
            if w is None:
                continue
            rows.append({"season": int(s), "method": m, "n_eligible": len(cols),
                         "n_weighted": len(nm), "n_eff": n_eff(w)})

        # THE discriminating test: same columns, same season, penalty varied.
        for lam in sweep.GRIDS["E6"]:
            w, nm = w_E6(a, tr, te, cols, active, skill, bench_col, lam)
            if w is not None:
                lam_rows.append({"season": int(s), "lam": lam, "n_eligible": len(cols),
                                 "n_eff": n_eff(w)})

    if "E13" in set(params.method):
        eta = params[params.method == "E13"]["param"].iloc[0]
        for s in sorted(df.loc[df.season > base.BURN_IN_THROUGH, "season"].unique()):
            v = ewa_neff(df, models, bench_col, float(eta), int(s))
            if np.isfinite(v):
                rows.append({"season": int(s), "method": "E13", "n_eligible": np.nan,
                             "n_weighted": np.nan, "n_eff": v})

    return pd.DataFrame(rows), pd.DataFrame(lam_rows)


def _lit(s):
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return s


def report(tab, lam, label):
    print(f"\n{'='*74}\nWEIGHT CONCENTRATION -- {label} line\n{'='*74}")
    g = tab.groupby("method").agg(n_eff=("n_eff", "mean"),
                                  n_eligible=("n_eligible", "mean"),
                                  n_weighted=("n_weighted", "mean")).round(2)
    g["share_of_weighted"] = (g.n_eff / g.n_weighted).round(3)
    g["retention"] = [RETENTION.get(m, np.nan) for m in g.index]
    g["by_construction"] = ["yes" if m in ("E4", "E7", "E10", "E11") else "no"
                            for m in g.index]
    print(g.to_string())

    print(f"\n-- ridge N_eff vs penalty, same columns (the discriminating test) --")
    lg = lam.groupby("lam").agg(n_eff=("n_eff", "mean"),
                                n_eligible=("n_eligible", "mean")).round(2)
    lg["share"] = (lg.n_eff / lg.n_eligible).round(3)
    print(lg.to_string())

    print("\n-- against measured retention (4 points; no correlation is computed on 4) --")
    sub = g[g.retention.notna()].sort_values("retention", ascending=False)
    print(sub[["n_eff", "share_of_weighted", "retention", "by_construction"]].to_string())


def _check():
    assert abs(n_eff([0.25] * 4) - 4.0) < 1e-9, "equal weights give N_eff = k"
    assert abs(n_eff([1.0, 0, 0, 0]) - 1.0) < 1e-9, "one live weight gives N_eff = 1"
    assert abs(n_eff([-0.5, 0.5]) - 2.0) < 1e-9, "sign must not change concentration"
    assert n_eff([1e3, 1e3]) == n_eff([1e-3, 1e-3]), "scale must not change concentration"
    assert np.isnan(n_eff([0.0, 0.0])), "an all-zero vector has no concentration"
    print("checks pass")


def main():
    df, models = base.load()
    for bench_col, label in (("lineopen", "opening"), ("line", "closing")):
        tab, lam = run(df, models, bench_col, label)
        report(tab, lam, label)
        tab.to_csv(OUT / f"pt_neff_{label}.csv", index=False)
        lam.to_csv(OUT / f"pt_neff_ridge_lambda_{label}.csv", index=False)
    print(f"\nwrote pt_neff_*.csv to {OUT}")


if __name__ == "__main__":
    _check()
    main()
