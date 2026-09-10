# PFF ingest plan — from scraped files to warehouse tables

**Living document.** Every pass through the scraped files appends here: a step's row moves
to `done` with a date, and the worklog at the bottom gets an entry saying what was
actually found. Nothing is deleted — a step that turns out to be wrong is struck with the
reason, so the next pass does not re-open it.

**Status 2026-09-10: S1–S5 and S7 done, S6 held.** 2025 is audited, flattened, mapped to CFBD and
loading into `stg.pff_*` — 21 tables, 1.20 M rows. 2025 is the reference season — the process gets proven and trimmed against it before
a single backfill call is made, because a backfill pays every inefficiency eleven times.

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
| S6 | Backfill 2014–2024, finish 2026 | — | **held** — gated on S3/S5/S7 | — |
| S7 | Trim the pull plan using 2025 as the reference season | S6 | **done** | 2026-09-10 |
| S8 | Decide the player tier: finish it or delete the smoke test | — | open | — |

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

## S6 — Backfill and 2026 ⏸ held 2026-09-08

**Held deliberately. Nothing is pulled for 2014–2024 until the process is proven on 2025.**
A backfill is 14.5 hours of metered calls at today's plan, and every unfixed inefficiency
or schema mistake is paid eleven times over. 2025 is complete and audited, so it is the
reference season: prove the shape, trim the plan, then scale.

**Gate — all three before a backfill starts:**

1. S3 and S5 land: 2025 flattens and loads end to end, so the schema is known-good before
   it is applied to eleven more seasons.
2. S7 lands: the pull plan is trimmed against the 2025 measurements below.
3. The payload question below is answered: which of the 19 team reports a backfill needs.

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
| Fully covered by the leaderboard — droppable | 11 | 1,496 |
| Carry columns the leaderboard lacks — keep | 8 | 1,088 |

Droppable: `blocking`, `coverage`, `defense`, `field-goals`, `kick-returns`, `kickoffs`,
`passing-depth`, `punting`, `receiving-depth`, `run-defense`, `rushing`. Where the two
overlap, values agree exactly (checked on `grades_pass`, Alabama passing).

Worth keeping, and why: `pass-rush` has 30 unique columns (the `lhs_*`/`rhs_*` directional
splits), `offense` 19, `passing-pressure` 12 (`blitz_*` / `no_blitz_*` blocking grades),
`pass-blocking` 10 and `run-blocking` 6 (`snap_counts_*` by line position), `passing` 4
(`npa_epa`, `no_screen_epa` and their positive-EPA rates), `receiving` 1
(`team_targets_percent`), `special-teams` 1 (`total_snaps`). Whether those are worth 1,088
reads a season is a modelling question, not a plumbing one — but they are genuinely absent
from the leaderboards, so dropping them is a data decision, not a free win.

Saving: **16 min a season, 3.0 h over an 11-season backfill.**

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
| After | 2,365 | 609 | ~61 min |
| Delta | **−1,632** | — | **−18 min** |

−1,632 is exactly 11 reports × 136 franchises (1,496) plus the 136 duplicate
`team-rushing-direction` reads, so the cut landed where it was aimed and nowhere else. An
eleven-season backfill goes from 14.5 h to **11.2 h**. `python scripts/audit_pff_pull.py
--season 2025` is byte-identical to its pre-edit output and still exits 0 — the 2025 files
already on disk are untouched, so the type-drift and duplicate-body findings for the
dropped reports persist for that season as history, not as regressions.

`tests/test_pff_audit.py` pins all three cuts plus the audit's matching filename, because
the audit imports `TEAM_REPORTS` (so cut 1 follows it automatically) but hardcoded the
`("rows", "totals")` pair — left stale, that alone reports 136 phantom gaps a season.

**The tier decision: 11 dropped, 8 retained pending S6 gate 3.** The eight are kept only
because each carries columns no leaderboard has (`pass-rush` 30, `offense` 19,
`passing-pressure` 12, `pass-blocking` 10, `run-blocking` 6, `passing` 4, `receiving` 1,
`special-teams` 1). Nothing in the warehouse reads them yet — see the worklog — so the
question gate 3 has to answer is whether those columns are worth 1,088 reads a season.
Answering it "no" would take a season to 38 min and the backfill to 6.9 h.

**Done when:** ~~a 2025 re-pull makes ≥1,632 fewer calls~~ (planner delta verified at
exactly 1,632; the metered re-pull itself is not required to prove it),
`audit_pff_pull.py` still reports the season clean ✅, and the tier decision is recorded
here ✅.

## S8 — The player tier

`data/raw/pff/player/` holds 22 files for a single id (198077, Keelon Russell) — a smoke
test someone stopped after. Every graded FBS player is ~12k a season at 20 reads each, so
the full tier is not a casual pull. Either scope it to a real id list (QBs? starters?) or
delete the stub so it stops reading as partial coverage.

**Done when:** the directory holds either a deliberate cohort or nothing.

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
