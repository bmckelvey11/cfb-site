"""Classify PFF and CFBD warehouse columns by whether they can be a pre-game feature.

Two independent tests. A column has to pass both to be usable before kickoff:

  1. CONSTRUCTION -- does the number encode the result of a game? Points, wins,
     margin, EPA/PPA, success rate, explosiveness, win probability and the
     ratings built from them do. Snap counts, alignment, personnel, play-calling
     rates, attempts by direction, target depth and time-to-throw do not.

  2. GRAIN -- can it be recomputed as of a cutoff? A week- or game-grain table
     can be summed over weeks 1..n-1, so even a result-informed column becomes a
     legitimate pre-game feature. A season-final snapshot cannot: it is one row
     per team-season with no as-of date, so it is lookahead for every game
     inside that season no matter what it measures.

The practically important cell is (2) failing while (1) passes -- a column that
measures nothing about outcomes and is still unusable, because the only copy we
hold is a season total. `stg.advanced_season_stats` is the whole table of those.

Verdicts:
    pregame_direct    known before the season starts; usable as-is
    pregame_windowed  usable ONLY as a trailing sum/mean over prior weeks
    lookahead_only    season-final snapshot; not usable for in-season games
    postgame          encodes this game's result; never a feature for it
    metadata          key or label, not a stat

Usage:
    python scripts/audit_pregame_eligibility.py              # summary to stdout
    python scripts/audit_pregame_eligibility.py --csv        # + per-column CSV
    python scripts/audit_pregame_eligibility.py --source pff

See docs/pregame-feature-eligibility-2026-09-16.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402

# --- the tables in play -------------------------------------------------------
# grain is a property of the table, verified against information_schema below.
PFF_TABLES = (
    "pff_blocking_alignment", "pff_defense_coverage", "pff_defense_pass_rush",
    "pff_defense_run", "pff_defense_summary", "pff_field_goal", "pff_franchise",
    "pff_kickoff", "pff_offense_summary", "pff_pass_blocking", "pff_passing",
    "pff_passing_allowed_pressure", "pff_player_season", "pff_punting",
    "pff_receiving", "pff_return", "pff_run_blocking", "pff_rushing",
    "pff_rushing_direction", "pff_special_teams", "pff_team_pass_block_week",
)

CFBD_TABLES = (
    "advanced_game_stats", "advanced_season_stats", "advanced_box_score__teams_ppa",
    "advanced_box_score__teams_havoc", "advanced_box_score__teams_success_rates",
    "advanced_box_score__teams_explosiveness", "advanced_box_score__teams_rushing",
    "advanced_box_score__teams_field_position",
    "advanced_box_score__teams_scoring_opportunities",
    "adjusted_team_season", "core_ratings", "ratings", "fpi", "elo",
    "team_stats", "game_team_stats", "talent", "recruiting_teams",
    "returning_production", "coaches", "drives",
)

# Tables whose contents are fixed before kickoff of the first game.
PRESEASON_TABLES = {"talent", "recruiting_teams", "returning_production"}

# --- column families ----------------------------------------------------------
# (regex, family, result_informed). First match wins, so order matters.
FAMILIES: tuple[tuple[str, str, bool], ...] = (
    # keys and labels
    (r"^(season|year|week|game_?id|team_?id|franchise_id|player_id|conference_?id|"
     r"teams?_\w*idx|_source_file|pulled_at|season_?type|through_?season_?type|"
     r"through_?week|model_?version|split|direction|home_away|cfbd_team_id)$", "key", False),
    (r"^(team|opponent|school|conference|player|position|jersey_number|"
     r"abbreviation|classification|slug|team_name|kind|match|stat_?name)$", "label", False),
    (r"^(draft_season|eligible_season)$", "label", False),

    # --- result-informed: encodes what happened ---
    (r"(points|score|winner|win_?prob|excitement)", "game_outcome", True),
    (r"(ppa|epa)", "epa_ppa", True),  # totalPPA has no separator
    (r"success_?rate", "success_rate", True),
    (r"explosive", "explosiveness", True),
    (r"^(sp[A-Z_]|sp_|spOverall|spOffense|spDefense|spSpecialTeams|overall|offense$|"
     r"defense$|fpi|elo|srs|efficiencies_|resume_?ranks?_)", "rating", True),
    (r"(yards|yds)", "yardage", True),
    (r"(touchdown|interception|fumble|sack|reception|completion|tackle|stop|"
     r"pressure|hurr|hit|havoc|turnover|penalt|catch|drop|target|first_?downs|"
     r"break_?up|safet|batted|forced|missed|avoided|blocks?$|made|percent_made)",
     "play_outcome", True),
    (r"(rating|grade_?s?_)", "grade_or_rating", True),
    (r"(line_?yards|second_?level|open_?field|stuff|power_?success|"
     r"points_?per_?opportunity|field_?position)", "efficiency", True),

    # more result-informed, matched after the broad patterns above
    (r"(^|_)(ypa|yprr|yco_?attempt|pbe|prp|elu_|big_?time|bats$|misses$|"
     r"thrown_?aways|aimed_?passes|assists|scrambles|total_?touches|"
     r"long$|longest$|rank$|scoring$)", "play_outcome", True),
    (r"(touchbacks|downeds|inside_?twenties|out_?of_?bounds|onside|returns$|"
     r"kicks_?returned|hangtime|average_?distance)", "play_outcome", True),
    (r"drive_?(id|number|result)|start(period|yardline|time)|end(period|yardline|time)|"
     r"elapsed_", "drive_detail", True),

    # --- result-free: usage, alignment, play-calling ---
    (r"snap_?counts?", "snap_count", False),
    (r"(^|_)snaps?($|_)", "snap_count", False),
    (r"(routes|dropbacks|attempts|plays|drives|pass_?block|run_?block|coverage_?snaps|"
     r"pass_?rush_?(snaps|opp|wins)|opportun)", "volume", False),
    (r"(rate$|_rate|percent|_pct|share)", "usage_rate", False),
    (r"(avg_?depth|avg_?time|time_?to_?throw|ttt|depth_?of_?target)", "deployment", False),
    (r"(usage|returning)", "returning_production", False),
    (r"^talent$", "recruiting", False),
    (r"(first_?name|last_?name|hire_?date|seasons$|^id$|is_?home_?offense|"
     r"conference$|team$|^teams$|stat_?value)", "label", False),
)

VERDICT_NOTE = {
    "pregame_direct": "known before the season; use as-is",
    "pregame_windowed": "sum/mean over prior weeks only; the season total is lookahead",
    "lookahead_only": "season-final snapshot, no as-of date; unusable for in-season games",
    "needs_rekey": "per-game rows with no game key; rekey via (season, teams) first",
    "postgame": "encodes this game's result",
    "metadata": "key or label",
}


def classify_column(col: str) -> tuple[str, bool]:
    for pattern, family, result_informed in FAMILIES:
        if re.search(pattern, col, flags=re.IGNORECASE):
            return family, result_informed
    return "other", True  # unmatched is assumed result-informed until reviewed


def table_grain(cols: set[str]) -> str:
    low = {c.lower() for c in cols}
    if "week" in low:
        return "week"
    if {"gameid", "game_id"} & low:
        return "game"
    # advanced_box_score and its children hold one row per GAME but carry no
    # game key and no week -- only season plus the two team names. The rows
    # cannot be ordered in time as stored, so they are unusable until rekeyed
    # by joining (season, home_team, away_team) back to core.fact_game.
    if {"gameinfo_hometeam", "gameinfo_awayteam"} & low:
        return "game_unkeyed"
    if "season" in low or "year" in low:
        return "season_final"
    return "static"


def verdict(table: str, family: str, result_informed: bool, grain: str) -> str:
    if family in ("key", "label"):
        return "metadata"
    if table in PRESEASON_TABLES:
        return "pregame_direct"
    if family == "game_outcome":
        return "postgame"
    if grain in ("week", "game"):
        return "pregame_windowed"
    if grain == "game_unkeyed":
        return "needs_rekey"
    return "lookahead_only"


def build(con: duckdb.DuckDBPyConnection, tables: tuple[str, ...], source: str) -> pd.DataFrame:
    rows = []
    for table in tables:
        cols = [r[0] for r in con.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'stg' and table_name = ? order by ordinal_position",
            [table]).fetchall()]
        if not cols:
            continue
        grain = table_grain(set(cols))
        for col in cols:
            family, result_informed = classify_column(col)
            rows.append({
                "source": source,
                "table": f"stg.{table}",
                "column": col,
                "grain": grain,
                "family": family,
                "result_informed": result_informed,
                "verdict": verdict(table, family, result_informed, grain),
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None)
    ap.add_argument("--source", choices=("pff", "cfbd", "all"), default="all")
    ap.add_argument("--csv", action="store_true", help="also write the per-column CSV")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    con = duckdb.connect(args.db or str(DB_PATH), read_only=True)
    frames = []
    if args.source in ("pff", "all"):
        frames.append(build(con, PFF_TABLES, "pff"))
    if args.source in ("cfbd", "all"):
        frames.append(build(con, CFBD_TABLES, "cfbd"))
    df = pd.concat(frames, ignore_index=True)

    print(f"{len(df)} columns across {df.table.nunique()} tables\n")
    print("-- verdict by source")
    print(pd.crosstab(df.verdict, df.source).to_string(), "\n")

    print("-- the usable ones, by family")
    ok = df[df.verdict.isin(("pregame_direct", "pregame_windowed"))]
    print(pd.crosstab([ok.source, ok.family], ok.verdict).to_string(), "\n")

    print("-- tables that are lookahead-only (season-final snapshots)")
    lo = df[df.verdict == "lookahead_only"]
    for t, n in lo.groupby("table").size().sort_values(ascending=False).items():
        print(f"   {t:52s} {n} cols")

    if args.csv:
        out = Path(args.out or PROCESSED / "pregame_feature_eligibility.csv")
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"\nwrote {len(df)} rows -> {out}")


def _selftest() -> None:
    """Pins the judgement calls that the regex order decides."""
    cases = {
        "snap_counts_dl": ("snap_count", False),
        "coverage_snaps": ("snap_count", False),
        "off_pass_snap_rate": ("snap_count", False),
        "gap_attempts": ("volume", False),
        "avg_time_to_throw": ("deployment", False),
        "offense_passingPlays_rate": ("volume", False),
        "grades_coverage_defense": ("grade_or_rating", True),
        "offense_ppa": ("epa_ppa", True),
        "spOverall": ("rating", True),
        "gameInfo_homePoints": ("game_outcome", True),
        "defense_havoc_total": ("play_outcome", True),
        "season": ("key", False),
    }
    for col, want in cases.items():
        got = classify_column(col)
        assert got == want, f"{col}: got {got}, want {want}"
    assert table_grain({"season", "week", "team"}) == "week"
    assert table_grain({"season", "team"}) == "season_final"
    assert verdict("advanced_season_stats", "usage_rate", False, "season_final") == "lookahead_only"
    assert verdict("pff_passing", "play_outcome", True, "week") == "pregame_windowed"
    assert verdict("talent", "other", True, "season_final") == "pregame_direct"
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
