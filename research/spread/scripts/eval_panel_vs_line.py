"""What ARE the ~140 `line*` columns in PT's panel?

EXPLORATORY, descriptive. Not registered in `prereg-line-movement.md`. Pooled and in-sample by
design -- this characterises the columns, it does not select among them. Walk-forward selection
is `prior_skill()` / `walk_forward()` in `eval_prediction_tracker_models.py`; use those to pick
a model, not this.

Three questions, each answered against the market line on each model's OWN support (the line's
RMSE is recomputed per column, so models covering different eras stay comparable to their own
benchmark):

  ARE THEY THE LINE?   R^2 of the column on `line`, slope, and sd of (model - line). A column
                       that is just the line re-published shows R^2 ~ 1 and sd ~ 0.

  DO THEY FORECAST?    RMSE against the realized margin, as a ratio to the line's RMSE on the
                       same games. Ratio < 1 means the column beat the closing number.

  WHAT PREDICTS SKILL? Correlation between how far a column strays from the line and how badly
                       it forecasts. If that correlation is strongly positive, deviation from
                       the line is error, not information -- and the panel carries nothing the
                       market does not already have.

`MARKET_LINES` (`lineca`, `linemidweek`) are excluded: they are market prices, not models.

    python research/spread/scripts/eval_panel_vs_line.py [--min-n 500]
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

OUT = base.OUT_DIR / "panel_vs_line.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=500,
                    help="skip columns with fewer graded games than this")
    a = ap.parse_args()

    df, models = base.load()
    d = df[df.line.notna()].copy()
    line = d.line.to_numpy(float)
    y = d.y.to_numpy(float)

    rows = []
    for m in models:
        if m in base.MARKET_LINES:
            continue
        v = d[m].to_numpy(float)
        ok = np.isfinite(v) & np.isfinite(line) & np.isfinite(y)
        if ok.sum() < a.min_n:
            continue
        rmse_m = float(np.sqrt(np.mean((y[ok] + v[ok]) ** 2)))
        rmse_l = float(np.sqrt(np.mean((y[ok] + line[ok]) ** 2)))
        slope = float(np.polyfit(line[ok], v[ok], 1)[0])
        rows.append({"model": m, "n": int(ok.sum()),
                     "r2_vs_line": float(np.corrcoef(v[ok], line[ok])[0, 1] ** 2),
                     "slope_on_line": slope,
                     "sd_deviation": float(np.std(v[ok] - line[ok])),
                     "rmse": rmse_m, "rmse_line": rmse_l, "ratio": rmse_m / rmse_l})
    t = pd.DataFrame(rows).sort_values("ratio").reset_index(drop=True)
    pd.set_option("display.width", 200)

    print("%d model columns with >= %d graded games (MARKET_LINES excluded)"
          % (len(t), a.min_n))
    print("line RMSE overall %.2f pts; sd of the margin %.2f"
          % (np.sqrt(np.mean((y + line) ** 2)), y.std()))

    print("")
    print("BEST TEN by RMSE ratio to the line (ratio < 1 would beat it)")
    print(t.head(10).to_string(index=False, float_format=lambda x: "%.4f" % x))
    print("")
    print("WORST EIGHT")
    print(t.tail(8).to_string(index=False, float_format=lambda x: "%.4f" % x))

    beat = int((t.ratio < 1).sum())
    print("")
    print("models beating the line: %d of %d      within 5%%: %d"
          % (beat, len(t), int((t.ratio < 1.05).sum())))
    print("ratio: median %.4f  best %.4f  worst %.4f"
          % (t.ratio.median(), t.ratio.min(), t.ratio.max()))

    print("")
    print("WHAT PREDICTS SKILL")
    c_sd = float(np.corrcoef(t.ratio, t.sd_deviation)[0, 1])
    c_r2 = float(np.corrcoef(t.ratio, t.r2_vs_line)[0, 1])
    print("  corr(RMSE ratio, sd of deviation from the line) = %+.3f" % c_sd)
    print("  corr(RMSE ratio, R^2 on the line)               = %+.3f" % c_r2)
    t["bin"] = pd.cut(t.sd_deviation, [0, 3, 5, 8, 12, 1e9],
                      labels=["<3pt", "3-5", "5-8", "8-12", ">12"])
    binned = t.groupby("bin", observed=True).agg(
        models=("model", "size"), mean_ratio=("ratio", "mean"), best=("ratio", "min"))
    print("")
    print("  binned by how far the column strays from the line:")
    print(binned.to_string(float_format=lambda x: "%.4f" % x))
    print("")
    print("  A strongly POSITIVE corr means straying from the line is error, not information.")

    OUT.write_text(json.dumps(
        {"n_models": len(t), "min_n": a.min_n, "n_beating_line": beat,
         "ratio_median": float(t.ratio.median()), "ratio_best": float(t.ratio.min()),
         "ratio_worst": float(t.ratio.max()),
         "corr_ratio_sd_deviation": c_sd, "corr_ratio_r2_line": c_r2,
         "binned": [{"bin": str(i), "models": int(r.models), "mean_ratio": float(r.mean_ratio),
                     "best": float(r.best)} for i, r in binned.iterrows()],
         "models": t.drop(columns=["bin"]).to_dict("records")}, indent=2))
    print("")
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
