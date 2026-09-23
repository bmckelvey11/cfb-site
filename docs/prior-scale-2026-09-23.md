# Carryover scale for the priors, and the frozen 2026 candidate

**Question.** The priors lost their 2021–2025 gain when given more weight, and 2021–2025
can no longer serve as a clean test for them. Tuned on pre-2021 data only, how much of last
season should the priors carry — and what exactly will 2026 be asked to confirm?

**Answer.** All of the fitted carryover. Tuned jointly with the penalties on one-step-ahead
total error over 2015–2019, the best scale is $k=1.0$ at $\lambda$ = (80, 8): the fitted
coefficients as they are, which makes the frozen candidate `prior_v3` identical to
`prior_v2`. Priors at that setting forecast 2015–2019 totals 0.24 points better than the
same fit with no priors. The candidate is frozen in `scripts/weekly_prior_v3.json`
(`88dbfdc`) and will be judged once, on the completed 2026 regular season.

Reproduce:

```text
python -m scripts.weekly_prior_scale tune
python -m scripts.weekly_prior_scale confirm --season 2026
```

`tune` reproduces the table below into `data/processed/ratings/weekly_prior_scale_tune.json`
and leaves the freeze alone; `tune --freeze` wrote the freeze once and refuses to overwrite
it.

Script: [`scripts/weekly_prior_scale.py`](../scripts/weekly_prior_scale.py). Tests:
[`tests/test_weekly_prior_scale.py`](../tests/test_weekly_prior_scale.py). Design, committed
before tuning (`f96b6e0`):
[`superpowers/specs/2026-09-23-prior-scale-2026-confirmation-design.md`](superpowers/specs/2026-09-23-prior-scale-2026-confirmation-design.md).
Frozen candidate: [`scripts/weekly_prior_v3.json`](../scripts/weekly_prior_v3.json).

## Method

- **Scale** $k$ multiplies every carryover coefficient (offense 0.471 + 0.127 × RP,
  defense 0.603, pace 0.463; fitted on 2014→2015 … 2018→2019). $k=0$ is the same
  prior-centered ridge with every prior at league average, so it forecasts week 1 at the
  league mean.
- **Grid:** $k\in\{0, 0.25, 0.5, 0.75, 1.0, 1.25\}$, each with the 7 × 7 λ grid, 294 points.
- **Loss:** one-step-ahead total MAE on 2015–2019, weeks 1+ (3,644 games). Seasons after 2019
  are not loaded.

## Numbers

| Scale $k$ | 0 | 0.25 | 0.5 | 0.75 | **1.0** | 1.25 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Best λ (PPP, pace) | 40, 4 | 80, 8 | 80, 8 | 80, 8 | **80, 8** | 80, 8 |
| MAE, 2015–2019 | 13.927 | 13.820 | 13.739 | 13.695 | **13.683** | 13.716 |

The curve falls steadily to $k=1$ and turns up at 1.25. Neither the scale nor the λ pick is
on a grid edge. Two caveats weaken what the curve can say. The 0.24-point gain over $k=0$ is
a tuning-set difference on the same games that chose it, with no interval. And the carryover
coefficients were themselves fitted by OLS on 2015–2019 final ratings, so a minimum near
$k=1$ on weekly forecasts of those same seasons is partly built in. 2026 is the only real
test.

## The 2026 protocol

- **Candidate:** `prior_v3` = $k$ 1.0, λ (80, 8), the coefficients above, priors from 2025
  final `ridge_v1` ratings and 2026 returning production.
- **Comparison:** `prior_v3` − `ridge_v1` (40, 8) on early weeks 2+ and on primary, 2026
  FBS-vs-FBS games with a Bovada open, week-cluster bootstrap.
- **One look counts:** the first run after no FBS-vs-FBS regular-season game is still
  scheduled (a game that passed its kickoff without completing is counted, not waited on).
  **Confirmed** if early 2+ *improves* and primary is not *worse*; *matches* is recorded as
  unconfirmed. About 14 week-clusters, so the interval will be wide. With one season,
  `classify_verdict`'s "at most one season disagrees" clause is vacuous: *improves* reduces
  to an interval entirely below 0.
- **Interim runs** are labeled `"look": "interim"`, carry no verdict, and change nothing. The
  first ran on 2026-09-23 over weeks 1–3 (106 early games, no primary games yet); its file
  is in `data/processed/ratings/`.
- The 2026 result gets its own dated doc at the final look.

## What this changes downstream

- The robustness failure on 2021–2025 (carryover ×1.5) is consistent with this curve, which
  also rises past $k=1$. The curve gives no reason to shrink the carryover below its fitted
  value, but for the reason above it is weak evidence either way.
- `ridge_v1` stays the base rating until 2026 says otherwise.

## What this does not support

- **Not a confirmation.** It picks a candidate on pre-2021 data; confirmation is 2026's job.
- **Not a reason to read ×0.5 off 2021–2025**, nor proof that $k=1$ is right: pre-2021
  tuning lands on the full carryover, partly by construction.
- **No betting value.** Forecast error against an untimed, unpriced vendor label.
