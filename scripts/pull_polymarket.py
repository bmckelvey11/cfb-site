"""Pull one Polymarket snapshot of CFB game prices into `data/ingest/polymarket/`.

    python scripts/pull_polymarket.py

Read-only and free: Polymarket's Gamma API needs no key and no account. Each run writes
a new timestamped file; snapshots are never overwritten, because the difference between
two of them IS the line movement. Then run `scripts/polymarket_flatten.py` (or
`refresh_cfbd.py`, which does it) to load them.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402
from cfb_system_maker.polymarket_client import fetch_markets, write_snapshot  # noqa: E402

OUT_DIR = cfb_paths.INGEST / "polymarket"


def main() -> int:
    print("=== pull polymarket cfb ===")
    try:
        payload = fetch_markets()
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    path = write_snapshot(payload, OUT_DIR)
    markets = sum(len(e["markets"]) for e in payload["events"])
    print(f"  series {payload['series_id']}: {payload['events_seen']} events listed, "
          f"{len(payload['events'])} upcoming games, {markets:,} markets -> {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
