"""Daily CFBD refresh into the DuckDB warehouse.

Force-rescrapes the current season's endpoints that actually change during the
season (games, lines, calendar, conferences, venues -- everything `build_core`'s
Phase 1 tables need), reflattens the Action Network tick CSV so the movement
scraped since the last run is visible, then does a full rebuild of `cfb.duckdb`
from data/raw + data/graphql + data/processed (that rebuild is a cheap, atomic
full-reload -- see `duckdb_load.build_duckdb` -- so there is no incremental-load
state to get wrong).

    python scripts/refresh_cfbd.py
    python scripts/refresh_cfbd.py --season 2026
    python scripts/refresh_cfbd.py --only games lines calendar conferences venues sp elo

`--season` defaults to the current CFB season: the calendar year Jul-Dec,
year - 1 Jan-Jun (bowls/playoff still belong to the prior season then).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

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
from cfb_system_maker.cfbd_client import find_cfbd_token  # noqa: E402
from cfb_system_maker.duckdb_core import build_core  # noqa: E402
from cfb_system_maker.duckdb_load import build_duckdb  # noqa: E402
from cfb_system_maker.scrapers import scrape  # noqa: E402

DEFAULT_ONLY = {"games", "lines", "calendar", "conferences", "venues"}


def _current_season(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", type=int, default=_current_season())
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

    print("=== rebuild cfb.duckdb ===")
    db_path, _ = build_duckdb(cfb_paths.DATA_ROOT, explode=True)
    built = build_core(db_path)
    print(f"Rebuilt {db_path} (core: {', '.join(built)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
