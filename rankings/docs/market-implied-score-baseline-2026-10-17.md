# Market-implied score baseline — 2026-10-17

**Answer: BUILT. The market-implied score is the score baseline to beat, and it beats both
in-house comparators clearly.**

- **2023–2025, SD fixed from 2021–2022 (2,251 games):** `implied` scores a pooled CRPS of
  6.213 and MAE of 8.781 points per side.
- **vs `ridge_v1`:** CRPS lower by 0.463 [0.325, 0.621], MAE lower by 0.66 [0.47, 0.87]. The
  gap holds in every season (CRPS −0.400, −0.441, −0.545 for 2023, 2024, 2025).
- **vs `mean`:** CRPS lower by 1.189 [1.066, 1.328], MAE lower by 1.728 [1.560, 1.915].
- **Calibration:** `implied` is close to unbiased (+0.32 points per side) with a slope of
  0.973 on actual-on-forecast. Its home and away scores are both slightly too spread out
  (slopes 0.970 and 0.958).
- **Joint structure:** the correlation between `implied`'s home and away errors is 0.038,
  close to zero. Theory §11 expected it to be clearly non-zero. See below.
- **Provisional:** CFBD's Bovada open has no timestamp, so whether it existed at decision
  time is assumed, not checked. Every number here is provisional until the odds provenance
  audit (roadmap §5) clears the open.

**Question.** What do the market's open spread and total, turned into one score per side,
score as a forecast of final points, and how far ahead are they of the in-house score models?

**Design:**
[`specs/2026-10-17-market-implied-score-design.md`](specs/2026-10-17-market-implied-score-design.md),
declared before build, amended once before scoring (opens start in 2021).
**Theory:** [`rating-model-theory.md`](rating-model-theory.md) §11.
**Reproduce:** `python -m scripts.market_implied_scores`
([`scripts/market_implied_scores.py`](../../scripts/market_implied_scores.py)). It writes
`data/processed/ratings/market_implied_scores.json`, which holds every number below. This was
the one scoring run, on code based at `53c9f27`.

## Method

For every FBS-vs-FBS game, regular season and postseason, with a Bovada `spreadOpen` and
`overUnderOpen` in `raw/lines_<season>.json` and a final score:

$$
\begin{gathered}
\hat S_h = \frac{T + M}{2}, \qquad \hat S_a = \frac{T - M}{2}, \qquad M = -s \\[1em]
\begin{array}{rl}
\text{where}\quad T: & \text{Bovada open total, points} \\
s: & \text{Bovada open spread, home-relative, negative when home is favoured} \\
M: & \text{implied home margin, points; positive when home is favoured} \\
\hat S_h, \hat S_a: & \text{implied home and away final scores, points}
\end{array}
\end{gathered}
$$

A home team favoured by 7 with a total of 55 gives a forecast of 31 to 24. Where a game has
more than one Bovada row, the first is used; a game needs both numbers to count.

The two comparators, each built only from games that kicked off before the week's first
kickoff:

| Name | Score forecast |
| --- | --- |
| `ridge_v1` | The weekly possession ridge's implied regulation points per side, plus half its overtime constant, refitted each week on that season's earlier games |
| `mean` | Season-to-date league mean final points, home and away separately |

Each model's forecast is a Normal with one SD for both sides. The SD is fitted on 2021–2022
by mean CRPS on a 0.5-point grid from 8 to 16, then held fixed:

| Model | Fitted SD (points) |
| --- | --- |
| `implied` | 11.0 |
| `ridge_v1` | 12.0 |
| `mean` | 13.5 |

Paired differences take the per-game loss as the mean of the two sides. Intervals are 95%
from a season-week block bootstrap, 2,000 draws, seed 20261017.

## Data and dates

- **Source:** CFBD `raw/lines_<season>.json` and `raw/games_<season>.json`. Nothing at or
  after 2026-10-17 00:00 UTC is read; the latest kickoff used is in the 2025 postseason.
- **Why 2021 onward:** no provider in `raw/lines` carries an open spread or total before
  2021. 2013–2020 holds only current lines, mostly consensus. The spec's 2014–2019 window
  could not be built (amendment in the spec).
- **Games:** 3,927 FBS-vs-FBS games with a Bovada open, 2021–2025. The comparison uses the
  3,685 that all three models share. The 242 left out are all from the opening week of each
  season, where neither comparator has an earlier game to fit on.

| Season | Games shared |
| --- | --- |
| 2021 | 720 |
| 2022 | 714 |
| 2023 | 738 |
| 2024 | 753 |
| 2025 | 760 |

## Results, 2023–2025 (descriptive, SD fixed)

2,390 games with a Bovada open; 2,251 shared.

| Model | MAE home | MAE away | MAE pooled | RMSE pooled | CRPS home | CRPS away | CRPS pooled |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `implied` | 9.208 | 8.355 | **8.781** | **11.024** | 6.492 | 5.934 | **6.213** |
| `ridge_v1` | 9.874 | 9.008 | 9.441 | 11.840 | 6.945 | 6.406 | 6.675 |
| `mean` | 10.941 | 10.077 | 10.509 | 13.080 | 7.664 | 7.140 | 7.402 |

All in points. Lower is better.

**Paired differences, `implied` minus comparator:**

| Comparator | MAE | CRPS | CRPS 2023 | CRPS 2024 | CRPS 2025 |
| --- | --- | --- | --- | --- | --- |
| `ridge_v1` | −0.660 [−0.870, −0.470] | −0.463 [−0.621, −0.325] | −0.400 | −0.441 | −0.545 |
| `mean` | −1.728 [−1.915, −1.560] | −1.189 [−1.328, −1.066] | −1.194 | −1.083 | −1.290 |

**Calibration.** Bias is actual minus forecast, so positive means the model scored too low.
Slope and intercept are from regressing actual points on forecast points; a slope of 1 and
intercept of 0 is perfect.

| Model | Side | Bias | Slope | Intercept |
| --- | --- | --- | --- | --- |
| `implied` | home | +0.488 | 0.970 | 1.32 |
| `implied` | away | +0.143 | 0.958 | 1.17 |
| `implied` | pooled | +0.316 | 0.973 | 1.03 |
| `ridge_v1` | home | −0.483 | 0.993 | −0.27 |
| `ridge_v1` | away | +1.235 | 0.937 | 2.70 |
| `ridge_v1` | pooled | +0.376 | 0.909 | 2.77 |
| `mean` | pooled | +0.350 | 0.589 | 11.16 |

`ridge_v1` under-forecasts away teams by about 1.2 points and over-forecasts home teams by
about 0.5. Its home edge is too large by roughly 1.7 points of margin. `implied` has no such
split. `mean` barely varies across games, so its slope says little.

## Results, other windows

**2021–2025 pooled (3,685 games; in-sample for the SD).** `implied` CRPS 6.247, MAE 8.847,
RMSE 11.080, slope 0.952. Against `ridge_v1`: CRPS −0.468 [−0.591, −0.357], MAE −0.652
[−0.826, −0.498]. Against `mean`: CRPS −1.222 [−1.329, −1.124], MAE −1.775 [−1.929, −1.631].
Every season from 2021 to 2025 favours `implied` against both comparators.

**2021–2022 (1,434 games; the SD fit window).** `implied` CRPS 6.301, MAE 8.950. Against
`ridge_v1`: CRPS −0.476 [−0.676, −0.307].

## Joint structure

If the market's two numbers miss together (a pace or weather shock that lifts both teams), the
home and away errors of `implied` should be positively correlated. They are not:

| Window | `implied` | `ridge_v1` | `mean` |
| --- | --- | --- | --- |
| 2023–2025 | 0.038 | −0.043 | −0.169 |
| 2021–2025 | 0.033 | −0.039 | −0.155 |
| 2021–2022 | 0.025 | −0.032 | −0.133 |

Two effects seem to cancel. Shared shocks to the game's pace push both errors the same way.
Shocks to the margin (one team plays far better than expected) push them opposite ways. In
the market's errors these roughly balance. `mean` knows nothing about the matchup, so the
margin shocks dominate and its errors are negatively correlated.

This does not show that home and away scores are independent. The correlation of the scores
themselves, and of the errors within subsets (high totals, weather, large spreads), is not
measured here. It does mean a per-side model with independent errors is not obviously wrong
on average, which matters for how much a joint score model can add over two per-side models.

## What this does not support

- **Decision time.** CFBD's Bovada open carries no observed-at time. That the open existed
  before any decision a model would make is assumed. Under the evaluation standard's
  reconstructibility gate, everything here is provisional until the odds provenance audit
  (roadmap §5) says the open can be trusted as pre-kickoff.
- **Betting.** A model that beats or loses to `implied` says nothing about a return. Nothing
  here is a bet.
- **Promotion.** This is a yardstick for later score and O/D models, not a candidate.
- **Early season.** The comparators are not built for the opening week, and `ridge_v1` uses
  only the current season, so its early weeks are weak. Part of its gap to `implied` comes
  from those weeks. This record does not break the gap down by week.
- **Before 2021.** No open lines exist on disk for 2013–2020, so the baseline cannot be
  scored there.
- **Margin.** `implied`'s margin is the open spread itself, already scored against Glicko in
  the v1 and P1 records. It is not re-scored here.

## Trial count

One baseline, two comparators, one SD grid per model. No rating was tuned, so the Glicko
family total in [`glicko-versions.md`](glicko-versions.md) does not change.
