# Prediction Tracker model evaluation and ensemble — results

Implements `docs/prediction-tracker-model-eval-plan.md`, which was written and committed
**before** anything was fit. Reproduce with `python scripts/eval_prediction_tracker_models.py`.

17,731 games, 2001–2025. 154 model columns, 113 with ≥200 clean-coverage games, **80 with
≥3 seasons** (below that a season-clustered bootstrap is degenerate and no inference is
reported). Walk-forward evaluation 2006–2025; weights for season *t* see only seasons < *t*.
All inference is a wild cluster bootstrap at season level (25 clusters).

---

## Headline

**No computer model beats the closing line, and neither does any combination of all 154 of
them.** The best single model, `lineca`, is statistically tied with the market
(ΔMSE +0.197, BH q = 0.066). The pre-registered ensemble is also tied (ΔMSE −0.191,
95% CI [−0.605, +0.246], p = 0.36).

This is a **tight null, not an underpowered one.** The CI rules out any improvement larger
than 0.656 MSE — about **0.021 RMSE**, a 0.13% gain — against a design that could have
detected 0.078 RMSE at 80% power.

**Where the models do add value: against a stale line.** Every result flips when the
benchmark is the opening number instead of the closing one. The market's own move from open
to close is what absorbs the models' information.

| | vs **opening** line | vs **closing** line |
|---|---|---|
| Benchmark RMSE | 15.770 | 15.617 |
| Models beating it (BH q<0.05) | **1** — `lineca` | **0** |
| Ensemble ΔMSE | **−2.64** [−4.33, −0.83], p<0.001 | −0.19 [−0.61, +0.25], p=0.36 |
| Weight the fit puts on the model consensus | **0.53 – 0.64** | 0.18 – 0.23 |

---

## 1. Which models are best

Ranked by paired ΔMSE against the closing line on the model's own games — **never by raw
RMSE**. Raw RMSE is not comparable across models because they cover different game sets:
`linegrinder` has the single best raw RMSE in the file (15.22 vs the market's 15.62) and
still *loses* to the market by 5.08 MSE on the games it actually covers. It drew easier
games. That confound is the reason every number below is paired.

Filtered to ≥3,000 games and ≥3 seasons. Negative ΔMSE = beats the line.

| Model | n | Seasons | RMSE | Volatility | ΔMSE vs close | q | ΔMSE vs open | q |
|---|---|---|---|---|---|---|---|---|
| **lineca** | 15,007 | 21 | 15.545 | 15.543 | **+0.197** | 0.066 | **−5.089** | 0.000 |
| **linemidweek** | 9,736 | 13 | 15.704 | 15.702 | +2.048 | 0.000 | **−2.640** | 0.114 |
| lineespn | 6,699 | 9 | 15.925 | 15.913 | +10.06 | 0.000 | +4.88 | 0.070 |
| lineteamrank | 7,551 | 10 | 16.003 | 15.999 | +11.27 | 0.000 | +6.27 | 0.009 |
| lineatom | 9,595 | 13 | 15.999 | 15.999 | +11.40 | 0.000 | +6.28 | 0.000 |
| linedokter | 14,347 | 20 | 15.920 | 15.911 | +11.55 | 0.000 | +6.19 | 0.000 |
| linepimean | 9,763 | 13 | 16.070 | 16.066 | +13.44 | 0.000 | +8.79 | 0.000 |
| lineash | 11,182 | 16 | 16.059 | 16.059 | +14.09 | 0.000 | +9.08 | 0.000 |
| linepig | 15,671 | 22 | 16.075 | 16.075 | +14.25 | 0.000 | +9.72 | 0.000 |
| linesag *(Sagarin)* | 17,709 | 25 | 16.295 | 16.295 | +21.66 | 0.000 | +15.82 | 0.000 |

Worst of the well-covered models: `linesportrends` (+100.2), `linesuper` (+97.4),
`lineloud` (+92.4), `lineclean` (+82.8) — RMSE 18.1–18.5 against a market at 15.6. These
are not marginal; including them is what sinks naive averaging (§3).

**`lineca` is the standout.** 21 seasons, 15,007 games, the only model that ties the closing
line and the only one that clearly beats the opening line. `linemidweek` is second on both.

### Accuracy and volatility are the same ranking

You asked for most accurate *and* least volatile. Empirically they are one question here:
Spearman correlation between the RMSE ranking and the volatility ranking is **0.9994**.

The reason is that these models are essentially unbiased — median |bias| across models is
0.34 points, max 3.98. With bias near zero, `volatility = √(MSE − bias²) ≈ RMSE`. There is
no model in this file that is accurate-but-erratic or steady-but-wrong; a model's mean error
tells you almost nothing its error spread doesn't.

*(Volatility is pre-committed as error SD with the model's own bias removed. Fixed in the
plan before fitting, precisely so that a model winning on one dispersion measure and losing
on another couldn't be chosen after the fact.)*

### Skill persists across seasons

Mean Spearman correlation of model skill rank between consecutive seasons: **0.775** over 24
season pairs (range 0.19–0.96). Last year's good models are usually this year's — which is
what makes the walk-forward screen in §3 work at all.

---

## 2. The market benchmark, and why the timing matters

| Forecast | RMSE | MAE | Bias |
|---|---|---|---|
| Closing line | **15.617** | 12.312 | −0.10 |
| Opening line | 15.770 | 12.425 | −0.06 |
| PT's own `lineavg` (mean of all models) | 15.953 | 12.605 | +0.06 |

Prediction Tracker publishes model forecasts mid-week. Scoring them only against the closing
line charges them for information that did not exist when they were published — that is a
statement about staleness, not model quality. Both benchmarks are reported throughout for
that reason, and they answer different questions:

- **Opening line** → *did the modeler add information available at publication time?* Yes,
  for `lineca` and the ensemble.
- **Closing line** → *can this beat the number you can actually bet?* No, for everything.

---

## 3. The ensemble

Five combination rules, all fit walk-forward, all scored on the **same 12,803 games**
(common support — scoring each on its own subsample would reproduce exactly the coverage
confound from §1).

| | Rule | RMSE | ΔMSE vs close | 95% CI | p |
|---|---|---|---|---|---|
| — | **closing line** | **15.5010** | — | — | — |
| E1 | mean of all available models | 15.7990 | +9.33 | [+8.03, +10.60] | <0.001 |
| E2 | median of available models | 15.7632 | +8.20 | [+7.04, +9.31] | <0.001 |
| E3 | mean of top-20 by prior skill | 15.6244 | +3.84 | [+2.60, +5.03] | <0.001 |
| **E4** | **market + 2-param consensus tilt** | **15.4948** | **−0.19** | **[−0.61, +0.25]** | **0.36** |
| E5 | ridge on the season's active set | 15.5051 | +0.13 | [−0.49, +0.77] | 0.67 |

The forecast-combination puzzle holds hard here. Averaging everything is **9.3 MSE worse**
than just reading the line, because the bad tail is genuinely bad. Screening to the top 20
recovers most of that but still loses. Only the deliberately 2-parameter E4 reaches parity,
and ridge over the full active set does no better than E4 despite far more freedom.

### The fitted model

E4, refit each season on all prior seasons, in margin space (`margin = −spread`):

```
predicted_margin = β₀ + β₁ · market_margin + β₂ · (consensus_margin − market_margin)
```

| Benchmark | β₀ | β₁ (market) | β₂ (consensus tilt) |
|---|---|---|---|
| vs closing (2023–25) | −0.30 … −0.46 | 1.022 … 1.024 | **0.18 … 0.23** |
| vs opening (2023–25) | −0.24 … −0.47 | 1.018 … 1.021 | **0.53 … 0.64** |

The coefficients are stable and they say something clean: **against the opening line, put
about 55% weight on where the model consensus disagrees with the market; against the closing
line, about 20% — and even that 20% does not pay.** β₁ ≈ 1.02 means a mild extrapolation of
the market number itself.

The screened top-20 is stable year to year, led by: `lineca`, `linemidweek`, `lineespn`,
`lineteamrank`, `linedokter`, `linepimean`, `linepibias`, `linepiratings`.

### Is the signal real, or just not usable?

E4 nests its benchmark, so the plan pre-specified **Clark-West** as the primary test. CW and
the plain paired difference disagree, and the disagreement is the finding:

| Test | Result | What it means |
|---|---|---|
| Clark-West | +0.596, CI [+0.186, +1.033], one-sided **p = 0.004** | The consensus tilt carries **real population signal** beyond the closing line. |
| Paired ΔMSE | −0.191, CI [−0.605, +0.246], **p = 0.36** | That signal **does not survive the cost of estimating it.** |

Both are correct. Clark-West asks whether the extra terms have predictive content; the
paired difference asks whether the bigger model actually forecasts better once you pay to
estimate those terms out-of-sample. Deployment hinges on the second. The models know
something the closing line doesn't — just not enough to overcome the noise in learning how
much to trust them.

### Decision value: it never pays

Betting E4's disagreements with the closing line at −110 (break-even 52.38%):

| Filter | Bets | Hit rate | ROI |
|---|---|---|---|
| any edge | 14,080 | 50.40% | −3.8% |
| \|edge\| > 1 | 1,543 | 51.20% | −2.3% |

Not close, at any threshold. A squared-error gain that never flips a profitable bet is not
deployable, and the plan said so before the number was computed.

---

## 4. Exploratory (post-hoc — excluded from the gate by the plan)

| Cut | Result | Verdict |
|---|---|---|
| Weeks 12–15 | ΔMSE −0.842, p = 0.020 | 1 of 5 week buckets tested → BH q = 0.10. **Not significant.** |
| Model-disagreement quartiles | nothing below p = 0.06 | No exploitable dispersion signal. |
| Sensitivity to K (pre-registered at 20) | K=5 +0.13, K=10 −0.01, **K=20 −0.20**, K=40 −0.08, K=80 +0.01 | **The pre-registered K landed on the single most favourable value.** The effect vanishes at every other K. |

That last row matters more than the other two. E4's small negative ΔMSE is not robust to a
parameter that was fixed arbitrarily in advance — which is evidence *for* the null, not
against it. Had K not been pre-registered, K=20 is exactly the value a search would have
selected and then reported as a finding.

---

## 5. What to actually use

- **If you have the closing line, use the closing line.** Nothing here improves on it, and
  the CI is tight enough to say that rather than merely fail to reject it.
- **If you are forecasting before close** — grading an opener, setting a midweek number,
  reacting to a stale book — the ensemble is worth a real 2.6 MSE
  (RMSE 15.770 → 15.636), and `lineca` alone is worth 5.1 MSE.
- **If you want one model rather than a blend,** `lineca` is the only defensible pick.
- **Do not average all the models.** It is 9.3 MSE worse than doing nothing.

Outputs under `{CFB_DATA_ROOT}/processed/`: `pt_leaderboard_{opening,closing}.csv`,
`pt_ensemble_spread_{opening,closing}.csv` (per-game ensemble spread and its edge vs the
market), `pt_e4_weights_{opening,closing}.csv`, `pt_model_eval.json`.

## 6. Limitations

- **Survivorship.** Models that stopped publishing may have been dropped for being bad. Skill
  is estimated only over the seasons a model was active, with no forward-fill, but the
  population of models is itself selected. Not fixable in-sample.
- **Game-selective missingness.** 111 model-seasons cover 30–75% of games while appearing
  across most weeks — they skip games rather than joining late, and a model that skips games
  it is unsure about looks better than it is. The leaderboard is restricted to the 997
  model-seasons at ≥95% within-season coverage to remove this; the unrestricted version is in
  the CSVs and is not to be used for ranking.
- **33 of 113 models have fewer than 3 seasons** and carry no inference at all. Several sit
  near the top of the raw ordering (`linesprs3`, `linefpi`, `linethocal`) — those placements
  are noise, and are reported with blank CIs rather than a rank.
- **The market benchmark is Prediction Tracker's own recorded line,** not an independently
  sourced closing price, and its exact capture time is undocumented upstream.
