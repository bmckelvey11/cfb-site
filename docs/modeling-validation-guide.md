# Sports Betting Modeling, Validation, and Data-Audit Guide

## Conversation summary

This document consolidates the discussion on selecting regression and machine-learning models for sports betting prediction and betting-market edge estimation; using walk-forward validation to prevent look-ahead bias; and auditing data, odds, modeling, calibration, and execution pipelines.

The central conclusion is that a successful betting research system depends less on selecting a universally superior algorithm and more on:

1. A target formulation aligned with the actual betting market.
2. Strict timestamp-aware data construction.
3. Walk-forward, out-of-sample model development and evaluation.
4. Probability or distribution calibration.
5. Market-relative evaluation using no-vig prices and closing-line value.
6. Execution-realistic backtesting.
7. Reproducible, testable data lineage and model versioning.

---

# 1. Regression and ML models for betting prediction

## 1.1 No universal model winner

No regression or machine-learning model is universally best for sports betting. Sports markets are noisy, non-stationary, competitive, and constrained by limited sample sizes. A strong practical system typically combines:

- A structural baseline, such as regularized regression, generalized additive modeling, or Bayesian hierarchical regression.
- A market baseline based on contemporaneously available no-vig implied probabilities.
- A nonlinear challenger, commonly gradient boosting.
- A time-safe blending and calibration layer.
- A conservative decision layer that accounts for vig, uncertainty, execution risk, and model error.

For conventional spreads and totals, the desired output is not just an expected margin or expected total. The useful object is a **predictive distribution**, or at minimum relevant conditional quantiles and line-specific probabilities. A model can have good RMSE yet make poor spread/total betting decisions if it estimates means well but misstates tails, variance, skewness, or push probabilities.

For a binary market, such as a moneyline or yes/no proposition, the useful output is a calibrated probability. A model with the highest classification accuracy is not necessarily the best betting model; a slightly less accurate classifier can be more valuable if its probability estimates are better calibrated where the offered price differs from its fair probability.

## 1.2 Regularized linear regression

### Suitable models

- Ridge regression.
- Lasso regression.
- Elastic net regression.
- Logistic regression for binary outcomes.
- Multinomial logistic regression for three-way outcomes.
- Poisson, negative-binomial, ordinal, or distributional generalized linear models for scores and counts.

### Strengths

- High stability with correlated features.
- Lower variance than highly flexible models.
- Easy to retrain in walk-forward settings.
- Often competitive when feature count is moderate and data are limited.
- More interpretable than tree ensembles or neural networks.
- Coefficients can be monitored for drift and can be regularized aggressively.
- Often a solid probability baseline when paired with correct target/link function and calibration checks.

### Weaknesses

- Nonlinearities and interactions must be engineered or modeled explicitly.
- Ordinary least squares optimizes conditional means; this can be misaligned with a spread/total wagering decision requiring tail probabilities or relevant quantiles.
- Misspecification can be consequential if relationships are strongly nonlinear or regime dependent.

### Practical role

Regularized regression should generally be the first production-grade baseline. It is especially attractive for small and medium datasets, sparse player/team histories, and market-residual models. A boosted-tree or neural model should have to demonstrate a durable, chronologically out-of-sample improvement over this benchmark.

## 1.3 Generalized additive models

A generalized additive model (GAM) extends a generalized linear model by replacing selected linear terms with smooth functions. In betting applications, GAMs can model smooth nonlinear effects while retaining substantially more transparency than fully unconstrained tree ensembles.

### Good use cases

- Rest days and schedule density.
- Travel distance and time-zone changes.
- Weather variables.
- Market probability or market residual effects.
- Rating differences.
- Course fit, course history, tee-time/weather interactions, and form effects in golf.
- Age, workload, minutes, expected playing time, and injury-return progression.

### Strengths

- Captures smooth nonlinear patterns without forcing arbitrary bins.
- Produces interpretable partial-effect curves.
- Usually has lower overfitting risk than high-capacity tree or neural models.
- Can be combined with a distributional likelihood and/or hierarchical structure.

### Weaknesses

- Requires thoughtful basis dimension, smoothing, and interaction design.
- Does not automatically discover arbitrary high-order interactions as readily as boosting.
- Complex categorical/entity effects may be better handled with random effects or Bayesian partial pooling.

### Practical role

Use a GAM when domain knowledge suggests that the relationship is nonlinear but smooth. It is often an excellent bridge between regularized linear models and gradient boosting.

## 1.4 Random forests

Random forests average predictions across many decorrelated decision trees.

### Strengths

- Minimal preprocessing requirements.
- Captures nonlinear effects and interactions.
- Robust to some outliers and monotonic transformations.
- Useful exploratory benchmark.

### Weaknesses

- Can be less sharp than gradient boosting on structured tabular data.
- Averaging tree-level probability estimates often pulls probabilities away from 0 and 1, which can create characteristic underconfidence and poor calibration.
- Large forests can conceal instability or feature leakage rather than diagnose it.
- Probability outputs commonly require post-hoc calibration.

### Practical role

Use random forests as a robust nonlinear baseline or exploratory model, but do not assume they are the first choice for price-sensitive probability estimation. They should be evaluated on probability calibration, log loss, and market-relative performance—not just classification accuracy.

## 1.5 Gradient boosting: XGBoost, LightGBM, and CatBoost

Gradient-boosted decision trees iteratively fit trees to residual errors. They are often the strongest flexible models for structured tabular data when trained and validated correctly.

### Strengths

- Captures nonlinearities, thresholds, and interactions.
- Strong performance on medium and large tabular datasets.
- Can accommodate large feature sets and many engineered covariates.
- Supports regression, classification, count objectives, quantile objectives, and custom losses.
- CatBoost is particularly convenient for categorical variables and can reduce preprocessing burden.
- LightGBM is often efficient at larger scale.
- XGBoost provides mature regularization and objective flexibility.

### Weaknesses

- High risk of backtest overfitting through hyperparameter search, temporal leakage, and feature mining.
- Raw probability estimates may be miscalibrated, particularly in rare-event or class-imbalanced markets.
- Model behavior can change materially with small data revisions, sparse segments, or regime shifts.
- Feature importance alone is not a causal interpretation and is not a leakage audit.

### Practical role

Use CatBoost, LightGBM, or XGBoost as the primary nonlinear challenger after establishing linear/GAM/hierarchical baselines. Demand improvement in properly time-split log loss, Brier score, reliability, and market-relative utility. Do not promote a boosted model solely because it has the best historical ROI after many feature and threshold searches.

## 1.6 Bayesian hierarchical regression

Bayesian hierarchical models explicitly represent shared structure across teams, players, coaches, venues, courses, seasons, and other repeated entities. They are particularly useful when individual entity sample sizes are small or noisy.

### Typical structure

A hierarchy can shrink team, player, or course effects toward a population-level mean:

$$
\theta_j \sim \mathcal{N}(\mu_\theta, \sigma_\theta^2)
$$

where $\theta_j$ is an entity-level effect and $\sigma_\theta$ controls the degree of pooling. Sparse entities receive stronger shrinkage; well-observed entities can deviate more from the population mean.

### Strengths

- Partial pooling reduces overreaction to noisy small samples.
- Natural uncertainty quantification through posterior distributions.
- Supports coherent distributional score/margin models.
- Can incorporate domain structure, changing player/team strength, home-field effects, course effects, and historical priors.
- Particularly suitable for sparse player props, team strength models, tournament sports, and entity-heavy problems.

### Weaknesses

- More demanding to specify, diagnose, and compute.
- Poorly chosen priors or hierarchy can induce rigidity or bias.
- Flexible Bayesian models still need strict temporal validation and can still leak.
- Point prediction can sometimes trail well-tuned boosted trees on large, rich tabular datasets.

### Practical role

Bayesian hierarchical models are often the strongest **structural foundation** for sports betting systems where data are grouped and sparse. They are valuable not only for expected outcomes but also for uncertainty-aware pricing and variance-aware decision rules.

## 1.7 Neural networks

Neural networks are most appropriate when data volume is genuinely large or inputs contain structure not well expressed in a flat tabular feature matrix.

### Stronger use cases

- Play-by-play sequences.
- Player tracking/spatiotemporal data.
- High-frequency live state data.
- Text, video, images, audio, or other unstructured inputs.
- Very large entity-event datasets with learned embeddings.

### Weaknesses in ordinary betting tables

- High data requirement.
- Greater hyperparameter and architectural search burden.
- Potentially weak uncalibrated probabilities.
- Harder diagnosis of data leakage and feature dependence.
- Less interpretability and more operational complexity.
- Often does not beat boosting on modest game-level tabular data.

### Practical role

Do not use a neural network merely because it is more sophisticated. Use it only when it has an input-structure advantage and achieves a meaningful, stable walk-forward improvement over boosted-tree and regularized baselines.

---

# 2. Recommendations by data size

## Under approximately 2,000 independent events

Preferred approach:

- Regularized logistic/linear/Poisson/negative-binomial model.
- GAM for a small number of known nonlinear effects.
- Bayesian hierarchical model with informative but tested priors.
- Compact, domain-driven feature set.
- Conservative calibration, often sigmoid/Platt rather than highly flexible isotonic calibration.
- Market probability as a strong baseline and potentially a prior/input.

Avoid:

- Deep neural networks.
- Wide unconstrained boosting searches.
- Large feature sets relative to the effective sample size.
- Isotonic calibration on small calibration subsets.
- Selecting models based on a few apparent high-ROI segments.

## Approximately 2,000 to 20,000 independent events

Preferred approach:

- Elastic net/logistic or distributional regression baseline.
- GAM and/or Bayesian partial pooling for interpretable structure.
- Carefully constrained CatBoost, LightGBM, or XGBoost challenger.
- Time-safe blend using prior out-of-fold predictions only.
- Separate or rolling calibration protocol.

Key control:

- Hyperparameter search must occur inside chronological development folds.
- Measure both predictive quality and calibration; do not rely on raw ROI alone.

## Approximately 20,000 to 200,000 independent events

Preferred approach:

- Gradient boosting can become the leading tabular model family.
- Keep structural and market baselines active.
- Use nested walk-forward tuning.
- Use distributional, quantile, count, or custom objectives appropriate to target type.
- Generate and preserve an immutable out-of-fold prediction ledger.

Key control:

- Large row count does not necessarily mean large independent sample size. Multiple snapshots per event, correlated player observations, and repeated entity rows can inflate apparent sample size.

## More than approximately 200,000 events or high-frequency/sequential data

Preferred approach:

- Gradient boosting remains a difficult baseline to beat for tabular inputs.
- Consider neural networks when sequence, spatial, tracking, or text structure is available.
- Use robust out-of-time evaluation, calibration, and latency-aware backtesting.

Key control:

- The more complex the model and data feed, the more likely operational timing, revisions, and selection bias—not the model family—will dominate real-world performance.

---

# 3. Match the model to the target

## 3.1 Spread or margin markets

Define a signed margin, for example:

$$
M = \text{home score} - \text{away score}
$$

A spread bettor needs a probability at the actual offered line $s$:

$$
P(M > s)
$$

or, depending on side and settlement conventions, a distribution that accounts for pushes:

$$
P(M > s), \quad P(M = s), \quad P(M < s)
$$

Useful model families:

- Bayesian location-scale or Student-$t$ regression.
- Quantile regression.
- Distributional GAM.
- Quantile gradient boosting.
- Joint or score-based models from which margin distributions are derived.

Do not rely only on a mean-margin prediction. A mean is not sufficient to price tail probabilities and may be poorly aligned with the bet decision.

## 3.2 Total markets

For a total line $\tau$, the primary quantity is:

$$
P(T > \tau)
$$

or its complement, with explicit push treatment where relevant.

Useful models:

- Poisson or negative-binomial count models.
- Bivariate score models.
- Gaussian or Student-$t$ distributional models for high-scoring contexts.
- Quantile or distributional boosted models.
- Bayesian models with team offense/defense and pace components.

Model variance explicitly. Two models with identical expected total can give substantially different over/under probabilities if their predictive variances differ.

## 3.3 Score prediction

A joint score distribution is generally preferable to fitting independent point predictions for the two sides. Independence assumptions can misstate the variance and covariance relevant to spreads, totals, and moneylines.

Useful approaches:

- Hierarchical Poisson or negative-binomial score models.
- Bivariate Poisson models.
- Latent offense/defense models.
- Correlated distributional models.

Derive market probabilities from simulated or analytically computed score distributions.

## 3.4 Binary probabilities: moneylines and props

For a binary outcome $Y$:

$$
P(Y=1 \mid X)
$$

Useful models:

- Regularized logistic regression.
- Hierarchical logistic regression.
- GAM with logit link.
- Gradient boosting plus time-safe calibration.

Primary model-selection metrics should include log loss and calibration, not just classification accuracy.

## 3.5 Multiclass outcomes

For three-way markets, such as home/draw/away:

- Use coherent multinomial probabilities that sum to one.
- Consider score-distribution models where the draw mechanism is structural.
- Evaluate multiclass log loss, calibration, and the probability simplex behavior rather than only top-class accuracy.

---

# 4. Calibration and proper evaluation

## 4.1 Why calibration matters

Betting is fundamentally a comparison between a model’s estimated probability and a market price. A model that says 60% should be correct roughly 60% of the time across comparable forecast instances. If it is systematically overconfident or underconfident, edge estimates and Kelly-style stake sizing become distorted.

For binary probabilities, report:

- Log loss / cross-entropy.
- Brier score.
- Calibration intercept.
- Calibration slope.
- Reliability curves.
- Calibration by time period, odds band, favorite/underdog status, market type, and estimated-edge bucket.
- Performance in the bettable tail, not only across all rows.

For spreads/totals and distributional predictions, report:

- Negative log predictive density where appropriate.
- Continuous ranked probability score (CRPS), when available.
- Pinball/quantile loss near bet-relevant quantiles.
- Empirical predictive-interval coverage.
- Calibration of line-specific probabilities such as $P(M > s)$ or $P(T > \tau)$.

## 4.2 Calibration methods

### Sigmoid or Platt calibration

Fit a logistic mapping from raw model scores/probabilities to observed outcomes. It is relatively stable with limited calibration data and is often appropriate for modest sample sizes.

### Isotonic regression

Fits a flexible monotonic mapping. It can correct complex calibration shapes but can overfit when calibration data are limited. Use only when the calibration set is sufficiently large, representative, and strictly time-safe.

### Temperature scaling

Often useful for multiclass neural or boosted model logits. It applies a lower-dimensional smoothing adjustment and preserves ranking/top-class ordering under common formulations.

### Rolling calibration protocol

For every future block:

1. Generate raw base-model probability using only earlier training data.
2. Fit the calibration model using only earlier out-of-fold raw predictions and known outcomes.
3. Apply calibration prospectively to the current future block.
4. Persist both raw and calibrated probabilities.

Never calibrate on in-sample predictions or on the final evaluation period’s known outcomes.

## 4.3 Accuracy is insufficient

Accuracy ignores confidence and odds. A 52% win probability and a 90% win probability can receive the same accuracy treatment if both classifications are correct, while their betting implications differ dramatically.

Optimize the forecasting layer using proper scoring rules and calibration. Then evaluate a separately specified betting rule using contemporaneous offered prices, vig, limits, and realistic execution assumptions.

---

# 5. Walk-forward validation

## 5.1 Core rule

For a prediction made at time $t$:

$$
\texttt{feature\_available\_at} \leq t < \texttt{event\_start\_time} \leq \texttt{outcome\_finalized\_at}
$$

Every feature must have been truly observable by $t$. All outcomes and post-event information must occur after $t$.

Walk-forward validation is an out-of-sample method that recreates this sequence historically:

1. Fit a pipeline using only data available through a cutoff.
2. Predict the next unseen event/time block.
3. Persist the prediction before inspecting the result.
4. Advance the cutoff.
5. Repeat until reaching the end of development data.
6. Evaluate the concatenated out-of-fold prediction ledger.

## 5.2 Why random cross-validation fails

Random K-fold cross-validation can place later events in training and earlier events in testing. In sports data, that enables future ratings, post-event statistics, revised records, season effects, later team knowledge, or correlated observations to leak into earlier tests.

It can also split multiple snapshots of the same game, team, player, or tournament across train and test. This makes the test set artificially easy and inflates expected performance.

## 5.3 Expanding-window validation

Train on all eligible prior history, then test on the next block.

```text
Fold 1: train [start, T1] → test (T1, T2]
Fold 2: train [start, T2] → test (T2, T3]
Fold 3: train [start, T3] → test (T3, T4]
```

Use expanding windows when long-run data remain relevant and additional historical samples help estimate stable parameters.

## 5.4 Rolling-window validation

Train only on a fixed-length recent history, then test on the next block.

```text
Fold 1: train [T0, T1] → test (T1, T2]
Fold 2: train [T1, T2] → test (T2, T3]
Fold 3: train [T2, T3] → test (T3, T4]
```

Use rolling windows when older data are stale because of rule changes, roster construction changes, scoring-environment drift, market evolution, or altered data quality.

## 5.5 Test-block selection

The test block should reflect the production retraining and decision schedule.

Examples:

- One event at a time for strict online/prequential simulation.
- One day or slate at a time for daily betting systems.
- One week at a time for many team sports.
- One tournament at a time for pre-tournament golf modeling.
- One round at a time for golf round markets, with strict round-level information sets.

A larger block reduces retraining cost and can produce more stable estimates. A smaller block more closely simulates frequent retraining but can be computationally expensive and operationally fragile.

## 5.6 Final untouched holdout

Reserve the final chronological period before extensive tuning begins.

Example:

```text
Development and rolling model selection: 2017–2023
Final untouched holdout: 2024
Prospective shadow/live monitoring: 2025 onward
```

The final holdout is evaluated once after feature definitions, hyperparameters, calibration policy, threshold policy, and execution assumptions are frozen. If it is used to make changes, it becomes a development period and a newer untouched period is needed.

---

# 6. Purging and embargoing

## 6.1 When ordinary walk-forward is insufficient

A simple chronological split can still leak when training labels or feature windows overlap the test period.

Common examples:

- Predicting a line move over the next 24 hours.
- Predicting future return or value over an overlapping time horizon.
- Multiple in-play snapshots for one game sharing the same final outcome.
- Rolling feature windows that can cross the train/test boundary.
- Labels resolved after an extended event or settlement period.

## 6.2 Purging

Purge training observations whose label interval overlaps the test information period.

For a training row $i$, retain it only when:

$$
\texttt{label\_end}_i < \texttt{test\_start}
$$

For a forward-horizon target, `label_end` is not necessarily event end; it may be observation time plus the label horizon.

## 6.3 Embargo

An embargo adds a time buffer between train and test to reduce dependence from nearby observations.

$$
\texttt{label\_end}_i < \texttt{test\_start} - \texttt{embargo}
$$

Use an embargo when short-term correlation, shared events, data-feed latency, or adjacent-window dependence can contaminate validation.

## 6.4 `TimeSeriesSplit` implementation notes

For equally spaced observations, `TimeSeriesSplit` can provide an expanding-window structure. Important settings include:

- `test_size`: number of observations in the future test block.
- `max_train_size`: limits training history and creates a rolling-window behavior.
- `gap`: excludes the observations immediately before the test block.

A split object cannot by itself prove that source data were available at the correct time. The input dataset must already satisfy as-of timestamp constraints.

---

# 7. Leakage prevention

## 7.1 Main leakage types

### As-of leakage

Using information that was published or became observable after the model’s claimed prediction time.

Examples:

- A late lineup in a morning betting model.
- An updated injury designation released after a simulated bet.
- Weather observations/forecasts refreshed later in the day.
- A live or closing market price in an opening-line model.

### Rolling-statistic leakage

A current event contributes to its own feature.

Example failure:

```python
season_avg = df.groupby("team")["points"].expanding().mean()
```

If the feature is used on the same row, the current game’s final points are included. Shift the aggregate before joining it to the current prediction row.

### Target-encoding leakage

An entity/category average uses outcomes from the test period or future observations.

All encoders must be fitted on training history only, preferably with cross-fitting or ordered/chronological encoding during development.

### Preprocessing leakage

Imputation, scaling, PCA, outlier clipping, feature selection, and representation learning are fitted on the entire dataset before splitting.

Every learned transformation must be fitted inside each training fold.

### Hyperparameter leakage

The analyst tunes models based on performance from a nominal test/final-holdout era. That era is no longer a test period.

### Calibration leakage

A calibrator is fitted using in-sample raw model predictions or known outcomes from a period supposedly being evaluated out of sample.

### Market-time leakage

Using a later odds snapshot as a feature or comparator for an earlier executable decision.

### Revision and survivorship leakage

Using final corrected historical data, current rosters, retrospective injury classifications, or complete records that were not available at the historical decision time.

## 7.2 Required data fields

Each prediction-level record should be traceable through these or equivalent fields:

```text
event_id
prediction_timestamp
bet_timestamp
event_start_time
feature_available_at
odds_timestamp
source_published_at
ingested_at
outcome_finalized_at
settlement_timestamp
record_revision_at
strategy_version
model_version
calibration_version
```

## 7.3 Safe as-of query rule

The data assembly layer should enforce a condition conceptually equivalent to:

```sql
WHERE feature_available_at <= prediction_timestamp
  AND odds_timestamp <= bet_timestamp
  AND event_start_time > prediction_timestamp
```

Use source publication time whenever possible. Ingestion time is not necessarily publication time; a source can be ingested late, and a provider can revise an old record after the fact.

---

# 8. Fold-safe pipeline design

Everything learned from data must be trained within each walk-forward training window.

## 8.1 Must be fit within training folds

- Imputation medians/modes/models.
- Scalers and normalization constants.
- Winsorization/clipping thresholds.
- PCA, embeddings, and dimensionality reduction.
- Feature selection.
- Target encoders.
- Category vocabularies.
- Team/player/course rating models.
- Hyperparameter selections.
- Base models.
- Blending/stacking models.
- Probability calibrators.
- Edge thresholds and other decision thresholds.

## 8.2 Pipeline rule

Fit transformations on training data, then apply unchanged to the next test block:

```text
fit(train) → transform(train) → train model
transform(test using train-fit transforms) → predict(test)
```

Never call `fit` or `fit_transform` on test data as part of historical evaluation.

## 8.3 Nested walk-forward tuning

Use nested temporal validation when selecting among model classes or tuning many parameters.

```text
Outer fold:
  Outer training period = all history before T
  Outer test period = next unseen block after T

Inside outer training period:
  Run inner walk-forward folds.
  Select hyperparameters/features/calibration configuration using inner metrics.

Then:
  Refit selected pipeline on the full outer training period.
  Predict outer test period once.
  Store immutable outer-test predictions.
```

Do not revisit the outer test result to alter the model. The final holdout must remain separate from both inner and outer development folds.

---

# 9. Market baseline, de-vigging, EV, and CLV

## 9.1 Market baseline

The contemporaneously available betting market is a powerful baseline. For each event and decision time, retain offered odds and calculate raw implied probability:

$$
p_i = \frac{1}{o_i}
$$

where $o_i$ is decimal odds.

Because sportsbook prices include margin, convert complete market snapshots into estimated no-vig probabilities using a documented de-vig method. Retain both raw and no-vig values.

A model should be evaluated against:

- The available market at the decision timestamp.
- A simple historical baseline.
- A regularized statistical baseline.
- Where relevant, the closing market as a post-decision benchmark.

## 9.2 Edge and expected value

For a binary bet with decimal odds $o$, model probability $p$, and unit stake, approximate expected profit is:

$$
EV = p(o - 1) - (1-p)
$$

The break-even probability is:

$$
p_{BE} = \frac{1}{o}
$$

For standard -110 odds, decimal odds are approximately 1.9091, yielding a no-push break-even probability of approximately 52.38%.

A small apparent edge should not automatically trigger a bet. It must exceed uncertainty from calibration error, feature instability, de-vig assumptions, price movement, latency, stake constraints, and execution limitations.

## 9.3 Closing-line value

CLV evaluates whether the price/line taken was better than an eventual closing market price.

Track:

- Price CLV: difference between wagered price and closing price, preferably on a no-vig implied-probability basis.
- Line CLV: improvement in point spread/total line relative to close.
- Model-to-close residual: model fair probability versus closing no-vig probability.
- Realized return after vig, settlement, and execution assumptions.

CLV is an important diagnostic but not proof of profitability. The closing market is informative and often efficient, but it can have biases, can react to information, and may not be a perfect fair-value label. Use it as a benchmark and monitoring tool, not as an earlier-timestamp feature.

---

# 10. Execution-realistic backtesting

A historical strategy should simulate what could actually have been placed.

## 10.1 Required execution assumptions

- Named sportsbook or explicitly defined executable line-shopping universe.
- Exact odds snapshot timestamp.
- Bet-placement latency.
- Market suspension/reopening behavior.
- Price movement/slippage assumption.
- Stake limits and liquidity constraints.
- Rejections, voids, unavailable markets, and stale prices.
- Market-specific settlement rules.
- Pushes, dead heats, each-way terms, partial payouts, overtime treatment, and cancellation rules.

## 10.2 Strategy rules must be fixed

Before final holdout evaluation, define:

- Minimum edge threshold.
- Staking method.
- Maximum bet size.
- Maximum exposure by event, team/player, market, slate, and correlated group.
- Book selection rule.
- Timing rule.
- Odds update/selection rule.
- Model blend and calibration policy.

Do not select edge thresholds, favorable odds bands, books, market subsets, or date ranges after viewing final out-of-sample ROI.

## 10.3 Report both prediction and betting metrics

Predictive quality:

- Log loss.
- Brier score.
- Calibration slope/intercept.
- Reliability curves.
- CRPS/negative log predictive density/quantile loss where applicable.

Betting quality:

- Number of bets.
- Stakes and turnover.
- Gross/net profit.
- ROI/yield.
- Average odds.
- CLV.
- Drawdown and drawdown duration.
- Return volatility.
- Fold-, season-, market-, book-, odds-band-, and edge-bucket-level results.

Short-sample ROI is highly variable. A robust edge should appear in chronologically separated blocks, survive reasonable execution assumptions, and produce sensible calibration and market-relative diagnostics.

---

# 11. Practical architecture

## 11.1 Recommended end-to-end workflow

1. **Define the decision contract.**
   - Specify sport, market, book universe, prediction time, bet time, execution assumptions, target, and settlement conventions.

2. **Build an as-of-valid dataset.**
   - Preserve event, feature, source-publication, odds, prediction, and outcome timestamps.
   - Enforce temporal joins.

3. **Create a market baseline.**
   - De-vig the contemporaneously available price.
   - Measure whether features/models add information beyond market consensus.

4. **Build a structural baseline.**
   - Use regularized regression, GAM, and/or Bayesian partial pooling.

5. **Build a nonlinear challenger.**
   - Train constrained CatBoost, LightGBM, or XGBoost on approved time-valid features and market/structural residual signals.

6. **Use nested walk-forward development.**
   - Tune only within prior time periods.
   - Generate immutable outer-fold predictions.

7. **Blend time-safely.**
   - Train a simple regularized meta-model only on prior out-of-fold predictions.

8. **Calibrate prospectively.**
   - Use historical out-of-fold predictions/outcomes that precede each test block.

9. **Apply fixed decision rules.**
   - Calculate no-vig market probability, fair model probability, EV, uncertainty, edge threshold, and stake size.

10. **Evaluate honestly.**
    - Track proper scoring, calibration, CLV, ROI, execution assumptions, and stability by chronological fold.

11. **Lock and evaluate final holdout.**
    - Do not alter the system based on final-holdout results without designating a new holdout.

12. **Deploy in shadow mode.**
    - Log exact real-time feature snapshots, odds quotes, model outputs, and hypothetical execution before using meaningful capital.

## 11.2 Recommended model stack by regime

### Small entity-heavy data

Use Bayesian hierarchical regression plus regularized GLM/GAM. Treat market information as a serious baseline/prior. Favor uncertainty-aware pricing and conservative decisions.

### Medium game-level tabular data

Use elastic net/GAM/Bayesian structural model as a baseline, plus calibrated CatBoost/LightGBM/XGBoost as nonlinear challenger. Blend only if the improvement persists across walk-forward folds.

### Large structured data

Use boosted trees as a leading candidate, but retain market/structural models, use distributional objectives where relevant, and calibrate prospectively.

### High-frequency sequential data

Use boosted trees for structured state features and consider neural sequence/spatiotemporal models only if they provide a meaningful information advantage and survive latency-aware, purged validation.

---

# 12. Data-audit checklist

## 12.1 Strategy and provenance

- [ ] Document the sport, league/tour, competition level, market, target, bookmaker universe, and execution window.
- [ ] Define prediction time, bet time, event start, label time, and settlement time.
- [ ] Specify data sources, vendor/API versions, extraction times, licenses, and revision behavior.
- [ ] Save raw source snapshots where possible.
- [ ] Version code, data, features, models, calibrators, thresholds, and staking rules.
- [ ] Record random seeds, package versions, database versions, and code commit hashes.
- [ ] Maintain a complete data dictionary.

## 12.2 Event data

- [ ] Enforce stable event IDs and canonical team/player identifiers.
- [ ] Reconcile duplicate events and source-specific aliases.
- [ ] Standardize home/away orientation and neutral-site labels.
- [ ] Preserve scheduled and actual start times where relevant.
- [ ] Encode cancellations, postponements, suspensions, voids, draws, pushes, dead heats, and settlement rules.
- [ ] Verify final results against trusted sources.

## 12.3 Odds data

- [ ] Store raw odds and normalized decimal odds.
- [ ] Store book, market, selection, line, timestamp, market status, and source.
- [ ] Validate line signs, favorite/underdog orientation, and selection mapping.
- [ ] Detect malformed, duplicate, stale, impossible, and post-start price records.
- [ ] Store exact executable prices, not only a best-of-market retrospective composite.
- [ ] De-vig complete market snapshots using a documented method.
- [ ] Keep opening, decision-time, and closing odds separate.

## 12.4 Feature availability

- [ ] Give every feature an availability timestamp or a documented conservative availability rule.
- [ ] Require `feature_available_at <= prediction_timestamp`.
- [ ] Shift rolling, cumulative, and expanding statistics.
- [ ] Update ratings only after event completion.
- [ ] Use publication time for injuries, lineups, weather, rankings, and news.
- [ ] Treat retrospective corrections as potentially unavailable unless historical snapshots can be reconstructed.
- [ ] Audit suspiciously powerful features for direct or indirect target leakage.

## 12.5 Joins and grain

- [ ] Define row grain and expected keys for every source table.
- [ ] Measure row counts before and after joins.
- [ ] Investigate all many-to-many joins.
- [ ] Use as-of joins for time-varying records.
- [ ] Verify unmatched records and entity mapping rates.
- [ ] Ensure one final model row per intended decision unless multiple snapshots are deliberately modeled.

## 12.6 Missingness and outliers

- [ ] Measure missingness across time, sources, books, markets, teams, and players.
- [ ] Fit imputers using training data only.
- [ ] Preserve missingness indicators where useful.
- [ ] Validate units, ranges, signs, and denominators.
- [ ] Fit clipping/winsorization thresholds on training data only.
- [ ] Preserve raw values separately from cleaned data.

## 12.7 Validation

- [ ] Use chronological walk-forward splits.
- [ ] Confirm every training timestamp precedes every test timestamp.
- [ ] Specify train window, test block, step, gap, and retraining cadence.
- [ ] Purge and embargo overlapping labels/information windows when needed.
- [ ] Maintain a final untouched chronological holdout.
- [ ] Report metrics by fold and time period.

## 12.8 Pipeline and model fitting

- [ ] Fit all preprocessing within training folds.
- [ ] Fit target encoders and category vocabularies using training data only.
- [ ] Conduct hyperparameter selection in nested chronological folds.
- [ ] Fit stacks/blends only from prior out-of-fold predictions.
- [ ] Persist out-of-fold predictions before joining outcomes.
- [ ] Use model and market baselines.

## 12.9 Calibration

- [ ] Fit calibration only using earlier out-of-fold predictions and outcomes.
- [ ] Track log loss, Brier score, reliability, slope, and intercept.
- [ ] Inspect calibration by market, time, odds band, and edge bucket.
- [ ] Assess distribution/quantile calibration for spreads and totals.

## 12.10 Backtest and risk

- [ ] Use contemporaneous executable prices.
- [ ] Incorporate settlement rules, vig, voids, pushes, odds movement, latency, limits, and liquidity.
- [ ] Freeze thresholds, staking, and exposure limits before final holdout evaluation.
- [ ] Report CLV and ROI separately.
- [ ] Report drawdowns, turnover, uncertainty, and sensitivity analysis.
- [ ] Evaluate robustness by season, book, market, edge bucket, and odds range.

---

# 13. Automated hard-fail tests

The following should generally fail a pipeline run rather than merely produce a warning:

- [ ] Duplicate primary keys at any declared table grain.
- [ ] Pre-event prediction timestamp on or after event start.
- [ ] Feature availability after prediction timestamp.
- [ ] Odds timestamp after simulated bet timestamp.
- [ ] Outcome finalized at or before prediction timestamp.
- [ ] A training row chronologically later than a test row in a walk-forward fold.
- [ ] Closing line included in feature list for an opening/early strategy.
- [ ] Target/outcome columns included in approved model features.
- [ ] Unexplained many-to-many join.
- [ ] Transformer/model/calibrator fitted outside the relevant training period.
- [ ] Missing mandatory source/timestamp fields.

Warnings requiring review:

- [ ] Unexpected source coverage decline.
- [ ] Sudden feature distribution shift.
- [ ] New categories/entities without documented handling.
- [ ] Increased source revision rates.
- [ ] Odds snapshots materially stale versus historical norms.
- [ ] Material degradation in calibration, CLV, or market-relative residuals.
- [ ] Major fold-to-fold performance divergence.

---

# 14. Final research certification

Use this statement only if the pipeline has passed the audit:

> For each recorded prediction and simulated wager, the system can reconstruct the information set, source records, feature values, odds quote, model version, calibration state, decision rule, and settlement outcome as they existed at the documented prediction and execution timestamps. No post-decision information was used to construct features, fit transformations, select hyperparameters, calibrate probabilities, choose thresholds, or evaluate the final held-out period.

---

# 15. Core takeaways

1. Start simple: regularized regression, GAMs, and Bayesian hierarchical models are not merely baselines; they are often the right production models for limited, structured sports data.
2. Use gradient boosting as the primary nonlinear challenger for medium/large tabular datasets, but require time-stable gains in proper scoring and calibration.
3. Use neural networks only when scale or sequential/spatial/unstructured inputs justify them.
4. Model what the market pays on: event probabilities for binary markets and predictive distributions or quantiles for spreads/totals.
5. Use walk-forward validation for all learning steps, not just final model fitting.
6. Fit preprocessing, feature selection, calibration, blending, and thresholds using only prior data.
7. Preserve true data availability timestamps; no splitter can rescue a dataset built with hindsight.
8. Compare against contemporaneous no-vig market prices and monitor CLV as a diagnostic.
9. Backtest executable prices and realistic settlement/execution constraints.
10. Keep an untouched chronological final holdout and deploy first in shadow mode.
