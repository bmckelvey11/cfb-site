# Market-implied score baseline, declared before build — design

**Status:** declared 2026-10-17, before the baseline is built or scored.
**Why:** roadmap §4 names the market-implied score as the first score baseline any new
score or O/D model must beat, and lists it as not built
([`../rating-model-roadmap.md`](../rating-model-roadmap.md)). Theory §11 derives it.
**Leaves alone:** every frozen Glicko file, P1's sealed confirmation, the sealed 2026
`prior_v3` confirmation, and every holdout. Nothing here reads a game after 2026-10-16.

## The baseline

The market's open spread and total imply one score for each side:

$$
\begin{gathered}
\hat S_h = \frac{T + M}{2}, \qquad \hat S_a = \frac{T - M}{2}, \qquad M = -s \\[1em]
\begin{array}{rl}
\text{where}\quad T: & \text{Bovada open total (CFBD } \texttt{overUnderOpen}\text{), points} \\
s: & \text{Bovada open spread (CFBD } \texttt{spreadOpen}\text{), home-relative, negative when home is favoured} \\
M: & \text{implied home margin, points; positive when home is favoured} \\
\hat S_h, \hat S_a: & \text{implied home and away final scores, points, overtime included}
\end{array}
\end{gathered}
$$

A home team favoured by 7 with a total of 55 gives $M = 7$, so $\hat S_h = 31$ and
$\hat S_a = 24$. The two scores always add back to the total and differ by the margin, so the
baseline carries exactly the information in the two lines and nothing else. The total
includes overtime, so the baseline is scored on final scores.

## Comparators

| Name | Score forecast |
| --- | --- |
| `implied` | $(T \pm M)/2$ from the Bovada open, above |
| `ridge_v1` | The weekly possession ridge's implied regulation points (`scripts/weekly_forecast.py::_parts`), plus half its overtime constant to each side, fitted on games that kicked off before the week's first kickoff |
| `mean` | Season-to-date league mean points, home and away separately, from games before the week's first kickoff |

Glicko forecasts margins only, so it enters as a margin comparator: `implied`'s margin is the
open spread itself, already scored against Glicko in the v1 and P1 records.

## Games and seasons

- FBS-vs-FBS games, regular season and postseason, with a Bovada `spreadOpen` and
  `overUnderOpen` in `raw/lines_<season>.json` and a final score.
- Seasons 2014–2019 and 2021–2025, reported apart. 2020 is skipped, as in every ratings record.
- `ridge_v1` and `mean` are scored only on weeks where they can be built, and the comparison
  uses the games all three share.

## Scoring

- Point error: MAE and RMSE per side (home score, away score) and pooled.
- Probabilistic: CRPS of a Normal forecast per side. The forecast SD is one number per model,
  fitted on 2014–2019 by mean CRPS on a 0.5-point grid, then held fixed for 2021–2025. That is
  the only tuned quantity.
- Calibration: slope and intercept of actual score on forecast score, per side.
- Joint structure: correlation between the home and away errors of `implied`. Theory §11
  predicts it is not zero, which a per-side model would miss.
- Intervals: paired differences (`implied` minus each comparator) with a season-week block
  bootstrap, 2,000 draws, seed 20261017.
- Trial count: one baseline, two comparators, one SD grid per model. The family total in
  `rankings/docs/glicko-versions.md` does not change, since no rating is tuned.

## What this cannot support

- **Decision time.** CFBD's Bovada open has no observed-at timestamp, so "the line existed
  before the decision" is assumed, not checked. The odds audit (roadmap §5) runs alongside;
  until it lands, every number here is provisional under the evaluation standard's
  reconstructibility gate.
- **Betting.** Beating or losing to the market's own implied score says nothing about a
  return. Nothing here is a bet.
- **Promotion.** 2021–2025 is descriptive. The baseline is a yardstick for later models, not
  a candidate.

## Outputs

- `scripts/market_implied_scores.py`: builds the three forecasts and scores them; prints and
  writes JSON under `processed/ratings/`.
- `rankings/docs/market-implied-score-baseline-2026-10-17.md`: the record.
- Roadmap §4 and §9 status rows updated.
