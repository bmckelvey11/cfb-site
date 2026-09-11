"""Daily CFBD refresh into the DuckDB warehouse.

Force-rescrapes the current season's endpoints that actually change during the
season (games, lines, calendar, conferences, venues -- everything `build_core`'s
Phase 1 tables need), re-pulls the two GraphQL dumps whose staleness reaches a
`core` value, reflattens the Action Network tick CSV so the movement
scraped since the last run is visible, then does a full rebuild of `cfb.duckdb`
from data/raw + data/graphql + data/processed (that rebuild is a cheap, atomic
full-reload -- see `duckdb_load.build_duckdb` -- so there is no incremental-load
state to get wrong), then checks that the rebuild reproduced the pinned
`stg.an_history_tick` schema. A rebuild is the only thing that can undo that pin,
so this is the run that has to notice; a failure exits non-zero into the
scheduler's log without implying the warehouse itself is unusable.

    python scripts/refresh_cfbd.py
    python scripts/refresh_cfbd.py --season 2026
    python scripts/refresh_cfbd.py --only games lines calendar conferences venues sp elo

`--season` defaults to the current CFB season: the calendar year Jul-Dec,
year - 1 Jan-Jun (bowls/playoff still belong to the prior season then).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfb_paths  # noqa: E402
from actionnetwork_flatten import IN_DIR as AN_HISTORY_DIR  # noqa: E402
from actionnetwork_flatten import collect as an_collect  # noqa: E402
from actionnetwork_flatten import write as an_write  # noqa: E402
from check_an_tick_pin import check as an_tick_check  # noqa: E402
from cfb_system_maker.cfbd_client import find_cfbd_token  # noqa: E402
from cfb_system_maker.cli import rebuild_processed_games  # noqa: E402
from cfb_system_maker.duckdb_core import build_core  # noqa: E402
from cfb_system_maker.duckdb_load import build_duckdb  # noqa: E402
from cfb_system_maker.graphql_client import graphql_scrape  # noqa: E402
from cfb_system_maker.scrapers import scrape  # noqa: E402
from pff_flatten import IN_DIR as PFF_IN_DIR  # noqa: E402
from pff_flatten import dimensions as pff_dimensions  # noqa: E402
from pff_flatten import flatten as pff_flatten  # noqa: E402
from pff_flatten import write as pff_write  # noqa: E402
from oddsapi_flatten import IN_DIR as OA_IN_DIR  # noqa: E402
from oddsapi_flatten import main as oddsapi_flatten_main  # noqa: E402

DEFAULT_ONLY = {"games", "lines", "calendar", "conferences", "venues"}

# The two GraphQL dumps measured as materially behind on 2026-09-11, and the only two whose
# staleness has a path to a `core` value. The other 48 are pulled by hand; see
# docs/graphql-dump-staleness-2026-09-11.md for why each stays off this list.
_GQL_REFRESH_TABLES = ("game", "gameLines")

# A pull that comes back smaller than this fraction of what is already on disk is treated as
# a short read and discarded. Both tables are append-mostly -- the 2026-09-11 pulls grew
# 112,672 -> 112,675 and 38,647 -> 39,008 -- so real shrinkage is a few rows, never 5%.
_GQL_MIN_RETAINED = 0.95


def _json_rows(path: Path) -> int | None:
    """Row count of a dump already on disk, or None if it is absent or unreadable."""
    if not path.is_file():
        return None
    try:
        return duckdb.sql(
            "SELECT count(*) FROM read_json_auto(?)", params=[str(path)]
        ).fetchone()[0]
    except duckdb.Error:
        return None


def _pull_graphql(token: str) -> None:
    """Re-pull the GraphQL dumps the rebuild is about to load.

    Same reason as the flattens below, and the same shape of bug: `refresh_cfbd.py` scraped
    REST and rebuilt the warehouse without ever re-pulling `data/graphql/*.json`, so every
    rebuild reloaded whatever those files held the last time someone pulled them by hand. On
    2026-09-11 `game.json` was 14 days old and measurably behind -- it lacked 4 in-span REST
    games and still called 415 finished games `scheduled` -- while `gameLines.json` lacked
    1,682 REST-lined games. A full pull took both gaps to zero.

    **Never pass `seasons=`.** `graphql_scrape` turns it into a `where` clause but
    `_write` replaces the whole file, so a season-scoped pull would truncate `game.json`
    from 1869-2026 down to the one season asked for. Same trap as `duckdb --only`.

    The pull is staged in a sibling directory and swapped in with `Path.replace`, mirroring
    `build_duckdb`'s `.building` idiom: the live dump is never the thing being written, so a
    crash mid-pull cannot leave a half-file behind.

    Two different failures, and the guard only covers one of them. A pull that *raises* is
    already safe -- `graphql_scrape` catches per table and `_write` runs only after
    `_paginate` returns, so the staged file simply never appears. What the count check
    catches is the quiet one: a short read that returns 5,000 rows instead of 112,675 and
    reports success, which would otherwise replace the dump with a truncated copy.

    Never fatal, like the flattens: the rebuild is the expensive half.
    """
    print("=== pull graphql dumps ===")
    live_dir = cfb_paths.DATA_ROOT / "graphql"
    stage_root = cfb_paths.DATA_ROOT / ".graphql-pull"
    for table in _GQL_REFRESH_TABLES:
        live = live_dir / f"{table}.json"
        before = _json_rows(live)
        try:
            reports = graphql_scrape(
                tables=[table], data_dir=stage_root, token=token
            )
        except Exception as exc:
            print(f"  {table:16} FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        report = reports[0]
        if report.error is not None:
            print(f"  {table:16} FAILED {report.error}", file=sys.stderr)
            continue
        staged = stage_root / "graphql" / f"{table}.json"
        if not staged.is_file():
            print(f"  {table:16} FAILED pull reported ok but wrote no file", file=sys.stderr)
            continue
        if before is not None and report.rows < before * _GQL_MIN_RETAINED:
            print(f"  {table:16} SHORT READ {report.rows:,} rows against {before:,} on "
                  f"disk; keeping the existing dump", file=sys.stderr)
            staged.unlink()
            continue
        live.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(live)
        delta = "" if before is None else f" ({report.rows - before:+,})"
        print(f"  {table:16} {report.rows:,} rows, {report.pages} page(s){delta}")


def _flatten_actionnetwork() -> None:
    """Regenerate the Action Network tick CSV the rebuild is about to load.

    `CFB-AN-History` scrapes new line movement every 5 hours, but the warehouse
    only sees it through `processed/actionnetwork/an_history_tick.csv`. Without
    this step the daily rebuild faithfully reloads whatever CSV was last written
    by hand, and every tick scraped since then stays invisible.

    Never fatal: a locked CSV (Excel takes an exclusive lock) or a bad payload
    must not cost us the rebuild, which is the expensive half.
    """
    print("=== flatten actionnetwork ticks ===")
    files = sorted(str(p) for p in AN_HISTORY_DIR.glob("history_*.json"))
    if not files:
        print(f"  no history files in {AN_HISTORY_DIR}; nothing to flatten")
        return
    try:
        rows, stats = an_collect(files)
        path = an_write(rows)
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        print("  rebuilding against the CSV already on disk")
        return
    print(f"  {stats['files']:,} files, {len(rows):,} ticks -> {path.name}")


def _flatten_pff() -> None:
    """Regenerate the PFF CSVs the rebuild is about to load, for the same reason.

    The PFF exports land in `data/raw/pff/` and reach the warehouse only through
    `processed/pff/*.csv`. Without this step a rebuild reloads whatever the last
    hand-run of the flattener wrote, and a week pulled since then stays invisible.

    Never fatal, like the Action Network flatten: the rebuild is the expensive half.
    """
    print("=== flatten pff ===")
    if not PFF_IN_DIR.is_dir():
        print(f"  no pull in {PFF_IN_DIR}; nothing to flatten")
        return
    try:
        rows, metrics, _dropped, names, people = pff_flatten(None)
        pff_dimensions(rows, None, names, people)
        written = pff_write(rows, metrics)
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        print("  rebuilding against the CSVs already on disk")
        return
    print(f"  {len(written)} tables, {sum(n for _, n, _ in written):,} rows")


def _rebuild_games_csv(season: int) -> None:
    """Regenerate ``processed/games.csv`` for the season just scraped.

    The scrape overwrites ``raw/games_<season>.json`` and ``raw/lines_<season>.json`` and
    nothing here rebuilt the CSV from them, so it drifted behind the warehouse by however
    long since someone last ran ``python -m cfb_system_maker build`` by hand. On
    2026-09-10 it was two days behind -- CSV 09-08 01:05 against the JSON at 09-10 05:00 --
    and both standing ``-m slow tests/test_core_agreement.py`` failures traced to it, since
    those tests compare the CSV against the warehouse. They had been read as regressions
    twice. Only one was pure staleness: rebuilding cleared the coverage drift outright and
    turned the other into a single real divergence, which the AN line union had caused and
    the stale CSV had been hiding.

    Only this season is rebuilt; every other season's rows are carried through, the same
    contract the ``build`` subcommand has.

    Never fatal, like the flattens above: the rebuild is the expensive half and a CSV that
    failed to write is worth finishing the run to report.
    """
    print("=== rebuild processed/games.csv ===")
    try:
        rebuilt, kept, total = rebuild_processed_games(cfb_paths.DATA_ROOT, [season])
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}")
        return
    print(f"  {rebuilt:,} game(s) for {season}, {kept:,} kept from other seasons "
          f"-> {total:,} total")


def _flatten_oddsapi() -> None:
    """Regenerate the the-odds-api CSVs the rebuild is about to load.

    Same reason as the other two: without it a rebuild reloads whatever the last hand-run
    wrote, and every snapshot the scheduled 6-hourly pull has landed since stays invisible.

    Never fatal -- but an unresolved team name is reported loudly, because it means a
    `stg.oa_odds_tick` row will reach `core.fact_game_odds` with a NULL `game_id`.
    """
    print("=== flatten oddsapi ===")
    if not OA_IN_DIR.is_dir():
        print(f"  no snapshots in {OA_IN_DIR}; nothing to flatten")
        return
    try:
        rc = oddsapi_flatten_main([])
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        print("  rebuilding against the CSVs already on disk")
        return
    if rc:
        print("  unresolved team names above will land as NULL game_id", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", type=int, default=cfb_paths.current_season())
    ap.add_argument("--only", nargs="+", default=sorted(DEFAULT_ONLY))
    args = ap.parse_args()

    token = find_cfbd_token(REPO / "env.env")

    print(f"=== scrape {args.season}: {' '.join(args.only)} ===")
    reports = scrape(
        [args.season],
        data_dir=cfb_paths.DATA_ROOT,
        only=set(args.only),
        token=token,
        resume=False,  # daily refresh must overwrite -- games/lines change all week
    )
    failed = [r for r in reports if r.error is not None]
    for r in reports:
        status = f"FAILED  {r.error}" if r.error else f"{r.rows} rows"
        print(f"  {r.name:16} {status}")
    if failed:
        print(f"{len(failed)} endpoint(s) failed; aborting before duckdb rebuild.")
        return 1

    # After the abort above: a dead REST endpoint must not cost a 4-minute GraphQL pull
    # that gets thrown away. Before the flattens and the CSV rebuild, so the ordering reads
    # as "refresh every source, then derive from them".
    _pull_graphql(token)

    _flatten_actionnetwork()
    _flatten_pff()
    _flatten_oddsapi()
    _rebuild_games_csv(args.season)

    print("=== rebuild cfb.duckdb ===")
    db_path, loads = build_duckdb(cfb_paths.DATA_ROOT, explode=True)
    # `build_duckdb` reports a failed table rather than raising, and the explode reports
    # the same way. Discarding this list made both silent: on 2026-09-11 a rebuild produced
    # a `stg` with no `an_*` tables at all, `build_core` then died in `_merge_game_lines`
    # on the `period` column the ActionNetwork backfill would have created, and the only
    # trace was the crash 200 lines later. `meta.load_report` does not cover the gap either
    # -- `_write_meta` runs *before* the explode, so it structurally cannot hold an explode
    # error. Printing here is the only place they surface.
    broken = [r for r in loads if r.error is not None]
    for r in broken:
        print(f"  LOAD ERROR {r.schema}.{r.name}: {r.error}", file=sys.stderr)
    if broken:
        print(f"  {len(broken)} table(s) failed to load; core may be incomplete",
              file=sys.stderr)
    built = build_core(db_path)
    print(f"Rebuilt {db_path} (core: {', '.join(built)})")

    return 0 if _check_an_tick_pin(db_path) else 1


def _check_an_tick_pin(db_path: Path) -> bool:
    """Verify the rebuild reproduced the pinned `stg.an_history_tick` schema.

    A rebuild is the only thing that can undo the pin, so this is the run that
    has to notice. Both halves of the check mean something different here than
    they do from the command line: `_flatten_actionnetwork` ran first, so the
    tick CSV and the AN JSON went in together and the stale-CSV explanation for
    orphans is off the table -- a shortfall means the payloads themselves
    disagree. A schema drift means the loader stopped honouring
    `_AN_TICK_COLUMNS`.

    Non-fatal to the warehouse, which is already written and usable; the
    non-zero exit is what puts it in the scheduler's log.
    """
    print("=== check an_history_tick pin ===")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        ok, lines = an_tick_check(con)
    finally:
        con.close()
    for line in lines:
        print(f"  {line}")
    if not ok:
        # check() writes for a command-line reader, who most often got here with a
        # stale CSV. This run reflattened first, so that hint does not apply.
        print("  (the CSV was reflattened this run -- staleness is not the cause)")
        print("  warehouse is rebuilt and usable; the pin check is what failed")
    return ok


if __name__ == "__main__":
    raise SystemExit(main())
