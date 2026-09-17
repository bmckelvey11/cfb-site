"""Is the slate's "edge" just the market having moved away from the opener?

E4 and its siblings predict the close ANCHORED ON THE OPENER. `weekly_slate.py` then compares
that prediction to the CURRENT book fair and calls the difference `edge`. If E4 barely leaves
the opener, that subtraction reproduces the move the market already made, with the sign flipped
-- so every "edge" is a bet the line retraces to its opener, which is the opposite of the
momentum claim the archive validated.

This regresses edge on the realized move since the opener over the served slate. A slope near
-1 and a correlation near -1 mean the edge carries no information beyond "the line moved."

    python research/spread/scripts/edge_vs_market_move.py [--slate <path>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slate", type=Path, default=base.OUT_DIR / "weekly_slate_latest.csv")
    ap.add_argument("--pred", default="E4")
    a = ap.parse_args()

    s = pd.read_csv(a.slate).dropna(subset=[a.pred, "book_fair", "open_pt", "line_pt"])
    moved = (s.line_pt - s.open_pt).to_numpy(float)
    edge = (s[a.pred] - s.book_fair).to_numpy(float)

    slope, intercept = np.polyfit(moved, edge, 1)
    print(f"{a.slate.name}: {len(s)} games, predictor {a.pred}")
    print(f"  corr(edge, move since opener) = {np.corrcoef(moved, edge)[0, 1]:+.3f}")
    print(f"  edge = {intercept:+.2f} {slope:+.2f} x (move since opener)")
    print(f"  -> each point the market moved off the opener creates {-slope:.2f} pts of edge")
    print(f"  mean |{a.pred} - open_pt|   = {np.abs(s[a.pred] - s.open_pt).mean():.2f}")
    print(f"  mean |{a.pred} - book_fair| = {np.abs(s[a.pred] - s.book_fair).mean():.2f}")
    print("\n  A slope near -1 means the edge is the market's own move, sign-flipped: betting it")
    print("  is a retrace-to-opener trade, not the momentum-from-the-opener trade the archive")
    print("  validated. See research/spread/docs/actionable-picks-2026-09-17.md section 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
