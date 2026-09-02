# DuckDB audit remediation plan — 2026-09-02

Plan for the findings in [`duckdb-audit-2026-09-02.md`](duckdb-audit-2026-09-02.md).
Ordered by **what breaks next**, not by audit severity.

**Status 2026-09-02: steps 1–5 done and verified against the live warehouse.** Sign-off was
*explicit 2012+*, *drop the column*, and *(a) conditional re-infer*. `core` is built (8 tables,
`fact_game` 34,645 rows), 715 unit tests pass, and **both live agreement tests pass** — they had
never run before, because they `pytest.skip` when `core` is missing. That is what surfaced S9.
Backlog below is untouched by design.

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

**The unexplained `cfb.duckdb` mtime is a read-write attach, and it is not a bug.**
[`scripts/promote_to_motherduck.py:67`](../scripts/promote_to_motherduck.py:67) is the only
read-write opener of the live file outside the loader, and its `ATTACH '{src_path}' AS src` is
**deliberately** not `READ_ONLY` — the script stamps `src.meta.warehouse_version` on a real
promote, guarded by an early `return 0` on `--dry-run`. No `warehouse_version` table exists in
the live file, so the 07:10 write was most likely an attach touching the header without changing
content. **Step 4a of an earlier draft of this plan proposed adding `READ_ONLY` here; that was
wrong and is withdrawn.** The takeaway that survives: `meta.load_report` is not a freshness
signal, because writers other than the loader can open this file.

## Two things NOT worth fixing

Checked, then dropped — recording them so nobody re-opens them.

**The stale `data/cfb.duckdb.building.wal` is harmless.** Tested directly: create a fresh DuckDB
file with a 30 MB orphan WAL of another database sitting beside it — DuckDB connects clean and
reports 0 tables. It does not replay, error, or corrupt. `build_duckdb` already unlinks
`.building` at [line 444](../cfb_system_maker/duckdb_load.py:444) before each run, so the orphan
WAL is 30 MB of dead disk, nothing more. No code change.

**`.building` needs no guard.** Same unlink-on-entry covers a leftover from an interrupted run.

---

## Step 1 — Make `build_core` run (S1) — DONE 2026-09-02

The whole point. Fails nightly today; `core` has never existed in a shipped build.

`_build_dim_week` ([`duckdb_core.py:66`](../cfb_system_maker/duckdb_core.py:66)) reads
`FROM stg.calendar`, which no longer exists. It needs `(season, week, seasonType)` and neither
staged calendar has it — `stg_gql.calendar` carries the value in `year` with `season` 100% NULL.

**Re-source onto `raw.calendar`.** Its JSON payload holds exactly `season` / `seasonType` /
`week` / `startDate` / `endDate` across 2012–2026 (258 rows, 15 seasons, no gaps), read with
`json_extract` the same way `_build_dim_team` already reads `raw.teams`. REST-canonical, which
matches the entity map in `graphql-schema-draft.md`.

**Signed off: explicit 2012+.** `raw.calendar` starts at 2012, `stg.games` at 1992.
`_build_fact_game` now bounds on `(SELECT min(season) FROM core.dim_week)` and
`_build_fact_game_line` inherits that bound rather than carrying orphan lines.

**Found while testing, and it constrains every future join:** the bound is by *season*, not by
per-week joinability. The CFBD calendar carries **one `postseason` row per season** (15 rows for
15 seasons) while games carry real postseason week numbers (11–20). Measured on live data,
**154 of 34,645** 2012+ games have no exact `(season, week, season_type)` partner in `dim_week` —
all postseason. `fact_game` keeps them. Anything joining `dim_week` must LEFT JOIN, or match on
`season` + `season_type` only; an inner join on `week` silently drops those 154 games. A first
draft of the new test asserted zero such orphans and failed against real data — the test was
wrong, not the code.

**Check (done):** the `stg.calendar` fixture in `tests/test_core_agreement.py` now seeds
`raw.calendar` as the loader does, plus `test_core_is_bounded_to_the_calendar_first_season`.
715 tests pass (was 703).

## Step 2 — Stop losing the traceback (root cause of the silence) — DONE 2026-09-02

The 09-01 failure logged its traceback because the process exited normally. The 09-02 one logged
nothing because the process was killed with output still buffered — Python block-buffers stdout
when redirected to a file.

Add `-u` to the interpreter invocation in
[`scripts/refresh_cfbd.cmd`](../scripts/refresh_cfbd.cmd). One flag. Progress lines then land in
`cfbd_refresh.log` as they happen, so an interrupted run leaves a partial trail instead of a
blank.

**Check:** run the wrapper, kill it mid-load, confirm the log holds the lines written so far.

## Step 3 — Kill the `season_type` trap before `core` consumes it (S2) — DONE 2026-09-02

`stg.games.season_type` is 100% NULL while `seasonType` holds regular 52,984 / postseason 751 /
spring_regular 504 / spring_postseason 28. Nothing reads it off DuckDB today, so it is latent —
but step 1 puts `core` back in business and `fact_game` is exactly the kind of query that would
trust the name. 36 tables share the collision (audit §10).

**Signed off: (b), drop the column.** A filter on a missing column errors; a filter on an
all-NULL column returns nothing. `drop_dead_spine_columns` runs as a post-pass in
`explode_payloads` and drops `season`/`week`/`season_type` from any `stg`/`stg_gql` table where
they are entirely NULL. `raw` keeps its spine columns — there they are load provenance, not a
query surface.

**Check (done):** `tests/test_drop_dead_spine.py`, 5 cases. The load-bearing one asserts the
dropped-column filter now raises instead of returning zero rows.

**Takes effect on the next full rebuild**, not on `--core-only` — the drop is part of the explode
phase.

## Step 4 — One-line fix — DONE 2026-09-02

- ~~`promote_to_motherduck.py:67` → add `READ_ONLY`~~ **Withdrawn.** Reading the surrounding code
  showed the read-write attach is deliberate (it stamps `src.meta.warehouse_version`) and
  `--dry-run` already returns before that write. Nothing to fix.
- `duckdb_load.py` → dropped the `db_path.unlink()` before `tmp_path.replace(db_path)`.
  `Path.replace` overwrites on Windows, so the unlink bought nothing and opened a window where a
  crash left **no warehouse at all**.

## Step 5 — S9: stop the loader discarding all-null-in-sample fields — DONE 2026-09-02

**Discovered by step 1.** Building `core` un-skipped the live agreement tests, and they fail on
2,383 games: `core.fact_game_line.spread_open` / `total_open` / both moneylines are 100% NULL
while the raw JSON has the values. Root cause and evidence in the audit's S9.

`json_group_structure` types a key `"NULL"` when every sampled value is null, and the struct built
from that then drops the field for the whole table. Confirmed on `raw.lines`: a 5000-row sample
types four fields `"NULL"`; a full scan types them `DOUBLE`/`HUGEINT`.

**Signed off: (a), the conditional re-infer.** Implementing it exposed a wrinkle worth
recording: the plain full-column re-scan **OOMs on `raw.plays`** (12 GiB, 21.8s to fail) — the
exact failure the original `LIMIT` comment warned about. Widening the sample is not a fix either:
`plays.wallclock` is still `"NULL"`-typed at a 500,000-row sample despite being populated in
1,628,388 rows.

**Shipped instead, keeping (a)'s semantics:** `_payload_structure` collects the `"NULL"`-typed
JSONPaths and adds one targeted sample per path — rows where that path is populated — then lets
`json_group_structure` merge types across the union. Bounded, exact for any key that appears at
all, and measured at `lines` 0.7s / `plays` 3.0s. Falls back to the sampled structure if the
union query fails, so a pathological table degrades to today's behavior instead of killing the
load.

**Check (done):** `tests/test_structure_inference.py`, 6 cases — the load-bearing one asserts a
value past the sample window survives the explode. On the live warehouse a re-explode plus a
`core` rebuild recovered 8,413 opening spreads, 6,917 opening totals and 7,908 moneylines in
`core.fact_game_line`, all previously zero, and **`test_live_warehouse_agreement_4_5_6` now
passes** — the SQL warehouse and `enrich._build_line_move_index` agree on all 13,515 games.

## Backlog — real, not urgent

| Finding | Why it waits | Trigger to do it |
|---|---|---|
| S5 `athleteId` VARCHAR in 17 tables | Bites only on player-table joins; nothing joins them today | First `core` player fact, or any cross-source athlete join |
| S6 998 season-less `gamePlayerStat` rows | Stale `data/graphql/gamePlayerStat.json` shadowing the 14 per-season files. **A file deletion in your data root — proposing, not performing** | Say the word |
| S4 `game_lines` grain | Doc-only, already cross-referenced in `graphql-schema-draft.md` | Phase 1b `fact_game_line` work |
| S8 74 dead payload columns | Cosmetic until someone trusts one | Scraper cleanup pass |
| S8 12 GB across 3 DB files | `.bak-2026-09-01` 4.9 GB + orphan `.building` 2.2 GB. **Your call, not mine** | Once step 1 proves a good build |

## Order and commits

| # | Change | Status |
|---|---|---|
| 0 | Correct the audit claims in the report | done — `94d9a3a`, amended again for step 4a |
| 1 | `_build_dim_week` re-source + 2012+ bound + test fixture | done — `e169ed7` |
| 2 | `-u` in `refresh_cfbd.cmd` | done — `e169ed7` |
| 3 | `drop_dead_spine_columns` + 5 tests | done — `e169ed7` |
| 4 | Drop the unlink (READ_ONLY half withdrawn) | done — `e169ed7` |

Steps 2 and 4 are independent of 1 and 3 and can land first. Step 3 should land before or with
step 1 if you pick option (b), since dropping columns changes what `fact_game` can select.

## Remaining

The backlog table above. Nothing else is open — steps 1–4 are committed and the suite is green
at 709 tests.

Two operational notes:

- **Step 3 only takes effect on a full rebuild.** The live warehouse still carries its dead spine
  columns until the next `duckdb --explode` run.
- **Step 5 (S9) is fixed, but only a full rebuild propagates it warehouse-wide.** The live file
  has had `lines` re-exploded; every other table keeps its sampling losses until the next
  `duckdb --explode`. Anything reading `stg.*` for a field that looks empty should re-check
  after that run.
