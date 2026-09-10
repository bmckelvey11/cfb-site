"""Audit a season's PFF pull on disk: bad files, gaps, and drift.

    python scripts/audit_pff_pull.py                    # 2025, summary
    python scripts/audit_pff_pull.py --season 2026 -v   # every offending file
    python scripts/audit_pff_pull.py --json report.json

The pullers report ok on files that are unusable, so a pull is verified after the fact
rather than trusted. Three failure modes come from docs/pff-cli.md (an export can be
empty, carry PFF's error envelope in the body, or hold headers and nothing else); the
rest are cross-file: the same bytes returned for two different weeks, a facet whose
columns change mid-season and so will not stack, a column whose declared type changes
between responses, and missing (op, week) cells.

Expected coverage is read off disk, not hardcoded: the leaderboard op list comes from
docs/pff-endpoint-reference.md (generated from the OpenAPI document), the week list
from data/raw/pff/team/leagues.json, and the FBS franchise list from that season's
team_directory. Read-only -- it never re-pulls or writes into data/raw.
"""

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import DATA_ROOT  # noqa: E402
from pull_pff_facet import error_code  # noqa: E402
from pull_pff_modeling import (  # noqa: E402
    SKIP_FACETS, TEAM_LEADER_GROUPS, TEAM_REPORTS, TEAM_STATS_CATEGORIES, fbs_rows, ncaa_weeks,
)

PFF_ROOT = DATA_ROOT / "raw" / "pff"
REFERENCE = REPO_ROOT / "docs" / "pff-endpoint-reference.md"
# Metadata, not rows. `team` is a 4-key dict and `columns` a list, so both would be
# counted as payload by a naive max() over the body.
ENVELOPE = {"columns", "category", "league", "scope", "season",
            "report", "section", "team", "week", "weekGroup", "weekTo"}
# `<op>_ncaa_<season>[_<division>][_wk<n>].csv`; signature exports carry no division (c406dcb).
LEADERBOARD = re.compile(r"^(?P<op>.+?)_ncaa_(?P<season>\d{4})(?:_(?P<division>fbs|fcs))?"
                         r"(?:_wk(?P<week>\d+))?\.(?P<ext>csv|json)$")


def leaderboard_ops() -> list[str]:
    """facet-* and signature-* operation ids, from the generated endpoint reference."""
    text = REFERENCE.read_text(encoding="utf-8")
    ops = re.findall(r"^### `((?:facet|signature)-[a-z-]+)`", text, re.MULTILINE)
    return sorted(set(ops) - SKIP_FACETS)


def inspect(path: Path) -> tuple[int | None, list[str] | None, str | None, dict]:
    """(data rows, column keys, defect, declared types). The defect is the first that applies."""
    if path.stat().st_size == 0:
        return None, None, "empty file", {}
    text = path.read_text(encoding="utf-8", errors="replace")
    code = error_code(text)
    if code:
        return None, None, f"error envelope: {code}", {}
    if path.suffix == ".json":
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return None, None, "unparseable JSON", {}
        if not isinstance(body, dict):
            return None, None, "JSON is not an object", {}
        # One key holds the payload: a list (rows, games, leagues) for a leaderboard or
        # a season report, a dict for the player reports, which return one object. The
        # envelope's own keys are not payload -- a team report's `columns` is a list and
        # its `team` a 4-key dict, so either would make an empty report look full.
        # `rows`, where present, is decisive; nothing else in an envelope is named that.
        n = (len(body["rows"]) if isinstance(body.get("rows"), list) else
             max((len(v) for k, v in body.items()
                  if k not in ENVELOPE and isinstance(v, (list, dict))), default=0))
        cols = body.get("columns") if isinstance(body.get("columns"), list) else []
        # A team report declares columns as {key,label,type}; the type is inferred from
        # that response, so it is tracked apart from the column set (see type_drift).
        keys = [c.get("key", str(c)) if isinstance(c, dict) else str(c) for c in cols]
        types = {c["key"]: c.get("type") for c in cols if isinstance(c, dict) and "key" in c}
        return n, (keys or None), ("no rows" if n == 0 else None), types
    lines = [row for row in csv.reader(text.splitlines()) if row]
    if not lines:
        return 0, None, "no rows", {}
    header, data = lines[0], lines[1:]
    if len(header) < 2:
        return len(data), header, "single-column body (export returned no columns)", {}
    return len(data), header, ("header only" if not data else None), {}


def team_op(stem: str, season: int, slugs: frozenset[str]) -> str:
    """`team_report_2025_akron-zips_coverage` -> `team_report.coverage`.

    The entity (team slug, franchise id, week) is dropped and the report qualifier
    kept, so files that should share a column set -- and only those -- share an op."""
    keep, tail, seen_season = [], [], False
    for part in stem.split("_"):
        if part == str(season):
            seen_season = True
        elif not seen_season:
            keep.append(part)
        elif part.isdigit() or re.fullmatch(r"wk\d+", part) or part in slugs:
            continue
        else:
            tail.append(part)
    return "_".join(keep) + ("." + "-".join(tail) if tail else "")


def fbs_slugs(season: int) -> frozenset[str]:
    directory = PFF_ROOT / "team" / f"team_directory_{season}.json"
    if not directory.exists():
        return frozenset()
    return frozenset(r["slug"] for r in fbs_rows(json.loads(directory.read_text(encoding="utf-8"))))


def scan(season: int) -> dict[str, dict]:
    """Every file belonging to `season`, tagged with its (tier, op, week) cell."""
    found, slugs = {}, fbs_slugs(season)
    for path in sorted(PFF_ROOT.rglob("*")):
        if path.is_dir() or path.suffix not in (".csv", ".json"):
            continue
        rel = path.relative_to(PFF_ROOT)
        tier = rel.parts[0] if len(rel.parts) > 1 else "leaderboard"
        if tier == "leaderboard":
            m = LEADERBOARD.match(path.name)
            if not m or int(m["season"]) != season:
                continue
            op, week = m["op"].replace("_", "-"), (int(m["week"]) if m["week"] else None)
        else:
            if f"_{season}_" not in path.name and not path.name.endswith(f"_{season}.json"):
                continue
            wk = re.search(r"_wk(\d+)", path.name)
            week = int(wk[1]) if wk else None
            op = team_op(path.stem, season, slugs)
        rows, cols, defect, types = inspect(path)
        found[str(rel)] = {"tier": tier, "op": op, "week": week, "rows": rows, "cols": cols,
                           "types": types, "defect": defect,
                           "sha": hashlib.sha256(path.read_bytes()).hexdigest()}
    return found


def duplicate_bodies(found: dict) -> list[tuple[str, list[str]]]:
    """Identical bytes for two files of one op that asked different questions.

    Covers the per-team tier as well as the weekly one: a parameter the API ignores
    shows up as the same body under two file names, and nothing else flags it."""
    by_op = collections.defaultdict(lambda: collections.defaultdict(list))
    for rel, f in found.items():
        if f["defect"]:
            continue
        by_op[f["op"].split(".")[0]][f["sha"]].append(rel)  # the qualifier is the question
    return sorted((op, sorted(files)) for op, shas in by_op.items()
                  for files in shas.values() if len(files) > 1)


def column_drift(found: dict) -> tuple[list[tuple[str, dict[frozenset, list[str]]]], list[str]]:
    """(membership drift, order-only drift).

    Files of one op that hold different columns will not stack; files that hold the
    same columns in a different order stack only if the reader goes by name."""
    by_op = collections.defaultdict(lambda: collections.defaultdict(list))
    order = collections.defaultdict(set)
    for rel, f in found.items():
        if f["defect"] or not f["cols"]:
            continue
        by_op[f["op"]][frozenset(f["cols"])].append(rel)
        order[f["op"]].add(tuple(f["cols"]))
    members = [(op, {k: sorted(v) for k, v in shapes.items()})
               for op, shapes in sorted(by_op.items()) if len(shapes) > 1]
    drifted = {op for op, _ in members}
    return members, sorted(op for op, seen in order.items() if len(seen) > 1 and op not in drifted)


def type_drift(found: dict) -> list[tuple[str, str, list[str]]]:
    """One column, two declared types across an op's files.

    PFF infers a JSON column's type from the rows in that response, so `patPercent`
    comes back `integer` for one team and `number` for the next. Harmless to read,
    fatal to a typed load that takes the first file's schema as the contract."""
    by_op = collections.defaultdict(lambda: collections.defaultdict(set))
    for f in found.values():
        for key, kind in (f["types"] or {}).items():
            by_op[f["op"]][key].add(kind)
    return sorted((op, key, sorted(kinds)) for op, keys in by_op.items()
                  for key, kinds in keys.items() if len(kinds) > 1)


def json_only(found: dict) -> list[str]:
    """Leaderboards that landed as JSON and never as CSV.

    The puller falls back to JSON when an export comes back empty (73e8ea6), so the
    data is there -- but a loader globbing `facet_*.csv` drops the facet silently."""
    ext = collections.defaultdict(set)
    for rel, f in found.items():
        if f["tier"] == "leaderboard":
            ext[f["op"]].add(Path(rel).suffix)
    return sorted(op for op, seen in ext.items() if ".csv" not in seen)


def missing_cells(found: dict, weeks: list[int]) -> list[str]:
    """(tier, op, week) cells the pull plan calls for that disk does not have."""
    have = {(f["tier"], f["op"].split(".")[0], f["week"]) for f in found.values()}
    # The facets are pulled season-to-date and per week; the signature stats week only.
    want = [("leaderboard", op, wk) for op in leaderboard_ops()
            for wk in (weeks if op.startswith("signature-") else [None, *weeks])]
    want += [("team", op, wk) for wk in weeks for op in ("games", "team_overview", "team_stats")]
    return sorted({f"{tier}/{op} " + ("season" if wk is None else f"wk{wk}")
                   for tier, op, wk in want if (tier, op, wk) not in have})


def stats_categories(season: int, weeks: list[int]) -> list[str]:
    """team-stats is one file per (week, category); the cell check cannot see a gap inside one."""
    on_disk = {p.name for p in (PFF_ROOT / "team").glob(f"team_stats_{season}_*.json")}
    return sorted(f"team_stats wk{wk} {cat}" for wk in weeks for cat in TEAM_STATS_CATEGORIES
                  if f"team_stats_{season}_wk{wk}_{cat}.json" not in on_disk)


def team_coverage(season: int) -> dict[str, list[str]]:
    """Per-franchise team-tier coverage: which FBS teams are missing which report."""
    directory = PFF_ROOT / "team" / f"team_directory_{season}.json"
    if not directory.exists():
        return {"": ["no team_directory on disk -- coverage unchecked"]}
    rows = fbs_rows(json.loads(directory.read_text(encoding="utf-8")))
    on_disk = {p.name for p in (PFF_ROOT / "team").glob("*.json")}
    gaps = {}
    for row in rows:
        slug, fid = row["slug"], row["franchiseId"]
        wanted = [f"team_schedule_{season}_{slug}.json", f"roster_{season}_{slug}.json",
                  f"team_summary_{season}_{fid}.json",
                  *(f"team_leaders_{season}_{slug}_{g}.json" for g in TEAM_LEADER_GROUPS),
                  f"team_rushing_direction_{season}_{slug}_rows.json",
                  *(f"team_report_{season}_{slug}_{r}.json" for r in TEAM_REPORTS)]
        absent = [w for w in wanted if w not in on_disk]
        if absent:
            gaps[slug] = absent
    return gaps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--json", type=Path, help="write the full report here")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every offending file")
    args = ap.parse_args()
    cut = None if args.verbose else 15

    weeks = ncaa_weeks(json.loads((PFF_ROOT / "team" / "leagues.json").read_text(encoding="utf-8")))
    found = scan(args.season)
    bad = {rel: f for rel, f in found.items() if f["defect"]}
    dupes, types = duplicate_bodies(found), type_drift(found)
    csvless = json_only(found)
    drift, reordered = column_drift(found)
    missing = missing_cells(found, weeks) + stats_categories(args.season, weeks)
    teams = team_coverage(args.season)
    tiers = collections.Counter(f["tier"] for f in found.values())

    print(f"PFF {args.season}: {len(found)} files ({len(found) - len(bad)} usable), "
          f"tiers {dict(tiers)}, weeks {min(weeks)}-{max(weeks)} ({len(weeks)})")

    print(f"\n[defects] {len(bad)} files")
    for defect, n in sorted(collections.Counter(f["defect"] for f in bad.values()).items()):
        print(f"  {n:5d}  {defect}")
    if args.verbose:
        for rel, f in sorted(bad.items()):
            print(f"         {rel}  -- {f['defect']}")

    print(f"\n[duplicate bodies] {len(dupes)} ops answered two questions with the same bytes")
    for op, files in dupes[:cut]:
        print(f"  {op}: {', '.join(Path(f).name for f in files)}")

    print(f"\n[column drift] {len(drift)} ops whose weekly files disagree on columns")
    for op, shapes in drift[:cut]:
        print(f"  {op}: {len(shapes)} column sets, widths {sorted(len(k) for k in shapes)}")
        if args.verbose:
            for cols, files in shapes.items():
                print(f"      {len(cols)} cols: {', '.join(Path(f).name for f in files)}")

    print(f"\n[declared-type drift] {len(types)} columns come back with two types across an op")
    for op, key, kinds in types[:cut]:
        print(f"  {op}.{key}: {'/'.join(kinds)}")

    print(f"\n[json only] {len(csvless)} leaderboards never landed as CSV: {', '.join(csvless)}")

    print(f"\n[missing cells] {len(missing)}")
    for cell in missing[:cut]:
        print(f"  {cell}")

    print(f"\n[team coverage] {len(teams)} FBS franchises with gaps")
    for slug, absent in sorted(teams.items())[:cut]:
        print(f"  {slug}: {len(absent)} missing ({', '.join(absent[:2])}{'...' if len(absent) > 2 else ''})")

    if args.json:
        args.json.write_text(json.dumps(
            {"season": args.season, "files": len(found),
             "defects": {rel: f["defect"] for rel, f in sorted(bad.items())},
             "duplicate_bodies": dupes,
             "column_drift": [(op, [list(c) for c in shapes]) for op, shapes in drift],
             "type_drift": types, "column_order_drift": reordered, "json_only": csvless,
             "missing_cells": missing, "team_gaps": teams}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
