"""Is PT's `phwin` -- its published P(home wins) -- better than the market line?

EXPLORATORY. Not registered in `prereg-line-movement.md`. Third of the PT-column studies, after
`eval_phcover_calibration.py` and `eval_linestd_confidence.py`. No verdict follows from it.

`phwin` is not like `phcover`. phcover encoded the panel's DISAGREEMENT with the market and sat
pinned near 0.50. phwin encodes the panel's LEVEL -- logit(phwin) regresses on `lineavg` at
R^2 0.997 -- so it spans 0.006 to 0.997 and will discriminate well simply because any sane
spread-to-win-probability map discriminates. That makes "does it discriminate" the wrong
question. The right one is whether it beats the MARKET, which is free and already in the panel.

  DISCRIMINATION  AUC of phwin vs AUC of the market line. AUC is rank-based, so scoring the
                  market by `-line` needs no fitting and gives neither side an in-sample edge.

  CALIBRATION     phwin's Brier and decile reliability, against a market baseline whose
                  spread-to-probability map is fit WALK-FORWARD on prior seasons only, so the
                  market is not handed in-sample information phwin never had.

Home wins iff `y > 0` (`y` is the margin oriented to PT's home team). College football has no
ties, so there is no push case here -- verified in-script.

    python research/spread/scripts/eval_phwin_accuracy.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "phwin_accuracy.json"
N_BOOT = 2000
RNG = np.random.default_rng(20260917)


def auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def cluster_boot(fn, clusters: np.ndarray, n_boot: int = N_BOOT):
    """Season-cluster bootstrap CI for any statistic fn(index_array)."""
    uniq = np.unique(clusters)
    if len(uniq) < base.MIN_CLUSTERS:
        return float("nan"), float("nan")
    idx = {c: np.flatnonzero(clusters == c) for c in uniq}
    vals = []
    for _ in range(n_boot):
        take = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        v = fn(take)
        if np.isfinite(v):
            vals.append(v)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def fit_logit_multi(X2: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    """Newton-Raphson logistic fit of y on [1, *X2 columns]."""
    X = np.column_stack([np.ones(len(X2)), X2])
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        pr = logistic(X @ b).clip(1e-9, 1 - 1e-9)
        W = pr * (1 - pr)
        step = np.linalg.solve((X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (y - pr))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def fit_logit(x: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    """Plain Newton-Raphson logistic fit of y on [1, x]. Small and dependency-free."""
    X = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = logistic(X @ b).clip(1e-9, 1 - 1e-9)
        W = p * (1 - p)
        step = np.linalg.solve((X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def main() -> int:
    df, _ = base.load()
    d = df[df.phwin.notna() & df.line.notna()].copy().sort_values("season").reset_index(drop=True)
    assert (d.y == 0).sum() == 0, "unexpected tie -- the win indicator would need a push rule"
    y = (d.y > 0).astype(int).to_numpy()
    p = d.phwin.to_numpy(float)
    line = d.line.to_numpy(float)
    seasons = d.season.to_numpy(int)

    out = {"n": len(d), "seasons": [int(d.season.min()), int(d.season.max())],
           "base_home_win_rate": float(y.mean()), "phwin_sd": float(p.std())}
    print(f"n = {len(d)} ({out['seasons'][0]}-{out['seasons'][1]}), no ties")
    print(f"home win rate {y.mean():.4f}   phwin mean {p.mean():.4f} sd {p.std():.4f} "
          f"range [{p.min():.3f}, {p.max():.3f}]")

    print("")
    print("DISCRIMINATION -- phwin vs the market line (rank-based, no fitting)")
    a_ph, a_mkt = auc(y, p), auc(y, -line)
    lo_d, hi_d = cluster_boot(lambda i: auc(y[i], p[i]) - auc(y[i], -line[i]), seasons)
    out["auc"] = {"phwin": a_ph, "market": a_mkt, "diff": a_ph - a_mkt, "lo": lo_d, "hi": hi_d}
    print(f"  phwin  AUC = {a_ph:.4f}")
    print(f"  market AUC = {a_mkt:.4f}   (scored by -line)")
    print(f"  difference = {a_ph - a_mkt:+.4f}  [{lo_d:+.4f}, {hi_d:+.4f}]  season clusters")
    print("  An interval containing 0 means phwin does not out-rank the market.")

    print("")
    print("CALIBRATION -- Brier, vs a WALK-FORWARD market map and the base rate")
    # market probability from a logit of home-win on line, fit on strictly prior seasons
    mkt = np.full(len(d), np.nan)
    for s in sorted(set(seasons)):
        tr, te = seasons < s, seasons == s
        if tr.sum() < 200:
            continue
        b = fit_logit(line[tr], y[tr])
        mkt[te] = logistic(b[0] + b[1] * line[te])
    ok = np.isfinite(mkt)
    n_ok = int(ok.sum())
    br_ph = float(((p[ok] - y[ok]) ** 2).mean())
    br_mkt = float(((mkt[ok] - y[ok]) ** 2).mean())
    br_base = float(((y[ok].mean() - y[ok]) ** 2).mean())
    lo_b, hi_b = cluster_boot(
        lambda i: ((p[ok][i] - y[ok][i]) ** 2).mean() - ((mkt[ok][i] - y[ok][i]) ** 2).mean(),
        seasons[ok])
    out["brier"] = {"n_scored": n_ok, "phwin": br_ph, "market_walkforward": br_mkt,
                    "base_rate": br_base, "diff_phwin_minus_market": br_ph - br_mkt,
                    "lo": lo_b, "hi": hi_b,
                    "skill_vs_base_phwin": 1 - br_ph / br_base,
                    "skill_vs_base_market": 1 - br_mkt / br_base}
    print(f"  scored on {n_ok} games (first season has no prior to fit on)")
    print(f"  phwin  Brier {br_ph:.5f}   skill vs base rate {1 - br_ph / br_base:+.4f}")
    print(f"  market Brier {br_mkt:.5f}   skill vs base rate {1 - br_mkt / br_base:+.4f}")
    print(f"  phwin - market = {br_ph - br_mkt:+.5f}  [{lo_b:+.5f}, {hi_b:+.5f}]  (negative = phwin better)")

    print("")
    print("  decile of phwin     n   mean phwin   realized home win")
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    rows = []
    for k in range(int(q.max()) + 1):
        m = q == k
        rows.append({"decile": k + 1, "n": int(m.sum()), "mean_phwin": float(p[m].mean()),
                     "realized": float(y[m].mean())})
        print(f"  {k+1:>2d} {int(m.sum()):16d}   {p[m].mean():.4f}       {y[m].mean():.4f}")
    out["deciles"] = rows

    # Encompassing test: head-to-head says which is better, this says whether phwin carries
    # anything the market does not. Logit of home-win on [line, logit(phwin)] -- if phwin's
    # coefficient is indistinguishable from 0, the market encompasses it entirely.
    print("")
    print("ENCOMPASSING -- does phwin add anything on top of the line?")
    lg = np.log(p.clip(1e-6, 1 - 1e-6) / (1 - p.clip(1e-6, 1 - 1e-6)))
    X = np.column_stack([line, lg])
    b_joint = fit_logit_multi(X, y)
    names = ["line", "logit(phwin)"]
    lo_hi = {}
    for j, nm in enumerate(names):
        l_, h_ = cluster_boot(lambda i, j=j: fit_logit_multi(X[i], y[i])[j + 1], seasons)
        lo_hi[nm] = (l_, h_)
        zero = "  <-- contains 0" if l_ <= 0 <= h_ else ""
        print(f"  {nm:14s} coef {b_joint[j+1]:+.4f}  [{l_:+.4f}, {h_:+.4f}]{zero}")
    out["encompassing"] = {"coef_line": float(b_joint[1]), "coef_logit_phwin": float(b_joint[2]),
                           "ci_line": lo_hi["line"], "ci_logit_phwin": lo_hi["logit(phwin)"]}

    # POWER. logit(phwin) is ~94% explained by `line`, so the encompassing coefficient is
    # estimated off the ~25% of its variation that survives. Frisch-Waugh means that does not
    # BIAS the coefficient -- orthogonalizing gives the identical number -- but it does gut the
    # power, and a CI containing 0 must not be read as "adds nothing" without saying what the
    # test could have detected. This prints that.
    print("")
    print("POWER -- what could the encompassing test actually have detected?")
    Xl = np.column_stack([np.ones(len(d)), line])
    bl, *_ = np.linalg.lstsq(Xl, lg, rcond=None)
    resid = lg - Xl @ bl
    r2_lg = 1 - (resid**2).sum() / ((lg - lg.mean()) ** 2).sum()
    b_solo = fit_logit_multi(lg.reshape(-1, 1), y)
    lo_s, hi_s = cluster_boot(lambda i: fit_logit_multi(lg[i].reshape(-1, 1), y[i])[1], seasons)
    se = (lo_hi["logit(phwin)"][1] - lo_hi["logit(phwin)"][0]) / 3.92
    out["power"] = {"r2_logit_phwin_on_line": float(r2_lg), "vif": float(1 / (1 - r2_lg)),
                    "sd_logit_phwin": float(lg.std()), "sd_residual": float(resid.std()),
                    "coef_phwin_alone": float(b_solo[1]), "ci_phwin_alone": [lo_s, hi_s],
                    "se_encompassing": float(se), "mde_80": float(2.8 * se)}
    print(f"  R2(logit(phwin) ~ line) = {r2_lg:.4f}   VIF = {1 / (1 - r2_lg):.1f}")
    print(f"  sd(logit phwin) {lg.std():.3f} -> residual {resid.std():.3f} "
          f"({100 * resid.std() / lg.std():.1f}% of the variation is independent of the line)")
    print(f"  phwin ALONE: coef {b_solo[1]:+.4f} [{lo_s:+.4f}, {hi_s:+.4f}] "
          f"(1.0 = right on its own scale; >1 = under-confident)")
    print(f"  encompassing SE {se:.4f}, MDE at 80% power {2.8 * se:.4f}")
    print("  So a FULLY informative residual (near the solo coefficient) is excluded; a modest")
    print("  contribution of 0.1-0.3 is NOT. Do not read the interval as 'adds nothing'.")

    OUT.write_text(json.dumps(out, indent=2))
    print("")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
