"""How many full-game lines an Action Network in-game price would corrupt.

Action Network labels a live, in-game offering ``period = 'event'`` -- the same label
it puts on the pregame line. ``_backfill_gamelines`` pivots offerings with
``MAX(CASE WHEN market_type = ... THEN line END)`` because ``stg.an_history`` carries no
timestamp to take a *last* on, so before the ``is_live`` filter a live tick won the
full-game aggregate whenever it was the larger number -- and won outright on the games
whose only full-game row is live.

This reports, per book, how many ``(game, book)`` full-game totals and spreads differ
between a MAX over every offering and a MAX over the pregame ones. On a fixed warehouse
``changed`` is what the fix removed; on a stale one it is what is still wrong. It reads
``stg`` directly rather than ``core.fact_game_line`` so it answers the same question
whether or not the warehouse has been rebuilt since the fix landed.

Read-only. Exits 0 always -- it reports, it does not decide.

Usage: python scripts/audit_an_live_lines.py [--json OUT] [--top 15]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402

# The same event -> game join `_backfill_gamelines` makes, restated rather than imported:
# that function builds it inside one big CREATE TABLE and does not expose it.
MAP_SQL = """
CREATE OR REPLACE TEMP VIEW _map AS
SELECT sb.event_id, g.gameId AS game_id
FROM stg.an_scoreboard sb
JOIN stg.games g
  ON g.season = sb.season
 AND g.week = sb.week
 AND g.homeTeam = list_first(list_transform(list_filter(
       TRY_CAST(sb.teams AS JSON[]),
       lambda t: TRY_CAST(json_extract(t, '$.id') AS BIGINT) = sb.home_team_id),
       lambda t: json_extract_string(t, '$.location')))
 AND g.awayTeam = list_first(list_transform(list_filter(
       TRY_CAST(sb.teams AS JSON[]),
       lambda t: TRY_CAST(json_extract(t, '$.id') AS BIGINT) = sb.away_team_id),
       lambda t: json_extract_string(t, '$.location')))
"""

# Both AN inputs, normalised to the backfill's period vocabulary.
OFFERS_SQL = """
CREATE OR REPLACE TEMP VIEW _offers AS
SELECT m.game_id, a.book_id,
       CASE WHEN a.period IN ('event', 'game') THEN 'game' ELSE a.period END AS period,
       a.market_type, a.side, a.line, a.is_live
FROM stg.an_market a JOIN _map m USING (event_id)
UNION ALL
SELECT m.game_id, h.book_id,
       CASE WHEN h.period IN ('event', 'game') THEN 'game' ELSE h.period END,
       h.market_type, h.side, h.line, h.is_live
FROM stg.an_history h JOIN _map m USING (event_id)
"""

# `all` is the pre-fix aggregate, `pregame` the post-fix one. Written as one pass so the
# two can never be measured over different row sets.
PIVOT_SQL = """
CREATE OR REPLACE TEMP VIEW _pivot AS
SELECT game_id, book_id,
  max(CASE WHEN market_type = 'total' AND side IN ('over', 'under')
           THEN line END)                                        AS total_all,
  max(CASE WHEN market_type = 'total' AND side IN ('over', 'under')
           AND is_live IS NOT TRUE THEN line END)                AS total_pregame,
  max(CASE WHEN market_type = 'spread' AND side = 'home'
           THEN line END)                                        AS spread_all,
  max(CASE WHEN market_type = 'spread' AND side = 'home'
           AND is_live IS NOT TRUE THEN line END)                AS spread_pregame
FROM _offers
WHERE period = 'game'
GROUP BY 1, 2
"""

BY_BOOK_SQL = """
SELECT coalesce(p.name, 'book ' || CAST(v.book_id AS VARCHAR))      AS book,
       v.book_id,
       count(*)                                                     AS games,
       count(*) FILTER (WHERE v.total_all IS DISTINCT FROM v.total_pregame)
                                                                    AS total_changed,
       count(*) FILTER (WHERE v.spread_all IS DISTINCT FROM v.spread_pregame)
                                                                    AS spread_changed,
       count(*) FILTER (WHERE v.total_pregame IS NULL
                          AND v.total_all IS NOT NULL)              AS total_live_only,
       round(max(abs(v.total_all - v.total_pregame)), 1)            AS worst_total_delta
FROM _pivot v
LEFT JOIN stg.lines_provider p
  ON p.linesProviderId = CASE v.book_id WHEN 15 THEN 888888 WHEN 71 THEN 38
                                        ELSE v.book_id + 9000000 END
GROUP BY 1, 2
ORDER BY total_changed DESC, spread_changed DESC
"""

WORST_SQL = """
SELECT g.season, g.week, g.awayTeam || ' @ ' || g.homeTeam AS matchup,
       coalesce(p.name, 'book ' || CAST(v.book_id AS VARCHAR)) AS book,
       v.total_all, v.total_pregame, v.spread_all, v.spread_pregame
FROM _pivot v
JOIN stg.games g ON g.gameId = v.game_id
LEFT JOIN stg.lines_provider p
  ON p.linesProviderId = CASE v.book_id WHEN 15 THEN 888888 WHEN 71 THEN 38
                                        ELSE v.book_id + 9000000 END
WHERE v.total_all IS DISTINCT FROM v.total_pregame
ORDER BY abs(coalesce(v.total_all, 0) - coalesce(v.total_pregame, 0)) DESC
LIMIT ?
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="write the report here as JSON")
    ap.add_argument("--top", type=int, default=15, help="worst rows to list")
    args = ap.parse_args()

    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    try:
        for sql in (MAP_SQL, OFFERS_SQL, PIVOT_SQL):
            con.execute(sql)
        books = con.execute(BY_BOOK_SQL).fetchdf()
        worst = con.execute(WORST_SQL, [args.top]).fetchdf()
    finally:
        con.close()

    print("Full-game lines that move when live offerings are dropped\n")
    print(books.to_string(index=False))
    print(f"\ntotals affected: {int(books['total_changed'].sum())}"
          f"  spreads affected: {int(books['spread_changed'].sum())}")
    print(f"\nWorst {args.top} totals:\n")
    print(worst.to_string(index=False))

    if args.json:
        args.json.write_text(
            json.dumps(
                {"by_book": books.to_dict("records"), "worst": worst.to_dict("records")},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
