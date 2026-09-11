"""Inventory of what each odds source actually holds on disk and in the warehouse.

Backs `docs/odds-sources-an-vs-apis-2026-09-11.md`: which markets, books, seasons and
history depth come from the Action Network scrape versus the-odds-api, oddspapi
(Pinnacle) and CFBD's `lines` endpoint. Read-only; prints tables, writes nothing.

    python scripts/audit_odds_sources.py
"""

from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

import duckdb

REPO = next(p for p in Path(__file__).resolve().parents if (p / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

DB = cfb_paths.DATA_ROOT / "cfb.duckdb"


def _show(con: duckdb.DuckDBPyConnection, title: str, sql: str) -> None:
    print(f"\n== {title}")
    try:
        print(con.sql(sql))
    except duckdb.Error as exc:  # a dropped table is a finding, not a crash
        print(f"  unavailable: {exc}")


def warehouse() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    _show(con, "AN scoreboard events by season (raw.an_scoreboard)", """
        with ev as (
          select season, cast(json_extract(g.value, '$.id') as int) event_id
          from raw.an_scoreboard, json_each(payload, '$.games') g)
        select season, count(distinct event_id) events from ev group by 1 order by 1""")
    _show(con, "AN history offers by season x period (stg.an_history, spread market)", """
        with ev as (
          select season, cast(json_extract(g.value, '$.id') as int) event_id
          from raw.an_scoreboard, json_each(payload, '$.games') g)
        select ev.season, h.period, count(distinct h.event_id) events,
               count(distinct h.book_id) books,
               count(distinct case when h.tickets_pct is not null then h.event_id end) with_splits
        from stg.an_history h join ev using (event_id)
        where h.market_type = 'spread' group by 1, 2 order by 1, 2""")
    _show(con, "AN per-book full-game spread coverage (stg.an_history)", """
        select book_id, count(distinct event_id) events from stg.an_history
        where period = 'event' and market_type = 'spread' group by 1 order by 1""")
    _show(con, "AN tick history (stg.an_history_tick)", """
        select period, count(*) ticks, count(distinct event_id) events, count(distinct book_id) books,
               min(updated_at) first_tick, max(updated_at) last_tick
        from stg.an_history_tick group by 1 order by 1""")
    _show(con, "the-odds-api in core (core.fact_game_odds)", """
        select count(*) rows_, count(distinct game_id) games, count(distinct book) books,
               count(distinct pulled_at) snapshots, min(pulled_at) first_pull, max(pulled_at) last_pull
        from core.fact_game_odds""")
    _show(con, "core.fact_game_line by source", """
        select _source, count(*) rows_, count(distinct game_id) games, count(distinct provider_key) books
        from core.fact_game_line group by 1""")
    _show(con, "AN-derived stg tables present", """
        select table_schema, table_name from information_schema.tables
        where table_name like 'an_%' or table_name like 'oa_%' order by 1, 2""")


def on_disk() -> None:
    an = cfb_paths.RAW / "actionnetwork"
    sb = glob.glob(str(an / "scoreboard_*_wk*.json"))
    by_season = collections.Counter(Path(p).name.split("_")[1] for p in sb)
    print("\n== raw/actionnetwork on disk")
    print(f"  scoreboard files: {len(sb)}  seasons: {dict(sorted(by_season.items()))}")
    print(f"  history_<id>.json (1H/1Q):    {len(glob.glob(str(an / 'history_[0-9]*.json')))}")
    print(f"  history_event_<id>.json (FG): {len(glob.glob(str(an / 'history_event_*.json')))}")
    for name in ("oddsapi", "oddspapi"):
        files = sorted(glob.glob(str(cfb_paths.INGEST / name / "*.json")))
        span = f"{Path(files[0]).name} .. {Path(files[-1]).name}" if files else "none"
        print(f"\n== ingest/{name}: {len(files)} snapshot(s)  {span}")
        if files:
            d = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
            evs = d.get("events") or d.get("fixtures") or []
            books = sorted({b.get("key") for e in evs for b in e.get("bookmakers", []) if isinstance(b, dict)})
            print(f"  latest: {len(evs)} events, books={books or d.get('bookmakers')}, markets={d.get('markets')}")
    print("\n== CFBD lines providers by season (raw/lines_<season>.json)")
    for path in sorted(glob.glob(str(cfb_paths.RAW / "lines_[0-9][0-9][0-9][0-9].json"))):
        games = json.loads(Path(path).read_text(encoding="utf-8"))
        games = games if isinstance(games, list) else games.get("data", [])
        prov = collections.Counter(l.get("provider") for g in games for l in g.get("lines", []))
        print(f"  {Path(path).stem[-4:]}: {len(games)} games  {dict(prov)}")


def main() -> int:
    on_disk()
    if DB.is_file():
        warehouse()
    else:
        print(f"\nno warehouse at {DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
