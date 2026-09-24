"""Current Glicko-margin ratings: the frozen P1 pool pick replayed through the latest scores.

    python -m scripts.glicko_ratings_table --season 2026

Descriptive only (spec status, docs/superpowers/specs/2026-09-24-glicko-pool-design.md): a
power rating and its RD, never an edge on a line. Uses rung P1 (glicko-pool-2026-09-24.md,
ADOPTED), which rates every completed Division I game from the raw CFBD files -- not just
games.csv's lined ones -- and pulls each team toward its conference mean at the offseason.

Writes data/processed/ratings/glicko_ratings_<season>.csv with one row per team that has
played this season: rank within its subdivision, rating in points above an average FBS team
on a neutral field, RD, and games played (every completed D-I game, whether or not it had a
betting line).
"""
from __future__ import annotations

import argparse
import math

import pandas as pd

from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games
from scripts.glicko_ratings import FBS, FROZEN_P1, VERSION, GlickoMargin, events, run


def ratings_table(m: GlickoMargin, season: int) -> pd.DataFrame:
    """Teams that played `season`, centred on this season's FBS mean, ranked within subdivision.

    ponytail: RD is as of each team's last game; an idle week would add tau^2 (2.25 points^2).
    """
    teams = [k for k in m.r if m.last.get(k) == season]
    t = pd.DataFrame({"team": teams, "subdivision": [m.div[k] for k in teams],
                      "rating": [m.r[k] for k in teams],
                      "rd": [math.sqrt(m.u2[k]) for k in teams],
                      "games": [m.n[k] for k in teams]})
    t["rating"] -= t.loc[t["subdivision"] == FBS, "rating"].mean()
    t["rank"] = t.groupby("subdivision")["rating"].rank(ascending=False, method="min").astype(int)
    cols = ["subdivision", "rank", "team", "rating", "rd", "games"]
    return t.sort_values(["subdivision", "rank"])[cols].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True)
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    g, drops = load_pool_games(DATA_ROOT, args.season, [])
    m = GlickoMargin(**FROZEN_P1, m0=fcs_seed_pool(g))
    run(m, g, events(g))
    t = ratings_table(m, args.season)
    as_of = g.loc[g["season"] == args.season, "kickoff"].max()

    out = PROCESSED / "ratings" / f"glicko_ratings_{args.season}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    body = t.round({"rating": 1, "rd": 1}).assign(as_of=as_of.isoformat(), version=f"P1/{VERSION}")
    try:
        body.to_csv(out, index=False)
    except PermissionError:
        # ponytail: the file is open elsewhere (e.g. Excel); write beside it instead of losing
        # the run. Rerun once the original is closed to replace it in place.
        alt = out.with_name(f"{out.stem}.new{out.suffix}")
        body.to_csv(alt, index=False)
        out = alt

    print(t[t["subdivision"] == FBS].head(25).round(1).to_string(index=False))
    unplayed = drops["unplayed_by_season"].get(args.season, 0)
    non_d1 = drops["non_d1_by_season"].get(args.season, 0)
    print(f"{len(t)} teams; results through {as_of:%Y-%m-%d}; {unplayed} games not yet "
          f"played and {non_d1} D-II/D-III/unlabelled games were left out.\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
