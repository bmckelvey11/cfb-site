# Research prompt — forecast combination methods

For Perplexity (or any deep-research tool). Grounded in the measured results in
`docs/prediction-tracker-model-eval.md` so the answer engages with our actual regime
rather than returning a generic combination-methods listicle.

Paste everything below the line.

---

I am combining a large panel of competing point forecasts and need to know which
combination methods are worth trying given a specific diagnostic result. Please answer with
named methods, primary citations, and a judgement on applicability to my setup — not a
general survey.

## Setup

- **Target**: the final margin of a college football game (continuous, roughly N(4.6, 21)).
- **Forecasters**: 154 independent published models, each emitting a point spread. 17,731
  games over 25 seasons (2001–2025).
- **Panel is unbalanced by design.** Missingness is *season-level*, not game-level: a model
  either publishes in a given season (and then covers ~all its games) or does not. Coverage
  ranges from 1 to 25 seasons; a median game has 48 of the 154 models present. Models enter
  and exit continuously.
- **Benchmark**: the betting market's closing spread, RMSE 15.617. This benchmark beats
  every one of the 154 individual models. The best single model ties it (ΔMSE +0.197,
  BH q = 0.066); all others lose, some catastrophically (RMSE up to 18.5).
- Forecasters are **near-unbiased** (median |bias| 0.34 points) and **highly correlated**
  with each other and with the benchmark.
- Individual forecaster skill is **persistent**: Spearman rank correlation of skill across
  consecutive seasons is 0.775.
- All evaluation is walk-forward (weights for season *t* fit only on seasons < *t*), with
  inference by wild cluster bootstrap at the season level.

## What I have already measured

Common support, 12,803 games, ΔMSE vs the closing line (negative = better):

| Method | RMSE | ΔMSE | 95% CI |
|---|---|---|---|
| Closing line (benchmark) | 15.5010 | — | — |
| Equal-weight mean of all available | 15.7990 | **+9.33** | [+8.02, +10.53] |
| Median of all available | 15.7632 | +8.20 | [+6.96, +9.39] |
| Equal-weight mean of top 20 by prior-season skill | 15.6244 | +3.84 | [+2.62, +4.98] |
| Recalibration only (`β₀ + β₁·market`, no models) | 15.5028 | +0.06 | [−0.18, +0.33] |
| `β₀ + β₁·market + β₂·(top-20 consensus − market)` | 15.4948 | −0.19 | [−0.60, +0.25] |
| Ridge on the season's active model set + market | 15.5051 | +0.13 | [−0.50, +0.76] |

## The diagnostic that defines my regime

Three findings that should constrain your answer:

1. **Clark-West rejects, the paired difference does not.** Against the recalibrated
   benchmark, Clark-West gives +0.451, one-sided p = 0.0005 — the extra term carries genuine
   population signal. The plain paired ΔMSE is −0.248 [−0.517, +0.002], p = 0.063. So the
   information is real but **does not survive the cost of estimating how much to weight it
   out-of-sample.**
2. **Extra flexibility buys nothing.** Ridge over 60+ active forecasters performs no better
   than a two-free-parameter fit. This looks signal-limited, not specification-limited.
3. **Naive equal weighting is catastrophically bad here** (+9.33 MSE), because the panel has
   a genuinely poor tail — the opposite of the usual forecast-combination-puzzle result where
   simple averages win.

## What I want to know

1. **Which combination methods are specifically designed for the "signal exists but
   estimation variance destroys it" regime?** I am aware of shrinkage toward equal weights
   and of Diebold & Shin's partially-egalitarian LASSO; what else, and what is the current
   state of the art? Please distinguish methods that shrink toward *equal weights* from ones
   that shrink toward a *strong external benchmark* (my case — the market is not one of the
   forecasters, it dominates all of them).
2. **Complete subset regressions** (Elliott, Gargano & Timmermann) — does the evidence
   support them over ridge/LASSO when predictors are many, highly correlated, and
   individually weak? What subset size does the literature suggest at k ≈ 60?
3. **Handling an unbalanced panel with entry/exit** without imputing a missing forecaster
   from its co-forecasters in the same row (which launders the consensus into every
   coefficient). What do factor-model or EM-based approaches offer, and do they actually beat
   per-period refitting on the active set?
4. **Dimension reduction before weighting** — principal components / factor extraction from
   the forecast panel, sometimes called factor-augmented forecast combination. Does it help
   when the forecasts are as correlated as mine, or does the first PC simply reproduce the
   consensus I already tested?
5. **Online / regret-minimising aggregation** (exponentially weighted average forecaster,
   Hedge, online gradient descent, Vovk's aggregating algorithm). These have worst-case
   regret guarantees rather than distributional assumptions. Is there empirical evidence they
   beat batch shrinkage on financial or sports forecast panels, and do the guarantees mean
   anything at my sample size?
6. **Forecast encompassing.** Is there a principled test for "the benchmark encompasses the
   whole panel" that is more informative than my pairwise Clark-West, and what is the right
   multiple-forecaster version?
7. **Robust / trimmed combination.** Given my bad tail, what does the literature say about
   trimmed means, winsorisation, or median-of-means versus explicit skill screening? Is there
   a principled way to choose the trim fraction rather than my arbitrary top-20?
8. **The market-as-benchmark literature specifically.** For settings where a betting or
   prediction market is the benchmark, what is the evidence on whether expert/statistical
   model panels contain information the market has not already priced? Please cite empirical
   work rather than theory.

## What I explicitly do not want

- Generic introductions to ensembling, bagging, boosting, or stacking unless you can argue
  they address finding (2) above — that extra flexibility bought nothing.
- Recommendations that require game-level features beyond the forecasts themselves. The
  question is purely about *combining these point forecasts*.
- Methods that need a balanced panel.

## Output format

For each method: the name, a one-line description of the estimator, the primary citation
(author, year, venue), the specific failure mode it addresses, and a one-line verdict on
whether my three diagnostics make it promising or a waste of time. Finish with a ranked
shortlist of at most five worth implementing, most promising first, and say what single
diagnostic would tell me early that a given one is not going to work.

Prefer peer-reviewed econometrics and forecasting sources (*International Journal of
Forecasting*, *Journal of Econometrics*, *Journal of Applied Econometrics*, *Journal of
Business & Economic Statistics*) and well-known working papers. Note explicitly where the
evidence is thin or contested.
