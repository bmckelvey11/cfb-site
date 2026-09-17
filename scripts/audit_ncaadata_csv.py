"""Audit what an external CFBD game export adds over the warehouse.

Written for C:/Users/mckel/OneDrive/Betting/NCAAData_1980-2020.csv (2026-09-17).
The file carries no betting lines; this script measures which of its columns
hold values the warehouse does not already have.

    python scripts/audit_ncaadata_csv.py [path-to-csv]
"""
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

CSV = sys.argv[1] if len(sys.argv) > 1 else r"C:/Users/mckel/OneDrive/Betting/NCAAData_1980-2020.csv"


def main() -> None:
    con = duckdb.connect(str(DATA_ROOT / "cfb.duckdb"), read_only=True)
    con.execute(
        "create or replace temp view csv as select "
        "try_cast(id as bigint) gid, try_cast(season as int) season, * exclude(id, season) "
        f"from read_csv('{CSV}', header=true, all_varchar=true)"
    )

    def q(label, sql):
        print(f"{label}: {con.execute(sql).fetchone()}")

    q("rows / season span", "select count(*), min(season), max(season) from csv")
    q(
        "id match (total, in fact_game_historical, in fact_game)",
        """select count(*),
             sum((h.game_id is not null)::int),
             sum((g.game_id is not null)::int)
           from csv x
           left join core.fact_game_historical h on h.game_id = x.gid
           left join core.fact_game g on g.game_id = x.gid""",
    )
    q(
        "quarter scores the warehouse lacks",
        """select count(*) from csv x
           where x.home_line_scores not in ('[]', '')
             and not exists (select 1 from stg.games__home_line_scores s where s.gameId = x.gid)
             and not exists (select 1 from stg.game__home_line_scores s where s.gameId = x.gid)""",
    )
    q(
        "attendance the warehouse lacks (pre-2012)",
        """select count(*) from csv x
           join core.fact_game_historical h on h.game_id = x.gid
           where x.attendance is not null and x.attendance <> '' and h.attendance is null""",
    )
    q(
        "excitement index the warehouse lacks",
        """select count(*) from csv x
           where x.excitement_index is not null and x.excitement_index <> ''
             and not exists (select 1 from stg.games s where s.gameId = x.gid and s.excitementIndex is not null)
             and not exists (select 1 from stg.game s where s.gameId = x.gid and s.excitement is not null)""",
    )
    q(
        "postgame win prob the warehouse lacks",
        """select count(*) from csv x
           where x.home_post_win_prob is not null and x.home_post_win_prob <> ''
             and not exists (select 1 from stg.games s where s.gameId = x.gid and s.homePostgameWinProbability is not null)
             and not exists (select 1 from stg.game s where s.gameId = x.gid and s.homePostgameWinProb is not null)""",
    )
    q(
        "games with a line, by era",
        """select sum((season < 2013)::int), sum((season >= 2013)::int)
           from core.fact_game g join core.fact_game_line l using(game_id)""",
    )


if __name__ == "__main__":
    main()
