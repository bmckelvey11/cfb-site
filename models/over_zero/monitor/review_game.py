"""Full review of one or more games from their two lines.

  python monitor/review_game.py SPREAD TOTAL [SPREAD TOTAL ...]
  python monitor/review_game.py 28 40.5  21 41

For each (spread, total) pair prints everything MODEL_GUIDE.md says to check
before betting: implied points, the bias number and verdict, which historical
group the game falls in and that group's record, price rules, sizing, how far
the line would have to move to flip the verdict, and the filter checklist.
Spread sign is ignored (only the favorite's margin matters); TOTAL is the
full-game combined over/under, not a team total.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import load_from_raw  # noqa: E402
from run_walkforward import fit_train  # noqa: E402
from models_v2 import censoring_bias, implied_team_points  # noqa: E402

THRESHOLD = 1.75
PLAN_WIN = 0.582          # CI lower bound -- the planning number per MODEL_GUIDE
MAX_PRICE = -125          # never bet worse than this
PREFERRED_PRICE = -120

# Walk-forward disjoint-bin record (monitor/bias_bins.py, 2016-2025).
BINS = [
    (0.00, 0.50, 8484, 48.10, "well below breakeven"),
    (0.50, 1.00, 1090, 52.11, "at/below breakeven"),
    (1.00, 1.75, 447, 52.80, "no demonstrated edge -- excluded by rule"),
    (1.75, 2.50, 157, 64.97, "clears breakeven with margin"),
    (2.50, np.inf, 77, 63.64, "clears breakeven with margin"),
]


def breakeven(price):
    return abs(price) / (abs(price) + 100.0)


def bias_of(spread, total, s1, s2):
    d, f = implied_team_points(np.array([spread]), np.array([total]))
    _, b = censoring_bias(d, f, s1, s2)
    return float(d[0]), float(f[0]), float(b[0])


def flip_total(spread, s1, s2, lo=10.0, hi=90.0):
    """Total at which bias crosses THRESHOLD for this spread (bias falls as
    the total rises, since a higher total lifts the dog off the floor)."""
    for _ in range(60):
        mid = (lo + hi) / 2
        _, _, b = bias_of(spread, mid, s1, s2)
        if b > THRESHOLD:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def review(spread, total, s1, s2, probit):
    spread = abs(spread)
    dog, fav, b = bias_of(spread, total, s1, s2)
    p = float(probit.win_prob(np.array([b]))[0])
    bet = b > THRESHOLD

    print(f"\n{'=' * 62}")
    print(f"GAME: favorite -{spread:g}, total {total:g}")
    print(f"{'=' * 62}")
    print(f"  Implied scores      : underdog {dog:.2f}, favorite {fav:.2f}")
    print(f"  Bias number         : {b:.2f}  (rule: bet over when > {THRESHOLD})")
    print(f"  VERDICT             : {'BET the over' if bet else 'PASS'}"
          + ("" if bet or b <= 1.0 else "  (1.00-1.75: no demonstrated edge)"))

    lo_e, hi_e, n, wr, note = next(t for t in BINS if t[0] < b <= t[1] or
                                   (t[1] is np.inf and b > t[0]))
    hi_lbl = "inf" if hi_e is np.inf else f"{hi_e:g}"
    print(f"  Historical group    : bias {lo_e:g}-{hi_lbl}: won {wr:.1f}% of "
          f"{n} honest-test bets -- {note}")
    print(f"  Model P(over)       : {p * 100:.1f}%  (calibration gap: trust "
          f"the verdict, not this number)")

    if bet:
        margin = b - THRESHOLD
        ft = flip_total(spread, s1, s2)
        print(f"  Margin to threshold : +{margin:.2f} bias points"
              + ("  ** fence-sitter: recompute at close **" if margin < 0.15 else ""))
        print(f"  Verdict flips if    : total rises above ~{ft:.1f} "
              f"(currently {total:g}); recompute after any line move")
        print(f"  Price rules         : take {PREFERRED_PRICE} or better; "
              f"{PREFERRED_PRICE - 1} to {MAX_PRICE} only if no better book; "
              f"never worse than {MAX_PRICE}")
        print(f"                        breakeven at -110 = 52.38%, at -120 = "
              f"54.55%; planning win rate = {PLAN_WIN * 100:.1f}%")
        print(f"  Sizing              : flat 1% of bankroll, or quarter-Kelly "
              f"off {PLAN_WIN * 100:.0f}% = ~3% (never off the 64.5% headline)")
        print(f"  Shop the number     : each 0.5 pt of total = ~1.2 pp of win "
              f"rate = ~5 cents of juice; take the lowest total on the board")
        print("  Checklist           : full-game combined total only | not a "
              "pick'em | major book or consensus line | log the bet "
              "(date, teams, lines, price, bias, closing line, result)")
    else:
        ft = flip_total(spread, s1, s2)
        if ft > 10.5:
            print(f"  Would qualify if    : total dropped below ~{ft:.1f} "
                  f"(currently {total:g}) at this spread")
    print()


def _self_check(s1, s2, probit):
    # Known worked examples from MODEL_GUIDE section 4.
    _, _, b1 = bias_of(28, 40.5, s1, s2)
    _, _, b2 = bias_of(21, 41, s1, s2)
    assert b1 > THRESHOLD, f"28/40.5 should qualify (bias {b1:.2f})"
    assert 1.0 < b2 < THRESHOLD, f"21/41 should be mid-band (bias {b2:.2f})"
    # Flip total must be consistent with the bias at that exact total.
    ft = flip_total(28, s1, s2)
    _, _, bf = bias_of(28, ft, s1, s2)
    assert abs(bf - THRESHOLD) < 0.01, f"flip-total inconsistent ({bf:.3f})"
    print("self-check OK")


def main():
    args = [a.lstrip("-") for a in sys.argv[1:]]
    if args and args[0] == "self-check":
        vals = []
    else:
        try:
            vals = [float(a) for a in args]
        except ValueError:
            sys.exit(__doc__)
        if not vals or len(vals) % 2:
            sys.exit(__doc__)

    data = load_from_raw(list(range(2013, 2026)))
    years = sorted(data)
    se, te, fp, dp = (np.concatenate([data[y][k] for y in years])
                      for k in range(4))
    s1, s2, probit = fit_train(se, te, fp, dp)
    print(f"Model trained on {se.size:,} games {years[0]}-{years[-1]} "
          f"(sigma dog={s1:.2f} fav={s2:.2f})")

    if not vals:
        _self_check(s1, s2, probit)
        return
    for i in range(0, len(vals), 2):
        review(vals[i], vals[i + 1], s1, s2, probit)


if __name__ == "__main__":
    main()
