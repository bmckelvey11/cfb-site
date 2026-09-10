"""the-odds-api snapshots -> `data/processed/oddsapi/*.csv`, ready for the loader.

Two tables, both vendor-shaped:

**`oa_odds_tick`** -- one row per outcome per snapshot: `(pulled_at, event_id, book, market,
side)` with its line and price. Long and narrow, the way `stg.an_history_tick` is, because
a wide row would need a column per book.

**`oa_snapshot`** -- one row per pull, carrying the quota fields. They are per-snapshot
metadata and nullable (they mirror response headers, and a missing header lands as null),
so they do not belong on twenty thousand tick rows.

**No `game_id` here, on purpose.** `refresh_cfbd.py` runs every flatten *before* it rebuilds
the warehouse, so a flatten that resolved games would read the previous run's `stg.games` --
and this week's kickoffs are exactly what goes stale. The pair-and-tiebreak resolution lives
in `duckdb_core.build_core`, after `dim_team` and `fact_game` exist. See
docs/oddsapi-game-join-2026-09-10.md.

Every snapshot's rows are kept, including ones identical to the pull before. Content-level
dedupe would save 72% (measured 2026-09-10: 18,776 outcome rows -> 5,309 distinct quotes,
half the series never moving across six snapshots), but storing every sample keeps
"observed unchanged at T" distinguishable from "not observed", and a season is a few
million rows.

    python scripts/oddsapi_flatten.py
    python scripts/oddsapi_flatten.py --list-unresolved

Exits 1 if a team name fails to resolve. The row is still written with the vendor's name --
no data is dropped -- but an unresolved name is a defect a scheduled run has to surface.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.oddsapi_schema import OA_TABLES, candidates, norm  # noqa: E402

IN_DIR = DATA_ROOT / "ingest" / "oddsapi"
OUT_DIR = DATA_ROOT / "processed" / "oddsapi"

TICK_COLUMNS = ["pulled_at", "event_id", "commence_time", "home_team", "away_team",
                "home_school", "away_school", "book", "book_title", "last_update",
                "market", "side", "outcome_name", "line", "odds", "_source_file"]
SNAPSHOT_COLUMNS = ["pulled_at", "sport", "regions", "markets", "odds_format",
                    "requests_last", "requests_used", "requests_remaining",
                    "event_count", "_source_file"]

# `totals` names its outcomes Over/Under. `spreads` and `h2h` name them after a team, so
# `side` comes from matching the event's OWN home/away strings -- not from re-resolving
# through dim_team, which could map two vendor spellings onto one side.
_TOTALS_SIDES = {"over": "over", "under": "under"}


def side_of(outcome_name: str, event: dict) -> str:
    """`home` / `away` / `over` / `under`, or raise.

    Raising rather than defaulting is the point. An unmatched name on a `spreads` outcome
    would otherwise take whichever side the default named, flipping the sign of the handicap
    on a row nothing downstream could audit.
    """
    key = str(outcome_name).strip().lower()
    if key in _TOTALS_SIDES:
        return _TOTALS_SIDES[key]
    if outcome_name == event.get("home_team"):
        return "home"
    if outcome_name == event.get("away_team"):
        return "away"
    raise ValueError(f"outcome {outcome_name!r} is neither Over/Under nor a team in "
                     f"{event.get('away_team')!r} at {event.get('home_team')!r}")


def flatten(paths: list[Path], schools: dict[str, str]
             ) -> tuple[list[dict], list[dict], dict[str, str]]:
    ticks: list[dict] = []
    snapshots: list[dict] = []
    names: dict[str, str] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        events = payload.get("events", [])
        pulled_at = payload.get("pulled_at", "")
        snapshots.append({
            "pulled_at": pulled_at,
            "sport": payload.get("sport", ""),
            "regions": ",".join(payload.get("regions") or []),
            "markets": ",".join(payload.get("markets") or []),
            "odds_format": payload.get("odds_format", ""),
            "requests_last": _blank_if_none(payload.get("requests_last")),
            "requests_used": _blank_if_none(payload.get("requests_used")),
            "requests_remaining": _blank_if_none(payload.get("requests_remaining")),
            "event_count": len(events),
            "_source_file": path.name,
        })
        for event in events:
            home_school = school_of(event.get("home_team", ""), schools)
            away_school = school_of(event.get("away_team", ""), schools)
            for vendor, cfbd in ((event.get("home_team"), home_school),
                                 (event.get("away_team"), away_school)):
                if vendor:
                    names[vendor] = cfbd
            for book in event.get("bookmakers", []):
                for market in book.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        ticks.append({
                            "pulled_at": pulled_at,
                            "event_id": event["id"],
                            "commence_time": event.get("commence_time", ""),
                            "home_team": event.get("home_team", ""),
                            "away_team": event.get("away_team", ""),
                            "home_school": home_school,
                            "away_school": away_school,
                            "book": book.get("key", ""),
                            "book_title": book.get("title", ""),
                            "last_update": book.get("last_update", ""),
                            "market": market.get("key", ""),
                            "side": side_of(outcome.get("name"), event),
                            "outcome_name": outcome.get("name", ""),
                            "line": _blank_if_none(outcome.get("point")),
                            "odds": _blank_if_none(outcome.get("price")),
                            "_source_file": path.name,
                        })
    return ticks, snapshots, names


def _blank_if_none(value):
    """`nullstr = ''` on the load side, so None has to reach the CSV as an empty field.

    `line` is None on every `h2h` row and the quota fields are None whenever the response
    header was missing, so this is the normal case, not an edge one.
    """
    return "" if value is None else value


def cfbd_schools() -> dict[str, str]:
    """`norm`ed school -> CFBD's own spelling, from every `teams_<season>.json` on disk.

    Read from the raw files rather than the warehouse on purpose: this runs before the
    rebuild, so the warehouse holds the previous run's teams while the raw files are what
    the rebuild is about to load.
    """
    out: dict[str, str] = {}
    for path in (DATA_ROOT / "raw").glob("teams_[0-9][0-9][0-9][0-9].json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("data", [])
        for row in rows:
            if isinstance(row, dict) and row.get("school"):
                out.setdefault(norm(row["school"]), row["school"])
    return out


def school_of(name: str, schools: dict[str, str]) -> str:
    """CFBD's spelling for a vendor name, or '' when nothing matches.

    This is the *only* place the mascot strip and the alias list are applied. `core` joins
    on the string this returns rather than re-implementing the rule in SQL, where the two
    copies would drift -- and where the SQL one would not know about `ALIASES` at all.
    """
    for cand in candidates(name):
        if cand in schools:
            return schools[cand]
    return ""


def write(ticks: list[dict], snapshots: list[dict]) -> list[tuple[str, int]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows, columns in (("oa_odds_tick", ticks, TICK_COLUMNS),
                                ("oa_snapshot", snapshots, SNAPSHOT_COLUMNS)):
        path = OUT_DIR / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        written.append((name, len(rows)))
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in-dir", type=Path, default=IN_DIR)
    ap.add_argument("--list-unresolved", action="store_true")
    args = ap.parse_args()

    paths = sorted(args.in_dir.glob("odds_*.json"))
    if not paths:
        print(f"no snapshots in {args.in_dir}")
        return 0

    schools = cfbd_schools()
    if not schools:
        # Reporting "0 unresolved" from having checked nothing reads exactly like success.
        print("  ERROR no data/raw/teams_<season>.json on disk; names cannot be resolved")
        return 1

    ticks, snapshots, names = flatten(paths, schools)
    written = write(ticks, snapshots)
    assert {name for name, _ in written} == set(OA_TABLES), "write() drifted from OA_TABLES"
    for name, rows in written:
        print(f"  {name:16s} {rows:,} rows")

    bad = sorted(vendor for vendor, cfbd in names.items() if not cfbd)
    print(f"  {len(paths)} snapshots, {len(names)} distinct team names, {len(bad)} unresolved")
    if bad:
        print("  UNRESOLVED -- add to cfb_system_maker/oddsapi_schema.ALIASES:")
        for name in (bad if args.list_unresolved else bad[:5]):
            print(f"    {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
