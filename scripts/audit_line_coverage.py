"""What betting-line coverage the warehouse actually has, by season and by book.

Row counts do not answer "can I model this season". Three things do, and they
arrived at different times:

* a **closing** line (grades a bet),
* an **opening** line (the other end of the movement the spread model predicts),
* **tick** history (when the move happened, so CLV has a timestamp).

This reports all three per season, plus the book panel, because the panel is not
stable: the long-history books (`consensus`, `teamrankings`, `numberfire`) stop
after 2023 and the sharp books (`circa`, `fanduel`, `pinnacle`) start in 2024,
so a backtest spanning that cut is not measuring one market.

Read-only. Exits 0 always -- it reports, it does not decide.

Usage: python scripts/audit_line_coverage.py [--json OUT] [--min-season 2013]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402

# A season needs an opener AND a close to measure movement; ticks to time it.
SEASON_SQL = """
SELECT g.season,
       count(DISTINCT g.game_id)                                        AS games,
       count(DISTINCT l.game_id)                                        AS lined,
       count(DISTINCT CASE WHEN l.spread_close IS NOT NULL
                           THEN l.game_id END)                          AS spread_close,
       count(DISTINCT CASE WHEN l.spread_open IS NOT NULL
                           THEN l.game_id END)                          AS spread_open,
       count(DISTINCT CASE WHEN l.total_close IS NOT NULL
                           THEN l.game_id END)                          AS total_close,
       count(DISTINCT CASE WHEN l.moneyline_home IS NOT NULL
                           THEN l.game_id END)                          AS moneyline,
       count(DISTINCT l.provider_key)                                   AS books
FROM core.fact_game AS g
LEFT JOIN core.fact_game_line AS l ON l.game_id = g.game_id
GROUP BY 1 ORDER BY 1
"""

BOOK_SQL = """
SELECT l.provider_key,
       min(g.season) AS first_season,
       max(g.season) AS last_season,
       count(DISTINCT g.season) AS seasons,
       count(*) AS rows
FROM core.fact_game_line AS l
JOIN core.fact_game AS g ON g.game_id = l.game_id
GROUP BY 1 ORDER BY 2, 3 DESC
"""

# Action Network: the scoreboard reaches back years further than the odds do.
AN_SQL = """
SELECT s.season,
       count(DISTINCT s.event_id)                                   AS scoreboard_events,
       count(DISTINCT m.event_id)                                   AS market_events,
       count(DISTINCT h.event_id)                                   AS history_events,
       count(DISTINCT t.event_id)                                   AS tick_events,
       coalesce(sum(t.ticks), 0)                                    AS ticks
FROM stg.an_scoreboard AS s
LEFT JOIN (SELECT DISTINCT event_id FROM stg.an_market)  AS m ON m.event_id = s.event_id
LEFT JOIN (SELECT DISTINCT event_id FROM stg.an_history) AS h ON h.event_id = s.event_id
LEFT JOIN (SELECT event_id, count(*) AS ticks
           FROM stg.an_history_tick GROUP BY 1)          AS t ON t.event_id = s.event_id
GROUP BY 1 ORDER BY 1
"""

ODDS_SQL = """
SELECT min(pulled_at)::DATE AS first_pull,
       max(pulled_at)::DATE AS last_pull,
       count(DISTINCT book)     AS books,
       count(DISTINCT game_id)  AS games,
       count(*)                 AS rows
FROM core.fact_game_odds
"""

# Games CFBD lists with a lines payload that is an empty array -- an upstream
# floor, not a load failure. This is the whole of the 2012 hole.
EMPTY_SQL = """
SELECT season,
       count(*) AS games,
       sum(CASE WHEN json_array_length(json_extract(payload, '$.lines')) = 0
                THEN 1 ELSE 0 END) AS empty_lines
FROM raw.lines GROUP BY 1 ORDER BY 1
"""


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    ap.add_argument("--min-season", type=int, default=0)
    args = ap.parse_args()

    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    try:
        seasons = [r for r in _rows(con, SEASON_SQL) if r["season"] >= args.min_season]
        books = _rows(con, BOOK_SQL)
        an = [r for r in _rows(con, AN_SQL) if r["season"] >= args.min_season]
        odds = _rows(con, ODDS_SQL)[0]
        empty = [r for r in _rows(con, EMPTY_SQL) if r["empty_lines"]]
    finally:
        con.close()

    print("=" * 78)
    print("CFBD line coverage per season  (distinct games, not rows)")
    print("=" * 78)
    print(f"{'season':>6} {'games':>6} {'lined':>6} {'spr_cl':>7} {'spr_op':>7} "
          f"{'tot_cl':>7} {'ml':>6} {'books':>5}  movement?")
    for r in seasons:
        # An opener plus a close is the minimum to measure a line move.
        movement = "open+close" if r["spread_open"] else (
            "close only" if r["spread_close"] else "NO LINES")
        print(f"{r['season']:>6} {r['games']:>6} {r['lined']:>6} "
              f"{r['spread_close']:>7} {r['spread_open']:>7} {r['total_close']:>7} "
              f"{r['moneyline']:>6} {r['books']:>5}  {movement}")

    print()
    print("=" * 78)
    print("Book panel -- note where the long-history books stop and the sharps start")
    print("=" * 78)
    print(f"{'book':<30} {'first':>5} {'last':>5} {'yrs':>4} {'rows':>8}")
    for b in books:
        print(f"{b['provider_key']:<30} {b['first_season']:>5} {b['last_season']:>5} "
              f"{b['seasons']:>4} {b['rows']:>8}")

    print()
    print("=" * 78)
    print("Action Network -- the scoreboard reaches back further than the odds")
    print("=" * 78)
    print(f"{'season':>6} {'events':>7} {'market':>7} {'1H/1Q':>7} {'tick_ev':>8} {'ticks':>9}")
    for r in an:
        print(f"{r['season']:>6} {r['scoreboard_events']:>7} {r['market_events']:>7} "
              f"{r['history_events']:>7} {r['tick_events']:>8} {r['ticks']:>9,}")

    print()
    print("=" * 78)
    print("the-odds-api live tape")
    print("=" * 78)
    print(f"  {odds['first_pull']} -> {odds['last_pull']}  |  {odds['books']} books, "
          f"{odds['games']} games, {odds['rows']:,} rows")

    if empty:
        print()
        print("Seasons where CFBD returns games with an EMPTY lines[] array")
        print("(an upstream floor -- these games can never reach core.fact_game_line)")
        for r in empty:
            print(f"  {r['season']}: {r['empty_lines']:>4} of {r['games']:>4} games")

    if args.json:
        args.json.write_text(
            json.dumps({"seasons": seasons, "books": books, "action_network": an,
                        "odds_api": odds, "empty_lines": empty},
                       indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
