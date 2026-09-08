# PFF warehouse schema — folding 30 report shapes into 19 tables

**Measured 2026-09-08** against `data/raw/pff/` (148 files, 58 MB: 26 facet reports × 2
seasons, 4 signature reports × 24 weeks). Every claim below was checked against those files
with a script, not read off the OpenAPI document. Companion docs:
[`pff-cli.md`](pff-cli.md) (pull mechanics) and
[`pff-endpoint-reference.md`](pff-endpoint-reference.md) (parameters).

This is a schema proposal. No loader code exists for it yet; §5 says what would have to.

## 1. What is on disk

Two shapes. **Facet** files are season aggregates, one row per player per franchise,
pulled with `--division fbs`. **Signature** files are one week each, take no `--division`,
and therefore cover every NCAA division (266 franchises in a 2025 week vs 146 in the FBS
facet files).

| Report | Grain | 2025 rows | Cols | Shape |
| --- | --- | ---: | ---: | --- |
| `offense_summary` (JSON) | player-season | 6,266 | 25 | spine + 8 snap counts + 3 grades |
| `passing_summary` | player-season | 569 | 44 | base passing metrics |
| `passing_depth` | player-season | 607 | 554 | same metrics × {behind_los, short, medium, deep} × {all, left, center, right} |
| `passing_pressure` | player-season | 607 | 197 | same metrics × {pressure, no_pressure, blitz, no_blitz} |
| `passing_concept` | player-season | 607 | 199 | same metrics × {pa, npa, screen, no_screen} |
| `passing_detail` (JSON) | player-season | 569 | 988 | **union of the four above** (see F5) |
| `passing_allowed_pressure` | player-season | 414 | 32 | pressures by blocker slot |
| `receiving_summary` | player-season | 2,398 | 47 | base receiving metrics |
| `receiving_depth` | player-season | 2,398 | 505 | same × 16 depth/direction buckets |
| `receiving_scheme` | player-season | 2,398 | 71 | same × {man, zone} |
| `receiving_concept` | player-season | 2,398 | 71 | same × {screen, slot} |
| `rushing_summary` | player-season | 1,727 | 47 | flat |
| `rushing_direction` (JSON) | player-season-direction | 1,707 × 8 | 12 | already nested long |
| `offense_blocking` | player-season | 6,052 | 31 | alignment snaps + pass-block + run-block base |
| `offense_pass_blocking` | player-season | 3,400 | 30 | pass-block base × {all, true_pass_set} |
| `offense_run_blocking` | player-season | 5,884 | 22 | run-block base × {all, gap, zone} |
| `defense_summary` | player-season | 5,767 | 55 | flat, alignment snaps |
| `defense_coverage` | player-season | 4,126 | 40 | base coverage metrics |
| `defense_coverage_scheme` | player-season | 4,007 | 65 | same × {man, zone} |
| `defense_pass_rush` | player-season | 4,296 | 34 | base × {all, true_pass_set} |
| `defense_run` | player-season | 5,607 | 24 | flat |
| `field_goal_summary` | player-season | 231 | 30 | {attempts, made, percent} × 7 distance bands |
| `kickoff_summary` | player-season | 287 | 23 | flat |
| `punting_summary` | player-season | 201 | 29 | flat |
| `return_summary` | player-season | 1,039 | 26 | 7 metrics × {kickoff, punt} |
| `special_summary` | player-season | 10,271 | 27 | 7 ST snap counts + 10 ST grades |
| `signature_passing_time_in_pocket` | player-**week** | ~450/wk | 91 | passing metrics × {less, more} (2.5 s) |
| `signature_defense_outside_pass_rush` | player-week | ~4,400/wk | 40 | pass-rush metrics × {all, lhs, rhs} |
| `signature_defense_slot_coverage` | player-week | ~1,200/wk | 17 | 12 coverage metrics, slot only |
| `signature_pass_blocking_efficiency_line` | **team**-week | ~270/wk | 10 | 7 metrics, no player |

Not on disk: `receiving_coverage` and `defense_coverage_matchup` (upstream 500 on every
NCAA pull, see `pff-cli.md`). Three reports are JSON because their CSV export is blank.

## 2. Findings that drive the merges

**F1 — the identity spine is repeated in all 30 files.** `player, player_id, position,
team_name, franchise_id, player_game_count` is in every player-grain file. Three
(`offense_summary`, `passing_detail`, `rushing_direction`) add `team` (a duplicate of
`team_name`), `jersey_number`, `draft_season`, `eligible_season`. Within one season file a
`player_id` never appears twice, and never on two franchises. Between seasons 806 of 2,802
returning defenders changed franchise, so franchise is a season attribute of a player, not
a player attribute.

**F2 — `franchise_id` is a stable team key; `team_name` is not a CFBD name.** No franchise
maps to two names across both seasons. Names are PFF abbreviations (`WASH STATE`, `MIAMI
FL`, `LA LAFAYET`): 79 of 146 match `stg.teams.school` exactly, 24 more match
`abbreviation`, ~35 need a hand map, and ~8 are all-star rosters (`AIN HULA`, `AMER SENR`,
`EAST SHRNE`, `HBCUGA`, …) that `--division fbs` deliberately includes.

**F3 — season-level grades and penalties are copied verbatim into every facet on that side
of the ball.** Verified identical on every overlapping row: `grades_defense`,
`grades_run_defense`, `grades_pass_rush_defense` (coverage/run/pass_rush vs
`defense_summary`), `grades_offense`, `grades_pass`, `grades_pass_route`,
`grades_hands_fumble` (passing/rushing/receiving/blocking vs each other and
`offense_summary`), and `penalties`. The *counting* stats are **not** copies — `tackles`
in `defense_coverage` are coverage tackles and differ from `defense_summary` on 3,446 of
4,126 rows, and `player_game_count` is phase-scoped (differs on 830 rows). So: grades and
penalties are player-season facts that belong in one place; counts stay with their phase.

**F4 — every "split" report is the base report's metric set under a prefix.** Measured
overlap of the stripped bucket columns against the base report:

| Split report | Buckets | Bucket metrics | Shared with base | Bucket-only | Base-only |
| --- | --- | ---: | ---: | --- | --- |
| `defense_coverage_scheme` | man, zone | 28 | 27 | `snap_counts_coverage_percent` | 6 season grades + penalties |
| `passing_depth` | 16 | 34 | 33 | `attempts_percent` | grades, penalties |
| `passing_pressure` | 4 | 46 | 36 | `dropbacks_percent`, 8 split-level grades | penalties |
| `passing_concept` | 4 | 47 | 36 | same as pressure | penalties |
| `receiving_depth` | 16 | 31 | 30 | `targets_percent` | grades, alignment rates, penalties |
| `receiving_scheme` | man, zone | 31 | 30 | `targets_percent` | same |
| `receiving_concept` | screen, slot | 31 | 30 | `targets_percent` | same |
| `time_in_pocket` (sig) | less, more | 46 | 36 | `dropbacks_percent`, 4 grades | penalties |

Each split family is one metric set with one extra dimension. Wide, that is 554 + 197 +
199 + 44 = 994 passing columns across four files; long, it is ~50 columns and a `split`
key.

**F5 — `passing_detail` is redundant.** Its 988 columns are the union of
`passing_summary`, `passing_depth`, `passing_pressure` and `passing_concept` (964 shared)
plus 27 `<split>_grades_{pass,run,screen}_block` columns, i.e. blocking grades on a QB
table. It is also the report that hung for 15 minutes and whose CSV export is blank. Drop
it from the pull; nothing is lost.

**F6 — summary vs component reports are not duplicates of each other.** `defense_summary`
has 17 columns none of the three defense components carry (alignment snap counts `box`,
`slot`, `dl_a_gap`…, `tackles_for_loss`, `safeties`, fumble recoveries) and the components
have 31 it lacks. `offense_blocking` likewise has the line-slot snap counts
(`snap_counts_lt/lg/ce/rg/rt/te`) that `pass_blocking`/`run_blocking` lack, while its
pass-block and run-block columns are exact copies of theirs (`pbe` identical on all 3,400
rows). Keep both levels; strip the copies.

**F7 — the schema already drifted between 2025 and 2026.** The 2026 pulls of
`passing_concept`, `passing_pressure` and `passing_detail` dropped 24–52
`<split>_grades_*defense*` columns (defensive grades on a passing report). Every other
report is column-identical across seasons. A long split table absorbs this; a wide one
needs a migration per drift.

**F8 — the wide split files are 16–18% blank cells** (`passing_depth` 16.3%,
`receiving_depth` 17.7%): buckets a player never threw into. Long form simply has no row.

**F9 — signature stats are per-week, not season-to-date.** A QB's `dropbacks` is 58 in
week 1 and 34 in week 2 with `player_game_count` 1 in each. Season totals are `SUM`.
`pass_blocking_efficiency_line` is the only team-grain report in the set.

## 3. Proposed tables

All under `stg.pff_*`, written flat by a flattener to `data/processed/pff/` and loaded
straight to `stg` the way `massey_*` and `an_history_tick` already are. `data/raw/pff/`
keeps the exports as landed; the loader's `data/raw/*.json` glob is not recursive, so they
never mint tables on their own.

Conventions: `season INTEGER` and `week INTEGER` come from the filename; `week` is `0` on
season-aggregate rows (not NULL — DuckDB rejects NULL in a primary key, checked). `pulled_at DATE` is the file mtime, because a facet season file is a
snapshot of the season *so far* and a re-pull overwrites it (see §6). Column names stay
PFF's, minus the split prefix.

### Dimensions (2)

| Table | Key | Columns | Source |
| --- | --- | --- | --- |
| `pff_franchise` | `franchise_id` | `team_name, kind ('team' \| 'allstar'), cfbd_team_id, match` | union of every file; `cfbd_team_id`/`match` maintained like `massey_teams` |
| `pff_player_season` | `(season, player_id)` | `franchise_id, player, position, jersey_number, draft_season, eligible_season` | `offense_summary` ∪ `defense_summary` ∪ `special_summary`, jersey/draft/eligible from `offense_summary` and `rushing_direction` where present |

### Player-season grades (1)

| Table | Key | Columns |
| --- | --- | --- |
| `pff_player_season_grades` | `(season, player_id)` | `penalties, declined_penalties`, offense: `grades_offense, grades_offense_penalty, grades_pass, grades_run, grades_pass_block, grades_run_block, grades_pass_route, grades_hands_drop, grades_hands_fumble`; defense: `grades_defense, grades_defense_penalty, grades_coverage_defense, grades_pass_rush_defense, grades_run_defense, grades_tackle`; ST: the 10 `grades_*` on `special_summary` plus `grades_fgep_kicker, grades_kickoff_kicker, grades_punter, grades_kick_return, grades_punt_return, grades_return` |

Built by coalescing across the season summaries (F3 says they agree). Every other table
below drops its unprefixed `grades_*`, `penalties` and `declined_penalties` columns.
Prefixed split grades (`man_grades_coverage_defense`, `pressure_grades_pass`) are *not*
season grades — they are the grade within that split and stay on the split row.

### Long split facts (4)

Key `(season, week, player_id, franchise_id, split)`; `week = 0` for facet rows.

| Table | `split` values | Metric cols | Feeds from |
| --- | --- | ---: | --- |
| `pff_passing` | `all`; `behind_los, short, medium, deep`; `{left,center,right}_{behind_los,short,medium,deep}`; `pressure, no_pressure, blitz, no_blitz`; `pa, npa, screen, no_screen`; weekly `ttt_le_2_5, ttt_gt_2_5` | 38 + `attempts_percent, dropbacks_percent` + split grades `grades_pass, grades_offense, grades_run, grades_hands_fumble` | `passing_summary` (all), `passing_depth`, `passing_pressure`, `passing_concept`, `signature_passing_time_in_pocket` |
| `pff_receiving` | `all`; 16 depth/direction; `man, zone`; `screen, slot` | 30 + `targets_percent` + `grades_hands_drop, grades_pass_route` | `receiving_summary` (all, plus its alignment cols `inline_*, slot_*, wide_*` on the `all` row), `receiving_depth`, `receiving_scheme`, `receiving_concept` |
| `pff_defense_coverage` | `all, man, zone`; weekly `slot` | 27 + `snap_counts_coverage_percent`, `grades_coverage_defense` | `defense_coverage`, `defense_coverage_scheme`, `signature_defense_slot_coverage` (rename `coverage_snaps` → `snap_counts_coverage`) |
| `pff_defense_pass_rush` | `all, true_pass_set`; weekly `all, lhs, rhs` | 13 + `grades_pass_rush_defense` | `defense_pass_rush`, `signature_defense_outside_pass_rush` (rename `pressures` → `total_pressures`, `pass_rush_snaps` → `snap_counts_pass_rush`, `misses` → `missed_tackles`) |

`base_attempts`, `base_dropbacks`, `base_targets`, `base_snap_counts_coverage` are the
denominators for the `*_percent` columns and equal the `all` row's count; drop them.

### Remaining player-season facts (10)

Key `(season, player_id, franchise_id)` plus `player_game_count` (phase-scoped, F3).

| Table | Cols | Source, minus spine and season grades |
| --- | ---: | --- |
| `pff_offense_snaps` | 8 | `offense_summary` snap counts |
| `pff_passing_allowed_pressure` | 26 | as is; wide by blocker slot is fine at 26 |
| `pff_rushing` | 40 | `rushing_summary`; its `receptions, targets, routes, grades_pass_route` duplicate `pff_receiving` `all` rows exactly and can go |
| `pff_rushing_direction` | 12 | `rushing_direction.directions[]`, key adds `direction` (LE RE LT RT LG RG ML MR) |
| `pff_pass_blocking` | 12 × `split ∈ {all, true_pass_set}` | `offense_pass_blocking` |
| `pff_run_blocking` | 5 × `split ∈ {all, gap, zone}` | `offense_run_blocking` |
| `pff_blocking_alignment` | 9 | `offense_blocking` alignment snaps only (`snap_counts_{lt,lg,ce,rg,rt,te,block,offense}`, `block_percent`); its pass/run block columns are copies (F6) |
| `pff_defense_summary` | 42 | `defense_summary` |
| `pff_defense_run` | 12 | `defense_run` |
| `pff_special_teams` | 10 | `special_summary` snap counts + `tackles, assists, missed_tackles` |

### Kicking game (3) and the one team table (1)

| Table | Key | Cols | Note |
| --- | --- | ---: | --- |
| `pff_kicking` | player-season | 42 | `field_goal_summary` full outer join `kickoff_summary` on the spine: 169 of the 231 FG kickers also kick off, same grain, both flat. FG bands stay wide; 7 × 3 is small |
| `pff_punting` | player-season | 24 | `punting_summary` — only 45 of 201 punters also kick off, so it stays its own table |
| `pff_return` | player-season | 20 | `return_summary` |
| `pff_team_pass_block_week` | `(season, week, franchise_id)` | 7 | `signature_pass_blocking_efficiency_line` |

**Total: 19 tables from 30 report shapes**, 4 dimension/grade tables and 15 facts. Widest
table is `pff_rushing` at ~40 columns, down from 988.

## 4. DDL for the non-obvious ones

```sql
CREATE TABLE stg.pff_franchise (
    franchise_id  INTEGER PRIMARY KEY,
    team_name     VARCHAR NOT NULL,
    kind          VARCHAR NOT NULL CHECK (kind IN ('team', 'allstar')),
    cfbd_team_id  INTEGER,          -- stg.teams.teamId; NULL until mapped
    match         VARCHAR           -- 'exact' | 'abbreviation' | 'manual' | NULL
);

CREATE TABLE stg.pff_player_season (
    season          INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    franchise_id    INTEGER NOT NULL REFERENCES stg.pff_franchise,
    player          VARCHAR NOT NULL,
    position        VARCHAR,
    jersey_number   VARCHAR,        -- string: '09', '00', 'D01' are real values
    draft_season    INTEGER,
    eligible_season INTEGER,
    PRIMARY KEY (season, player_id)
);

CREATE TABLE stg.pff_passing (
    season            INTEGER NOT NULL,
    week              INTEGER NOT NULL,  -- 0 = season aggregate from a facet pull
    player_id         INTEGER NOT NULL,
    franchise_id      INTEGER NOT NULL,
    split             VARCHAR NOT NULL,  -- 'all', 'short', 'left_deep', 'pressure', 'pa', 'ttt_le_2_5', ...
    player_game_count INTEGER,
    attempts INTEGER, aimed_passes INTEGER, completions INTEGER, yards INTEGER,
    touchdowns INTEGER, interceptions INTEGER, sacks INTEGER, dropbacks INTEGER,
    passing_snaps INTEGER, first_downs INTEGER, big_time_throws INTEGER,
    turnover_worthy_plays INTEGER, drops INTEGER, bats INTEGER, hit_as_threw INTEGER,
    scrambles INTEGER, spikes INTEGER, thrown_aways INTEGER, def_gen_pressures INTEGER,
    accuracy_percent DOUBLE, completion_percent DOUBLE, ypa DOUBLE, qb_rating DOUBLE,
    avg_depth_of_target DOUBLE, avg_time_to_throw DOUBLE, btt_rate DOUBLE, twp_rate DOUBLE,
    drop_rate DOUBLE, sack_percent DOUBLE, pressure_to_sack_rate DOUBLE, epa DOUBLE,
    positive_epa_percent DOUBLE, attempts_percent DOUBLE, dropbacks_percent DOUBLE,
    grades_pass DOUBLE, grades_offense DOUBLE, grades_run DOUBLE, grades_hands_fumble DOUBLE,
    pulled_at DATE NOT NULL,
    PRIMARY KEY (season, week, player_id, franchise_id, split)
);
-- pff_receiving, pff_defense_coverage, pff_defense_pass_rush: same key, their metric set.
```

`week = 0` rather than NULL because DuckDB enforces NOT NULL on every primary-key column
(`Constraint Error: NOT NULL constraint failed`, tested on 1.x).

## 5. What has to exist for this to load

1. **`scripts/pff_flatten.py`** — reads `data/raw/pff/*`, writes one CSV per table above
   to `data/processed/pff/`. The split unpivot is one regex per family:
   `^(behind_los|short|medium|deep|(left|center|right)_(behind_los|short|medium|deep)|pressure|no_pressure|blitz|no_blitz|pa|npa|screen|no_screen)_(.+)$`
   → `(split, metric)`. Season, week and division come from the filename:
   `^(facet|signature)_(?P<report>.+?)_ncaa_(?P<season>\d{4})(?:_(?P<division>fbs|fcs|lower))?(?:_wk(?P<week>\d+))?\.(csv|json)$`.
2. **Loader plan entries** — a `_PFF_TABLES` tuple beside `_MASSEY_TABLES` in
   `duckdb_load.py`, straight to `stg`, no `raw` twin, same as Massey. Nothing else in the
   loader changes; the glob does not see `data/raw/pff/`.
3. **`pff_franchise` hand map** — ~35 names. Same shape as `massey_teams.match`; the
   `stg.teams.alternateNames` table is the first place to look before hand-typing.
4. **Pull schedule change** — drop `facet-passing-detail` from `pull_pff_facet.py all`
   (F5). It is the slowest report and adds nothing.
5. **Signature division tag** — the 2025 signature files are all-division. Either filter
   to franchises present in the same season's FBS facet files at flatten time, or keep every
   row and let `pff_franchise.kind`/`cfbd_team_id` do the filtering downstream. The second is
   less code and loses nothing.

## 6. Open decisions

- **Point-in-time.** A facet season file is season-to-date at pull time and a re-pull
  overwrites it, so the 2026 files are "through week 2" and will silently become "through
  week 3". For the no-lookahead rule that is a problem: a pre-game feature built from
  `pff_passing` `week = 0` rows leaks the rest of the season. Two fixes, pick one:
  (a) pull facets weekly with `--week N` (every facet takes it) so every row is a
  per-week row like the signature stats and season-to-date is a windowed `SUM`; or
  (b) keep season pulls but name the file with the pull date and keep every snapshot.
  (a) is the same shape as the signature data and the cleaner warehouse; it costs 26
  exports per week, well inside the 20/minute budget.
- **2-bucket tables.** `pff_pass_blocking`, `pff_run_blocking` and `pff_defense_pass_rush`
  could stay wide (`true_pass_set_*`, `gap_*`, `zone_*`) at under 35 columns each. They
  are long above only so that every split in the warehouse reads the same way. Wide is
  defensible; say so and the flattener is simpler.
- **`grades_run_block` disagrees between `offense_blocking` and `offense_summary` on 166
  of 6,052 rows** (every other grade checked matched exactly). Unexplained; the grades
  table should take `offense_summary` and the discrepancy is worth one look.
- **All-star rows.** `--division fbs` includes ~8 all-star franchises. They are harmless in
  the dimension with `kind = 'allstar'`, but a player who appears on a real team *and* an
  all-star roster in one season breaks the `(season, player_id)` key of
  `pff_player_season`. Not observed in 2025 or 2026 (zero duplicate `player_id` in any
  file), but the flattener should assert it rather than assume it.
