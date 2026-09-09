"""Every method's against-the-spread record at the opener, against the price you actually pay.

R^2 of the move and CLV in points both measure whether a method anticipates the closing NUMBER.
Neither says whether backing it wins BETS. That needs the ATS record compared to the break-even
a -110 line demands: 110/210 = 52.381%. A method can carry real, significant CLV and still sit
below that, because a point of spread buys less win probability on a big number than a small one.

This tabulates every method and threshold from the registered opener-CLV tables and marks which,
if any, clear break-even with an interval that excludes it. It exists because
`line-movement-results.md` claimed for a while that the ATS record "confirms the CLV is cashable"
-- and the two rows holding that claim up were a method later retired as a grid artifact, and a
35-bet cell whose 95% interval ran past 100%.

    python research/spread/scripts/eval_ats_vs_breakeven.py

Reads the amendment A2/A6 walk-forward run (all ten methods, one support, n = 14,068).
EXPLORATORY, like every archive result here: the one confirmatory hypothesis is the version B E4
slope at the Monday anchor. No new fitting happens -- these are the registered runs' own numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

SRC = base.OUT_DIR / "pt_movement_a2_decon_wf.json"
OUT = base.OUT_DIR / "pt_ats_vs_breakeven.json"
JUICE = -110
BREAKEVEN = 110 / 210            # 52.381% -- what -110 demands just to stay level
MIN_BETS = 100                   # below this an interval is decoration, not evidence


def roi_at_110(rate: float) -> float:
    """A won bet returns 100/110; a lost one returns -1."""
    return rate * (100 / 110) - (1 - rate)


def main() -> int:
    d = json.loads(SRC.read_text())
    rows = d["clv_open"]
    print(f"n = {d['n']:,} games, seasons {d['seasons'][0]}-{d['seasons'][-1]}, "
          f"walk-forward decontaminated panel (A6)")
    print(f"break-even at {JUICE} is {BREAKEVEN:.3%}. CLV is in points; ATS is in bets.\n")
    print(f"{'method':>7} {'thr':>4} {'bets':>6} {'CLV':>7} {'ATS':>8} {'95% CI':>18} "
          f"{'vs B/E':>8} {'ROI':>8}  verdict")

    out, clears = [], []
    for r in sorted(rows, key=lambda x: (-x["ats_open"], x["method"])):
        rate, lo, hi, n = r["ats_open"], r["ats_lo"], r["ats_hi"], r["bets"]
        gap, roi = rate - BREAKEVEN, roi_at_110(rate)
        thin = n < MIN_BETS
        broken = hi > 1.0                      # normal approximation has left the building
        beats = lo > BREAKEVEN and not thin and not broken
        verdict = ("CLEARS" if beats else
                   "interval not valid" if broken else
                   f"only {n} bets" if thin else
                   "does not clear")
        print(f"{r['method']:>7} {r['thr']:>4.0f} {n:6d} {r['clv']:+7.2f} {rate:8.1%} "
              f"[{lo:6.1%},{hi:6.1%}] {gap:+8.1%} {roi:+8.1%}  {verdict}")
        out.append({**r, "gap_vs_breakeven": gap, "roi_110": roi,
                    "clears_breakeven": bool(beats), "verdict": verdict})
        if beats:
            clears.append(f"{r['method']} at |pred| >= {r['thr']:.0f}")

    print()
    if clears:
        print("Clears break-even with an interval excluding it: " + ", ".join(clears))
    else:
        print("NOTHING clears break-even with an interval excluding it.")
    print("An interval that merely excludes 50% is not the test -- 50% is not the price. A bet at")
    print(f"{JUICE} has to win {BREAKEVEN:.1%} of the time before it returns a cent, and every")
    print("number above is measured at the opener, which PT's timing cannot reach anyway.")

    OUT.write_text(json.dumps({"source": SRC.name, "n": d["n"], "juice": JUICE,
                               "breakeven": BREAKEVEN, "min_bets": MIN_BETS,
                               "rows": out, "clears": clears}, indent=2, default=float))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
