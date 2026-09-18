"""Points scored per game-minute, bucketed by minute within each quarter.

Points are the change in total score from the previous play (score fields are
post-play), clamped to 1..8. Outputs a CSV and a PNG to docs/assets/.
"""
import argparse
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cfb_paths import DB_PATH  # noqa: E402

SQL = """
with p as (
  select gameId, season, period, clock_minutes, driveNumber, playNumber,
         (offenseScore + defenseScore)::BIGINT as tot
  from stg.plays
  where season between ? and ? and period between 1 and 4
       and clock_minutes between 0 and 14
),
d as (
  select *, tot - lag(tot) over (
      partition by gameId order by period, driveNumber, playNumber) as pts
  from p
),
g as (select count(distinct gameId) as games from d)
select period,
       15 - clock_minutes as minute,       -- 1 = first minute of the quarter
       sum(case when pts between 1 and 8 then pts else 0 end)::double
         / any_value(g.games) as pts_per_game
from d, g
group by all
order by all
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", default="docs/assets")
    args = ap.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(SQL, [args.start, args.end]).df()
    games = con.execute(
        "select count(distinct gameId) from stg.plays "
        "where season between ? and ? and period between 1 and 4",
        [args.start, args.end],
    ).fetchone()[0]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    csv = out / f"scoring-by-minute-{args.start}-{args.end}.csv"
    png = out / f"scoring-by-minute-{args.start}-{args.end}.png"
    df.to_csv(csv, index=False)

    fig, ax = plt.subplots(figsize=(11, 5))
    x = (df["period"] - 1) * 15 + df["minute"]
    ax.bar(x, df["pts_per_game"], width=0.85, color="#2b6cb0")
    for q in (15.5, 30.5, 45.5):
        ax.axvline(q, color="#999", lw=1, ls="--")
    ax.set_xticks([1, 15, 16, 30, 31, 45, 46, 60])
    ax.set_xticklabels(["Q1:1", "Q1:15", "Q2:1", "Q2:15",
                        "Q3:1", "Q3:15", "Q4:1", "Q4:15"])
    ax.set_xlabel("minute elapsed within quarter")
    ax.set_ylabel("points per game")
    ax.set_title(f"CFB scoring by minute of quarter, {args.start}-{args.end} "
                 f"({games:,} games, regulation only)")
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(png, dpi=140)
    print(f"games={games:,} total_pts_per_game={df['pts_per_game'].sum():.2f}")
    print(csv)
    print(png)


if __name__ == "__main__":
    main()
