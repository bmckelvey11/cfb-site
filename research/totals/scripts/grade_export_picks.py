"""Grade the 2022-23 Greenline export picks against CFBD finals.

`parse_greenline_history.py` derives 220 picks on the three `ncaa-best-bets*.csv` slates.
The source carries no result, so the only way to grade them is from the final score --
which this does, at the line in the capture, per the unit's standing rule.

WHAT THIS CANNOT PRODUCE, and why there is no ROI column:

  The exports carry no price. `breakeven_prob` is NULL on every export row, so the price
  each pick was offered at is not reconstructible at decision time. Executable prices are
  an integrity gate in `docs/model-evaluation-standard.md`, and a failure at the integrity
  layer "should invalidate the financial score rather than merely reduce it". So this
  reports a record, never a return.

  For the same reason MONEYLINE IS NOT JUDGEABLE AT ALL. A moneyline pick's break-even is
  entirely a function of its price -- a +300 dog hitting 30% is profitable, a -3000 chalk
  hitting 90% is not -- so its hit rate carries no verdict. It is printed for completeness
  and scored `n/a`.

  Spread and total are judged against 52.38% (-110 both ways). That is an ASSUMPTION about
  a price we do not have, not an observation, and it is the reason those verdicts are
  weaker than the PFF_hist ones in greenline-archive-2026-09-17.md, where PFF published a
  break-even per bet.

  PFF's cover probability is not recoverable either: the exports give `Value` (its edge
  over its own break-even) without that break-even, so no proper score can be computed
  against a de-vigged market. There is no Brier or log score here by omission, not oversight.

Dependence: a game contributes up to three picks, and a favourite covering the spread and
winning the moneyline is close to the same event twice. Intervals are therefore reported
both unclustered (Wilson) and clustered by game (bootstrap over games, not rows).

Trials: one. The `> 0` rule is PFF's own, applied as-is, with no threshold fitted here.

Usage:
    python research/totals/scripts/grade_export_picks.py
    python research/totals/scripts/grade_export_picks.py --self-check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

ARCHIVE = INGEST / "pff_scoreboard" / "greenline_history_archive.csv"

ALPHA = 0.05      # one-sided, matching greenline_archive_review.py
POWER = 0.80
FLAT_110 = 0.5238   # assumed break-even; see the docstring
BOOT = 10_000
SEED = 20260921


def mde(n: int, p0: float) -> float:
    """Smallest true win rate a sample of n could distinguish from p0."""
    if n <= 0 or not 0 < p0 < 1:
        return float("nan")
    return p0 + (stats.norm.ppf(1 - ALPHA) + stats.norm.ppf(POWER)) * (
        (p0 * (1 - p0) / n) ** 0.5)


def wilson(w: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p, z2 = w / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5) / denom
    return (centre - half, centre + half)


def grade_row(market: str, side: str, line: float | None,
              home_pts: float | None, away_pts: float | None) -> str | None:
    """W / L / P for one pick, at the line in the capture.

    `line` is already the number as that side takes it (`side_line` in the parser): the
    home spread for `home`, its negation for `away`, the total for both `over`/`under`.
    """
    if home_pts is None or away_pts is None or pd.isna(home_pts) or pd.isna(away_pts):
        return None
    if market == "moneyline":
        mine = home_pts if side == "home" else away_pts
        theirs = away_pts if side == "home" else home_pts
        return "W" if mine > theirs else ("P" if mine == theirs else "L")
    if line is None or pd.isna(line):
        return None
    if market == "total":
        total = home_pts + away_pts
        if total == line:
            return "P"
        return "W" if ((total > line) == (side == "over")) else "L"
    if market == "spread":
        margin = (home_pts - away_pts) if side == "home" else (away_pts - home_pts)
        edge = margin + line
        return "P" if edge == 0 else ("W" if edge > 0 else "L")
    return None


def cluster_ci(dec: pd.DataFrame, rng: np.random.Generator) -> tuple[float, float]:
    """95% interval resampling GAMES, not rows -- picks on one game are not independent."""
    games = dec["game_id"].dropna().unique()
    if len(games) == 0:
        return (float("nan"), float("nan"))
    by_game = {g: d["won"].to_numpy() for g, d in dec.groupby("game_id")}
    draws = np.empty(BOOT)
    for i in range(BOOT):
        pick = rng.choice(games, size=len(games), replace=True)
        vals = np.concatenate([by_game[g] for g in pick])
        draws[i] = vals.mean()
    return tuple(np.percentile(draws, [2.5, 97.5]))


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for label, pool in [("ALL (ex moneyline)", df[df["market"] != "moneyline"]),
                        ("spread", df[df["market"] == "spread"]),
                        ("total", df[df["market"] == "total"]),
                        ("moneyline", df[df["market"] == "moneyline"])]:
        dec = pool[pool["result"].isin(["W", "L"])].copy()
        if dec.empty:
            continue
        dec["won"] = (dec["result"] == "W").astype(float)
        w, n = int(dec["won"].sum()), len(dec)
        lo, hi = wilson(w, n)
        clo, chi = cluster_ci(dec, rng)
        judged = label != "moneyline"
        floor = mde(n, FLAT_110) if judged else float("nan")
        hit = w / n
        rows.append({
            "split": label, "n": n, "W": w, "L": n - w,
            "push": int((pool["result"] == "P").sum()),
            "games": int(dec["game_id"].nunique()),
            "hit": hit, "wilson_lo": lo, "wilson_hi": hi,
            "game_lo": clo, "game_hi": chi,
            "mde": floor,
            "verdict": ("not judgeable -- no price" if not judged
                        else ("clears floor" if hit >= floor else "below floor")),
        })
    return pd.DataFrame(rows)


def load() -> pd.DataFrame:
    df = pd.read_csv(ARCHIVE)
    picks = df[(df["snapshot"] == "export") & (df["is_greenline_pick"] == True)].copy()  # noqa: E712
    picks["result"] = [
        grade_row(r.market, r.side, r.market_line, r.home_points, r.away_points)
        for r in picks.itertuples()
    ]
    return picks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return 0

    picks = load()
    ungradeable = picks["result"].isna().sum()
    print(f"archive: {ARCHIVE}")
    print(f"export picks: {len(picks)}   graded: {len(picks) - ungradeable}   "
          f"no final score: {ungradeable}")
    print(f"distinct games: {picks['game_id'].nunique()}   "
          f"slates: {picks['source_file'].nunique()}\n")

    out = summarize(picks)
    show = out.copy()
    for c in ("hit", "wilson_lo", "wilson_hi", "game_lo", "game_hi", "mde"):
        show[c] = (100 * show[c]).round(1)
    show.columns = ["split", "n", "W", "L", "push", "games", "hit%", "wil_lo", "wil_hi",
                    "gm_lo", "gm_hi", "mde%", "verdict"]
    print(show.to_string(index=False))
    print("\nNo ROI column: the exports carry no price, which is an integrity-gate")
    print("failure under docs/model-evaluation-standard.md. Spread/total are judged")
    print("against an ASSUMED 52.38%; moneyline cannot be judged at all.")
    return 0


def self_check() -> None:
    # Total: the capture line decides, and an exact landing is a push.
    assert grade_row("total", "over", 54.0, 30, 28) == "W"    # 58 > 54
    assert grade_row("total", "under", 54.0, 30, 28) == "L"
    assert grade_row("total", "under", 54.0, 20, 24) == "W"   # 44 < 54
    assert grade_row("total", "over", 54.0, 27, 27) == "P"    # lands exactly

    # Spread: `line` is already signed for the side taking it. Home -7 needs to win by 8.
    assert grade_row("spread", "home", -7.0, 28, 20) == "W"   # margin 8, 8-7 > 0
    assert grade_row("spread", "home", -7.0, 27, 20) == "P"   # margin 7, lands on it
    assert grade_row("spread", "home", -7.0, 26, 20) == "L"   # margin 6
    assert grade_row("spread", "away", 7.0, 26, 20) == "W"    # away +7, loses by 6
    assert grade_row("spread", "away", 7.0, 28, 20) == "L"

    # Moneyline ignores the line entirely.
    assert grade_row("moneyline", "home", None, 28, 20) == "W"
    assert grade_row("moneyline", "away", None, 28, 20) == "L"

    # No final score -> not gradeable, never a loss.
    assert grade_row("total", "over", 54.0, None, 28) is None
    assert grade_row("spread", "home", -7.0, float("nan"), 20) is None

    # Wilson: a 50/100 split straddles 0.5 and narrows as n grows.
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi and abs((lo + hi) / 2 - 0.5) < 1e-9
    lo2, hi2 = wilson(500, 1000)
    assert (hi2 - lo2) < (hi - lo)

    # MDE sits above the break-even it is measured from and shrinks with n.
    assert mde(100, FLAT_110) > mde(1000, FLAT_110) > FLAT_110

    # Clustering must not be free. Where a game's picks agree with each other -- 20 games
    # sweeping, 10 games losing out -- three rows carry one game's worth of information,
    # so the game-clustered interval has to be wider than the row-wise one. (Identical
    # games would be degenerate: every resample returns the same mean, variance zero.)
    dec = pd.DataFrame({
        "game_id": np.repeat(np.arange(30), 3),
        "won": np.repeat([1.0] * 20 + [0.0] * 10, 3),
    })
    rng = np.random.default_rng(SEED)
    clo, chi = cluster_ci(dec, rng)
    wlo, whi = wilson(int(dec["won"].sum()), len(dec))
    assert abs((clo + chi) / 2 - 2 / 3) < 0.05, (clo, chi)
    assert (chi - clo) > (whi - wlo), (clo, chi, wlo, whi)

    print("self-check ok")


if __name__ == "__main__":
    raise SystemExit(main())
