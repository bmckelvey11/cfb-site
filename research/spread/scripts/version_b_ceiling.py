"""How much CLV is even available at the version B anchor, and when is the anchor captured?

Version B grades E4's side against the real close, taken at the week's first snapshot on or
after Monday 00:00 ET (`eval_version_b.monday_anchor`). Two questions this answers that the
slope and the bet table do not:

  CEILING   With perfect foresight of sign(close - anchor), mean CLV is E|close - anchor|.
            That is the most any forecast anchored here can win, before vig. Compare it to
            the 2-4 points the archive measured AT THE OPENER
            (research/spread/docs/line-movement-results.md) to see how much of the move is
            already gone by the time the forward collector can act.

  ANCHOR     Which ET weekday each week's anchor actually landed on. Amendment B2's "mon"
  WEEKDAY    bucket is empty in the served artifact; this says whether that is PT's slate
             rollover or simply a week the collector did not run on Monday.

Neither number is a verdict. Amendment B3 still governs when version B may be read.

    python research/spread/scripts/version_b_ceiling.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_version_b as vb  # noqa: E402


def main() -> int:
    log = pd.read_csv(vb.LOG)
    g = vb.monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [vb.close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    graded = g[g.close.notna() & (g.kick_utc < datetime.now(timezone.utc))].copy()
    if len(graded) < 30:
        print(f"{len(graded)} graded games -- nothing to estimate yet")
        return 0

    move = (graded.close - graded.line_pt).to_numpy(float)
    edge = np.abs((graded.E4 - graded.line_pt).to_numpy(float))

    print(f"graded {len(graded)} games over {graded.week.nunique()} week(s): "
          f"{sorted(graded.week.unique())}")
    print("\nCEILING -- mean CLV under perfect foresight of the move from the anchor")
    print(f"  {'bucket':12s} {'games':>6s} {'E|move|':>9s} {'sd(move)':>9s}")
    for label, m in [("all", np.ones(len(move), bool)),
                     ("|edge| >= 1", edge >= 1.0),
                     ("|edge| >= 2", edge >= 2.0)]:
        if m.sum() < 5:
            print(f"  {label:12s} {int(m.sum()):6d}   too few")
            continue
        print(f"  {label:12s} {int(m.sum()):6d} {np.abs(move[m]).mean():9.2f} {move[m].std():9.2f}")
    print("  A forecast capturing a fraction f of the move earns f x E|move| points of CLV.")
    print("  Breakeven at -110 is 52.38% ATS; ~0.5 pt of CLV is worth roughly 1-2% ATS.")

    print("\nANCHOR WEEKDAY -- ET weekday of each week's anchor capture")
    a = graded.copy()
    a["anchor_et"] = pd.to_datetime(a.captured_utc, utc=True, format="mixed").dt.tz_convert(vb.ET)
    for week, sub in a.groupby("week"):
        first = sub.anchor_et.min()
        days = sorted(sub.anchor_et.dt.day_name().unique())
        print(f"  {week}: first anchor {first.strftime('%a %Y-%m-%d %H:%M ET')}  "
              f"weekdays {days}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
