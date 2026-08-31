"""Fit the Arscott (2022) pipeline on historical seasons, then apply it to a
future week's lines (no scores yet) to produce over/under picks.

Run:  python v1/predict_week.py --fit-seasons 2015 2016 ... 2025 \
          --raw data/raw/lines_2026_week1.json --book DraftKings
"""

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from censoring_bias import censoring_bias, fit_pipeline, implied_team_points
from run_on_project_data import DEFAULT_CSV, load

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT_CSV = REPO / "data" / "processed" / "predictions.csv"
DEFAULT_SNAPSHOT_DIR = REPO / "data" / "predictions"
CFBD_LINES_URL = "https://api.collegefootballdata.com/lines"
CSV_COLUMNS = [
    "run_at", "source", "book", "game_id", "game_date", "week",
    "home_team", "away_team", "spread", "total", "dog_implied",
    "bias", "p_over", "threshold", "pick",
]


def load_future_lines(path, book):
    """Extract home-relative spread/total for one book from a lines_{...}.json
    file with unplayed games (no scores). Skips games missing that book,
    missing spread/total, or pick'em (spread == 0)."""
    games = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for g in games:
        line = next((l for l in (g.get("lines") or [])
                     if l.get("provider") == book), None)
        if line is None:
            continue
        spread, total = line.get("spread"), line.get("overUnder")
        if spread is None or total is None or float(spread) == 0:
            continue
        rows.append({
            "game_id": g.get("id"),
            "game_date": (g.get("startDate") or "")[:10],
            "week": g.get("week"),
            "home_team": g.get("homeTeam"),
            "away_team": g.get("awayTeam"),
            "spread": float(spread),   # home-relative, neg = home favored
            "total": float(total),
        })
    return rows


def _cfbd_token():
    """CFBD API token from env vars or the hub repo's env.env (gitignored).

    The hub root is the only env.env -- per README, do not add a second one
    under over_zero/."""
    import os
    for key in ("CFBD_API_KEY", "CFBD-API", "BEARER_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    env = REPO.parent / "env.env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() in ("CFBD_API_KEY", "CFBD-API", "BEARER_TOKEN"):
                    return v.strip()
    raise SystemExit("CFBD token not found (env var CFBD_API_KEY / CFBD-API "
                     "or a line in env.env)")


def fetch_lines(season, week, out_path):
    """Pull current lines (played or not) from the CFBD REST API for one
    season, keep the requested week, write the snapshot to out_path."""
    import urllib.request
    req = urllib.request.Request(
        f"{CFBD_LINES_URL}?year={season}&seasonType=regular",
        headers={"Authorization": f"Bearer {_cfbd_token()}"})
    data = json.load(urllib.request.urlopen(req, timeout=60))
    keep = [g for g in data if g.get("week") == week]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(keep, indent=1), encoding="utf-8")
    print(f"Fetched {len(keep)} week-{week} games ({len(data)} total "
          f"{season} records) -> {out_path.name}")
    return out_path


def append_csv(path, rows, run_at, source, book, dog_est, bias_totals,
               win_probs, threshold):
    """Append one row per scored game. Reruns accumulate, so the file doubles
    as a line-move history: same game_id, later run_at, new numbers."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if new_file:
            w.writeheader()
        for r, d, b, p in zip(rows, dog_est, bias_totals, win_probs):
            w.writerow({
                "run_at": run_at, "source": source, "book": book,
                "game_id": r["game_id"], "game_date": r["game_date"],
                "week": r["week"], "home_team": r["home_team"],
                "away_team": r["away_team"], "spread": r["spread"],
                "total": r["total"], "dog_implied": round(float(d), 2),
                "bias": round(float(b), 3), "p_over": round(float(p), 4),
                "threshold": threshold,
                "pick": "OVER" if b > threshold else "",
            })


def snapshot_name(run_at, raw_stem, book):
    """Filename for one run's immutable snapshot. run_at is already UTC and
    second-resolution, so two runs never collide."""
    stamp = re.sub(r"[:\-]", "", run_at).replace("Z", "")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{raw_stem}_{book}")
    return f"{stamp}_{safe}.csv"


def main():
    ap = argparse.ArgumentParser(
        description="Fit on historical seasons, predict a future week's overs")
    ap.add_argument("--fit-csv", default=str(DEFAULT_CSV))
    ap.add_argument("--fit-seasons", type=int, nargs="+", required=True,
                     help="historical seasons to fit the pipeline on")
    ap.add_argument("--raw", default=None,
                     help="path to lines_{...}.json for the target week; "
                          "required unless --fetch")
    ap.add_argument("--fetch", action="store_true",
                     help="pull current lines from the CFBD API first "
                          "(token from env.env), write them to --raw "
                          "(default data/raw/lines_{season}_week{week}.json), "
                          "then score")
    ap.add_argument("--season", type=int, default=2026,
                     help="season for --fetch")
    ap.add_argument("--week", type=int, default=1, help="week for --fetch")
    ap.add_argument("--book", default="DraftKings",
                     help="sportsbook to read spread/total from (no consensus "
                          "book exists this far from kickoff)")
    ap.add_argument("--threshold", type=float, default=1.75,
                     help="bet rule: over when expected censoring bias > this "
                          "(per MODEL_GUIDE; 1.00-1.75 shows no demonstrated edge)")
    ap.add_argument("--csv", default=str(DEFAULT_OUT_CSV),
                     help="append every scored game to this CSV "
                          "(--csv '' to disable)")
    ap.add_argument("--snapshot-dir", default=str(DEFAULT_SNAPSHOT_DIR),
                     help="also write an immutable per-run snapshot CSV here "
                          "(--snapshot-dir '' to disable)")
    args = ap.parse_args()

    if args.fetch:
        raw = args.raw or str(REPO / "data" / "raw" /
                              f"lines_{args.season}_week{args.week}.json")
        args.raw = str(fetch_lines(args.season, args.week, raw))
    elif not args.raw:
        ap.error("--raw is required unless --fetch is given")

    spread_est, totals_est, fav_points, dog_points = load(
        Path(args.fit_csv), args.fit_seasons
    )
    n = spread_est.size
    print(f"Fit on {n:,} games from seasons {args.fit_seasons}")
    if n < 250:
        print("Warning: small fit sample; sigmas/probit may be unstable.")
    fit = fit_pipeline(spread_est, totals_est, fav_points, dog_points)

    rows = load_future_lines(args.raw, args.book)
    print(f"Loaded {len(rows)} games with {args.book} lines from {args.raw}\n")
    print("NOTE: lines captured well before kickoff (opening lines), not "
          "closing lines the model was fit against historically -- treat "
          "as illustrative, not a validated edge.\n")

    spread_arr = np.array([abs(r["spread"]) for r in rows])
    total_arr = np.array([r["total"] for r in rows])
    dog_est, fav_est = implied_team_points(spread_arr, total_arr)
    _, bias_totals = censoring_bias(
        dog_est, fav_est, fit.tobit_dog.sigma, fit.tobit_fav.sigma
    )
    win_probs = fit.probit.win_prob(bias_totals)

    print(f"{'home':<20} {'away':<20} {'total':>6} {'bias':>6} {'P(over)':>8} pick")
    picks = 0
    for r, bias, p in zip(rows, bias_totals, win_probs):
        pick = "OVER" if bias > args.threshold else ""
        if pick:
            picks += 1
        print(f"{r['home_team']:<20} {r['away_team']:<20} {r['total']:>6.1f} "
              f"{bias:>6.2f} {p*100:>7.2f}% {pick}")
    print(f"\n{picks}/{len(rows)} games clear bias > {args.threshold}")

    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.csv:
        append_csv(args.csv, rows, run_at, Path(args.raw).name, args.book,
                   dog_est, bias_totals, win_probs, args.threshold)
        print(f"Appended {len(rows)} rows to {args.csv}")
    if args.snapshot_dir:
        snap = Path(args.snapshot_dir) / snapshot_name(
            run_at, Path(args.raw).stem, args.book)
        append_csv(snap, rows, run_at, Path(args.raw).name, args.book,
                   dog_est, bias_totals, win_probs, args.threshold)
        print(f"Wrote snapshot {snap}")


if __name__ == "__main__":
    main()
