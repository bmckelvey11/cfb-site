# Carryover scale tuned pre-2021, confirmed on 2026 — design

**Status:** declared 2026-09-23, before the scale is tuned and before any 2026 result is
read by this thread.
**Builds on:** [`docs/weekly-lambda-total-2026-09-23.md`](../../weekly-lambda-total-2026-09-23.md):
at total-tuned λ the priors improve both populations but lose the gain under more prior
weight, and 2021–2025 is no longer an untouched holdout for this question.
**Review:** none (Codex sandbox error 206). The user chose this step; the defaults below are
Claude's.

## Question

Tuned on pre-2021 total-forecast loss, how much weight should last season carry — and
does the frozen result forecast 2026 better than `ridge_v1`?

## Tuning (pre-2021 only)

- **Scale** $k$ multiplies every carryover coefficient ($b$, $c$, $b_D$, $a$, fitted as
  before on 2014→2015 … 2018→2019): $k\in\{0,\,0.25,\,0.5,\,0.75,\,1.0,\,1.25\}$. $k=0$ is a
  prior-free ridge that forecasts week 1 at league average, so the tuning itself says
  whether priors help before 2021.
- **Jointly with λ:** for each $k$, the 7 × 7 λ grid of the λ re-tune; loss = one-step-ahead
  total MAE on 2015–2019, weeks 1+. 294 grid points.
- **Candidate `prior_v3`:** the $(k,\lambda_{\text{PPP}},\lambda_{\text{pace}})$ with the
  lowest loss. Written to `scripts/weekly_prior_v3.json` and **committed before any 2026
  scoring run**. If $k=0$ wins, there is no prior candidate and the 2026 step is not run.

## 2026 confirmation

- **Data:** 2026 regular season, FBS vs FBS, completed games only, Bovada open present.
  Priors from 2025 final `ridge_v1` ratings and 2026 returning production. Nothing about
  the candidate changes after the freeze.
- **Declared comparison:** `prior_v3` − `ridge_v1` (at 40, 8), early weeks 2+ and primary,
  `classify_verdict`, week-cluster bootstrap. Week 1 reported, not gated.
- **One confirmatory look:** the verdict counts once, after the last regular-season week of
  2026 is complete. Any earlier run is written with `"look": "interim"` and is descriptive
  only: no verdict is quoted from it and nothing is changed because of it.
- **Confirm** if, at the final look, early 2+ *improves* and primary is not *worse*. A
  single season has one cluster per week (~14), so the interval will be wide; a *matches*
  is recorded as unconfirmed, not as a failure.
- **Also reported:** `prior_v3` − open, and `ridge_v1` − open, per population.

## Files

- `scripts/weekly_prior_scale.py`: `tune` (writes the frozen JSON) and `confirm --season`
  (reads it; refuses to run without it).
- `scripts/weekly_prior_v3.json`: the frozen candidate, committed on its own.
- `tests/test_weekly_prior_scale.py`: the scale tuner returns the minimum of its grid and
  reads no season outside its tuning seasons; `confirm` refuses to run without a frozen file.
- Finding doc for the tuning result; the 2026 result gets its own dated doc at the final
  look.

## What this cannot claim

- An interim 2026 look is not evidence either way.
- No betting value: the open has no capture time and no price.
