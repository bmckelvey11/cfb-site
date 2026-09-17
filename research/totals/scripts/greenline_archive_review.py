"""Grade the PFF Greenline archive: does the vendor's self-reported record clear its floor?

Reads the CSV that `parse_greenline_history.py` writes. Reports, per split, the realized
hit rate against the break-even implied by the price actually quoted, the ROI that follows
from it, and the minimum detectable win rate for that sample size.

Three things this is careful about, because each one flips a conclusion:

  The archive is TWO-SIDED. Every game/market carries both sides, so all-rows pooling
  returns 50% and ~0 CLV as an arithmetic identity. Only `is_greenline_pick` rows are bets.

  Hit rate is NOT comparable across markets. A moneyline pick on a +135 dog breaks even
  at 42.6%, not 52.38%, so a 41.7% moneyline hit rate is close to a coin flip on price
  rather than a disaster. Every split is therefore judged against the mean break-even of
  its own rows -- PFF publishes it per bet -- and ROI is computed from the implied decimal
  price, not from a flat -110 assumption.

  MDE is the gate. Per `research/totals/CLAUDE.md`, no split is called an edge until it
  clears the minimum win rate its own n could detect (one-sided, alpha 0.05, power 0.80).
  The `verdict` column says `below floor` whenever it does not, in either direction.

Usage:
    python research/totals/scripts/greenline_archive_review.py
    python research/totals/scripts/greenline_archive_review.py --csv PATH
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

ALPHA = 0.05      # one-sided
POWER = 0.80
PICK_SNAPSHOT = "open_greenline"   # never "close" -- that selection is result-informed


def mde(n: int, p0: float) -> float:
    """Smallest true win rate a sample of n could distinguish from p0."""
    if n <= 0 or not 0 < p0 < 1:
        return float("nan")
    z_a = stats.norm.ppf(1 - ALPHA)
    z_b = stats.norm.ppf(POWER)
    return p0 + (z_a + z_b) * ((p0 * (1 - p0) / n) ** 0.5)


def grade(pool: pd.DataFrame) -> dict | None:
    """One split. Break-even comes from the quoted price, not a flat -110."""
    dec = pool[pool["bet_result"].isin(["W", "L"])].copy()
    if dec.empty:
        return None
    be = dec["breakeven_prob"].dropna()
    p0 = float(be.mean()) if len(be) else 0.5238
    hit = float((dec["bet_result"] == "W").mean())

    # breakeven = 1/decimal, so a win pays (1/breakeven - 1) per unit staked.
    priced = dec[dec["breakeven_prob"].notna()].copy()
    if priced.empty:
        roi = float("nan")
    else:
        payout = 1.0 / priced["breakeven_prob"] - 1.0
        won = priced["bet_result"] == "W"
        roi = float((won * payout - (~won) * 1.0).mean())

    floor = mde(len(dec), p0)
    return {
        "n": len(dec),
        "hit": hit,
        "breakeven": p0,
        "vs_be": hit - p0,
        "roi": roi,
        "mde": floor,
        "verdict": "clears floor" if hit >= floor else "below floor",
    }


def report(df: pd.DataFrame) -> pd.DataFrame:
    graded = df[df["snapshot"] == PICK_SNAPSHOT].copy()
    picks = graded[graded["is_greenline_pick"] == True]  # noqa: E712

    rows = []

    def add(label: str, pool: pd.DataFrame) -> None:
        g = grade(pool)
        if g:
            rows.append({"split": label, **g})

    add("ALL ROWS (both sides)", graded)
    add("picks: all", picks)
    for season, s_grp in picks.groupby("season", dropna=True):
        add(f"picks: {int(season)}", s_grp)
        for market, m_grp in s_grp.groupby("market", dropna=True):
            add(f"picks: {int(season)} {market}", m_grp)
    return pd.DataFrame(rows)


def self_check() -> None:
    """Synthesise splits with known answers and confirm the grader recovers them."""
    # MDE shrinks with n and always sits above the break-even it is measured from.
    assert mde(100, 0.5238) > mde(1000, 0.5238) > 0.5238
    assert abs(mde(360, 0.5238) - 0.589) < 0.002, mde(360, 0.5238)

    def pool(n_win, n_loss, be):
        return pd.DataFrame({
            "bet_result": ["W"] * n_win + ["L"] * n_loss,
            "breakeven_prob": [be] * (n_win + n_loss),
        })

    # A coin flip priced at -110 loses the vig: 50% at be 0.5238 => ROI ~ -4.5%.
    g = grade(pool(50, 50, 0.5238))
    assert abs(g["hit"] - 0.50) < 1e-9 and g["verdict"] == "below floor"
    assert abs(g["roi"] - (0.5 * (1 / 0.5238 - 1) - 0.5)) < 1e-9, g

    # A 41.7% moneyline priced at +150 (be 0.40) is PROFITABLE -- the whole reason
    # hit rate is never compared across markets.
    g = grade(pool(42, 58, 0.40))
    assert g["hit"] < 0.50 and g["roi"] > 0, g
    assert g["vs_be"] > 0, g

    # A big enough sample well past its floor is allowed to clear it.
    g = grade(pool(700, 300, 0.5238))
    assert g["verdict"] == "clears floor", g

    # A push is not a decided bet and must not count either way.
    g = grade(pd.DataFrame({"bet_result": ["W", "L", "P"],
                            "breakeven_prob": [0.5238] * 3}))
    assert g["n"] == 2, g

    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path,
                    default=INGEST / "pff_scoreboard" / "greenline_history_archive.csv")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    df = pd.read_csv(args.csv)
    print(f"archive: {args.csv}  ({len(df)} rows)\n")

    out = report(df)
    show = out.copy()
    for c in ("hit", "breakeven", "vs_be", "mde"):
        show[c] = (100 * show[c]).round(1)
    show["roi"] = (100 * show["roi"]).round(2)
    show.columns = ["split", "n", "hit%", "breakeven%", "hit-be", "roi%", "mde%", "verdict"]
    print(show.to_string(index=False))

    clv = df[(df["snapshot"] == "close") & (df["is_greenline_pick"] == True)]["clv"]  # noqa: E712
    clv = clv.dropna()
    if len(clv):
        t = stats.ttest_1samp(clv, 0.0)
        print(f"\nCLV on picks (PFF's own, close vs its own opening number):")
        print(f"  n={len(clv)}  mean={clv.mean():+.4f}  median={clv.median():+.4f}  "
              f"t={t.statistic:+.2f}  p={t.pvalue:.4f}")

    print("\nWhat this does not support:")
    print("  - These are PFF's own published lines and its own CLV, graded against its own")
    print("    opening number. It prices Greenline vs its close, not vs a book you could")
    print("    actually reach, and it is not an independent audit of the vendor.")
    print("  - 2020 is the COVID season (reduced, reshuffled schedule). One season of one")
    print("    vendor's self-report is not a basis for sizing.")
    print("  - Any split marked 'below floor' is not evidence in either direction.")


if __name__ == "__main__":
    main()
