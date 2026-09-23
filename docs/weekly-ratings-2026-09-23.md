# Weekly PPP and pace ratings vs the mean and the Bovada open (Release B)

**Question.** Do weekly, as-of opponent-adjusted team points-per-possession and pace
ratings forecast FBS game totals better than simpler baselines — an unadjusted
season-to-date version and a pooled train mean — on seasons they were not tuned on? And how
do they compare with the Bovada open?

**Answer.** Yes against both baselines, not against the open. On 2,618 FBS-vs-FBS games
from 2021–2025 where both teams had played at least three FBS games, the ridge rating's
total is 1.14 points closer than the raw version and 0.84 points closer than the train mean
(mean absolute error; both intervals clear of zero, every season the same sign, unchanged
at half and double the tuned penalty). It is 0.33 points further from the total than the
Bovada open label, every season. Its disagreement with the open carries no detectable
information about where the total lands.

Reproduce:

```text
python -m scripts.weekly_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025
```

Scripts: [`scripts/weekly_ratings.py`](../scripts/weekly_ratings.py) (fits),
[`scripts/weekly_ratings_eval.py`](../scripts/weekly_ratings_eval.py) (tuning and scoring).
Tests: [`tests/test_weekly_ratings.py`](../tests/test_weekly_ratings.py). Design and
equations: [`superpowers/specs/2026-09-22-weekly-ratings-design.md`](superpowers/specs/2026-09-22-weekly-ratings-design.md).
Outputs (gitignored): `data/processed/ratings/weekly_ratings_eval.json` (every number
below, input and code sha256s) and `weekly_ratings_snapshots.csv` (39,924 team rows).

## Method

- **Ratings.** Guide §7.1–7.3 without priors
  ([`totals-modeling-guide.md`](../research/totals/docs/totals-modeling-guide.md)).
  Team points per possession is $\mu+O_{\text{team}}+D_{\text{opp}}+hH$, weighted by
  possessions; possessions per team is $\nu+P_{\text{home}}+P_{\text{away}}$; the total is
  possessions times the two teams' rates plus the average overtime points.
  - `ridge_v1`: ridge penalty toward 0 (league average); $\mu$, $\nu$, $h$ unpenalized.
  - `raw_v1`: season-to-date means minus the league mean; no adjustment, no shrinkage.
- **Points and possessions.** Points are Q1–Q4 line scores. Drive score fields are never
  read: from 2021 on, 19–58 FBS games a season have drive points above the final score.
  Possessions are regulation drives. So $O$ is a **team** rate: a team's own defensive and
  return touchdowns are in it.
- **Gate.** A game with no drives, or whose two teams' drive counts differ by more than 2,
  is withheld from fits (12–31 games a season, about 2%). It can still be scored.
- **As of.** Week $w$'s ratings are fit on the season's games that kicked off strictly
  before week $w$'s earliest kickoff, through the Release A `snapshot()`. Week 1 is not
  rated.
- **Tuning.** On 2014–2019 only (85 weekly cutoffs), by one-step-ahead component loss:
  possession-weighted squared error of points per possession for $\lambda_{\text{PPP}}$,
  squared error of possessions for $\lambda_{\text{pace}}$. Picks: $\lambda_{\text{PPP}}=40$
  possessions, $\lambda_{\text{pace}}=8$ games; neither on its grid's edge. A penalty of 40
  possessions means a team needs about three games before its own results outweigh league
  average.
- **Scoring.** 2021–2025, penalties frozen. Four forecasts of the full-game total on the
  same games: the Bovada `overUnderOpen` label (fixed book, no fallback), the mean total of
  every FBS-vs-FBS game since 2014 before the cutoff, `raw_v1`, `ridge_v1`. Differences are
  paired per game; intervals are a week-cluster bootstrap (whole season-weeks resampled,
  10,000 draws, seed 20260922) because every game in a week shares one snapshot. The MDE
  beside each interval is 2.8 × the bootstrap SE (80% power, two-sided 5%).
- **Verdict rule**, declared before scoring: *improves* if the pooled interval is below 0
  and at most one season disagrees; *worse* if it is above 0; *matches* otherwise.
- **Trials:** 12 tuning grid points (tune seasons only), 2 methods scored, 1 book, 2
  stress variants (penalties ×0.5 and ×2).

## Data

- `data/raw/games_<s>.json`, `drives_<s>.json` for 2014–2025, `lines_<s>.json` for
  2021–2025. 2020 is loaded for the train mean only; it is neither tuned nor scored.
- Scored: 3,488 week-2+ FBS-vs-FBS regular-season games, 3,480 with a Bovada open.
  Primary population (both teams ≥3 prior ungated FBS-vs-FBS games): 2,618. Early (some team
  <3): 862.

## Numbers

**Primary population, pooled 2021–2025 (n = 2,618; 61 season-week clusters).**

| Forecast | MAE | RMSE | Bias (forecast − actual) |
| --- | ---: | ---: | ---: |
| Bovada open label | 12.60 | 15.86 | −0.22 |
| `ridge_v1` | 12.94 | 16.35 | −0.18 |
| Train mean | 13.78 | 17.19 | +2.23 |
| `raw_v1` | 14.08 | 17.69 | −0.24 |

**Paired MAE differences** (first minus second; negative = first is closer).

| Comparison | Difference | 95% interval | MDE | Per season 2021 / 22 / 23 / 24 / 25 | Verdict |
| --- | ---: | --- | ---: | --- | --- |
| ridge − raw | −1.14 | −1.39 to −0.91 | 0.34 | −1.40 / −0.73 / −0.92 / −1.43 / −1.21 | improves, stable |
| ridge − train mean | −0.84 | −1.09 to −0.59 | 0.36 | −0.47 / −1.31 / −1.31 / −0.34 / −0.78 | improves, stable |
| ridge − open | +0.33 | +0.19 to +0.48 | 0.21 | +0.46 / +0.49 / +0.21 / +0.18 / +0.35 | (reported) |
| raw − train mean | +0.30 | −0.10 to +0.70 | 0.58 | +0.92 / −0.58 / −0.39 / +1.09 / +0.43 | (reported) |

Stress: at penalties ×0.5 the two verdict differences are −0.89 and −0.59, at ×2 they are
−1.22 and −0.93; every interval stays below zero, so both verdicts hold.

**Encompassing slope against the open**, $b$ in $T-L=a+b(F-L)$, where $T$ is the total,
$L$ the open and $F$ the forecast:

| Forecast | $b$ | 95% interval |
| --- | ---: | --- |
| `ridge_v1` | 0.03 | −0.13 to 0.20 |
| `raw_v1` | −0.09 | −0.16 to −0.01 |
| Train mean | 0.15 | 0.06 to 0.23 |

**Early population** (week 2+, a team with <3 prior games; n = 862, 23 clusters): open
12.59, ridge 13.24, train mean 13.47. Ridge − mean −0.23 (−0.56 to +0.14, MDE 0.50):
cannot tell. Ridge − open +0.65 (+0.21 to +1.13). Ridge's early bias is −1.36 points.

## What this changes downstream

- **Guide §13 step 3 is built.** Point-in-time PPP and pace ratings exist, with as-of
  snapshots, and the ridge version clears the go/no-go bar against simpler baselines. It is
  the base rating for Release C and for priors (step 4), where only the penalty's target
  changes.
- **Opponent adjustment and shrinkage are what earn the gain.** The raw version is no
  better than a pooled mean (−0.10 to +0.70). Averaging a team's own games, even after three
  of them, is too noisy to use.
- **The open stays the benchmark to beat, and ridge does not beat it.** Ridge is 0.33
  points worse on average and its disagreement with the open has no detectable value
  ($b$ = 0.03). Nothing here is a reason to trust a ratings-vs-open gap.
- **Early weeks need priors.** Where some team has fewer than three games, ridge cannot be
  told apart from the pooled mean and is 0.65 points behind the open, and its −1.36 bias
  says the early current-season league levels run low. That is the step-4 problem, now
  measured.

## What this does not support

- **No betting value.** This is forecast error of a point total against a labeled vendor
  number with no capture time and no price ([Release A](pregame-replay-2026-09-22.md)). It
  grades no wager and supports no return, cover-rate or closing-line claim.
- **Not "−0.84 against the mean is all team-rating skill".** The pooled mean carries a
  +2.23 bias from scoring drift since 2014, and ridge uses current-season league levels, so
  part of that gap is a level correction. Ridge − raw (same league levels, −1.14) is the
  comparison that isolates adjustment and shrinkage. A current-season-mean baseline was not
  declared before scoring and is not added here.
- **Not "ratings add nothing beyond the open".** The encompassing slope uses an estimated
  regressor: rating noise biases $b$ toward zero, so $b\approx0$ is a weak null, not
  evidence of absence.
- **The train mean's slope of 0.15 is not an established market miscalibration.** It says
  totals landed about 15% of the way from the open toward the pooled mean, which would mean
  the opens are slightly too spread out. Its interval is clear of zero, but this is one
  comparison among several, on unpriced, untimed opens; it is a lead for guide §14 item 2,
  not a finding.
- **Not a statement about FBS–FCS games, 2020, week 1, or seasons before 2021** against
  the open.
- **Not a tuned final model.** No garbage-time filter, no neutral pace, no priors, one
  penalty per rating.
