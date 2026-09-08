"""Pull the PFF data a game model needs, and flatten it to one row per team-game.

    python scripts/pull_pff_modeling.py --seasons 2025                 # one season
    python scripts/pull_pff_modeling.py --seasons 2014-2026            # backfill
    python scripts/pull_pff_modeling.py --seasons 2026 --player-facets # + weekly leaderboards
    python scripts/pull_pff_modeling.py --seasons 2026 --weeks 1 --player-facets --rosters
    python scripts/pull_pff_modeling.py --seasons 2025 --dry-run

Four cheap reads give a complete team-game history without touching the export
budget, and none of them loops over teams:

    ref-leagues      seasons and week ids (postseason weeks are 17-20, not 15-18)
    team-directory   every franchise with its group ids; group 11 is FBS
    ref-games        one call per (season, week): game_id, home/away, score, kickoff
    team-overview    one call per (season, week) with --week: PFF's 14 team grades
                     for every team that played that week, all divisions

That is 42 reads a season. (`team-summary` gives the same grades one franchise at a
time -- 138 reads a season and only the teams you list -- so it is not used.)

Three more, all `/v2` and all pinned to PFF's *current* season (they take no season
parameter, so history is not reachable through them):

    team-list        one read: the whole schedule 2004-now, future games included
    team-stats       7 categories x week: EPA/play, success rate, explosive rate,
                     points per drive, third down, red zone, turnovers, pass/rush
                     splits, opponent tendencies -- every team, ranked
    team-roster      --rosters: one read per FBS team, depth chart with grade,
                     status and snap share (availability signal for the live week)

Files that exist are skipped except in the live season; use --weeks to scope a run.

Everything lands as JSON under data/raw/pff/team/ (outside the warehouse glob, which
is not recursive), then `team_game.csv` is rebuilt under data/processed/pff/: one row
per (game_id, franchise_id) with that team's grades, the opponent's grades from the
same game, home/away, points, kickoff, and whether each side is FBS. A game's grades are a *result* of that
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
TEAM_STATS_CATEGORIES = ("offense-overall-success", "offense-passing", "offense-rushing",
                         "defense-overall-success", "defense-passing", "defense-rushing",
                         "defense-opponent-tendencies")
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


def fbs_rows(directory: dict) -> list[dict]:
    return [r for r in directory["rows"] if FBS_GROUP_ID in r["groupIds"].split(";")]


def fbs_franchises(directory: dict) -> list[int]:
    return sorted(r["franchiseId"] for r in fbs_rows(directory))


def flatten_team_games(team_dir: Path, seasons: list[int], fbs: set[int] = frozenset()) -> list[dict]:
    """One row per (game, franchise): own grades, opponent grades, points, kickoff.

    A week's overview row has no game id, so it is matched to that week's games by
    franchise -- sound because a team plays at most one game per PFF week id.
    """
    rows = []
    for season in seasons:
        for path in sorted(team_dir.glob(f"team_overview_{season}_wk*.json")):
            week = int(path.stem.rsplit("wk", 1)[1])
            games_path = team_dir / f"games_{season}_wk{week}.json"
            if not games_path.exists():
                continue
            grades = {r["franchise_id"]: r
                      for r in json.loads(path.read_text(encoding="utf-8"))["team_overview"]}
            for g in json.loads(games_path.read_text(encoding="utf-8"))["games"]:
                for side, opp_side in (("home", "away"), ("away", "home")):
                    fid, opp_fid = g[f"{side}_franchise_id"], g[f"{opp_side}_franchise_id"]
                    own, opp = grades.get(fid, {}), grades.get(opp_fid, {})
                    rows.append({
                        "season": season, "week": week, "game_id": g["id"], "start": g.get("start"),
                        "lock_status": g.get("lock_status"), "franchise_id": fid, "home": int(side == "home"),
                        "fbs": int(fid in fbs), "opponent_franchise_id": opp_fid, "opp_fbs": int(opp_fid in fbs),
                        "points_scored": (g.get("score") or {}).get(f"{side}_team"),
                        "points_allowed": (g.get("score") or {}).get(f"{opp_side}_team"),
                        # ponytail: both sides' grades on one row so a model never joins
                        "graded": int(bool(own)),
                        **{c: own.get(c) for c in GRADE_COLS},
                        **{f"opp_{c}": opp.get(c) for c in GRADE_COLS},
                    })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", default=str(current_season()),
                    help="e.g. 2025, 2014-2026, 2019,2021-2023 (default: current season)")
    ap.add_argument("--weeks", help="week ids to pull, e.g. 1 or 0-3 (default: every non-all-star week)")
    ap.add_argument("--player-facets", action="store_true",
                    help="also export every weekly facet/signature leaderboard (slow: ~2 min/week)")
    ap.add_argument("--rosters", action="store_true",
                    help="also pull every FBS team's depth-chart roster (current season only, 138 reads)")
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
    if args.weeks:
        weeks = [w for w in parse_seasons(args.weeks) if w in weeks]
    directory = json.loads(directory_path.read_text(encoding="utf-8"))
    fbs = set(fbs_franchises(directory))
    print(f"{len(seasons)} seasons x {len(weeks)} weeks, {len(fbs)} FBS franchises")
    # the schedule: every game PFF knows about, past and future, in one read
    pull("team-list", ["team-list", "ncaa"], team_dir / "schedule.json", season=live)

    # 2. per (season, week): the games played, and every team's grades for that week
    failures = 0
    for season in seasons:
        for week in weeks:
            failures += not pull(f"games {season} wk{week}", ["games", "ncaa", str(season), str(week)],
                                 team_dir / f"games_{season}_wk{week}.json", season)
            failures += not pull(f"team-overview {season} wk{week}",
                                 ["team-overview", "ncaa", str(season), "--week", str(week)],
                                 team_dir / f"team_overview_{season}_wk{week}.json", season)
            if season == live:  # /v2 has no season parameter; it only ever answers for `live`
                for cat in TEAM_STATS_CATEGORIES:
                    failures += not pull(f"team-stats {season} wk{week} {cat}",
                                         ["team-stats", "ncaa", "--category", cat, "--week-ids", str(week)],
                                         team_dir / f"team_stats_{season}_wk{week}_{cat}.json", season)
        if args.rosters and season == live:
            for r in fbs_rows(directory):
                failures += not pull(f"team-roster {r['slug']}", ["team-roster", "ncaa", r["slug"]],
                                     team_dir / f"roster_{season}_{r['slug']}.json", season)
        elif args.rosters:
            print(f"skip rosters {season}: team-roster only serves the current season ({live})")

    # 3. optional: the weekly player leaderboards, through the facet puller
    if args.player_facets:
        ops = {e["id"]: e for e in exportable_ops(load_spec(None)).values()
               if e["id"] not in SKIP_FACETS
               and set(e["required"]) <= {"league", "season", "week", "division"}}
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
        # every season on disk, not just this run's -- the CSV is the whole history
        on_disk = sorted({int(f.stem.split("_")[2]) for f in team_dir.glob("team_overview_*_wk*.json")})
        rows = flatten_team_games(team_dir, on_disk, fbs)
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
