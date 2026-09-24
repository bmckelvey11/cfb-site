"""Is `circa` on the line tape a sportsbook close -- and which book is each ActionNetwork id?

Every `circa`, `pinnacle`, `fanduel`, `betmgm` and `bet365` row in `core.fact_game_line` comes
from the ActionNetwork tape (`_source = 'gql'`), labelled by `duckdb_load._AN_PROVIDER_NAMES`.
`research/spread/docs/README.md` records AN's own `/web/v1/books` list (2026-09-08), which
disagrees with every one of those labels. This script tests the labels against the data
instead of against either list:

1. `circa` vs the other books' **opener** and **close** medians, per season (leave-one-out).
2. The two games that raised the question, every book side by side.
3. Orientation: is a `circa` sign disagreement a flipped home/away, or a line that moved
   through zero after the open?
4. Is the `circa` gap larger for games whose line opened further from kickoff?
5. AN book 30 against book 15 (the consensus) on the 2026 tick tape.
6. Identity matrix, 2026: each AN book id's line *in effect at* each the-odds-api pull and
   each oddspapi Pinnacle pull, matched on line and price. The book an id really is shows up
   as the one it matches exactly.

    python scripts/audit_an_book_labels.py

Read-only; opens the warehouse `read_only=True` and closes it. Findings:
cfb_system_maker/docs/circa-line-audit-2026-09-24.md.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.duckdb_load import _AN_SCHOOL_ALIAS  # noqa: E402
from pull_oddspapi import is_full_game_spread  # noqa: E402

EXCLUDE = ("circa", "teamrankings", "numberfire")  # circa is the suspect; the rest aren't books
AN_KEYS = ("circa", "pinnacle", "fanduel", "betmgm", "bet365")
AN_BOOK_IDS = (15, 30, 49, 68, 69, 71, 75)
EXAMPLES = (401869941, 401757282)


def show(con: duckdb.DuckDBPyConnection, title: str, sql: str) -> None:
    print(f"\n== {title}")
    print(con.sql(sql).df().to_string(index=False))


def pinnacle_rows() -> pd.DataFrame:
    """Full-game main-line home spread from every oddspapi Pinnacle snapshot."""
    out = []
    for path in sorted((DATA_ROOT / "ingest" / "oddspapi").glob("oddspapi_ncaa_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        pulled = datetime.fromisoformat(payload["pulled_at"])
        for fx in payload["fixtures"]:
            markets = ((fx.get("bookmakerOdds") or {}).get("pinnacle") or {}).get("markets") or {}
            for m in markets.values():
                if not is_full_game_spread(m):
                    continue
                for oc in m["outcomes"].values():
                    pl = oc["players"].get("0") or {}
                    oid = str(pl.get("bookmakerOutcomeId") or "")
                    if pl.get("mainLine") and pl.get("active") and oid.endswith("/home"):
                        out.append({"pulled_at": pulled,
                                    "start": fx["startTime"][:10],
                                    "home_full": fx.get("participant1Name"),
                                    "away_full": fx.get("participant2Name"),
                                    "line": float(oid.split("/")[0]),
                                    "odds": int(pl["priceAmerican"])})
    return pd.DataFrame(out)


def main() -> None:
    con = duckdb.connect(str(DATA_ROOT / "cfb.duckdb"), read_only=True)
    try:
        excl = ", ".join(repr(k) for k in EXCLUDE)
        # Leave-one-out: each book is compared with the *other* books on the same game.
        # Opens come only from REST rows -- the AN tape carries no opener column.
        con.execute(f"""
            CREATE TEMP TABLE ref AS
            SELECT l.game_id, g.season, g.week, g.season_type, l.provider_key,
                   l.spread_close AS spread,
                   median(o.spread_close) AS close_med,
                   median(o.spread_open)  AS open_med,
                   count(o.spread_close)  AS n_other
            FROM core.fact_game_line l
            JOIN core.fact_game g USING (game_id)
            JOIN core.fact_game_line o
              ON o.game_id = l.game_id AND o.provider_key <> l.provider_key
             AND o.provider_key NOT IN ({excl})
            WHERE g.season >= 2024 AND l.spread_close IS NOT NULL
            GROUP BY ALL
            HAVING count(o.spread_close) >= 3
        """)

        keys = ", ".join(repr(k) for k in AN_KEYS + ("draftkings",))
        show(con, "1. gap to the other books' close and REST-opener medians", f"""
            SELECT provider_key, season, count(*) n,
                   round(avg(abs(spread - close_med)), 2)              mean_gap_close,
                   round(avg((abs(spread - close_med) <= 0.5)::INT), 3) within_half_close,
                   count(open_med)                                      n_open,
                   round(avg(abs(spread - open_med)), 2)               mean_gap_open,
                   round(avg((abs(spread - open_med) <= 0.5)::INT), 3)  within_half_open
            FROM ref WHERE provider_key IN ({keys})
            GROUP BY ALL ORDER BY provider_key, season""")

        # CFBD's openers are per book and captured on CFBD's own clock, so this is a weak
        # opener test; section 5 is the strong one, for the season that has the tick tape.
        show(con, "1b. circa == a REST book's open / close, exact", """
            SELECT r.provider_key AS rest_book, g.season, count(*) n,
                   round(avg((c.spread_close = r.spread_open)::INT), 3)  AS eq_open,
                   round(avg((c.spread_close = r.spread_close)::INT), 3) AS eq_close
            FROM core.fact_game_line c
            JOIN core.fact_game_line r
              ON r.game_id = c.game_id AND r._source IN ('rest', 'both')
             AND r.spread_open IS NOT NULL AND r.spread_close IS NOT NULL
            JOIN core.fact_game g ON g.game_id = c.game_id
            WHERE c.provider_key = 'circa' AND c.spread_close IS NOT NULL
            GROUP BY ALL HAVING count(*) >= 100 ORDER BY rest_book, season""")

        ids = ", ".join(str(g) for g in EXAMPLES)
        show(con, "2. the two example games", f"""
            SELECT game_id, provider_key, _source, spread_open, spread_close,
                   moneyline_home, moneyline_away
            FROM core.fact_game_line WHERE game_id IN ({ids})
              AND provider_key NOT IN ('teamrankings', 'numberfire')
            ORDER BY game_id, provider_key""")

        # A flip lands on -close (and -open); an opener that moved through zero merely
        # crosses sign. Only |line| >= 3 can tell the two apart.
        show(con, "3. circa orientation: sign disagreements vs rows that equal the mirrored line", """
            SELECT season, count(*) n,
                   count(*) FILTER (WHERE sign(spread) * sign(close_med) = -1)      AS sign_vs_close,
                   count(*) FILTER (WHERE abs(close_med) >= 3)                      AS n_close_3plus,
                   count(*) FILTER (WHERE abs(close_med) >= 3
                                      AND sign(spread) * sign(close_med) = -1)      AS sign_vs_close_3plus,
                   count(*) FILTER (WHERE abs(close_med) >= 3
                                      AND abs(spread + close_med) <= 0.5)           AS equals_minus_close,
                   count(*) FILTER (WHERE abs(open_med) >= 3
                                      AND abs(spread + open_med) <= 0.5)            AS equals_minus_open
            FROM ref WHERE provider_key = 'circa' GROUP BY 1 ORDER BY 1""")

        show(con, "4a. mean |gap to close median| by week of season", f"""
            SELECT provider_key,
                   round(avg(abs(spread - close_med)) FILTER (WHERE week <= 1), 2)            AS wk_0_1,
                   round(avg(abs(spread - close_med)) FILTER (WHERE week BETWEEN 2 AND 4), 2) AS wk_2_4,
                   round(avg(abs(spread - close_med)) FILTER (WHERE week BETWEEN 5 AND 8), 2) AS wk_5_8,
                   round(avg(abs(spread - close_med)) FILTER (WHERE week >= 9
                         AND season_type = 'regular'), 2)                                     AS wk_9_plus,
                   round(avg(abs(spread - close_med)) FILTER (WHERE season_type <> 'regular'), 2) AS post
            FROM ref WHERE provider_key IN ({keys}) GROUP BY 1 ORDER BY 1""")

        alias = " ".join(
            "WHEN '{}' THEN '{}'".format(a.replace("'", "''"), b.replace("'", "''"))
            for a, b in _AN_SCHOOL_ALIAS.items())

        def team(tid: str, field: str) -> str:
            return (f"list_first(list_transform(list_filter(TRY_CAST(teams AS JSON[]), "
                    f"lambda t: TRY_CAST(json_extract(t, '$.id') AS BIGINT) = {tid}), "
                    f"lambda t: json_extract_string(t, '$.{field}')))")

        # Same event -> game join the loader's backfill uses.
        con.execute(f"""
            CREATE TEMP TABLE an_event AS
            WITH sb AS (
              SELECT event_id, season, week, start_time,
                     {team('home_team_id', 'location')}  AS home_loc,
                     {team('away_team_id', 'location')}  AS away_loc,
                     {team('home_team_id', 'full_name')} AS home_full,
                     {team('away_team_id', 'full_name')} AS away_full
              FROM stg.an_scoreboard WHERE season >= 2026
              QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY _source_file DESC) = 1
            )
            SELECT sb.*, g."gameId" AS game_id
            FROM sb LEFT JOIN stg.games g
              ON g.season = sb.season AND g.week = sb.week
             AND g."homeTeam" = CASE sb.home_loc {alias} ELSE sb.home_loc END
             AND g."awayTeam" = CASE sb.away_loc {alias} ELSE sb.away_loc END
        """)
        con.execute("""
            CREATE TEMP TABLE an_tick AS
            SELECT event_id, book_id, updated_at, line, odds
            FROM stg.an_history_tick
            WHERE period = 'event' AND market_type = 'spread' AND side = 'home'
              AND NOT coalesce(is_live, false) AND NOT coalesce(is_alt_market, false)
        """)

        # Lead time = the consensus's first tick to kickoff. An opener never updates, so the
        # capture time is the wrong axis; how long ago the line opened is the right one.
        show(con, "4b. 2026: circa gap to close by how far ahead of kickoff the line opened", """
            WITH lead AS (
              SELECT e.game_id,
                     date_diff('hour', min(t.updated_at), any_value(e.start_time)) / 24.0 AS days
              FROM an_tick t JOIN an_event e USING (event_id)
              WHERE t.book_id = 15 GROUP BY 1
            )
            SELECT CASE WHEN days < 7 THEN 'a <7d' WHEN days < 14 THEN 'b 7-14d'
                        WHEN days < 60 THEN 'c 14-60d' ELSE 'd 60d+' END AS opened,
                   count(*) n, round(avg(abs(spread - close_med)), 2) mean_gap_close,
                   round(avg((abs(spread - close_med) >= 3)::INT), 3)  share_3plus
            FROM ref JOIN lead USING (game_id)
            WHERE provider_key = 'circa' GROUP BY 1 ORDER BY 1""")

        # Book 15's first tick carries line_status 'opener': that is AN's consensus opener.
        show(con, "5a. 2026: circa (core) vs the consensus opener and the consensus last tick", """
            WITH b15 AS (
              SELECT e.game_id,
                     arg_min(t.line, t.updated_at) AS open_line,
                     arg_max(t.line, t.updated_at) AS last_line
              FROM an_tick t JOIN an_event e USING (event_id)
              WHERE t.book_id = 15 GROUP BY 1
            )
            SELECT count(*) n,
                   round(avg((c.spread_close = b.open_line)::INT), 3)           AS eq_consensus_open,
                   round(avg((abs(c.spread_close - b.open_line) <= 0.5)::INT), 3) AS within_half_open,
                   round(avg((c.spread_close = b.last_line)::INT), 3)           AS eq_consensus_last
            FROM core.fact_game_line c JOIN b15 b USING (game_id)
            WHERE c.provider_key = 'circa' AND c.spread_close IS NOT NULL""")

        # The flattener copies each offering's history[]; if 30's is 15's, the tick tape
        # cannot tell them apart even though the offering's own value differs.
        show(con, "5b. 2026 tick tape: book 30 ticks vs book 15 ticks at the same instant", """
            SELECT count(*) AS b30_ticks,
                   count(b.line) AS with_b15_tick_same_instant,
                   count(*) FILTER (WHERE a.line = b.line AND a.odds = b.odds) AS identical
            FROM an_tick a
            LEFT JOIN an_tick b
              ON b.event_id = a.event_id AND b.updated_at = a.updated_at AND b.book_id = 15
            WHERE a.book_id = 30""")

        con.register("pin_df", pinnacle_rows())
        # Reference lines observed at a known instant: the-odds-api pulls (home orientation
        # checked against core) and oddspapi Pinnacle pulls (matched on AN's full team names).
        con.execute("""
            CREATE TEMP TABLE obs AS
            SELECT e.event_id, o.book, o.pulled_at, o.line, o.odds
            FROM core.fact_game_odds o
            JOIN core.fact_game g ON g.game_id = o.game_id AND g.home_team_id = o.home_team_id
            JOIN an_event e ON e.game_id = o.game_id
            WHERE o.market = 'spreads' AND o.side = 'home' AND o.pulled_at < o.commence_time
            UNION ALL
            SELECT e.event_id, 'pinnacle (oddspapi)', p.pulled_at, p.line, p.odds
            FROM pin_df p JOIN an_event e
              ON e.home_full = p.home_full AND e.away_full = p.away_full
             AND abs(date_diff('day', CAST(e.start_time AS DATE), CAST(p.start AS DATE))) <= 1
            WHERE p.pulled_at < e.start_time
        """)
        ids = ", ".join(str(b) for b in AN_BOOK_IDS)
        # Only pulls the AN tape had caught up to: an event whose history was last fetched
        # before the pull cannot say what was in effect at it.
        con.execute(f"""
            CREATE TEMP TABLE m6 AS
            WITH seen AS (SELECT event_id, max(updated_at) AS last_seen FROM an_tick GROUP BY 1),
            yb AS (
              SELECT o.*, b.book_id FROM obs o JOIN seen s USING (event_id)
              CROSS JOIN (SELECT unnest([{ids}]) AS book_id) b
              WHERE o.pulled_at <= s.last_seen
            )
            SELECT yb.book, yb.book_id,
                   (x.line = yb.line AND x.odds = yb.odds)::INT AS exact,
                   (x.line = yb.line)::INT                      AS line_only
            FROM yb ASOF JOIN an_tick x
              ON x.event_id = yb.event_id AND x.book_id = yb.book_id
             AND x.updated_at <= yb.pulled_at
        """)
        for col in ("exact", "line_only"):
            show(con, f"6. 2026 identity ({col}): share of pulls where AN id's line in effect "
                      "matches the book's", f"""
                PIVOT (SELECT book, book_id, {col} FROM m6)
                ON book_id USING round(avg({col}), 2) GROUP BY book ORDER BY book""")
        show(con, "6b. pulls compared per reference book", """
            SELECT book, count(*) n_pulls, count(DISTINCT event_id) n_events
            FROM obs GROUP BY 1 ORDER BY 1""")
        # A reference nothing matches is either a book nobody is, or a broken join. Pinnacle's
        # last pre-kickoff pull has to sit on the other books' close for the first reading.
        show(con, "6c. reference sanity: last pre-kickoff pull vs the books' close median", """
            WITH last AS (
              SELECT o.book, e.game_id, arg_max(o.line, o.pulled_at) AS line
              FROM obs o JOIN an_event e USING (event_id) GROUP BY 1, 2
            ),
            med AS (SELECT game_id, any_value(close_med) AS close_med FROM ref
                    WHERE provider_key = 'circa' GROUP BY 1)
            SELECT book, count(*) n,
                   round(avg(abs(line - close_med)), 2) AS mean_gap_close,
                   round(avg((sign(line) = sign(close_med))::INT)
                         FILTER (WHERE abs(close_med) >= 3), 3) AS sign_agree_3plus
            FROM last JOIN med USING (game_id) GROUP BY 1 ORDER BY 1""")
    finally:
        con.close()


if __name__ == "__main__":
    main()
