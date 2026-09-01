"""Correlate win-probability onset timing against favorite scoring shortfall.

For every qualifying bet (bias > 1.75), finds the first play where the
favorite's win probability crosses THRESHOLD, expresses that as a fraction of
the game's total plays, and checks it against how far the favorite's actual
score landed from the spread/total-implied number.

Run from models/over_zero/ after pull_win_probability.py:
    python research/2026-08-31_win_prob_onset/analyze_onset.py [--season 2025]
"""
import json, csv, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
BETS_PATH = HERE.parents[1] / "docs" / "backtest_bets.csv"
THRESHOLD = 0.95


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    return cov / (sx * sy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default=None)
    args = ap.parse_args()

    suffix = f"_{args.season}" if args.season else "_qualifying"
    wp_path = HERE / f"win_probability{suffix}.json"
    with open(wp_path) as f:
        wp_data = json.load(f)

    bets = {}
    with open(BETS_PATH) as f:
        for row in csv.DictReader(f):
            if row["passes_filter"] != "1":
                continue
            if args.season and row["season"] != args.season:
                continue
            bets[row["game_id"]] = row

    results = []
    for gid, plays in wp_data.items():
        if not plays or gid not in bets:
            continue
        bet = bets[gid]
        fav_team = bet["fav_team"]
        home, away = plays[0]["home"], plays[0]["away"]
        fav_is_home = fav_team == home
        if not fav_is_home and fav_team != away:
            continue  # team-name mismatch, skip

        n = len(plays)
        onset_idx = None
        for i, p in enumerate(plays):
            hwp = p.get("homeWinProbability")
            if hwp is None:
                continue
            fav_wp = hwp if fav_is_home else (1 - hwp)
            if fav_wp >= THRESHOLD:
                onset_idx = i
                break

        fav_impl = (float(bet["total"]) + float(bet["spread"])) / 2
        fav_gap = float(bet["fav_pts"]) - fav_impl
        onset_frac = (onset_idx / (n - 1)) if (onset_idx is not None and n > 1) else None

        results.append({
            "game_id": gid, "season": bet["season"], "week": bet["week"],
            "fav": fav_team, "dog": bet["dog_team"],
            "onset_frac": onset_frac, "fav_gap": fav_gap, "over": bet["over"],
        })

    crossed = [r for r in results if r["onset_frac"] is not None]
    print(f"matched games: {len(results)}  crossed {THRESHOLD} WP: {len(crossed)}")

    r_all = pearson([x["onset_frac"] for x in crossed], [x["fav_gap"] for x in crossed])
    print(f"Pearson r(onset_frac, fav_gap) = {r_all:.4f}  n={len(crossed)}")

    buckets = [(0, 0.20), (0.20, 0.35), (0.35, 0.50), (0.50, 1.0)]
    print(f"\n{'onset bucket':<14}{'n':>4}{'avg_fav_gap':>13}{'win_rate':>10}")
    for lo, hi in buckets:
        g = [r for r in crossed if lo <= r["onset_frac"] < hi]
        if g:
            n = len(g)
            avg = sum(x["fav_gap"] for x in g) / n
            wins = sum(1 for x in g if x["over"] == "1")
            print(f"{lo:.0%}-{hi:.0%}".ljust(14) + f"{n:>4}{avg:>13.2f}{100*wins/n:>9.1f}%")


if __name__ == "__main__":
    main()
