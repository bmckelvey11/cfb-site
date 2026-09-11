"""Daily CFBD refresh into the DuckDB warehouse.

Force-rescrapes the current season's endpoints that actually change during the
season (games, lines, calendar, conferences, venues -- everything `build_core`'s
Phase 1 tables need), reflattens the Action Network tick CSV so the movement
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
from cfb_system_maker.scrapers import scrape  # noqa: E402
from pff_flatten import IN_DIR as PFF_IN_DIR  # noqa: E402
from pff_flatten import dimensions as pff_dimensions  # noqa: E402
from pff_flatten import flatten as pff_flatten  # noqa: E402
from pff_flatten import write as pff_write  # noqa: E402
from oddsapi_flatten import IN_DIR as OA_IN_DIR  # noqa: E402
from oddsapi_flatten import main as oddsapi_flatten_main  # noqa: E402

DEFAULT_ONLY = {"games", "lines", "calendar", "conferences", "venues"}


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

    _flatten_actionnetwork()
    _flatten_pff()
    _flatten_oddsapi()
    _rebuild_games_csv(args.season)

    print("=== rebuild cfb.duckdb ===")
    db_path, _ = build_duckdb(cfb_paths.DATA_ROOT, explode=True)
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
