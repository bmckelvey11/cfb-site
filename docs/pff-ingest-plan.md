# PFF ingest plan — from scraped files to warehouse tables

**Living document.** Every pass through the scraped files appends here: a step's row moves
to `done` with a date, and the worklog at the bottom gets an entry saying what was
actually found. Nothing is deleted — a step that turns out to be wrong is struck with the
reason, so the next pass does not re-open it.

**Status 2026-09-21: S1–S5, S7 and S8 done. S6 is half done — `PFF_API` was rotated, the go
was given, and 2023, 2024 and 2026 are pulled and audit clean. 2014–2022 remain,
at ~1,620 reads + 5,480 exports.** 2025 stays the reference season: the process was proven
and trimmed against it before any backfill call, because a backfill pays every inefficiency
once per season. Applying it to 2024 cost two corrections — the season-level leaderboards
`--player-facets` does not plan, and two direction codes 2025 never emitted — both recorded
in the 2026-09-21 worklog entry.

**Scope: `data/raw/pff/` only.** The other scrapers (CFBD, Action Network, Massey) already
land in the warehouse through `refresh_cfbd.py` and are not in this plan. Widen it only if
PFF's shape turns out to be the general case.

**Design is not in scope here.** [`pff-warehouse-schema.md`](pff-warehouse-schema.md) owns
the 19-table target, the DDL, and the open design questions. This file owns the *order* of
the work and its state. Where the two disagree, the schema doc wins on shape and this one
wins on what is finished.

## Status board

| # | Step | Blocks | State | Date |
|---|---|---|---|---|
| S1 | Audit the pull — every file verified, gaps named | everything | **done** | 2026-09-08 |
| S2 | Settle point-in-time: per-week pulls vs dated snapshots | S3 | **done** — per week | 2026-09-08 |
| S3 | `scripts/pff_flatten.py` — raw → `data/processed/pff/` | S5 | **done** | 2026-09-08 |
| S4 | `pff_franchise` map — PFF slug → `cfbd_team_id` | S5 | **done** | 2026-09-09 |
| S5 | loader entries → `stg` | S6 | **done** | 2026-09-09 |
| S6 | Backfill 2014–2024, finish 2026 | — | **parts 1–2 done** — 2023 + 2024 + 2026 clean; 2014–2022 open | 2026-09-21 |
| S7 | Trim the pull plan using 2025 as the reference season | S6 | **done** | 2026-09-10 |
| S8 | Decide the player tier: finish it or delete the smoke test | — | **done** — deleted | 2026-09-10 |

## S1 — Audit the pull ✅ 2026-09-08

`python scripts/audit_pff_pull.py --season 2025`. Reusable, read-only, re-run after any
pull. Checks the three ways a PFF export fails while `restish` exits 0 (empty, error
envelope in the body, header-only), plus five cross-file conditions: duplicate bodies,
column-set drift, column-order drift, declared-type drift, and missing (op, week) cells.
Expected coverage is read off disk — ops from `pff-endpoint-reference.md`, weeks from
`team/leagues.json`, franchises from that season's `team_directory` — so it does not go
stale when the plan changes.

**2025: 4,657 files, zero unusable, zero gaps.** 639 leaderboards, 3,998 team-tier, 20
player. All 21 non-all-star weeks, all 136 FBS franchises complete. Findings and their
load-time consequences are written up in
[`pff-warehouse-schema.md` §5b](pff-warehouse-schema.md); the five that survive into the
flattener are carried as S3's acceptance criteria below.

**Done when:** the script exists, is tested, and reports 2025 clean. ✅

## S2 — Point-in-time: per week ✅ 2026-09-08

**Decided: (a) the weekly file is the grain.** A facet *season* file is season-to-date at
pull time and a re-pull overwrites it, so a pre-game feature built from one leaks the rest
of the season backwards. Every PFF fact is therefore keyed `(season, week, entity)`, and
season-to-date is a windowed `SUM` over weeks `< N` — never a stored row.

Three things checked while recording this, all of which make the decision cheaper than it
looked:

- **The puller already does it.** `pull_pff_modeling.py --player-facets` pulls per week
  only; it never asks for a season-level facet. The season files sitting in
  `data/raw/pff/` are legacy snapshots from the earlier `pull_pff_facet.py` run. No puller
  change is needed — the change is entirely downstream.
- **The weekly files reconstruct the season file exactly.** Union of the 21 weekly headers
  equals the season header, column for column: `facet-passing-concept` 199, and
  `facet-passing-pressure` 197. Nothing is lost by dropping the season file as a row
  source.
- **So the schema source is the union of weeks, not the season file.** That rule also
  covers the four signature ops, which have no season file at all (their union across 22
  weekly files is 105 columns). S3 criterion 2 is amended to match.

The legacy season files stay on disk — they are a free cross-check that the union is
complete, and `audit_pff_pull.py` expects them for the facet ops. They are not row
sources; the flattener must skip any leaderboard file without a `_wk` in its name.

**Done when:** the choice is recorded here with its date, and §6 of the schema doc is
amended to match. ✅

## S3 — `scripts/pff_flatten.py` ✅ 2026-09-08

Reads `data/raw/pff/`, writes one CSV per target table to `data/processed/pff/`. The split
unpivot regex and filename regex are given in
[`pff-warehouse-schema.md` §5.1](pff-warehouse-schema.md). Five audit findings are the
acceptance criteria — a flattener that does not handle all five is not done:

1. **Glob `.csv` *and* `.json`.** `facet-offense-summary`, `facet-rushing-direction` and
   `facet-passing-detail` exist for 2025 only as JSON (the puller's fallback). A
   `facet_*.csv` glob drops two facets silently.
2. **Schema is the union of that season's weekly headers; union by name.** Weekly column
   sets are *disjoint*, not nested: passing-concept wk11 and wk18 are both 183 wide and
   each holds four the other lacks. Never stack positionally, never pin to one week. Per
   S2 the union is the rule rather than the season file, because the signature ops have no
   season file; where a season file does exist it is asserted equal to the union as a
   cross-check (holds for 2025: 199 and 197).
3. **Load one rushing-direction view, not two.** PFF ignores `team-rushing-direction`'s
   `table` parameter: `_rows.json` and `_totals.json` are byte-identical for all 136
   franchises.
4. **Pin column types; do not infer per file.** 320 team-report columns declare two types
   across responses (`draftSeason` integer/string, percentages integer/number/string).
   Normalize blanks to NULL first, then numerics → `DOUBLE`, ids and years → `VARCHAR`.
   Same failure class as `stg.an_history_tick` (f0c729b).
5. **Read columns by name.** Order varies between teams on 7 ops with identical membership.

6. **Weekly files only.** Per S2 the grain is `(season, week, entity)`; a leaderboard file
   with no `_wk` in its name is a legacy season-to-date snapshot and is not a row source.

The target shape is [`pff-sample-schema.sql`](pff-sample-schema.sql) — runnable DuckDB DDL
for one table per family, with these six criteria already expressed as column types, keys
and constraints. It supersedes §3's `week = 0` and `player_game_count` conventions, both of
which S2 invalidated.

**Done when:** `data/processed/pff/` holds every table in §3 of the schema doc for 2025,
a test asserts each of the five above on a fixture, and `audit_pff_pull.py` still reports
2025 clean afterwards (the flattener must not write into `data/raw/`). ✅

    python scripts/pff_flatten.py --seasons 2025 --validate

29 weekly sources fold into 21 tables, 1.09 M rows for 2025. `--validate` reads every CSV
back with the pinned types and inserts the six the sample DDL defines into it, so a
duplicated split label fails on the primary key and an undeclared direction fails on the
CHECK. All 21 pass; 25 tests in `tests/test_pff_flatten.py`, one of which round-trips a
real 2025 value.

## S4 — `pff_franchise` map ✅ 2026-09-09

Built into `pff_flatten.map_to_cfbd`, the way `massey_flatten` matches: normalize, index
CFBD by school+mascot and by school, and hand-map only what no rule reaches. **11 overrides,
not the ~35 estimated** — all 265 `kind = 'team'` franchises resolve, to 265 distinct CFBD
ids.

| Match | Franchises |
| --- | --- |
| `school+mascot` exact | 243 |
| `school`, after stripping a known mascot | 11 |
| `override` | 11 |
| not mapped (`kind = 'allstar'`, no CFBD counterpart) | 76 |

Three normalization rules did the work an override list would otherwise have absorbed:
`&` is dropped rather than expanded (PFF's slug drops it, so `East Texas A&M` and
`east-texas-am` meet at `east texas am`); `St` expands to `State` only when it is not the
first token, because a leading `St` is Saint; and a trailing `(MN)`-style disambiguator is
cut.

Two rules exist to refuse rather than to match, and both earned it:

- **Only a known mascot may be stripped.** Free suffix-stripping reads
  `louisiana-monroe-warhawks` down to `louisiana` and hands UL Monroe the Ragin' Cajuns'
  CFBD id. Caught by asserting the mapped ids are distinct, not by reading the output.
- **An ambiguous school is never guessed.** CFBD files the Florida school as plain `Miami`,
  so both Miamis normalize to `miami`; the rule declines and an override decides. CFBD's
  three-letter `alternateNames` (`liu`, `cal`, `sou`) are excluded from the index for the
  same reason -- they collide across schools.

**Done when:** every FBS franchise in the 2025 `team_directory` resolves to a
`cfbd_team_id`, and the join is asserted at 100% in a test. ✅
`tests/test_pff_flatten.py` asserts full coverage *and* distinctness.

## S5 — Loader entries ✅ 2026-09-09

Straight to `stg`, no `raw` twin, the way Massey and the AN tick CSV already load. The
warehouse glob is not recursive and does not see `data/raw/pff/`, so nothing else in the
loader changes.

**The pin is split in two, because `_AN_TICK_COLUMNS`'s shape does not scale.** That dict
enumerates fifteen columns by hand and drifted once already; twenty-one tables of ~30
columns is a second hand-typed copy waiting to do the same. So
`cfb_system_maker/pff_schema.py` holds one rule that both readers import — the flattener
that writes the CSVs and `_plan_loads` that loads them — with the *table list* pinned by
hand (a table that stops being written fails loudly) and the *types* derived from the
column name. `read_csv_auto` is never used: PFF declares one column `integer` on a whole
value and `number` otherwise.

`scripts/refresh_cfbd.py` reflattens PFF before the rebuild, beside the Action Network
flatten and for the same reason — otherwise a rebuild faithfully reloads whatever CSVs
were last written by hand and a week pulled since then stays invisible.

`scripts/check_pff_pin.py` is the sibling check: all 21 tables present, every column's type
matching the rule, and every mapped `cfbd_team_id` reaching `stg.teams` (265/265, verified
against the live warehouse).

**Done when:** a rebuild lands the PFF tables, `scripts/check_an_tick_pin.py`'s sibling
check passes for PFF, and row counts match the processed CSVs.

## S6 — Backfill and 2026 ▶ parts 1–2 done 2026-09-21 — 2023 + 2024 + 2026 clean, 2014–2022 open

> **2026-09-21.** Both blockers below are cleared — `PFF_API` was rotated and the go was
> given, scoped to two seasons. **2024 and 2026 are pulled and audit clean**; 2014–2023
> are still open at ~1,800 reads + 6,090 exports. See the worklog entry of that date for
> the numbers, the season-level-leaderboard gap in the puller, and
> `#pff-export-skip-ignores-size`. The original text follows as the record of the hold.

**Held deliberately. Nothing is pulled for 2014–2024 until the process is proven on 2025.**
Every unfixed inefficiency or schema mistake is paid eleven times over, so 2025 — complete
and audited — is the reference season: prove the shape, trim the plan, then scale.

**Cost, final after S7 and gate 3: 9.0 hours, not the 14.5 first recorded** (49 min a
season × 11). The whole per-team report tier is gone, which is where the saving came from.

**Gate — all three before a backfill starts:**

1. ✅ **2026-09-10.** S3 and S5 landed: 2025 flattens and loads end to end, 21 tables and
   1.20 M rows, so the schema is known-good before it is applied to eleven more seasons.
2. ✅ **2026-09-10.** S7 landed: the pull plan is trimmed and the saving measured with the
   puller's own planner, 3,997 → 2,365 reads a season.
3. ✅ **2026-09-10 — answered: none.** The payload question was which of the team reports a
   backfill needs. S7 showed thirteen redundant; the last six were dropped by decision on
   the fact that nothing consumes them — no loader reads a `team_report_*` file, and every
   one of §3's 19 target tables is sourced from a leaderboard export. The tier was 816
   reads a season feeding nothing. Reversible: `TEAM_REPORTS` is empty rather than deleted,
   and restoring one report is a one-line change plus 136 reads for that season.

**The one remaining blocker is `#rotate-secrets-after-compromise`.** The 2026-09-09 machine
compromise means `PFF_API` is assumed disclosed, and eleven seasons of metered calls should
not run on a credential in that state. After that it is a go/no-go on 9 hours.

2026 is a separate case and is *not* held — it is mid-season (207 files, one zero-byte,
780 cells that fill as weeks are played) and its weekly pull should keep running. It just
should not gain a new tier until S7 says which ones are worth pulling.

**Done when:** `audit_pff_pull.py` reports every backfilled season clean, and the 2026
weekly pull is on the same schedule as the Action Network history job.

## S7 — Trim the pull plan, measured on 2025 ✅ 2026-09-10

2025 is the only complete season, so it is where the cost of a pull gets measured and cut.
All numbers below are from files on disk against the puller's own pacing constants
(`READ_PACING_SECONDS = 0.65`, `EXPORT_PACING_SECONDS = 3.5`) — no API calls were made to
produce them.

**What a season costs today:** 3,998 reads + 613 exports ≈ **79 min**. The per-team report
tier is 3,808 of those reads — roughly half the wall clock, and the whole difference
between a 14.5-hour and a 7-hour backfill.

### Three cuts, largest first

**1. Eleven of the nineteen team reports are a re-cut of leaderboard data.**
`python scripts/pff_tier_overlap.py --season 2025` compares each report's columns against
its matching league-wide leaderboard, in snake_case, ignoring biographical columns (the
roster pull has them) and two recoverable ones (`games_played` is `player_game_count` on
the leaderboard; `team_abbreviation` is in the directory). Result:

| | Reports | Reads/season |
|---|---|---|
| Fully covered by the leaderboard — droppable | 12 | 1,632 |
| Covered by a sibling report — droppable | 1 | 136 |
| Carry columns nothing else has — keep | 6 | 816 |

Droppable as leaderboard re-cuts: `blocking`, `coverage`, `defense`, `field-goals`,
`kick-returns`, `kickoffs`, `offense`, `passing-depth`, `punting`, `receiving-depth`,
`run-defense`, `rushing`. Where the two overlap, values agree exactly (checked on
`grades_pass`, Alabama passing).

Droppable as a sibling's subset: `run-blocking`. See *The correction* below.

Worth keeping, and why: `pass-rush` has 30 unique columns (the `lhs_*`/`rhs_*` directional
splits), `passing-pressure` 12 (`blitz_*` / `no_blitz_*` blocking grades), `pass-blocking`
10 (`snap_counts_*` by line position, plus pressure/sack rates allowed), `passing` 4
(`npa_epa`, `no_screen_epa` and their positive-EPA rates), `receiving` 1
(`team_targets_percent`), `special-teams` 1 (`total_snaps`). Whether those are worth 816
reads a season is a modelling question, not a plumbing one — but they are genuinely absent
from everything else, so dropping them is a data decision, not a free win.

Saving: **19 min a season, 3.5 h over an 11-season backfill.**

### The correction — two more reports dropped, 2026-09-10

The first pass of this step kept eight reports. Two of them did not deserve it, and both
mistakes were invisible in the summary counts:

**`offense` was never unique.** `pff_tier_overlap.py` read a leaderboard's columns only
from a `columns` envelope. Three 2025 leaderboards never landed as CSV and their JSON has
no such envelope — the shape is `{op_name: [row, ...]}` — so `facet_offense_summary` scored
**zero** columns and all 19 of the `offense` report's columns looked unique. Reading the
row keys instead: 28 columns on each side, and all 19 present on the leaderboard. The
audit's own `[json only]` line named the affected files the whole time.

**`run-blocking` is a subset of `pass-blocking`.** Its six `snap_counts_*` line-position
columns are the only ones no leaderboard has, and `pass-blocking` carries all six —
**19,206 cells across all 136 franchises, zero disagreements**, over a population 163
players larger. Unlike the eight-vs-zero payload question, this is proven redundancy, so it
is a timing decision and belongs in this step rather than in S6's gate 3.

**2. `team-rushing-direction` is pulled twice for one answer.** PFF ignores the `table`
parameter: `_rows.json` and `_totals.json` are byte-identical for all 136 franchises.
**Nothing is lost by dropping one** — the body already holds both views, `rows`
(player-grain) and `teamTotals` (franchise-grain), over the same direction vocabulary. Two
tables from one file. Saving: 136 reads a season (~1.5 min), and 1,632 junk files across a
backfill.

**3. `facet-passing-detail` stays out.** Already in `SKIP_FACETS` — the union of the other
four passing facets, and it hangs. Confirm nothing re-adds it.

### Applied 2026-09-10 — measured, not estimated

All three cuts are in `scripts/pull_pff_modeling.py`. The saving was re-measured with the
puller's own planner rather than taken from the arithmetic above:

```
python scripts/pull_pff_modeling.py --seasons 2025 --team-reports --player-facets --force --dry-run
```

| | Reads | Exports | Wall clock |
|---|---:|---:|---:|
| Before | 3,997 | 609 | ~79 min |
| After the first pass | 2,365 | 609 | ~61 min |
| After the correction | 2,093 | 609 | ~58 min |
| After gate 3 answered | 1,277 | 609 | ~49 min |
| Delta | **−2,720** | — | **−30 min** |

−2,720 is exactly all 19 reports × 136 franchises (2,584) plus the 136 duplicate
`team-rushing-direction` reads, so the cut landed where it was aimed and nowhere else. An
eleven-season backfill goes from 14.5 h to **9.0 h**. `python scripts/audit_pff_pull.py
--season 2025` is byte-identical to its pre-edit output and still exits 0 — the 2025 files
already on disk are untouched, so the type-drift and duplicate-body findings for the
dropped reports persist for that season as history, not as regressions.

`tests/test_pff_audit.py` pins all three cuts plus the audit's matching filename, because
the audit imports `TEAM_REPORTS` (so cut 1 follows it automatically) but hardcoded the
`("rows", "totals")` pair — left stale, that alone reports 136 phantom gaps a season.

**The tier decision, final: all 19 dropped.** Thirteen were shown redundant — twelve a
re-cut of the leaderboards, `run-blocking` a strict subset of `pass-blocking`. The last six
did carry columns nothing else has (`pass-rush` 30, `passing-pressure` 12, `pass-blocking`
10, `passing` 4, `receiving` 1, `special-teams` 1), and were dropped **by decision on
2026-09-10, answering S6's gate 3**: no loader reads a `team_report_*` file and no target
table in [`pff-warehouse-schema.md`](pff-warehouse-schema.md) is sourced from one, so the
tier was 816 reads a season feeding nothing.

`TEAM_REPORTS` is now empty rather than deleted, so the audit still reads it and putting a
report back is a one-line change. Files already under `data/raw/pff/team/` are untouched;
only future pulls stop. If a model later wants the directional pass-rush splits — the one
genuinely distinctive block, 30 columns — restore `pass-rush` alone and re-pull that
season for 136 reads.

**Done when:** ~~a 2025 re-pull makes ≥1,632 fewer calls~~ (planner delta verified at
exactly 1,632; the metered re-pull itself is not required to prove it),
`audit_pff_pull.py` still reports the season clean ✅, and the tier decision is recorded
here ✅.

## S8 — The player tier ✅ 2026-09-10 — deleted

`data/raw/pff/player/` held 22 files for a single id (198077, Keelon Russell) — a smoke
test someone stopped after. **Deleted.** Nothing read them: the flattener's registry is
leaderboard exports only, and `audit_pff_pull.py` counts the player tier without requiring
it, so the audit for 2025 is unchanged apart from the tier disappearing (4,657 → 4,637
files, zero defects, zero gaps, still exits 0).

The alternative was scoping a cohort, and there is nothing to scope it against yet: no
model asks for player-grain PFF data, and every graded FBS player is ~12k a season at 20
reads each. Twenty-two files for one quarterback was not coverage, it was a directory
implying coverage that did not exist — which is the specific harm this step named.

Re-pulling the same smoke test is one command and ~15 s of metered budget, so nothing is
foreclosed:

```bash
python scripts/pull_pff_modeling.py --seasons 2025 --player-ids 198077
```

**Done when:** the directory holds either a deliberate cohort or nothing. ✅ nothing.

## Worklog

Append-only. One entry per pass, newest last.

### 2026-09-08 — S1 done

Wrote `scripts/audit_pff_pull.py` and `tests/test_pff_audit.py`; 2025 comes back with
4,657 files and zero defects. Three of the audit's own checks were too narrow on the first
pass and were widened before the result was trusted: `columns` was being counted as
payload (so a team report with a full header and no rows read as usable — 3,998 files were
unverified), duplicate detection skipped every file without a week (the whole per-team
tier, which is where the 136 `team-rushing-direction` duplicates were hiding), and a
leaderboard that only ever landed as JSON was not named. Findings written to
`pff-warehouse-schema.md` §5b. Commits `f522775` (script) and `c5122a8` (widened checks,
findings doc).

### 2026-09-08 — S2 done: per-week grain

Signed off on (a). Verified rather than assumed: the union of a season's weekly headers
equals the season header exactly for both drifting facets (199, 197), the four signature
ops have no season file at all so the union is the only available schema source, and
`pull_pff_modeling.py --player-facets` was already pulling week-only — the season files on
disk are legacy `pull_pff_facet.py` output. Net effect: no puller change, S3's schema rule
becomes "union of that season's weekly headers" instead of "the season file", and the
flattener skips any leaderboard file without `_wk` in its name. Schema doc §6 amended.

### 2026-09-08 — S6 held, S7 measured on 2025

Backfill is on hold until 2025 proves the process. Wrote `scripts/pff_tier_overlap.py` to
answer the payload question with evidence rather than a guess: eleven of the nineteen team
reports are fully covered by their league-wide leaderboard once naming convention is
normalized (values agree exactly where they overlap), and eight carry columns that are
genuinely absent — the `lhs_*`/`rhs_*` pass-rush splits, the `blitz_*` blocking grades, the
`snap_counts_*` line positions, and the `npa_epa`/`no_screen_epa` family. So "drop the
per-team tier" was the wrong instinct; the right cut is eleven reports, not nineteen.

Sizing a season from file counts and the puller's pacing constants: 79 min today, 62 min
trimmed, 38 min if the eight unique-column reports also go. A backfill is 14.5 h / 11.4 h /
6.9 h respectively — which is why S6 waits.

The overlap work also surfaced a latent hole in the audit: a team report's envelope holds
`report`, `section`, `team`, `week`, `weekGroup` and `weekTo` beyond the five keys
`ENVELOPE` knew about, and `team` is a 4-key dict — so a report with `rows: []` would have
counted 4 and read as usable. All 2,584 `team_report` files sat behind that hole. `rows` is
decisive now where present, and the envelope set is complete. 2025 still audits clean.

### 2026-09-08 — sample schema, and three corrections it forced

Wrote [`pff-sample-schema.sql`](pff-sample-schema.sql): runnable DuckDB DDL for one table
per family (dimension, long split fact, wide fact with an extra key part, team-grain fact),
so S3 and S5 build against a shape rather than a paragraph. Verified by executing it — six
tables create, the season-to-date window query parses and runs, the `direction` CHECK
fires.

Grounding it in real 2025 columns rather than the §3 prose turned up three things:

- **`player_game_count` is 1 on every weekly row** (all 21 weeks of `facet_passing_summary`
  checked). §3 carries it as a fact column on ten tables; under the S2 weekly grain it
  holds nothing. Games played is `COUNT(DISTINCT week)`. Dropped from the sample.
- **`week = 0` has nothing to mark.** §3 reserved it for season-aggregate rows; S2 removed
  season files as a row source, so weeks are just 0–20 and the sentinel is gone.
- **The `team-rushing-direction` duplicate is cheaper than it looked, and §3's direction
  list is wrong.** The body holds both views — `rows` player-grain and `teamTotals`
  franchise-grain — so dropping the second call loses nothing and yields two tables from
  one file. And `direction` takes 19 values, not the 8 gaps §3 lists: end-around and
  jet-sweep by side (`EA-L/R`, `JS-L/R`), designed QB runs and scrambles (`QBK`, `QBSc`,
  `QBSn`, `QBT`, `QBF`), and `R-L`/`R-R`.

The signature line report was also mis-described from memory: it is franchise-grain (216
rows, 216 distinct franchises — all-division, per c406dcb) and carries `pbe`, `pass_snaps`
and `attempts`, not the `grades_pass_block` and `snap_counts_pass_block` first drafted.

### 2026-09-08 — S3 done: the flattener, and a split regex that was wrong twice over

`scripts/pff_flatten.py`. 29 weekly sources → 21 tables, 1.09 M rows for 2025, all of them
loading back under the pinned types and the six with DDL passing their keys and CHECKs.

The schema doc's §5.1 split regex does not survive contact with the headers, in both
directions. It **misses** eight split families (`man`, `zone`, `slot`, `true_pass_set`,
`gap`, `lhs`, `rhs`, and the time-in-pocket pair), and it **false-matches**: applied to
`facet_passing_summary`, which has no splits at all, it reads `pressure_to_sack_rate` as
split `pressure` with metric `to_sack_rate`. Splits are an enumerated set per source now,
matched longest-first, and a declared split that matches no column fails the run.

Two things only the data could have said:

- **An unsplit column is that report's own total, not the `all` row's.** The concept
  report's `dropbacks` is charted dropbacks and the time-in-pocket report's is timed
  dropbacks; neither equals `facet_passing_summary`'s. Merging them onto `all` produced
  10.9 K silent disagreements before they were given their own labels (`concept`,
  `ttt_all`, `outside`).
- **The signature outside-pass-rush report is a different population.** Its unprefixed
  `pressures` equals `lhs + rhs` on 370 of 400 rows, and its `pass_rush_snaps` disagrees
  with the facet's on 616 — so it is `outside`, not `all`.

`ttt_le_2_5`/`ttt_gt_2_5` in §3 do not exist either; PFF names them `less_*`/`more_*`, kept
relabelled so the split column says what it means. That is the fifth correction the files
have made to the prose, which is why the registry declares sources and the columns come
from the headers.

### 2026-09-09 — S4 done: 265 franchises, 11 overrides

The map is rules plus a short override list, and the rules are the interesting part: `&`
dropped rather than expanded, `St` expanded only when it is not the first token, trailing
parentheticals cut. That took the hand-mapped residue from the estimated ~35 to 11.

Two near-misses are worth keeping in mind for the next vendor map. Free suffix-stripping
matched `louisiana-monroe-warhawks` to plain `Louisiana` -- a *successful* match to the
wrong team, invisible in any coverage count. Only comparing distinct mapped ids against
mapped rows caught it; the fix is that the stripped suffix has to be a mascot CFBD knows.
And CFBD's `alternateNames` carries three-letter abbreviations (`liu`, `cal`, `sou`) that
collide across schools, so indexing them created ambiguity that looked like signal.

Also repaired a self-inflicted one: an earlier patch wrote literal backspace bytes into
`norm`'s regex in place of ``, which greps and `sed` render invisibly. The word-boundary
strip silently stopped firing, and `bryant-university-bulldogs` fell through to the
override list rather than matching by rule. Found by testing `norm` directly instead of
trusting the match count, which had stayed plausible at 264/265.

### 2026-09-09 — S5 done: 21 tables, 1.20 M rows into `stg`

The pin got split rather than copied. `_AN_TICK_COLUMNS` enumerates fifteen columns by
hand and drifted once; twenty-one tables of ~30 columns would have been that mistake at
forty times the size. So `cfb_system_maker/pff_schema.py` holds one rule imported by both
readers — `scripts/pff_flatten.py`, which writes the CSVs, and `_plan_loads`, which loads
them — with the table list pinned by hand and the types derived from the column name.

Two things only the load could have said:

- **`team` is identity, not a metric.** The JSON exports carry it beside `team_name`.
  Typed by rule it fell through to INTEGER, and DuckDB refused a file holding `"KANSAS"`.
  It is spine now.
- **`validate` was passing on files the loader then rejected.** `SELECT count(*)` over
  `read_csv` is projection-pushed down and converts no column, so a wrongly typed one
  never surfaced. It materializes into a temp table now, which is what the loader does.

`scripts/refresh_cfbd.py` reflattens PFF before the rebuild, beside the Action Network
flatten and for the same reason: without it a rebuild faithfully reloads whatever CSVs
were last written by hand, and a week pulled since then stays invisible.
`scripts/check_pff_pin.py` is the read-only sibling check — all 21 tables present, every
column's type matching the rule, and every mapped `cfbd_team_id` reaching `stg.teams`
(265/265 against the live warehouse).

### 2026-09-10 — `jersey_number` was a stub

`pff_player_season.jersey_number` was written empty on every row and never filled: the
carry-forward loop that fills `draft_season` and `eligible_season` from whichever source
supplies them did not list it, so the initializer's `""` stood. Only three sources carry
it (`offense_summary`, `passing_detail`, `rushing_direction`), which is exactly the case
the carry-forward exists for. Now 32.2% populated — the rest are players who appear only
in sources PFF does not tag with a number, not a defect.

### 2026-09-10 — S7 done: 79 → 61 min a season

The three cuts are applied and the saving re-measured with the puller's own planner rather
than trusted from the arithmetic: 3,997 → 2,365 reads for 2025, a delta of exactly 1,632 —
11 reports × 136 franchises plus the 136 duplicate `team-rushing-direction` reads. An
eleven-season backfill drops from 14.5 h to 11.2 h. The audit's 2025 output is
byte-identical before and after, which is the check that matters: the cut removed calls,
not coverage.

**The finding that outlives this step: nothing in the warehouse reads a `team_report_*`
file.** The flattener's registry is entirely `facet_*` and `signature_*` leaderboard
exports, and every one of `pff-warehouse-schema.md`'s 19 target tables — including the
single team table, which comes from `signature_pass_blocking_efficiency_line` — is sourced
from a leaderboard. In the live tree the only readers of `team_report_*` are the puller
that writes them, the audit that counts them, and `pff_tier_overlap.py`, which exists to
measure them. So the whole per-team report tier is 2,584 reads a season feeding no loader
by design, not merely none yet.

That does **not** widen the cut here. S7 is a timing step and the eight retained reports
are a payload question S6's gate 3 owns; this is evidence for that decision, recorded so
gate 3 does not have to re-derive it. Dropping the remaining eight would take a season to
38 min and the backfill to 6.9 h — the largest single lever left in the PFF pull.

One trap worth naming for whoever answers gate 3: `audit_pff_pull.py` imports
`TEAM_REPORTS`, so a cut there follows automatically, but the `team-rushing-direction`
filenames were hardcoded as a `("rows", "totals")` pair. Left stale that reports 136
phantom gaps a season — a defect that looks exactly like a failed pull. Pinned in
`tests/test_pff_audit.py` now.

### 2026-09-10 — S8 closed by deletion

Deleted the 22-file player stub. The decision rule was which of the two branches could be
reversed: deleting costs one command and ~15 s to restore, while defining a cohort commits
the backfill to a shape no model has asked for. Nothing consumed the files -- checked
against the flattener registry and the audit's expected coverage, not assumed -- and the
2025 audit is byte-identical apart from the `player` tier leaving the file census.

That leaves S6 as the only step not done or deliberately closed, and its gate (S3, S5, S7)
is now fully satisfied.

### 2026-09-10 — S7 corrected: two more reports dropped

Asked what the eight retained reports actually hold, and the answer was that two of them
hold nothing. Both errors were invisible in the summary counts and only showed up when the
column lists were read out.

`offense` was scored against a leaderboard that `pff_tier_overlap.py` had read as having
zero columns: it took columns from a `columns` envelope, and the three leaderboards that
never landed as CSV have no envelope — their JSON is `{op_name: [row, ...]}`. So all 19 of
`offense`'s columns looked unique. They are all on `facet_offense_summary`; both sides have
28 columns. The audit's `[json only]` line had been naming those files since S1.

`run-blocking` was scored correctly and is still redundant, against a sibling rather than a
leaderboard: `pass-blocking` carries all six of its `snap_counts_*` line-position columns,
identical on 19,206 cells across all 136 franchises, over a population 163 players larger.

Net: 13 of 19 team reports dropped rather than 11, a season goes 79 → 58 min, and an
eleven-season backfill 14.5 → 10.6 h. The lesson worth keeping is that "N unique columns"
is only as good as the comparison's ability to read both sides — a parser that silently
returns an empty set makes everything look novel, and a count cannot show you that.

### 2026-09-10 — gate 3 answered: the whole team tier is dropped

Decision: pull none of the nineteen per-team reports. Thirteen were already shown
redundant; the last six went on the fact that nothing consumes them. No loader reads a
`team_report_*` file, the flattener's registry is leaderboard exports end to end, and every
target table in the schema doc is sourced from a leaderboard — so six reports carrying 58
genuinely distinctive columns were still 816 reads a season feeding nothing.

A season is now 1,277 reads and ~49 min, against 3,997 and ~79 min this morning: −2,720,
which is all 19 reports × 136 franchises plus the 136 duplicate `team-rushing-direction`
reads. An eleven-season backfill is **9.0 h**, down from the 14.5 h this file has carried
since S6 was written.

Made deliberately cheap to reverse, because "nothing reads it" is a statement about today.
`TEAM_REPORTS` is an empty tuple rather than a deleted loop, files already on disk are
untouched, and `pff_tier_overlap.py` still measures all nineteen off those files, so the
evidence for the decision outlives the decision. If a model wants the `lhs_*`/`rhs_*`
directional pass-rush splits — the one block with no substitute anywhere — restoring
`pass-rush` costs one line and 136 reads a season.

That closes S6's last gate. It now waits only on the secrets rotation and a go.

### 2026-09-21 — S6 part 1: 2024 and 2026 pulled, `PFF_API` rotated

**Both gates cleared.** The user rotated `PFF_API` at the provider and pasted the new key
into `env.env` directly — it never passed through a chat transcript, which is the whole
point given the key it replaced was the one assumed disclosed on 2026-09-09. Verified by
fingerprint rather than by reading it: `sha256[:12]` moved `fd12be007189` → `c71ccd25d534`,
same 35-byte length. Then the explicit go, scoped to **two seasons, not eleven** — 2024 and
2026.

**The run.** `python scripts/pull_pff_modeling.py --seasons 2024,2026 --player-facets`:
369 reads, 1,131 exports, **0 failed, 89.8 min**. The planner predicted ~70 min; the 28%
overrun is the export tier drifting from the 3.5 s pacing constant to ~4.0 s/export under
a sustained run, so `EXPORT_PACING_SECONDS` is optimistic at length. Worth knowing before
pricing the remaining nine seasons off the planner's estimate.

A 99-read probe ran first, against 2014–2024 week 0, for two reasons: `--dry-run` refuses
without a `team_directory_<season>.json` on disk, and a live read is the only proof the new
key authenticates. It left ~90 stray week-0 rows for 2016–2023 in `team_game.csv`
(4 in 2016, 10 in 2017, … 20 in 2023) — real data, harmless, and they disappear into the
full seasons whenever 2014–2023 is pulled.

**2024 needed a second pull the planner does not cover.** The first audit came back with
**25 missing cells, every one a season-level leaderboard** — `--player-facets` plans weekly
exports only, and the 23 season-level (no-`--week`) CSVs 2025 carries have no equivalent in
`pull_pff_modeling.py`'s plan at all. Closed with
`python scripts/pull_pff_facet.py all --league ncaa --season 2024 --division fbs`: 26 of 28
exported in ~2 min. **This is a gap in the puller, not in the pull** — any future season
backfilled through `pull_pff_modeling.py` alone will land 25 cells short the same way.

**Audit verdicts.**

| | 2024 | 2026 |
|---|---|---|
| Files (usable) | 825 (825) | 471 (346) |
| Defects | **0** | 125 |
| Duplicate bodies | 0 | 1 op |
| Declared-type drift | 0 | 0 |
| Missing cells | **0** | 493 |
| Column drift | 3 ops | 3 ops |

**2024 is clean** and matches 2025's shape: the 3 column-drift ops
(`facet-passing-concept`, `facet-passing-pressure`, `signature-passing-time-in-pocket`) and
the 3 json-only leaderboards (`facet-offense-summary`, `facet-passing-detail`,
`facet-rushing-direction`) are the same families 2025 shows, and the 134 franchises with
"team coverage" gaps are the per-team report tier S7 dropped on purpose. The audit counts
that tier in its census whether or not `TEAM_REPORTS` is populated, so **134 gaps is the
expected reading for a trimmed season, not a defect** — 2025 reads differently only because
it was pulled before the trim, with 3,998 team files to 2024's 190.

**2026's 125 defects are all "no rows", and all in wk4–wk20** — 7 or 8 files a week across
seventeen unplayed weeks. The season is complete through wk3 (games: wk0 77, wk1 132,
wk2 131, wk3 128), which is correct for 2026-09-21. The single duplicate-body op is
`team_overview` returning identical bytes for wk4 through wk20, which is the same fact seen
from the other side: PFF answers a future week with the current standing. **None of this is
sticky** — `wanted()` short-circuits on `season == live`, so every current-season file is
re-pulled on every run and fills in as weeks are played.

**One real defect found and fixed, and it exposes a bug.**
`facet_defense_coverage_ncaa_2026_fbs_wk1.csv` was **zero bytes, dated 2026-09-08** — a
played week sitting empty since the original 2026 pull. The 89.8-minute run did not repair
it. Cause: the export planner's skip test is existence-only —

```python
if args.force or not any((args.out_dir / f"{stem}{ext}").exists() for ext in (".csv", ".json")):
```

— while the read path's `wanted()` checks size too (`not dest.stat().st_size`). So a
zero-byte export is treated as done. An explicit re-pull recovered **2,578 rows × 40 cols**.
Outside the live season a file like this is skipped *forever*; `find data/raw/pff -name
'*.csv' -size 0` now returns nothing, so 2024–2026 are clear, but the defect is latent for
every season 2014–2023 will pull. Tracked as `#pff-export-skip-ignores-size`.

The two `FAIL` lines in the wk1 re-pull (`facet-defense-coverage-matchup`,
`facet-receiving-coverage`, both `upstream 500`) are expected: they are two of the three
ids in `SKIP_FACETS`, pinned out because PFF 500s on them.

**State after this run.** `data/processed/pff/team_game.csv` is 10,064 rows × 39 cols —
2024 3,340, 2025 3,406, 2026 3,228, plus the ~90 probe rows. `data/raw/pff` grew 323 MB →
~490 MB.

**S6 is not done.** 2014–2023 remain: **1,800 reads + 6,090 exports, ~375 min planned**,
which the pacing drift above puts nearer 8 hours in practice, plus ~2 min a season of
season-level leaderboards the planner omits. Fixing `#pff-export-skip-ignores-size` before
that run is cheap insurance — otherwise every zero-byte export it produces is permanent.

**Addendum — the flatten and load hop, same day.** The entry above stopped at hop 1. Hops
2 and 3 ran after it: `pff_flatten.py --validate` over every season on disk, then
`check_pff_pin.py`.

Every column resolved — none of 2024's three column-drift ops broke the split rule, which
was the live risk, since the rule fails hard on an unrecognized column. **One table did
fail**: `pff_rushing_direction`, on `CHECK constraint failed`. Two direction codes the
2025-only pull never emitted — `NV` (39 rows across all raw files) and `LP-R` (1) — against
a CHECK enumerating 19. Both are real: `NV` rows carry ordinary attempts and yards, so it
is an uncharted-run bucket, not a null marker. Widened to 21 in `pff-sample-schema.sql`
with the reasoning at the constraint; `--validate` then reported 0 FAILs across 21 tables
and `check_pff_pin.py` exited 0 (21/21 tables, types ok, join ok).

**Scope of that failure, stated precisely:** the CHECK exists only in the sample DDL, which
`--validate` loads into. `cfb_system_maker/pff_schema.py` has no direction constraint, so
the live load was never at risk and the nightly would have taken both values silently. This
was documentation drift that `--validate` caught — which is the argument for running it by
hand after a new season rather than trusting the next scheduled refresh.

**`stg` is still at the pre-2024 counts** (1,429,515 rows) and that is expected. The
processed CSVs now hold ~2.67 M rows, and `refresh_cfbd.py` calls `_flatten_pff()` before
`build_duckdb`, so the next scheduled refresh loads them. No hand rebuild was run: a full
rebuild is ~26 min and has twice dropped `stg.an_*` under memory pressure, which is not a
risk worth taking to land data the nightly picks up anyway.

**Untouched, and named so it is not mistaken for done:** S6's done-when has a second clause
— *"and the 2026 weekly pull is on the same schedule as the Action Network history job."*
Nothing here scheduled anything. 2026 is complete through wk3 because it was pulled by
hand today, not because a job keeps it that way.

### 2026-09-21 (later) — S6 part 2: 2023 closed, and its residual is a vendor gap

2023 was pulled earlier the same evening (raw file mtimes run 20:21–21:22, ~1 h). This entry
covers the residual sweep that closed it, not that pull.

`audit_pff_pull.py --season 2023` at the start: **770 files, 8 defects, 55 missing cells**.
`pull_pff_modeling.py --seasons 2023 --player-facets` planned **0 reads, 54 exports, ~3 min**
and ran in **3.8 min, 0 failed** — and landed **zero new files**. That is not a failure: all 54
cells are weeks **14 and 16**, and both come back `SKIP: no data` (blank CSV *and* an empty JSON
body, `pull_pff_facet.pull_one`). Probed directly to be sure the week ids were not the problem:

| cell | result |
| --- | --- |
| `facet-defense-coverage` 2023 wk14 | `SKIP: no data` |
| `facet-defense-coverage` 2023 wk16 | `SKIP: no data` |
| `facet-defense-coverage` 2023 wk15 (control) | `ok  17 rows, 40 cols` |

**Both weeks are correct, not vendor defects** — the schedule explains them, and the reason is
worth recording because it will recur in 2014–2022:

- **wk16 had no games at all.** `games_2023_wk16.json` is `{"games": []}`, and all 8 audit
  defects are that same week's team files (`games`, 7 × `team_stats`).
- **wk14 had 8 games and every one was FCS** — Chattanooga @ Furman, NDSU @ Montana State,
  Richmond @ Albany, and five more playoff games. The leaderboard exports are `--division fbs`
  pinned (`docs/pff-cli.md`: never leave it unpinned on NCAA), so an empty FBS leaderboard for
  an all-FCS week is the right answer.

`team-stats` is the apparent contradiction and resolves the same way: it is **not**
division-pinned, so `team_stats_2023_wk14_offense-passing.json` carries **16 rows — the 16 FCS
teams that played** — against 150 in wk13, 10 in wk15 (5 games) and 0 in wk16. wk15 returning
17 leaderboard rows is Army @ Navy, the one FBS game in it. Everything lines up.

2024 and 2025 carry all 21 weeks for the same op because both had FBS games in every week.
Nothing to fix here; re-pulling costs 3 min and correctly returns nothing.

**One cell was a real gap and is now filled.** The audit counted 55 where the planner counted
54; the 55th was the **season-level** (no-`--week`) `facet-offense-pass-blocking`, which
`--player-facets` never plans — the same omission recorded for 2024 above.
`pull_pff_facet.py facet-offense-pass-blocking --league ncaa --season 2023 --division fbs`
returned **3,075 rows × 30 cols**. 2023's season-level count is now **26**, matching 2024 and
2025 exactly (diffed by name, zero residual).

**Final audit: 771 files (763 usable), tiers {leaderboard: 581, team: 190}, weeks 0–20, exit 0.**
Everything it still reports is named:

- **8 defects** — 2023 wk16, a week with no games.
- **54 missing cells** — 2023 wk14 (all-FCS week, FBS-pinned export) and wk16 (no games).
- **133 team-coverage gaps** — the per-team report tier S7 dropped; the expected reading for a
  trimmed season, same as 2024's 134.
- **3 column-drift ops, 3 JSON-only leaderboards** — pre-existing and unchanged by this sweep.

`team_game.csv` stands at **13,312 rows** — 2023 3,268, 2024 3,340, 2025 3,406, 2026 3,228, plus
the ~90 probe rows. 2023's share landed in the earlier run, not this sweep; every
`pull_pff_modeling.py` run rebuilds the file from all seasons on disk, so the 3.8-min run
reproduced the same number from the same inputs. No warehouse rebuild was run, for the reason
given in the addendum above: `refresh_cfbd.py` reflattens before `build_duckdb`, so the one new
CSV lands on the next scheduled refresh.

**Still open: 2014–2022.** The TODO's ~8 h figure was priced for 2014–2023; 2023 is now off it.
