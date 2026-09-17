# Which PFF and CFBD stats can be pre-game features

**Question.** List the PFF and CFBD stats that are not forward-looking — the ones
usable as features before kickoff.

**Answer.** Almost no stat is forward-looking by itself; the *aggregation* is. Of
1,043 columns across 42 tables, 565 are usable pre-game and 129 are not usable at
all — and the dividing line is mostly the table's grain, not what the number
measures.

| Verdict | PFF | CFBD | Meaning |
|---|---:|---:|---|
| `pregame_windowed` | **476** | **74** | usable as a trailing sum/mean over prior weeks; the season total is lookahead |
| `pregame_direct` | 0 | **15** | fixed before the season starts; use as-is |
| `needs_rekey` | 0 | 55 | per-game rows carrying no game key; rekey before use |
| `lookahead_only` | **0** | **129** | season-final snapshot with no as-of date; unusable for in-season games |
| `postgame` | 0 | 55 | encodes this game's result |
| `metadata` | 121 | 118 | keys and labels |

**Every PFF stat column is usable**, because all 21 PFF tables are week-grain.
**No CFBD rating is**, because we hold only season-final snapshots of them.

Reproduce:

```bash
export CFB_DATA_ROOT=C:/Users/mckel/dev/cfb/data
python scripts/audit_pregame_eligibility.py --csv
python scripts/audit_pregame_eligibility.py --source pff
```

Per-column output: `data/processed/pregame_feature_eligibility.csv` (1,043 rows).

## The two tests

A column has to pass both.

**1. Construction — does the number encode the result of a game?** Points, wins,
margin, EPA/PPA, success rate, explosiveness, win probability and the ratings built
from them do. Snap counts, alignment, personnel, play-calling rates, attempts by
direction, target depth and time-to-throw do not.

**2. Grain — can it be recomputed as of a cutoff?** A week- or game-grain table can
be summed over weeks 1..n−1, so *even a result-informed column becomes a legitimate
pre-game feature*. A season-final snapshot cannot: one row per team-season, no as-of
date, so it is lookahead for every game inside that season regardless of what it
measures.

Test 2 is the one that actually decides most cases, and it cuts the opposite way from
intuition twice:

- **Result-informed but fine.** Trailing EPA, trailing success rate, trailing points
  per game are all legitimate pre-game features. Being about outcomes is not
  disqualifying; being about *this* outcome is.
- **Result-free and still unusable.** `stg.advanced_season_stats` holds
  `offense_passingPlays_rate`, `offense_rushingPlays_rate` and
  `offense_standardDowns_rate` — pure play-calling, nothing to do with results — and
  all 75 of its stat columns are unusable, because the table is a season total with
  no week column. **Use `stg.advanced_game_stats` instead**: same metric family, 56
  columns, week grain, windowable.

This matches how the app's `FEATURE_REGISTRY` already works — its 19 `season_to_date`
features are trailing computations, and its `result_lookahead` group currently has
zero members precisely because the trailing versions are what got built.

## PFF: all 21 tables, all windowable

Every PFF staging table carries `season` + `week` and is per-week, not cumulative, so
a trailing window over weeks 1..n−1 is always available. 476 stat columns:

| Family | Cols | Result-informed | Examples |
|---|---:|:---:|---|
| `play_outcome` | 267 | yes | receptions, sacks, stops, interceptions, pressures, missed tackles |
| `grades_*` | 51 | yes | `grades_coverage_defense`, `grades_pass_block`, `grades_run` |
| `snap_count` | 52 | **no** | `snap_counts_dl`, `snap_counts_box`, `coverage_snaps`, `snap_counts_slot` |
| `volume` | 34 | **no** | `attempts`, `dropbacks`, `routes`, `run_plays`, `pass_rush_opp` |
| `usage_rate` | 32 | **no** | `slot_rate`, `pass_block_percent`, `coverage_percent`, `route_rate` |
| `yardage` | 31 | yes | yards, yards after catch, yards after contact |
| `epa_ppa` / `explosiveness` / `efficiency` / `rating` | 8 | yes | `epa`, `positive_epa_percent`, `elusive_rating`, `qb_rating` |
| `deployment` | 1 | **no** | `avg_time_to_throw` |

The 119 result-free columns (snap counts, volume, usage rates, deployment) are the
cleanest material in the warehouse: they pass both tests, and they are what the
scheme work in `pff-scheme-inventory-2026-09-16.md` is built from.

**PFF grades are a judgment call, resolved in favour of usable.** A grade is assigned
by a charter who watched the play, so it is result-informed in the strict sense. But
the grade for weeks 1–5 exists before week 6 kicks off, which is the only thing
pre-game eligibility asks. Windowed, they are fine; the season grade is not.

## CFBD: it depends entirely on the table

| Table | Grain | Verdict | Stat cols |
|---|---|---|---:|
| `advanced_game_stats` | week | `pregame_windowed` | 56 |
| `drives` | drive, keyed to `gameId` | `pregame_windowed` (18) + `postgame` (4) | 22 |
| `returning_production` | preseason | `pregame_direct` | 12 |
| `recruiting_teams` | preseason | `pregame_direct` | 2 |
| `talent` | preseason | `pregame_direct` | 1 |
| `advanced_box_score__teams_*` (7 tables) | game, **unkeyed** | `needs_rekey` (55) + `postgame` (45) | 100 |
| `advanced_season_stats` | season-final | `lookahead_only` | 75 |
| `adjusted_team_season` | season-final | `lookahead_only` | 22 |
| `ratings` | season-final | `lookahead_only` | 16 |
| `fpi` | season-final | `lookahead_only` | 10 |
| `core_ratings` | season-final | `lookahead_only` | 5 |
| `elo` | season-final | `lookahead_only` | 1 |

### No rating is usable in-season, and only Elo can be fixed

`core_ratings` for 2025 has exactly one row per team with
`throughWeek = 1, throughSeasonType = 'postseason'` — a single season-final snapshot.
`ratings`, `fpi`, `elo` and `adjusted_team_season` are likewise one row per
team-season. So SP+, FPI, Elo, SRS and opponent-adjusted EPA **cannot be used for any
game inside the season they describe.**

Whether that is fixable depends on the endpoint, and mostly it is not. From the
vendored client (`cfbd-python/cfbd/api/ratings_api.py`):

| Method | Week parameter? |
|---|---|
| `RatingsApi.get_elo` | **yes** — `week`, documented as defaulting to the latest available week |
| `RatingsApi.get_core` | no — `year`, `team`, `conference` only |
| `RatingsApi.get_sp` | no |
| `RatingsApi.get_fpi` | no |
| `RatingsApi.get_srs` | no |

So **Elo is a pull problem** — one column, worth fixing, since we take the default and
get the season-final value. SP+, FPI, SRS and core ratings are season-final *at the
API*, and no ingest change recovers them. `throughWeek` on `core_ratings` is a
passthrough field describing the snapshot served, not a knob we can turn.

The practical consequence: for in-season games the only team-strength measure that can
be made pre-game is a trailing window over `advanced_game_stats`, unadjusted for
opponent. Prior-season ratings stay usable, and the app registry already does exactly
that — `core_ratings` appears there via `raw_prior_team_season`.

### The box score tables need rekeying first

`advanced_box_score` and its seven exploded children hold one row per game but carry
no `gameId` and no `week` — only `season` plus the two team names and the final score.
The rows cannot be ordered in time as stored.

The rekey works. Joining `(season, gameInfo_homeTeam, gameInfo_awayTeam)` to
`core.fact_game` resolves 11,484 box-score rows to 11,556 game rows — every row
matches, and **37 keys (0.3%) are ambiguous** because the same pairing occurs twice in
a season (a conference-championship rematch). Those 37 need a tiebreak or dropping.
Until that lands, the 55 non-outcome columns are unusable.

## A third axis: scheme identity vs performance

Lookahead is not the only filter. For classifying *what* an offense or defense does —
as opposed to how well it does it — there is a separate question: does the column
describe a choice, or a result of that choice?

**Success rate, EPA/PPA, explosiveness and yardage should not be in a scheme feature
set.** They measure quality, and clustering on quality rediscovers team strength
rather than style. `docs/coach-playstyle-analysis.md` is the worked example: raw
advanced stats produced a PC1 holding 42% of variance that was simply team quality,
with Saban and Smart grouped together because they win, not because they coach alike.
The same trap reappeared in the scheme work — `def_box_snap_share` correlates .421
with SP+.

The scheme-identity columns are the result-free ones: snap counts, alignment, usage
rates, volume and deployment. 119 PFF columns qualify by the `result_informed` flag,
but that flag answers the lookahead question, not this one, and it lets about a dozen
performance measures through. These are result-free enough to window but are *not*
scheme:

`pass_rush_win_rate`, `pass_rush_wins` (`pff_defense_pass_rush`); `accuracy_percent`,
`btt_rate`, `twp_rate`, `comp_pct_diff` (`pff_passing`); `caught_percent`
(`pff_receiving`); `breakaway_percent` (`pff_rushing`); the `*_percent` make rates in
`pff_field_goal`; `percent_returned` (`pff_kickoff`, `pff_punting`).

Excluding those leaves roughly 105 genuine scheme columns, concentrated in eight
tables: `pff_defense_summary` (14 alignment snap counts), `pff_blocking_alignment`
(11), `pff_receiving` (11 slot/wide/inline deployment), `pff_passing_allowed_pressure`
(9 pressure-location shares), `pff_defense_pass_rush` (6 usage), `pff_offense_summary`
(6 pass/run snap splits), `pff_rushing` (gap/zone attempts), `pff_run_blocking` (3)
and `pff_defense_coverage` (5, which the `split` dimension turns into man/zone).

**CFBD contributes essentially nothing here.** Its play-calling rates —
`offense_passingPlays_rate`, `rushingPlays_rate`, `standardDowns_rate`,
`passingDowns_rate` — exist *only* in `advanced_season_stats`, which is season-final.
`advanced_game_stats` carries no `*_rate` columns except `stuffRate`, and no pass/run
play split, so the rates cannot be rebuilt at week grain. For pre-game scheme
identity, PFF is the entire supply.

## What this does not support

- **Passing both tests does not make a feature clean.** `def_dl_a_gap_share` passes
  both and still proxies for Power Four / Group of Five level — the A-gap-anchored
  defensive group is 72% G5 (see `pff-scheme-inventory-2026-09-16.md`). Lookahead is
  one failure mode among several; confounding is a separate check.
- **The classification is pattern-based, not semantic.** Columns are matched to
  families by regex over their names. Every column matched a family on this run (zero
  unclassified) and the selftest pins the judgment calls, but a renamed or newly
  ingested column could land in the wrong family silently. Re-run the script after any
  schema change and read the family counts.
- **`drives` is drive-grain, and "windowed" means prior *games*.** `driveResult`,
  `startYardline` and `endPeriod` describe plays inside a game. They are windowable
  only because `drives` carries `gameId`, so drives from prior games can be
  aggregated — aggregating drives from the target game is lookahead of the most direct
  kind. The four `*OffenseScore`/`*DefenseScore` columns are tagged `postgame` outright.
- **`pregame_windowed` is a permission, not an implementation.** Nothing here windows
  anything. A column tagged `pregame_windowed` and then used as a season total is
  exactly as contaminated as a `lookahead_only` one. The verdict says a safe version
  is *constructible*.
- **Window length and staleness are not addressed.** Whether a feature should use
  three weeks or the whole prior season, and how to handle week 1 with no prior games,
  are modelling decisions this audit does not touch.
- **Betting lines, weather and schedule are out of scope.** They live in other tables
  and the app registry already classifies them (`betting_lines`, `weather`,
  `matchup`, `metadata` groups). This audit covers PFF and CFBD stat tables only.
- **Opponent adjustment is lost.** The only opponent-adjusted measures we hold
  (`adjusted_team_season`) are season-final. A trailing window of raw
  `advanced_game_stats` is unadjusted, so early-season values reflect schedule
  strength as much as team strength.

## Files

| Path | What |
|---|---|
| `scripts/audit_pregame_eligibility.py` | the classifier, with `--selftest` pinning the judgment calls |
| `data/processed/pregame_feature_eligibility.csv` | 1,043 rows: table, column, grain, family, result_informed, verdict (not committed) |
| `cfb_system_maker/features.py` | the app registry whose `season_to_date` group is the existing precedent |
| `docs/pff-scheme-inventory-2026-09-16.md` | the result-free PFF columns put to use |
