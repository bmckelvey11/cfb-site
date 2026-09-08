"""Pull every PFF API operation that yields data, and flatten the team-game core.

    python scripts/pull_pff_modeling.py --seasons 2025                     # league-wide core
    python scripts/pull_pff_modeling.py --seasons 2014-2026                # backfill the core
    python scripts/pull_pff_modeling.py --seasons 2026 --weeks 1 --player-facets
    python scripts/pull_pff_modeling.py --seasons 2025 --team-reports --teams alabama-crimson-tide
    python scripts/pull_pff_modeling.py --seasons 2025 --player-ids 198077,@data/qbs.txt
    python scripts/pull_pff_modeling.py --seasons 2025 --dry-run

Every command line is built from the OpenAPI document: required parameters become
positionals in spec order, optional ones become flags. Nothing about argument order
is hardcoded, so a new operation needs a line in one of the PLAN tables below and
nothing else.

Tiers, cheapest first. All reads (100/minute) unless marked export (20/minute).

  core -- always. League-wide, no per-entity loop, ~50 reads a season:
    ref-leagues            week ids (postseason is 17-20; all-star 21 and 30)
    team-directory         per season: every franchise with group ids; group 11 = FBS
    team-list              one read: the whole schedule 2004-now, future games included
    ref-games              per (season, week): game_id, home/away, score, kickoff
    team-overview --week   per (season, week): PFF's 14 team grades for every team
    team-stats             per (season, week) x 7 categories: EPA/play, success rate,
                           explosive rate, points/drive, 3rd down, red zone, turnovers,
                           pass/rush splits, opponent tendencies -- every team, ranked

  --player-facets -- the 25 league-wide leaderboards + 4 signature stats, per week,
    as CSV exports through pull_pff_facet.py. ~2 minutes a week.

  --team-reports -- per FBS team per season, 28 reads a team (~45 min a season for
    all 138; scope with --teams): team-schedule, team-roster, team-leaders x4,
    team-rushing-direction x2, team-report x19, team-summary.

  --player-ids -- per player, 2 + 20 reads a season: ref-players, player-seasons, and
    the 20 season-scoped player-* reports. Every graded FBS player is ~12k a season,
    so this takes an explicit id list (comma-separated, @file for one id per line).

Landing: data/raw/pff/team/ and data/raw/pff/player/ as JSON, leaderboards as CSV in
data/raw/pff/. None of it is under the warehouse glob, which is not recursive. Then
data/processed/pff/team_game.csv is rebuilt from every season on disk: one row per
(game, team) with own and opponent grades, home/away, points, kickoff, FBS flags.
A game's grades are a *result* of that game -- pre-game features roll earlier weeks.

Files already on disk are skipped, except in the current season, which grows weekly;
--force re-pulls. A 429 sleeps to the next wall-clock minute and retries once. stdin
is closed on every restish call: with a terminal attached it waits forever from a
non-interactive shell.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import DATA_ROOT, current_season  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pull_pff_facet import (  # noqa: E402
    EXPORT_PACING_SECONDS, api_key, error_code, exportable_ops, load_spec, pull_one,
    resolve, restish_bin,
)

READ_PACING_SECONDS = 0.7  # 100 reads/minute, with headroom
FBS_GROUP_ID = "11"
# passing_detail is the union of the other four passing facets and hangs;
# the other two answer 500 for every NCAA pull. See docs/pff-warehouse-schema.md.
SKIP_FACETS = {"facet-passing-detail", "facet-receiving-coverage", "facet-defense-coverage-matchup"}

TEAM_STATS_CATEGORIES = ("offense-overall-success", "offense-passing", "offense-rushing",
                         "defense-overall-success", "defense-passing", "defense-rushing",
                         "defense-opponent-tendencies")
TEAM_REPORTS = ("offense", "passing", "passing-depth", "passing-pressure", "receiving",
                "receiving-depth", "rushing", "blocking", "pass-blocking", "run-blocking",
                "defense", "run-defense", "pass-rush", "coverage", "special-teams",
                "kick-returns", "field-goals", "punting", "kickoffs")
TEAM_LEADER_GROUPS = ("receiving", "passing", "rushing", "defense")
PLAYER_REPORTS = ("offense-summary", "offense-blocking", "offense-pass-blocking", "offense-run-blocking",
                  "passing-summary", "passing-concept", "passing-depth", "passing-pressure",
                  "rushing-summary", "rushing-direction", "receiving-summary", "receiving-depth",
                  "defense-summary", "field-goal-summary", "kickoff-summary", "punting-summary",
                  "return-summary", "special-summary", "snaps-summary", "position-pivot")

GRADE_COLS = (
    "grades_overall", "grades_offense", "grades_pass", "grades_run", "grades_pass_block",
    "grades_run_block", "grades_pass_route", "grades_defense", "grades_run_defense",
    "grades_pass_rush_defense", "grades_coverage_defense", "grades_tackle", "grades_misc_st",
)


# ---------------------------------------------------------------- spec-driven commands

def all_ops(spec: dict) -> dict[str, dict]:
    """operationId -> required wire names (in order) and optional wire name -> flag."""
    ops = {}
    for methods in spec["paths"].values():
        op = methods.get("get")
        if not op:
            continue
        params = [resolve(spec, p) for p in op.get("parameters", [])]
        ops[op["operationId"]] = {
            "required": [p["name"] for p in params if p.get("required")],
            "optional": {p["name"]: "--" + p.get("x-cli-name", re.sub(r"(?<!^)(?=[A-Z])", "-", p["name"]).lower())
                         for p in params if not p.get("required")},
        }
    return ops


def command(ops: dict, op_id: str, values: dict) -> list[str]:
    """`values` is keyed by wire name; positionals in spec order, the rest as flags."""
    op = ops[op_id]
    cmd = [op_id] + [str(values[k]) for k in op["required"]]
    for wire, flag in op["optional"].items():
        if values.get(wire) is not None:
            cmd += [flag, str(values[wire])]
    return cmd


def read_json(binary: str, args: list[str], dest: Path, env: dict, timeout: float) -> str | None:
    """Run one read to dest as JSON. Returns an error string, or None."""
    cmd = [binary, "pff", *args, "-p", "ci", "-o", "json", "--rsh-print", "b"]
    for attempt in (1, 2):
        with dest.open("wb") as fh:
            try:
                proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                      env=env, timeout=timeout)
            except subprocess.TimeoutExpired:
                proc = None
        if proc is None:
            dest.unlink(missing_ok=True)
            return f"timed out after {timeout:.0f}s"
        body = dest.read_text(encoding="utf-8", errors="replace")
        code = error_code(body)
        if code is None and proc.returncode == 0 and body.strip().startswith("{"):
            return None
        dest.unlink(missing_ok=True)
        if code and code.startswith("rate_limited") and attempt == 1:
            time.sleep(61 - time.time() % 60)  # windows are wall-clock minutes
            continue
        return code or proc.stderr.decode(errors="replace").strip()[:200] or "empty body"
    return "rate_limited twice"


# ---------------------------------------------------------------- small pure helpers

def parse_seasons(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


def parse_ids(spec: str) -> list[int]:
    """Comma-separated ids; an @path item is a file with one id per line."""
    out = []
    for part in spec.split(","):
        if part.startswith("@"):
            out += [int(x) for x in Path(part[1:]).read_text(encoding="utf-8").split() if x.strip()]
        elif part.strip():
            out.append(int(part))
    return sorted(set(out))


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


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", default=str(current_season()),
                    help="e.g. 2025, 2014-2026, 2019,2021-2023 (default: current season)")
    ap.add_argument("--weeks", help="week ids to pull, e.g. 1 or 0-3 (default: every non-all-star week)")
    ap.add_argument("--player-facets", action="store_true",
                    help="also export every weekly facet/signature leaderboard (~2 min/week)")
    ap.add_argument("--team-reports", action="store_true",
                    help="also pull the per-team /v2 reports and team-summary (28 reads/team)")
    ap.add_argument("--teams", help="comma-separated team slugs to scope --team-reports (default: every FBS team)")
    ap.add_argument("--player-ids", help="comma-separated player ids, @file for one per line: pull the player-* reports")
    ap.add_argument("--force", action="store_true", help="re-pull files that already exist")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--out-dir", type=Path, default=DATA_ROOT / "raw" / "pff")
    ap.add_argument("--spec", type=Path, help="local OpenAPI json (default: fetch the live one)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seasons = parse_seasons(args.seasons)
    team_dir, player_dir = args.out_dir / "team", args.out_dir / "player"
    team_dir.mkdir(parents=True, exist_ok=True)
    spec = load_spec(args.spec)
    ops = all_ops(spec)
    binary = restish_bin()
    env = {**os.environ, "PFF_API": api_key()}
    live = current_season()
    failures = 0

    def pull(op_id: str, values: dict, dest: Path, season: int | None = None) -> bool:
        nonlocal failures
        if not args.force and dest.exists() and dest.stat().st_size and season != live:
            return True
        label = " ".join(command(ops, op_id, values))
        if args.dry_run:
            print(f"would pull {label} -> {dest.relative_to(args.out_dir)}")
            return True
        err = read_json(binary, command(ops, op_id, values), dest, env, args.timeout)
        print(f"{'FAIL' if err else 'ok  '} {label}" + (f": {err}" if err else ""), flush=True)
        time.sleep(READ_PACING_SECONDS)
        failures += bool(err)
        return err is None

    # 1. reference -------------------------------------------------------------
    leagues_path = team_dir / "leagues.json"
    pull("ref-leagues", {}, leagues_path, live)
    pull("team-list", {"league": "ncaa"}, team_dir / "schedule.json", live)
    directories = {}
    for season in seasons:
        dest = team_dir / f"team_directory_{season}.json"
        pull("team-directory", {"league": "ncaa", "season": season}, dest, season)
        if dest.exists():
            directories[season] = json.loads(dest.read_text(encoding="utf-8"))
    if args.dry_run and not (leagues_path.exists() and directories):
        print("dry run needs leagues.json and a team_directory on disk; run once without --dry-run")
        return
    weeks = ncaa_weeks(json.loads(leagues_path.read_text(encoding="utf-8")))
    if args.weeks:
        weeks = [w for w in parse_seasons(args.weeks) if w in weeks]
    print(f"{len(seasons)} seasons x {len(weeks)} weeks")

    # 2. core: per (season, week), league-wide ---------------------------------
    for season in seasons:
        for week in weeks:
            pull("ref-games", {"league": "ncaa", "season": season, "week": week},
                 team_dir / f"games_{season}_wk{week}.json", season)
            pull("team-overview", {"league": "ncaa", "season": season, "week": week},
                 team_dir / f"team_overview_{season}_wk{week}.json", season)
            for cat in TEAM_STATS_CATEGORIES:
                pull("team-stats", {"league": "ncaa", "season": season, "weekIds": week, "category": cat},
                     team_dir / f"team_stats_{season}_wk{week}_{cat}.json", season)

    # 3. per team ---------------------------------------------------------------
    if args.team_reports:
        for season in seasons:
            teams = fbs_rows(directories.get(season, {"rows": []}))
            if args.teams:
                keep = set(args.teams.split(","))
                teams = [t for t in teams if t["slug"] in keep]
            for t in teams:
                slug, fid = t["slug"], t["franchiseId"]
                base = {"league": "ncaa", "team": slug, "season": season}
                pull("team-schedule", base, team_dir / f"team_schedule_{season}_{slug}.json", season)
                pull("team-roster", base, team_dir / f"roster_{season}_{slug}.json", season)
                for group in TEAM_LEADER_GROUPS:
                    pull("team-leaders", {**base, "group": group},
                         team_dir / f"team_leaders_{season}_{slug}_{group}.json", season)
                for table in ("rows", "totals"):
                    pull("team-rushing-direction", {**base, "table": table},
                         team_dir / f"team_rushing_direction_{season}_{slug}_{table}.json", season)
                for report in TEAM_REPORTS:
                    pull("team-report", {**base, "report": report},
                         team_dir / f"team_report_{season}_{slug}_{report}.json", season)
                pull("team-summary", {"league": "ncaa", "season": season, "franchise_id": fid},
                     team_dir / f"team_summary_{season}_{fid}.json", season)

    # 4. per player -------------------------------------------------------------
    if args.player_ids:
        player_dir.mkdir(exist_ok=True)
        for pid in parse_ids(args.player_ids):
            pull("ref-players", {"league": "ncaa", "id": pid}, player_dir / f"player_{pid}_ref.json", live)
            pull("player-seasons", {"league": "ncaa", "player_id": pid}, player_dir / f"player_{pid}_seasons.json", live)
            for season in seasons:
                for report in PLAYER_REPORTS:
                    pull(f"player-{report}", {"league": "ncaa", "season": season, "player_id": pid},
                         player_dir / f"player_{pid}_{season}_{report.replace('-', '_')}.json", season)

    # 5. weekly leaderboards, as exports ----------------------------------------
    if args.player_facets:
        facets = {e["id"]: e for e in exportable_ops(spec).values()
                  if e["id"] not in SKIP_FACETS
                  and set(e["required"]) <= {"league", "season", "week", "division"}}
        for season in seasons:
            for week in weeks:
                values = {"league": "ncaa", "season": str(season), "week": str(week), "division": "fbs"}
                for entry in sorted(facets.values(), key=lambda e: e["id"]):
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

    # 6. the modeling table, from every season on disk --------------------------
    if not args.dry_run:
        on_disk = sorted({int(f.stem.split("_")[2]) for f in team_dir.glob("team_overview_*_wk*.json")})
        fbs = set()
        for f in team_dir.glob("team_directory_*.json"):
            fbs |= set(fbs_franchises(json.loads(f.read_text(encoding="utf-8"))))
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
