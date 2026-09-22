"""Snapshot DRatings' NCAA FBS power ratings (Donchess Inference Index) to CSV.

DRatings overwrites the page in place and keeps no history, so a week not captured is lost.
Each snapshot is keyed on the page's own "Updated" timestamp; re-running before DRatings
publishes again rewrites the same file.

    python research/spread/scripts/scrape_dratings.py

Output: $CFB_DATA_ROOT/ingest/dratings/fbs_ratings_<updated UTC>.csv, one row per team.
Methodology: https://www.dratings.com/methodology/
"""

from __future__ import annotations

import csv
import html
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

URL = "https://www.dratings.com/sports/ncaa-fbs-football-ratings/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUT_DIR = cfb_paths.INGEST / "dratings"

# Columns after the team cell. "Overall" and "Change" are bare; the rest carry "(rank)".
RANKED = ("sos", "standard", "inference", "vegas")
FIELDS = ["updated_at", "fetched_at", "rank", "dratings_team_id", "team", "record",
          "overall", "change", *(f"{c}{s}" for c in RANKED for s in ("", "_rank"))]

TEAM_CELL = re.compile(
    r'(\d+)\.&nbsp;<a href="/teams/ncaa-fbs-football-ratings/(\d+)-[^"]*">([^<]+)</a>'
    r'\s*<span[^>]*>\(([^)]*)\)</span>'
)
VALUE_RANK = re.compile(r"^(-?[\d.]+)\s*\((\d+)\)$")


def _text(cell: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", cell)).split())


def parse(page: str) -> tuple[str, list[dict]]:
    updated = re.search(r'Updated <time datetime="([^"]+)"', page).group(1)
    start = page.index('id="scroll-ratings"')
    body = page[page.index("<tbody", start):page.index("</tbody>", start)]
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        rank, team_id, team, record = TEAM_CELL.search(cells[0]).groups()
        row = {"updated_at": updated, "rank": int(rank), "dratings_team_id": int(team_id),
               "team": html.unescape(team), "record": record,
               "overall": float(_text(cells[1])), "change": _text(cells[2])}
        for name, cell in zip(RANKED, cells[3:], strict=True):
            value, pos = VALUE_RANK.match(_text(cell)).groups()
            row[name], row[f"{name}_rank"] = float(value), int(pos)
        rows.append(row)
    return updated, rows


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=45).read().decode("utf-8")
    updated, rows = parse(page)
    # ponytail: 130+ FBS teams expected; a short table means the markup changed.
    if len(rows) < 130:
        sys.exit(f"parsed only {len(rows)} teams -- DRatings markup likely changed")
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"fbs_ratings_{updated.replace(':', '')}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({**r, "fetched_at": fetched} for r in rows)
    print(f"{len(rows)} teams, DRatings updated {updated} -> {out}")


if __name__ == "__main__":
    main()
