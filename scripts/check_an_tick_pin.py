"""Check that ``stg.an_history_tick`` still matches its pinned schema.

Two independent checks, reported separately because they fail for unrelated
reasons and only one of them is a code defect:

**schema** -- every column of ``stg.an_history_tick``, in order, against
``duckdb_load._AN_TICK_COLUMNS``. A drift here means the table was built by
something other than the pinned loader (``read_csv_auto`` sniffing, a hand-made
CREATE TABLE), and ``scripts/migrate_an_history_tick.py`` is the fix.

**join** -- every tick row reaching ``stg.an_history`` on
``event_id``/``book_id``/``market_id``/``side`` with no cast on either side. That
is the whole point of the pin, but a shortfall usually is *not* a type problem:
the tick CSV and ``raw/actionnetwork/history_*.json`` must be regenerated
together. ``refresh_cfbd.py`` flattens before it rebuilds for exactly this
reason; rebuild by calling ``build_duckdb`` yourself and the CSV goes stale
against JSON the 5-hourly scraper has since refreshed, orphaning any offer whose
``market_id`` moved upstream in between. Re-run
``scripts/actionnetwork_flatten.py``, reload, and check again before reading a
shortfall as a bug.

    python scripts/check_an_tick_pin.py
    python scripts/check_an_tick_pin.py --db path/to/other.duckdb

Exits 0 when both checks pass, 1 otherwise. Read-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402
from cfb_system_maker.duckdb_load import _AN_TICK_COLUMNS, _AN_TICK_TABLE  # noqa: E402

TABLE = f"stg.{_AN_TICK_TABLE}"

# No cast on either side: that the two agree without one is what the pin buys.
_JOIN_SQL = f"""
SELECT COUNT(*) FROM {TABLE} t
JOIN stg.an_history h
  ON h.event_id = t.event_id
 AND h.book_id = t.book_id
 AND h.market_id = t.market_id
 AND h.side IS NOT DISTINCT FROM t.side
"""


def live_types(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Column name -> type, in table order."""
    rows = con.execute(
        "SELECT column_name, data_type FROM duckdb_columns()"
        f" WHERE schema_name = 'stg' AND table_name = '{_AN_TICK_TABLE}'"
        " ORDER BY column_index"
    ).fetchall()
    return {name: dtype for name, dtype in rows}


def schema_faults(live: dict[str, str]) -> list[str]:
    """Every way the live table departs from the pin, worst first."""
    faults = [
        f"{name}: {live.get(name, '<missing>')}, pinned {want}"
        for name, want in _AN_TICK_COLUMNS.items()
        if live.get(name) != want
    ]
    extra = [name for name in live if name not in _AN_TICK_COLUMNS]
    if extra:
        faults.append(f"unpinned column(s): {', '.join(extra)}")
    # `read_csv(columns=...)` maps positionally, so order is part of the contract.
    if not faults and list(live) != list(_AN_TICK_COLUMNS):
        faults.append(f"column order drift: {', '.join(live)}")
    return faults


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--db", default=str(cfb_paths.DB_PATH))
    a = p.parse_args()

    con = duckdb.connect(a.db, read_only=True)
    try:
        live = live_types(con)
        if not live:
            print(f"{TABLE} does not exist")
            return 1

        faults = schema_faults(live)
        for fault in faults:
            print(f"  {fault}")
        print(
            f"schema : {'DRIFTED -- see scripts/migrate_an_history_tick.py' if faults else 'ok'}"
            f" ({len(_AN_TICK_COLUMNS)} columns)"
        )

        rows = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        have_history = con.execute(
            "SELECT COUNT(*) FROM duckdb_tables()"
            " WHERE schema_name = 'stg' AND table_name = 'an_history'"
        ).fetchone()[0]
        if not have_history:
            print("join   : skipped -- no stg.an_history to join")
            return 1 if faults else 0

        joined = con.execute(_JOIN_SQL).fetchone()[0]
        orphans = rows - joined
        print(f"join   : {joined:,}/{rows:,} tick rows reach stg.an_history without a cast")
        if orphans:
            print(
                f"  {orphans:,} orphan(s) -- most likely a stale CSV, not a type fault."
                " Re-run scripts/actionnetwork_flatten.py, reload, check again."
            )
    finally:
        con.close()
    return 1 if (faults or orphans) else 0


if __name__ == "__main__":
    raise SystemExit(main())
