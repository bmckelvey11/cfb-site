"""Current Glicko-margin ratings: the frozen v1 picks replayed through the latest final scores.

    python -m scripts.glicko_ratings_table --season 2026

Descriptive only (spec status, 2026-09-24): a power rating and its RD, never an edge on a
line. Writes data/processed/ratings/glicko_ratings_<season>.csv with one row per team that has
played this season: rank within its subdivision, rating in points above an average FBS team
on a neutral field, RD, games played, and the kickoff of the latest result included.
"""
from __future__ import annotations

import argparse
import math

import pandas as pd

from scripts.glicko_ratings import FBS, FROZEN_V1, VERSION, GlickoMargin, events, run
from scripts.glicko_ratings_eval import fcs_seed, load


def ratings_table(m: GlickoMargin, season: int) -> pd.DataFrame:
    """Teams that played `season`, centred on this season's FBS mean, ranked within subdivision.

    ponytail: RD is as of each team's last game; an idle week would add tau^2 (0.56 points^2).
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

    g, drops = load(DATA_ROOT, args.season, [])
    m = GlickoMargin(**FROZEN_V1, m0=fcs_seed(g))
    run(m, g, events(g))
    t = ratings_table(m, args.season)
    as_of = g.loc[g["season"] == args.season, "kickoff"].max()

    out = PROCESSED / "ratings" / f"glicko_ratings_{args.season}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    t.round({"rating": 1, "rd": 1}).assign(as_of=as_of.isoformat(), version=VERSION).to_csv(
        out, index=False)

    print(t[t["subdivision"] == FBS].head(25).round(1).to_string(index=False))
    unplayed = drops["no_final_score_by_season"].get(args.season, 0)
    print(f"{len(t)} teams; results through {as_of:%Y-%m-%d}; {unplayed} lined games not yet "
          f"played were left out.\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
