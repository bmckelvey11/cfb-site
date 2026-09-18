"""Scoring by minute of quarter, split by pre-play game state and by spread.

Unit of exposure is a game-minute cell (gameId, period, minute). Each cell is
assigned to one bucket by the state at its first play, so points-per-cell is
comparable across buckets and against the unconditional series computed the
same way.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cfb_paths import DB_PATH  # noqa: E402

BASE = """
with p as (
  select p.gameId, p.period, p.clock_minutes, p.driveNumber, p.playNumber,
         (p.offenseScore + p.defenseScore)::BIGINT as tot,
         case when p.offense = p.home
              then p.offenseScore::BIGINT - p.defenseScore::BIGINT
              else p.defenseScore::BIGINT - p.offenseScore::BIGINT end as home_margin,
         (p.offense = p.home) as off_is_home,
         abs(g.selected_spread) as spread
  from stg.plays p
  left join core.fact_game g on g.game_id = p.gameId::INTEGER
  where p.season between ? and ? and p.period between 1 and 4
    and p.clock_minutes between 0 and 14
),
d as (
  select *,
    tot - lag(tot) over w as pts,
    lag(home_margin) over w as home_margin_pre,
    row_number() over (
      partition by gameId, period, clock_minutes
      order by driveNumber, playNumber) as rn_in_cell
  from p
  window w as (partition by gameId order by period, driveNumber, playNumber)
),
obs as (
  select gameId, period, 15 - clock_minutes as minute,
         sum(case when pts between 1 and 8 then pts else 0 end) as pts,
         any_value(case when rn_in_cell = 1 then
             case when off_is_home then home_margin_pre else -home_margin_pre end
           end) as off_margin_obs
  from d
  group by all
),
games as (
  select distinct gameId, max(spread) as spread from p group by gameId
),
grid as (
  select g.gameId, g.spread, q.period, m.minute
  from games g
  cross join (select unnest([1,2,3,4]) as period) q
  cross join (select unnest(range(1,16)) as minute) m
),
e as (
  -- every game-minute of regulation, including minutes with no snap;
  -- state carried forward from the last observed play
  select grid.gameId, grid.period, grid.minute, grid.spread,
         coalesce(obs.pts, 0) as pts,
         last_value(obs.off_margin_obs ignore nulls) over (
           partition by grid.gameId order by grid.period, grid.minute
           rows between unbounded preceding and current row) as off_margin_pre
  from grid left join obs
    on obs.gameId = grid.gameId and obs.period = grid.period
       and obs.minute = grid.minute
)
"""

STATE_CASE = """
  case
    when off_margin_pre is null then null
    when off_margin_pre >= 15 then 'offense up 15+'
    when off_margin_pre >= 4  then 'offense up 4-14'
    when off_margin_pre >= -3 then 'within 3'
    when off_margin_pre >= -14 then 'offense down 4-14'
    else 'offense down 15+' end
"""
STATE_ORDER = ["offense up 15+", "offense up 4-14", "within 3",
               "offense down 4-14", "offense down 15+"]

SPREAD_CASE = """
  case
    when spread is null then null
    when spread <= 3 then 'spread 0-3'
    when spread <= 7 then 'spread 3.5-7'
    when spread <= 14 then 'spread 7.5-14'
    else 'spread 14.5+' end
"""
SPREAD_ORDER = ["spread 0-3", "spread 3.5-7", "spread 7.5-14", "spread 14.5+"]


def series(con, start, end, case_sql):
    sql = BASE + f"""
    select {case_sql} as bucket, period, minute,
           sum(pts)::double / count(*) as pts_per_cell,
           count(*) as cells
    from e
    where {'true' if case_sql == "'all'" else case_sql + ' is not null'}
    group by all order by all
    """
    return con.execute(sql, [start, end]).df()


def plot(df, order, title, path):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    for name in order:
        s = df[df.bucket == name].sort_values(["period", "minute"])
        x = (s["period"] - 1) * 15 + s["minute"]
        ax.plot(x, s["pts_per_cell"], lw=1.6, marker="o", ms=2.5, label=name)
    for q in (15.5, 30.5, 45.5):
        ax.axvline(q, color="#bbb", lw=1, ls="--")
    ax.set_xticks([1, 15, 16, 30, 31, 45, 46, 60])
    ax.set_xticklabels(["Q1:1", "Q1:15", "Q2:1", "Q2:15",
                        "Q3:1", "Q3:15", "Q4:1", "Q4:15"])
    ax.set_xlabel("minute elapsed within quarter")
    ax.set_ylabel("points per game-minute of exposure")
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=3)
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default="docs/assets")
    a = ap.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{a.start}-{a.end}"

    uncond = series(con, a.start, a.end, "'all'")
    uncond.to_csv(out / f"scoring-by-minute-cells-{tag}.csv", index=False)
    print("unconditional pts/cell overall: "
          f"{(uncond.pts_per_cell * uncond.cells).sum() / uncond.cells.sum():.3f}")
    print(f"cells={uncond.cells.sum():,}")

    for case, order, slug, title in (
        (STATE_CASE, STATE_ORDER, "state",
         f"Scoring by minute, by pre-play game state ({tag})"),
        (SPREAD_CASE, SPREAD_ORDER, "spread",
         f"Scoring by minute, by closing spread ({tag})"),
    ):
        df = series(con, a.start, a.end, case)
        df.to_csv(out / f"scoring-by-minute-{slug}-{tag}.csv", index=False)
        plot(df, order, title, out / f"scoring-by-minute-{slug}-{tag}.png")
        tot = df.groupby("bucket").apply(
            lambda s: (s.pts_per_cell * s.cells).sum() / s.cells.sum(),
            include_groups=False)
        print(f"\n[{slug}] pts per cell, pooled:")
        print(tot.reindex(order).round(3).to_string())
        print(df.groupby("bucket").cells.sum().reindex(order).to_string())


if __name__ == "__main__":
    main()
