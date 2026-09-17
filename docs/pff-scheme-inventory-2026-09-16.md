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
  Air Raid or a 3-4. Turning 21 rates into named schemes requires a clustering step —
  **since run, see the appended section below: it does not support a taxonomy on
  either side of the ball** — and the existing
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

---

# Do the rates cluster into "types"? — 2026-09-16

**Question.** The inventory above says a scheme taxonomy "has not been run." This runs
it: k-means on the 2025 rates, offense and defense clustered separately.

**Answer. The rates are stable team properties; the cluster boundaries are not.**
Between the first and second half of 2025, `def_dl_a_gap_share` correlates .918 with
itself and `off_gap_run_rate` .810 — these measure something real and persistent. But
labels fit independently on the two halves agree at ARI .243 (offense) and .441
(defense). Neither side supports a taxonomy. Use the continuous rates as features and
do not ship a cluster id.

```bash
export CFB_DATA_ROOT=C:/Users/mckel/dev/cfb/data
python scripts/pff_scheme_profile.py --season 2025 --week-min 0 --week-max 7 \
    --out data/processed/pff_scheme_profile_2025_h1.csv
python scripts/pff_scheme_profile.py --season 2025 --week-min 8 --week-max 99 \
    --out data/processed/pff_scheme_profile_2025_h2.csv
python scripts/pff_scheme_clusters.py --season 2025 --drop-quality --split-half
```

## Method

136 FBS teams, 2025. Features z-scored, k-means (`n_init=25`, `random_state=0`),
offense and defense fitted separately. The two `_faced` rates are excluded from both
sets — opponent behaviour, not the team's own type. `def_corner_snap_share` (sd .005)
and `def_slot_db_share` (sd .009) are excluded as near-constant across FBS. That
leaves 11 offensive and 6 defensive features.

Five diagnostics, because "k-means returned k clusters" is not evidence that k types
exist:

| Diagnostic | What it answers |
|---|---|
| \|r\| with SP+ overall, per feature | is this style, or team quality in costume? |
| silhouette, k = 2..8 | are the groups separated at all? |
| out-of-bag bootstrap ARI (100 resamples) | do the cut lines survive resampling the teams? |
| ARI vs a cut on the lead PC1 feature | did k-means find k types, or one axis? |
| split-half ARI (weeks 0–7 vs 8+) | does a label describe the team, or its sample? |

The bootstrap scores held-out teams only. Scoring the full sample compares
nearest-centroid assignments — centroid drift, not partition stability — and the
duplicate rows in a resample pull centroids toward dense regions, which inflates it.
The single-axis baseline reproduces k-means' own cluster sizes rather than equal
quantiles, so a 100/36 k-means split is not compared against a forced 68/68 cut.

## Quality contamination: offense clean, defense not

Offense has no feature above \|r\| = .25 with SP+ (max .226, `off_play_action_rate`),
so the residualization `coach_style_cluster` needed does not apply. Defense has two:
`def_box_snap_share` (r = .421) and `def_fs_snap_share` (r = .382). Dropping them
improves every defensive diagnostic, so the four-feature set is used throughout below.

## Result

| | offense (11 feats) | defense (4 feats, SP+-clean) |
|---|---:|---:|
| PC1 / PC2 | 30.7% / 20.9% | 41.7% / 24.8% |
| best silhouette | **0.180** at k=2 | **0.323** at k=2 |
| OOB bootstrap ARI at k=2 | **0.272** | **0.591** |
| ARI vs lead-feature cut | 0.252 (`off_pass_snap_rate`) | **0.561** (`def_dl_a_gap_share`) |
| split-half label ARI | **0.243** | **0.441** |
| face validity | passes | passes |

Every k from 3 to 8 is worse than k=2 on both sides (offense .129–.142, defense
.182–.257). There is no evidence for a five-type or four-type taxonomy at any k.

**Offense is a continuum.** Silhouette 0.18 is not separation, and OOB bootstrap ARI
0.272 means resampling the teams reshuffles most of the partition. The k=2 split it
produces is the ground/air axis — cluster 0 (n=39) is −0.80 z on pass rate, +0.78
gap-run, +0.65 designed-QB-run, +0.57 inline TE; cluster 1 (n=97) is the mirror. Face
validity passes (Army/Navy/Air Force all in 0; Hawaii/MTSU/FAU all in 1), but that
confirms the *axis* is measured correctly, not that there is a boundary on it. The
academies are the tail of a distribution, not a species.

**Defense is one axis, not a type.** Its diagnostics are better than offense's on
every line, and the 36-team minority cluster is a recognisable A-gap-anchored front:

| Feature | majority (n=100) | minority (n=36) |
|---|---:|---:|
| `def_dl_a_gap_share` | .072 | **.157** |
| `def_dl_outside_t_share` | .487 | .424 |
| `def_dl_snap_share` | .384 | .365 |
| `def_man_rate` | .307 | .257 |

Members include Iowa State, TCU, Cincinnati, Houston, West Virginia, Kentucky,
Illinois, Virginia Tech, Memphis, Tulane, App State, Coastal Carolina and Troy — a
list of long-running 3-down/odd-front programs.

But the partition agrees at ARI .561 with a simple cut on `def_dl_a_gap_share` alone,
so k-means did not find a multivariate type; it found a threshold on one rate. And
that rate correlates .918 with itself across halves of the season while the *labels*
only reach .441. The stable object is the number, not the group.

Offensive and defensive labels are near-independent: the minority defensive cluster is
26% of the pass-leaning offensive group and 26% of the ground-leaning one.

## What the four groups actually are

| | n | profile (raw means vs the other group) |
|---|---:|---|
| **Offense 0** — gap-run, play-action, heavier personnel | 39 | pass rate .474 vs .565, gap-run .571 vs .414, play-action .403 vs .291, inline TE .169 vs .129, designed QB run .241 vs .157, runs to the edge more (interior .415 vs .508) |
| **Offense 1** — spread, zone-run, quick game | 97 | the mirror; also more slot usage (.392 vs .357) |
| **Defense 0** — outside-technique front | 100 | A-gap share .072 vs .157, outside-T .487 vs .424, more DL snaps (.384 vs .365), more man (.307 vs .257) |
| **Defense 1** — A-gap-anchored front | 36 | the mirror; also more box defenders (.283 vs .258) |

Offense 0 is not the academies-and-nobody-else group it might sound like. It holds Ohio
State, Georgia, Texas, Penn State, Tennessee, Ole Miss, USC, Iowa, Kansas State, BYU and
Utah alongside Army, Navy and Air Force — the common thread is gap blocking plus
play-action out of heavier personnel, which in 2025 is as much a blue-blood profile as an
option one.

### The defensive split carries a level confound; the offensive one does not

| | P4 share | mean SP+ overall |
|---|---:|---:|
| Offense 0 / Offense 1 | .462 / .505 | +4.0 / −1.6 |
| Defense 0 / Defense 1 | **.570 / .278** | **+1.6 / −4.4** |

The offensive groups are balanced on conference level, so the +5.6 SP+ gap between them is
about those teams, not about who they play. The defensive groups are not: the
A-gap-anchored group is 72% Group of Five (App State, Coastal, Georgia State, Louisiana,
ULM, Marshall, Miami (OH), ODU, Rice, Sam Houston, San Jose State, South Alabama, Temple,
Troy, UTEP, UTSA, Utah State), against ten P4 members (Cincinnati, Houston, Illinois, Iowa
State, Kentucky, Miami (FL), Mississippi State, TCU, Virginia Tech, West Virginia).

That survives dropping the two SP+-loaded features, because it is not really a quality
effect — it is a roster-resource one. A program without two high-end edge defenders plays
a nose over the centre. So `def_dl_a_gap_share` is partly measuring recruiting, and any
model using it against a P4/G5 mixed slate should expect it to proxy for level.

## What this does not support

- **No taxonomy on either side, at any k.** If scheme is wanted as a feature, use the
  continuous rates — `def_dl_a_gap_share`, `off_pass_snap_rate`,
  `off_qb_designed_run_rate`, `off_gap_run_rate` — not a cluster id. The labels CSV is
  written for inspection, not for use as a feature.
- **Split-half is not season-over-season.** PFF's warehouse holds only 2025 and a
  partial 2026, so the test that killed `coach_style_cluster` — does a label survive
  into the next season, across coaching turnover — cannot be run at all here. The
  earlier draft of this doc suggested running `--season 2024`; that data does not
  exist. Split-half rules out one-sample artifacts and nothing more.
- **Halves are not independent in the way a season boundary is.** Same coach, same
  roster, same scheme install, so this test isolates sample noise from real change and
  nothing else. A season boundary adds coaching and roster turnover, which this cannot
  see. Which of the two numbers is larger is not something these data settle — in-season
  drift from injuries, coordinator adjustments and opponent adaptation cuts the other way.
- **`off_deep_attempt_rate` barely persists** (split-half r = .256) and
  `off_quick_game_rate` (.575) and `off_behind_los_rate` (.581) are middling. Those
  three are weaker team properties than the rest and should carry less weight.
- **Feature selection touched SP+.** The two dropped defensive features were chosen by
  correlation with a full-season outcome measure, in-sample on 2025. The labels
  themselves use only pre-game-observable play-calling rates, but a shipped version
  must fix the feature set on prior seasons or inherit `result_lookahead`.
- **No outcome test of any kind.** Nothing was run against margin, total, or the line.
  No edge is claimed or implied.
- **k-means only.** No GMM, HDBSCAN or hierarchical alternative was tried. The low
  silhouettes are unlikely to be an artifact of that choice, but it is untested.

## Files

| Path | What |
|---|---|
| `scripts/pff_scheme_clusters.py` | the clustering run and its five diagnostics |
| `scripts/pff_scheme_profile.py` | `--week-min/--week-max` build the split-half inputs |
| `scripts/pff_scheme_team_tables.py` | the two per-side team tables below |
| `data/processed/pff_scheme_clusters_2025.csv` | 136 teams, `offense_cluster` + `defense_cluster` (not committed, inspection only) |

## Per-side team tables

`scripts/pff_scheme_team_tables.py` writes one file per side of the ball, each one
row per FBS team, carrying every rate that went into the analysis plus the
team-season context the warehouse already holds:

```bash
python scripts/pff_scheme_team_tables.py --season 2025
```

| File | Shape | Contents |
|---|---|---|
| `data/processed/pff_scheme_offense_2025.csv` | 136 × 51 | 11 scheme rates, 2 faced rates, `offense_cluster`, dropbacks, then tempo (`off_plays_per_game`, `off_drives_per_game`), PPA, success rate, explosiveness, points per opportunity, line/second-level/open-field yards, power success, stuff rate allowed, havoc allowed, standard/passing-downs splits, opponent-adjusted EPA and success rate, SP+ offense, FPI offense |
| `data/processed/pff_scheme_defense_2025.csv` | 136 × 49 | 6 scheme rates plus the 2 near-constant ones, `defense_cluster`, snap volumes, then tempo faced, PPA allowed, success/explosiveness allowed, havoc (total, front-seven, DB), stuff rate, line yards allowed, opponent-adjusted EPA allowed, SP+ defense, FPI defense |

Both carry `conference`, `games`, `wins`, `sp_overall`, `fpi` and `elo` so either
stands alone. The team key is `stg.pff_franchise.cfbd_team_id` → `core.dim_team` →
the CFBD feeds; all 136 teams join with no nulls in any column.

Tempo is plays per game and drives per game — CFBD carries no seconds-per-play, so
that is the closest available measure.

**The `*_cluster` columns are for inspection only.** Per the diagnostics above the
labels do not persist (split-half ARI .243 / .441); model on the continuous rates.
