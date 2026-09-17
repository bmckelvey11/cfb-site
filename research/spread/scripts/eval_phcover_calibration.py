"""How accurate is The Prediction Tracker's `phcover` -- its published P(home covers)?

EXPLORATORY. Not registered in `prereg-line-movement.md`; nothing here is a version A or B
read, and no verdict follows from it.

`phcover` ships in PT's CSV from 2017 on. Three questions, in the order that decides the answer:

  DRIVER        Is phcover independent information, or a transform of something already in the
                panel? Regressed on `line`, `lineavg`, and their difference.

  DISCRIMINATION Does phcover rank covers above non-covers? AUC, with a season-cluster
                bootstrap CI. This is the question that matters: a probability pinned near 0.50
                can be perfectly calibrated and still carry no signal.

  CALIBRATION   Do the stated probabilities match realized cover rates? Brier score against the
                base rate (Brier skill score) plus a decile reliability table with bin counts.

Cover is scored on the panel's own line, oriented to PT's home team the way `base.load()`
orients the margin: home covers iff `y + line > 0`. `y + line == 0` is a PUSH and is dropped
from every rate and from the AUC -- it is not a binary outcome.

    python research/spread/scripts/eval_phcover_calibration.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "phcover_calibration.json"
BREAKEVEN = 110 / 210          # 0.52381, the ATS rate a -110 bet must clear
N_BOOT = 2000
RNG = np.random.default_rng(20260917)


def auc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney), ties averaged."""
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def cluster_boot_auc(y, p, clusters, n_boot=N_BOOT):
    """Season-cluster bootstrap CI for AUC: resample whole seasons, not games."""
    uniq = np.unique(clusters)
    if len(uniq) < base.MIN_CLUSTERS:
        return (float("nan"), float("nan"))
    idx = {c: np.flatnonzero(clusters == c) for c in uniq}
    out = []
    for _ in range(n_boot):
        take = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        a = auc(y[take], p[take])
        if np.isfinite(a):
            out.append(a)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))) if out else (float("nan"),) * 2


def main() -> int:
    df, _ = base.load()
    d = df[df.phcover.notna() & df.line.notna()].copy()

    edge = d.y.to_numpy(float) + d.line.to_numpy(float)     # >0 home covers, ==0 push
    d["push"] = edge == 0
    d["cover"] = (edge > 0).astype(int)
    n_all, n_push = len(d), int(d.push.sum())
    g = d[~d.push].copy()                                    # graded: pushes dropped
    y = g.cover.to_numpy(int)
    p = g.phcover.to_numpy(float)
    seasons = g.season.to_numpy(int)

    out = {"n_with_phcover": n_all, "n_push": n_push, "n_graded": len(g),
           "seasons": [int(g.season.min()), int(g.season.max())]}
    print(f"n = {n_all} games with phcover, {n_push} pushes dropped, {len(g)} graded "
          f"({out['seasons'][0]}-{out['seasons'][1]})")
    print(f"base cover rate = {y.mean():.4f}   break-even at -110 = {BREAKEVEN:.4f}")
    print(f"phcover: mean {p.mean():.4f}  sd {p.std():.4f}  "
          f"min {p.min():.3f}  max {p.max():.3f}  IQR {np.percentile(p,75)-np.percentile(p,25):.4f}")
    out["base_cover_rate"] = float(y.mean())
    out["phcover_sd"] = float(p.std())

    print("\nDRIVER -- what is phcover a function of?")
    g["disagree"] = g.lineavg - g.line
    for name, cols in [("line", ["line"]), ("lineavg", ["lineavg"]), ("lineavg - line", ["disagree"]),
                       ("all three", ["line", "lineavg", "disagree"])]:
        X = np.column_stack([np.ones(len(g))] + [g[c].to_numpy(float) for c in cols])
        ok = np.isfinite(X).all(1)
        b, *_ = np.linalg.lstsq(X[ok], p[ok], rcond=None)
        resid = p[ok] - X[ok] @ b
        r2 = 1 - (resid**2).sum() / ((p[ok] - p[ok].mean())**2).sum()
        out[f"r2_phcover_on_{name.replace(' ', '_')}"] = float(r2)
        print(f"  phcover ~ {name:16s} R2 = {r2:.4f}")

    print("\nDISCRIMINATION -- does phcover rank covers above non-covers?")
    a = auc(y, p)
    lo, hi = cluster_boot_auc(y, p, seasons)
    out["auc"] = {"auc": a, "lo": lo, "hi": hi, "clusters": int(len(np.unique(seasons)))}
    print(f"  AUC = {a:.4f}  [{lo:.4f}, {hi:.4f}]  ({len(np.unique(seasons))} season clusters)")
    print("  0.500 = no ability to rank. An interval containing 0.500 is no discrimination.")

    print("\nCALIBRATION -- Brier score and skill against the base rate")
    brier = float(((p - y) ** 2).mean())
    brier_base = float(((y.mean() - y) ** 2).mean())
    bss = 1 - brier / brier_base
    out["brier"], out["brier_baserate"], out["brier_skill_score"] = brier, brier_base, float(bss)
    print(f"  Brier {brier:.5f}   base-rate Brier {brier_base:.5f}   skill score {bss:+.5f}")
    print("  A skill score <= 0 means the constant base rate forecasts at least as well.")

    print("\n  decile of phcover      n   mean phcover   realized cover")
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    rows = []
    for b_ in range(int(q.max()) + 1):
        m = q == b_
        rows.append({"decile": b_ + 1, "n": int(m.sum()),
                     "mean_phcover": float(p[m].mean()), "realized": float(y[m].mean())})
        print(f"  {b_+1:>2d}  {int(m.sum()):19d}   {p[m].mean():.4f}        {y[m].mean():.4f}")
    out["deciles"] = rows

    print("\n  Betting the top decile of phcover (home side):")
    top = q == int(q.max())
    print(f"    {int(top.sum())} bets, {y[top].mean():.4f} ATS vs {BREAKEVEN:.4f} break-even")
    out["top_decile"] = {"n": int(top.sum()), "ats": float(y[top].mean()), "breakeven": BREAKEVEN}

    print("")
    print("  Fading it -- betting the BOTTOM decile's home side:")
    bot = q == 0
    print(f"    {int(bot.sum())} bets, {y[bot].mean():.4f} ATS vs {BREAKEVEN:.4f} break-even")
    out["bottom_decile"] = {"n": int(bot.sum()), "ats": float(y[bot].mean())}

    # Is the top-vs-bottom decile gap real, or one or two seasons? Season-cluster bootstrap on
    # the difference in cover rate. A CI containing 0 means the inversion is not established.
    gap = y[bot].mean() - y[top].mean()
    uniq = np.unique(seasons)
    idx = {c: np.flatnonzero(seasons == c) for c in uniq}
    boots = []
    for _ in range(N_BOOT):
        take = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        qq, yy = q[take], y[take]
        mb, mt = qq == 0, qq == int(q.max())
        if mb.sum() and mt.sum():
            boots.append(yy[mb].mean() - yy[mt].mean())
    glo, ghi = float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
    out["decile_gap_bottom_minus_top"] = {"gap": float(gap), "lo": glo, "hi": ghi}
    print(f"    bottom - top cover rate = {gap:+.4f} [{glo:+.4f}, {ghi:+.4f}] (season clusters)")

    print("")
    print("STABILITY -- AUC by season")
    per = []
    for s in uniq:
        m = seasons == s
        per.append({"season": int(s), "n": int(m.sum()), "auc": auc(y[m], p[m])})
        print(f"  {int(s)}  n {int(m.sum()):4d}  AUC {per[-1]['auc']:.4f}")
    out["auc_by_season"] = per
    above = sum(1 for r in per if r["auc"] > 0.5)
    print(f"  above 0.500 in {above} of {len(per)} seasons")
    out["seasons_auc_above_half"] = above

    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
