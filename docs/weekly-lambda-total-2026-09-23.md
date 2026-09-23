# Re-tuning the rating penalties on total-forecast loss

**Question.** The weekly ratings' penalties were tuned on component losses (points per
possession, possessions), but the total is what gets scored, and both `ridge_v1` and
`prior_v1` scored better at double the penalty on 2021–2025 — a preference that could not
be adopted because those seasons were seen. Tuned jointly on one-step-ahead total error
over pre-2021 seasons only, do the penalties change, do they forecast 2021–2025 better, and
do the priors now pass their go rule?

**Answer.** The ridge penalties do not move in any way that matters: total-loss tuning on
2014–2019 picks (40, 4) against Release B's (40, 8), their tuning losses differ by 0.003
points, and on 2021–2025 the two forecast the same (difference −0.001, interval ±0.03). The
scored seasons' preference for double the penalty is not something pre-2021 data would have
chosen. With priors, total-loss tuning picks a heavier offense/defense penalty (80, 8),
and at those settings the priors improve on the ridge in both early weeks (−0.36) and later
weeks (−0.11) — but they are still a no-go by the declared rule: the gain is lost whenever
the priors are given more weight (carryover ×1.5, or both penalties doubled).

Reproduce:

```text
python -m scripts.weekly_total_tuning
```

Script: [`scripts/weekly_total_tuning.py`](../scripts/weekly_total_tuning.py). Tests:
[`tests/test_weekly_total_tuning.py`](../tests/test_weekly_total_tuning.py). Design, committed
before any scoring run (`fc099b6`):
[`superpowers/specs/2026-09-23-lambda-total-tuning-design.md`](superpowers/specs/2026-09-23-lambda-total-tuning-design.md).
Output (gitignored): `data/processed/ratings/weekly_total_tuning_eval.json`.

## Method

- **Loss:** one-step-ahead mean absolute error of the full-game total, every cutoff, every
  game of the week (gated games included, as in scoring).
- **Joint grid:** $\lambda_{\text{PPP}}\in\{10,\dots,640\}$ possessions ×
  $\lambda_{\text{pace}}\in\{1,\dots,64\}$ games, 49 points per method.
- **`ridge_v2`:** Release B's ridge at the pair tuned on 2014–2019, weeks 2+ (4,113 games).
- **`prior_v2`:** the priors release's prior-centered ridge (same carryover coefficients) at
  the pair tuned on 2015–2019, weeks 1+ (3,644 games).
- **Scoring:** 2021–2025, Bovada open, the Release B populations (early 2+: 862 games, 23
  season-week clusters; primary: 2,618, 61 clusters), week-cluster bootstrap, 10,000 draws.
- **Declared comparisons:** `ridge_v2` − `ridge_v1` (not stress-gated); `prior_v2` −
  `ridge_v2` with the priors go rule under coefficient stress (×0.5, ×1.5) and **matched**
  λ stress (both methods at ×0.5 and ×2 of their own tuned pair).
- **Trials:** 98 grid points on tuning seasons; 2 methods scored.

## Numbers

**Tuning.** `ridge_v2`: (40, 4), MAE 13.844; Release B's (40, 8) scores 13.848 on the same
games, and the next three pairs are within 0.035. `prior_v2`: (80, 8), MAE 13.683; at
(40, 8) the priors score 13.739. Neither pick is on a grid edge.

**`ridge_v2` − `ridge_v1`:** early 2+ −0.006 (−0.050 to +0.035, MDE 0.06); primary −0.001
(−0.035 to +0.031, MDE 0.05). Both *matches*.

**`prior_v2` − `ridge_v2`** (negative = priors closer):

| | Early 2+ | Primary |
| --- | --- | --- |
| Base | **−0.36** (−0.61 to −0.14), improves | **−0.11** (−0.22 to −0.01), improves |
| Per season 2021 / 22 / 23 / 24 / 25 | −0.38 / −0.97 / −0.22 / −0.00 / −0.28 | −0.14 / −0.12 / +0.02 / −0.24 / −0.08 |
| Coefficients ×0.5 | −0.30 (−0.45 to −0.15), improves | −0.14 (−0.22 to −0.06), improves |
| Coefficients ×1.5 | −0.27 (−0.62 to +0.04), matches | −0.01 (−0.16 to +0.13), matches |
| Matched λ ×0.5 | −0.53 (−0.78 to −0.31), improves | −0.27 (−0.36 to −0.18), improves |
| Matched λ ×2 | −0.26 (−0.51 to −0.04), matches (two seasons disagree) | +0.01 (−0.11 to +0.13), matches |
| **Go** | **no**: unstable | |

**All forecasts on the same games** (MAE, bias):

| Forecast | Early 2+ | Primary |
| --- | --- | --- |
| Bovada open | 12.59, −0.15 | 12.60, −0.22 |
| `prior_v2` | 12.87, −1.48 | 12.82, −0.20 |
| `ridge_v2` | 13.24, −1.41 | 12.94, −0.20 |
| `ridge_v1` | 13.24, −1.36 | 12.94, −0.18 |
| Train mean | 13.47, +2.21 | 13.78, +2.23 |

Against the open: `prior_v2` +0.28 early (−0.05 to +0.65, no longer distinguishable) and
+0.22 primary (+0.08 to +0.37); `ridge_v2` +0.64 and +0.33. Encompassing slopes against the
open, `prior_v2`: 0.22 early (−0.05 to 0.53), 0.13 primary (−0.08 to 0.34).

Week 1 does not depend on λ, so it is the priors release's result unchanged.

## What this changes downstream

- **Release B's λ stands.** Tuning on the scored metric, on pre-2021 data, lands on the same
  place. The 2021–2025 preference for λ ×2 is an observation about those seasons, not a
  setting; nothing here supports changing it.
- **The priors question is sharper, not settled.** At their own total-tuned penalty the
  priors improve both populations, and the early forecasts close most of the gap to the
  open. Every variant that gives the priors *less* weight keeps or grows the gain; every
  variant that gives them *more* weight loses it. The fitted carryover (offense 0.47,
  defense 0.60, pace 0.46) sits on the good side of that line but without the margin the
  declared rule asks for.
- **The principled next test** is to fit the priors' overall weight the same way the
  penalty was just fit — one scale on the carryover, tuned on pre-2021 total loss — and
  score it once, instead of reading ×0.5 off the scored seasons.
- `ridge_v1` remains the base rating.

## What this does not support

- **Not "priors work".** The go rule was declared and failed; the base-setting wins are
  real within this run but not robust to the stated perturbations.
- **Not adopting λ ×0.5 or carryover ×0.5.** Both look best here and were seen on the scored
  seasons.
- **Not a market finding.** Closing the early gap to the open is forecast error against an
  untimed, unpriced vendor label; no wager is graded. The early intervals rest on 23
  clusters, which runs narrow.
- **Not a claim about the tuning grid's resolution.** Adjacent pairs are within 0.035 MAE;
  the pick is one point on a flat surface.
