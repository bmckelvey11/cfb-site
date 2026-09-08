"""Pull the PFF data a game model needs, and flatten it to one row per team-game.

    python scripts/pull_pff_modeling.py --seasons 2025                 # one season
    python scripts/pull_pff_modeling.py --seasons 2014-2026            # backfill
    python scripts/pull_pff_modeling.py --seasons 2026 --player-facets # + weekly leaderboards
    python scripts/pull_pff_modeling.py --seasons 2025 --dry-run

Four cheap reads give a complete team-game history without touching the export
budget:

    ref-leagues      seasons and week ids (postseason weeks are 17-20, not 15-18)
    team-directory   every franchise with its group ids; group 11 is FBS
    ref-games        one call per (season, week): game_id, home/away, score, kickoff
    team-summary     one call per (season, franchise): PFF's 14 team grades per game

Everything lands as JSON under data/raw/pff/team/ (outside the warehouse glob, which
is not recursive), then `team_game.csv` is rebuilt under data/processed/pff/: one row
per (game_id, franchise_id) with that team's grades, the opponent's grades from the
same game, home/away, points, and kickoff. A game's grades are a *result* of that
game -- a pre-game feature has to roll them from earlier weeks. That is the model's
job; this script only lands the facts.

`--player-facets` also runs every exportable leaderboard (`facet-*`, `signature-*`)
per week through pull_pff_facet.py, minus the three that are redundant or broken.
That is 25+4 exports a week at 20/minute, so about 2 minutes per week.

Reads are metered at 100/minute on a fixed wall-clock window; a 429 sleeps to the
next minute and retries once. Auth is the `ci` API-key profile (docs/pff-cli.md).
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import DATA_ROOT, current_season  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pull_pff_facet import (  # noqa: E402
    EXPORT_PACING_SECONDS, api_key, error_code, exportable_ops, load_spec, pull_one,
    restish_bin,
)

READ_PACING_SECONDS = 0.7  # 100 reads/minute, with headroom
FBS_GROUP_ID = "11"
# passing_detail is the union of the other four passing facets and hangs;
# the other two answer 500 for every NCAA pull. See docs/pff-warehouse-schema.md.
SKIP_FACETS = {"facet-passing-detail", "facet-receiving-coverage", "facet-defense-coverage-matchup"}

GRADE_COLS = (
    "grades_overall", "grades_offense", "grades_pass", "grades_run", "grades_pass_block",
    "grades_run_block", "grades_pass_route", "grades_defense", "grades_run_defense",
    "grades_pass_rush_defense", "grades_coverage_defense", "grades_tackle", "grades_misc_st",
)


def read_json(binary: str, args: list[str], dest: Path, env: dict, timeout: float) -> str | None:
    """Run a /v1 read to dest as JSON. Returns an error string, or None."""
    cmd = [binary, "pff", *args, "-p", "ci", "-o", "json", "--rsh-print", "b"]
    for attempt in (1, 2):
        with dest.open("wb") as fh:
            # stdin must be closed: with a terminal attached restish waits on it
            # forever from a non-interactive shell.
            try:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                      env=env, timeout=timeout)
            except subprocess.TimeoutExpired:
                dest.unlink(missing_ok=True)
                return f"timed out after {timeout:.0f}s"
        body = dest.read_text(encoding="utf-8", errors="replace")
        code = error_code(body)
        if code is None and proc.returncode == 0 and body.strip().startswith("{"):
            return None
        dest.unlink(missing_ok=True)
        if code and code.startswith("rate_limited") and attempt == 1:
            # ponytail: windows are wall-clock minutes, so sleep to the next one
            time.sleep(61 - time.time() % 60)
            continue
        return code or proc.stderr.decode(errors="replace").strip()[:200] or "empty body"
    return "rate_limited twice"


def parse_seasons(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


def ncaa_weeks(leagues: dict) -> list[int]:
    lg = next(x for x in leagues["leagues"] if x["slug"] == "ncaa")
    return [w["id"] for w in lg["weeks"] if not w["all_star"]]


def fbs_franchises(directory: dict) -> list[int]:
    return sorted(r["franchiseId"] for r in directory["rows"] if FBS_GROUP_ID in r["groupIds"].split(";"))


def flatten_team_games(team_dir: Path, seasons: list[int]) -> list[dict]:
    """One row per (game, franchise): own grades, opponent grades, points, kickoff."""
    games = {}
    for path in team_dir.glob("games_*_wk*.json"):
        for g in json.loads(path.read_text(encoding="utf-8"))["games"]:
            games[g["id"]] = g
    by_game: dict[int, dict[int, dict]] = {}
    for season in seasons:
        for path in team_dir.glob(f"team_summary_{season}_*.json"):
            for row in json.loads(path.read_text(encoding="utf-8"))["team_summary"]:
                by_game.setdefault(row["game_id"], {})[row["franchise_id"]] = row
    rows = []
    for game_id, sides in sorted(by_game.items()):
        g = games.get(game_id, {})
        for fid, own in sides.items():
            opp = sides.get(own.get("opponent_franchise_id"), {})
            rows.append({
                "season": g.get("season"), "week": own.get("week"), "game_id": game_id,
                "start": g.get("start"), "lock_status": own.get("lock_status"),
                "franchise_id": fid, "home": int(bool(own.get("home"))),
                "opponent_franchise_id": own.get("opponent_franchise_id"),
                "points_scored": own.get("points_scored"), "points_allowed": own.get("points_allowed"),
                # ponytail: both sides' grades on one row so a model never joins
                "opp_in_pull": int(bool(opp)),
                **{c: own.get(c) for c in GRADE_COLS},
                **{f"opp_{c}": opp.get(c) for c in GRADE_COLS},
            })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", default=str(current_season()),
                    help="e.g. 2025, 2014-2026, 2019,2021-2023 (default: current season)")
    ap.add_argument("--franchises", help="comma-separated franchise ids (default: every FBS team)")
    ap.add_argument("--player-facets", action="store_true",
                    help="also export every weekly facet/signature leaderboard (slow: ~2 min/week)")
    ap.add_argument("--force", action="store_true", help="re-pull files that already exist")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out-dir", type=Path, default=DATA_ROOT / "raw" / "pff")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seasons = parse_seasons(args.seasons)
    team_dir = args.out_dir / "team"
    team_dir.mkdir(parents=True, exist_ok=True)
    binary = restish_bin()
    env = {**os.environ, "PFF_API": api_key()}
    live = current_season()

    def fresh(dest: Path, season: int | None = None) -> bool:
        """Skip files already on disk -- except the live season, which grows weekly."""
        if args.force or not dest.exists() or dest.stat().st_size == 0:
            return False
        return season != live

    def pull(label: str, cmd: list[str], dest: Path, season: int | None = None) -> bool:
        if fresh(dest, season):
            return True
        if args.dry_run:
            print(f"would pull {label} -> {dest.name}")
            return True
        err = read_json(binary, cmd, dest, env, args.timeout)
        print(f"{'FAIL' if err else 'ok  '} {label}" + (f": {err}" if err else ""), flush=True)
        time.sleep(READ_PACING_SECONDS)
        return err is None

    # 1. reference: weeks and franchises (two reads, refreshed every run)
    leagues_path, directory_path = team_dir / "leagues.json", team_dir / "team_directory.json"
    pull("ref-leagues", ["leagues"], leagues_path, season=live)
    pull("team-directory", ["team-directory", "ncaa"], directory_path, season=live)
    if args.dry_run and not (leagues_path.exists() and directory_path.exists()):
        print("dry run needs leagues.json and team_directory.json on disk once; run without --dry-run first")
        return
    weeks = ncaa_weeks(json.loads(leagues_path.read_text(encoding="utf-8")))
    franchises = ([int(x) for x in args.franchises.split(",")] if args.franchises
                  else fbs_franchises(json.loads(directory_path.read_text(encoding="utf-8"))))
    print(f"{len(seasons)} seasons x {len(weeks)} weeks, {len(franchises)} franchises")

    # 2. games per week, team grades per franchise-season, one overview per season
    failures = 0
    for season in seasons:
        for week in weeks:
            failures += not pull(f"games {season} wk{week}", ["games", "ncaa", str(season), str(week)],
                                 team_dir / f"games_{season}_wk{week}.json", season)
        for fid in franchises:
            failures += not pull(f"team-summary {season} {fid}", ["team-summary", "ncaa", str(season), str(fid)],
                                 team_dir / f"team_summary_{season}_{fid}.json", season)
        failures += not pull(f"team-overview {season}", ["team-overview", "ncaa", str(season)],
                             team_dir / f"team_overview_{season}.json", season)

    # 3. optional: the weekly player leaderboards, through the facet puller
    if args.player_facets:
        ops = {e["id"]: e for e in exportable_ops(load_spec(None)).values() if e["id"] not in SKIP_FACETS}
        for season in seasons:
            for week in weeks:
                values = {"league": "ncaa", "season": str(season), "week": str(week), "division": "fbs"}
                for entry in sorted(ops.values(), key=lambda e: e["id"]):
                    stem = f"{entry['id'].replace('-', '_')}_ncaa_{season}_fbs_wk{week}"
                    if not args.force and any((args.out_dir / f"{stem}{ext}").exists() for ext in (".csv", ".json")):
                        continue
                    if args.dry_run:
                        print(f"would export {entry['id']} {season} wk{week}")
                        continue
                    line = pull_one(binary, entry, values, args.out_dir, "ci", env, args.timeout)
                    print(line, flush=True)
                    failures += not line.startswith(("ok", "JSON", "SKIP"))
                    time.sleep(EXPORT_PACING_SECONDS)

    # 4. flatten to the modeling table
    if not args.dry_run:
        rows = flatten_team_games(team_dir, seasons)
        out = DATA_ROOT / "processed" / "pff" / "team_game.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["game_id"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} team-game rows -> {out}")
    if failures:
        raise SystemExit(f"{failures} pulls failed")


if __name__ == "__main__":
    main()
