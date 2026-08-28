# DuckDB rebuild — design spec

This is a spec to review before touching anything, not a runbook. It describes the loader
that already exists (`cfb_system_maker/duckdb_load.py`, driven by the `duckdb` CLI
subcommand) and the state of the artifact it produces, `data/cfb.duckdb`. It proposes no new
code. Where it names a gap the rebuild will hit, that gap is flagged for a decision, not
silently fixed.

## Why a clean rebuild is needed

`data/cfb.duckdb` cannot be reproduced by any current-code invocation of `duckdb_load.py`.
Two independent problems, verified against the live file (not estimated):

**1. The catalog does not match the load report that built it.**

```bash
python - <<'PY'
import duckdb
con = duckdb.connect('data/cfb.duckdb', read_only=True)
print(con.execute("SELECT table_schema, COUNT(*) FROM information_schema.tables GROUP BY 1 ORDER BY 1").fetchall())
print(con.execute("SELECT MAX(loaded_at), COUNT(*) FROM meta.load_report").fetchone())
print(con.execute("SELECT schema, COUNT(*) FROM meta.load_report GROUP BY 1").fetchall())
PY
```

| Evidence | Value |
|---|---|
| `meta.load_report` `loaded_at` | 2026-08-27 05:51 (61 `raw` + 36 `graphql` rows) |
| `data/cfb.duckdb` mtime | 2026-08-28 11:07 |
| Live catalog | `raw` 97, `stg` 99, `meta` 1 — **no `graphql` schema at all** |

36 of the 97 `raw` tables are absent from the `raw` load report; 35 of those 36 appear
instead in the report's `graphql` rows. One of them is `calendar_gql` — the clash suffix
`explode_payloads` mints when a `stg` name collides — sitting in the `raw` schema. And 3
`stg` tables (`ppa_games_defense`, `venue_orientation`, `venue_orientation_labeled`) have no
`raw` twin at all:

```bash
python - <<'PY'
import duckdb
con = duckdb.connect('data/cfb.duckdb', read_only=True)
raw_tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='raw'").fetchall()}
report_raw = {r[0] for r in con.execute("SELECT name FROM meta.load_report WHERE schema='raw'").fetchall()}
report_gql = {r[0] for r in con.execute("SELECT name FROM meta.load_report WHERE schema='graphql'").fetchall()}
missing = raw_tables - report_raw
print('raw tables not in raw report:', len(missing), '| of those, in gql report:', len(missing & report_gql))
stg = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='stg'").fetchall()}
print('stg tables with no raw twin:', [t for t in stg if t not in raw_tables and t not in report_gql])
PY
```

State this as an **observation**, not a diagnosis — the mechanism is an open question for
the reviewer. A hand edit, a modified loader run, and a MotherDuck round-trip (see
`## MotherDuck mirror` below) would all leave a fingerprint like this one: the GraphQL
schema's contents sitting in `raw` while the load report still calls them `graphql`, plus
orphan `stg` tables. What is not in doubt is the conclusion: no invocation of the loader as
it exists today produces this catalog, and `meta.load_report` describes a smaller, older
build than the file now contains.

**2. It is also stale**, independent of problem 1. The build predates two scrapes that
landed later the same day:

```bash
python - <<'PY'
import glob
print('_post_wk files:', len(glob.glob('data/raw/*_post_wk*.json')))
print('_ngt files:', len(glob.glob('data/raw/*_ngt*.json')))
print('raw json total:', len(glob.glob('data/raw/*.json')))
print('graphql json total:', len(glob.glob('data/graphql/*.json')))
PY
```

`data/raw/` now holds **132 `_post_wk` files** and **520 `_ngt` files** (newest scraped
2026-08-28 16:42), none of which are in the DB. Totals on disk: 2,558 `data/raw/*.json`, 50
`data/graphql/*.json`, plus `data/raw/actionnetwork/` and `data/raw/actionnetwork_odds.csv`.

A clean rebuild fixes both: it is a pure function of what is on disk right now, so the
catalog-vs-report mismatch cannot recur, and it picks up every file scraped since.

## Sources

The loader reads three places under `{data-dir}` (default `data`), skips a small
denylist, and writes one DuckDB file:

| Source | Schema | Notes |
|---|---|---|
| `data/raw/*.json` | `raw` | REST dumps from `scrapers.py`. One table per stem (season/week suffix stripped — see `## Schema`). |
| `data/raw/actionnetwork_odds.csv` | `raw.actionnetwork_odds` | The one CSV source; loaded via `read_csv_auto`, not the JSON path. |
| `data/raw/actionnetwork/scoreboard_*.json`, `history_*.json` | `raw.actionnetwork_scoreboard`, `raw.actionnetwork_history` | Object-rooted JSON (`format='unstructured'`), off by default toggle is `--skip-actionnetwork` to exclude them. |
| `data/graphql/*.json` | `graphql` | GraphQL table dumps from `graphql_client.py`. Same stem-parsing as `raw`. |

**Skipped stems** (`_SKIP_STEMS` in `duckdb_load.py`, plus anything starting with `_`):
`user_info` — account-metering telemetry, same category as the deliberately-unregistered
`/info/usage` endpoint in `docs/data-coverage.md`. Not a data floor; a deliberate exclusion.

**Empty files are silently skipped, not errored.** `_load_job` filters out any path with
`stat().st_size == 0` before building the table; a `SEASON_WEEK` endpoint's empty week
(`docs/data-coverage.md`'s "empty files are floors, not failures") therefore never becomes a
zero-row table — it becomes no table entry for that file, same as if the file didn't exist.

## Schema

Three schemas, two shapes:

- **`raw` / `graphql`** — one table per endpoint/table stem. Every row is
  `(payload JSON, source_file VARCHAR, season INTEGER, week INTEGER)`. Payload stays JSON
  deliberately: CFBD's field names drift season to season (`normalize._first`'s multi-key
  lookups exist for the same reason), and a JSON column absorbs that drift without a schema
  migration. `season`/`week` are parsed from the filename by a separate in-SQL regex (see
  `## raw vs stg` below for why this is a second parser, not the same one that groups files
  into tables).
- **`stg`** — the exploded view, one table per `raw`/`graphql` source, built by
  `explode_payloads`/`flatten_stg_nested`. Nested JSON objects become prefixed columns
  (`offense.overall` → `offense_overall`); JSON arrays stay as DuckDB `LIST`s so row grain is
  unchanged — an endpoint that returns one row per game still returns one `stg` row per game,
  never one row per list element. The load filename survives as `_source_file`.
- **`meta.load_report`** — one row per `raw`/`graphql` load job: `schema, name, files, rows,
  error, loaded_at`. It is **not a manifest of the finished database** — see the next
  paragraph for exactly what it omits.

**What `meta.load_report` does not cover, and why the artifact above got confusing:**
`_write_meta` runs immediately after the `raw`/`graphql` load loop and *before* the
`if explode:` branch in `build_duckdb`. `stg` table reports are returned to the caller and
printed to the console, but never written to `meta.load_report` — there is no
`meta.load_report` row for any `stg.*` table, ever. Two CLI flags write **no** report rows at
all: `--explode-only` and `--flatten-nested` operate on an existing file and never touch
`meta.load_report`, so a database built by `duckdb` then modified by either flag will show a
`loaded_at` that predates the modification — which is part of why the current file's report
undercounts its own catalog (`## Why a clean rebuild is needed` above).

## Load order

Tables are independent — `_plan_loads` returns raw and graphql jobs, and nothing in
`_load_job` depends on another job having run first. There is exactly **one**
order-dependent semantic in the whole pipeline, and it lives in `explode_payloads`, not in
the raw/graphql load: when a `stg` destination name would collide (a REST endpoint and a
GraphQL table share a stem, e.g. `calendar`), `explode_payloads` sorts its source list
`raw`-first (`sources.sort(key=lambda row: (0 if row[0] == "raw" else 1, row[1]))`), so
`raw.calendar` wins bare `stg.calendar` and the GraphQL table lands at `stg.calendar_gql`
(`_stg_dest_name`). Nothing else in the loader depends on load order.

## Rebuild semantics

`build_duckdb` is a **full rebuild, atomic at the file level** — not an incremental load and
not resumable, by design:

1. Build into `{db}.building` (a sibling temp file; any leftover from a previous crashed
   build is unlinked first).
2. Run every planned job into that temp file.
3. On success: close the connection, unlink the old `{db}` if present, `Path.replace()` the
   temp file onto the final name. `replace()` is a single filesystem rename — there is no
   window where `{db}` is half-written.
4. On any exception during steps 1–2: close the connection if open, unlink the `.building`
   temp file, re-raise. The old `{db}` (if it existed) is untouched.

**Idempotency here means the DB is a pure function of (on-disk files, flags)** — run it
twice against the same `data/raw` + `data/graphql` and you get byte-for-byte-equivalent
tables, not a merge of the old database with new files. This is deliberately **not**
skip-if-exists / `--force` idempotency. That vocabulary belongs one layer upstream, in
`scrapers.py` — the scraper resumes by skipping an endpoint/season/week whose output file
already exists, and `--force` re-scrapes it. The loader has no equivalent flag and no
equivalent behavior: it does not check whether a table already exists in an old database and
skip re-reading its source file. Every rebuild reads every planned file, every time.

**`--only` is destructive, not incremental — the sharpest footgun in the CLI.** It filters
which jobs `_plan_loads` returns (by table name), then runs the same full-rebuild-plus-replace
sequence above. `duckdb --only games` against a database that currently has 196 tables
produces a **one-table** database, because the temp file starts empty and only the filtered
jobs run into it. There is no additive form of `--only` — it cannot be used to patch one
table into an existing multi-table file.

**`--explode-only` and `--flatten-nested` are the two exceptions to "always rebuilds
everything."** Both open the *existing* `{db}` file directly (no `.building` temp, no
replace) and mutate `stg.*` in place — `--explode-only` calls `explode_payloads` against the
live file, `--flatten-nested` calls `flatten_stg_nested`. Neither reloads `raw`/`graphql`,
and neither writes `meta.load_report` rows (see `## Schema` above). They fail with a printed
message and exit code 1 if `{db}` does not already exist.

## raw vs stg

`raw`/`graphql` and `stg` answer different questions and exist for different reasons:

- **`raw` / `graphql` are schema-drift-proof by construction.** Payload stays JSON precisely
  because CFBD's field casing and shape are inconsistent across seasons and endpoints
  (`normalize._first`'s multi-key fallback exists for the same underlying reason). Nothing
  about this shape can fail to load a season because of an unexpected key.
- **`stg` is the queryable, columnar view**, built in two passes:
  - `explode_payloads` (`--explode` on the initial load, or `--explode-only` against an
    existing file): `json_group_structure(payload)` infers a DuckDB type from the JSON in
    that table, `json_transform` casts payload to it, then `unnest(..., recursive := true,
    keep_parent_names := true)` flattens one level of nested objects into
    `parent_child`-named columns. Dotted names from `keep_parent_names` are then rewritten to
    underscores (`_rename_dotted_columns`) since DuckDB permits dotted identifiers but they
    are a footgun in SQL written without quoting. Arrays are deliberately **not** unnested —
    they stay as `LIST` columns, so row grain matches the source payload exactly.
  - `flatten_stg_nested` (`--flatten-nested`, or called automatically inside
    `_explode_table` right after the first unnest): `json_transform`'s single `unnest` pass
    can leave `STRUCT` columns behind when the JSON nests more than one level deep (e.g.
    `offense.havoc.db`). This pass loops — up to 12 iterations, stopping when no `STRUCT`
    columns remain or the iteration made no progress — repeating the same
    `struct_pack`/`unnest`/rename sequence at the table level until every struct is
    flattened. It is the same underscore-renaming convention: `offense.havoc.db` becomes
    `offense_havoc_db`.

## CLI surface

```
--data-dir            (default: data)
--output               DuckDB path (default: {data-dir}/cfb.duckdb)
--only                 load only these table names (destructive rebuild — see "Rebuild semantics")
--skip-actionnetwork    skip data/raw/actionnetwork/ scoreboard+history objects
--explode               after load, explode JSON payloads into stg.* columns
--explode-only          explode payloads in an existing DuckDB file; do not reload JSON
--flatten-nested        flatten leftover STRUCT columns on existing stg.* tables
```
