"""Flatten Action Network line-movement history into a tidy CSV.

Reads $CFB_DATA_ROOT/raw/actionnetwork/history_*.json and writes one table to
$CFB_DATA_ROOT/processed/actionnetwork/:

  an_history_tick.csv   one row per (event, book, period, market, side, updated_at)

This is the part of the scraped payload the warehouse does not have. Each offer in
a history file carries a nested `history[]` of timestamped `{value, odds,
line_status}` entries; `duckdb_load._explode_an_history` reads only the offer's
top-level snapshot, so `stg.an_history` holds closing prices and no movement.

Only the full-game files `collect_line_timing.py` writes (`history_event_*.json`)
actually carry ticks -- the 2026-08 bulk backfill of 1H/1Q periods came back with
`history: []` on every offer, so it contributes offers and no rows. That is a
property of the payloads on disk, not a bug here: `--report` prints the split.

    python scripts/actionnetwork_flatten.py
    python scripts/actionnetwork_flatten.py --report     # counts only, write nothing
    python scripts/actionnetwork_flatten.py --validate   # re-read the written CSV

Nothing loads this yet. `duckdb_load._plan_loads` would take it the way it takes
`processed/massey/*.csv` -- straight to `stg`, no raw twin -- once the shape is agreed.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))
IN_DIR = DATA_ROOT / "raw" / "actionnetwork"
OUT_DIR = DATA_ROOT / "processed" / "actionnetwork"
OUT_NAME = "an_history_tick.csv"

# Offer scalars that identify the offering; the tick supplies the rest.
COLUMNS = [
    "event_id", "book_id", "period", "market_type", "side",
    "team_id", "market_id", "outcome_id", "is_alt_market", "is_live",
    "updated_at", "line", "odds", "line_status", "_source_file",
]

_EVENT_ID_RE = re.compile(r"history_(?:event_)?(\d+)")


def _event_id(offer: dict, path: Path) -> int | None:
    """Offer's own id, else the one in the filename."""
    if offer.get("event_id") is not None:
        return int(offer["event_id"])
    match = _EVENT_ID_RE.search(path.stem)
    return int(match.group(1)) if match else None


def ticks(path: Path) -> tuple[list[dict], int]:
    """Rows for one history file, plus the number of offers walked."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    offers = 0
    # book id -> period -> market -> [offer]
    for book in payload.values():
        if not isinstance(book, dict):
            continue
        for period, markets in book.items():
            if not isinstance(markets, dict):
                continue
            for market, offer_list in markets.items():
                for offer in offer_list or []:
                    offers += 1
                    base = {
                        "event_id": _event_id(offer, path),
                        "book_id": offer.get("book_id"),
                        "period": offer.get("period") or period,
                        "market_type": offer.get("type") or market,
                        "side": offer.get("side"),
                        "team_id": offer.get("team_id"),
                        "market_id": offer.get("market_id"),
                        "outcome_id": offer.get("outcome_id"),
                        "is_alt_market": offer.get("is_alt_market"),
                        "is_live": offer.get("is_live"),
                        "_source_file": path.name,
                    }
                    for tick in offer.get("history") or []:
                        rows.append({
                            **base,
                            "updated_at": tick.get("updated_at"),
                            "line": tick.get("value"),
                            "odds": tick.get("odds"),
                            "line_status": tick.get("line_status"),
                        })
    return rows, offers


def collect(files: list[str]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    stats = {"files": len(files), "files_with_ticks": 0, "offers": 0, "unparsed": 0}
    for name in files:
        path = Path(name)
        try:
            file_rows, offers = ticks(path)
        except Exception as exc:  # a truncated file must not lose the rest
            stats["unparsed"] += 1
            print(f"  SKIP {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        stats["offers"] += offers
        if file_rows:
            stats["files_with_ticks"] += 1
        rows.extend(file_rows)

    # One offer can repeat a price at the same timestamp across scrapes of the same
    # event; the natural key is the whole offering plus the tick time.
    key = ("event_id", "book_id", "period", "market_type", "side", "market_id", "updated_at")
    seen: set[tuple] = set()
    unique = []
    for row in rows:
        k = tuple(row[c] for c in key)
        if k in seen:
            continue
        seen.add(k)
        unique.append(row)
    stats["duplicates"] = len(rows) - len(unique)

    unique.sort(key=lambda r: tuple(
        (r[c] is None, r[c]) for c in
        ("event_id", "book_id", "period", "market_type", "side", "updated_at")
    ))
    return unique, stats


def write(rows: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / OUT_NAME
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def validate() -> int:
    path = OUT_DIR / OUT_NAME
    if not path.exists():
        print(f"{path} does not exist; run without --validate first", file=sys.stderr)
        return 1
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            print(f"header mismatch: {reader.fieldnames}", file=sys.stderr)
            return 1
        rows = list(reader)
    bad = [r for r in rows if not r["event_id"] or not r["updated_at"] or not r["line"]]
    events = {r["event_id"] for r in rows}
    books = {r["book_id"] for r in rows}
    print(f"{path}: {len(rows):,} rows, {len(events):,} events, {len(books)} books")
    print(f"  periods : {sorted({r['period'] for r in rows})}")
    print(f"  markets : {sorted({r['market_type'] for r in rows})}")
    print(f"  span    : {min(r['updated_at'] for r in rows)} .. {max(r['updated_at'] for r in rows)}")
    if bad:
        print(f"  {len(bad)} row(s) missing event_id/updated_at/line", file=sys.stderr)
        return 1
    print("  ok: no missing event_id/updated_at/line")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--report", action="store_true", help="print counts and stop")
    p.add_argument("--validate", action="store_true", help="check the written CSV and stop")
    args = p.parse_args(argv)

    if args.validate:
        return validate()

    files = sorted(glob.glob(str(IN_DIR / "history_*.json")))
    if not files:
        print(f"no history files in {IN_DIR}", file=sys.stderr)
        return 1

    rows, stats = collect(files)
    print(f"{stats['files']:,} history files, {stats['offers']:,} offers")
    print(f"{stats['files_with_ticks']:,} carry ticks, {stats['unparsed']} unparsed")
    print(f"{len(rows):,} tick rows ({stats['duplicates']:,} duplicates dropped)")
    if args.report:
        return 0

    path = write(rows)
    print(f"\nwrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
