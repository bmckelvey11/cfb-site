"""How far back CFBD serves betting lines, and which providers cover which seasons.

Two independent views of the same question:

* ``--api``   asks CFBD directly (one call per season, default seasonType=regular).
* ``--local`` counts what is already in ``raw.lines`` in the warehouse.

They answer different things: the API is what CFBD *would* serve today, the warehouse
is what has actually been pulled. Both are reported so a gap between them is visible
rather than assumed away.

    python scripts/probe_lines_coverage.py --local
    python scripts/probe_lines_coverage.py --api --years 2010 2011 2012 2013

Needs the fetch venv for --api (see docs/fetch-venv-2026-09-17.md); --local only needs duckdb.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from cfb_system_maker.cfbd_client import find_cfbd_token  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DB_PATH  # noqa: E402

API = "https://api.collegefootballdata.com/lines?year={year}"


def probe_api(years: list[int]) -> None:
    token = find_cfbd_token(REPO / "env.env")
    print(f"{'season':>6}  {'games':>6}  {'w/ lines':>8}  providers")
    for year in years:
        request = urllib.request.Request(
            API.format(year=year), headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        with_lines = sum(1 for game in payload if game.get("lines"))
        providers = sorted(
            {line.get("provider") for game in payload for line in (game.get("lines") or []) if line.get("provider")}
        )
        print(f"{year:>6}  {len(payload):>6}  {with_lines:>8}  {', '.join(providers) or '-'}")


def probe_local(db_path: Path) -> None:
    import duckdb  # noqa: PLC0415

    con = duckdb.connect(str(db_path), read_only=True)
    # json_array_length on an absent key yields NULL, so an empty `lines` array and a
    # missing one both fall out of the > 0 test -- which is the intent: no usable line.
    rows = con.execute(
        """
        select season,
               count(*) as games,
               sum(case when json_array_length(json_extract(payload, '$.lines')) > 0 then 1 else 0 end) as with_lines
        from raw.lines
        group by 1 order by 1
        """
    ).fetchall()
    print(f"{'season':>6}  {'games':>6}  {'w/ lines':>8}")
    for season, games, with_lines in rows:
        print(f"{season:>6}  {games:>6}  {int(with_lines or 0):>8}")

    print("\nproviders by season (rows, not games):")
    per_provider = con.execute(
        """
        with exploded as (
          select season, json_extract_string(line.value, '$.provider') as provider
          from raw.lines, lateral unnest(json_extract(payload, '$.lines')::json[]) as line(value)
        )
        select season, provider, count(*) as n
        from exploded where provider is not null
        group by 1, 2 order by season, n desc
        """
    ).fetchall()
    current = None
    for season, provider, n in per_provider:
        if season != current:
            print(f"\n  {season}: ", end="")
            current = season
        else:
            print(", ", end="")
        print(f"{provider} {n}", end="")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", action="store_true", help="query CFBD (one call per season)")
    parser.add_argument("--local", action="store_true", help="count raw.lines in the warehouse")
    parser.add_argument("--years", type=int, nargs="+", default=[2000, 2005, 2008, 2010, 2011, 2012, 2013])
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    if not args.api and not args.local:
        parser.error("pick at least one of --api / --local")
    if args.api:
        print("=== CFBD API ===")
        probe_api(args.years)
    if args.local:
        if args.api:
            print()
        print("=== warehouse raw.lines ===")
        probe_local(Path(args.db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
