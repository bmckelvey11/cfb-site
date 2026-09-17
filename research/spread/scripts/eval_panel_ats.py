"""Does any single panel model have an ATS edge, whatever its RMSE?

EXPLORATORY. Not registered in `prereg-line-movement.md`.

`eval_panel_vs_line.py` showed no column beats the market line on RMSE. That is a weak test of
bettability and must not be read as one: RMSE is squared, symmetric, and averaged over every
game, so it is dominated by the middle of the distribution. A bet needs only the SIGN of the
disagreement to be right, only on the games you choose, and only 52.381% of the time. A model
can be worse on average and still profitable on a subset.

So this asks the betting question directly, per model:

  Bet the side the model favours when it disagrees with the line by at least a threshold.
  Model implies home margin -model, market implies -line, so the model favours HOME iff
  (model - line) < 0. Home covers iff y + line > 0. Pushes dropped.

141 models x 3 thresholds is a lot of chances to find a winner by luck, so:

  * season-cluster bootstrap SE for every cell
  * Benjamini-Hochberg q-values over the whole family (`base.bh_qvalues`)
  * IN-SAMPLE and pooled -- a surviving cell is a hypothesis to test walk-forward, never an
    edge. `prior_skill()` / `walk_forward()` are the registered machinery for that.

    python research/spread/scripts/eval_panel_ats.py [--min-bets 200]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "panel_ats.json"
BREAKEVEN = 110 / 210
THRESHOLDS = [1.0, 2.0, 3.0]
N_BOOT = 1000
RNG = np.random.default_rng(20260917)


def cluster_se(x: np.ndarray, clusters: np.ndarray) -> float:
    uniq = np.unique(clusters)
    if len(uniq) < base.MIN_CLUSTERS:
        return float("nan")
    idx = {c: np.flatnonzero(clusters == c) for c in uniq}
    vals = []
    for _ in range(N_BOOT):
        take = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        if len(take):
            vals.append(x[take].mean())
    return float(np.std(vals))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-bets", type=int, default=200)
    a = ap.parse_args()

    df, models = base.load()
    d = df[df.line.notna()].copy()
    line = d.line.to_numpy(float)
    y = d.y.to_numpy(float)
    seasons = d.season.to_numpy(int)
    edge_cover = y + line
    live = edge_cover != 0                       # drop pushes
    home_covers = (edge_cover > 0).astype(int)

    rows = []
    for m in models:
        if m in base.MARKET_LINES:
            continue
        v = d[m].to_numpy(float)
        for thr in THRESHOLDS:
            disagree = v - line
            sel = np.isfinite(disagree) & live & (np.abs(disagree) >= thr)
            if sel.sum() < a.min_bets:
                continue
            bet_home = disagree[sel] < 0
            won = np.where(bet_home, home_covers[sel] == 1, home_covers[sel] == 0).astype(float)
            se = cluster_se(won, seasons[sel])
            z = (won.mean() - BREAKEVEN) / se if se and np.isfinite(se) and se > 0 else np.nan
            rows.append({"model": m, "thr": thr, "bets": int(sel.sum()),
                         "ats": float(won.mean()), "se": se, "z": float(z),
                         "seasons": int(len(np.unique(seasons[sel])))})

    t = pd.DataFrame(rows)
    # two-sided p from the cluster-bootstrap z, then BH across the whole family
    from math import erfc, sqrt
    t["p"] = [erfc(abs(z) / sqrt(2)) if np.isfinite(z) else 1.0 for z in t.z]
    t["q"] = base.bh_qvalues(t.p.to_numpy())
    t = t.sort_values("ats", ascending=False).reset_index(drop=True)
    pd.set_option("display.width", 220)

    print("%d model-threshold cells with >= %d bets (%d models)"
          % (len(t), a.min_bets, t.model.nunique()))
    print("break-even at -110 = %.5f" % BREAKEVEN)
    print("")
    print("TOP 12 BY RAW ATS")
    print(t.head(12).to_string(index=False, float_format=lambda x: "%.4f" % x))

    clears = t[(t.ats > BREAKEVEN) & (t.q < 0.10)]
    print("")
    print("cells above break-even at all:              %d of %d" % (int((t.ats > BREAKEVEN).sum()), len(t)))
    print("cells above break-even with raw p < 0.05:   %d" % int(((t.ats > BREAKEVEN) & (t.p < 0.05)).sum()))
    print("cells surviving BH q < 0.10 (the real bar): %d" % len(clears))
    if len(clears):
        print(clears.to_string(index=False, float_format=lambda x: "%.4f" % x))
    print("")
    print("pooled ATS across every cell: %.4f   median cell ATS: %.4f"
          % (float(np.average(t.ats, weights=t.bets)), float(t.ats.median())))

    OUT.write_text(json.dumps({"breakeven": BREAKEVEN, "min_bets": a.min_bets,
                               "n_cells": len(t), "n_models": int(t.model.nunique()),
                               "n_above_breakeven": int((t.ats > BREAKEVEN).sum()),
                               "n_bh_survivors": int(len(clears)),
                               "cells": t.to_dict("records")}, indent=2))
    print("")
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
