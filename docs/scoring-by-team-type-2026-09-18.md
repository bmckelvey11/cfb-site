# Where each type of team scores its points (2015-2025)

**Question.** Split a team's own scoring across the four quarters and the two
halves. Do some *types* of team — good offenses, fast offenses — put their points
in different places than others?

## Method

`stg.game_team__line_scores`, FBS vs FBS only, regulation quarters
(`lineScores_idx` 1-4; overtime periods are excluded), 2015-2025. 8,325 games,
16,650 team-games, 27.37 points per team-game.

Two team-type dimensions, both taken from the team's **prior season**, so the
bucket label is never computed from the games being measured:

| dimension | source | buckets |
| --- | --- | --- |
| offense quality | `stg.ratings.spOffense`, season − 1 | quartiles, cut per season |
| tempo | `stg.advanced_season_stats.offense_plays` / games, season − 1 | quartiles, cut per season |

Quartile cut points are recomputed **per season**, so "fastest 25%" means the
same thing in 2015 and 2025 despite the scoring drift over the window. Prior-season
attributes are available for 127-136 of the 128-136 teams in each season
(SP+ 97-100%, tempo 98-100%); teams without a prior FBS season are dropped.

Shares are **ratios of pooled totals** — sum of points in Qk over sum of all
points in the bucket — not averages of per-game shares. A team held scoreless has
no defined per-game share, and a 3-point game should not weigh the same as a
45-point one.

Reproduce: `python scripts/analyze_scoring_by_team_type.py`.

## Baseline: every team, every game

| | Q1 | Q2 | Q3 | Q4 |
| --- | --- | --- | --- | --- |
| share of own points | 22.28% | 29.77% | 22.63% | 25.32% |

First half 52.06%, second half 47.94%. Q2 is by far the biggest quarter and Q1 is
the smallest — the same shape the play-level analysis found
([scoring-by-minute](scoring-by-minute-2026-09-18.md): Q2 is 17.26 of 56.50 points
per game, 30.6%). Two independent sources, one answer.

## By offense quality — good offenses front-load

| prior-season SP+ offense | pts/game | Q1 | Q2 | Q3 | Q4 | 1H | 2H |
| --- | --- | --- | --- | --- | --- | --- | --- |
| top quartile | 31.53 | 22.90% | 30.13% | 22.73% | **24.25%** | **53.03%** | 46.97% |
| 3rd | 28.53 | 22.31% | 29.59% | 22.73% | 25.37% | 51.90% | 48.10% |
| 2nd | 25.99 | 22.29% | 29.82% | 22.39% | 25.50% | 52.11% | 47.89% |
| bottom quartile | 23.20 | 21.33% | 29.46% | 22.69% | **26.52%** | **50.79%** | 49.21% |

Monotone in both tails. The best offenses take **22.90%** of their points in Q1
and **24.25%** in Q4; the worst take **21.33%** and **26.52%**. The first-half
share runs 53.03% down to 50.79% — a **2.24 point** gap between the extremes.

**Does it reproduce?** The best-minus-worst first-half gap is positive in
**10 of 11 seasons**, ranging −0.68 (2015) to +5.16 (2018):

| season | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gap (pp) | −0.68 | 3.02 | 0.31 | 5.16 | 2.31 | 2.64 | 1.66 | 3.14 | 3.20 | 1.89 | 2.09 |

Real and repeatable, but noisy season to season — a single season is not enough
to measure it.

## By tempo — much weaker, and not a clean gradient

| prior-season plays/game | pts/game | Q1 | Q2 | Q3 | Q4 | 1H | 2H |
| --- | --- | --- | --- | --- | --- | --- | --- |
| fastest 25% | 29.24 | 22.87% | 29.54% | 22.73% | 24.87% | 52.41% | 47.59% |
| fast-mid | 27.77 | 22.21% | 30.31% | 22.55% | 24.92% | 52.53% | 47.47% |
| slow-mid | 27.05 | 22.35% | 29.44% | 22.46% | 25.75% | 51.78% | 48.22% |
| slowest 25% | 25.54 | 21.63% | 29.81% | 22.82% | 25.74% | 51.45% | 48.55% |

Tempo moves the *level* clearly — fastest 29.24 against slowest 25.54 points per
game — but barely moves the *shape*. The two fast buckets sit at 52.4-52.5%
first-half and the two slow buckets at 51.4-51.8%, a 1.08 point gap between the
extremes, less than half the offense-quality gap, and the middle two buckets are
out of order. Treat this as "fast teams are slightly more front-loaded", not as a
gradient.

## What is probably going on

The offense-quality pattern is what garbage time looks like from the other side.
A bad offense spends more of its Q4 minutes trailing, and the
[minute-level split](scoring-by-minute-2026-09-18.md) shows a trailing offense
scoring at 1.18 points per game-minute in Q4 against 0.87-0.90 for a leading one,
rising to 3.00 in the final minute. The two findings are the same mechanism seen
through different keys: bad offenses are back-loaded because bad offenses trail,
and trailing teams score late against defenses that have stopped selling out.

This is an interpretation, not a measured decomposition — nothing here separates
game state from team type.

## What this does not support

- **No causal claim.** Bad offenses are back-loaded; this does not show that being
  bad *causes* late scoring. Game state is the obvious confound and was not
  controlled for.
- **Not a market study.** No line, total or live price is joined anywhere here.
  A team type's Q4 share says nothing about whether a quarter or half line is
  mispriced.
- **Shares are not rates.** A bucket's Q4 share is a share of *its own* points,
  so a back-loaded bad offense still scores fewer Q4 points per game (6.15) than
  a front-loaded good one (7.65).
- **Prior-season labels are stale by construction.** A team that changes
  coordinator carries last year's bucket. That is the price of avoiding
  circularity, and it biases every effect here *towards zero*.
- **Opponent is not controlled.** A top-quartile offense also tends to face the
  schedule a top-quartile program draws. The buckets mix team quality with
  opponent quality.
- **Overtime is excluded** and postseason is pooled in.
- **Two dimensions only.** Pass rate and explosiveness correlate with both of
  these and were not run separately.
