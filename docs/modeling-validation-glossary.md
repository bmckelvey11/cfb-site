# Sports Betting Modeling, Validation, and Data-Audit Glossary

## A

### Accuracy
The fraction of predicted class labels that are correct. For a binary classifier, it is:

$$
\frac{\text{true positives} + \text{true negatives}}{\text{all predictions}}
$$

Accuracy is often a weak primary metric for betting because it ignores predicted probability confidence, odds, vig, and payoff asymmetry.

### Actual start time
The time an event actually begins, which can differ from the scheduled start time because of delay, postponement, or rescheduling. It matters for validating whether a price or feature was truly pre-event.

### Aggregation leakage
Leakage caused when group-level, season-to-date, rolling, or cumulative aggregates include outcomes from the row being predicted or from future rows.

### As-of join
A temporal join that selects the latest valid record available at or before a specified timestamp. Example: joining the latest injury report published before a model prediction time, rather than the latest injury report in the database.

### As-of-valid dataset
A dataset built so that every row contains only information genuinely available at its stated prediction timestamp. This is the required base for honest historical forecasting and backtesting.

### Availability timestamp
The time at which a feature, source record, news item, lineup, weather forecast, odds quote, or other input became observable to the strategy. Often stored as `feature_available_at` or `source_published_at`.

## B

### बै / Bet placement timestamp
The exact time a historical wager is modeled as having been placed. It should be separate from the prediction timestamp if the system has processing, review, or execution latency.

### Betting edge
The amount by which the model’s estimated fair probability or fair price exceeds the market’s break-even probability or estimated no-vig probability. An apparent edge is not necessarily actionable because of uncertainty, vig, price movement, limits, and execution constraints.

### Betting-market edge estimation
The process of converting model forecasts and sportsbook odds into an estimate of expected value, typically after de-vigging market prices and accounting for execution assumptions.

### Bivariate Poisson model
A joint count model for two correlated scoring processes. It can be useful when modeling the scores of two teams, especially when independence between team scores would be unrealistic.

### Brier score
A proper scoring rule for binary probability forecasts:

$$
\text{Brier} = \frac{1}{N}\sum_{i=1}^{N}(p_i-y_i)^2
$$

where $p_i$ is the predicted probability and $y_i$ is 0 or 1. Lower is better. The score reflects both probability accuracy and calibration but should be interpreted alongside reliability diagnostics.

### Buffer
A period of observations excluded near a train/test boundary to reduce dependence or information overlap. Also called an embargo or gap, depending on the use case.

## C

### Calibration
The agreement between predicted probabilities and observed event frequencies. A model is calibrated if events predicted at 60% occur about 60% of the time over a large, representative set of such forecasts.

### Calibration intercept
A diagnostic for systematic probability bias, typically estimated through a logistic recalibration regression. A nonzero intercept can indicate systematic over- or underprediction after accounting for forecast spread.

### Calibration slope
A diagnostic for forecast extremity. A slope below 1 commonly indicates predictions are too extreme/overfit; a slope above 1 can indicate predictions are insufficiently extreme. It should be estimated out of sample.

### Calibration set
A dataset of predictions and known outcomes used to fit a mapping from raw model outputs to calibrated probabilities. In temporal applications, it must precede the evaluation/prediction period.

### CatBoost
A gradient-boosted decision-tree library with methods designed to handle categorical variables and ordered target statistics. It is often a strong nonlinear candidate for structured sports data but still requires time-safe validation and calibration checks.

### Category vocabulary
The set of categorical levels recognized by a preprocessing pipeline, such as team IDs, player positions, venues, or bookmakers. It should be learned from training data only, with an explicit procedure for unseen test categories.

### Classification
A predictive task where the target is discrete, such as win/loss, over/under, or home/draw/away.

### Closing line
The market price or point line immediately before the bookmaker’s pre-event market closes, often near event start. It is useful as a post-decision benchmark but cannot be a feature in a strategy claiming to bet earlier prices.

### Closing-line value (CLV)
A measure of whether a placed wager obtained a better price or line than the later closing market. Price CLV compares odds or no-vig probabilities; line CLV compares point spreads or totals. Positive CLV is informative but does not prove realized profitability.

### Code commit hash
A unique identifier for a specific version of version-controlled code. Recording it with each backtest helps reproduce the exact data-processing and modeling logic used.

### Conditional distribution
The probability distribution of an outcome given available predictors. For a spread model, it is the distribution of final margin conditional on the information set available before the event.

### Conditional mean
The expected outcome given predictors:

$$
E[Y \mid X]
$$

It is the target of ordinary least squares regression. It is not alone sufficient for spread/total pricing when decision-making depends on tail probabilities or quantiles.

### Conditional median
The 50th percentile of the outcome distribution conditional on predictors. In equal-payout settings, it has a direct decision interpretation for choosing a side around a line, although actual EV also depends on payout and distributional detail.

### Continuous ranked probability score (CRPS)
A proper scoring rule for a full predictive distribution. It compares the predicted cumulative distribution with the realized outcome; lower is better. It is useful for evaluating distributions of margin, total, or score rather than only point forecasts.

### Correlated outcomes
Outcomes that are not statistically independent because they share teams, players, games, market conditions, time periods, or latent variables. Correlation can make a dataset appear larger than its effective independent sample size.

### Cross-fitting
A procedure that generates a feature or prediction for each observation using a model trained without that observation. It is commonly used for target encoding and stacking to reduce in-sample leakage.

### Cross-entropy
Another name for log loss when evaluating probabilistic classification. Lower is better.

### Cross-validation
A method for estimating generalization performance by repeatedly splitting data into training and test/validation subsets. In sports and other temporal settings, split design must respect time and information availability.

## D

### Data dictionary
A structured catalog describing every dataset field: definition, source, units, grain, data type, allowed values, timestamp semantics, availability rule, update cadence, and transformation lineage.

### Data lineage
The traceable chain from a raw source record through ingestion, cleaning, joins, transformations, feature engineering, model input, prediction, and reported result.

### Data revision
A later correction or update to historical records, such as changed box scores, player attribution, injury classification, odds history, or lineup information. Revisions can create hindsight bias if used in historical backtests without reconstructing what was known at the time.

### Dead heat
A settlement condition, common in racing or tournament markets, where multiple selections tie for a placing. Payouts are often divided according to market rules and must be handled explicitly in backtests.

### Decision contract
A written specification of the strategy’s intended behavior: target market, data sources, prediction time, betting time, books, execution assumptions, threshold rules, stake sizing, and settlement conventions.

### De-vigging
The conversion of sportsbook odds containing margin/overround into an estimate of fair or no-vig probabilities. Different methods can yield slightly different fair-probability estimates, especially in high-margin or multiway markets.

### Decimal odds
Odds expressed as total return per unit stake, including stake. For decimal odds $o$, a winning unit wager returns $o$ total and earns $o-1$ profit.

### Discrimination
A model’s ability to assign higher probabilities to events that occur than to events that do not. Discrimination does not ensure calibration.

### Distributional regression
A model that predicts parameters of an entire conditional distribution, such as mean and variance, rather than only a single conditional mean. It is useful for margin, total, and score modeling.

### Drawdown
The decline from a prior bankroll or equity peak to a subsequent trough. Maximum drawdown is the largest such decline over the evaluation interval.

## E

### Edge bucket
A group of wagers categorized by estimated model edge, such as 0–1%, 1–2%, 2–3%, and so on. It is used to check whether larger estimated edges correspond to stronger realized predictive or betting performance.

### Effective sample size
The amount of independent information in a dataset after accounting for repeated entities, correlated observations, overlapping windows, clustered games, and duplicated snapshots. It can be much smaller than raw row count.

### Elastic net
A regularized regression method combining L1 (lasso) and L2 (ridge) penalties. It is useful when features are correlated and feature selection/shrinkage is desired.

### Embargo
A deliberate time buffer after the end of training and before the beginning of a test period. It reduces leakage or dependence when labels/features have overlapping time windows.

### Entity effect
A model component associated with a repeated entity, such as a team, player, coach, referee, venue, course, or bookmaker.

### Entity mapping
The process of linking different aliases, IDs, name formats, or source representations to one canonical team/player/event/etc. identity.

### Expected value (EV)
The average profit expected per wager under a probability model and payoff schedule. For a unit bet at decimal odds $o$ with model win probability $p$:

$$
EV = p(o-1) - (1-p)
$$

This assumes a binary win/loss outcome; pushes, partial payouts, voids, and other settlement conditions require additional terms.

### Execution realism
The degree to which a backtest reflects what could actually have been placed: available price, timing, latency, limits, liquidity, rejection, line movement, market suspension, and settlement rules.

### Expanding window
A walk-forward training scheme where each successive training set includes all prior eligible data. It maximizes historical sample size but may retain stale regimes.

## F

### Fair probability
A model-estimated or de-vigged estimate of the probability of an outcome without bookmaker margin. It is used to compare against offered odds and calculate expected value.

### Feature
An input variable used by a prediction model, such as team ratings, player form, rest days, weather, lineup status, market probability, or course fit.

### Feature availability
The fact that a feature was observable and usable before the model’s prediction decision. It should be represented by a timestamp or a documented conservative availability rule.

### Feature leakage
The use of a feature that contains direct or indirect information about the future target, future market, or post-decision state.

### Feature lineage
Documentation of how a final feature was generated from raw source fields, including transformations, joins, availability rules, and versioned code.

### Feature selection
Selecting a subset of candidate predictors for a model. It must be performed inside training data/folds, not using the full dataset including test outcomes.

### Final holdout
A chronologically later dataset kept untouched during feature development, model selection, calibration design, threshold selection, and tuning. It should be evaluated only after the research design is frozen.

### Fold
One train/test split in a cross-validation scheme. In walk-forward validation, the training period precedes the corresponding test period.

### Forward horizon
The future duration used to define a target. For example, a target might be whether a price moves within the next 24 hours. Forward horizons commonly require purging and embargoing because labels can overlap across rows.

## G

### GAM (generalized additive model)
A generalized regression model in which selected predictors enter through smooth functions rather than only linear coefficients. GAMs can capture smooth nonlinear effects while retaining interpretability.

### Gap
A number of observations or time duration deliberately excluded between training and test folds. In scikit-learn `TimeSeriesSplit`, `gap` removes observations immediately before each test fold.

### Generalized linear model (GLM)
A model combining a linear predictor with a link function and probability distribution. Examples include logistic regression for binary outcomes, Poisson regression for counts, and negative-binomial regression for overdispersed counts.

### Gradient boosting
An ensemble method that builds decision trees sequentially, with each new tree improving on prior residual errors. XGBoost, LightGBM, and CatBoost are major implementations.

### Grouped chronological split
A time-respecting validation split that also accounts for grouped dependence, such as multiple odds snapshots from one game or repeated observations tied to a common final outcome.

## H

### Hierarchical model
A model that includes multiple levels of parameters, such as league-level, team-level, player-level, season-level, and event-level effects. Hierarchical models commonly use partial pooling.

### Holdout period
A set of observations withheld from model fitting and selection to estimate out-of-sample performance. In temporal settings, it should be a future chronological period.

### Home/away orientation
The convention identifying which team/player is designated home versus away. Incorrect orientation is a common source of sign errors in spreads, ratings, score differences, and odds mapping.

### Hyperparameter
A model configuration value selected before or during fitting, such as tree depth, learning rate, regularization strength, number of trees, spline complexity, prior scale, or neural-network architecture.

### Hyperparameter leakage
Performance inflation caused by using test/final-holdout results to choose hyperparameters, features, architectures, thresholds, or other model settings.

## I

### Implied probability
The probability implied by offered odds before removing vig. For decimal odds $o$:

$$
p_{\text{implied}} = \frac{1}{o}
$$

### Imputation
The process of replacing missing values. Any learned imputation statistic/model must be fitted on training data only within each fold.

### In-play / live betting
Betting after an event has started. It requires high-resolution timestamps, feed-latency modeling, market-suspension handling, and special care to prevent repeated snapshots from leaking the same final outcome across splits.

### In-sample prediction
A prediction made for observations used to fit the model. It is generally optimistic and unsuitable as the basis for honest backtest or calibration evaluation.

### Isotonic regression
A nonparametric monotonic calibration method. It can correct complex calibration shapes but can overfit with limited calibration data.

## K

### Kelly criterion
A bankroll-sizing formula that maximizes expected logarithmic bankroll growth under assumptions including accurate probabilities, known odds, and repeated independent bets. In practice, estimation error, correlation, limits, and nonstationarity often justify fractional Kelly or stricter caps.

### Key number
A point margin or total that occurs unusually often in a sport, such as common final-score margins in American football. Crossing a key number can make line CLV more valuable than a simple arithmetic line difference suggests.

## L

### Label
The outcome variable used to supervise a model, such as winner, final score, whether a total went over, final margin, or whether a line moved over a future horizon.

### Label end time
The timestamp at which the label’s information interval ends. For a game-result label, this may be event completion; for a future-line-movement target, it may be observation time plus the forecast horizon.

### Latency
The delay between information becoming available, a model producing a signal, a wager being sent, and a sportsbook accepting or updating the price. Ignoring latency can inflate a historical backtest.

### Lasso regression
A regularized regression method using an L1 penalty. It can shrink coefficients to zero and thus perform feature selection, but can be unstable among highly correlated features.

### Leakage
Any use of information unavailable at the time a prediction would have been made. Leakage includes future outcomes, post-event records, later odds, globally fit transformations, test-driven tuning, and revised history treated as real time.

### LightGBM
A high-performance gradient-boosted decision-tree library. It is often effective on large tabular datasets but needs careful time-aware tuning, regularization, and calibration validation.

### Line CLV
Closing-line value measured by improvement in a point spread or total line relative to the eventual close. It should incorporate market direction and key-number context.

### Line shopping
Comparing multiple sportsbooks to obtain the most favorable available odds or line. A backtest may only assume it when historical data and operational capability demonstrate that the chosen best price was actually observable and executable.

### Line movement
A change in offered odds, spread, total, or other market price over time. Predicting future line movement is a forward-horizon task that can require purged/embargoed validation.

### Log loss
A proper scoring rule for probabilistic classification:

$$
-\frac{1}{N}\sum_{i=1}^{N}\left[y_i\log(p_i)+(1-y_i)\log(1-p_i)\right]
$$

Lower is better. It penalizes highly confident incorrect forecasts strongly.

### Look-ahead bias
Bias caused by allowing a model, data process, selection rule, or backtest to use information that would only become known after the simulated historical decision. It typically makes performance appear unrealistically strong.

## M

### Margin
The difference in final score between sides, commonly defined as home score minus away score. It is a natural target for spread modeling.

### Market baseline
A benchmark forecast based on contemporaneously available sportsbook odds, usually converted to no-vig probabilities. It is a crucial comparison because markets aggregate substantial public information.

### Market efficiency
The degree to which market prices incorporate available information such that systematic excess expected returns are difficult to obtain. Efficiency is not necessarily absolute and can vary by sport, market, timing, liquidity, bookmaker, and information regime.

### Market probability
The implied probability from a sportsbook price, either raw (including vig) or no-vig after a margin-removal method.

### Maximum drawdown
The largest peak-to-trough decline in bankroll/equity over an evaluation period.

### Meta-model
A model trained on predictions from base models, often used in stacking/blending. It should be trained on out-of-fold base predictions rather than in-sample predictions.

### Model card
A structured document describing a model’s purpose, target, inputs, time assumptions, training data, performance, limitations, calibration, risks, monitoring, and deployment version.

### Model drift
Change over time in model performance, feature distributions, calibration, target relationships, or market behavior. Drift can result from sport rule changes, roster changes, strategic adaptation, sportsbook changes, or data-source changes.

### Multiclass classification
A classification task with more than two possible outcomes, such as home win/draw/away win. Outputs should form a coherent probability vector summing to one.

### Multiple testing
The increased chance of finding apparently favorable results by chance after trying many models, features, date ranges, filters, thresholds, markets, books, or performance metrics.

## N

### Negative-binomial regression
A count model that permits overdispersion, meaning variance greater than the mean. It can be more appropriate than Poisson regression for certain sports scoring/count outcomes.

### Nested walk-forward validation
A temporal validation design in which inner chronological folds select hyperparameters/features/configurations within an outer training period, and outer future folds estimate out-of-sample performance.

### Neural network
A flexible machine-learning model composed of layers of nonlinear transformations. It is most justified for large-scale or structured sequential, spatial, tracking, text, image, or other unstructured sports data.

### No-vig probability
An estimated fair probability after removing sportsbook margin/overround from a complete market. It is used as a market benchmark and for edge estimation.

### Non-stationarity
The property that data relationships, distributions, market behavior, or target processes change over time. It motivates rolling windows, monitoring, and conservative out-of-time evaluation.

## O

### Odds snapshot
A record of an offered sportsbook price, line, market status, and timestamp for a selection. Multiple snapshots can exist for the same event/market/selection as prices change.

### Odds timestamp
The time at which a sportsbook odds quote was observed or captured. It must be no later than the simulated execution time to be valid for a historical wager.

### Offsetting market information
Using market probability, line, or price as a baseline/feature while modeling residual predictive information. This can focus a model on information not already reflected in the current market.

### One-hot encoding
A method that represents categorical values with binary indicator columns. It should be fitted in a fold-safe pipeline and must define behavior for categories unseen in training.

### Ordered target encoding
A target-encoding technique that constructs category statistics using only preceding observations in an ordered dataset. It is useful for avoiding temporal target leakage when correctly implemented.

### Out-of-fold (OOF) prediction
A prediction for an observation generated by a model that was not trained on that observation. In walk-forward settings, valid OOF predictions should also be generated using only earlier data.

### Out-of-sample (OOS)
Refers to performance on observations not used to fit or select the evaluated model. For time-dependent systems, OOS data should occur later than the training data.

### Overfitting
Fitting noise, chance patterns, or idiosyncratic historical details rather than durable signal. It can appear as excellent in-sample/backtest performance and poor future performance.

### Overround
The total of raw implied probabilities in a market, minus one. It represents bookmaker margin in a simplified fixed-odds setting.

## P

### Partial pooling
A hierarchical-model mechanism that shrinks noisy group/entity estimates toward a shared population distribution. It prevents overreacting to small samples while allowing well-observed entities to differ meaningfully.

### Pinball loss
A loss function used in quantile regression. It evaluates forecast accuracy for a chosen quantile, which can be relevant to pricing a spread/total at a payout-dependent threshold.

### Pipeline
A reproducible ordered set of preprocessing and modeling steps, such as imputation, scaling, encoding, feature selection, model fit, and calibration. Pipelines help ensure transformations are fitted only on training data.

### Platt scaling
A sigmoid/logistic calibration procedure that maps raw model scores or probabilities to calibrated probabilities. It is often more stable than isotonic regression with modest calibration samples.

### Poisson regression
A generalized linear model for count outcomes, commonly using a log link. It can be used to model scores or event counts but assumes variance equals the mean unless extended.

### Posterior distribution
In Bayesian inference, the probability distribution of parameters or future outcomes after combining prior assumptions with observed data.

### Predictive distribution
The estimated probability distribution of a future outcome conditional on available information. It is the appropriate object for many spread, total, score, and uncertainty-aware betting decisions.

### Prediction timestamp
The exact time at which a model is assumed to have generated a forecast. It defines the allowable information set for historical reconstruction.

### Prequential evaluation
Sequential evaluation in which the model predicts the next observation/event using prior data, observes the outcome, updates or refits, then repeats. Also called predict-then-update evaluation.

### Price CLV
Closing-line value measured through the difference between the wagered price and closing price, often transformed into no-vig implied probabilities.

### Probability calibration curve / reliability diagram
A plot comparing average predicted probability with empirical event frequency across bins. It should be accompanied by bin counts because sparse bins can be noisy.

### Proper scoring rule
A metric that is optimized in expectation by reporting true beliefs/probabilities. Examples include log loss, Brier score, CRPS, and negative log predictive density.

### Purging
Removing training observations whose label or information intervals overlap the test period, preventing future-period information from contaminating the training set.

### Push
A bet settlement in which the relevant result exactly equals the line, usually returning stake. Push probabilities should be modeled or accounted for explicitly in applicable markets.

## Q

### Quantile
A value below which a specified fraction of a distribution lies. The 0.50 quantile is the median; the 0.90 quantile is the 90th percentile.

### Quantile regression
A regression method that models conditional quantiles rather than only conditional means. It can be useful for line-specific spread/total decisions and tail-risk estimation.

## R

### Random forest
An ensemble of decorrelated decision trees whose predictions are averaged. It can capture nonlinearities/interactions but is often a less compelling primary choice than boosted trees for calibrated tabular betting probabilities.

### Random K-fold cross-validation
A cross-validation method that randomly assigns observations to folds. It is generally inappropriate for chronological sports forecasting or betting data because it can introduce future information into training.

### Raw implied probability
The direct implied probability from sportsbook odds before removing vig.

### Realized ROI
The historical return on investment actually observed in a backtest or live record. It is noisy, depends on stake/execution assumptions, and should not be the only criterion for model selection.

### Reliability
The calibration component of probabilistic prediction: whether forecast probabilities correspond to observed frequencies.

### Residual model
A model trained to predict the remaining error after a baseline, such as a market probability or structural regression model. In betting, residual modeling can focus nonlinear capacity on information not already captured by the market baseline.

### Retraining cadence
How often the model and associated components are updated in production, such as event-by-event, daily, weekly, round-by-round, or tournament-by-tournament. Historical validation should simulate the intended cadence.

### Ridge regression
A regularized linear regression using an L2 penalty. It is stable under multicollinearity and tends to shrink correlated coefficients together.

### Rolling feature
A feature computed from a trailing historical window, such as last 5 games, last 20 rounds, or trailing 30 days. It must use only observations completed before the prediction timestamp.

### Rolling window
A walk-forward training scheme that keeps a fixed-length recent history and discards older observations as time advances.

### ROI / yield
Return on investment, commonly net profit divided by stake/turnover. It must be interpreted with sample size, odds distribution, drawdown, execution assumptions, and uncertainty.

## S

### Sample leakage
A broad term for contamination across training, validation, and test samples. It includes duplicate rows, repeated game snapshots, shared labels, future data, globally fitted transforms, and test-driven selection.

### Scheduled start time
The planned event start. It may differ from actual start and should not automatically be treated as the time information became unavailable or a market closed.

### Score model
A probabilistic model of team/player scores or counts. A joint score model can produce coherent derived probabilities for moneyline, spread, and total markets.

### Season-to-date feature
A statistic accumulated over the current season before an event, such as scoring average, win percentage, or strokes gained. It must exclude the event being predicted.

### Selection bias
Bias introduced when the evaluated sample, model, threshold, time period, bookmaker, market, or feature set is chosen based on favorable observed outcomes.

### Settlement rules
The bookmaker’s rules determining bet outcomes and payouts, including treatment of overtime, postponement, voids, pushes, dead heats, shortened events, and player participation requirements.

### Shadow mode
Running a system prospectively without placing real bets, while logging live inputs, model outputs, offered prices, theoretical wagers, and eventual outcomes. It validates operational timing and data quality before capital deployment.

### Shrinkage
The reduction of parameter estimates toward zero or a population mean to reduce variance and overfitting. Ridge, lasso, elastic net, and Bayesian priors all produce forms of shrinkage.

### Sigmoid calibration
See Platt scaling.

### Slippage
The deterioration between a quoted price/line at signal time and the price/line actually available when a wager is executed. It is especially important in moving or low-liquidity markets.

### Source publication time
The time a provider first made a source record available. It is generally more meaningful than database ingestion time for determining whether historical information could have been used.

### Spread
A handicap line applied to a side’s final margin. A spread model should estimate the probability that final margin exceeds, falls below, or equals the offered line, according to settlement rules.

### Stacking
An ensemble method that uses a meta-model to combine base-model predictions. The meta-model must be trained on out-of-fold predictions to avoid in-sample overstatement.

### Stake sizing
The rule for determining wager size based on bankroll, estimated edge, uncertainty, limits, and risk caps. It should be fixed before final evaluation and assessed under realistic constraints.

### Stale price
An odds quote no longer realistically available at the stated execution time, often due to market movement, delayed data feed, suspension, or ingestion lag.

### Strategy version
A reproducible identifier for the full decision system: data contract, feature set, model, calibration, thresholds, staking logic, and execution assumptions.

### Supervised learning
Machine learning in which a model learns a mapping from input features to known labeled outcomes.

## T

### Target
The dependent variable a model seeks to predict. Examples include final margin, total score, win probability, player statistic outcome, or next-24-hour line movement.

### Target encoding
Representing a categorical entity using statistics of the target, such as a team’s historical win rate. It is a high-risk leakage source unless calculated only from prior training observations.

### Temperature scaling
A probability-calibration method that rescales model logits with a single temperature parameter. It is commonly used for multiclass or neural-network calibration.

### Test block
The future period predicted by a model in one walk-forward fold. It may consist of an event, day, week, slate, tournament, round, or specified number of rows.

### Test set
Data withheld from fitting in a given validation fold and used to estimate out-of-sample performance. In time-aware validation, it occurs after the associated training set.

### Time-series split
A cross-validation split preserving chronological order. Successive training sets precede test sets; it can use expanding or rolling windows and may include a gap.

### Timestamp normalization
The conversion of timestamps from different sources/time zones/formats into a consistent, timezone-aware standard, typically UTC.

### Train/test contamination
Any circumstance in which information from test observations affects training, preprocessing, calibration, selection, or threshold setting.

### Training window
The historical time range used to fit a model for a particular walk-forward fold.

### Transformation leakage
Leakage caused when a data transformation learns from the full dataset rather than training rows only. Examples include global scaling, global imputation, global PCA, and global winsorization.

## U

### Uncertainty quantification
Estimating uncertainty around parameter estimates, probabilities, predictions, distributions, or expected value. Bayesian posterior intervals, ensembles, bootstraps, and distributional models are common approaches.

### Unit stake
A standardized wager size, often 1 unit, used to report return independent of bankroll size.

### Untouched holdout
See final holdout.

## V

### Validation set
Data used to choose model settings or compare candidates. In temporal research, validation must occur after the associated training period and before the final holdout period.

### Variance
A measure of outcome dispersion. For spread and total markets, predictive variance has direct implications for tail probabilities even if expected score/margin is unchanged.

### Vig
Sportsbook margin embedded in offered odds. It makes raw implied probabilities sum to more than one across a complete market in typical fixed-odds books.

### Void
A wager canceled under sportsbook rules, typically returning stake. It must not be scored as an ordinary win or loss.

## W

### Walk-forward validation
A chronological validation method that repeatedly trains on past data and predicts the next unseen future block. It is a core defense against look-ahead bias when paired with as-of-valid data construction.

### Walk-forward fold
One iteration of walk-forward validation containing a prior training window and a later test block.

### Walk-forward optimization
A related term sometimes used for repeatedly retuning and evaluating a strategy over moving time periods. It should still keep tuning separate from outer testing and maintain a final untouched holdout.

### Window length
The amount of past data used for training or rolling features. It can be fixed (rolling) or cumulative (expanding) and should be selected using time-safe validation.

### Win probability
The probability that a specified selection wins under the market’s settlement definition. For moneylines and binary props, it is typically the direct model target.

### Winsorization
Capping extreme feature values at selected thresholds. Thresholds must be estimated from training data only to avoid transformation leakage.

## X

### XGBoost
A widely used gradient-boosted decision-tree implementation supporting regularization, classification, regression, ranking, and custom objectives. It is a strong tabular-data candidate but requires careful temporal validation, hyperparameter control, and probability calibration.

---

# Key formulas

## Raw implied probability

$$
p_{\text{implied}} = \frac{1}{o}
$$

where $o$ is decimal odds.

## Binary expected value per unit stake

$$
EV = p(o-1) - (1-p)
$$

where $p$ is model win probability and $o$ is decimal odds.

## Break-even probability

$$
p_{BE} = \frac{1}{o}
$$

For standard -110 odds, $o \approx 1.9091$, so $p_{BE} \approx 52.38\%$ when no push is possible.

## Brier score

$$
\text{Brier} = \frac{1}{N}\sum_{i=1}^{N}(p_i-y_i)^2
$$

## Binary log loss

$$
-\frac{1}{N}\sum_{i=1}^{N}\left[y_i\log(p_i)+(1-y_i)\log(1-p_i)\right]
$$

## Feature-availability rule

$$
\texttt{feature\_available\_at} \leq \texttt{prediction\_timestamp}
$$

## Core temporal ordering rule

$$
\texttt{feature\_available\_at} \leq \texttt{prediction\_timestamp} < \texttt{event\_start\_time} \leq \texttt{outcome\_finalized\_at}
$$

## Purging rule

For training observation $i$, retain it before a test block only when:

$$
\texttt{label\_end}_i < \texttt{test\_start}
$$

With an embargo buffer:

$$
\texttt{label\_end}_i < \texttt{test\_start} - \texttt{embargo}
$$

---

# Practical reminders

- A chronological splitter does not fix a dataset that already contains hindsight; feature availability must be audited first.
- The closing line is a useful benchmark, not an allowed feature for an earlier-line strategy.
- In-sample predictions are not valid for calibration or performance claims.
- Fit all transformations inside the training portion of every fold.
- Preserve immutable out-of-fold predictions and evaluate from that ledger.
- Prefer stable results across contiguous time periods over the single highest historical ROI.
- A complex model should earn deployment by beating market and simpler-model baselines on time-valid, properly calibrated evaluation.
