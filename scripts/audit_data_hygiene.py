"""Audit the data folder and the DuckDB warehouse for hygiene and quality.

Read-only. Prints a markdown report (or writes it with ``--out``), and can write the
findings as JSON (``--json``). Exits 0 unless ``--strict`` and a FAIL finding exists.

    python scripts/audit_data_hygiene.py
    python scripts/audit_data_hygiene.py --out cfb_system_maker/docs/data-audit-rerun.md
    python scripts/audit_data_hygiene.py --checks folder          # no warehouse
    python scripts/audit_data_hygiene.py --checks warehouse --strict

Two halves, because they answer different questions:

* **folder** -- what is on disk under ``CFB_DATA_ROOT``: sizes and ages, stray files
  the pipeline does not own, duplicate copies, raw dumps that would mint an unregistered
  table, empty payloads that are not documented floors, GraphQL dump age, and whether any
  input is newer than the warehouse that was built from it.
* **warehouse** -- what is in ``cfb.duckdb``: expected tables and columns, row counts
  and season coverage, duplicate keys on declared grains, NULL and NaN rates on key
  columns, JSON-typed columns (mixed-type payload fields), join integrity from ``stg``
  into ``core`` and between ``core`` tables, ``games.csv`` against ``core.fact_game``,
  and schema drift against the previous snapshot this script wrote.

Severity is FAIL (a consumer reads wrong or missing data today), WARN (hygiene debt or a
gap that will bite the next person), INFO (measured, nothing to do). Every finding names
the evidence so the report is checkable, and the script never changes anything -- the
proposed deletions and moves are listed for a human.

Complements, not replaces: ``scripts/audit_duckdb.py`` (loader reconciliation, dead
columns, key types), ``scripts/audit_coverage.py`` (scraper registry vs disk),
``scripts/audit_graphql_dump_age.py`` (dump staleness measured against fresh REST),
``scripts/check_an_tick_pin.py`` (the tick schema pin).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT, DB_PATH, current_season  # noqa: E402
from cfb_system_maker.duckdb_load import _SKIP_STEMS, _SUPERSEDED_REST, parse_dump_stem  # noqa: E402
from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_EXCLUDED  # noqa: E402
from cfb_system_maker.scrapers import ENDPOINTS  # noqa: E402

# ----------------------------------------------------------------------------- knowledge

# Top-level entries the pipeline owns. Anything else in the data root is a stray.
DATA_ROOT_OWNED = {
    "cfb.duckdb", "cfb.duckdb.lock", "cfb.duckdb.building", "cfb.duckdb.tmp",
    "cfb.duckdb.wal", "raw", "graphql", "processed", "ingest", "logs", "systems",
    "search_runs", "backups", "audit", ".graphql-pull",
}

# Empty `[]` payloads that are documented data floors (docs/data-coverage.md, "Empty
# files are floors, not failures"). Anything empty outside this map is flagged.
KNOWN_FLOORS: dict[str, range] = {
    "transfer_portal": range(2012, 2021),
    "teams_ats": range(2012, 2019),
    "kicker_paar": range(2012, 2016),
    "talent": range(2012, 2015),
    "returning_production": range(2012, 2014),
    "adjusted_player_passing": range(2012, 2013),
    "adjusted_player_rushing": range(2012, 2013),
    "player_usage": range(2012, 2013),
    "player_usage_ngt": range(2012, 2013),
    "ppa_players_season": range(2012, 2013),
    "ppa_players_season_ngt": range(2012, 2013),
    "player_success_season": range(2012, 2013),
    "player_success_season_ngt": range(2012, 2013),
    "pregame_win_prob": range(2012, 2013),
    "win_probability": range(2012, 2014),
    "core_ratings": range(2012, 2016),  # cfb_system_maker/CLAUDE.md: empty before 2016
}

# Raw stems that are not scraper endpoints but are meant to be there: the two REST dumps
# the loader keeps in `raw` only (`_SUPERSEDED_REST`), and the OpenStreetMap venue match
# `enrich.py` reads from `raw/venue_orientation.json`.
KNOWN_RAW_EXTRAS = frozenset(_SUPERSEDED_REST) | {"venue_orientation"}

# Endpoints `refresh_cfbd.py` re-scrapes daily; the current season's file must exist.
REFRESH_ENDPOINTS = ("games", "lines", "calendar", "conferences", "venues")

# `stg` tables a consumer reads today and a rebuild must produce. `an_scoreboard` and its
# children are the ones a 2026-09-11 OOM dropped; `period`/`line_source` on `game_lines`
# is what the ActionNetwork backfill adds and `core._merge_game_lines` needs.
EXPECTED_STG = (
    "games", "game", "lines", "lines__lines", "game_lines", "lines_provider", "calendar",
    "an_scoreboard", "an_market", "an_team", "an_linescore", "an_history",
    "an_history_tick", "oa_odds_tick", "oa_snapshot", "massey_ranks", "massey_editions",
)
EXPECTED_CORE = (
    "dim_week", "dim_conference", "dim_team", "dim_venue", "dim_lines_provider",
    "dim_coach", "dim_draft_pick", "dim_recruit", "fact_game", "fact_game_line",
    "fact_game_team", "fact_game_odds", "fact_coach_season", "fact_team_talent",
    "fact_game_historical",
)
EXPECTED_COLUMNS = (
    ("stg", "game_lines", "period"),
    ("stg", "game_lines", "line_source"),
)

# Declared grains: (table, key columns). Duplicates here mean a join fans out.
DECLARED_GRAINS = (
    ("stg.games", ("gameId",)),
    ("stg.game", ("gameId",)),
    ("stg.lines", ("gameId",)),
    ("stg.game_lines", ("gameId", "linesProviderId", "period")),
    ("stg.teams", ("teamId", "season")),
    ("stg.venues", ("venueId",)),
    ("stg.calendar", ("season", "week", "seasonType")),
    ("stg.drives", ("driveId",)),
    ("stg.plays", ("playId",)),
    ("stg.weather", ("gameId",)),
    ("stg.an_scoreboard", ("event_id", "_source_file")),
    ("stg.an_history", ("event_id", "book_id", "market_id", "side")),
    ("stg.an_history_tick", ("event_id", "book_id", "market_id", "side", "updated_at")),
    ("stg.oa_odds_tick", ("pulled_at", "event_id", "book", "market", "side")),
    ("stg.massey_ranks", ("date", "massey_id", "system")),
    ("core.fact_game", ("game_id",)),
    ("core.fact_game_line", ("game_id", "provider_key")),
    ("core.fact_game_team", ("game_id", "team_id")),
    ("core.fact_game_odds", ("game_id", "pulled_at", "book", "market", "side")),
    ("core.dim_team", ("team_id",)),
)

# Key columns whose NULL rate matters. (table, column, max_null_fraction).
KEY_NULL_LIMITS = (
    ("stg.games", "gameId", 0.0), ("stg.games", "homeTeamId", 0.0),
    ("stg.games", "awayTeamId", 0.0), ("stg.games", "startDate", 0.0),
    ("stg.games", "season", 0.0),
    ("stg.lines", "gameId", 0.0),
    ("stg.game_lines", "gameId", 0.0), ("stg.game_lines", "linesProviderId", 0.0),
    ("stg.game_lines", "spread", 0.05), ("stg.game_lines", "overUnder", 0.15),
    ("stg.an_history", "event_id", 0.0), ("stg.an_history", "line", 0.02),
    ("stg.an_history_tick", "event_id", 0.0), ("stg.an_history_tick", "updated_at", 0.0),
    ("stg.oa_odds_tick", "event_id", 0.0), ("stg.oa_odds_tick", "pulled_at", 0.0),
    ("core.fact_game", "game_id", 0.0), ("core.fact_game", "home_team_id", 0.0),
    ("core.fact_game", "away_team_id", 0.0), ("core.fact_game", "start_date", 0.0),
    ("core.fact_game_line", "spread_close", 0.05),
    ("core.fact_game_line", "total_close", 0.15),
    ("core.fact_game_odds", "game_id", 0.0), ("core.fact_game_odds", "odds", 0.0),
)

# Join integrity: (label, child, child col, parent, parent col, child predicate, must be 0).
# `must be 0` False rows are measured and reported as INFO -- known, documented gaps.
FK_CHECKS = (
    ("core.fact_game.game_id -> stg.games", "core.fact_game", "game_id",
     "stg.games", "gameId", None, True),
    ("core.fact_game_line.game_id -> core.fact_game", "core.fact_game_line", "game_id",
     "core.fact_game", "game_id", None, True),
    ("core.fact_game_line.provider_key -> core.dim_lines_provider", "core.fact_game_line",
     "provider_key", "core.dim_lines_provider", "provider_key", None, True),
    ("core.fact_game_team.game_id -> core.fact_game", "core.fact_game_team", "game_id",
     "core.fact_game", "game_id", None, True),
    ("core.fact_game_odds.game_id -> core.fact_game", "core.fact_game_odds", "game_id",
     "core.fact_game", "game_id", None, True),
    ("core.fact_coach_season.coach_id -> core.dim_coach", "core.fact_coach_season",
     "coach_id", "core.dim_coach", "coach_id", None, True),
    ("core.fact_game.venue_id -> core.dim_venue", "core.fact_game", "venue_id",
     "core.dim_venue", "venue_id", "venue_id IS NOT NULL", True),
    ("core.fact_game.home_conference_id -> core.dim_conference", "core.fact_game",
     "home_conference_id", "core.dim_conference", "conference_id",
     "home_conference_id IS NOT NULL", True),
    # Name-derived ids for opponents outside CFBD's team table (DII/DIII/NAIA schools).
    ("core.fact_game.home_team_id -> core.dim_team", "core.fact_game", "home_team_id",
     "core.dim_team", "team_id", None, False),
    ("core.fact_game.away_team_id -> core.dim_team", "core.fact_game", "away_team_id",
     "core.dim_team", "team_id", None, False),
    ("core.fact_game_team.team_id -> core.dim_team", "core.fact_game_team", "team_id",
     "core.dim_team", "team_id", None, False),
    ("core.fact_team_talent.team_id -> core.dim_team", "core.fact_team_talent", "team_id",
     "core.dim_team", "team_id", "team_id IS NOT NULL", False),
    # Postseason weeks: the calendar carries one `postseason` row per season.
    ("core.fact_game (season, week, season_type) -> core.dim_week", "core.fact_game",
     None, "core.dim_week", None, None, False),
    ("stg.an_history_tick -> stg.an_history", "stg.an_history_tick", None,
     "stg.an_history", None, None, True),
)

# Tables whose season coverage is reported, with the season column.
COVERAGE_TABLES = (
    ("stg.games", "season"), ("stg.game", "season"), ("stg.lines", "season"),
    ("stg.plays", "season"), ("stg.drives", "season"), ("stg.game_team_stats", "season"),
    ("stg.win_probability", "season"), ("stg.weather", "season"), ("stg.sp", "year"),
    ("stg.elo", "year"), ("stg.fpi", "year"), ("stg.talent", "year"),
    ("stg.team_talent", "year"), ("stg.massey_ranks", "season"),
    ("stg.pff_passing", "season"), ("stg.an_scoreboard", "season"),
    ("core.fact_game", "season"), ("core.fact_game_historical", "season"),
    ("core.fact_coach_season", "season"),
)

# ----------------------------------------------------------------------------- plumbing


@dataclass
class Finding:
    severity: str  # FAIL | WARN | INFO
    code: str
    message: str


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.findings: list[Finding] = []

    def section(self, title: str) -> None:
        self.lines += ["", "## " + title, ""]

    def add(self, *lines: str) -> None:
        self.lines.extend(lines)

    def table(self, header: list[str], rows: list[list[object]]) -> None:
        self.lines.append("| " + " | ".join(header) + " |")
        self.lines.append("|" + "|".join("---" for _ in header) + "|")
        for row in rows:
            self.lines.append("| " + " | ".join(str(c) for c in row) + " |")
        self.lines.append("")

    def fail(self, code: str, message: str) -> None:
        self.findings.append(Finding("FAIL", code, message))

    def warn(self, code: str, message: str) -> None:
        self.findings.append(Finding("WARN", code, message))

    def info(self, code: str, message: str) -> None:
        self.findings.append(Finding("INFO", code, message))


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _age_days(path: Path, now: datetime) -> float:
    return (now - _mtime(path)).total_seconds() / 86400


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _tree_stats(path: Path) -> tuple[int, int, datetime | None]:
    """(bytes, files, newest mtime) for a file or a directory tree."""
    if path.is_file():
        return path.stat().st_size, 1, _mtime(path)
    size, files, newest = 0, 0, None
    for p in path.rglob("*"):
        if p.is_file():
            st = p.stat()
            size += st.st_size
            files += 1
            m = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            newest = m if newest is None or m > newest else newest
    return size, files, newest


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _quote_key(cols: tuple[str, ...]) -> str:
    return ", ".join(f'"{c}"' for c in cols)


# ----------------------------------------------------------------------------- pure logic
# Kept free of I/O so tests can drive them with lists.


def stray_entries(names: list[str]) -> list[str]:
    """Top-level data-root names the pipeline does not own."""
    return sorted(n for n in names if n not in DATA_ROOT_OWNED)


def group_raw_stems(stems: list[str]) -> dict[str, list[tuple[str, int | None]]]:
    """Group dump stems the way the loader does: table -> [(stem, season)]."""
    groups: dict[str, list[tuple[str, int | None]]] = defaultdict(list)
    for stem in stems:
        if stem in _SKIP_STEMS or stem.startswith("_"):
            continue
        name, season, _, _ = parse_dump_stem(stem)
        groups[name].append((stem, season))
    return dict(groups)


def classify_empty(name: str, season: int | None) -> str:
    """'floor' when docs say this endpoint has no data for that season, else 'unexpected'."""
    floor = KNOWN_FLOORS.get(name)
    if floor is not None and season is not None and season in floor:
        return "floor"
    return "unexpected"


def season_gaps(seasons: list[int]) -> list[int]:
    if not seasons:
        return []
    have = set(seasons)
    return [y for y in range(min(seasons), max(seasons) + 1) if y not in have]


def find_duplicates(hashes: dict[str, str]) -> list[list[str]]:
    """Groups of paths sharing a content hash, largest group first."""
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path, digest in hashes.items():
        by_hash[digest].append(path)
    return sorted((sorted(v) for v in by_hash.values() if len(v) > 1), key=len, reverse=True)


def diff_schemas(
    old: dict[str, dict[str, str]], new: dict[str, dict[str, str]]
) -> dict[str, list[str]]:
    """Compare {table: {column: type}} snapshots."""
    out: dict[str, list[str]] = {
        "tables_added": [], "tables_removed": [], "columns_added": [],
        "columns_removed": [], "types_changed": [],
    }
    out["tables_added"] = sorted(set(new) - set(old))
    out["tables_removed"] = sorted(set(old) - set(new))
    for t in sorted(set(old) & set(new)):
        oc, nc = old[t], new[t]
        for c in sorted(set(nc) - set(oc)):
            out["columns_added"].append(f"{t}.{c} {nc[c]}")
        for c in sorted(set(oc) - set(nc)):
            out["columns_removed"].append(f"{t}.{c} {oc[c]}")
        for c in sorted(set(oc) & set(nc)):
            if oc[c] != nc[c]:
                out["types_changed"].append(f"{t}.{c} {oc[c]} -> {nc[c]}")
    return out


# ----------------------------------------------------------------------------- folder


def check_folder(rep: Report, root: Path, now: datetime, stale_days: int,
                 loaded_at: datetime | None) -> None:
    season = current_season(now)
    rep.section("Data folder inventory")
    rep.add(f"Root `{root}`. Sizes are whole trees; ages are from the newest file.", "")
    rows = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        size, files, newest = _tree_stats(entry)
        age = f"{(now - newest).total_seconds() / 86400:.1f}d" if newest else "-"
        owned = "" if entry.name in DATA_ROOT_OWNED else " **stray**"
        rows.append([f"`{entry.name}`{owned}", _fmt_bytes(size), files, age])
    rep.table(["entry", "size", "files", "newest"], rows)

    for name in stray_entries([p.name for p in root.iterdir()]):
        p = root / name
        rep.warn("stray-root-file", f"`{name}` in the data root is not a pipeline output "
                 f"({_fmt_bytes(_tree_stats(p)[0])}, {_age_days(p, now):.0f}d old)")

    # ---- backups / regenerable copies
    backups = root / "backups"
    if backups.is_dir():
        files = sorted(p for p in backups.iterdir() if p.is_file())
        size = sum(f.stat().st_size for f in files)
        rep.add(f"`backups/`: {len(files)} file(s), {_fmt_bytes(size)}: "
                + ", ".join(f"`{f.name}` ({_age_days(f, now):.0f}d)" for f in files), "")
        if size > 2 * 2**30:
            rep.warn("backups-size", f"`backups/` holds {_fmt_bytes(size)} across {len(files)} "
                     f"warehouse copies; every one is rebuildable from raw with refresh_cfbd.py")
    fb = root / "processed" / "feature_backups"
    if fb.is_dir():
        size, files, _ = _tree_stats(fb)
        if files:
            rep.info("feature-backups", f"`processed/feature_backups/` {_fmt_bytes(size)} in "
                     f"{files} file(s); regenerable with `enrich`")

    # ---- raw dumps
    rep.section("Raw dumps (`raw/*.json`) vs the loader")
    raw = root / "raw"
    json_paths = {p.stem: p for p in raw.glob("*.json")} if raw.is_dir() else {}
    groups = group_raw_stems(list(json_paths))
    registry = {e.name: e for e in ENDPOINTS}
    rows, empties_unexpected, empties_floor, unregistered = [], [], [], []
    for name, members in sorted(groups.items()):
        seasons = sorted({s for _, s in members if s is not None})
        paths = [json_paths[stem] for stem, _ in members]
        empties = [(stem, s) for stem, s in members if json_paths[stem].stat().st_size <= 2]
        newest = max(_mtime(p) for p in paths)
        age = (now - newest).total_seconds() / 86400
        ep = registry.get(name)
        mode = ep.mode if ep else ("known extra" if name in KNOWN_RAW_EXTRAS else "**unregistered**")
        if ep is None and name not in KNOWN_RAW_EXTRAS:
            unregistered.append(name)
        for stem, s in empties:
            if classify_empty(name, s) == "floor":
                empties_floor.append(stem)
            else:
                empties_unexpected.append(stem)
        gaps = season_gaps(seasons)
        flags = []
        if gaps:
            flags.append("gaps " + ",".join(map(str, gaps)))
        if ep and ep.mode in ("season", "season_week") and seasons and seasons[-1] < season:
            flags.append(f"no {season}")
        rows.append([f"`{name}`", mode, len(members),
                     f"{seasons[0]}-{seasons[-1]}" if seasons else "-",
                     len(empties), f"{age:.0f}d", "; ".join(flags)])
    rep.table(["table", "mode", "files", "seasons", "empty", "newest", "flags"], rows)
    for name in unregistered:
        stems = ", ".join(f"`{stem}`" for stem, _ in groups[name])
        rep.warn("unregistered-raw-stem", f"`raw/{name}` is not a scraper endpoint; the loader "
                 f"mints `raw.{name}`/`stg.{name}` from it anyway ({stems}). Point-in-time "
                 f"snapshots belong in `ingest/`, which is not globbed")
    for stem in empties_unexpected:
        rep.warn("empty-payload-undocumented",
                 f"`raw/{stem}.json` is empty and is not a documented floor")
    rep.add(f"Empty payloads: {len(empties_floor)} documented floors, "
            f"{len(empties_unexpected)} undocumented"
            + (": " + ", ".join(f"`{s}`" for s in empties_unexpected)
               if empties_unexpected else ""), "")
    for name in REFRESH_ENDPOINTS:
        p = raw / f"{name}_{season}.json"
        if (name in registry and registry[name].mode == "season"
                and (not p.exists() or p.stat().st_size <= 2)):
            rep.fail("refresh-endpoint-missing", f"`raw/{p.name}` missing or empty; "
                     f"refresh_cfbd.py re-scrapes it daily")
    per_week = sorted(n for n, m in groups.items()
                      if registry.get(n) and registry[n].mode == "season_week")
    missing_week = [n for n in per_week if not any(s == season for _, s in groups[n])]
    if missing_week:
        rep.info("season-week-not-current", f"{len(missing_week)} season_week endpoint(s) have no "
                 f"{season} files (not on the daily refresh): "
                 + ", ".join(f"`{n}`" for n in missing_week))
    non_json = (sorted(p.name for p in raw.iterdir() if p.is_file() and p.suffix != ".json")
                if raw.is_dir() else [])
    if non_json:
        rep.info("raw-non-json", "non-JSON files in `raw/`: " + ", ".join(f"`{n}`" for n in non_json)
                 + " (`actionnetwork_odds.csv` loads as `raw.an_odds`; the rest are ignored)")
    skipped = sorted(s for s in json_paths if s in _SKIP_STEMS or s.startswith("_"))
    if skipped:
        rep.info("raw-skipped-stems", "loader-skipped stems: " + ", ".join(f"`{s}`" for s in skipped))

    # ---- graphql dumps
    rep.section("GraphQL dumps (`graphql/*.json`)")
    gql = root / "graphql"
    rows = []
    if gql.is_dir():
        ggroups: dict[str, list[Path]] = defaultdict(list)
        for p in sorted(gql.glob("*.json")):
            name, _, _, _ = parse_dump_stem(p.stem)
            ggroups[name].append(p)
        stale = 0
        for name, paths in sorted(ggroups.items()):
            whole = [p for p in paths if parse_dump_stem(p.stem)[1] is None]
            per_season = [p for p in paths if parse_dump_stem(p.stem)[1] is not None]
            newest = max(_mtime(p) for p in paths)
            oldest = min(_mtime(p) for p in paths)
            size = sum(p.stat().st_size for p in paths)
            note = ""
            if whole and per_season:
                note = "**whole-corpus file beside per-season files**"
                rep.warn("gql-shadow-dump", f"`graphql/{whole[0].name}` "
                         f"({_age_days(whole[0], now):.0f}d, {_fmt_bytes(whole[0].stat().st_size)}) "
                         f"loads alongside {len(per_season)} per-season `{name}_<season>.json` "
                         f"files; its rows carry no season (audit S6, 2026-09-02)")
            elif name in GQL_EXCLUDED and name not in GQL_ENTITY_TO_RAW:
                note = "excluded from the default pull"
            newest_age = (now - newest).total_seconds() / 86400
            stale += newest_age > stale_days
            rows.append([f"`{name}`", len(paths), _fmt_bytes(size), f"{newest_age:.0f}d",
                         f"{(now - oldest).total_seconds() / 86400:.0f}d", note])
        rep.table(["entity", "files", "size", "newest", "oldest", "note"], rows)
        if stale:
            rep.info("gql-dumps-stale", f"{stale} GraphQL dump(s) older than {stale_days}d; only "
                     f"`game` and `gameLines` are on the refresh path "
                     f"(docs/graphql-dump-staleness-2026-09-11.md)")

    # ---- inputs newer than the warehouse
    rep.section("Inputs vs the warehouse load")
    if loaded_at is None:
        rep.add("No `meta.load_report` to compare against (warehouse checks skipped).", "")
    else:
        rep.add(f"Warehouse loaded at {loaded_at:%Y-%m-%d %H:%M:%S} UTC.", "")
        newer: list[tuple[str, datetime]] = []
        inputs = list(json_paths.values()) + (sorted(gql.glob("*.json")) if gql.is_dir() else [])
        for p in inputs:
            if p.stem in _SKIP_STEMS or p.stem.startswith("_"):
                continue
            if _mtime(p) > loaded_at:
                newer.append((str(p.relative_to(root)), _mtime(p)))
        an = raw / "actionnetwork"
        if an.is_dir():
            newer += [(str(p.relative_to(root)), _mtime(p))
                      for p in an.glob("*.json") if _mtime(p) > loaded_at]
        for rel in ("processed/actionnetwork/an_history_tick.csv",
                    "processed/oddsapi/oa_odds_tick.csv", "processed/oddsapi/oa_snapshot.csv",
                    "processed/massey/massey_ranks.csv"):
            p = root / rel
            if p.exists() and _mtime(p) > loaded_at:
                newer.append((rel, _mtime(p)))
        pff = root / "processed" / "pff"
        if pff.is_dir():
            newer += [(str(p.relative_to(root)), _mtime(p))
                      for p in pff.glob("*.csv") if _mtime(p) > loaded_at]
        if newer:
            rep.warn("inputs-newer-than-warehouse", f"{len(newer)} input file(s) are newer than "
                     f"the warehouse load; the warehouse is stale until the next refresh_cfbd.py run")
            latest = sorted(newer, key=lambda x: x[1], reverse=True)[:8]
            rep.add(f"{len(newer)} file(s) newer than the load, e.g. "
                    + ", ".join(f"`{n}`" for n, _ in latest), "")
        else:
            rep.add("Every raw, GraphQL, ActionNetwork and processed input predates the load.", "")

    # ---- duplicates among loose files (data root and processed top level)
    rep.section("Duplicate files")
    candidates = [p for p in root.iterdir() if p.is_file() and p.suffix != ".duckdb"]
    proc = root / "processed"
    if proc.is_dir():
        candidates += [p for p in proc.iterdir() if p.is_file()]
    hashes = {str(p.relative_to(root)): _sha1(p)
              for p in candidates if p.stat().st_size < 200 * 2**20}
    dupes = find_duplicates(hashes)
    if dupes:
        for group in dupes:
            rep.warn("duplicate-file", "identical content: " + ", ".join(f"`{p}`" for p in group))
        rep.add(f"{len(dupes)} duplicate group(s) among {len(hashes)} loose files.", "")
    else:
        rep.add(f"No byte-identical pairs among {len(hashes)} loose files.", "")


# ----------------------------------------------------------------------------- warehouse


def _table_exists(con: duckdb.DuckDBPyConnection, qualified: str) -> bool:
    schema, name = qualified.split(".", 1)
    return con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE schema_name=? AND table_name=?",
        [schema, name],
    ).fetchone()[0] == 1


def _columns(con: duckdb.DuckDBPyConnection, qualified: str) -> dict[str, str]:
    schema, name = qualified.split(".", 1)
    return dict(con.execute(
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_schema=? AND table_name=? ORDER BY ordinal_position",
        [schema, name],
    ).fetchall())


def check_catalog(rep: Report, con: duckdb.DuckDBPyConnection,
                  db_path: Path | None) -> datetime | None:
    rep.section("Warehouse catalog")
    if db_path is not None and db_path.exists():
        rep.add(f"`{db_path}`: {_fmt_bytes(db_path.stat().st_size)}.", "")
    rows = con.execute(
        "SELECT schema_name, count(*), sum(estimated_size) FROM duckdb_tables()"
        " GROUP BY 1 ORDER BY 1"
    ).fetchall()
    rep.table(["schema", "tables", "rows"], [[s, n, f"{int(r):,}"] for s, n, r in rows])
    loaded_at = None
    if _table_exists(con, "meta.load_report"):
        loaded_at, n, errors = con.execute(
            "SELECT max(loaded_at), count(*), count(error) FROM meta.load_report"
        ).fetchone()
        rep.add(f"`meta.load_report`: {n} loads at {loaded_at} UTC, {errors} with errors.", "")
        for s, name, err in con.execute(
            "SELECT schema, name, error FROM meta.load_report WHERE error IS NOT NULL"
        ).fetchall():
            rep.fail("load-error", f"`{s}.{name}`: {err}")
        loaded_at = loaded_at.replace(tzinfo=timezone.utc) if loaded_at else None
    else:
        rep.fail("no-load-report", "`meta.load_report` is missing; not a loader-built file")
    zero = [f"{s}.{t}" for s, t in con.execute(
        "SELECT schema_name, table_name FROM duckdb_tables() WHERE estimated_size = 0"
        " ORDER BY 1, 2"
    ).fetchall()]
    if zero:
        rep.info("zero-row-tables", "empty tables: " + ", ".join(f"`{t}`" for t in zero))
    missing = [f"stg.{t}" for t in EXPECTED_STG if not _table_exists(con, f"stg.{t}")]
    missing += [f"core.{t}" for t in EXPECTED_CORE if not _table_exists(con, f"core.{t}")]
    for t in missing:
        rep.fail("expected-table-missing", f"`{t}` is missing")
    for schema, table, column in EXPECTED_COLUMNS:
        q = f"{schema}.{table}"
        if _table_exists(con, q) and column not in _columns(con, q):
            rep.fail("expected-column-missing", f"`{q}.{column}` is missing (the ActionNetwork "
                     f"backfill did not widen the table)")
    if not missing:
        rep.add(f"All {len(EXPECTED_STG)} expected `stg` and {len(EXPECTED_CORE)} expected "
                f"`core` tables exist.", "")
    return loaded_at


def check_row_counts(rep: Report, con: duckdb.DuckDBPyConnection) -> None:
    rep.section("Row counts")
    rows = con.execute(
        "SELECT schema_name, table_name, estimated_size, column_count FROM duckdb_tables()"
        " ORDER BY schema_name, table_name"
    ).fetchall()
    rep.add(f"<details><summary>{len(rows)} tables</summary>", "")
    rep.table(["table", "rows", "cols"],
              [[f"`{s}.{t}`", f"{int(n):,}", c] for s, t, n, c in rows])
    rep.add("</details>", "")


def check_coverage(rep: Report, con: duckdb.DuckDBPyConnection, now: datetime) -> None:
    season = current_season(now)
    rep.section("Season coverage")
    rows = []
    for table, col in COVERAGE_TABLES:
        if not _table_exists(con, table):
            rows.append([f"`{table}`", "-", "-", "-", "-", "missing"])
            continue
        if col not in _columns(con, table):
            rows.append([f"`{table}`", "-", "-", "-", "-", f"no `{col}` column"])
            continue
        seasons = [int(s) for (s,) in con.execute(
            f'SELECT DISTINCT "{col}" FROM {table} WHERE "{col}" IS NOT NULL ORDER BY 1'
        ).fetchall()]
        nulls = con.execute(
            f'SELECT count(*) FILTER (WHERE "{col}" IS NULL) FROM {table}'
        ).fetchone()[0]
        gaps = season_gaps([s for s in seasons if s >= 2012])
        flags = []
        if gaps:
            flags.append("gaps " + ",".join(map(str, gaps)))
        if nulls:
            flags.append(f"{nulls:,} NULL")
        if seasons and seasons[-1] < season:
            flags.append(f"ends {seasons[-1]}")
        rows.append([f"`{table}`", col, f"{seasons[0]}-{seasons[-1]}" if seasons else "-",
                     len(seasons), nulls, "; ".join(flags)])
    rep.table(["table", "col", "range", "seasons", "null seasons", "flags"], rows)


def check_grains(rep: Report, con: duckdb.DuckDBPyConnection) -> None:
    rep.section("Duplicate keys on declared grains")
    rows = []
    for table, keys in DECLARED_GRAINS:
        if not _table_exists(con, table):
            rows.append([f"`{table}`", ", ".join(keys), "-", "missing"])
            continue
        cols = _columns(con, table)
        absent = [k for k in keys if k not in cols]
        if absent:
            rows.append([f"`{table}`", ", ".join(keys), "-", "no column " + ", ".join(absent)])
            continue
        n, d = con.execute(
            f"SELECT count(*), count(DISTINCT ({_quote_key(keys)})) FROM {table}"
        ).fetchone()
        dup = n - d
        if dup:
            rep.fail("grain-duplicates",
                     f"`{table}` has {dup:,} duplicate rows on ({', '.join(keys)})")
        rows.append([f"`{table}`", ", ".join(keys), f"{n:,}", f"**{dup:,}**" if dup else "0"])
    rep.table(["table", "key", "rows", "dupes"], rows)


def check_nulls_and_nan(rep: Report, con: duckdb.DuckDBPyConnection) -> None:
    rep.section("NULL and NaN rates on key columns")
    rows = []
    for table, col, limit in KEY_NULL_LIMITS:
        if not _table_exists(con, table) or col not in _columns(con, table):
            rows.append([f"`{table}`", col, "-", "-", "missing"])
            continue
        n, nulls = con.execute(
            f'SELECT count(*), count(*) - count("{col}") FROM {table}'
        ).fetchone()
        frac = nulls / n if n else 0.0
        flag = ""
        if frac > limit:
            flag = f"**over {limit:.0%}**"
            rep.warn("key-null-rate", f"`{table}.{col}` is {frac:.1%} NULL "
                     f"({nulls:,}/{n:,}), limit {limit:.0%}")
        rows.append([f"`{table}`", col, f"{n:,}", f"{frac:.2%}", flag])
    rep.table(["table", "column", "rows", "NULL", "flag"], rows)

    # JSON-typed columns are payload fields the explode could not type: a mix of numbers
    # and the GraphQL "NaN" string, or a genuinely mixed payload. Neither compares cleanly.
    json_cols = con.execute(
        "SELECT table_name, column_name FROM information_schema.columns"
        " WHERE table_schema='stg' AND data_type='JSON' ORDER BY 1, 2"
    ).fetchall()
    if json_cols:
        rep.warn("json-typed-columns", "JSON-typed `stg` columns (mixed-type payload fields): "
                 + ", ".join(f"`{t}.{c}`" for t, c in json_cols))
    # NaN in any DOUBLE column of stg/core: coalesce treats it as a value.
    nan_hits = []
    doubles = con.execute(
        "SELECT table_schema, table_name, column_name FROM information_schema.columns"
        " WHERE table_schema IN ('stg', 'core') AND data_type IN ('DOUBLE', 'FLOAT', 'REAL')"
        " ORDER BY 1, 2, 3"
    ).fetchall()
    by_table: dict[tuple[str, str], list[str]] = defaultdict(list)
    for s, t, c in doubles:
        by_table[(s, t)].append(c)
    for (s, t), cols in by_table.items():
        exprs = ", ".join(f'count(*) FILTER (WHERE isnan("{c}"))' for c in cols)
        counts = con.execute(f'SELECT {exprs} FROM "{s}"."{t}"').fetchone()
        nan_hits += [(f"{s}.{t}.{c}", int(v)) for c, v in zip(cols, counts) if v]
    if nan_hits:
        rep.warn("nan-values", f"NaN in {len(nan_hits)} DOUBLE column(s): "
                 + ", ".join(f"`{c}` ({v:,})" for c, v in nan_hits))
    rep.add(f"Scanned {len(doubles)} DOUBLE columns in {len(by_table)} tables for NaN: "
            f"{len(nan_hits)} column(s) carry any. JSON-typed `stg` columns: {len(json_cols)}.",
            "")


def check_joins(rep: Report, con: duckdb.DuckDBPyConnection) -> None:
    rep.section("Join integrity")
    rows = []
    for label, child, ccol, parent, pcol, where, must_be_zero in FK_CHECKS:
        if not (_table_exists(con, child) and _table_exists(con, parent)):
            rows.append([label, "-", "-", "missing table"])
            continue
        if ccol is None and child == "core.fact_game":
            sql = ("SELECT count(*) FROM core.fact_game f LEFT JOIN core.dim_week w"
                   " ON w.season=f.season AND w.week=f.week AND w.season_type=f.season_type"
                   " WHERE w.season IS NULL")
        elif ccol is None:
            sql = ("SELECT count(*) FROM stg.an_history_tick t LEFT JOIN stg.an_history h"
                   " ON h.event_id=t.event_id AND h.book_id=t.book_id"
                   " AND h.market_id=t.market_id AND h.side IS NOT DISTINCT FROM t.side"
                   " WHERE h.event_id IS NULL")
        else:
            cond = f" AND c.{where}" if where else ""
            sql = (f'SELECT count(*) FROM {child} c LEFT JOIN {parent} p'
                   f' ON p."{pcol}" = c."{ccol}" WHERE p."{pcol}" IS NULL{cond}')
        total = con.execute(f"SELECT count(*) FROM {child}").fetchone()[0]
        try:
            orphans = con.execute(sql).fetchone()[0]
        except duckdb.Error as exc:
            rows.append([label, "-", "-", "error: " + str(exc).splitlines()[0][:80]])
            continue
        if orphans and must_be_zero:
            rep.fail("join-orphans", f"{label}: {orphans:,} orphan row(s) of {total:,}")
        elif orphans:
            rep.info("join-orphans-known", f"{label}: {orphans:,} of {total:,} (documented gap)")
        rows.append([label, f"{total:,}",
                     f"**{orphans:,}**" if orphans and must_be_zero else f"{orphans:,}",
                     "must be 0" if must_be_zero else "known"])
    rep.table(["join", "rows", "orphans", "rule"], rows)


def check_games_csv(rep: Report, con: duckdb.DuckDBPyConnection, root: Path) -> None:
    rep.section("`processed/games.csv` vs `core.fact_game`")
    csv_path = root / "processed" / "games.csv"
    if not csv_path.exists() or not _table_exists(con, "core.fact_game"):
        rep.add("games.csv or core.fact_game missing; skipped.", "")
        return
    per_season: dict[int, int] = defaultdict(int)
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            per_season[int(row["season"])] += 1
    wh = dict(con.execute(
        "SELECT season, count(*) FILTER (WHERE has_line) FROM core.fact_game GROUP BY 1"
    ).fetchall())
    rows, drift = [], 0
    for s in sorted(set(per_season) | {k for k, v in wh.items() if v}):
        a, b = per_season.get(s, 0), int(wh.get(s, 0))
        drift += abs(a - b)
        rows.append([s, a, b, "" if a == b else f"**{a - b:+d}**"])
    rep.table(["season", "games.csv", "fact_game has_line", "diff"], rows)
    if drift:
        rep.warn("games-csv-drift", f"`games.csv` and `core.fact_game.has_line` differ by "
                 f"{drift:,} row(s) across seasons; `refresh_cfbd.py` rebuilds only the "
                 f"current season's CSV")
    else:
        rep.add(f"games.csv ({sum(per_season.values()):,} rows) agrees with `has_line` "
                f"on every season.", "")


def snapshot_schema(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, str]]:
    snap: dict[str, dict[str, str]] = defaultdict(dict)
    for s, t, c, d in con.execute(
        "SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns"
        " WHERE table_schema IN ('raw', 'stg', 'core', 'meta') ORDER BY 1, 2, ordinal_position"
    ).fetchall():
        snap[f"{s}.{t}"][c] = d
    return dict(snap)


def check_schema_drift(rep: Report, con: duckdb.DuckDBPyConnection,
                       snapshot_dir: Path, now: datetime) -> None:
    rep.section("Schema drift")
    current = snapshot_schema(con)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    previous = sorted(snapshot_dir.glob("schema_*.json"))
    if previous:
        old = json.loads(previous[-1].read_text(encoding="utf-8"))
        diff = diff_schemas(old, current)
        changed = sum(len(v) for v in diff.values())
        rep.add(f"Against `{previous[-1].name}`: {changed} change(s).", "")
        for key, items in diff.items():
            if items:
                rep.add(f"- {key.replace('_', ' ')} ({len(items)}): "
                        + ", ".join(f"`{i}`" for i in items[:30])
                        + (" ..." if len(items) > 30 else ""))
        if diff["tables_removed"] or diff["types_changed"]:
            rep.warn("schema-drift", f"{len(diff['tables_removed'])} table(s) removed, "
                     f"{len(diff['types_changed'])} type change(s) since `{previous[-1].name}`")
        rep.add("")
    else:
        rep.add("No previous snapshot; this run writes the baseline.", "")
    path = snapshot_dir / f"schema_{now:%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
    rep.add(f"Snapshot written: `{path}` ({len(current)} tables).", "")


# ----------------------------------------------------------------------------- main


def render(rep: Report, title: str) -> str:
    counts = {s: sum(1 for f in rep.findings if f.severity == s) for s in ("FAIL", "WARN", "INFO")}
    head = [f"# {title}", "",
            f"Generated by `scripts/audit_data_hygiene.py` at "
            f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
            "", f"**{counts['FAIL']} FAIL, {counts['WARN']} WARN, {counts['INFO']} INFO.**", "",
            "| severity | code | finding |", "|---|---|---|"]
    order = {"FAIL": 0, "WARN": 1, "INFO": 2}
    for f in sorted(rep.findings, key=lambda f: (order[f.severity], f.code)):
        head.append(f"| {f.severity} | `{f.code}` | {f.message} |")
    return "\n".join(head + rep.lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-root", default=str(DATA_ROOT))
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", help="write the markdown report here instead of stdout")
    ap.add_argument("--json", help="write findings as JSON here")
    ap.add_argument("--checks", default="all", choices=["all", "folder", "warehouse"])
    ap.add_argument("--stale-days", type=int, default=30)
    ap.add_argument("--snapshot-dir", help="schema snapshots (default <data-root>/audit)")
    ap.add_argument("--no-row-counts", action="store_true",
                    help="omit the full row-count appendix")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any FAIL")
    args = ap.parse_args(argv)

    root = Path(args.data_root)
    db_path = Path(args.db)
    now = datetime.now(timezone.utc)
    rep = Report()
    loaded_at = None
    t0 = time.time()

    con = None
    if args.checks in ("all", "warehouse"):
        if not db_path.exists():
            rep.fail("no-warehouse", f"`{db_path}` does not exist")
        else:
            con = duckdb.connect(str(db_path), read_only=True)
            loaded_at = check_catalog(rep, con, db_path)
    if args.checks in ("all", "folder"):
        check_folder(rep, root, now, args.stale_days, loaded_at)
    if con is not None:
        check_coverage(rep, con, now)
        check_grains(rep, con)
        check_nulls_and_nan(rep, con)
        check_joins(rep, con)
        check_games_csv(rep, con, root)
        snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else root / "audit"
        check_schema_drift(rep, con, snapshot_dir, now)
        if not args.no_row_counts:
            check_row_counts(rep, con)
        con.close()

    rep.add("", f"_Ran in {time.time() - t0:.1f}s._")
    text = render(rep, f"Data hygiene audit - `{root.name}` / `{db_path.name}`")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(f) for f in rep.findings], indent=1),
                                   encoding="utf-8")
    fails = sum(1 for f in rep.findings if f.severity == "FAIL")
    warns = sum(1 for f in rep.findings if f.severity == "WARN")
    print(f"{fails} FAIL, {warns} WARN", file=sys.stderr)
    return 1 if (args.strict and fails) else 0


if __name__ == "__main__":
    raise SystemExit(main())
