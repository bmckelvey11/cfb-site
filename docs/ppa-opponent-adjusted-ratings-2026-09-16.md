# Opponent-adjusted team PPA ratings (v1.0)

**Date:** 2026-09-16
**Script:** [`scripts/build_ppa_opponent_adjusted_ratings.py`](../scripts/build_ppa_opponent_adjusted_ratings.py) (`VERSION = "1.0"`)
**Test:** [`tests/test_ppa_opponent_adjusted_ratings.py`](../tests/test_ppa_opponent_adjusted_ratings.py)

## Question

How do we rate teams' offense and defense this early in the season, adjusted for
opponent strength, when most teams have only 1-3 games played?

## Method

Two-stage, mixed-effects opponent adjustment on `stg.ppa_games` (team-per-game
offense/defense PPA, joined to `stg.games` for home/away):

1. **Stage 1 — crossed random effects.** For a season's games, fit
   `statsmodels.MixedLM` with a home-field fixed effect and team + opponent as
   crossed random effects (via variance components, one shared group). This
   separates a team's own PPA from the strength of the opponents it played —
   the actual opponent adjustment. Run twice per season: once on
   `offense_overall`, once on `-defense_overall` (CFBD's raw sign has higher
   `defense_overall` = more PPA allowed = worse defense; negated so higher is
   always better for both `off_rating` and `def_rating`).
2. **Stage 2 — cross-season shrinkage.** Blend the current season's team
   estimate with a pooled prior-seasons estimate (`--prior-seasons`, default
   1), weighted by each estimate's own BLUP standard error
   (`precision = 1/se²`). Early in a season the current-season estimate has a
   wide SE (few games) and the blend leans on the prior; as games accumulate,
   the current season dominates. No date logic is hardcoded — rerun weekly
   against the latest warehouse snapshot.

## Data and date range

- `stg.ppa_games` × `stg.games`, `seasonType = 'regular'` only.
- Current season: 2026, through the snapshot pulled 2026-09-16 (up to week 3,
  138 FBS teams with 1-3 games played).
- Prior-seasons default: 2025 regular season (1,650 rows, 136 teams) as the
  shrinkage prior.

## Numbers

Top 10 by `overall_rating` (= `off_rating + def_rating`), 2026 through week ~3:

| team | games_played | off_rating | def_rating | overall_rating |
|---|---|---|---|---|
| Indiana | 2 | 0.150 | 0.080 | 0.229 |
| Ohio State | 2 | 0.117 | 0.104 | 0.221 |
| Oregon | 2 | 0.111 | 0.085 | 0.196 |
| Notre Dame | 2 | 0.110 | 0.086 | 0.196 |
| Texas Tech | 2 | 0.065 | 0.103 | 0.168 |
| Miami | 2 | 0.074 | 0.083 | 0.157 |
| Utah | 2 | 0.116 | 0.042 | 0.157 |
| Alabama | 2 | 0.073 | 0.073 | 0.146 |
| Georgia | 2 | 0.082 | 0.057 | 0.139 |
| Vanderbilt | 2 | 0.151 | -0.015 | 0.136 |

Full 138-team output: `data/exports/ppa_ratings_v1.0_2026.csv` (not committed —
data stays out of git per repo rules; rerun the script to reproduce).

136 of 138 teams are `blended` (both current and prior-season estimates
available); 2 are `current_only` (no 2025 regular-season row — e.g. a team new
to FBS or missing prior data).

## What this does not support

- **Not validated against betting lines or outcomes.** This is a rating, not
  a backtested edge — no claim it beats a market total or spread.
- **Not wired into `models/totals` or `research/spread`.** Standalone output
  only, per the scoping decision behind this build.
- **Regular season only.** Postseason/bowl games are excluded from both
  stages.
- **One-year prior by default.** `--prior-seasons 2` pools two prior years
  into one fit rather than weighting them by recency — an equal-weight pool,
  not a recency-decayed one.
- **Small early-season sample.** At 1-3 games played, Stage 1's own SE
  estimates (not just the shrinkage step) are themselves noisy; the
  `ConvergenceWarning` MixedLM emits on some fits reflects a variance
  component near the boundary of its search space, not necessarily a fitting
  failure — but it means Stage 1 SEs should be read as approximate, not exact.

## Reproduce

```bash
python scripts/build_ppa_opponent_adjusted_ratings.py --season 2026
python scripts/build_ppa_opponent_adjusted_ratings.py --season 2026 --week 3 --prior-seasons 2
```
