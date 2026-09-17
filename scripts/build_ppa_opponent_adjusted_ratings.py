"""Opponent-adjusted team PPA ratings via crossed random-effects (mixed) models.

v1.0
- Stage 1: for a set of games, fit two crossed team/opponent random-effects
  models (statsmodels MixedLM via variance components) — one on offense PPA,
  one on defense PPA — separating a team's own ability from the strength of
  opponents it played. `defense_overall` is CFBD's raw sign (higher = more
  points-added allowed = worse defense); this script fits on its negation so
  higher is always better for both off_rating and def_rating.
- Stage 2: precision-weighted shrinkage of the current-season estimate toward
  a pooled prior-seasons estimate, using each fit's own BLUP standard errors.
  Early season (few games, wide current-season SE) leans on the prior; as
  games accumulate the current season dominates. No date logic is hardcoded —
  rerun weekly against the latest warehouse snapshot.

Usage:
    python scripts/build_ppa_opponent_adjusted_ratings.py --season 2026
    python scripts/build_ppa_opponent_adjusted_ratings.py --season 2026 --week 3 --prior-seasons 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cfb_paths

VERSION = "1.0"


def load_ppa_games(con: duckdb.DuckDBPyConnection, seasons: list[int], max_week: int | None = None) -> pd.DataFrame:
    if not seasons:
        return pd.DataFrame(columns=["season", "week", "team", "opponent", "offense_overall", "defense_overall", "is_home"])
    season_list = ",".join(str(s) for s in seasons)
    df = con.execute(f"""
        SELECT p.season, p.week, p.team, p.opponent, p.offense_overall, p.defense_overall,
               (p.team = g.homeTeam AND NOT COALESCE(g.neutralSite, FALSE)) AS is_home
        FROM stg.ppa_games p
        JOIN stg.games g USING (gameId)
        WHERE p.season IN ({season_list}) AND p.seasonType = 'regular'
    """).fetchdf()
    if max_week is not None:
        df = df[df["week"] <= max_week]
    return df


def fit_crossed_effects(df: pd.DataFrame, response: str) -> dict[str, dict[str, float]]:
    """Crossed team/opponent random effects on `response`. Returns {team: {estimate, se}}."""
    data = df.dropna(subset=[response, "is_home"]).copy()
    if data["team"].nunique() < 2 or len(data) < 10:
        return {}
    data["grp"] = 1
    model = sm.MixedLM.from_formula(
        f"{response} ~ is_home",
        groups="grp",
        vc_formula={"team": "0 + C(team)", "opponent": "0 + C(opponent)"},
        data=data,
    )
    result = model.fit(reml=True)
    re = result.random_effects[1]
    cov = result.random_effects_cov[1]
    se = pd.Series(np.sqrt(np.diag(cov)), index=cov.index)

    prefix = "team[C(team)["
    suffix = "]]"
    ratings: dict[str, dict[str, float]] = {}
    for key, value in re.items():
        if key.startswith(prefix) and key.endswith(suffix):
            team = key[len(prefix):-len(suffix)]
            ratings[team] = {"estimate": float(value), "se": float(se[key])}
    return ratings


def shrink_toward_prior(current: dict, prior: dict) -> dict[str, dict]:
    """Precision-weighted blend of current-season and prior-seasons estimates."""
    blended: dict[str, dict] = {}
    for team in sorted(set(current) | set(prior)):
        cur, pri = current.get(team), prior.get(team)
        if cur is None and pri is None:
            continue
        if cur is None:
            blended[team] = {"estimate": pri["estimate"], "se": pri["se"], "source": "prior_only"}
            continue
        if pri is None:
            blended[team] = {"estimate": cur["estimate"], "se": cur["se"], "source": "current_only"}
            continue
        prec_cur = 1.0 / cur["se"] ** 2
        prec_pri = 1.0 / pri["se"] ** 2
        estimate = (prec_cur * cur["estimate"] + prec_pri * pri["estimate"]) / (prec_cur + prec_pri)
        se = (1.0 / (prec_cur + prec_pri)) ** 0.5
        blended[team] = {
            "estimate": estimate, "se": se, "source": "blended",
            "current_estimate": cur["estimate"], "current_se": cur["se"],
            "prior_estimate": pri["estimate"], "prior_se": pri["se"],
        }
    return blended


def build_ratings(con: duckdb.DuckDBPyConnection, season: int, week: int | None, prior_seasons: int) -> pd.DataFrame:
    current_df = load_ppa_games(con, [season], max_week=week)
    current_df = current_df.assign(defense_adj=-current_df["defense_overall"])
    prior_years = [season - i for i in range(1, prior_seasons + 1)]
    prior_df = load_ppa_games(con, prior_years)
    prior_df = prior_df.assign(defense_adj=-prior_df["defense_overall"])

    off_blend = shrink_toward_prior(
        fit_crossed_effects(current_df, "offense_overall"),
        fit_crossed_effects(prior_df, "offense_overall"),
    )
    def_blend = shrink_toward_prior(
        fit_crossed_effects(current_df, "defense_adj"),
        fit_crossed_effects(prior_df, "defense_adj"),
    )

    games_played = current_df.groupby("team").size().to_dict()
    rows = []
    for team in sorted(set(off_blend) | set(def_blend)):
        o, d = off_blend.get(team, {}), def_blend.get(team, {})
        rows.append({
            "team": team,
            "games_played": games_played.get(team, 0),
            "off_rating": o.get("estimate"),
            "off_se": o.get("se"),
            "off_source": o.get("source"),
            "def_rating": d.get("estimate"),
            "def_se": d.get("se"),
            "def_source": d.get("source"),
        })
    ratings = pd.DataFrame(rows)
    ratings["overall_rating"] = ratings["off_rating"] + ratings["def_rating"]
    return ratings.sort_values("overall_rating", ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Opponent-adjusted PPA ratings (v{VERSION})")
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
    out_path = out_dir / f"ppa_ratings_v{VERSION}_{args.season}{week_tag}.csv"
    ratings.to_csv(out_path, index=False)
    print(f"wrote {len(ratings)} teams -> {out_path}")


if __name__ == "__main__":
    main()
