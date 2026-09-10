"""Flatten the PFF leaderboard pull into tidy per-table CSVs.

Reads $CFB_DATA_ROOT/raw/pff/ and writes $CFB_DATA_ROOT/processed/pff/<table>.csv, one
per table in docs/pff-warehouse-schema.md §3, shaped to docs/pff-sample-schema.sql.

    python scripts/pff_flatten.py                     # every season on disk
    python scripts/pff_flatten.py --seasons 2025
    python scripts/pff_flatten.py --report            # counts only, write nothing
    python scripts/pff_flatten.py --validate          # load the CSVs into the sample DDL

Twenty-nine weekly sources fold into nineteen tables. Nothing about a table's columns is
typed out here: a source declares only where its rows come from and which split families
its column names carry, and the column set is the union of the real headers. That is
deliberate -- the schema doc's prose has been wrong about PFF's actual columns four times
(the `week = 0` sentinel, `player_game_count`, the rushing-direction vocabulary, the
signature-line grain), so the files are the authority and the prose is the summary.

The split unpivot turns `left_deep_attempts` into a row with `split = 'left_deep'` and
`attempts`. Splits are an enumerated set per source, matched longest-first, never a greedy
`(.+?)_(.+)` capture: `facet_passing_summary` has no splits at all, and a greedy rule reads
its `pressure_to_sack_rate` as split `pressure` with metric `to_sack_rate`. Every non-key
column must resolve to a declared split or the run fails -- a silently unrecognized column
is how a metric goes missing.

Ingest-plan criteria this satisfies (docs/pff-ingest-plan.md S3): weekly files only, both
`.csv` and `.json` sources, column union by name across weeks, one rushing-direction view,
types pinned by rule rather than inferred per file, and columns read by name.

`--validate` is the check that matters: the CSVs are read back with the pinned types and
inserted into docs/pff-sample-schema.sql, so a duplicated split label fails on the primary
key and an undeclared direction fails on the CHECK.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.pff_schema import PFF_TABLES, column_type  # noqa: E402

IN_DIR = DATA_ROOT / "raw" / "pff"
OUT_DIR = DATA_ROOT / "processed" / "pff"
SAMPLE_DDL = REPO_ROOT / "docs" / "pff-sample-schema.sql"

# `<stem>_ncaa_<season>[_<division>]_wk<week>.<ext>`; signature exports carry no division.
WEEKLY = re.compile(r"^(?P<stem>.+?)_ncaa_(?P<season>\d{4})(?:_(?:fbs|fcs))?"
                    r"_wk(?P<week>\d+)\.(?P<ext>csv|json)$")

# Spine columns: they identify the row, so they never become metrics and never carry a
# split prefix. `player_game_count` is 1 on every weekly row, so it is dropped outright.
# `team` is `team_name` under another name: the JSON exports carry both. It is identity,
# not a metric, and typing it by rule made it an INTEGER holding "KANSAS".
SPINE = {"player", "player_id", "position", "team_name", "team", "franchise_id"}
DROP = {"player_game_count"}

DEPTH = ("behind_los", "short", "medium", "deep")
DEPTH16 = tuple(f"{side}_{d}" for side in ("left", "center", "right") for d in DEPTH) + DEPTH

# PFF names the time-in-pocket splits `less_*` and `more_*` with the threshold only in the
# report title. Relabelled so the split column says what it means.
RELABEL = {"less": "ttt_under_2_5", "more": "ttt_over_2_5"}

# Columns whose only job is to be the denominator of a `*_percent` on the same row. They
# equal the `all` row's count, so they carry nothing once the table is long.
BASE = re.compile(r"^base_")


@dataclass(frozen=True)
class Source:
    """One weekly report, and how its columns map onto a table."""

    stem: str
    table: str
    splits: tuple[str, ...] = ()
    # Unprefixed columns become this split. None means the source has no split column at
    # all (a wide table); "" means unprefixed columns are dropped rather than kept.
    base_split: str | None = None
    grain: str = "player"          # 'player' | 'franchise'
    nested: str | None = None      # a per-row list to explode, e.g. rushing directions
    nested_key: str | None = None  # the column in that list that extends the key


SOURCES = (
    # --- long split facts ------------------------------------------------------------
    Source("facet_passing_summary", "pff_passing", base_split="all"),
    Source("facet_passing_depth", "pff_passing", DEPTH16, base_split=""),
    Source("facet_passing_pressure", "pff_passing", ("pressure", "no_pressure", "blitz", "no_blitz"),
           base_split=""),   # its unprefixed leftovers are the season grades, not a split
    # An unsplit column is that report's own total, not the `all` row's. Measured: the
    # concept report's `dropbacks` is charted dropbacks and the time-in-pocket report's is
    # timed dropbacks -- neither equals `facet_passing_summary`. Each gets its own label.
    Source("facet_passing_concept", "pff_passing", ("pa", "npa", "screen", "no_screen"),
           base_split="concept"),
    Source("signature_passing_time_in_pocket", "pff_passing", ("less", "more"),
           base_split="ttt_all"),
    Source("facet_receiving_summary", "pff_receiving", base_split="all"),
    Source("facet_receiving_depth", "pff_receiving", DEPTH16, base_split=""),
    Source("facet_receiving_scheme", "pff_receiving", ("man", "zone"), base_split=""),
    Source("facet_receiving_concept", "pff_receiving", ("slot", "screen"), base_split=""),
    Source("facet_defense_coverage", "pff_defense_coverage", base_split="all"),
    Source("facet_defense_coverage_scheme", "pff_defense_coverage", ("man", "zone"), base_split=""),
    Source("signature_defense_slot_coverage", "pff_defense_coverage", base_split="slot"),
    Source("facet_defense_pass_rush", "pff_defense_pass_rush", ("true_pass_set",), base_split="all"),
    # Its unprefixed columns are the outside total: `pressures` == lhs + rhs on 370 of 400
    # rows, and `pass_rush_snaps` disagrees with the facet's on 616. Not the same `all`.
    Source("signature_defense_outside_pass_rush", "pff_defense_pass_rush", ("lhs", "rhs"),
           base_split="outside"),
    Source("facet_offense_pass_blocking", "pff_pass_blocking", ("true_pass_set",), base_split="all"),
    Source("facet_offense_run_blocking", "pff_run_blocking", ("gap", "zone"), base_split="all"),
    # --- wide player-season facts ----------------------------------------------------
    Source("facet_offense_summary", "pff_offense_summary"),
    Source("facet_defense_summary", "pff_defense_summary"),
    Source("facet_defense_run", "pff_defense_run"),
    Source("facet_rushing_summary", "pff_rushing"),
    Source("facet_offense_blocking", "pff_blocking_alignment"),
    Source("facet_passing_allowed_pressure", "pff_passing_allowed_pressure"),
    Source("facet_special_summary", "pff_special_teams"),
    Source("facet_field_goal_summary", "pff_field_goal"),
    Source("facet_kickoff_summary", "pff_kickoff"),
    Source("facet_punting_summary", "pff_punting"),
    Source("facet_return_summary", "pff_return"),
    Source("facet_rushing_direction", "pff_rushing_direction",
           nested="directions", nested_key="direction"),
    # --- team grain ------------------------------------------------------------------
    Source("signature_pass_blocking_efficiency_line", "pff_team_pass_block_week",
           grain="franchise"),
)

# Types are pinned in cfb_system_maker/pff_schema.py, which the loader imports too: one
# rule, two readers. PFF declares a column `integer` on a whole value and `number`
# otherwise in the same column across two responses, so nothing may be inferred here.


def split_of(column: str, source: Source) -> tuple[str, str] | None:
    """(split, metric), or None when the column is not a metric at all.

    Longest-first so `no_screen_x` cannot be read as split `no` and `no_pressure_x` cannot
    be read as split `pressure`.
    """
    if column in SPINE or column in DROP or BASE.match(column):
        return None
    for prefix in sorted(source.splits, key=len, reverse=True):
        if column.startswith(prefix + "_"):
            return RELABEL.get(prefix, prefix), column[len(prefix) + 1:]
    if source.base_split is None:
        return "", column                      # a wide table: no split column
    if source.base_split == "":
        return None
    return source.base_split, column


def read_rows(path: Path) -> list[dict]:
    """A weekly file's rows, CSV or JSON. JSON is the puller's fallback, not a new shape."""
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    body = json.loads(path.read_text(encoding="utf-8"))
    for key, value in body.items():
        if isinstance(value, list):
            return value
    return []


def clean(value) -> str:
    """'' and None become NULL; everything else is written as PFF wrote it."""
    return "" if value is None or value == "" else str(value)


def flatten(seasons: set[int] | None) -> tuple[dict[str, list[dict]], dict[str, set[str]],
                                              collections.Counter, dict[str, str], dict]:
    """(rows, metric columns, dropped columns, franchise names, player spine)."""
    by_stem = {s.stem: s for s in SOURCES}
    # (table, key) -> row. Several sources feed one table at the same split: the `all` row
    # of `pff_defense_pass_rush` comes from both the facet and the signature report, and
    # `pff_passing`'s from three. They merge into one row rather than colliding on the
    # primary key -- which is what the DuckDB round-trip in --validate would otherwise
    # catch as a duplicate.
    merged: dict[str, dict[tuple, dict]] = collections.defaultdict(dict)
    metrics: dict[str, set[str]] = collections.defaultdict(set)
    dropped: collections.Counter = collections.Counter()
    matched: dict[str, set[str]] = collections.defaultdict(set)
    conflicts: collections.Counter = collections.Counter()
    names: dict[str, str] = {}          # franchise_id -> team_name, for the dimension
    people: dict[tuple, dict] = {}      # (season, player_id) -> spine, for the dimension

    for path in sorted(IN_DIR.iterdir()):
        m = WEEKLY.match(path.name) if path.is_file() else None
        if not m or m["stem"] not in by_stem:
            continue
        season, week = int(m["season"]), int(m["week"])
        if seasons and season not in seasons:
            continue
        source = by_stem[m["stem"]]
        pulled_at = path.stat().st_mtime

        for raw in read_rows(path):
            children = raw.get(source.nested) or [{}] if source.nested else [{}]
            for child in children:
                record = {**raw, **child}
                record.pop(source.nested, None)
                key = {"season": season, "week": week,
                       "franchise_id": clean(record.get("franchise_id"))}
                if key["franchise_id"] and record.get("team_name"):
                    names.setdefault(key["franchise_id"], str(record["team_name"]))
                if source.grain == "player":
                    key["player_id"] = clean(record.get("player_id"))
                if key.get("player_id") and record.get("player"):
                    # The spine columns never become metrics, so the player dimension is
                    # collected here, where the row is already open.
                    person = people.setdefault((season, key["player_id"]), {
                        "season": season, "player_id": key["player_id"],
                        "franchise_id": key["franchise_id"], "player": str(record["player"]),
                        "position": clean(record.get("position")), "jersey_number": "",
                        "draft_season": "", "eligible_season": ""})
                    # `jersey_number` rides the same carry-forward as the other two: only
                    # offense_summary, passing_detail and rushing_direction supply it, so the
                    # first row that has it wins and the rest leave it alone.
                    for column in ("jersey_number", "draft_season", "eligible_season"):
                        if not person[column]:
                            person[column] = clean(record.get(column))
                if source.nested_key:
                    key[source.nested_key] = clean(record.get(source.nested_key))

                buckets: dict[str, dict] = collections.defaultdict(dict)
                for column, value in record.items():
                    if source.nested_key and column == source.nested_key:
                        continue
                    parsed = split_of(column, source)
                    if parsed is None:
                        dropped[f"{source.stem}.{column}"] += 1
                        continue
                    split, metric = parsed
                    matched[source.stem].add(split)
                    buckets[split][metric] = clean(value)
                    metrics[source.table].add(metric)

                for split, values in buckets.items():
                    row = dict(key)
                    if split:
                        row["split"] = split
                    identity = tuple(sorted(row.items()))
                    target = merged[source.table].get(identity)
                    if target is None:
                        target = merged[source.table][identity] = dict(row, pulled_at=pulled_at)
                    for metric, value in values.items():
                        seen = target.get(metric)
                        if seen not in (None, "", value) and value != "":
                            conflicts[f"{source.table}.{metric}"] += 1
                        if value != "" or metric not in target:
                            target[metric] = value

    # A declared split that never matched a column is a registry typo, and it would drop a
    # whole family of metrics without any other symptom.
    missing = sorted(f"{s.stem}.{sp}" for s in SOURCES for sp in s.splits
                     if matched.get(s.stem) and RELABEL.get(sp, sp) not in matched[s.stem])
    if missing:
        raise SystemExit("declared splits that matched no column: " + ", ".join(missing))

    rows = {table: list(by_key.values()) for table, by_key in merged.items()}
    if conflicts:
        print("sources disagree on a shared metric (first value kept):")
        for name, n in conflicts.most_common(10):
            print(f"  {name}: {n} rows")
    return rows, metrics, dropped, names, people


# ---------------------------------------------------------------- CFBD team map (S4)

CFBD_RAW = DATA_ROOT / "raw"

# PFF slug -> CFBD school, for the cases no normalization rule reaches. Kept small on
# purpose: a rule that fixes a class of names beats an entry that fixes one.
OVERRIDES = {
    "albany-great-danes": "UAlbany",
    "liu-sharks": "LIU Post",
    "mississippi-rebels": "Ole Miss",
    "southeastern-louisiana-lions": "SE Louisiana",
    "usf-bulls": "South Florida",
    # CFBD files the Florida school as plain `Miami`, so both Miamis normalize to `miami`
    # and the ambiguity rule correctly refuses to guess.
    "miami-fl-hurricanes": "Miami",
    "louisiana-monroe-warhawks": "UL Monroe",
    # PFF carries a longer mascot than CFBD does, so the mascot strip cannot reach the
    # school: `Fightin' Blue Hens` vs `Blue Hens`, `Golden Panthers` vs `Panthers`.
    "delaware-fightin-blue-hens": "Delaware",
    "florida-international-golden-panthers": "Florida International",
    "mcneese-state-cowboys": "McNeese",   # CFBD dropped the `State` in 2024
    "ut-rio-grand-valley-vaqueros": "UT Rio Grande Valley",   # PFF spells it "Grand"
}


def norm(name: str) -> str:
    """Normalize a school name for matching.

    `&` is dropped rather than expanded, because PFF's slug drops it too: `East Texas A&M`
    and `east-texas-am` both reduce to `east texas am`. `St` expands to `State` only when
    it is not the first token -- leading `St` is Saint, as in `st-thomas-tommies`. A
    trailing disambiguator in parentheses (`St. Thomas (MN)`) is cut.
    """
    name = re.sub(r"\s*\([^)]*\)\s*$", " ", name.lower().replace("&", "").replace("'", ""))
    name = re.sub(r"\b(university|univ|college of|the)\b", " ", name)
    tokens = re.sub(r"[^a-z0-9]+", " ", name).split()
    return " ".join("state" if t == "st" and i else t for i, t in enumerate(tokens))


def cfbd_index() -> tuple[dict[str, int], dict[str, set[int]], dict[int, str], set[str]]:
    """(school+mascot -> id, school or alternate name -> ids, id -> school, mascots)."""
    full: dict[str, int] = {}
    school: dict[str, set[int]] = collections.defaultdict(set)
    names: dict[int, str] = {}
    mascots: set[str] = set()
    for path in sorted(CFBD_RAW.glob("teams_2*.json")):
        if "ats" in path.name:
            continue
        for team in json.loads(path.read_text(encoding="utf-8")):
            name, mascot, tid = team.get("school"), team.get("mascot"), team.get("id")
            if not name or tid is None:
                continue
            names[tid] = name
            if mascot:
                full.setdefault(norm(f"{name} {mascot}"), tid)
                mascots.add(norm(mascot))
            school[norm(name)].add(tid)
            for alternate in team.get("alternateNames") or []:
                # `liu`, `cal`, `sou` are abbreviations CFBD files under alternateNames,
                # and they collide across schools. Only real names are indexed.
                if alternate and len(alternate) > 3 and not alternate.isupper():
                    school[norm(alternate)].add(tid)
    return full, school, names, mascots


def map_to_cfbd(franchises: list[dict]) -> collections.Counter:
    """Fill `cfbd_team_id` and `match` in place; returns the tally by match kind."""
    full, school, names, mascots = cfbd_index()
    by_school = {v: k for k, v in names.items()}   # raw name: `Miami` != `Miami (OH)`
    tally: collections.Counter = collections.Counter()
    for row in franchises:
        if row["kind"] != "team":
            tally["allstar or lower division (not mapped)"] += 1
            continue
        slug = row["slug"]
        if slug in OVERRIDES:
            row["cfbd_team_id"], row["match"] = by_school.get(OVERRIDES[slug], ""), "override"
            tally["override"] += 1
            continue
        name = norm(slug.replace("-", " "))
        if name in full:
            row["cfbd_team_id"], row["match"] = full[name], "school+mascot"
            tally["school+mascot"] += 1
            continue
        # Drop the mascot, and only the mascot: the removed suffix has to be a mascot CFBD
        # knows. Stripping trailing tokens freely reads `louisiana monroe warhawks` down to
        # `louisiana` and hands UL Monroe the Ragin' Cajuns' id. The remainder must then
        # name exactly one school -- an ambiguous hit is left unmatched, never guessed.
        tokens = name.split()
        for cut in range(len(tokens) - 1, 0, -1):
            if " ".join(tokens[cut:]) not in mascots:
                continue
            ids = school.get(" ".join(tokens[:cut]))
            if ids and len(ids) == 1:
                row["cfbd_team_id"], row["match"] = next(iter(ids)), "school"
                tally["school"] += 1
                break
        else:
            tally["unmatched"] += 1
    return tally


def dimensions(rows: dict[str, list[dict]], seasons: set[int] | None,
               names: dict[str, str], people: dict) -> None:
    """`pff_franchise` and `pff_player_season`, from the directory and the summaries.

    The directory holds 265 franchises for 2025 -- 136 FBS (group 11) and 129 FCS -- but
    the signature exports take no `--division` and so return rows for franchises outside
    it, all-star squads included. Those are kept with `kind = 'allstar'` rather than
    dropped, because filtering belongs downstream on `cfbd_team_id` (schema doc §5.5).
    """
    seen = {r["franchise_id"] for table in rows.values() for r in table if r.get("franchise_id")}
    franchise: dict[str, dict] = {}
    for path in sorted((IN_DIR / "team").glob("team_directory_*.json")):
        season = int(re.search(r"(\d{4})", path.name)[1])
        if seasons and season not in seasons:
            continue
        for row in json.loads(path.read_text(encoding="utf-8"))["rows"]:
            groups = set(row["groupIds"].split(";"))
            franchise[str(row["franchiseId"])] = {
                "franchise_id": row["franchiseId"], "slug": row["slug"],
                "team_name": row["name"], "kind": "team" if groups & {"11", "12"} else "allstar",
                "cfbd_team_id": "", "match": ""}
    for fid in sorted(seen - set(franchise), key=int):
        # In the data, absent from the directory: an all-star squad, or a division the
        # signature exports reach because they take no `--division`. It still needs an
        # identity, so the name comes from the rows and the slug is synthesized.
        franchise[fid] = {"franchise_id": fid, "slug": f"franchise-{fid}",
                          "team_name": names.get(fid, f"franchise {fid}"),
                          "kind": "allstar", "cfbd_team_id": "", "match": ""}
    rows["pff_franchise"] = list(franchise.values())
    tally = map_to_cfbd(rows["pff_franchise"])
    print("  cfbd map: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))

    rows["pff_player_season"] = list(people.values())


DIMENSION_COLUMNS = {
    "pff_franchise": ["franchise_id", "slug", "team_name", "kind", "cfbd_team_id", "match"],
    "pff_player_season": ["season", "player_id", "franchise_id", "player", "position",
                          "jersey_number", "draft_season", "eligible_season"],
}


def write(rows: dict[str, list[dict]], metrics: dict[str, set[str]]) -> list[tuple[str, int, int]]:
    """One CSV per table; the header is the union of the columns actually produced."""
    import datetime

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for table, table_rows in sorted(rows.items()):
        if table in DIMENSION_COLUMNS:
            header = DIMENSION_COLUMNS[table]
        else:
            keys = [k for k in ("season", "week", "player_id", "franchise_id", "direction",
                                "split") if k in table_rows[0]]
            header = keys + sorted(metrics[table]) + ["pulled_at"]
        path = OUT_DIR / f"{table}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            for row in table_rows:
                row = dict(row)
                if "pulled_at" in row:
                    row["pulled_at"] = datetime.date.fromtimestamp(row["pulled_at"]).isoformat()
                writer.writerow(row)
        written.append((table, len(table_rows), len(header)))
    return written


def validate(tables: set[str]) -> int:
    """Two checks, on the CSVs just written.

    Every table is re-read with the pinned types and '' as NULL -- that is what the loader
    will do, so a column the type rule gets wrong fails here rather than at rebuild time.
    Tables the sample DDL defines are then inserted into it, which is the check that
    matters: a primary-key violation means the unpivot produced two rows for one split,
    and a CHECK violation means a split or direction label nothing declared.
    """
    import duckdb

    con = duckdb.connect()
    con.execute(SAMPLE_DDL.read_text(encoding="utf-8"))
    in_ddl = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'").fetchall()}
    bad = 0
    for table in sorted(tables):
        path = OUT_DIR / f"{table}.csv"
        header = next(csv.reader(path.open(encoding="utf-8")))
        types = {c: column_type(c) for c in header}
        try:
            # `SELECT count(*)` is projection-pushed down and converts no column, so a
            # wrongly typed one passes. Materializing is what the loader does.
            con.execute("CREATE OR REPLACE TEMP TABLE probe AS SELECT * FROM read_csv(?, "
                        "header = true, columns = ?, nullstr = '')", [str(path), types])
            n = con.execute("SELECT count(*) FROM probe").fetchone()[0]
        except duckdb.Error as exc:
            bad += 1
            print(f"  FAIL   {table:30s} types: {str(exc).splitlines()[0][:80]}")
            continue
        if table not in in_ddl:
            print(f"  ok     {table:30s} {n:7d} rows, {len(header):3d} cols (no DDL to check)")
            continue
        shared = [c for c in header if c in {r[0] for r in con.execute(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = 'stg' AND table_name = '{table}'").fetchall()}]
        cols = ", ".join(f'"{c}"' for c in shared)
        try:
            con.execute(f"INSERT INTO stg.{table} ({cols}) SELECT {cols} FROM read_csv(?, "
                        f"header = true, columns = ?, nullstr = '')", [str(path), types])
            print(f"  ok     {table:30s} {n:7d} rows into stg.{table}, keys and CHECKs hold")
        except duckdb.Error as exc:
            bad += 1
            print(f"  FAIL   {table:30s} {str(exc).splitlines()[0][:80]}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", help="comma-separated, e.g. 2025 (default: every season on disk)")
    ap.add_argument("--report", action="store_true", help="counts only, write nothing")
    ap.add_argument("--validate", action="store_true", help="re-read the written CSVs, typed")
    args = ap.parse_args()

    seasons = {int(s) for s in args.seasons.split(",")} if args.seasons else None
    rows, metrics, dropped, names, people = flatten(seasons)

    dimensions(rows, seasons, names, people)
    print(f"{len(rows)} tables from {len(SOURCES)} sources")
    if dropped:
        print(f"  ({len(dropped)} column names dropped by declaration -- spine, base_* "
              f"denominators, and the unsplit duplicates of a split source)")
    if args.report:
        for table, table_rows in sorted(rows.items()):
            splits = {r.get("split", "-") for r in table_rows}
            print(f"  {table:32s} {len(table_rows):8d} rows, {len(metrics[table]):3d} metrics, "
                  f"{len(splits):2d} splits")
        return

    for table, n, cols in write(rows, metrics):
        print(f"  {table:32s} {n:8d} rows, {cols:3d} cols")

    if args.validate:
        print("\nvalidate:")
        raise SystemExit(1 if validate(set(rows)) else 0)


if __name__ == "__main__":
    main()
