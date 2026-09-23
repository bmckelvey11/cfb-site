# Previous-season priors for the weekly ratings

**Question.** Does starting each team's weekly ratings from a prior built on last season,
instead of from league average, make the Release B totals forecast better — in the early
weeks where Release B collapsed to the mean, and without costing anything later? Can
week 1 be forecast at all?

**Answer.** Not by the rule declared before scoring. At the tuned settings the priors help
in weeks 2+ while a team has fewer than three games (0.24 points closer than Release B's
ridge, interval clear of zero, four of five seasons) and are indistinguishable from it once
both teams have three games. But the early gain disappears when the ridge penalty is halved
or the prior coefficients are scaled up by half, so the declared go condition — improve
early, not worse later, both unchanged under all four stress variants — is not met. Week 1
can now be forecast; the priors beat the pooled mean there in three of five seasons and
trail the Bovada open in three of five.

Reproduce:

```text
python -m scripts.weekly_priors_eval --tune-seasons 2015-2019 --score-seasons 2021-2025
```

Scripts: [`scripts/weekly_priors.py`](../scripts/weekly_priors.py) (priors),
[`scripts/weekly_ratings.py`](../scripts/weekly_ratings.py) (`fit_ridge(prior=...)`),
[`scripts/weekly_priors_eval.py`](../scripts/weekly_priors_eval.py) (tuning and scoring).
Tests: [`tests/test_weekly_priors.py`](../tests/test_weekly_priors.py). Design:
[`superpowers/specs/2026-09-23-weekly-priors-design.md`](superpowers/specs/2026-09-23-weekly-priors-design.md).
Outputs (gitignored): `data/processed/ratings/weekly_priors_eval.json` (every number below,
input and code sha256s) and `weekly_priors_snapshots.csv` (10,230 team rows). Release B's
outputs are not touched.

## Method

- **Priors** (guide §7.4, restricted to CFBD inputs). Last season's final Release B ridge
  ratings, scaled toward average: offense $O_0=(b+c\,\text{RP})\,O_{-1}$ with $\text{RP}$ =
  CFBD offensive returning production (`percentPPA`); defense $D_0=b_D\,D_{-1}$ (CFBD has no
  defensive returning production); pace $P_0=a\,P_{-1}$. Centered per season. A team new to
  FBS starts at 0 (1–3 a season); no scored-season team needed RP imputed.
- **Coefficients** by no-intercept OLS on the 2014→2015 … 2018→2019 transitions (642
  team pairs), target = the next season's final rating, team-clustered SEs.
- **`prior_v1`** is Release B's ridge with each rating written as prior plus deviation, and
  only the deviation penalized (guide §7.5). With no games, ratings are the priors. Week 1
  uses last season's final league levels.
- **Penalties** re-tuned with the priors on 2015–2019 by Release B's one-step-ahead
  component loss, week 1 included.
- **Scoring** on 2021–2025, everything frozen, against Release B's `ridge_v1` on the same
  games, with the Bovada open and the pooled train mean alongside. Week-cluster bootstrap,
  10,000 draws, seed 20260922; MDE = 2.8 × bootstrap SE.
- **Declared go:** `prior_v1` − `ridge_v1` *improves* on early weeks 2+ **and** is not
  *worse* on primary, both unchanged at λ ×0.5, λ ×2, coefficients ×0.5 and ×1.5.
- **Release B check:** the run recomputes `ridge_v1` and `raw_v1` and reproduces Release B's
  recorded pooled differences (−1.1381, −0.8401) exactly.
- **Trials:** 14 λ grid points, 4 coefficients, 1 method, 4 stress variants.

## Numbers

**Carryover coefficients** (642 pairs, 2015–2019 targets):

| Coefficient | Estimate | SE | Reading |
| --- | ---: | ---: | --- |
| $b$ (offense, base) | 0.471 | 0.105 | about half of last season's offense carries over |
| $c$ (offense × RP) | 0.127 | 0.144 | returning production adds no detectable carryover |
| $b_D$ (defense) | 0.603 | 0.037 | defense carries over more than offense |
| $a$ (pace) | 0.463 | 0.048 | |

RP runs 0.03–1.27 (CFBD's `percentPPA` can exceed 1). At mean RP (0.61) the offense
carryover is 0.55.

**Tuned penalties:** 40 possessions and 8 games, the same as Release B, both inside their
grids.

**Declared verdicts**, `prior_v1` − `ridge_v1` MAE (negative = priors closer):

| Population | n | Difference | 95% interval | MDE | Per season 2021 / 22 / 23 / 24 / 25 | Verdict |
| --- | ---: | ---: | --- | ---: | --- | --- |
| Early weeks 2+ | 862 | −0.24 | −0.44 to −0.07 | 0.27 | −0.28 / −0.80 / −0.01 / +0.06 / −0.23 | improves, **unstable** |
| Primary | 2,618 | −0.01 | −0.09 to +0.06 | 0.10 | +0.04 / −0.03 / −0.04 / −0.01 / −0.03 | matches, **unstable** |

**Stress** (same comparison, each variant against the unchanged `ridge_v1`):

| Variant | Early 2+ | Primary |
| --- | --- | --- |
| λ ×0.5 | +0.07 (−0.12 to +0.27), matches | +0.24 (+0.14 to +0.33), worse |
| λ ×2 | −0.36 (−0.61 to −0.12), improves | −0.12 (−0.23 to −0.01), improves |
| coefficients ×0.5 | −0.20 (−0.31 to −0.10), improves | −0.03 (−0.07 to +0.00), matches |
| coefficients ×1.5 | −0.14 (−0.43 to +0.12), matches | +0.05 (−0.06 to +0.15), matches |

**Early weeks 2+, all forecasts on the same 862 games:** open 12.59, `prior_v1` 13.00,
`ridge_v1` 13.24, train mean 13.47. `prior_v1` − mean −0.48 (−0.82 to −0.10; Release B's
ridge could not separate from the mean here). `prior_v1` − open +0.41 (+0.04 to +0.80).
Encompassing slope against the open 0.16 (−0.11 to 0.47). Both ridge versions run about
1.4 points low early.

**Primary, 2,618 games:** open 12.60, `prior_v1` 12.92, `ridge_v1` 12.94. `prior_v1` − open
+0.32 (+0.17 to +0.47). Encompassing slope 0.02 (−0.16 to 0.22).

**Week 1** (241 games; one cluster per season, so no interval):

| Forecast | MAE | Bias (forecast − actual) |
| --- | ---: | ---: |
| Bovada open | 12.89 | +3.14 |
| `prior_v1` | 13.50 | +2.69 |
| Train mean | 13.63 | +4.03 |

| Paired MAE difference | Pooled | Per season 2021 / 22 / 23 / 24 / 25 | Seasons priors closer |
| --- | ---: | --- | ---: |
| `prior_v1` − train mean | −0.13 | +0.23 / −0.50 / +0.56 / −0.57 / −0.51 | 3 of 5 |
| `prior_v1` − open | +0.61 | −0.76 / −0.39 / +1.39 / +1.22 / +1.82 | 2 of 5 |

Every week-1 forecast runs high, the open included, by 2.7–4.0 points.

## What this changes downstream

- **Priors are built, not adopted.** `fit_ridge(prior=...)`, the carryover fit and week-1
  ratings exist and are tested. By the declared rule the release is a no-go, so Release B's
  `ridge_v1` stays the base rating for Release C.
- **The instability has a direction.** Weaker shrinkage (λ ×0.5) or stronger carryover
  (coefficients ×1.5) erases the early gain; stronger shrinkage (λ ×2) enlarges it and also
  wins on primary. The tuned λ came from component loss on 2014–2019; a λ chosen for the
  total, on pre-2021 seasons, is the next test. **λ ×2 cannot be adopted from this run**: it
  was seen on the scored seasons, so choosing it here would be a threshold picked on the
  test set.
- **Returning production does not earn its term** ($c$ = 0.13, SE 0.14). A carryover-only
  prior is the simpler equivalent until an input with more signal (talent change, the
  play-caller table) is available.
- **Week 1 is now forecastable**, and forecasts there run high across the board. Whether
  week-1 league levels should be discounted is a separate question (guide §14 item 3's
  clock-effect work is adjacent).

## What this does not support

- **Not "priors don't help".** The base result is an early improvement with an interval
  clear of zero; the no-go is about robustness to the settings, as declared, not about sign.
- **Not a verdict on week 1.** Five clusters cannot carry an interval; three of five is a
  count, not evidence.
- **Not a market finding.** The open's week-1 bias of +3.14 is one number per season pooled
  over five seasons of untimed, unpriced opens. It is a lead, not a mispricing.
- **No betting value.** Forecast error against a vendor label with no capture time and no
  price ([Release A](pregame-replay-2026-09-22.md)); no wager is graded.
- **Not a full guide §7.4 prior.** No talent change, no coaching or play-caller switch, no
  per-team prior strength, no second lag.
