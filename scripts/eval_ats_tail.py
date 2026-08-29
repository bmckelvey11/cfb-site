"""Is there an actionable ATS edge in the disagreement tail?

Pre-registered in docs/prereg-ats-tail-test.md and committed BEFORE this ran. Buckets, bet
rule, breakeven, inference and the stopping rule are fixed there. One run, no re-cutting.

The combination work measured squared error. Betting is decided by sign against a threshold,
which is a different objective, so this tests the thing that actually determines whether the
predictions can be acted on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
from eval_combination_sweep import holm  # noqa: E402

SRC = base.OUT_DIR / "pt_ensemble_spread_closing.csv"
BREAKEVEN = 1 / 1.909091          # -110: risk 110 to win 100 -> 0.523809...
EDGES = [(0, 1), (1, 2), (2, 3), (3, 5), (5, np.inf)]


def graded(df):
    """Bet the side the consensus prefers; grade against the closing spread.

    cover = actual_margin + market_spread, so > 0 means the HOME side covered.
    """
    d = df.dropna(subset=["edge_vs_market", "actual_margin", "market_spread"]).copy()
    cover = d["actual_margin"] + d["market_spread"]
    bet_home = d["edge_vs_market"] > 0
    d["push"] = cover == 0
    d["win"] = np.where(bet_home, cover > 0, cover < 0)
    d["abs_edge"] = d["edge_vs_market"].abs()
    # an exactly-zero edge picks no side at all
    return d[(d["edge_vs_market"] != 0) & ~d["push"]]


def boot(win, season, n_boot=base.N_BOOT):
    """Wild cluster bootstrap by season for (win rate - breakeven)."""
    d = win.astype(float) - BREAKEVEN
    return base.wild_cluster_boot(d, season)


def run(df, label):
    g = graded(df)
    rows = []
    for lo, hi in EDGES:
        sel = g[(g.abs_edge >= lo) & (g.abs_edge < hi)]
        if len(sel) < 50:
            rows.append({"bucket": f"[{lo},{hi})", "n": len(sel)})
            continue
        wr = float(sel["win"].mean())
        mean, ci, p = boot(sel["win"].to_numpy(), sel["season"].to_numpy())
        # units won per unit risked at -110
        roi = wr * (100 / 110) - (1 - wr)
        rows.append({"bucket": f"[{lo},{hi})", "n": len(sel), "win_rate": wr,
                     "vs_breakeven": mean, "ci_lo": ci[0], "ci_hi": ci[1], "p": p,
                     "roi_at_-110": roi})
    t = pd.DataFrame(rows)
    if "p" in t:
        t["p_holm"] = np.nan
        ok = t.p.notna()
        t.loc[ok, "p_holm"] = holm(t.loc[ok, "p"].to_numpy())
    print(f"\n{'='*78}\nATS TAIL TEST -- {label}\n{'='*78}")
    print(f"breakeven at -110 = {BREAKEVEN:.4f}; bootstrap p floor = {1/base.N_BOOT:.5f}")
    print(f"graded bets: {len(g)} of {len(df)} rows "
          f"({len(df) - len(g)} pushes or zero-edge)\n")
    print(t.to_string(index=False))
    return t, g


def main():
    df = pd.read_csv(SRC)
    t, g = run(df, "E4 screened consensus vs the closing line")

    print(f"\noverall: {g['win'].mean():.4f} on {len(g)} bets "
          f"(breakeven {BREAKEVEN:.4f})")
    m, ci, p = boot(g["win"].to_numpy(), g["season"].to_numpy())
    print(f"  vs breakeven {m:+.4f} [{ci[0]:+.4f},{ci[1]:+.4f}] p={p:.4f}")

    clears = t[t.get("p_holm", pd.Series(dtype=float)).notna()
               & (t.get("win_rate", pd.Series(dtype=float)) > BREAKEVEN)
               & (t.get("p_holm", pd.Series(dtype=float)) < 0.05)] if "p_holm" in t else t.iloc[:0]
    print("\n" + "-" * 78)
    if len(clears):
        print("A bucket cleared breakeven. Per the pre-registration this is NOT a system:")
        print("one post-hoc-flavoured slice, no confirmation window, eight prior defects.")
        print(clears.to_string(index=False))
    else:
        print("NO bucket clears the -110 breakeven after Holm. This is the pre-registered")
        print("expectation and it means the predictions are not actionable against the close.")
    t.to_csv(base.OUT_DIR / "pt_ats_tail_closing.csv", index=False)


def _check():
    """Grading is the whole test; a wrong cover rule would invent or destroy an edge."""
    d = pd.DataFrame({
        # rows 0,1: home favoured by 17, won by 8 -> did NOT cover
        # row 2: cover lands exactly on the number -> push
        # row 3: consensus agrees with the market exactly -> no side to bet
        "edge_vs_market": [1.2, -1.2, 2.0, 0.0],
        "actual_margin": [8.0, 8.0, 3.0, 5.0],
        "market_spread": [-17.0, -17.0, -3.0, -3.0],
        "season": [2006] * 4,
    })
    g = graded(d)
    assert len(g) == 2, "a push and a zero edge must both be dropped"
    assert not g.iloc[0]["win"], "home bet must lose when the favourite fails to cover"
    assert g.iloc[1]["win"], "away bet must win on the same game"
    assert abs(BREAKEVEN - 0.5238) < 1e-3, "-110 breakeven"
    print("checks pass")


if __name__ == "__main__":
    _check()
    main()
