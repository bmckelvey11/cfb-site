---
task: duckdb-rebuild-spec
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-qrn — Summary

Wrote `docs/duckdb-rebuild-spec.md`, a reviewed-before-implementation spec describing the
loader `cfb_system_maker/duckdb_load.py` already implements. Documentation only — no code,
config, or test files touched.

## Why this was needed

`data/cfb.duckdb` is not reproducible by any current-code invocation of the loader and is
stale. Verified against the live file before writing anything:

| Evidence | Value |
|---|---|
| `meta.load_report` `loaded_at` | 2026-08-27 05:51 (61 `raw` + 36 `graphql` rows) |
| `data/cfb.duckdb` mtime | 2026-08-28 11:07 |
| Live catalog | `raw` 97, `stg` 99, `meta` 1 — no `graphql` schema at all |
| 36 of 97 `raw` tables | absent from the `raw` load report; 35 appear in the `graphql` report instead |
| `stg` tables with no `raw` twin | `ppa_games_defense`, `venue_orientation`, `venue_orientation_labeled` |
| Files on disk not in the DB | 132 `_post_wk` files, 520 `_ngt` files |

The spec states these as observations (mechanism unconfirmed — hand edit, modified loader
run, or MotherDuck round-trip would all produce this fingerprint), not a diagnosis.

## What the doc covers

Two tasks, two commits, matching the plan's required headings exactly:

1. **Motivation, sources, schema, load semantics, raw vs stg** — why a clean rebuild is
   needed; `## Sources` (raw/graphql/actionnetwork, skipped `user_info` stem, silently-skipped
   empty files); `## Schema` (`raw`/`graphql` JSON-payload shape, `stg`, and what
   `meta.load_report` does not cover — no `stg` rows ever, and `--explode-only`/
   `--flatten-nested` write no report rows at all); load order (one order-dependent semantic:
   `explode_payloads` sorts raw-first so `raw.calendar` wins the `stg.calendar` name over
   GraphQL, which lands at `stg.calendar_gql`); `## Rebuild semantics` (full rebuild, atomic
   `.building` → `replace()`, resume/`--force` explicitly located in `scrapers.py` not here,
   `--only` flagged as destructive-not-incremental); `## raw vs stg` (the explode and flatten
   passes, dotted-to-underscore renaming, arrays left as `LIST`s). `## CLI surface` lists
   exactly the 7 flags the `duckdb` subparser defines.

2. **Known gaps, add-endpoint process, MotherDuck note** — `## Known gaps the rebuild will
   surface`: `_post_wk` postseason files don't match `_SEASON_WEEK_RE`, so a rebuild today
   mints ~132 single-file tables with NULL `season` and postseason rows go invisible to any
   `WHERE season = 2024` filter; the `_ngt` interaction hits the same gap
   (`ppa_players_games_ngt_2024_post_wk3` also fails to parse); the fix is presented as a
   review decision (optional `_post` segment + `season_type` column) because it changes table
   identity, not as an implementation. `## Adding a new endpoint`: register in `scrapers.py`/
   `GQL_DEFAULT_TABLES`, scrape, rebuild — the loader only changes for a new filename shape.
   `## MotherDuck mirror`: `md:cfb` is manual/out-of-band, no code implements it (grep across
   `.py` files returns nothing).

## Verification

Both automated checks specified in the plan ran and passed, exactly as written:

- Task 1: CLI flag set (7) matches the `## CLI surface` fenced block exactly (no invented,
  none missing); required headings present; `meta.load_report` and `.building` both named.
- Task 2: three new headings present; `parse_dump_stem` re-derived live against all 132
  `_post_wk` files on disk — every one still fails to parse, matching the doc's claim; `md:cfb`
  named.

Both checks needed `data/` and `data/cfb.duckdb`, which this worktree does not have (gitignored,
not checked out). Used a temporary NTFS junction (`data` → the main repo's `data/` directory)
purely for read-only verification, removed before finishing — `git status` confirms it left no
trace, and it is untracked and unmodified by this task.

## Deviations from Plan

None — plan executed exactly as written. All facts in the doc were independently
re-verified against the live database and disk during execution rather than taken on faith
from the plan's pre-computed evidence, and every number matched.

## Commits

- `4fd680f` — `docs: write DuckDB rebuild spec — motivation, sources, schema, semantics`
- `f0aa970` — `docs: add known gaps, add-endpoint process, and MotherDuck note to rebuild spec`

## Self-Check: PASSED

- `docs/duckdb-rebuild-spec.md` — FOUND
- `4fd680f` — FOUND in `git log --oneline --all`
- `f0aa970` — FOUND in `git log --oneline --all`
- `git status --short` shows no file outside `docs/` modified by this task.
