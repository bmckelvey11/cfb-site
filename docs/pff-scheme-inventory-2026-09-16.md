# What PFF knows about team scheme — 2025 inventory

**Question.** Are team offensive and defensive schemes in the PFF data we hold?

**Answer.** Not as labels. There is no scheme *name* anywhere in the 21 `stg.pff_*`
tables — no "Air Raid", no "3-4", no "Tampa 2", no text column of any kind. What PFF
carries is a `split` dimension on six tables plus alignment snap counts on two more,
and from those, **21 team-level scheme rates are computable for all 136 FBS teams in
2025**. Scheme is measurable here; it is not labelled here.

Reproduce:

```bash
export CFB_DATA_ROOT=C:/Users/mckel/dev/cfb/data   # cfb_paths raises on import without it
python scripts/pff_scheme_profile.py --season 2025
python scripts/pff_scheme_profile.py --season 2025 --inventory   # split inventory
python scripts/pff_scheme_profile.py --selftest
```

Output: `$CFB_DATA_ROOT/processed/pff_scheme_profile_2025.csv`, 136 rows × 26 columns.

## Data and range

| | |
|---|---|
| Source | `data/raw/pff/facet_*_ncaa_2025_fbs*.csv` → `stg.pff_*` (753 raw files) |
| Season | 2025, weeks 0–21 (week 18 = bowls, 80 franchises; 19–21 = CFP) |
| Grain | player × week × split, **per-week not cumulative** (verified on a single player across weeks) |
| Teams | 136 FBS franchises with man/zone coverage snaps; all 136 carry a `cfbd_team_id` |
| Volume | 1,684–3,987 coverage snaps and 171–626 dropbacks per team |
| Pulled | `pulled_at = 2026-09-08` |

The scheme facets are already loaded. `facet_defense_coverage_scheme`,
`facet_receiving_scheme`, and `facet_offense_run_blocking` are on disk *and* flattened
— `pff_flatten.py` explodes their `man_*` / `zone_*` / `gap_*` column prefixes into
`split` rows. There is no unpulled or unloaded scheme endpoint.

## Where scheme lives

### Split dimension (six tables)

| Table | Splits carrying scheme signal |
|---|---|
| `pff_defense_coverage` | `man`, `zone`, `slot` (+ `all`) |
| `pff_run_blocking` | `gap`, `zone` (+ `all`) |
| `pff_passing` | `pa`/`npa`, `screen`/`no_screen`, `blitz`/`no_blitz`, `pressure`/`no_pressure`, `ttt_under_2_5`/`ttt_over_2_5`, depth (`behind_los`/`short`/`medium`/`deep`) × field third, `concept` |
| `pff_receiving` | `man`, `zone`, `slot`, `screen`, depth × field third |
| `pff_defense_pass_rush` | `lhs`, `rhs`, `outside`, `true_pass_set` |
| `pff_pass_blocking` | `true_pass_set` |

### Alignment snap counts (no split needed)

- `pff_defense_summary` — `snap_counts_dl`, `_box`, `_offball`, `_corner`, `_fs`, `_slot`, and DL technique (`_dl_a_gap`, `_dl_b_gap`, `_dl_over_t`, `_dl_outside_t`)
- `pff_receiving` — `slot_snaps` / `wide_snaps` / `inline_snaps` (and the matching `_rate` fields)
- `pff_blocking_alignment` — OL snaps by position (`lt`/`lg`/`ce`/`rg`/`rt`/`te`)
- `pff_rushing_direction` — attempts by gap (`LE`…`RE`)
- `pff_rushing` — `gap_attempts` / `zone_attempts` per ball-carrier

## The 21 rates, 2025

Defense (coverage shell and front):

| Column | mean | sd | min | max |
|---|---:|---:|---:|---:|
| `def_man_rate` | .294 | .113 | .073 | .670 |
| `def_dl_snap_share` | .379 | .017 | .311 | .421 |
| `def_box_snap_share` | .265 | .028 | .203 | .353 |
| `def_corner_snap_share` | .162 | .005 | .150 | .171 |
| `def_slot_db_share` | .106 | .009 | .075 | .125 |
| `def_fs_snap_share` | .086 | .018 | .045 | .127 |
| `def_dl_a_gap_share` | .094 | .055 | .002 | .268 |
| `def_dl_outside_t_share` | .470 | .049 | .184 | .603 |

Offense (own play-calling):

| Column | mean | sd | min | max |
|---|---:|---:|---:|---:|
| `off_pass_snap_rate` | .539 | .081 | .206 | .710 |
| `off_gap_run_rate` | .459 | .145 | .140 | .781 |
| `off_play_action_rate` | .323 | .090 | .127 | .606 |
| `off_screen_rate` | .142 | .050 | .015 | .299 |
| `off_quick_game_rate` | .474 | .067 | .271 | .631 |
| `off_deep_attempt_rate` | .157 | .037 | .088 | .289 |
| `off_behind_los_rate` | .195 | .058 | .066 | .427 |
| `off_wr_slot_rate` | .382 | .043 | .174 | .493 |
| `off_te_inline_rate` | .140 | .050 | .017 | .363 |
| `off_qb_designed_run_rate` | .181 | .093 | .023 | .537 |
| `off_run_interior_rate` | .482 | .072 | .302 | .625 |

`off_run_interior_rate` is *all* carries by gap, QB keeps included — a designed keep
is coded to the gap it hits, so it is not separable from an RB carry here. For an
option team roughly half that rate is the quarterback.

Opponent behaviour against the offense (**not** this team's own call):
`off_blitz_faced_rate` (.372 ± .052), `off_pressure_faced_rate` (.320 ± .052).

`def_corner_snap_share` (sd .005) and `def_slot_db_share` (sd .009) are near-constant
across FBS — they carry almost no discriminating signal and are kept only as
denominators/context.

### Face validity

The extremes land where football says they should, which is the only external check
available without a ground-truth scheme label:

| Rate | Highest | Lowest |
|---|---|---|
| `off_qb_designed_run_rate` | Army .537, Navy .417, Air Force .404 | Stanford .023, Minnesota .037 |
| `off_pass_snap_rate` | Middle Tennessee .710, Hawaii .685, FAU .678 | Army .206, Air Force .242, Navy .270 |
| `off_te_inline_rate` | Army .363, Air Force .307, Iowa State .233 | Hawaii .017, San Jose State .028 |
| `def_man_rate` | Colorado State .670, Utah .589, Eastern Michigan .569 | Pittsburgh .073, East Carolina .076, Indiana .087 |
| `off_gap_run_rate` | Navy .781, Vanderbilt .778, Utah .749 | Akron .140, Miami (OH) .143 |
| `off_play_action_rate` | Old Dominion .606, Ole Miss .520 | Buffalo .127, Hawaii .134 |

The three service academies separating on QB-run, pass rate and inline TE
simultaneously, and Hawaii anchoring the opposite end of two of the three, is the
signature of a working measurement rather than a noisy one.

## Two metrics that look right and are wrong

Both were in the first pass; both are now removed or replaced. Recording them because
each is a trap anyone re-deriving this will hit.

1. **`pff_rushing_direction` QB codes are not designed QB runs.** `QBK`, `QBSn`,
   `QBSc`, `QBF`, `QBT` are kneels, sneaks, scrambles and fumbles — 810 `QBK`
   attempts league-wide across 2025 is a kneel count, not an offense. A designed QB
   keep is coded to the gap it hits (`LE`, `MR`, …), so it is indistinguishable from
   an RB carry in that table. Using the `QB%` codes put Army at .064 and Louisville
   first. The working version joins `pff_player_season.position = 'QB'` against
   `pff_rushing` and subtracts `scrambles`, which puts Army at .537.
2. **Gap-run rate from `pff_run_blocking` and from `pff_rushing` are the same
   number.** r = 0.9997 across the 136 teams. Only the blocking-snap version is
   carried.

Two further traps, avoided in the script and worth naming:

- **`split = 'all'` overlaps the partitioning splits and has a different row
  population** (28,080 vs 27,440 on coverage). It is excluded from every sum.
- **Absent numerics are NaN, not NULL** (same failure mode as
  `gql-numerics-are-nan-not-null`). Every rate gates on `denominator > 0`, never on
  `IS NOT NULL`. The flattener also emits a row per split whether or not the player
  had a snap there — `pff_receiving` has exactly 14,934 rows for all 21 splits.

## What this does not support

- **No scheme taxonomy.** These are continuous rates. Nothing here says a team runs
  Air Raid or a 3-4. Turning 21 rates into named schemes requires a clustering step
  that has not been run and would need its own validation — and the existing
  precedent is discouraging: `coach_style_cluster`
  (`docs/coach-playstyle-analysis.md`) found exactly one discrete style out of five,
  labels that hold for under half a coach's own seasons, and no edge surviving
  multiplicity correction.
- **No defensive blitz or pressure *sent* rate.** The `blitz`/`no_blitz` and
  `pressure`/`no_pressure` splits live on `pff_passing` — the QB's view, i.e. what
  an offense *faced*. These tables carry no `opponent_id`, so the rate cannot be
  re-attributed to the defense that sent it. Defensive blitz rate is not derivable
  from this data as loaded.
- **`def_man_rate` is a coverage-defender snap share, not a play share.** Five to
  seven defenders cover per dropback, and a single play can mix man and zone
  assignments. It ranks teams on man usage; it does not state the fraction of
  snaps that were man coverage.
- **No formation or personnel grouping.** No 11/12/21 personnel, no shotgun vs
  under-center, no tempo/seconds-per-play, no field-position or down-and-distance
  conditioning. Alignment snap counts are the closest proxy and they are
  position-based, not formation-based.
- **No predictive claim whatsoever.** Nothing here was tested against any outcome —
  not margin, not total, not the line. This is an inventory of what is measurable.
  Unlike `coach_style_cluster`, these rates are built only from pre-game-observable
  play-calling counts, so a trailing-window version would not be
  `result_lookahead` — but that version has not been built and no edge is claimed.
- **FBS 2025 only.** Other seasons are present in the same tables and the script
  takes `--season`, but nothing outside 2025 was checked here.

## Files

| Path | What |
|---|---|
| `scripts/pff_scheme_profile.py` | generator + `--inventory` + `--selftest` |
| `data/processed/pff_scheme_profile_2025.csv` | 136 teams × 26 columns (not committed) |
| `docs/pff-endpoint-reference.md` | the PFF endpoints, incl. `coverage_scheme` / `receiving/scheme` |
| `docs/coach-playstyle-analysis.md` | prior art: CFBD-based coach style clusters, and why they are quarantined |
