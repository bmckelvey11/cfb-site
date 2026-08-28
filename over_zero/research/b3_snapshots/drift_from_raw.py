"""B3: open-to-close totals drift, computed directly from raw historical
lines files (data/raw/lines_{season}.json) instead of a live
capture_odds.py snapshot loop.

Owner-approved deviation from the original plan; see research/BLOCKERS.md,
"2026-07-31 -- B3.1 (odds snapshot capture) -- plan deviation, owner-approved".

Two populations, per game-book pair with both overUnderOpen and overUnder
present:
  ALL games        -- every qualifying book-game pair.
  QUALIFYING games  -- restricted to games whose closing consensus line
                       (via pick_line) has censoring bias > 1.0 (i.e. the
                       spread/total combination pushes one team's implied
                       score toward the zero floor).

drift = overUnder - overUnderOpen (positive = total rose toward close).
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import _team_censor_bias, implied_team_points, pick_line

RAW = REPO / "data" / "raw"
SEASONS = range(2013, 2026)
SIGMA_DOG, SIGMA_FAV = 11.03, 11.78


def season_drifts(season):
    """Return (all_drifts, qual_drifts, n_skipped_null) for one season."""
    path = RAW / f"lines_{season}.json"
    if not path.exists():
        return None
    games = json.loads(path.read_text(encoding="utf-8"))

    all_drifts = []
    qual_drifts = []
    n_skipped_null = 0

    for g in games:
        lines = g.get("lines") or []

        game_drifts = []
        for book in lines:
            open_ou = book.get("overUnderOpen")
            close_ou = book.get("overUnder")
            if open_ou is None or close_ou is None:
                n_skipped_null += 1
                continue
            game_drifts.append(float(close_ou) - float(open_ou))

        all_drifts.extend(game_drifts)

        if not game_drifts:
            continue

        picked = pick_line(g)
        if picked is None:
            continue
        spread, total = picked
        dog_est, fav_est = implied_team_points(abs(spread), total)
        bias = (_team_censor_bias(dog_est, SIGMA_DOG)
                + _team_censor_bias(fav_est, SIGMA_FAV))
        if float(bias) > 1.0:
            qual_drifts.extend(game_drifts)

    return (np.array(all_drifts), np.array(qual_drifts), n_skipped_null)


def mean_ci(arr):
    """(n, mean, se, lo, hi) -- 95% CI as mean +/- 1.96*SE. NaNs if n<2."""
    n = arr.size
    if n < 2:
        return n, float("nan"), float("nan"), float("nan"), float("nan")
    mean = arr.mean()
    se = arr.std(ddof=1) / np.sqrt(n)
    return n, mean, se, mean - 1.96 * se, mean + 1.96 * se


def fmt(label, arr):
    n, mean, se, lo, hi = mean_ci(arr)
    if n < 2:
        return f"  {label}: n={n} (insufficient data)"
    return (f"  {label}: n={n:,}  mean={mean:+.4f}  SE={se:.4f}  "
            f"95% CI [{lo:+.4f}, {hi:+.4f}]")


def main():
    by_season = {}
    for season in SEASONS:
        result = season_drifts(season)
        if result is None:
            print(f"season {season}: (no raw file)")
            continue
        all_d, qual_d, n_skipped = result
        by_season[season] = (all_d, qual_d, n_skipped)
        print(f"season {season}:  book-pairs kept(ALL)={all_d.size:,}  "
              f"kept(QUALIFYING)={qual_d.size:,}  skipped(null open/close)={n_skipped:,}")

    print()
    print("=== PER-SEASON BREAKDOWN ===")
    for season in sorted(by_season):
        all_d, qual_d, _ = by_season[season]
        print(f"season {season}:")
        print(fmt("ALL       ", all_d))
        print(fmt("QUALIFYING", qual_d))

    all_pooled = np.concatenate([v[0] for v in by_season.values()]) if by_season else np.array([])
    qual_pooled = np.concatenate([v[1] for v in by_season.values()]) if by_season else np.array([])
    total_skipped = sum(v[2] for v in by_season.values())

    print()
    print("=== POOLED (all seasons) ===")
    print(fmt("ALL       ", all_pooled))
    print(fmt("QUALIFYING", qual_pooled))
    print(f"  total book-pairs skipped (null overUnderOpen or overUnder): {total_skipped:,}")


if __name__ == "__main__":
    main()
