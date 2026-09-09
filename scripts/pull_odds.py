"""Pull one the-odds-api.com snapshot of NCAAF odds into `data/ingest/oddsapi/`.

    python scripts/pull_odds.py
    python scripts/pull_odds.py --markets h2h spreads totals --regions us us2

Each run writes a new timestamped file; snapshots are never overwritten, because
the difference between two of them IS the line movement. Lands in `ingest/`, not
`raw/`, since nothing in the loader reads it yet -- `cfb_paths` globs `raw/*.json`
and a stray file there becomes a permanent table.

Cost is one credit per region per market (the default costs 3, of 500/month on
the free plan). The run prints what it spent and what is left.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402
from cfb_system_maker.oddsapi_client import (  # noqa: E402
    DEFAULT_MARKETS,
    DEFAULT_REGIONS,
    SPORT,
    fetch_odds,
    find_odds_token,
    write_snapshot,
)

OUT_DIR = cfb_paths.INGEST / "oddsapi"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sport", default=SPORT)
    ap.add_argument("--regions", nargs="+", default=list(DEFAULT_REGIONS))
    ap.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    ap.add_argument("--odds-format", default="american", choices=["american", "decimal"])
    args = ap.parse_args()

    token = find_odds_token(REPO / "env.env")
    cost = len(args.regions) * len(args.markets)
    print(f"=== pull {args.sport}: {','.join(args.regions)} x {','.join(args.markets)} (~{cost} credits) ===")

    try:
        payload = fetch_odds(
            token=token,
            sport=args.sport,
            regions=tuple(args.regions),
            markets=tuple(args.markets),
            odds_format=args.odds_format,
        )
    except Exception as exc:  # the client already redacted the key out of this
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    path = write_snapshot(payload, OUT_DIR)
    books = {b["key"] for e in payload["events"] for b in e.get("bookmakers", [])}
    print(f"  {len(payload['events']):,} events, {len(books)} books -> {path.name}")
    print(f"  spent {payload['requests_last']}, {payload['requests_remaining']} remaining this period")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
