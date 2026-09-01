"""Pull per-play CFBD win probability for every qualifying over_zero bet.

Scoped pull, not a full-season scrape: reads game_id + fav_team/dog_team from
docs/backtest_bets.csv (passes_filter == 1) and fetches MetricsApi.get_win_probability
per game_id directly, bypassing the season-wide PER_GAME scraper.

Run from models/over_zero/:
    python research/2026-08-31_win_prob_onset/pull_win_probability.py [--season 2025]

Writes win_probability_qualifying.json (or _<season>.json) next to this script.
"""
import sys, json, time, csv, os, argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # models/over_zero/research/<date>/ -> cfb/
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)
from cfb_system_maker.cfbd_client import _load_cfbd_module, _to_dict, find_cfbd_token  # noqa: E402

BETS_PATH = REPO_ROOT / "models" / "over_zero" / "docs" / "backtest_bets.csv"
HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default=None, help="restrict to one season, e.g. 2025")
    args = ap.parse_args()

    game_ids = []
    with open(BETS_PATH) as f:
        for row in csv.DictReader(f):
            if row["passes_filter"] != "1":
                continue
            if args.season and row["season"] != args.season:
                continue
            game_ids.append(int(row["game_id"]))

    print(f"pulling win probability for {len(game_ids)} qualifying games"
          + (f" (season {args.season})" if args.season else " (2016-2025)"))

    cfbd = _load_cfbd_module()
    token = find_cfbd_token(str(REPO_ROOT / "env.env"))
    configuration = cfbd.Configuration(access_token=token)

    results = {}
    with cfbd.ApiClient(configuration) as api_client:
        metrics_api = cfbd.MetricsApi(api_client)
        for i, gid in enumerate(game_ids):
            try:
                rows = metrics_api.get_win_probability(game_id=gid)
                results[gid] = [_to_dict(r) for r in rows]
            except Exception as e:
                print(f"  {gid}: FAILED {e}")
            if (i + 1) % 20 == 0 or (i + 1) == len(game_ids):
                print(f"  {i+1}/{len(game_ids)} done")
            time.sleep(0.25)

    suffix = f"_{args.season}" if args.season else "_qualifying"
    out_path = HERE / f"win_probability{suffix}.json"
    with open(out_path, "w") as f:
        json.dump(results, f)

    zero_play = sum(1 for rows in results.values() if len(rows) == 0)
    print(f"\ndone: {len(results)} games returned, {zero_play} had 0 plays (no CFBD WP coverage)")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
