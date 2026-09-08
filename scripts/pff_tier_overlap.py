"""What does the per-team report tier hold that the league-wide leaderboards do not?

    python scripts/pff_tier_overlap.py                 # 2025
    python scripts/pff_tier_overlap.py --season 2025 -v

The team-report tier is 3,808 of a season's 3,998 reads -- roughly half the wall clock of
a full pull, and the whole difference between a 14-hour and a 7-hour backfill. Most of it
is the same players re-cut by team, so the question before any backfill is which of the 19
reports carry columns the leaderboards do not.

Column names differ by convention only (`gradesPass` vs `grades_pass`), so both sides are
compared in snake_case. Two groups of columns are ignored: biographical ones, which the
roster pull already carries, and ones recoverable from another file (`games_played` is
`player_game_count` on the leaderboard; `team_abbreviation` is in the team directory).
Read-only; sizes a decision, changes nothing.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

PFF_ROOT = DATA_ROOT / "raw" / "pff"
# Identity and roster columns; `roster_<season>_<slug>.json` already carries them.
BIOGRAPHICAL = {"draft_season", "eligible_season", "jersey_number", "team", "team_name",
                "franchise_id", "player", "player_id", "position"}
# Present only in the report tier but recoverable elsewhere: the games a player appeared in
# is `player_game_count` on the leaderboard, and the abbreviation is in the team directory.
DERIVABLE = {"games_played", "team_abbreviation"}
# team-report name -> the leaderboard that covers the same players and metrics.
PAIRS = {
    "offense": "facet_offense_summary", "passing": "facet_passing_summary",
    "passing-depth": "facet_passing_depth", "passing-pressure": "facet_passing_pressure",
    "receiving": "facet_receiving_summary", "receiving-depth": "facet_receiving_depth",
    "rushing": "facet_rushing_summary", "blocking": "facet_offense_blocking",
    "pass-blocking": "facet_offense_pass_blocking", "run-blocking": "facet_offense_run_blocking",
    "defense": "facet_defense_summary", "run-defense": "facet_defense_run",
    "pass-rush": "facet_defense_pass_rush", "coverage": "facet_defense_coverage",
    "special-teams": "facet_special_summary", "kick-returns": "facet_return_summary",
    "field-goals": "facet_field_goal_summary", "punting": "facet_punting_summary",
    "kickoffs": "facet_kickoff_summary",
}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def leaderboard_columns(stem: str, season: int) -> set[str]:
    """Every column the leaderboard offers for a season, unioned over its weekly files."""
    cols: set[str] = set()
    for path in PFF_ROOT.glob(f"{stem}_ncaa_{season}*.csv"):
        with path.open(encoding="utf-8") as fh:
            cols |= set(next(csv.reader(fh), []))
    for path in PFF_ROOT.glob(f"{stem}_ncaa_{season}*.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        cols |= {snake(c["key"]) for c in body.get("columns", []) if isinstance(c, dict)}
    return cols


def report_columns(report: str, season: int) -> tuple[set[str], int]:
    """Every column the per-team report offers, unioned over the franchises pulled."""
    cols, seen = set(), 0
    for path in (PFF_ROOT / "team").glob(f"team_report_{season}_*_{report}.json"):
        body = json.loads(path.read_text(encoding="utf-8"))
        cols |= {snake(c["key"]) for c in body.get("columns", []) if isinstance(c, dict)}
        seen += 1
    return cols, seen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("-v", "--verbose", action="store_true", help="name every unique column")
    args = ap.parse_args()

    carries, redundant = [], []
    for report, stem in sorted(PAIRS.items()):
        rcols, files = report_columns(report, args.season)
        if not files:
            continue
        unique = rcols - leaderboard_columns(stem, args.season) - BIOGRAPHICAL - DERIVABLE
        (carries if unique else redundant).append((report, stem, files, sorted(unique)))

    print(f"PFF {args.season}: 19 team reports against their leaderboards\n")
    print(f"[carries unique columns] {len(carries)} reports")
    for report, stem, files, unique in carries:
        shown = unique if args.verbose else unique[:6]
        print(f"  {report:16s} {len(unique):3d} unique ({files} files) -- {', '.join(shown)}"
              f"{'...' if len(unique) > len(shown) else ''}")

    print(f"\n[fully covered by the leaderboard] {len(redundant)} reports")
    for report, stem, files, _ in redundant:
        print(f"  {report:16s} {files} files -> {stem}")

    saved = sum(files for _, _, files, _ in redundant)
    print(f"\n{saved} reads a season are a re-cut of leaderboard data "
          f"({saved * 0.65 / 60:.0f} min a season, {saved * 0.65 * 11 / 3600:.1f} h over an "
          f"11-season backfill).")


if __name__ == "__main__":
    main()
