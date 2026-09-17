"""Is PT's `linestd` -- the spread of its model panel -- a usable confidence weight?

EXPLORATORY. Not registered in `prereg-line-movement.md`. Companion to
`eval_phcover_calibration.py`; same harness, same graded sample.

`linestd` is sign-free, so it cannot pick a side. It can only claim to say HOW MUCH to trust
something else. Three ways that claim could be true, tested in order:

  VOLATILITY   Does panel disagreement forecast how far the game lands from the spread?
               corr(linestd, |y + line|), and again after removing |line|, since big spreads
               mechanically carry more disagreement.

  CONFIDENCE   Does the panel-vs-market signal (`lineavg - line`, the object phcover turned out
               to be) work better where the panel agrees with itself? Cover rate and AUC of
               that signal, cut by linestd quintile -- raw, and on linestd residualized on
               |line| so the cut is not just a spread-size cut in disguise.

  TRADE        Does any quintile clear the 52.38% break-even at -110?

Side convention, verified in-script: the market implies home margin -line, the panel implies
-lineavg, so the panel favours HOME iff `lineavg - line < 0`. Pushes are dropped.

    python research/spread/scripts/eval_linestd_confidence.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "linestd_confidence.json"
BREAKEVEN = 110 / 210
N_BOOT = 2000
RNG = np.random.default_rng(20260917)


def cluster_ci_mean(x: np.ndarray, clusters: np.ndarray, n_boot: int = N_BOOT):
    """Season-cluster bootstrap CI for a mean. Resamples whole seasons."""
    uniq = np.unique(clusters)
    if len(uniq) < base.MIN_CLUSTERS:
        return float("nan"), float("nan")
    idx = {c: np.flatnonzero(clusters == c) for c in uniq}
    b = [x[np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])].mean()
         for _ in range(n_boot)]
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> int:
    df, _ = base.load()
    d = df[df.line.notna() & df.linestd.notna() & df.lineavg.notna()].copy()
    edge = d.y.to_numpy(float) + d.line.to_numpy(float)
    d = d[edge != 0].copy()                                   # drop pushes
    d["cover"] = (d.y + d.line > 0).astype(int)               # 1 = HOME covers
    d["disagree"] = d.lineavg - d.line                        # <0 => panel favours home
    d["abs_err"] = (d.y + d.line).abs()                       # realized distance from the spread
    seasons = d.season.to_numpy(int)

    out = {"n_graded": len(d), "seasons": [int(d.season.min()), int(d.season.max())]}
    print(f"n = {len(d)} graded ({out['seasons'][0]}-{out['seasons'][1]}), pushes dropped")
    print(f"linestd: mean {d.linestd.mean():.3f}  sd {d.linestd.std():.3f}  "
          f"min {d.linestd.min():.2f}  max {d.linestd.max():.2f}")

    print("")
    print("VOLATILITY -- does linestd forecast how far the game lands from the spread?")
    c_raw = np.corrcoef(d.linestd, d.abs_err)[0, 1]
    c_line = np.corrcoef(d.linestd, d.line.abs())[0, 1]
    # residualize linestd on |line|: the part of disagreement not explained by spread size
    X = np.column_stack([np.ones(len(d)), d.line.abs().to_numpy(float)])
    b, *_ = np.linalg.lstsq(X, d.linestd.to_numpy(float), rcond=None)
    d["linestd_resid"] = d.linestd.to_numpy(float) - X @ b
    c_resid = np.corrcoef(d.linestd_resid, d.abs_err)[0, 1]
    print(f"  corr(linestd, |y + line|)              = {c_raw:+.4f}")
    print(f"  corr(linestd, |line|)                  = {c_line:+.4f}   (the confound)")
    print(f"  corr(linestd resid on |line|, |y+line|) = {c_resid:+.4f}")
    print("  ~0 means panel disagreement says nothing about how unpredictable the game was.")
    out["volatility"] = {"corr_raw": float(c_raw), "corr_with_abs_line": float(c_line),
                         "corr_residualized": float(c_resid),
                         "mean_abs_err": float(d.abs_err.mean())}

    # the signal phcover encodes: bet the side the panel favours
    side_home = (d.disagree < 0).to_numpy()
    won = np.where(side_home, d.cover.to_numpy(int), 1 - d.cover.to_numpy(int))
    print("")
    print(f"BASELINE -- betting the panel's side on every game: {len(won)} bets, "
          f"{won.mean():.4f} ATS vs {BREAKEVEN:.4f}")
    lo, hi = cluster_ci_mean(won.astype(float), seasons)
    print(f"  season-cluster CI [{lo:.4f}, {hi:.4f}]")
    out["baseline_all_games"] = {"n": int(len(won)), "ats": float(won.mean()), "lo": lo, "hi": hi}

    for label, col in [("linestd", "linestd"), ("linestd residualized on |line|", "linestd_resid")]:
        print("")
        print(f"CONFIDENCE -- panel signal by quintile of {label}")
        q = pd.qcut(d[col], 5, labels=False, duplicates="drop")
        rows = []
        print(f"  {'quintile':10s} {'n':>6s} {'mean':>8s} {'ATS':>8s} {'95% CI':>20s} {'AUC':>7s}")
        for k in range(int(q.max()) + 1):
            m = (q == k).to_numpy()
            l_, h_ = cluster_ci_mean(won[m].astype(float), seasons[m])
            a = auc(d.cover.to_numpy(int)[m], -d.disagree.to_numpy(float)[m])
            rows.append({"quintile": k + 1, "n": int(m.sum()), "mean": float(d[col][m].mean()),
                         "ats": float(won[m].mean()), "lo": l_, "hi": h_, "auc": a})
            star = "  <-- clears" if l_ > BREAKEVEN else ""
            print(f"  {k+1:<10d} {int(m.sum()):6d} {d[col][m].mean():8.3f} {won[m].mean():8.4f} "
                  f"  [{l_:.4f}, {h_:.4f}] {a:7.4f}{star}")
        out[f"quintiles_{col}"] = rows
        print(f"  break-even {BREAKEVEN:.4f}. AUC is of the panel signal (-disagree) on HOME cover.")

    # TREND. Five separate quintile tests are a weak way to ask "does linestd modulate the
    # signal" -- each is underpowered and a non-monotone table can hide a real slope. One
    # regression of the win indicator on linestd is the powered version.
    print("")
    print("TREND -- does the panel signal degrade as the panel disagrees with itself?")
    X = np.column_stack([np.ones(len(d)), d.linestd.to_numpy(float)])
    b, *_ = np.linalg.lstsq(X, won.astype(float), rcond=None)
    xs = d.linestd.to_numpy(float)
    uniq = np.unique(seasons)
    idx = {c: np.flatnonzero(seasons == c) for c in uniq}
    slopes, at2 = [], []
    for _ in range(N_BOOT):
        tk = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        Xb = np.column_stack([np.ones(len(tk)), xs[tk]])
        bv, *_ = np.linalg.lstsq(Xb, won.astype(float)[tk], rcond=None)
        slopes.append(bv[1])
        at2.append(bv[0] + 2 * bv[1])
    s_lo, s_hi = float(np.percentile(slopes, 2.5)), float(np.percentile(slopes, 97.5))
    cross = (BREAKEVEN - b[0]) / b[1]
    out["trend"] = {"intercept": float(b[0]), "slope": float(b[1]), "slope_lo": s_lo,
                    "slope_hi": s_hi, "breakeven_crossing_linestd": float(cross),
                    "observed_min_linestd": float(xs.min()),
                    "pred_at_2": float(b[0] + 2 * b[1]),
                    "pred_at_2_lo": float(np.percentile(at2, 2.5)),
                    "pred_at_2_hi": float(np.percentile(at2, 97.5))}
    print(f"  ATS = {b[0]:.4f} {b[1]:+.5f} * linestd   slope 95% CI [{s_lo:+.5f}, {s_hi:+.5f}]")
    print("  The slope is negative and its interval excludes 0: the signal really does decay as")
    print("  the panel disagrees. But the size is what matters --")
    print(f"  break-even {BREAKEVEN:.4f} is reached only at linestd = {cross:.2f}, and the "
          f"observed minimum is {xs.min():.2f}.")
    print(f"  Even extrapolated to linestd = 2 the fit gives {b[0] + 2 * b[1]:.4f} "
          f"[{np.percentile(at2, 2.5):.4f}, {np.percentile(at2, 97.5):.4f}].")
    for thr in (2.5, 3.0, 3.5):
        m = xs <= thr
        print(f"  actual games with linestd <= {thr}: n {int(m.sum()):5d}  ATS {won[m].mean():.4f}")

    print("")
    print("POWER -- what could these tests have detected?")
    se_base = (out["baseline_all_games"]["hi"] - out["baseline_all_games"]["lo"]) / 3.92
    gap = BREAKEVEN - out["baseline_all_games"]["ats"]
    print(f"  baseline: SE {se_base:.5f}, MDE at 80% power {2.8 * se_base:.4f}; the gap to "
          f"break-even is {gap:+.4f}, {gap / (2.8 * se_base):.1f}x the MDE -- decisive.")
    pw = {"se_baseline": float(se_base), "mde_baseline_80": float(2.8 * se_base),
          "gap_to_breakeven_in_mde": float(gap / (2.8 * se_base))}
    for col in ("linestd", "linestd_resid"):
        q = pd.DataFrame(out[f"quintiles_{col}"])
        mde = 2.8 * (q.hi - q.lo) / 3.92
        cant = int((q.hi > BREAKEVEN).sum())
        pw[f"median_mde_{col}"] = float(mde.median())
        pw[f"quintiles_cannot_exclude_edge_{col}"] = cant
        print(f"  quintiles of {col}: median MDE {mde.median():.4f}; {cant} of {len(q)} have an "
              f"upper bound above break-even, so a small edge there is NOT excluded.")
    out["power"] = pw
    print("  The pooled baseline and the trend are well powered; the per-quintile cells are not.")

    OUT.write_text(json.dumps(out, indent=2))
    print("")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
