"""Coverage audit: expected vs actual raw/graphql files, driven by the registry.

Re-runnable. Reports per endpoint: expected filenames (from ENDPOINTS + mode)
vs what's on disk, plus which existing files are empty `[]`.

    python scripts/audit_coverage.py --data-dir data --seasons 2012-2025
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as `python scripts/...`
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.scrapers import (  # noqa: E402
    ENDPOINTS, ONCE, SEASON, SEASON_WEEK, GRID, PER_GAME, PER_PLAYER, ON_DEMAND,
)

BULK_MODES = {ONCE, SEASON, SEASON_WEEK, GRID}


def expected_files(ep, seasons: list[int], weeks: range, raw: Path | None = None) -> list[str]:
    if ep.mode in (ONCE, GRID):
        return [f"{ep.name}.json"]
    if ep.mode in (SEASON, PER_GAME, PER_PLAYER):
        floor = ep.min_season or 0
        return [f"{ep.name}_{s}.json" for s in seasons if s >= floor]
    if ep.mode == SEASON_WEEK:
        want = [f"{ep.name}_{s}_wk{w}.json" for s in seasons for w in weeks]
        # Postseason lands in its own `_post_wk` files because postseason week numbering
        # restarts at 1. Which weeks those are is data, not a range: 2025 has postseason
        # in weeks 1, 13 and 14, and at least one season has week 15. Read them off the
        # same games seed the scraper uses, so a missing postseason pull is visible here
        # rather than silently absent.
        for s in seasons:
            want += [f"{ep.name}_{s}_post_wk{w}.json" for w in _postseason_weeks(raw, s)]
        return want
    return []  # ON_DEMAND: never bulk-scraped


def _postseason_weeks(raw: Path | None, season: int) -> list[int]:
    if raw is None:
        return []
    path = raw / f"games_{season}.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return sorted({
        row["week"] for row in rows
        if (row.get("seasonType") or row.get("season_type")) == "postseason"
        and row.get("week") is not None
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(DATA_ROOT))
    ap.add_argument("--seasons", default="2012-2025")
    ap.add_argument("--weeks", default="1-15")
    args = ap.parse_args()

    lo, hi = (int(x) for x in args.seasons.split("-"))
    seasons = list(range(lo, hi + 1))
    wlo, whi = (int(x) for x in args.weeks.split("-"))
    weeks = range(wlo, whi + 1)

    raw = Path(args.data_dir) / "raw"
    on_disk = {p.name for p in raw.glob("*.json")}

    print(f"registry: {len(ENDPOINTS)} endpoints | seasons {lo}-{hi} | weeks {wlo}-{whi}")
    print(f"{'mode':12} {'endpoint':28} {'have':>6} {'want':>6}  missing")
    print("-" * 80)

    totals = {"complete": 0, "partial": 0, "empty": 0, "ondemand": 0, "optin": 0}
    detail: dict[str, list[str]] = {}
    empties: dict[str, list[str]] = {}

    for ep in ENDPOINTS:
        want = expected_files(ep, seasons, weeks, raw)
        if not want:
            totals["ondemand"] += 1
            print(f"{ep.mode:12} {ep.name:28} {'-':>6} {'-':>6}  (on-demand, not bulk)")
            continue
        have = [f for f in want if f in on_disk]
        miss = [f for f in want if f not in on_disk]
        detail[ep.name] = miss

        # Empty `[]` payloads among files we do have. Tested by size, not by parsing:
        # save_raw writes json.dumps(rows, indent=2), so an empty list is exactly the
        # 2 bytes `[]`. Parsing instead would read every file, and data/raw/ holds
        # multi-GB per-game dumps.
        blank = [f for f in have if _is_empty_json(raw / f)]
        if blank:
            empties[ep.name] = blank

        if ep.mode in (PER_GAME, PER_PLAYER):
            totals["optin"] += 1
            tag = " (opt-in fan-out)"
        elif not miss:
            totals["complete"] += 1
            tag = ""
        elif not have:
            totals["empty"] += 1
            tag = ""
        else:
            totals["partial"] += 1
            tag = ""

        summary = "" if not miss else _compact(miss)
        print(f"{ep.mode:12} {ep.name:28} {len(have):>6} {len(want):>6}  {summary}{tag}")

    print("-" * 80)
    print("totals:", totals)

    if empties:
        print("\nEMPTY `[]` FILES (scraped, zero rows — real floor or silent failure):")
        for name, files in sorted(empties.items()):
            yrs = sorted({f.replace(name + "_", "").replace(".json", "") for f in files})
            print(f"  {name:28} {len(files):>3}  {', '.join(yrs)}")

    gql = Path(args.data_dir) / "graphql"
    if gql.exists():
        try:
            from cfb_system_maker.graphql_client import GQL_DEFAULT_TABLES
            got = {p.stem for p in gql.glob("*.json")}
            missing = [t for t in GQL_DEFAULT_TABLES if t not in got]
            have_default = len(GQL_DEFAULT_TABLES) - len(missing)
            # A per-season pull writes `{table}_{season}.json`; count those as shards of
            # their base table, not as separate tables.
            extra = sorted(t for t in got - set(GQL_DEFAULT_TABLES) if not _is_shard(t, got))
            shards = sorted(t for t in got - set(GQL_DEFAULT_TABLES) if _is_shard(t, got))
            print(f"\nGRAPHQL: {have_default}/{len(GQL_DEFAULT_TABLES)} default tables on disk"
                  f" ({len(got)} file(s) total)")
            if missing:
                print("  missing:", ", ".join(missing))
            if extra:
                print("  extra (not in default list):", ", ".join(extra))
            if shards:
                print(f"  per-season shards: {', '.join(shards)}")
        except Exception as exc:  # pragma: no cover
            print("\nGRAPHQL: could not compare —", exc)


_EMPTY_JSON = {b"[]", b"{}"}


def _is_empty_json(path: Path) -> bool:
    """True if the file holds an empty JSON array/object, by size rather than parsing.

    Anything larger than a few bytes has content, so only tiny files are opened.
    """
    try:
        if path.stat().st_size > 8:
            return False
        return path.read_bytes().strip() in _EMPTY_JSON
    except OSError:
        return False


def _is_shard(stem: str, stems: set[str]) -> bool:
    """True if `stem` is `{base}_{season}` for a base table also present on disk."""
    base, sep, tail = stem.rpartition("_")
    return bool(sep) and tail.isdigit() and len(tail) == 4 and base in stems


def _compact(files: list[str]) -> str:
    """Shorten a missing-file list to something readable."""
    if len(files) <= 4:
        return ", ".join(files)
    return f"{len(files)} files: {files[0]} ... {files[-1]}"


if __name__ == "__main__":
    main()
