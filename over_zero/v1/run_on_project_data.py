"""Run the Arscott (2022) model recreation on this repo's real CFBD data
(data/processed/games.csv) instead of synthetic data.

Maps the project's home-spread convention to the paper's underdog perspective:
the favorite is whichever team has the negative spread; spreadEst = |spread|
(>= 0), totalsEst = total, with favPoints/dogPoints assigned accordingly.

Run:  python v1/run_on_project_data.py [--csv path/to/games.csv]
"""

import csv
import json
from pathlib import Path

import numpy as np

from censoring_bias import (
    censoring_bias,
    fit_pipeline,
    implied_team_points,
    kfold_cross_validate,
    ols_line_test,
    strategy_returns,
)

REPO = Path(__file__).resolve().parents[1]  # over-zero/
DEFAULT_CSV = REPO / "data" / "processed" / "games.csv"
RAW_DIR = REPO / "data" / "raw"


def load_from_raw(seasons, raw_dir=RAW_DIR):
    """Load directly from data/raw/lines_{season}.json, which carries both the
    final scores and every book's lines.

    Per game, pick a line with BOTH a spread and a total (prefer 'consensus',
    else the first such book). This recovers seasons that the consensus-only
    processed build dropped because the first usable book was spread-only.
    """
    spread_est, totals_est, fav_pts, dog_pts = [], [], [], []
    for season in seasons:
        path = Path(raw_dir) / f"lines_{season}.json"
        if not path.exists():
            print(f"  (no raw file for {season}: {path.name})")
            continue
        for g in json.loads(path.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            if hp is None or ap is None:
                continue
            both = [l for l in (g.get("lines") or [])
                    if l.get("spread") is not None and l.get("overUnder") is not None]
            if not both:
                continue
            line = next((l for l in both
                         if str(l.get("provider", "")).lower() == "consensus"), both[0])
            spread = float(line["spread"])      # home-relative (neg = home favored)
            total = float(line["overUnder"])
            if spread == 0:
                continue
            if spread < 0:                       # home favored
                fav, dog = float(hp), float(ap)
            else:
                fav, dog = float(ap), float(hp)
            spread_est.append(abs(spread))
            totals_est.append(total)
            fav_pts.append(fav)
            dog_pts.append(dog)
    return (np.array(spread_est), np.array(totals_est),
            np.array(fav_pts), np.array(dog_pts))


def load(csv_path, seasons=None):
    """Return spread_est, totals_est, fav_points, dog_points from games.csv.

    Drops rows with missing spread/total/points and pick'em games (spread == 0).
    `seasons` (set of str/int) optionally restricts to those seasons.
    """
    seasons = {str(s) for s in seasons} if seasons else None
    spread_est, totals_est, fav_pts, dog_pts = [], [], [], []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if seasons is not None and row.get("season") not in seasons:
                continue
            try:
                spread = float(row["spread"])      # home spread
                total = float(row["total"])
                hp = float(row["home_points"])
                ap = float(row["away_points"])
            except (ValueError, KeyError, TypeError):
                continue
            if spread == 0:                        # no favorite -> skip (per paper)
                continue
            # Favorite = negative-spread side (underdog perspective: spread_est > 0).
            if spread < 0:                         # home favored
                fav, dog = hp, ap
            else:                                  # away favored
                fav, dog = ap, hp
            spread_est.append(abs(spread))
            totals_est.append(total)
            fav_pts.append(fav)
            dog_pts.append(dog)
    return (np.array(spread_est), np.array(totals_est),
            np.array(fav_pts), np.array(dog_pts))


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run Arscott (2022) models on games.csv")
    ap.add_argument("--season", type=int, nargs="*", help="restrict to season(s)")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to games.csv")
    ap.add_argument("--raw", action="store_true",
                    help="load from data/raw/lines_{season}.json (needs --season); "
                         "picks a book with both spread and total, recovers more games")
    args = ap.parse_args()

    if args.raw:
        if not args.season:
            ap.error("--raw requires --season")
        spread_est, totals_est, fav_points, dog_points = load_from_raw(args.season)
        src = f"raw lines_{args.season}.json"
    else:
        spread_est, totals_est, fav_points, dog_points = load(Path(args.csv), args.season)
        src = f"{args.csv}" + (f" season={args.season}" if args.season else "")
    n = spread_est.size
    print(f"Loaded {n:,} usable games from {src}")
    if n < 50:
        print("Too few games for stable estimates; results are illustrative only.")

    true_spread = fav_points - dog_points
    true_totals = fav_points + dog_points

    print("\n[2] OLS line-bias tests (null: alpha=0, beta=1)")
    sp = ols_line_test(true_spread, spread_est)
    to = ols_line_test(true_totals, totals_est)
    print(f"  spread: a={sp.alpha:+.3f} b={sp.beta:.3f} sd={sp.resid_std:.2f} "
          f"F={sp.f_stat:.2f}(p={sp.f_pvalue:.3f})")
    print(f"  totals: a={to.alpha:+.3f} b={to.beta:.3f} sd={to.resid_std:.2f} "
          f"F={to.f_stat:.2f}(p={to.f_pvalue:.3f})")

    fit = fit_pipeline(spread_est, totals_est, fav_points, dog_points)
    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    ols_dog = ols_line_test(dog_points, dog_est)
    print("\n[3,4] Underdog points OLS vs Tobit")
    print(f"  OLS  : a={ols_dog.alpha:+.3f} b={ols_dog.beta:.3f} sd={ols_dog.resid_std:.2f}")
    print(f"  Tobit: a={fit.tobit_dog.alpha:+.3f} b={fit.tobit_dog.beta:.3f} "
          f"sigma={fit.tobit_dog.sigma:.2f} ({fit.tobit_dog.n_censored} censored)")
    print(f"  Tobit favorite sigma = {fit.tobit_fav.sigma:.2f}")

    pf = fit.probit
    print("\n[6] Probit P(over) = Phi(const + slope*biasTotals)")
    print(f"  const={pf.const:+.3f} slope={pf.slope:+.3f} "
          f"bias@52.38% hurdle={pf.bias_for_hurdle(0.5238):.2f}")

    _, bias_totals = censoring_bias(
        dog_est, fav_est, fit.tobit_dog.sigma, fit.tobit_fav.sigma
    )
    nu = true_totals - totals_est
    keep = nu != 0
    over_wins = (nu > 0).astype(float)
    win_probs = pf.win_prob(bias_totals)

    print("\n[9] In-sample 'bet the over' by censoring-bias threshold")
    print(f"  {'thr':>6} {'N':>6} {'win%':>7} {'unit%':>7} {'kelly%':>7} "
          f"{'.25Kbankroll':>12}")
    for thr in (1.00, 1.75):
        sel = keep & (bias_totals > thr)
        if sel.sum() == 0:
            print(f"  >{thr:<5.2f}  (no games)")
            continue
        res = strategy_returns(over_wins[sel], win_probs[sel], kelly_fraction=0.25)
        print(f"  >{thr:<5.2f} {res.n_bets:>6} {res.win_rate*100:>6.2f}% "
              f"{res.unit_return*100:>6.2f}% {res.kelly_return*100:>6.2f}% "
              f"{res.kelly_bankroll_roi*100:>+11.1f}%")

    if n >= 250:
        print("\n[10] 5-fold out-of-sample (bet over where Pwin>52.38%)")
        for i, (cvfit, res) in enumerate(
            kfold_cross_validate(spread_est, totals_est, fav_points, dog_points), 1
        ):
            if res is None:
                print(f"  fold {i}: no bets cleared hurdle")
                continue
            print(f"  fold {i}: N={res.n_bets} win={res.win_rate*100:.2f}% "
                  f"unit={res.unit_return*100:+.2f}% kelly={res.kelly_return*100:+.2f}%")


if __name__ == "__main__":
    main()
