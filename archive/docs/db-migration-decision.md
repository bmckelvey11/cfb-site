# Flat-file vs. Postgres — decision framework

**Archived 2026-08-31 — superseded.** The migration happened, to DuckDB (not Postgres):
`cfb.duckdb` is now the source of truth (see root `CLAUDE.md`), with a `core` star schema
(`duckdb-core-ddl.md`) implemented and mirrored to MotherDuck `md:cfb`. Kept for the
decision-framework reasoning and trigger table, not as current guidance.

**Verdict as of 2026-07-20: stay flat-file.** Nothing in the current data volume, access
pattern, or user count crosses a threshold that a database would fix. There's a real
performance bug in the web app today, but it's a missing-cache bug, not a storage-format
problem — see "Fix this first" below. This doc gives the thresholds to re-run this decision
against later, not a one-time answer.

## Current scale (measured, not estimated)

| Artifact | Size | Rows | Read pattern |
|---|---|---|---|
| `data/processed/games.csv` | 1.1 MB | ~12,964 games | Full parse, every web request |
| `data/processed/features.json` | 37 MB | 1 object/game | Full JSON parse, every web request |
| `data/raw/*.json` (REST dump) | 4.3 GB / 1,601 files | — | Batch input to `enrich`, not read by the web app |
| `data/graphql/*.json` | 172 MB / 26 files | — | Batch input to `enrich`, not read by the web app |
| `data/systems/*.json` (saved systems) | ~single file | 1 | Written by `POST /save`, one file per system |

The web app's actual working set — `games.csv` + `features.json` — is **38 MB combined**. The
4.5 GB of raw scrape data is write-once/batch-only; it feeds the `enrich` step, which is run
manually via CLI, not on any request path.

## Two different problems — don't conflate them

**Problem A (real, present): no caching in `web.py`.** Every route handler —
`index`, `compare`, `api_backtest`, `filter_detail` — independently calls
`load_processed_games` and `_try_load_features`, which fully re-parse the 1.1 MB CSV and the
37 MB JSON **from scratch, per HTTP request**, with zero memoization. This is a real bug: it
makes every page load pay a ~38 MB parse cost for data that only changes when someone runs
`build`/`enrich` from the CLI. Fixing this is a caching problem — load once at app startup (or
cache with an mtime check) — and should happen regardless of what storage format is
underneath. **This is not a reason to migrate to Postgres**; a database would still need the
same fix (an ORM session/connection-pool warm-up) if queried naively per request.

**Problem B (hypothetical, not yet true): the flat-file format itself becomes the
bottleneck.** This is the actual "should we migrate" question, and it's a separate axis from
Problem A. The rest of this doc is about Problem B.

## Why flat-file is enough today

- **Single local developer, single-process dev server.** `cli.py` runs Flask via plain
  `app.run(...)` with no `threaded=True`, no WSGI server. There's no concurrent-write scenario
  to protect against — `save_system` is the only web-triggered write, and it's one small
  per-system JSON file with no observed contention (1 file exists today).
- **The whole working set fits comfortably in memory.** 38 MB is nothing to hold as Python
  objects; a linear scan over 13k rows is sub-millisecond-to-low-millisecond work even
  unindexed. A DB's indexing advantage doesn't matter until the row count or filter complexity
  makes a full scan actually slow — it doesn't yet.
- **The join work is already done, once, upstream.** `enrich.py` is exactly the ETL step a
  database would otherwise do at query time (joining raw REST/GraphQL sources by
  `game_id`/`(team, season)` — see `schema-audit.md`'s verified join keys). The output,
  `features.json`, is a single denormalized table. A DB's main strength — efficient
  multi-table joins at query time — isn't being exploited, because there's deliberately only
  one table to query.
- **The filter engine is a Python DSL, not SQL.** `matches_system`/`SystemFilter` is a
  registry-driven, extensible predicate evaluated in Python (`backtest.py`). Moving to Postgres
  wouldn't just mean "store the same rows in a table" — it would mean translating that
  predicate DSL into generated SQL (or falling back to pulling all rows into Python anyway,
  which is what happens today). That's a real rewrite, not a config change.
- **The bottleneck that exists is CPU, not I/O.** `compute_system_stats` runs a 1,000-iteration
  Monte Carlo permutation test per backtest call, and `filter_detail` re-runs `matches_system`
  once per distinct candidate value. Both are Python-side compute over in-memory rows. Postgres
  wouldn't speed this up unless the stats engine were rewritten in SQL (window functions,
  `TABLESAMPLE`, etc.) — a materially bigger project than adding a database.

## What already assumes Postgres is coming (don't redo this work)

The scraper layer was designed with this migration in mind from day one —
`scrapers.py`: *"Raw JSON is the load format for Postgres later (a JSONB staging column)."*
Two documents already exist and stay valid regardless of when the migration happens:

- **`schema-audit.md`** — verified REST↔GraphQL join keys against real 2023 data (not assumed),
  plus a suggested `dim_team`/`dim_athlete`/`dim_game`/`fact_*` Postgres model.
- **`docs/graphql-schema-draft.md`** — full draft DDL for all 61 REST endpoints + 24 GraphQL
  tables, endpoint coverage table, and the REST/GraphQL shape-divergence gotchas (name-keyed
  vs. id-keyed teams, hidden FKs, natural-key tables).

Staying flat-file now doesn't waste that work — it's already a checkpoint you can execute from
whenever a trigger below fires, not a redo.

## Triggers to re-run this decision

Revisit this doc — don't migrate speculatively — when any of these actually happens:

| Trigger | Why it matters | Current status |
|---|---|---|
| `features.json` grows from tens of MB into the hundreds-of-MB/GB range | Full-file JSON parse per request (even after fixing Problem A's cache) starts costing real seconds and real memory | Not yet — 37 MB. Would jump here if `game_player_stats`/play-level data (~974 MB REST, ~425 MB+ deferred GraphQL) gets joined into the registry — see `defer-gameplayerstat-pull` decision |
| More than one person needs concurrent web access, especially with writes | Flat-file whole-file overwrites (`save_processed_games`, `save_features`) have no locking; concurrent writers can race | Not yet — single local developer, dev server |
| Something other than this one Flask app needs to query the data (BI tool, another service, ad hoc SQL) | Flat-file requires loading the whole thing into a process; a DB lets any client query a subset | Not yet — sole consumer is this app |
| Rebuilding derived data needs to be incremental, not full-rebuild | `enrich`/`build` currently rewrite the entire output file every run; that gets slower as the dataset grows | Not yet — full rebuild of 13k games is fast today |
| Durability/backup guarantees beyond "the file on disk" become a requirement | Flat-file has no transaction log, no point-in-time recovery | Not yet — no incident, no stated requirement |

## Do this now, independent of the DB question

Fix Problem A: load `games.csv`/`features.json` once (at app startup, or behind a cache keyed
on file mtime) instead of re-parsing on every request. This is a small, storage-format-agnostic
fix that removes the actual performance cost users would notice today — and it's needed either
way, since a Postgres migration wouldn't eliminate the need for a warm connection/session, only
change what's being warmed.
