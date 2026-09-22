# Sports Betting Prediction Data Audit Checklist

## Purpose

Use this checklist before trusting any research result, backtest, model comparison, calibration result, closing-line-value analysis, or live betting recommendation. It is designed for pregame and in-play sports betting datasets, including game-level, player-level, team-level, tournament-level, round-level, and odds-snapshot data.

**Core rule:** For every prediction made at timestamp $t$, every feature must have been available at or before $t$. Every outcome, closing line, settlement record, and post-event statistic must be unavailable to the model at $t$.

$$
\texttt{feature\_available\_at} \leq \texttt{prediction\_timestamp} < \texttt{event\_start\_time} \leq \texttt{outcome\_finalized\_at}
$$

---

## 1. Audit scope and decision contract

### 1.1 Define the strategy precisely

- [ ] Document the sport, league/tour, competition level, market type, and bookmaker(s).
- [ ] State the target: moneyline, spread, total, team total, player prop, match-up, outright, round market, live/in-play market, or another defined market.
- [ ] State the prediction target separately from the betting decision target.
- [ ] Define the prediction timestamp for every strategy.
- [ ] Define the intended bet-placement timestamp or permissible placement window.
- [ ] Define whether the strategy uses opening lines, a fixed pre-event timestamp, best available price, last available pre-event price, or live odds.
- [ ] Define the event start time and time-zone convention.
- [ ] Define the outcome settlement convention, including pushes, voids, postponed games, abandoned events, dead heats, and partial refunds.
- [ ] Define the odds format stored internally: decimal odds recommended; convert American/fractional odds at ingestion.
- [ ] Define whether backtest results assume one book, a line-shopping universe, a best-price feed, or executable price snapshots.
- [ ] Define max stake, limits, liquidity, account restrictions, timing delays, and transaction assumptions.
- [ ] Freeze the strategy specification before evaluating the final holdout period.

### 1.2 Version and provenance controls

- [ ] Assign a unique `strategy_version` to the model, feature set, calibration method, thresholds, and staking logic.
- [ ] Record code commit hash for every backtest run.
- [ ] Record dependency versions, random seeds, model-library versions, and database snapshot/version.
- [ ] Record raw-data source, vendor, API endpoint, extraction time, and license/usage constraints.
- [ ] Save raw input files or immutable source snapshots whenever permitted.
- [ ] Store all transformations in version-controlled code or reproducible SQL.
- [ ] Maintain a data dictionary with definition, source, unit, coverage, timestamp semantics, and update cadence for every column.
- [ ] Record known data defects, vendor revisions, schema changes, and coverage gaps.

---

## 2. Required timestamp fields

Every prediction-level row should retain, directly or through auditable joins, the following fields.

| Field | Required meaning | Audit condition |
|---|---|---|
| `event_id` | Stable identifier for the sporting event | Unique and consistent across sources |
| `event_start_time` | Scheduled or actual start timestamp | Time zone normalized; revisions retained if relevant |
| `prediction_timestamp` | Exact moment the model is assumed to make a prediction | Must be before event start; must match strategy contract |
| `bet_timestamp` | Exact simulated or actual execution time | Must be at/after prediction and before market cutoff |
| `feature_available_at` | Time a specific feature became observable | Must be no later than prediction timestamp |
| `odds_timestamp` | Time an offered market price was captured | Must be no later than bet timestamp |
| `source_published_at` | Provider publication time | Used to distinguish event date from data availability |
| `ingested_at` | Time data entered local storage | Must not substitute for provider availability without justification |
| `outcome_finalized_at` | Time official result became known | Strictly after prediction timestamp |
| `settlement_timestamp` | Time wager was settled | Supports payoff and void/push auditing |
| `record_revision_at` | Time source corrected the historical record | Enables detection of hindsight from revised data |

### Timestamp integrity checks

- [ ] All timestamps are timezone-aware.
- [ ] One canonical timezone is used in storage, preferably UTC.
- [ ] Local start times, DST transitions, and venue time zones are handled correctly.
- [ ] `prediction_timestamp < event_start_time` for all pre-event rows.
- [ ] `odds_timestamp <= bet_timestamp` for all executed price records.
- [ ] `feature_available_at <= prediction_timestamp` for all model inputs.
- [ ] `outcome_finalized_at > prediction_timestamp` for all supervised labels.
- [ ] Missing timestamps are either resolved, explicitly excluded, or assigned a conservative availability rule documented in the data dictionary.
- [ ] No timestamp is silently rounded in a way that could convert post-event information into pre-event information.
- [ ] Source update latency is accounted for when a feed publishes data after the actual event/news occurrence.

---

## 3. Raw event data audit

### 3.1 Event identity and coverage

- [ ] Every event has a stable unique key independent of row order.
- [ ] Duplicate events are identified by source ID, teams/players, start time, and competition.
- [ ] Home/away orientation is standardized and verified.
- [ ] Neutral-site events are explicitly flagged.
- [ ] Event status is stored: scheduled, live, completed, postponed, canceled, abandoned, suspended, or void.
- [ ] Rescheduled events retain original and actual start times when both matter.
- [ ] Doubleheaders, playoff series, tournament rounds, and multi-leg ties have unambiguous identifiers.
- [ ] Competition, season, phase, venue, round, and event format are represented consistently.
- [ ] Historical coverage by season, competition, and market is tabulated.
- [ ] Gaps caused by vendor outages, league changes, or unavailable markets are recorded.

### 3.2 Outcome quality

- [ ] Final scores/results reconcile against a trusted official or primary source.
- [ ] Outcome convention is consistent across all seasons and data sources.
- [ ] Overtime, extra innings, shootouts, tiebreakers, playoffs, and shortened events are treated consistently with market settlement rules.
- [ ] Pushes, ties, draws, voids, cancellations, dead heats, and partial outcomes are explicitly encoded.
- [ ] Corrected scores or results retain both original source state and final corrected state where available.
- [ ] Label generation is unit-tested for representative edge cases.
- [ ] No final outcome field is included in a feature table, directly or indirectly.

### 3.3 Entity identity

- [ ] Team, player, coach, referee, venue, tournament, and bookmaker IDs are mapped to canonical IDs.
- [ ] Team relocations, renames, mergers, expansions, and historical aliases are handled.
- [ ] Player name collisions, suffixes, accents, and traded-team assignments are resolved.
- [ ] Roster membership has effective start and end timestamps.
- [ ] Team/player joins are validated around trades, loans, promotions, demotions, injuries, and lineup changes.
- [ ] Unmatched entity records are counted and reviewed rather than silently dropped.

---

## 4. Odds and market-data audit

### 4.1 Price validity

- [ ] Store raw odds exactly as received, plus normalized decimal odds and implied probability.
- [ ] Retain bookmaker, market type, selection, line, odds, currency if applicable, timestamp, source, and market status.
- [ ] Validate decimal odds are greater than 1.0 for standard fixed-odds bets.
- [ ] Identify malformed prices, stale snapshots, duplicated ticks, zero/negative prices, and impossible line movements.
- [ ] Confirm favorite/underdog orientation after every odds conversion.
- [ ] Confirm spread sign conventions and home/away orientation.
- [ ] Confirm total-over/under selection and line conventions.
- [ ] Confirm prop units and definitions across books and vendors.
- [ ] Validate that the selected price was available from the named book at the simulated execution time.
- [ ] Do not use a best-of-market price unless the strategy could observe and execute it in real time.

### 4.2 Market timing

- [ ] Define open, mid-market, fixed-time, bet-time, and close snapshots separately.
- [ ] Verify that closing lines are never features in an opening-line or early-price model.
- [ ] Verify that late lineup/news-informed prices are never features in an earlier-timestamp strategy.
- [ ] Confirm that odds snapshots are sorted by exchange/book timestamp, not ingestion order alone.
- [ ] Deduplicate snapshots using event, market, selection, book, line, price, and timestamp.
- [ ] Flag price records after event start for a pre-event strategy.
- [ ] Flag odds timestamp anomalies relative to start time.
- [ ] Distinguish suspended/reopened markets from continuously tradable markets.
- [ ] Record book-specific cutoff times and settlement rules.
- [ ] Validate that price availability survives realistic bet latency assumptions.

### 4.3 Vig and fair-market conversion

- [ ] Calculate raw implied probabilities from decimal odds: $p_i = 1/o_i$.
- [ ] Calculate market overround for each complete market snapshot.
- [ ] Apply a documented de-vig method consistently.
- [ ] Retain both raw and no-vig probabilities.
- [ ] Use an appropriate multiway de-vig method for markets with more than two outcomes.
- [ ] Do not compare model probability directly to raw implied probability without accounting for vig.
- [ ] Audit incomplete market snapshots before computing no-vig probabilities.
- [ ] Validate that de-vig probabilities sum to approximately 1 after rounding.
- [ ] Report sensitivity of edge estimates to the selected de-vig method when margins are material.

### 4.4 Closing-line value

- [ ] Define the closing-line source and precise cutoff timestamp.
- [ ] Store closing line, closing price, closing no-vig probability, and source book/consensus.
- [ ] Store both line CLV and price/probability CLV.
- [ ] Preserve key-number context for spreads and totals where relevant.
- [ ] Treat CLV as a post-decision diagnostic, never as a feature for earlier decisions.
- [ ] Separate CLV results by bookmaker, market, price range, time-to-start, and liquidity regime.
- [ ] Investigate systematically negative CLV before attributing losses to variance.
- [ ] Do not claim profitability solely from positive CLV or predictive skill solely from beating close.

---

## 5. Feature availability and look-ahead audit

### 5.1 Column-level feature certification

For every feature, document:

- [ ] Feature name and definition.
- [ ] Source table/API/vendor.
- [ ] Unit and transformation.
- [ ] Entity grain: event, team-event, player-event, snapshot, season, or another explicit grain.
- [ ] Earliest time it becomes observable.
- [ ] Whether it is known pre-event, available only at a scheduled publication time, or revised retrospectively.
- [ ] Historical backfill/revision behavior.
- [ ] Required joins and their temporal conditions.
- [ ] Missingness rule and whether missingness itself is predictive.
- [ ] Data owner or code location responsible for construction.

### 5.2 Availability checks

- [ ] Every feature has an explicit `feature_available_at` timestamp or a documented conservative rule.
- [ ] Every feature satisfies `feature_available_at <= prediction_timestamp`.
- [ ] Features derived from event statistics are shifted so that current-event outcomes cannot enter current-event features.
- [ ] Season-to-date statistics include only events completed before the prediction timestamp.
- [ ] Rolling averages, rolling rates, moving sums, and exponentially weighted features are shifted before use.
- [ ] Rankings, standings, Elo ratings, player ratings, and team powers are calculated from prior completed events only.
- [ ] Ratings update after an event is completed, not at event start.
- [ ] Future schedule features do not include post-prediction schedule revisions unless those were known at the time.
- [ ] Injury, lineup, weather, referee, venue, travel, and news features use publication time rather than eventual truth time.
- [ ] Any feature updated after the event is treated as invalid unless a pre-event snapshot is available.
- [ ] Historical data corrections are either reconstructed as-of or excluded from strict real-time backtests.

### 5.3 Rolling-statistics tests

- [ ] For each rolling feature, manually inspect several early, middle, and late-season rows.
- [ ] Confirm the current event does not contribute to its own rolling statistic.
- [ ] Confirm the next event does not contribute to prior-event features.
- [ ] Confirm rolling windows reset or carry across seasons according to the documented design.
- [ ] Confirm offseason, transfer, roster, and rule changes are represented appropriately.
- [ ] Confirm opponent-adjusted statistics use only prior opponent information.
- [ ] Confirm feature denominators are available before event start.
- [ ] Confirm aggregate features do not use future samples due to groupby/order errors.

### 5.4 Target leakage tests

- [ ] Compute correlations, mutual information, and feature importance only as diagnostics; investigate suspiciously powerful features.
- [ ] Flag any feature with near-perfect predictive performance unexpectedly early in development.
- [ ] Search source tables for direct labels, post-event status fields, final rankings, final scores, and final market fields.
- [ ] Check that postgame box-score columns, final strokes gained, full-event possession metrics, and final lineup status do not enter pregame models.
- [ ] Check that settlement data are segregated from feature tables.
- [ ] Test whether model performance collapses when suspected leakage columns are removed.
- [ ] Run a shuffled-label test; strong performance under shuffled labels indicates leakage or evaluation error.

---

## 6. Join and granularity audit

### 6.1 Grain definition

- [ ] State the grain of every table: one row per event, team-event, player-event, odds snapshot, wager, tournament-round, or another explicit unit.
- [ ] State the expected primary key for every table.
- [ ] Confirm source primary keys are unique at their declared grain.
- [ ] Confirm final modeling table has the intended number of rows per decision.
- [ ] Confirm the target is unique at the model-row grain.
- [ ] Confirm a single event is not inadvertently represented multiple times through duplicate odds or entity joins.

### 6.2 Join safety

- [ ] Profile row counts before and after every join.
- [ ] Investigate any many-to-many join explicitly.
- [ ] Use temporal/as-of joins for time-varying records.
- [ ] Add join assertions for expected maximum match cardinality.
- [ ] Check unmatched rates by source, season, league, bookmaker, and entity.
- [ ] Ensure a later injury/lineup/news record cannot join to an earlier prediction row.
- [ ] Verify all team/player IDs refer to the correct entity as of event time.
- [ ] Check home/away and player/opponent orientation after joins.
- [ ] Verify data type and unit compatibility before arithmetic transformations.
- [ ] Reconcile aggregate totals before and after joins.

### 6.3 Duplicate handling

- [ ] Identify exact duplicates.
- [ ] Identify semantic duplicates with different IDs or timestamps.
- [ ] Define deterministic precedence rules for duplicate source records.
- [ ] Retain audit records of dropped/merged duplicates.
- [ ] Do not silently use the latest revised row if that row was unavailable historically.
- [ ] Confirm duplicate removal does not eliminate legitimate multiple snapshots or multiple market selections.

---

## 7. Missing data, outliers, and revisions

### 7.1 Missingness

- [ ] Measure missingness by feature, season, league, team/player, book, market, and timestamp.
- [ ] Identify whether missingness changes before versus after particular dates or vendor schema updates.
- [ ] Confirm missingness is not caused by future-unavailable fields masquerading as pre-event data.
- [ ] Define imputation per feature and fit learned imputers on training data only.
- [ ] Add explicit missingness indicators where operationally useful.
- [ ] Check whether missing values correlate with outcome, odds, event type, or source quality.
- [ ] Exclude rows only under a predeclared policy; quantify coverage lost.
- [ ] Ensure test-period missingness is not resolved using future values.

### 7.2 Outliers and impossible values

- [ ] Validate ranges, units, signs, and denominators for every numerical feature.
- [ ] Check for impossible dates, negative counts, impossible scores, invalid lines, and invalid odds.
- [ ] Flag sudden distribution shifts by season and vendor.
- [ ] Investigate extreme observations before winsorizing or clipping.
- [ ] Fit clipping thresholds/winsorization parameters on training data only.
- [ ] Preserve raw values separately from cleaned/transformed values.
- [ ] Verify outlier treatment does not erase meaningful rare conditions such as weather extremes or injury severity.

### 7.3 Retrospective revisions

- [ ] Identify sources that revise box scores, play-by-play, player attribution, injuries, rankings, or odds histories.
- [ ] Determine whether historical snapshots can be reconstructed as known at prediction time.
- [ ] Retain source revision timestamps where available.
- [ ] Mark data as hindsight-contaminated if revision time is unknown and pre-event availability cannot be established.
- [ ] Run sensitivity tests excluding sources with uncertain revision behavior.
- [ ] Do not mix final revised historical data with real-time deployment data without documenting the mismatch.

---

## 8. Train, validation, and test partition audit

### 8.1 Chronological partitions

- [ ] Sort observations by exact prediction timestamp.
- [ ] Use chronological walk-forward/rolling-origin splits rather than random K-fold splits.
- [ ] Verify every training timestamp is strictly earlier than every test timestamp in each fold.
- [ ] Specify initial training length, test block length, step size, and retraining cadence.
- [ ] Use an expanding window when long-run data remain relevant.
- [ ] Use a rolling fixed-length window when regime drift makes older data stale.
- [ ] Preserve a final chronological holdout period untouched until the research design is frozen.
- [ ] Report performance by fold, not only the pooled average.
- [ ] Check stability across seasons, rule eras, market regimes, and sample-size regimes.

### 8.2 Purging and embargo

- [ ] Identify the information interval and label interval for every row.
- [ ] Purge training rows whose label periods overlap a future test period.
- [ ] Apply an embargo buffer when nearby observations could share information or correlated outcomes.
- [ ] Use purging for forward-return, future-line-movement, in-play, overlapping horizon, and repeated-snapshot labels.
- [ ] Document the rationale and duration for each gap/embargo.
- [ ] Verify no event appears in train and test through different snapshots when that would leak its eventual outcome.

### 8.3 Group dependence

- [ ] Assess whether rows cluster by game, team, player, season, tournament, venue, or slate.
- [ ] Prevent multiple snapshots of the same game from crossing train/test when targets share the final outcome.
- [ ] Prevent player/team records from exposing a post-event aggregate in a different row.
- [ ] For entity-heavy models, evaluate cold-start/new-team/new-player cases separately.
- [ ] Consider grouped chronological splits when the same entity has highly correlated observations near a cutoff.

---

## 9. Preprocessing and feature-engineering audit

- [ ] Fit imputation, scaling, encoding, PCA, feature selection, clipping, and dimensionality reduction inside each training fold.
- [ ] Implement preprocessing as a pipeline so transforms are fit only on the training subset.
- [ ] Fit target encoders using only training labels; use cross-fitted or ordered encoding where appropriate.
- [ ] Fit categorical vocabularies only on training data, with an explicit unknown-category treatment.
- [ ] Fit normalization constants and baseline rates on training history only.
- [ ] Fit feature selection only inside nested validation, not on full data.
- [ ] Fit residualization against the market only within training data.
- [ ] Verify engineered interactions do not mix future-known components.
- [ ] Preserve a feature lineage record from raw source to final model matrix.
- [ ] Generate a per-fold feature-availability report.

---

## 10. Model-selection and hyperparameter audit

- [ ] Define primary selection metric before tuning.
- [ ] Use nested walk-forward validation when comparing model classes or tuning many hyperparameters.
- [ ] Select hyperparameters using only inner training/validation periods of each outer fold.
- [ ] Refit selected model only on the outer training history before predicting the outer test block.
- [ ] Keep outer test predictions immutable after generation.
- [ ] Do not tune on the final holdout era.
- [ ] Log every experiment, parameter set, feature set, random seed, and evaluation result.
- [ ] Track the number of researcher degrees of freedom: models, thresholds, feature variants, books, markets, and date filters tested.
- [ ] Correct interpretation for multiple testing; favor repeated-period stability over the best single backtest.
- [ ] Compare against simple baselines: market no-vig probability, closing market where appropriate as a benchmark, historical average, Elo/rating model, and regularized linear/logistic model.
- [ ] Require a nonlinear/complex model to improve proper scoring and calibration, not merely a cherry-picked ROI segment.

---

## 11. Probability, distribution, and calibration audit

### 11.1 Target appropriateness

- [ ] Use a probability target for moneyline and binary prop markets.
- [ ] Use a coherent multiclass probability model for draw/three-way markets.
- [ ] Use a predictive distribution or relevant quantiles for spreads and totals, not only a conditional mean.
- [ ] Treat pushes explicitly for integer or key-number markets.
- [ ] Confirm the model output maps correctly to the offered market line.

### 11.2 Calibration protocol

- [ ] Generate raw predictions out of fold using chronological walk-forward splits.
- [ ] Fit a calibration model only on earlier out-of-fold predictions/outcomes.
- [ ] Apply the calibrator prospectively to later test blocks.
- [ ] Never fit a calibrator on in-sample predictions.
- [ ] Never fit a calibrator using the final holdout outcomes.
- [ ] Use a separate chronological calibration block when out-of-fold rolling calibration is impractical.
- [ ] Use lower-variance calibration methods for limited calibration samples.
- [ ] Treat flexible calibrators such as isotonic regression cautiously on small samples.
- [ ] Refit calibration on the same cadence intended for production.
- [ ] Log calibration data window, method, parameters, and effective sample size.

### 11.3 Calibration diagnostics

- [ ] Report log loss/cross-entropy.
- [ ] Report Brier score.
- [ ] Report calibration intercept and calibration slope.
- [ ] Plot reliability curves with sample counts per bin.
- [ ] Evaluate calibration by time period, market, odds band, and favorite/underdog status.
- [ ] Evaluate calibration specifically in the bettable edge tail.
- [ ] Check that high-confidence predictions occur often enough to assess empirically.
- [ ] Compare raw versus calibrated performance without selecting post hoc solely on test ROI.
- [ ] For totals/spreads, assess distributional calibration and coverage of predictive intervals.
- [ ] Measure quantile calibration near relevant breakeven thresholds.

---

## 12. Backtest and execution audit

### 12.1 Wager construction

- [ ] Convert model outputs to fair probabilities or fair prices using a documented method.
- [ ] Compare the model estimate to the contemporaneously available offered odds, not to a later price.
- [ ] Calculate expected value using the actual payout convention.
- [ ] Include pushes, voids, dead heats, partial payouts, and market-specific settlement rules.
- [ ] Use no-vig market probability for market-relative diagnostics.
- [ ] Predefine the minimum edge rule.
- [ ] Predefine maximum stake, bankroll fraction, and stake-sizing formula.
- [ ] Include maximum exposure by game, team/player, slate, market, correlation cluster, and day.
- [ ] Apply realistic price rounding, stake limits, timing, bet rejection, and line movement assumptions.
- [ ] Clearly distinguish “signal generated” from “wager executable.”

### 12.2 Strategy threshold integrity

- [ ] Choose edge thresholds in training/nested-validation data only.
- [ ] Do not select thresholds after inspecting final holdout ROI.
- [ ] Do not filter to a favorable bookmaker, time window, odds range, or market only after observing outcomes.
- [ ] Report the number of bets and turnover for every threshold examined.
- [ ] Report results over contiguous time periods, not only the full-sample aggregate.
- [ ] Test whether edge deciles are monotonically related to realized outcomes/return.
- [ ] Use confidence intervals or resampling for ROI and yield estimates.
- [ ] Separate statistical evidence of predictive edge from realized P&L variance.

### 12.3 Execution realism

- [ ] Confirm historical offered prices were executable, not merely observed.
- [ ] Model bet-delay assumptions between signal and price capture.
- [ ] Model or report line-movement slippage.
- [ ] Account for unavailable/limited markets, account limits, and restricted stakes where applicable.
- [ ] Do not assume simultaneous best price across all books unless the execution system can do so.
- [ ] Account for market suspension around news and lineup announcements.
- [ ] Separate opening, early, pregame, and closing execution windows.
- [ ] Log rejected, stale, missing, and unmatched price observations.

---

## 13. Evaluation and reporting audit

### 13.1 Predictive quality

- [ ] Report out-of-fold log loss for probability targets.
- [ ] Report Brier score for probability targets.
- [ ] Report calibration slope/intercept and reliability curve.
- [ ] Report MAE/RMSE only as secondary metrics for score/margin point estimates.
- [ ] Report CRPS, negative log predictive density, or quantile loss for distributional spread/total models where feasible.
- [ ] Compare all model metrics to market and simple statistical baselines.
- [ ] Report sample size and effective number of independent events.
- [ ] Report confidence intervals or uncertainty estimates.

### 13.2 Betting quality

- [ ] Report bet count, stake, turnover, gross profit, net profit, ROI/yield, and average odds.
- [ ] Report win rate only with odds context; do not treat win rate as profitability.
- [ ] Report ROI by fold, season, month, market, bookmaker, odds band, edge bucket, and time-to-start.
- [ ] Report CLV separately from realized ROI.
- [ ] Report maximum drawdown, drawdown duration, and return volatility.
- [ ] Report results before and after assumed/actual execution costs.
- [ ] Report sensitivity to edge thresholds, calibration choice, de-vig method, and odds timestamp selection.
- [ ] Identify whether results depend on a small number of unusually favorable bets or events.
- [ ] Avoid annualizing unstable short-horizon betting returns.

### 13.3 Robustness tests

- [ ] Re-run with alternate chronological cut points.
- [ ] Re-run with alternate reasonable train-window lengths.
- [ ] Re-run with conservative odds-latency/slippage assumptions.
- [ ] Re-run excluding suspect sources, data gaps, and uncertain revisions.
- [ ] Re-run excluding the best-performing season, market, team, player, or bookmaker.
- [ ] Re-run with randomized or placebo features to check for accidental leakage.
- [ ] Re-run on a new season or newly collected prospective data.
- [ ] Confirm the strategy remains directionally coherent across materially different periods.

---

## 14. Sport-specific audit extensions

### 14.1 Team sports

- [ ] Verify home/away/neutral-site treatment.
- [ ] Audit overtime/extra-time settlement according to each market rule.
- [ ] Ensure team strength and Elo updates use only prior completed games.
- [ ] Confirm rest, travel, and schedule-density calculations use schedule information known at prediction time.
- [ ] Confirm roster, injury, starter, lineup, and minutes projections use publication timestamps.
- [ ] Audit trade, transfer, coaching-change, promotion/relegation, and expansion-team handling.

### 14.2 Player props

- [ ] Verify player identifier and team assignment as of the prediction timestamp.
- [ ] Confirm projected role, starter status, minutes, usage, and lineup features are timestamp-valid.
- [ ] Reconcile prop definition and units across sportsbooks.
- [ ] Confirm DNP, inactive, early exit, void, and settlement rules.
- [ ] Avoid using final minutes, final usage, final lineup, or postgame player statistics in pregame features.
- [ ] Model dependence across correlated props when evaluating portfolio-level exposure.

### 14.3 Golf and tournament sports

- [ ] Separate pre-tournament, pre-round, in-round, and post-round information sets.
- [ ] Ensure strokes-gained, scoring, field-strength, and form features are finalized before the model timestamp.
- [ ] Confirm tournament/course identifiers, course rotations, tees, formats, and weather windows.
- [ ] Handle cuts, withdrawals, disqualifications, dead heats, each-way terms, and shortened events explicitly.
- [ ] Ensure tournament field/tee-time data were known at the claimed bet time.
- [ ] Do not use completed-round or final-tournament statistics in an earlier market model.
- [ ] Validate player-course history for name/ID continuity and small-sample shrinkage.

### 14.4 In-play markets

- [ ] Record exchange/book odds timestamp to sufficient resolution.
- [ ] Record model input timestamp and infer/measure data-feed latency.
- [ ] Apply realistic order/placement latency and market-suspension behavior.
- [ ] Confirm live state variables are only available at the decision time.
- [ ] Purge/embargo overlapping observations that share future label windows.
- [ ] Prevent multiple snapshots of the same event from leaking final outcomes across folds.
- [ ] Audit clock, score, possession/state, and feed-correction timestamps.

---

## 15. Automated data-quality tests

Run these tests in CI or scheduled pipeline monitoring.

### 15.1 Hard-fail tests

- [ ] No duplicate primary keys at declared table grain.
- [ ] No prediction row with `prediction_timestamp >= event_start_time` for pre-event models.
- [ ] No feature with `feature_available_at > prediction_timestamp`.
- [ ] No odds row with `odds_timestamp > bet_timestamp`.
- [ ] No label with `outcome_finalized_at <= prediction_timestamp`.
- [ ] No training observation timestamp later than test observation timestamp in any fold.
- [ ] No target/outcome columns in approved model feature list.
- [ ] No unexplained many-to-many join.
- [ ] No model pipeline transformer fitted outside the training fold.
- [ ] No closing-line field in an earlier-line model feature matrix.

### 15.2 Warning tests

- [ ] Missingness rate changes materially from historical baseline.
- [ ] Feature distribution shifts materially by date or source.
- [ ] Odds coverage falls below expected threshold.
- [ ] Number of events/markets deviates from expected schedule.
- [ ] New categorical values appear unexpectedly.
- [ ] Model feature importance changes sharply.
- [ ] Calibration slope/intercept deteriorates materially.
- [ ] CLV and model-to-market residuals diverge materially.
- [ ] Price snapshots become stale relative to normal latency.
- [ ] Source revision volume rises materially.

### 15.3 Reproducibility tests

- [ ] Rebuilding the same raw snapshot reproduces row counts and key aggregates.
- [ ] Rerunning the same code/version/seed reproduces predictions within tolerance.
- [ ] Each prediction can be traced to source records, feature versions, model version, calibration version, and odds record.
- [ ] A randomly sampled historical prediction can be reconstructed exactly as of its timestamp.
- [ ] Final evaluation uses only persisted, out-of-fold predictions.

---

## 16. Pre-deployment sign-off

### Data sign-off

- [ ] Raw source coverage, timestamp semantics, entity mapping, and revisions are documented.
- [ ] All model inputs have passed as-of availability checks.
- [ ] Odds are executable under the stated strategy assumptions.
- [ ] Outcome and settlement rules are correct for every target market.
- [ ] Leakage tests and timestamp assertions pass.

### Modeling sign-off

- [ ] Model selection used nested walk-forward validation or a documented equivalent.
- [ ] Calibration was fit only on prior/out-of-fold information.
- [ ] Final holdout results were not used for feature/model/threshold selection.
- [ ] Complex models beat simple and market baselines on appropriate proper scoring rules or demonstrate a defensible incremental use.
- [ ] Performance is stable across multiple contiguous folds and not driven by a single period.

### Strategy sign-off

- [ ] Edge threshold, staking, risk caps, and execution assumptions are frozen.
- [ ] No-vig conversion and EV calculations are reviewed.
- [ ] Results include uncertainty, drawdowns, turnover, CLV, and sensitivity analysis.
- [ ] Monitoring and rollback criteria are defined.
- [ ] Shadow-mode logging is operational before real capital deployment.

---

## 17. Fast red-flag list

Stop and investigate if any of the following is true:

- [ ] Random train/test splitting was used for a time-dependent betting model.
- [ ] The database contains only current/revised historical values with no as-of reconstruction.
- [ ] Closing odds appear in a model designed to bet opening or early prices.
- [ ] Features were standardized, imputed, selected, encoded, or calibrated on all data before splitting.
- [ ] A current game/event contributes to its own season-to-date or rolling statistic.
- [ ] Multiple snapshots from the same event appear across train and test without purging/group control.
- [ ] Backtest pricing is best available across books but the strategy has no mechanism to execute that best price.
- [ ] Edge threshold, market filter, feature set, or time range was chosen after observing final test ROI.
- [ ] Performance is excellent overall but weak or unstable by chronological fold.
- [ ] Results disappear when using only prices and information genuinely available at the stated timestamp.
- [ ] The model outperforms a strong market baseline dramatically without a clear, auditable reason.
- [ ] A historical prediction cannot be recreated from the data snapshot and code available at that point in time.

---

## 18. Minimum audit artifact package

Before publishing or deploying a strategy, save:

- [ ] Data dictionary and source-provenance report.
- [ ] Feature-availability matrix with as-of rules.
- [ ] Event/odds/outcome schema and primary-key definitions.
- [ ] Data-quality test results and exception log.
- [ ] Walk-forward fold definitions and fold-level sample counts.
- [ ] Nested tuning configuration and experiment ledger.
- [ ] Immutable out-of-fold prediction ledger.
- [ ] Calibration report and reliability plots.
- [ ] Market baseline and no-vig conversion documentation.
- [ ] Backtest assumptions, execution model, and settlement policy.
- [ ] Fold-level predictive, CLV, and financial performance report.
- [ ] Final holdout report.
- [ ] Model card, risk limits, deployment version, and rollback plan.

---

## Final certification

Use this declaration only when all material checks pass:

> For each recorded prediction and simulated wager, the research pipeline can reconstruct the information set, odds quote, feature values, model version, calibration state, decision rule, and settlement outcome as they existed at the documented prediction and execution timestamps. No post-decision information was used to construct features, fit transformations, select hyperparameters, calibrate probabilities, choose thresholds, or evaluate the final held-out period.
