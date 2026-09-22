# Feature sidecar store: `processed/features.duckdb`

Date: 2026-09-18. Reproduce sizes and timings with
`python scripts/measure_feature_store.py`.

## Question

The Flask app and CLI load registry features from a sidecar next to `games.csv`.
Can that sidecar move off a 60+ MB JSON blob without breaking the nightly refresh
while the dev server keeps the file open on Windows?

## Schema

Both `data/processed/features.duckdb` and `data/processed/upcoming_features.duckdb`
use the same layout, written by `cfb_system_maker.enrich.save_features_to`.

| Table | Grain | Columns |
| --- | --- | --- |
| `features` | One row per game | `game_id` (`INTEGER`) plus one typed column per feature key present in the snapshot (DuckDB types inferred at write time from the staging JSON array). |
| `meta` | Single row | `registry_version` (`VARCHAR`), `game_count` (`BIGINT`), `generated_at` (`VARCHAR`, UTC ISO-8601). Same fields as the legacy JSON `_meta` object. |

Readers: `load_features` / `load_features_from` prefer `<stem>.duckdb` beside the
legacy `*.json` path; JSON is read only when DuckDB is absent. Writers no longer
emit `features.json` or `upcoming_features.json` after this change.

## Why in-place `CREATE OR REPLACE TABLE` (no file swap)

`build_duckdb` finishes with `os.replace` on `data/cfb.duckdb`
([`app-vs-warehouse-read-path-2026-09-16.md`](app-vs-warehouse-read-path-2026-09-16.md)).
A long-lived DuckDB handle on that file blocks the swap on Windows (`WinError 5`),
which breaks the 05:00 warehouse rebuild when anything keeps the warehouse open.

The feature sidecar is separate from `cfb.duckdb` precisely so the app can keep
reading while `enrich` runs. Regeneration uses `CREATE OR REPLACE TABLE` on the
existing `features.duckdb` file instead of writing a temp file and replacing it,
so a Flask process (or any reader) holding `features.duckdb` open does not block
the scheduled enrich step. Staging JSON beside the sidecar is deleted immediately
after `read_json` ingest; only the DuckDB file persists.

Reproduce the warehouse swap failure: `python scripts/check_duckdb_swap_lock.py`.

**Windows file handle:** a long-lived `read_only=True` connection in another process
still blocks `duckdb.connect` for write on the same file (`IOException: being used
by another process`). The Flask app opens read-only and closes before returning, so
scheduled enrich retries briefly (`_connect_features_duckdb_writer`) rather than
requiring a file swap. Do not leave a notebook or REPL connection open on
`features.duckdb` during enrich.

Reproduce enrich while the dev server polls the sidecar + a full `refresh_cfbd.py`:
`python scripts/check_feature_store_refresh_under_reader.py`.

## Measured size and load (2026-09-18, this checkout)

`CFB_DATA_ROOT=C:\Users\mckel\dev\cfb\data`, 13,947 games, Python 3.14, DuckDB
as pinned in `requirements.lock`.

| Artifact | Size | Load path |
| --- | ---: | --- |
| `processed/features.json` (legacy, last on disk) | 60.29 MB | Full-file `json.loads` |
| `processed/features.duckdb` (serving) | 3.51 MB | `load_features()` via read-only connect, `SELECT * FROM features`, close |

| Operation | Wall time |
| --- | ---: |
| `json.loads` entire `features.json` | 0.51 s (warm OS cache; see script output) |
| `load_features()` from DuckDB | 0.78 s (13,947 games; read-only connect, full `SELECT *`, dict build) |

The JSON sidecar is retired for writes; the size row documents what the app used
to parse on every cold load before the DuckDB path. The DuckDB file is an order
of magnitude smaller on disk because columnar storage replaces indented JSON text.

## What this does **not** support

- **Does not move `games.csv`.** Spread/total grading and game identity still
  come from `processed/games.csv` unchanged.
- **Does not point the app at `data/cfb.duckdb`.** The warehouse remains a
  parallel derive for research and `core`; the system maker still does not open
  it on the request path ([`app-vs-warehouse-read-path-2026-09-16.md`](app-vs-warehouse-read-path-2026-09-16.md)).
- **Does not remove raw JSON indexing inside `enrich.py`.** Feature resolution
  still walks `data/raw/` and `data/graphql/` at enrich time; only the persisted
  sidecar format changed.
