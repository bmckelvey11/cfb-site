# Drive-level dispersion features and a volatility axis

Date: 2026-08-28
Status: design approved, not implemented

## Goal

Extend the coach/team profiling work beyond season-mean advanced stats into
**distributional** statistics — standard deviation, median, IQR, skew, tail
percentiles — computed from drive-level data, and determine whether team
*volatility* is a real, separable, persistent construct.

Two products come out of one pipeline:

1. **Career volatility grouping** — a categorical coach label, sibling to the
   existing `coach_style_cluster`. Descriptive; `result_lookahead` like its sibling.
2. **Entering-game volatility numerics** — per team-game dispersion over that
   team's strictly-prior drives this season. Follows the `computed_running`
   contract, so it is a legitimate pregame input, not quarantined.

Both are **conditional on phase D passing its gates** (below). Shipping nothing
is an expected and acceptable outcome.

## Motivation

`docs/coach-playstyle-analysis.md` established that the existing level-based
taxonomy is real but soft: silhouette 0.13 at k=5, season-to-career stability
45.6% against a 22.5% chance baseline, and no market edge (0 of 10 tests survive
Holm). It also listed two limitations this design directly addresses:

- **Tempo is plays-per-game**, contaminated by possession count. Drive `elapsed`
  gives clean seconds-per-play.
- **2016 is a hard floor**, imposed by broken havoc splits. A drive-based feature
  set needs no havoc, so the window extends to **2013** — the betting-line floor —
  adding three seasons and about a third more data.

A dispersion measure is a different *construct* from a mean, not merely more
features. A boom-bust offense and a metronome can share identical means. Variance
drives cover distributions, so if volatility is persistent it is more
betting-relevant than level.

## Data

Verified present and complete for 2013–2024:

| Source | Shape | Used for |
|---|---|---|
| `data/raw/drives_{season}.json` | ~34k drives/season, ~17–29 MB | primary dispersion source |
| `data/raw/advanced_game_stats_{season}.json` | ~2,850 team-games/season | secondary, down-and-distance constructs |

Per team-season: **median 133 offensive drives** (min 11, max 174). `elapsed` is
`{minutes, seconds}`. `driveResult` is one of PUNT, TD, FG, DOWNS, INT, FUMBLE,
MISSED FG, END OF HALF, and similar.

## Architecture

Career and entering-game volatility are the same computation over different
windows. Per-drive residuals are computed once and aggregated twice.

```
drives_{2013..2024}.json  (~250 MB)
        |
        v
  drive_stats.py  -> per-drive records
        |            (team, game_id, season, week, plays, yards,
        |             seconds, start_yards_to_goal, result)
        v
  opponent residualization
        |   drive value minus opponent's season mean allowed;
        |   raw and residual BOTH retained so phase D can report
        |   how much the adjustment actually moves rankings
        v
        +---------------------+----------------------+
        v                     v                      v
  career window        season-to-date window     exploratory
  (coach, all seasons) (strictly prior games)    (phase D only)
        |                     |                      |
        v                     v                      v
  volatility           computed_drive_var        factor analysis
  clustering           entering-game numerics    dimensionality +
  -> categorical       -> legitimate pregame     independence tests
  -> result_lookahead
```

### Components

| Component | Responsibility |
|---|---|
| `cfb_system_maker/drive_stats.py` | Parse drives into per-drive records; compute dispersion over a supplied window. Pure functions; path in, data out. |
| `scripts/build_drive_aggregates.py` | Run the parse once; write `data/processed/drive_stats.json`. |
| `scripts/explore_drive_dispersion.py` | Phase D only. Factor analysis, stability, split-half reliability, residualization impact. |
| `cfb_system_maker/enrich.py` (edit) | New source kind `computed_drive_var`; loads the cache. |
| `cfb_system_maker/features.py` (edit) | Register surviving features. |

### Why a precompute cache

Parsing ~250 MB of drives JSON on every `enrich` run is unacceptable — `enrich`
already walks a dozen endpoint families per season. This follows the existing
`computed_v1` pattern: `scripts/build_drive_aggregates.py` writes
`data/processed/drive_stats.json`; `enrich` loads it. Cache missing means
features read `None` and fail closed, identical to `v1_over_prob` before
`refit-v1` has run.

### Why `drive_stats.py` is separate from `running_stats.py`

`running_stats.py` is 4.7 KB doing one thing: season-to-date team aggregates from
game-level inputs. Drive parsing plus dispersion math would roughly double it and
mix two input granularities in one file. Separate module, same `computed_*`
convention.

## Features

### Per-drive base metrics

Computed separately for a team's offense and its defense.

| Metric | Type | Captures |
|---|---|---|
| `plays` | continuous | drive length |
| `yards` | continuous | drive productivity |
| `seconds` | continuous | drive duration (from `elapsed`) |
| `sec_per_play` | continuous | clean tempo |
| `yards_per_play` | continuous | efficiency |
| `start_yards_to_goal` | continuous | field position |
| `scored` (TD or FG) | binary | drive conversion |
| `td` | binary | finishing vs settling for three |
| `turnover` (INT or FUMBLE) | binary | disaster rate |
| `three_and_out` (3 or fewer plays then PUNT) | binary | stall rate |

### Statistics

Continuous metrics: mean, median, std, IQR (p75 minus p25), skew, p10, p90.

Binary metrics: **rate only.** For a Bernoulli variable std equals
sqrt(p(1-p)), a deterministic function of the mean; including both injects
perfectly redundant columns and distorts any distance metric.

Drive-derived total: 6 continuous x 7 statistics x 2 sides = 84, plus
4 binary rates x 2 sides = 8, giving **92 features.**

### Second block: game-level

From `advanced_game_stats`, for constructs drives cannot express (down-and-distance
based): offensive and defensive success rate, explosiveness, PPA, line yards.
8 metrics x 5 statistics (mean, median, std, IQR, skew — p10/p90 dropped as
meaningless at n of about 12 games) = **40 features.**

**Wide exploratory matrix: about 132 features.**

### Unit of analysis

Factor analysis on 132 features requires n much greater than p. At coach level
the correlation matrix is near-singular and factors are unstable — the 2013–2024
window yields 230 coaches with three or more seasons, against 132 columns. At
**team-season** level the same window gives about 1,500 rows (1,539 coach-seasons
of six or more games), comfortably above 132.

Therefore **phase D runs at team-season level.** Only the roughly 12 features it
selects are carried up to coach-level volatility clustering (230 coaches). The factor structure
is estimated on the larger sample and merely applied at coach level.

### Entering-game emission thresholds

Skew and tail percentiles need far more sample than a mean or median — a p90 over
26 drives is essentially the third-largest value. Starting proposal, to be
**replaced by phase D's split-half reliability measurements**:

| Prior drives | Emits |
|---|---|
| under 20 | `None` (fail closed) |
| 20–59 | mean, median, rates |
| 60 or more | adds std, IQR |
| 100 or more | adds skew, p10, p90 |

## Phase D: gates

Each decision rule is fixed **before** any output is seen. Otherwise phase D
becomes a search for a reason to build phase B.

### Gate 1 — Is dispersion separable from level?

Factor-analyze the 132-feature team-season matrix. For each dispersion feature,
compare its maximum loading on dispersion-dominant factors against its maximum
loading on level-dominant factors.

- **Pass:** dispersion loads primarily onto its own factors. Proceed.
- **Fail:** dispersion loads mainly onto level factors — "volatile" restates
  "bad." **Ship nothing; write the negative result.**

### Gate 2 — Is volatility persistent for a coach?

Assign each coach-season to its nearest career volatility centroid; measure how
often a coach's seasons land in their own cluster against the chance baseline.
Method identical to `docs/coach-playstyle-analysis.md`.

Recorded prior: dispersion measures are consistently far less repeatable than
level measures across sports analytics — team variance is mostly schedule, injury
timing, and luck. The level label managed 45.6% against 22.5%. **Expectation is
that volatility stability lands materially lower, plausibly near chance.**

- **Pass:** stability meaningfully above chance.
- **Fail:** at or near chance means no coach-level volatility construct. **Drop
  the categorical label.** Entering-game numerics may still survive Gate 3, since
  they describe a team-season rather than a coach.

### Gate 3 — Does entering-game volatility carry within-season signal?

Split-half reliability: correlate a team's volatility over odd-numbered games
against even-numbered games within the same season, isolating repeatability from
schedule drift. Run at each candidate sample threshold to set the fail-closed
floors from evidence.

- **Pass:** split-half correlation clears about 0.3 at some achievable drive
  count. Ship the numerics at that floor.
- **Fail:** near zero at every threshold. **Ship nothing.**

### Measured but not gated

Spearman correlation between raw and opponent-residualized orderings. If the
adjustment barely moves rankings it is documented as unnecessary rather than
silently retained.

### No betting test in phase D

If numerics survive Gate 3, the market test is separate work with its own
walk-forward setup and multiplicity budget. Bolting it on here would invite
exactly the "one of these is p under 0.05" reading that
`docs/coach-playstyle-analysis.md` correctly refused.

## Error handling

- **Missing season file** — skipped, not an error. Matches `scrapers.py` and
  `enrich.py` convention.
- **Missing cache** (`drive_stats.json`) — features read `None`, fail closed.
- **Drive with zero plays** — `sec_per_play` and `yards_per_play` undefined; the
  drive is excluded from those metrics only and retained for the others.
- **Team below drive threshold** — emits `None` per the threshold table. A season
  opener always emits `None`, matching `running_stats`.
- **Unknown `driveResult`** — counted in the denominator, contributes to no binary
  rate. New CFBD result strings must not silently inflate a rate.

## Testing

Following `tests/test_running_stats.py`, the closest analog.

- **Parse** — a hand-built drives fixture produces expected per-drive records;
  `{minutes, seconds}` converts correctly.
- **No lookahead** — the central test. A team-game's entering-game value is
  computed from strictly-prior games only; a fixture where the current game would
  visibly change the value must not change it.
- **Thresholds** — below floor emits `None`; each tier emits exactly its statistic
  set.
- **Binary rate correctness** — rates match hand-computed values; no std emitted
  for binary metrics.
- **Zero-play drives** — excluded from ratio metrics, retained elsewhere.
- **Residualization** — a synthetic opponent effect is removed by the residual step.
- **Registry** — `test_features.py` uniqueness holds; `enrich` emits the new keys.

## Out of scope

- Play-level data (`plays_*.json`). Scraped only for selected weeks, not a
  complete panel.
- Any change to the existing `coach_style_cluster` feature or its labels.
- The market test for surviving numerics (separate work).
- Backfilling drives before 2013 — below the betting-line floor established by
  DATA-01, so games there cannot be graded anyway.

## Success criteria

1. `python scripts/build_drive_aggregates.py` writes the cache for 2013–2024.
2. `python scripts/explore_drive_dispersion.py` reports all three gates with an
   explicit pass/fail against the rules above.
3. Whatever the gates say is honored — including shipping no feature at all.
4. A docs note records the outcome either way, in the pattern of
   `docs/coach-playstyle-analysis.md`.
5. Full suite green.
