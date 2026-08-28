"""Score upcoming games: expected censoring bias + P(over) from the two lines.

  python monitor/score_game.py SPREAD TOTAL [SPREAD TOTAL ...]
  python monitor/score_game.py 21 41  30 47  3.5 62.5

SPREAD is the game point spread (sign ignored -- only the favorite's margin
matters); TOTAL is the game total, i.e. the standard combined over/under on
both teams' points (not a team total). Trains the full pipeline (Tobit
sigmas + probit) on every completed season in data/raw, then scores each
(game spread, game total) pair. Betting rules per
docs/MODEL_GUIDE.md: bet the over at bias > 1.75, at -120 juice or better,
using lines as close to closing as possible. Games at bias 1.00-1.75 print
"pass (no edge)": walk-forward they win 52.80% (CI [48.2, 57.4]), which is
indistinguishable from the 52.38% breakeven -- not shown to lose, just not
shown to win. See monitor/bias_bins.py for the bin-by-bin evidence.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import load_from_raw  # noqa: E402
from run_walkforward import fit_train  # noqa: E402
from models_v2 import censoring_bias, implied_team_points  # noqa: E402


def _argv():
    """Let users paste negative spreads: '-21.5' -> '21.5' (sign is ignored)."""
    out = []
    for a in sys.argv[1:]:
        if a.startswith("-") and a.lstrip("-").replace(".", "", 1).isdigit():
            out.append(a.lstrip("-"))
        else:
            out.append(a)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lines", type=float, nargs="+", metavar="SPREAD_TOTAL",
                    help="pairs: SPREAD TOTAL [SPREAD TOTAL ...]")
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)),
                    help="training seasons (default: all available)")
    args = ap.parse_args(_argv())
    if len(args.lines) % 2:
        ap.error("supply pairs: SPREAD TOTAL [SPREAD TOTAL ...]")

    data = load_from_raw(args.season)
    if not data:
        sys.exit("No training data found (need data/raw).")
    years = sorted(data)
    se, te, fp, dp = (np.concatenate([data[y][k] for y in years])
                      for k in range(4))
    s1, s2, probit = fit_train(se, te, fp, dp)
    print(f"Trained on {se.size:,} games {years[0]}-{years[-1]}: "
          f"sigma dog={s1:.2f} fav={s2:.2f}, "
          f"probit const={probit.const:+.3f} slope={probit.slope:+.3f}\n")

    print(f"  {'spread':>7} {'total':>6} {'dogEst':>7} {'bias':>6} "
          f"{'P(over)':>8}  verdict")
    for i in range(0, len(args.lines), 2):
        sp, total = abs(args.lines[i]), args.lines[i + 1]
        dog, fav = implied_team_points(sp, total)
        _, bias = censoring_bias(dog, fav, s1, s2)
        b = float(bias)
        p = float(probit.win_prob(b))
        verdict = ("BET over" if b > 1.75 else
                   "pass (no edge)" if b > 1.0 else "pass")
        print(f"  {sp:>7.1f} {total:>6.1f} {float(dog):>7.2f} {b:>6.2f} "
              f"{p*100:>7.2f}%  {verdict}")
    print("\nRules: bet only bias > 1.75; -120 or better on the over; "
          "closing-ish lines;\nfull-game COMBINED totals only (the standard "
          "game over/under -- not team totals).\nSee docs/MODEL_GUIDE.md.")


if __name__ == "__main__":
    main()
