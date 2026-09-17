"""Snapshot cfbdepth.com's depth-chart sheets.

The site is a React shell over 139 public Google Sheets -- one per FBS team,
seven tabs each, all sharing the same tab gids. See
docs/cfbdepth-scrape-2026-09-16.md for the architecture and the caveats.

Sheets are overwritten in place upstream, so every run is a fresh point-in-time
snapshot and lands in its own dated directory under INGEST.

    python scripts/pull_cfbdepth.py                 # all teams, all tabs
    python scripts/pull_cfbdepth.py --teams alabama uga
    python scripts/pull_cfbdepth.py --tabs injuryReport --force
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfb_paths import INGEST

REGISTRY = Path(__file__).resolve().parent.parent / "docs" / "cfbdepth-teams-registry.json"
EXPORT = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
TABS = ["dashboard", "offense", "defense", "specialTeam",
        "injuryReport", "rosterBreakdown", "playerRating"]

# ponytail: fixed sleep between requests, not a token bucket. ~970 requests at
# 0.4s is under 7 minutes and stays well clear of Google's export throttling.
DELAY_S = 0.4


def fetch(session, url, attempts=4):
    """GET with retries -- this host renegotiates TLS mid-request and Windows
    schannel/OpenSSL both drop the connection often enough to matter."""
    for i in range(attempts):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            # Bytes, not text: Google sends CRLF and text-mode writes would
            # translate the LF again, leaving CR CR LF and a phantom blank
            # line between every row.
            return r.content
        except Exception as exc:
            if i == attempts - 1:
                raise
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--teams", nargs="*", help="team slugs (default: all)")
    ap.add_argument("--tabs", nargs="*", default=TABS, choices=TABS)
    ap.add_argument("--out", type=Path, help="override output directory")
    ap.add_argument("--force", action="store_true", help="refetch files already present")
    args = ap.parse_args()

    registry = json.loads(REGISTRY.read_text())
    slugs = args.teams or sorted(registry)
    unknown = [s for s in slugs if s not in registry]
    if unknown:
        ap.error(f"not in registry: {', '.join(unknown)}")

    out = args.out or INGEST / "cfbdepth" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    written = skipped = 0
    failures = []
    for n, slug in enumerate(slugs, 1):
        sid = registry[slug]["spreadsheetId"]
        for tab in args.tabs:
            path = out / f"{slug}_{tab}.csv"
            if path.exists() and not args.force:
                skipped += 1
                continue
            try:
                path.write_bytes(
                    fetch(session, EXPORT.format(sid=sid, gid=registry[slug][tab]))
                )
                written += 1
            except Exception as exc:
                failures.append((slug, tab, str(exc)[:120]))
            time.sleep(DELAY_S)
        print(f"[{n}/{len(slugs)}] {slug}", flush=True)

    print(f"\n{written} written, {skipped} skipped, {len(failures)} failed -> {out}")
    for slug, tab, err in failures:
        print(f"  FAIL {slug}/{tab}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
