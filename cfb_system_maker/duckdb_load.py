"""Load scraped JSON dumps into a DuckDB staging file.

Each REST endpoint / GraphQL table becomes one DuckDB table. Nested objects stay
JSON (the documented JSONB staging shape) so season-to-season schema drift does
not break the load. Filename suffixes supply season/week columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

# Skip account-metering telemetry (docs/data-coverage.md).
_SKIP_STEMS = frozenset({"user_info"})

# 1992–2026 games files exist on disk; keep the window wide for new seasons.
_YEAR_MIN = 1990
_YEAR_MAX = 2035

# Optional ``_post`` before ``_wk`` — postseason scrapes write ``{name}_{year}_post_wk{n}``.
_SEASON_WEEK_RE = re.compile(r"^(.+)_(\d{4})_(post_)?wk(\d+)$")
_SEASON_RE = re.compile(r"^(.+)_(\d{4})$")

# DuckDB allocates a buffer of maximum_object_size per JSON read. Size it to the
# file (plus slack) instead of a global gigabyte, or small tables OOM immediately.
_DEFAULT_OBJECT_SIZE = 16_777_216
_OBJECT_SIZE_SLACK = 1_048_576

_JSON_TABLE_SQL = """
CREATE TABLE {table} (
  payload JSON,
  source_file VARCHAR,
  season INTEGER,
  week INTEGER,
  season_type VARCHAR
)
"""


@dataclass(frozen=True)
class TableLoad:
    schema: str
    name: str
    files: int
    rows: int
    error: str | None = None


def parse_dump_stem(stem: str) -> tuple[str, int | None, int | None, str | None]:
    """Split dump stems into ``(table, season, week, season_type)``.

    ``plays_2023_wk1`` → ``('plays', 2023, 1, 'regular')``;
    ``plays_2023_post_wk1`` → ``('plays', 2023, 1, 'postseason')``;
    ``games_2023`` → ``('games', 2023, None, None)`` (season-level; type is in payload);
    unknown stems stay whole with null season/week/type.
    """
    match = _SEASON_WEEK_RE.fullmatch(stem)
    if match:
        year = int(match.group(2))
        if _YEAR_MIN <= year <= _YEAR_MAX:
            season_type = "postseason" if match.group(3) else "regular"
            return match.group(1), year, int(match.group(4)), season_type
    match = _SEASON_RE.fullmatch(stem)
    if match:
        year = int(match.group(2))
        if _YEAR_MIN <= year <= _YEAR_MAX:
            return match.group(1), year, None, None
    return stem, None, None, None


def build_duckdb(
    data_dir: str | Path,
    output: str | Path | None = None,
    *,
    only: set[str] | None = None,
    include_actionnetwork: bool = True,
    explode: bool = False,
    progress: Callable[[TableLoad], None] | None = None,
) -> tuple[Path, list[TableLoad]]:
    """Create ``{data_dir}/cfb.duckdb`` (or ``output``) from raw + graphql dumps."""
    data_dir = Path(data_dir)
    db_path = Path(output) if output else data_dir / "cfb.duckdb"
    tmp_path = db_path.with_name(db_path.name + ".building")
    if tmp_path.exists():
        tmp_path.unlink()
    tmp_path.parent.mkdir(parents=True, exist_ok=True)

    jobs = _plan_loads(data_dir, only=only, include_actionnetwork=include_actionnetwork)
    reports: list[TableLoad] = []
    con = duckdb.connect(str(tmp_path))
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("CREATE SCHEMA IF NOT EXISTS graphql")
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        for job in jobs:
            report = _load_job(con, job)
            reports.append(report)
            if progress is not None:
                progress(report)
        _write_meta(con, reports)
        if explode:
            reports.extend(explode_payloads(con, progress=progress))
        con.close()
        con = None
        if db_path.exists():
            db_path.unlink()
        tmp_path.replace(db_path)
    except Exception:
        if con is not None:
            con.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return db_path, reports


def explode_payloads(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Create ``stg.*`` tables with JSON payload keys exploded into columns.

    Nested objects become prefixed columns (``offense.overall`` → ``offense_overall``).
    Arrays stay lists (row grain unchanged). ``raw`` / ``graphql`` stay as JSON.
    Load filename is kept as ``_source_file``.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        con.execute("CREATE SCHEMA IF NOT EXISTS stg")
        sources = con.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = 'payload'
              AND table_schema IN ('raw', 'graphql')
            GROUP BY 1, 2
            ORDER BY table_schema DESC, table_name
            """
        ).fetchall()
        taken: set[str] = set()
        # REST first so graphql.calendar loses the name clash, not raw.calendar.
        sources.sort(key=lambda row: (0 if row[0] == "raw" else 1, row[1]))
        for schema, name in sources:
            dest = _stg_dest_name(name, taken)
            report = _explode_table(con, schema, name, dest)
            reports.append(report)
            if report.error is None:
                taken.add(dest.lower())
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
    finally:
        if owns_connection:
            con.close()
    return reports


def flatten_stg_nested(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Flatten leftover STRUCT columns on existing ``stg.*`` tables.

    Same naming as ``explode_payloads``: dotted paths become underscores.
    Tables with no STRUCT columns are skipped.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        tables = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'stg'
            ORDER BY table_name
            """
        ).fetchall()
        for (name,) in tables:
            report = _flatten_struct_columns(con, "stg", name)
            if report is None:
                continue
            reports.append(report)
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
    finally:
        if owns_connection:
            con.close()
    return reports


def _stg_dest_name(name: str, taken: set[str]) -> str:
    if name.lower() not in taken:
        return name
    suffix = name + "_gql"
    if suffix.lower() not in taken:
        return suffix
    return "gql_" + name


def _explode_table(con: duckdb.DuckDBPyConnection, schema: str, name: str, dest: str) -> TableLoad:
    source = _qualify(schema, name)
    target = _qualify("stg", dest)
    try:
        structure = con.execute(f"SELECT json_group_structure(payload) FROM {source}").fetchone()[0]
        if structure is None:
            return TableLoad("stg", dest, 0, 0, error="empty payload")
        con.execute(f"DROP TABLE IF EXISTS {target}")
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT
              source_file AS _source_file,
              unnest(
                json_transform(payload, ?),
                recursive := true,
                keep_parent_names := true
              )
            FROM {source}
            """,
            [structure],
        )
        _rename_dotted_columns(con, target)
        leftover = _flatten_struct_columns(con, "stg", dest)
        if leftover is not None and leftover.error:
            return leftover
        rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
        return TableLoad("stg", dest, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {target}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad("stg", dest, 0, 0, error=f"{type(exc).__name__}: {detail}")


def _flatten_struct_columns(
    con: duckdb.DuckDBPyConnection, schema: str, name: str
) -> TableLoad | None:
    table = _qualify(schema, name)
    tmp_name = name + "__flattening"
    tmp = _qualify(schema, tmp_name)
    rewrote = False
    try:
        previous: list[str] | None = None
        for _ in range(12):
            struct_cols = [
                row[0]
                for row in con.execute(f"DESCRIBE {table}").fetchall()
                if _is_struct_type(row[1])
            ]
            if not struct_cols or struct_cols == previous:
                break
            previous = struct_cols
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
            exclude = ", ".join(_ident(col) for col in struct_cols)
            packed = ", ".join(f"{_ident(col)} := {_ident(col)}" for col in struct_cols)
            con.execute(
                f"""
                CREATE TABLE {tmp} AS
                SELECT
                  * EXCLUDE ({exclude}),
                  unnest(
                    struct_pack({packed}),
                    recursive := true,
                    keep_parent_names := true
                  )
                FROM {table}
                """
            )
            con.execute(f"DROP TABLE {table}")
            con.execute(f"ALTER TABLE {tmp} RENAME TO {_ident(name)}")
            _rename_dotted_columns(con, table)
            rewrote = True
        if not rewrote:
            return None
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(schema, name, 0, 0, error=f"{type(exc).__name__}: {detail}")


def _rename_dotted_columns(con: duckdb.DuckDBPyConnection, table: str) -> None:
    cols = [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
    taken = {col.lower() for col in cols}
    for col in cols:
        if "." not in col:
            continue
        dest = col.replace(".", "_")
        base = dest
        suffix = 2
        while dest.lower() in taken:
            dest = f"{base}_{suffix}"
            suffix += 1
        con.execute(f"ALTER TABLE {table} RENAME COLUMN {_ident(col)} TO {_ident(dest)}")
        taken.discard(col.lower())
        taken.add(dest.lower())


def _is_struct_type(dtype: object) -> bool:
    text = str(dtype).strip()
    upper = text.upper()
    return upper.startswith("STRUCT") and not upper.endswith("[]")


def _plan_loads(
    data_dir: Path,
    *,
    only: set[str] | None,
    include_actionnetwork: bool,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    raw_groups: dict[str, list[Path]] = {}
    raw_dir = data_dir / "raw"
    if raw_dir.is_dir():
        for path in sorted(raw_dir.glob("*.json")):
            if path.stem in _SKIP_STEMS or path.stem.startswith("_"):
                continue
            name, _, _, _ = parse_dump_stem(path.stem)
            raw_groups.setdefault(name, []).append(path)
        for name, paths in sorted(raw_groups.items()):
            if only is not None and name not in only:
                continue
            jobs.append({"schema": "raw", "name": name, "paths": paths, "format": "array"})

        csv_path = raw_dir / "actionnetwork_odds.csv"
        if csv_path.exists() and (only is None or "actionnetwork_odds" in only):
            jobs.append({"schema": "raw", "name": "actionnetwork_odds", "paths": [csv_path], "format": "csv"})

    gql_dir = data_dir / "graphql"
    if gql_dir.is_dir():
        gql_groups: dict[str, list[Path]] = {}
        for path in sorted(gql_dir.glob("*.json")):
            name, _, _, _ = parse_dump_stem(path.stem)
            gql_groups.setdefault(name, []).append(path)
        for name, paths in sorted(gql_groups.items()):
            if only is not None and name not in only:
                continue
            jobs.append({"schema": "graphql", "name": name, "paths": paths, "format": "array"})

    if include_actionnetwork:
        an_dir = data_dir / "raw" / "actionnetwork"
        if an_dir.is_dir():
            boards = sorted(an_dir.glob("scoreboard_*.json"))
            if boards and (only is None or "actionnetwork_scoreboard" in only):
                jobs.append(
                    {
                        "schema": "raw",
                        "name": "actionnetwork_scoreboard",
                        "paths": boards,
                        "format": "object",
                    }
                )
            histories = sorted(an_dir.glob("history_*.json"))
            if histories and (only is None or "actionnetwork_history" in only):
                jobs.append(
                    {
                        "schema": "raw",
                        "name": "actionnetwork_history",
                        "paths": histories,
                        "format": "object",
                    }
                )
    return jobs


def _load_job(con: duckdb.DuckDBPyConnection, job: dict[str, Any]) -> TableLoad:
    table = _qualify(job["schema"], job["name"])
    paths: list[Path] = [p for p in job["paths"] if p.stat().st_size > 0]
    if not paths:
        return TableLoad(job["schema"], job["name"], 0, 0, error="no non-empty files")
    try:
        if job["format"] == "csv":
            con.execute(
                f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto({_sql_path_list(paths)})"
            )
        else:
            con.execute(_JSON_TABLE_SQL.format(table=table))
            for path in paths:
                _insert_json_file(con, table, path)
        con.execute("CHECKPOINT")
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(job["schema"], job["name"], len(paths), int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {table}")
            con.execute("CHECKPOINT")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(job["schema"], job["name"], len(paths), 0, error=f"{type(exc).__name__}: {detail}")


def _insert_json_file(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    json_format = _json_root_format(path)
    object_size = max(_DEFAULT_OBJECT_SIZE, path.stat().st_size + _OBJECT_SIZE_SLACK)
    _, season, week, season_type = parse_dump_stem(path.stem)
    # Bind season/week/type from the stem parser (one source of truth) — do not
    # re-parse filenames with a second in-SQL regex that can drift from grouping.
    con.execute(
        f"""
        INSERT INTO {table}
        SELECT
          json AS payload,
          filename AS source_file,
          ?::INTEGER AS season,
          ?::INTEGER AS week,
          ?::VARCHAR AS season_type
        FROM read_json_objects(
          {_sql_path_list([path])},
          format='{json_format}',
          filename=true,
          maximum_object_size={object_size}
        )
        """,
        [season, week, season_type],
    )


def _json_root_format(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        while True:
            char = handle.read(1)
            if not char:
                return "array"
            if not char.isspace():
                return "unstructured" if char == "{" else "array"


def _write_meta(con: duckdb.DuckDBPyConnection, reports: Iterable[TableLoad]) -> None:
    con.execute(
        """
        CREATE TABLE meta.load_report (
          schema VARCHAR,
          name VARCHAR,
          files INTEGER,
          rows BIGINT,
          error VARCHAR,
          loaded_at TIMESTAMP
        )
        """
    )
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for report in reports:
        con.execute(
            "INSERT INTO meta.load_report VALUES (?, ?, ?, ?, ?, ?)",
            [report.schema, report.name, report.files, report.rows, report.error, loaded_at],
        )


def _qualify(schema: str, name: str) -> str:
    return f"{_ident(schema)}.{_ident(name)}"


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_path_list(paths: list[Path]) -> str:
    return "[" + ", ".join(_sql_str(p.resolve().as_posix()) for p in paths) + "]"


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
