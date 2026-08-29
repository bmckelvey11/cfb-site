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

## Known gaps the rebuild will surface

### `_post_wk` files do not parse — postseason rows go missing from a season filter

`_scrape_season_week`'s postseason pass (`docs/data-coverage.md`, closed by quick task
`260828-l60`) writes `{name}_{season}_post_wk{week}.json`. The loader's stem parser does not
know that shape:

```bash
python -c "
from cfb_system_maker.duckdb_load import parse_dump_stem
print(parse_dump_stem('game_team_stats_2024_post_wk1'))
"
```

`parse_dump_stem('game_team_stats_2024_post_wk1')` previously returned
`('game_team_stats_2024_post_wk1', None, None)` — whole stem as table name, no season.

The in-SQL filename regex used to populate the `season`/`week` columns (`_insert_json_file`)
disagrees with the stem parser on the same file — it extracts `season=None` (its year regex
also expects `_wk` or end-of-string right after the year) but `week=1` (its week regex only
needs a trailing `_wk\d+.json`, which `_post_wk1.json` does match). So today's rebuild will
mint **~132 single-file tables**, one per `_post_wk` file, each with a NULL `season` column
and a populated `week` column:

```bash
python -c "
import glob
print(len(glob.glob('data/raw/*_post_wk*.json')))
"
```

**Blast radius:** any query filtering `WHERE season = 2024` on the regular table (e.g.
`raw.game_team_stats`) silently excludes every postseason row for that season, because those
rows never entered the regular table at all — they are sitting in ~132 separate
`raw.game_team_stats_2024_post_wk1`-style tables that nothing joins against.
`tests/test_duckdb_load.py` has no test case for the `_post_wk` filename shape, which is why
nothing caught this before now.

**`_ngt` files interact the same way when they are also postseason.** Plain `_ngt` files
parse correctly (`ppa_games_ngt_2024` → `('ppa_games_ngt', 2024, None)`), but a postseason
`_ngt` file hits the identical gap:

```bash
python -c "
from cfb_system_maker.duckdb_load import parse_dump_stem
print(parse_dump_stem('ppa_players_games_ngt_2024_post_wk3'))
"
```

`('ppa_players_games_ngt_2024_post_wk3', None, None)` — same failure mode, same fix needed.

**Fix (implemented 2026-08-28).** `_SEASON_WEEK_RE` accepts an optional `_post_` segment;
`parse_dump_stem` returns `(name, season, week, season_type)` with `season_type`
`regular` | `postseason` for week-scoped files (`NULL` for season-only / once dumps).
Raw/graphql JSON tables gain a `season_type` column populated from that parser (no second
in-SQL filename regex). Regular and postseason week files group into the same table —
a schema change for consumers that previously saw orphan `*_post_wk*` table names.

**Rebuild note (2026-08-28):** clean rebuild to `$CFB_DATA_ROOT/cfb.duckdb` with `--explode`
landed `raw` 77 + `graphql` 36 (separate schemas; zero `*_post_wk*` table names;
`raw.game_team_stats` postseason rows all have non-null `season`). Two `stg` explode
passes OOM on this machine (`plays`, `gamePlayerStat`) — raw payloads remain; defer those
`stg` tables or explode on a higher-RAM host. Rebuild used `--skip-actionnetwork`.

### `--only` is destructive, and `meta.load_report` omits the `stg` pass

Both already covered under `## Rebuild semantics` and `## Schema` above — repeated here
because both are exactly the kind of thing a rebuild run "surfaces" if the operator isn't
already holding them in mind: `--only <table>` against an existing multi-table database
replaces it with a one-table database, and `meta.load_report` after a full rebuild with
`--explode` will show `raw`/`graphql` rows but no `stg` rows, so it cannot be used to confirm
the explode pass ran.

## Adding a new endpoint

The true answer is short, and does not touch this file: register the `Endpoint` in
`scrapers.py`'s `ENDPOINTS` (or add the table name to `GQL_DEFAULT_TABLES` for a GraphQL
table), scrape it, then rebuild. `_plan_loads` groups files purely by filename glob
(`data/raw/*.json`, `data/graphql/*.json`) and stem, so a new endpoint's dumps are picked up
automatically the next time `duckdb` runs — no registration step inside `duckdb_load.py`.

`duckdb_load.py` only needs changing when a new **filename shape** appears — not a new
endpoint under an existing shape. `_post_wk` (above) is exactly that case: it wasn't a new
endpoint, it was an existing endpoint writing a filename pattern the stem parser had never
seen. Any future filename convention (a new suffix, a new separator) would need the same kind
of `_SEASON_WEEK_RE`/`_SEASON_RE` update before a rebuild groups it correctly.

## MotherDuck mirror

`md:cfb` — referenced in `consolidation.md` as "a MotherDuck mirror (same pattern as
Greenview), not a local folder" if cross-machine sharing is ever needed — is a **manual,
out-of-band step**. There is no code for it anywhere in this repo:

```bash
grep -ri motherduck --include="*.py" -r .
```

returns nothing; the only hits for "motherduck" in the whole tree are prose in
`consolidation.md`. This spec does not describe a push to `md:cfb` as part of the rebuild
because the codebase does not implement one — if a mirror is wanted, it is a separate manual
`duckdb` CLI session against the rebuilt local file, not a step this loader performs.

---

A threat model was deliberately omitted from this spec: it is a documentation-only change,
crosses no trust boundary, and installs no package.
