"""Where in a game each type of team scores its points.

Splits regulation quarter-by-quarter scoring (stg.game_team__line_scores, FBS vs
FBS) by two *prior-season* team attributes, so the bucket label is never built
from the games being measured:

  tempo     -- prior-season offensive plays per game, quartiles
  offense   -- prior-season SP+ offensive rating, quartiles

Shares are ratios of pooled totals (sum of points in Qk over sum of all points
in the bucket), not averages of per-game shares -- a team held to 0 has no
defined per-game share, and a 3-point game should not weigh as much as a 45.

Writes CSVs to docs/assets/ and prints every number in the write-up.
Usage: python scripts/analyze_scoring_by_team_type.py [--start 2015] [--end 2025]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DB_PATH  # noqa: E402

BASE = """
create or replace temp view games as
  select "gameId"::BIGINT as gid, season
  from stg.game
  where season between {lo} and {hi}
    and "homeClassification" = 'fbs' and "awayClassification" = 'fbs';

create or replace temp view qtr as
  select g.season, l."teamId"::BIGINT as tid, g.gid,
         l."lineScores_idx" as q, l."lineScores"::BIGINT as pts
  from stg.game_team__line_scores l
  join games g on g.gid = l."gameId"::BIGINT
  where l."lineScores_idx" between 1 and 4;

-- prior-season attributes, keyed on teamId; advanced stats reach it by name
create or replace temp view team_year as
  select distinct year, team, "teamId"::BIGINT as tid from stg.ratings;

create or replace temp view prior as
  select ty.tid,
         ty.year + 1 as season,
         r."spOffense" as sp_offense,
         a.offense_plays::DOUBLE / nullif(gp.games, 0) as plays_per_game
  from team_year ty
  join stg.ratings r on r."teamId"::BIGINT = ty.tid and r.year = ty.year
  left join stg.advanced_season_stats a on a.team = ty.team and a.season = ty.year
  left join (
    select season, "teamId"::BIGINT as tid, count(distinct "gameId") as games
    from stg.game_team__line_scores
    where "lineScores_idx" = 1
    group by all
  ) gp on gp.tid = ty.tid and gp.season = ty.year;

create or replace temp view tagged as
  select q.*, p.sp_offense, p.plays_per_game
  from qtr q left join prior p on p.tid = q.tid and p.season = q.season;
"""

# quartile cut points are computed per season so a bucket means the same thing
# in 2015 and 2025 despite the scoring drift
BUCKET = """
create or replace temp view bucketed as
  with cuts as (
    select season,
           quantile_cont(sp_offense, [0.25, 0.5, 0.75]) as sp_q,
           quantile_cont(plays_per_game, [0.25, 0.5, 0.75]) as tempo_q
    from (select distinct season, tid, sp_offense, plays_per_game from tagged)
    group by season
  )
  select t.*,
    case when t.sp_offense is null then null
         when t.sp_offense >= c.sp_q[3] then 'Q4 best offense'
         when t.sp_offense >= c.sp_q[2] then 'Q3'
         when t.sp_offense >= c.sp_q[1] then 'Q2'
         else 'Q1 worst offense' end as off_bucket,
    case when t.plays_per_game is null then null
         when t.plays_per_game >= c.tempo_q[3] then 'fastest 25%'
         when t.plays_per_game >= c.tempo_q[2] then 'fast-mid'
         when t.plays_per_game >= c.tempo_q[1] then 'slow-mid'
         else 'slowest 25%' end as tempo_bucket
  from tagged t join cuts c using (season);
"""

SPLIT = """
select {col} as bucket,
       count(distinct gid || '-' || tid) as team_games,
       sum(pts) as pts,
       sum(pts) filter (where q = 1)::DOUBLE / count(distinct gid || '-' || tid) as q1_pg,
       sum(pts) filter (where q = 2)::DOUBLE / count(distinct gid || '-' || tid) as q2_pg,
       sum(pts) filter (where q = 3)::DOUBLE / count(distinct gid || '-' || tid) as q3_pg,
       sum(pts) filter (where q = 4)::DOUBLE / count(distinct gid || '-' || tid) as q4_pg,
       100.0 * sum(pts) filter (where q = 1) / sum(pts) as q1_share,
       100.0 * sum(pts) filter (where q = 2) / sum(pts) as q2_share,
       100.0 * sum(pts) filter (where q = 3) / sum(pts) as q3_share,
       100.0 * sum(pts) filter (where q = 4) / sum(pts) as q4_share,
       100.0 * sum(pts) filter (where q <= 2) / sum(pts) as h1_share,
       100.0 * sum(pts) filter (where q >= 3) / sum(pts) as h2_share
from bucketed
where {col} is not null
group by all order by all
"""

OFF_ORDER = ["Q4 best offense", "Q3", "Q2", "Q1 worst offense"]
TEMPO_ORDER = ["fastest 25%", "fast-mid", "slow-mid", "slowest 25%"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default="docs/assets")
    a = ap.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(BASE.format(lo=a.start, hi=a.end))
    con.execute(BUCKET)

    out = REPO / a.out
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.start}-{a.end}"

    cov = con.execute(
        "select season, count(distinct tid) teams, "
        "count(distinct tid) filter (where sp_offense is not null) sp, "
        "count(distinct tid) filter (where plays_per_game is not null) tempo "
        "from tagged group by 1 order by 1"
    ).df()
    print("prior-season attribute coverage (teams per season):")
    print(cov.to_string(index=False))

    overall = con.execute(
        "select 100.0*sum(pts) filter (where q<=2)/sum(pts) h1, "
        "sum(pts)::DOUBLE/count(distinct gid||'-'||tid) ppg, "
        "count(distinct gid) games from bucketed"
    ).fetchone()
    print(f"\nall teams: H1 share {overall[0]:.2f}%  "
          f"{overall[1]:.2f} pts/team-game  {overall[2]:,} games")

    shares = con.execute(
        "select " + ", ".join(
            f"100.0*sum(pts) filter (where q={k})/sum(pts) q{k}" for k in (1, 2, 3, 4)
        ) + " from bucketed"
    ).df()
    print("all teams, share of own points by quarter:")
    print(shares.round(2).to_string(index=False))

    for col, order, slug in (("off_bucket", OFF_ORDER, "offense"),
                             ("tempo_bucket", TEMPO_ORDER, "tempo")):
        df = con.execute(SPLIT.format(col=col)).df()
        df = df.set_index("bucket").reindex(order).reset_index()
        df.to_csv(out / f"scoring-by-team-type-{slug}-{tag}.csv", index=False)
        print(f"\n[{slug}]")
        print(df.round(3).to_string(index=False))

    # does the headline contrast reproduce season by season, or is it pooling?
    gap = con.execute(
        "select season, "
        "max(h1) filter (where off_bucket = 'Q4 best offense') "
        "- max(h1) filter (where off_bucket = 'Q1 worst offense') as h1_gap "
        "from (select season, off_bucket, "
        "      100.0*sum(pts) filter (where q<=2)/sum(pts) as h1 "
        "      from bucketed where off_bucket is not null group by 1, 2) "
        "group by 1 order by 1"
    ).df()
    gap.to_csv(out / f"scoring-by-team-type-offense-h1gap-{tag}.csv", index=False)
    pos = int((gap.h1_gap > 0).sum())
    print(f"\nbest-minus-worst offense H1 share gap, per season "
          f"(positive in {pos}/{len(gap)}):")
    print(gap.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
