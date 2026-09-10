"""Bet record by favorite-spread magnitude, and the favorite/dog decomposition.

Asked directly: what is the backtest record on games with a spread over 50?
The answer turns out to have a mechanism behind it, so this script reports both
the record and the leg-level errors that explain it.

The model is a DOG-floor story: censoring at zero lifts the underdog's realized
points above the spread/total-implied number, and the total goes over. It says
nothing about the favorite, which it takes at its implied number. Splitting the
realized-minus-implied error into a favorite leg and a dog leg tests whether the
edge survives at extreme spreads because the dog leg failed or because the
favorite leg turned against it.

Reads `docs/backtest_bets.csv` (written by `monitor/roi_report.py`) -- the same
walk-forward graded bets behind `docs/ROI_HITRATE.md`, so `--all` reproduces
that file's pooled 234 / 151-83 / 64.53% row as a check.

    python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py
    python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py --cut 45
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "models" / "over_zero" / "v1"))

from censoring_bias import implied_team_points  # noqa: E402

BETS = REPO / "models" / "over_zero" / "docs" / "backtest_bets.csv"
BREAK_EVEN = 100 / 110   # -110 flat, the price every ROI in ROI_HITRATE.md uses


def record(x: pd.DataFrame, label: str) -> dict:
    """Win-loss, hit rate with a Jeffreys interval, and flat ROI at -110."""
    n = len(x)
    if not n:
        return {"bucket": label, "n": 0}
    w = int(x.over.sum())
    lo, hi = stats.beta.ppf([0.025, 0.975], w + 0.5, n - w + 0.5)
    return {"bucket": label, "n": n, "record": f"{w}-{n - w}",
            "hit_rate": w / n, "ci_lo": lo, "ci_hi": hi,
            "roi": (w * BREAK_EVEN - (n - w)) / n}


def legs(x: pd.DataFrame) -> dict:
    """Mean realized-minus-implied points, split favorite vs underdog.

    `implied_team_points` is the model's own split of the spread/total pair, so
    these are errors against the number the model actually bet, not against a
    re-derived one.
    """
    return {"fav_err": x.fav_err.mean(), "dog_err": x.dog_err.mean(),
            "total_err": (x.fav_err + x.dog_err).mean()}


def load(path: Path) -> pd.DataFrame:
    b = pd.read_csv(path)
    b = b[b.passes_filter == 1].copy()
    dog_imp, fav_imp = implied_team_points(b.spread.to_numpy(), b.total.to_numpy())
    b["fav_err"] = b.fav_pts - fav_imp
    b["dog_err"] = b.dog_pts - dog_imp
    return b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", default=str(BETS))
    ap.add_argument("--cut", type=float, default=50.0,
                    help="spread magnitude splitting the two groups; strictly above")
    ap.add_argument("--bins", default="0,30,40,50",
                    help="bucket edges, read as (lo, hi]; the last is open-ended")
    args = ap.parse_args()

    b = load(Path(args.bets))
    print(f"{len(b)} graded bets (bias > 1.75, walk-forward) from "
          f"{b.season.min()}-{b.season.max()}\n")

    edges = [float(e) for e in args.bins.split(",")]
    rows = []
    for lo, hi in zip(edges, edges[1:] + [None]):
        # Buckets are (lo, hi]: half-open the other way would put a spread of exactly
        # 40 in two rows, and the counts would stop summing to the bet total.
        x = b[b.spread > lo] if hi is None else b[(b.spread > lo) & (b.spread <= hi)]
        label = f">{lo:g}" if hi is None else f"{lo:g}-{hi:g}"
        rows.append({**record(x, label), **legs(x)})
    rows.append({**record(b, "ALL"), **legs(b)})
    t = pd.DataFrame(rows)
    print(t.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # The headline split. Two-sided: censoring theory predicts the HIGH bucket does
    # better (its mean bias is larger), so a one-sided test in the observed direction
    # would be picking the tail after seeing the data.
    hi_, lo_ = b[b.spread > args.cut], b[b.spread <= args.cut]
    tab = [[int(hi_.over.sum()), len(hi_) - int(hi_.over.sum())],
           [int(lo_.over.sum()), len(lo_) - int(lo_.over.sum())]]
    print(f"\n>{args.cut:g} vs <={args.cut:g}: {tab}  Fisher two-sided p = "
          f"{stats.fisher_exact(tab)[1]:.4f}")
    print(f"mean model bias  >{args.cut:g}: {hi_.bias.mean():.3f}   "
          f"<={args.cut:g}: {lo_.bias.mean():.3f}   "
          "(theory says the higher-bias group should win MORE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
