# DuckDB audit remediation plan — 2026-09-02

Plan for the findings in [`duckdb-audit-2026-09-02.md`](duckdb-audit-2026-09-02.md).
Ordered by **what breaks next**, not by audit severity. Nothing here is implemented yet.

**Architecture is not in scope.** Single-node DuckDB, atomic full-refresh, one nightly
Windows Task Scheduler job, three in-repo consumers. No orchestrator, no streaming layer, no
warehouse-vs-lakehouse decision to make. The failures are a broken build, a silent log, and a
column-naming trap — not a platform problem. Everything below is small and local.

## Two audit claims corrected before planning

Both came out of diagnosis done for this plan; the report is amended in step 0.

**The 2026-09-02 refresh was interrupted, not buggy.** The audit said "a second, independent
failure inside the raw rebuild — investigate it separately." That is wrong. No Python process is
running, the log has no `---- exited N ----` line (the `.cmd` wrapper always writes one on a
non-zero exit), and `.building` froze at 05:07 with the machine idle after. That is a killed
process — sleep or shutdown — not a crash. There is no raw-load bug to hunt.

**The unexplained `cfb.duckdb` mtime is `promote_to_motherduck.py`.**
[`scripts/promote_to_motherduck.py:67`](../scripts/promote_to_motherduck.py:67) runs
`ATTACH '{src_path}' AS src` with **no `READ_ONLY`**, so promoting to MotherDuck opens the local
warehouse read-write and touches it. `mirror_duckdb_to_sqlite.py:27` does the same attach
correctly with `(READ_ONLY)`. That accounts for the 2026-09-02 07:10 write against a
`meta.load_report` stamped 09-01 09:11. Warehouse provenance is now fully accounted for.

## Two things NOT worth fixing

Checked, then dropped — recording them so nobody re-opens them.

**The stale `data/cfb.duckdb.building.wal` is harmless.** Tested directly: create a fresh DuckDB
file with a 30 MB orphan WAL of another database sitting beside it — DuckDB connects clean and
reports 0 tables. It does not replay, error, or corrupt. `build_duckdb` already unlinks
`.building` at [line 444](../cfb_system_maker/duckdb_load.py:444) before each run, so the orphan
WAL is 30 MB of dead disk, nothing more. No code change.

**`.building` needs no guard.** Same unlink-on-entry covers a leftover from an interrupted run.

---

## Step 1 — Make `build_core` run (S1)

The whole point. Fails nightly today; `core` has never existed in a shipped build.

`_build_dim_week` ([`duckdb_core.py:66`](../cfb_system_maker/duckdb_core.py:66)) reads
`FROM stg.calendar`, which no longer exists. It needs `(season, week, seasonType)` and neither
staged calendar has it — `stg_gql.calendar` carries the value in `year` with `season` 100% NULL.

**Re-source onto `raw.calendar`.** Its JSON payload holds exactly `season` / `seasonType` /
`week` / `startDate` / `endDate` across 2012–2026 (258 rows, 15 seasons, no gaps), read with
`json_extract` the same way `_build_dim_team` already reads `raw.teams`. REST-canonical, which
matches the entity map in `graphql-schema-draft.md`.

One judgement call worth your sign-off: **`raw.calendar` starts at 2012, `stg.games` at 1992.**
`dim_week` will only cover 2012+. Every consumer today is 2012+ (`stg.lines` 2012–2026, plays and
drives 2012–2025), so this is not a regression — but if `fact_game` joins `dim_week` on an inner
join, games from 1992–2011 silently vanish. Decide: left-join and allow a null week key, or
declare `core` a 2012+ layer and filter explicitly. **Recommend the second** — explicit and
matches actual coverage.

**Check:** change the `stg.calendar` fixture in
[`tests/test_core_agreement.py:87`](../tests/test_core_agreement.py:87) to build whatever the
loader actually produces. Without that, the suite stays green over a broken build — which is the
entire reason this went unnoticed for a day. The fixture change *is* the check.

Then run `python -m cfb_system_maker.cli duckdb --core-only` against a copy of the warehouse and
confirm all 8 tables build before pointing it at the live file.

## Step 2 — Stop losing the traceback (root cause of the silence)

The 09-01 failure logged its traceback because the process exited normally. The 09-02 one logged
nothing because the process was killed with output still buffered — Python block-buffers stdout
when redirected to a file.

Add `-u` to the interpreter invocation in
[`scripts/refresh_cfbd.cmd`](../scripts/refresh_cfbd.cmd). One flag. Progress lines then land in
`cfbd_refresh.log` as they happen, so an interrupted run leaves a partial trail instead of a
blank.

**Check:** run the wrapper, kill it mid-load, confirm the log holds the lines written so far.

## Step 3 — Kill the `season_type` trap before `core` consumes it (S2)

`stg.games.season_type` is 100% NULL while `seasonType` holds regular 52,984 / postseason 751 /
spring_regular 504 / spring_postseason 28. Nothing reads it off DuckDB today, so it is latent —
but step 1 puts `core` back in business and `fact_game` is exactly the kind of query that would
trust the name. 36 tables share the collision (audit §10).

Two options, pick one:

- **(a) Coalesce at explode time** — `COALESCE(season, year)` / `COALESCE(season_type, seasonType)`
  when the partition column is unpopulated. Keeps one canonical name, hides the split.
- **(b) Drop the partition column where it is entirely NULL.** A filter on a missing column
  errors; a filter on an all-NULL column returns nothing. **Recommend (b)** — loud beats silent,
  and it deletes code instead of adding it.

**Check:** assert no `stg`/`stg_gql` table has a 100%-NULL partition column alongside a populated
payload twin — that is audit check `twin_columns`, already written. Wire it as a test.

## Step 4 — One-word and one-line fixes

- `promote_to_motherduck.py:67` → `ATTACH '{src_path}' AS src (READ_ONLY)`. Matches
  `mirror_duckdb_to_sqlite.py`. Stops a promote run from writing the source warehouse.
- `duckdb_load.py:466-468` → drop the `db_path.unlink()` before `tmp_path.replace(db_path)`.
  `Path.replace` overwrites on Windows, so the unlink buys nothing and opens a window where a
  crash leaves **no warehouse at all**.

Both trivially reviewable; one commit.

## Backlog — real, not urgent

| Finding | Why it waits | Trigger to do it |
|---|---|---|
| S5 `athleteId` VARCHAR in 17 tables | Bites only on player-table joins; nothing joins them today | First `core` player fact, or any cross-source athlete join |
| S6 998 season-less `gamePlayerStat` rows | Stale `data/graphql/gamePlayerStat.json` shadowing the 14 per-season files. **A file deletion in your data root — proposing, not performing** | Say the word |
| S4 `game_lines` grain | Doc-only, already cross-referenced in `graphql-schema-draft.md` | Phase 1b `fact_game_line` work |
| S8 74 dead payload columns | Cosmetic until someone trusts one | Scraper cleanup pass |
| S8 12 GB across 3 DB files | `.bak-2026-09-01` 4.9 GB + orphan `.building` 2.2 GB. **Your call, not mine** | Once step 1 proves a good build |

## Order and commits

| # | Change | Commit |
|---|---|---|
| 0 | Correct the two audit claims above in the report | docs |
| 1 | `_build_dim_week` re-source + test fixture | fix |
| 2 | `-u` in `refresh_cfbd.cmd` | fix |
| 3 | `season_type` decision + `twin_columns` as a test | fix |
| 4 | `READ_ONLY` attach + drop the unlink | fix |

Steps 2 and 4 are independent of 1 and 3 and can land first. Step 3 should land before or with
step 1 if you pick option (b), since dropping columns changes what `fact_game` can select.

**Needs your sign-off before I start:**
1. `dim_week` 2012+ — filter `core` explicitly, or left-join and allow null week keys?
2. `season_type` — coalesce (a) or drop (b)?
