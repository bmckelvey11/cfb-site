"""Team pace stats from play-by-play clock deltas.

Pace here is *tempo*: game-clock seconds from the snap of a clock-running play to the
next snap in the same drive. Only a rush that is not a first down and not a touchdown
starts a pair, so the clock ran between the two snaps in every season -- the 2023 rule
that stopped first downs from stopping the clock does not touch these pairs. The delta is
play duration plus huddle-to-snap time; play duration is roughly constant across teams,
so the differences between teams are tempo.

CFBD's per-play clock is stale in whole games: in 2015-2023, most FBS games repeat the
clock across most consecutive snaps. Only games with `core.fact_game_clock_quality.clock_ok`
are kept. Wallclock (2018+) is stale in the same games through 2024 and is not used; from
2025 it covers games the clock misses (v2 path).

Stats per team-season (lower seconds = faster):
  tempo_s        median neutral seconds per snap, offense
  hurry_rate     share of neutral snaps inside that season's fastest league quartile
  trail_delta_s  median seconds when trailing by 9+ minus tempo_s (negative = speeds up)
  tempo_faced_s  median neutral seconds of opponents' snaps against this defense

Writes PROCESSED/pace/{pace_team_game.csv, pace_team_season.csv} and prints split-half
and year-over-year reliability and correlation with plays and possessions per game.

    python -m scripts.pace_stats
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))  # so `py scripts/pace_stats.py` finds cfb_paths

from cfb_system_maker.duckdb_core import SCRIMMAGE_PLAY_TYPES as SCRIMMAGE  # noqa: E402

MIN_NEUTRAL = 30  # pairs a team-season needs before a neutral stat is reported
MIN_TRAIL = 15    # pairs a team-season needs before trail_delta_s is reported

PAIRS_SQL = f"""
with fbs as (
  select g.gameId from stg.games g
  join core.fact_game_clock_quality q on q.game_id = g.gameId and q.clock_ok
  where g.homeClassification = 'fbs' and g.awayClassification = 'fbs'
    and g.seasonType = 'regular'
),
p as (
  select pl.gameId, pl.season, pl.week, pl.offense, pl.defense, pl.playType,
         pl.period, pl.yardsGained, pl.distance,
         cast(pl.offenseScore as int) - cast(pl.defenseScore as int) as margin,
         cast(pl.clock_minutes * 60 + pl.clock_seconds as int) as secs_left,
         lead(pl.playType) over w as nxt_type,
         lead(pl.offense)  over w as nxt_offense,
         lead(pl.period)   over w as nxt_period,
         lead(cast(pl.clock_minutes * 60 + pl.clock_seconds as int)) over w as nxt_secs
  from stg.plays pl join fbs using (gameId)
  window w as (partition by pl.driveId order by pl.playNumber, pl.playId)
)
select gameId as game_id, season, week, offense, defense, period, secs_left, margin,
       yardsGained >= distance as first_down,
       secs_left - nxt_secs as dclk
from p
where playType = 'Rush' and period <= 4
  and nxt_offense = offense and nxt_period = period
  and nxt_type in {SCRIMMAGE}
"""

VOLUME_SQL = f"""
with fbs as (
  select gameId, season, week from stg.games
  where homeClassification = 'fbs' and awayClassification = 'fbs'
    and seasonType = 'regular'
),
plays as (
  select fbs.season, fbs.week, gameId as game_id, offense, count(*) as plays
  from stg.plays join fbs using (gameId)
  where playType in {SCRIMMAGE} and period <= 4
  group by all
),
poss as (
  select game_id, offense, count(*) as possessions
  from core.fact_drive_postgame
  where start_period between 1 and 4 and game_id in (select gameId from fbs)
  group by 1, 2
)
select * from plays join poss using (game_id, offense)
"""


def load_pairs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Post-rush snap pairs in clean-clock games, clock-running rushes only."""
    p = con.execute(PAIRS_SQL).df()
    return p[~p["first_down"]].reset_index(drop=True)


def late_half(p: pd.DataFrame) -> pd.Series:
    """Final two minutes of Q2 or Q4: two-minute drill, kneels, clock management."""
    return p["period"].isin([2, 4]) & (p["secs_left"] <= 120)


def neutral_mask(p: pd.DataFrame) -> pd.Series:
    """Snaps where neither team's scoreboard state is forcing its tempo."""
    # TODO(human): define the neutral game state. Columns: period (1-4), secs_left
    # (seconds left in the period at the rush snap), margin (offense minus defense).
    # Provisional rule below so the script runs; replace it.
    return (p["period"] <= 3) & (p["margin"].abs() <= 14) & ~late_half(p)


def trailing_mask(p: pd.DataFrame) -> pd.Series:
    return (p["margin"] <= -9) & ~late_half(p)


def season_stats(p: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, team). Stats with too few pairs are NaN."""
    neu, trl = p[neutral_mask(p)], p[trailing_mask(p)]
    fast = neu.groupby("season")["dclk"].transform(lambda s: s.quantile(0.25))
    neu = neu.assign(hurry=neu["dclk"] <= fast)
    off, keys = neu.groupby(["season", "offense"]), ["season", "offense"]
    out = pd.DataFrame({
        "tempo_s": off["dclk"].median(),
        "hurry_rate": off["hurry"].mean(),
        "n_neutral": off.size(),
        "trail_s": trl.groupby(keys)["dclk"].median(),
        "n_trail": trl.groupby(keys).size(),
    })
    faced = neu.groupby(["season", "defense"])["dclk"].agg(["median", "size"])
    faced.index.names = keys
    out = out.join(faced.rename(columns={"median": "tempo_faced_s", "size": "n_faced"}),
                   how="outer")
    out.index.names = ["season", "team"]
    out["trail_delta_s"] = (out.pop("trail_s") - out["tempo_s"]).where(out["n_trail"] >= MIN_TRAIL)
    out.loc[out["n_neutral"] < MIN_NEUTRAL, ["tempo_s", "hurry_rate"]] = np.nan
    out.loc[out["n_faced"] < MIN_NEUTRAL, "tempo_faced_s"] = np.nan
    return out


def team_game(p: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """Per team-game neutral tempo, for as-of (shift-1 expanding) features downstream."""
    neu = p[neutral_mask(p)]
    g = (neu.groupby(["season", "week", "game_id", "offense"])["dclk"]
         .agg(tempo_s="median", n_neutral="size").reset_index())
    return volume.merge(g, on=["season", "week", "game_id", "offense"], how="left")


STATS = ["tempo_s", "hurry_rate", "trail_delta_s", "tempo_faced_s"]


def reliability(p: pd.DataFrame, season: pd.DataFrame) -> pd.DataFrame:
    """Split-half r (odd vs even games), Spearman-Brown full-season r, year-over-year r."""
    order = p.groupby(["season", "offense"])["week"].rank(method="dense").astype(int)
    halves = [season_stats(p[order % 2 == k]) for k in (0, 1)]
    nxt = season.reset_index().assign(season=lambda d: d["season"] - 1).set_index(["season", "team"])
    rows = {}
    for s in STATS:
        a, b = halves[0][s].align(halves[1][s], join="inner")
        r = a.corr(b)
        cur, fut = season[s].align(nxt[s], join="inner")
        rows[s] = {"split_half_r": r, "full_season_r": 2 * r / (1 + r),
                   "yoy_r": cur.corr(fut), "team_seasons": int(season[s].notna().sum())}
    return pd.DataFrame(rows).T


def main() -> None:
    from cfb_paths import DB_PATH, PROCESSED

    con = duckdb.connect(str(DB_PATH), read_only=True)
    p, volume = load_pairs(con), con.execute(VOLUME_SQL).df()
    season = season_stats(p)
    per_game = volume.groupby(["season", "offense"])[["plays", "possessions"]].mean()
    per_game.index.names = ["season", "team"]
    season = season.join(per_game)

    out = PROCESSED / "pace"
    out.mkdir(parents=True, exist_ok=True)
    team_game(p, volume).to_csv(out / "pace_team_game.csv", index=False)
    season.to_csv(out / "pace_team_season.csv")

    print(f"pairs {len(p):,} in {p['game_id'].nunique():,} clean-clock games")
    print(p[neutral_mask(p)].groupby("season")["dclk"].median().rename("league_tempo_s").to_string())
    print("\nreliability\n", reliability(p, season).round(3).to_string())
    # Within-season correlation, so the league-wide tempo drift does not inflate it.
    z = season.groupby(level="season").transform(lambda c: (c - c.mean()) / c.std())
    print("\ncorrelation with volume (within-season z)\n",
          z[STATS].corrwith(z["plays"]).rename("plays").to_frame()
          .join(z[STATS].corrwith(z["possessions"]).rename("possessions")).round(3).to_string())
    # Schedule check: tempo faced vs the pair-weighted own tempo of the offenses faced.
    neu = p[neutral_mask(p)].merge(season["tempo_s"].rename("opp_tempo"),
                                   left_on=["season", "offense"], right_index=True)
    sched = neu.groupby(["season", "defense"])["opp_tempo"].mean().rename_axis(["season", "team"])
    zs = z[["tempo_faced_s"]].join(sched.groupby(level="season").transform(
        lambda c: (c - c.mean()) / c.std())).dropna()
    print(f"\nr(tempo_faced_s, opponents' own tempo_s), within-season z: "
          f"{zs.corr().iloc[0, 1]:.3f} (n {len(zs)})")

    rated = season["tempo_s"].groupby(level="season").count()
    last = rated[rated >= 100].index.max()  # the live season rates too few teams early on
    latest = season.loc[last].dropna(subset=["tempo_s"])
    print(f"\n{last}: {len(latest)} teams rated")
    print("\nfastest\n", latest.nsmallest(10, "tempo_s")[STATS + ["n_neutral"]].round(2).to_string())
    print("\nslowest\n", latest.nlargest(10, "tempo_s")[STATS + ["n_neutral"]].round(2).to_string())


if __name__ == "__main__":
    main()
