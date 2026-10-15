"""Opponent-adjusted team power ratings from the closing spread.

v1.0
Reuses the crossed team/opponent random-effects fit and cross-season
shrinkage built for PPA ratings (scripts/build_ppa_opponent_adjusted_ratings.py),
swapping the response variable to the closing point spread. A spread already
prices in information (injuries, depth, matchup-specific factors) that
box-score PPA can't see, so this is a distinct signal, not a redundant
opponent proxy.

Sign convention: `spread` is the number added to the home team's score
(negative = home favored). Home team's implied margin = -spread.

Usage:
    python scripts/build_spread_implied_power_ratings.py --season 2026
    python scripts/build_spread_implied_power_ratings.py --season 2026 --week 3 --prior-seasons 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cfb_paths
from scripts.build_ppa_opponent_adjusted_ratings import fit_crossed_effects, shrink_toward_prior

VERSION = "1.0"


def spread_to_paired_rows(games: pd.DataFrame) -> pd.DataFrame:
    """Reshape one-row-per-game spreads into two rows per game (home/away perspective)."""
    # astype(bool) before negating: `~` on an object column (any None present)
    # is Python's integer inversion (~True == -2), not a logical NOT.
    is_home_team = ~games["neutralSite"].fillna(False).astype(bool)
    home_rows = pd.DataFrame({
        "season": games["season"],
        "week": games["week"],
        "team": games["homeTeam"],
        "opponent": games["awayTeam"],
        "margin": -games["spread"],
        "is_home": is_home_team,
    })
    away_rows = pd.DataFrame({
        "season": games["season"],
        "week": games["week"],
        "team": games["awayTeam"],
        "opponent": games["homeTeam"],
        "margin": games["spread"],
        "is_home": False,
    })
    return pd.concat([home_rows, away_rows], ignore_index=True)


def load_games(con: duckdb.DuckDBPyConnection, seasons: list[int], max_week: int | None = None) -> pd.DataFrame:
    if not seasons:
        return pd.DataFrame(columns=["season", "week", "homeTeam", "awayTeam", "spread", "neutralSite"])
    season_list = ",".join(str(s) for s in seasons)
    df = con.execute(f"""
        SELECT season, week, homeTeam, awayTeam, spread, neutralSite
        FROM stg.games
        WHERE season IN ({season_list}) AND seasonType = 'regular' AND spread IS NOT NULL
    """).fetchdf()
    if max_week is not None:
        df = df[df["week"] <= max_week]
    return df


def build_ratings(con: duckdb.DuckDBPyConnection, season: int, week: int | None, prior_seasons: int) -> pd.DataFrame:
    current_games = load_games(con, [season], max_week=week)
    prior_years = [season - i for i in range(1, prior_seasons + 1)]
    prior_games = load_games(con, prior_years)

    current_paired = spread_to_paired_rows(current_games)
    prior_paired = spread_to_paired_rows(prior_games)

    blend = shrink_toward_prior(
        fit_crossed_effects(current_paired, "margin"),
        fit_crossed_effects(prior_paired, "margin"),
    )

    games_played = current_paired.groupby("team").size().to_dict()
    rows = []
    for team, stats in blend.items():
        rows.append({
            "team": team,
            "games_played": games_played.get(team, 0),
            "power_rating": stats["estimate"],
            "power_se": stats["se"],
            "source": stats["source"],
        })
    ratings = pd.DataFrame(rows, columns=["team", "games_played", "power_rating", "power_se", "source"])
    return ratings.sort_values("power_rating", ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Spread-implied power ratings (v{VERSION})")
    parser.add_argument("--season", type=int, default=cfb_paths.current_season())
    parser.add_argument("--week", type=int, default=None, help="cutoff week; default = latest loaded")
    parser.add_argument("--prior-seasons", type=int, default=1, help="prior seasons pooled for the shrinkage prior")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    ratings = build_ratings(con, args.season, args.week, args.prior_seasons)
    ratings.insert(0, "rating_version", VERSION)

    out_dir = args.out or (cfb_paths.DATA_ROOT / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    week_tag = f"_wk{args.week}" if args.week else ""
    out_path = out_dir / f"spread_power_ratings_v{VERSION}_{args.season}{week_tag}.csv"
    ratings.to_csv(out_path, index=False)
    print(f"wrote {len(ratings)} teams -> {out_path}")


if __name__ == "__main__":
    main()
