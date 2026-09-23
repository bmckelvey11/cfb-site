# Re-tuning the rating penalties on total-forecast loss — design

**Status:** declared 2026-09-23 (`fc099b6`) before any scoring run; implemented and scored
the same day. Result: [`docs/weekly-lambda-total-2026-09-23.md`](../../weekly-lambda-total-2026-09-23.md).
**Builds on:** [`docs/weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md)
(`ridge_v1`) and [`docs/weekly-priors-2026-09-23.md`](../../weekly-priors-2026-09-23.md)
(`prior_v1`). Both scored better at λ ×2 on 2021–2025, which cannot be adopted from those
runs because the scored seasons were seen. This re-asks the question on pre-2021 data.
**Review:** none (Codex sandbox error 206). The user chose this step; the defaults below are
Claude's and are fixed here before scoring.

## Question

Release B tuned $\lambda_{\text{PPP}}$ and $\lambda_{\text{pace}}$ separately, each on its own
component loss. The thing scored is the total. Does tuning both penalties jointly on
one-step-ahead total-forecast error, on pre-2021 seasons only, choose different values —
and if so, do they forecast 2021–2025 totals better? At those values, do the priors pass
the go rule they failed?

## Method

- **Loss:** one-step-ahead mean absolute error of the full-game total, the metric scored.
  For each tuning season and each cutoff, fit on games before the cutoff and forecast every
  game of that week (gated games included, as in scoring).
- **Joint grid:** $\lambda_{\text{PPP}}\in\{10,20,40,80,160,320,640\}$ ×
  $\lambda_{\text{pace}}\in\{1,2,4,8,16,32,64\}$, 49 points per method. The total couples
  the two penalties, so they are not tuned independently here. A pick on a grid edge is
  flagged.
- **`ridge_v2`:** Release B's ridge at the λ pair tuned this way on 2014–2019, weeks 2+.
- **`prior_v2`:** the priors release's prior-centered ridge at the λ pair tuned this way on
  2015–2019, weeks 1+. Prior coefficients unchanged (fitted on 2014→2015 … 2018→2019).
- **Scoring:** 2021–2025, Bovada open, same populations and bootstrap as Release B and the
  priors release.

## Declared comparisons

Verdict rule unchanged (`classify_verdict`: worse if the pooled interval is above 0;
improves if it is below 0 and at most one season disagrees; else matches).

1. **`ridge_v2` − `ridge_v1`**, primary and early 2+. If the tuned pair equals (40, 8) the
   comparison is identically 0 and is reported as "λ unchanged". Not gated by stress: the
   question is the λ itself.
2. **`prior_v2` − `ridge_v2`**, early 2+ and primary, with the priors release's go rule:
   early improves, primary not worse, both unchanged under coefficient stress (×0.5, ×1.5)
   **and** under matched λ stress (both methods at ×0.5 and at ×2 of their own tuned pair).
   Matched λ stress replaces the priors release's confounded version, by design, before
   scoring.

**Trials:** 98 grid points (49 per method), on tuning seasons only; 2 methods scored.

## Files

- `scripts/weekly_total_tuning.py`: `tune_total` (joint grid, total MAE) and the scoring
  run; writes `data/processed/ratings/weekly_total_tuning_eval.json`. Reuses the existing
  fits, `run_season`, and the priors scoring functions; Release B's and the priors
  release's outputs are not touched.
- `tests/test_weekly_total_tuning.py`: the tuner returns the minimum of its own grid and is
  unchanged by games outside its tuning seasons.
- Finding doc in root `docs/`, README row, guide §13 steps 3–4 updated.

## What this cannot claim

- Nothing about betting value; the open has no clock and no price.
- A λ tuned on total error is still a pre-2021 choice; if it differs from ×2, the scored
  seasons' preference for ×2 stays an observation, not a setting.
