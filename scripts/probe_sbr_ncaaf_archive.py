"""Measure what the Sportsbook Reviews Online NCAAF odds archive actually serves.

The archive is the only verified source of pre-2013 college football *totals* and
moneylines (CFBD's lines floor is 2013 -- see docs/cfbd-lines-coverage-2026-09-17.md).
Each season is an HTML table, two rows per game, no file download. This probe reports
per-season row counts and field fill so the coverage claim is measured, not assumed.

robots.txt (checked 2026-09-17) allows /scoresoddsarchives/; only /go/ is disallowed.
The default user agent is a browser string because the site 404s unknown agents.

    python scripts/probe_sbr_ncaaf_archive.py            # pre-2013 seasons
    python scripts/probe_sbr_ncaaf_archive.py --all
"""
from __future__ import annotations

import argparse
import html
import re
import time
import urllib.request

BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaa-football-{}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
# Season pages are labelled by the split year, e.g. the 2007 season is "2007-08".
SEASONS = [f"{y}-{str(y + 1)[2:]}" for y in range(2007, 2023)]
DELAY_S = 2.0  # ponytail: fixed delay, plenty for 16 pages; revisit only if throttled


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def table_rows(page: str) -> list[list[str]]:
    out = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            " ".join(html.unescape(re.sub(r"<[^>]*>", " ", c)).split())
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", raw, re.S)
        ]
        if cells:
            out.append(cells)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="every season, not just pre-2013")
    args = ap.parse_args()

    seasons = SEASONS if args.all else [s for s in SEASONS if int(s[:4]) < 2013]

    print("season   rows  games  open  close    ML    2H")
    for i, season in enumerate(seasons):
        if i:
            time.sleep(DELAY_S)
        try:
            rows = table_rows(fetch(BASE.format(season)))
        except Exception as exc:  # noqa: BLE001 - report, don't abort the sweep
            print(f"{season}  ERROR {exc}")
            continue

        header = rows[0] if rows else []
        body = [r for r in rows[1:] if len(r) == len(header)]
        idx = {name: n for n, name in enumerate(header)}

        def filled(col: str) -> int:
            n = idx.get(col)
            if n is None:
                return -1
            # "NL" is the archive's no-line marker; blank cells also occur.
            return sum(1 for r in body if r[n] not in ("", "NL", "nl"))

        print(
            f"{season}  {len(body):5d}  {len(body) // 2:5d}  "
            f"{filled('Open'):4d}  {filled('Close'):4d}  "
            f"{filled('ML'):4d}  {filled('2H'):4d}"
        )

    print("\nTwo rows per game (V then H). Per pair, one row's Open/Close is the spread")
    print("and the other's is the game total -- which is which is NOT flagged in the")
    print("markup and has to be inferred. Resolve that before trusting any parse.")


if __name__ == "__main__":
    main()
