# PFF team stats against total line movement, 2026-09-22

Reproduce: `python research/totals/scripts/pff_line_movement.py --out research/totals/docs`.

## Question

Do the five PFF team features registered on 2026-09-22 predict how the market moves a
total between open and close? A bet-free test: it accrues on every game with a price,
not only on graded picks, which is what makes it answerable where the win/loss version
was not.

**Why this sits in `research/totals/` and not `models/totals/`.** It was run as the
line-movement half of open question D, and the flag half — do the features behave
differently on Greenline's board — turned out to be unidentified here, for a reason worth
recording in this unit. The surviving result is feature screening with no harness behind it,
so anything that *builds* on it belongs in `models/totals/`; this record does not.

## Data

- 956 FBS games with an open, a close, and PFF features for both teams (693 in 2025, 263 in 2026), on 84 slate days.
- Outcome: close minus open, averaged across providers carrying both. SD 1.91 points.
- Provider disagreement inside a game is 0.90 points (mean within-game SD) against a
  1.95-point between-game SD, so roughly a tenth of the outcome's variance is provider
  timing. That widens the intervals below; it does not bias the coefficients.
- Pre-run MDE, from `power_calc.py --sd 1.95 --cluster-size 13 --icc 0.05`: 0.18 points
  per SD of feature at n=1,444, 0.22 at n=1,000.

## Coefficients

OLS, `move ~ features + total_open + season-week FE`, SEs clustered on slate date.
Holm corrects across the five features. The `week-cluster` column re-runs the same fit
clustering on season-week instead, because teams repeat across dates and the features
are team attributes; where the two disagree the wider one counts.

A feature is the mean of two teams' z-scores, so its own SD is about 0.73, not 1 — `b`
is per unit of that mean and `b per SD` rescales it to the sample spread. Positive means
the market moves the total **up**; the under side is negative.

| feature | b | SE | b per SD | p | Holm p | SE, week-cluster |
|---|---:|---:|---:|---:|---:|---:|
| pass_rush | -0.007 | 0.084 | -0.005 | 0.935 | 0.935 | 0.084 |
| run_heavy | +0.117 | 0.101 | +0.082 | 0.246 | 0.492 | 0.103 |
| no_deep | +0.141 | 0.079 | +0.100 | 0.074 | 0.221 | 0.078 |
| weak_qb | +0.340 | 0.099 | +0.255 | 0.001 | 0.003 | 0.095 |
| coverage | -0.213 | 0.097 | -0.152 | 0.027 | 0.109 | 0.084 |

## Season stability

Required by [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)
(Tier 1, fold and season stability). The same fit, each season alone.

| feature | 2025 (n=693) | 2026 (n=263) |
|---|---:|---:|
| pass_rush | -0.103 ± 0.103 | +0.302 ± 0.078 |
| run_heavy | +0.043 ± 0.115 | +0.437 ± 0.176 |
| no_deep | +0.168 ± 0.089 | +0.036 ± 0.150 |
| weak_qb | +0.345 ± 0.134 | +0.310 ± 0.104 |
| coverage | -0.256 ± 0.121 | -0.086 ± 0.131 |

`total_open` -0.0609 ± 0.0125 per point of opening total.

## The flag interaction

**Not estimable: there are no unflagged controls in this sample.** All 103 of the 103 games in 2026 weeks 2-3 that carry an open, a close and PFF features for both
teams are on the Greenline board, so the dummy has no within-week variation.

This is not because the board covers everything — it does not. It graded 49 of the 120
priced week-2 games and 57 of 119 in week 3. The unflagged remainder are games this
analysis cannot use at all: PFF's facet pull is FBS-only, so a game against a non-FBS
opponent has no team features and never enters the sample. Among the FBS games that do
enter, board coverage is effectively total. The 2026 week-4 rows read as unflagged only
because grading has not landed for that week; they are not a control group and were not
used as one.

So a flag interaction needs a different contrast than flagged-vs-unflagged. The variable
that would discriminate is membership of the published under list, or a cut on PFF's
stated `value` — a different regressor from the one registered here, named as the next
test rather than swapped in and run on this sample.

## Out of sample

Fit on 2025, tested on 2026. Controls-only R² +0.0066; with the five features +0.0072 (change +0.0006). Correlation between prediction and
actual move rises +0.085 → +0.115.
R² understates here because the predictions are deliberately flat: an effect of a quarter
point against a two-point outcome cannot explain much variance and is not supposed to.
Descriptive only — it was not the decision statistic, and 2026 features come from the
completed 2025 season by the fallback rule, so the folds share a season.

## Reading

- **`weak_qb` survives Holm** (+0.340 ± 0.099, Holm p 0.003); +0.255 points per SD, which at the
  unit's standing half-point-is-two-points figure is about 1.0pp of win probability per SD.
  Same sign both seasons (+0.345 in 2025, +0.310 in 2026) and the
  week-clustered SE does not widen it, which is what a real association should look like.
- Small, though. This is a nudge on the closing number, not a filter that picks games.

## What this does not support

- Any causal reading. These are conditional associations on observational data.
- Extending to 2020 or 2022-23, which carry no PFF data.
- A sixth feature or a second specification on this sample. The budget was seven looks.
- A claim about Greenline. The flag term is unidentified here, so nothing above says whether
  PFF's picks are good — only that its team grades track where the number goes.
- A proper score against a same-time de-vigged market, which
  [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md) makes Tier 1.
  The benchmark used is the opening number, not a de-vigged price, so this measures
  incremental movement prediction and not forecast skill against the market's own probability.
- Anything resting on a final untouched holdout: there isn't one. The 2025→2026 split is the
  only out-of-sample evidence and its folds share a season through the feature fallback.

