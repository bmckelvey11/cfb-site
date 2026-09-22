**Superseded by** [feature-evaluation-framework.md](../../docs/feature-evaluation-framework.md)

# College Football Feature Research: Implementation Blueprint

## Purpose

This continuation turns the feature-evaluation framework into an implementable college football research system. The goal is to produce an auditable chain from raw CFBD data to point-in-time features, chronological predictions, market-relative tests, and production decisions.

The platform is not complete when it can display correlations or feature importance. It is complete when any claimed signal can be reconstructed, challenged, and evaluated without contaminating future tests.

## Separate research tracks

Maintain three linked but separately scored models:

| Track | Primary output | Question | Benchmark |
|---|---|---|---|
| Team strength | Latent offense, defense, special teams | How good is each unit now? | Prior and opponent-adjusted rating |
| Game forecast | Margin, total, and uncertainty | What outcome distribution is expected? | Football baseline and market |
| Betting decision | Bet, side, price, stake, or pass | Is the offered price actionable? | No-bet and incumbent policies |

CFBD describes PPA, WEPA, Elo, SRS, CORE, and win probability as models answering different questions rather than interchangeable ratings.[cite:242] Apply that principle internally: a play metric can improve team estimation without improving ATS predictions, and a strong game forecast can still fail after vig or poor execution.

## CFBD source map

CFBD and cfbfastR expose games, lines, drives, plays, advanced statistics, PPA, returning production, usage, transfers, coaches, venues, ratings, and other building blocks.[cite:230][cite:231][cite:232]

| Domain | Source | Derived features | Main risk |
|---|---|---|---|
| Games | Games/calendar | Opponent, venue, rest, result | Neutral-site and schedule corrections |
| Market | `/lines` | Spread, total, moneyline, dispersion | Historical timestamp semantics |
| Plays | `/plays` | PPA, success, pace, explosiveness | Corrections, clocks, missing plays |
| Drives | `/drives` | Points/drive, field position | Non-offensive and end-half drives |
| Advanced stats | `/stats/game/advanced` | Success, explosiveness, havoc | Definition/version drift |
| PPA | `/ppa/games`, `/ppa/teams` | Unit and pass/rush value | End-of-period aggregation leakage |
| WEPA | `/wepa/team/season` | Opponent-adjusted efficiency | Point-in-time reconstruction |
| Returning production | `/player/returning` | Returning usage and PPA | Transfer and offseason revisions |
| Players/portal | Player endpoints | QB continuity, portal production | Identity and effective-date resolution |
| Recruiting | Recruiting/talent endpoints | Roster-talent prior | Missing or reclassified players |
| Coaches | `/coaches` | Head-coach continuity | Coordinator data may need another source |
| Venues | `/venues` | Travel, altitude, surface | Neutral and temporary venues |
| Kicking | `/metrics/fg/ep` | Distance-adjusted kicker value | Sparse attempts and turnover |

Historical play rows include game and drive identifiers, teams, score, period, clock, field position, down, distance, play type, text, and PPA.[cite:233] CFBD line responses preserve provider-level open/current spreads and totals plus moneylines, but this does not eliminate the need to verify what was known at the intended decision timestamp.[cite:240]

## Warehouse layers

Use immutable raw data and versioned derived layers.

| Schema | Function | Example tables |
|---|---|---|
| `raw` | Exact source responses | `raw_cfbd_plays`, `raw_cfbd_lines` |
| `staging` | Typed source normalization | `stg_plays`, `stg_games`, `stg_lines` |
| `canonical` | Stable analytical grains | `fct_game`, `fct_team_game`, `fct_play` |
| `snapshot` | Historical information sets | `snap_team_week`, `snap_market_game_ts` |
| `features` | Versioned model inputs | `feat_team_form_v1`, `feat_matchup_v1` |
| `experiments` | Runs, folds, predictions, losses | `experiment_run`, `fold_prediction` |
| `betting` | Quotes, decisions, fills, settlements | `market_quote`, `bet_decision`, `bet_fill` |

Every raw load should record `ingested_at`, endpoint, parameters, response hash, source timestamp when available, and whether it is an original load, correction, or backfill. Never silently overwrite a corrected play or market record.

## Canonical grains

### Team-game

Use one row per team per game:

```text
fct_team_game
- game_id
- team_id
- opponent_id
- season
- week
- start_time_utc
- home_away_neutral
- points_for
- points_against
- offensive_plays
- defensive_plays
- offensive_drives
- defensive_drives
- is_fbs_opponent
- is_overtime
- source_available_ts
```

### Play

Use one row per play:

```text
fct_play
- game_id
- drive_id
- play_id
- offense_team_id
- defense_team_id
- period
- clock_seconds
- offense_score_before
- defense_score_before
- down
- distance
- yards_to_goal
- play_type
- yards_gained
- ppa
- success_flag
- explosive_flag
- sack_flag
- turnover_flag
- game_state_weight
- source_available_ts
- source_version
```

CFBD's success definition requires at least 50% of needed yards on first down, 70% on second, and 100% on third or fourth; scoring plays are successful unless explicitly failed.[cite:194] Store the definition version because other ecosystems use alternatives such as positive EPA.

### Market quote

Use one row per game, provider, market, side, and observation:

```text
market_quote
- game_id
- provider
- market_type
- side
- observed_at_utc
- line_value
- american_odds
- decimal_odds
- open_close_flag
- source_ingested_at
- quality_flag
```

Consensus should be a derived and versioned object—not a destructively stored replacement for provider prices.

### Prediction snapshot

```text
prediction_snapshot
- game_id
- prediction_ts
- horizon_id
- training_cutoff
- feature_set_version
- model_version
- margin_mean
- total_mean
- margin_scale
- total_scale
- home_win_probability
- prediction_created_at
```

`prediction_ts` is the historical decision cutoff. `prediction_created_at` records when the system generated the row, separating reconstructed backtests from genuine prospective forecasts.

## Point-in-time rule

Every feature row must satisfy:

```text
source_available_ts <= prediction_ts
```

A safe conceptual query is:

```sql
SELECT
    p.game_id,
    p.team_id,
    AVG(g.off_ppa_per_play) AS prior_off_ppa
FROM game_prediction_index p
JOIN fct_team_game g
  ON g.team_id = p.team_id
 AND g.start_time_utc < p.prediction_ts
 AND g.source_available_ts <= p.prediction_ts
GROUP BY 1, 2;
```

This rule must also govern opponent adjustment. A Week 4 team statistic adjusted using opponents' full-season ratings contains future information even if the team's raw games stop at Week 3.

## Sequential ratings

At each prediction cutoff:

1. Select completed games available before the cutoff.
2. Fit offense, defense, home-field, and season effects using only those games.
3. Shrink team effects toward preseason or population priors.
4. Produce a rating snapshot for every team.
5. Freeze that snapshot for the upcoming games.
6. Advance to the next cutoff and refit.

The output should be `team_rating_snapshot`, keyed by team and prediction time, rather than a single end-of-season rating joined backward.

## Feature registry

Each feature needs machine-readable lineage:

```yaml
feature_id: off_ppa_ewm_01
family: efficiency
entity_grain: team_prediction_snapshot
sources: [fct_play]
horizons: [sunday_open, wednesday_1800]
lookback:
  type: exponential
  half_life_games: 4
filters:
  exclude_kneels: true
  overtime: exclude
  fcs_policy: downweight
opponent_adjustment: sequential_v2
prior: preseason_offense_v3
missing_policy: hierarchical_impute
version: 1.0.0
status: candidate
```

Also store the expected direction, applicable targets, known confounders, first usable season, owner, and associated experiments.

## Validation calendar

Ordinary random cross-validation can train on future observations and test on the past. Time-series splitting preserves order and can insert a gap between training and test periods.[cite:256] College football needs a calendar-aware implementation because Saturday games share an information set and offseasons create large temporal gaps.

### Outer season folds

Use expanding, leave-one-season-forward tests:

| Fold | Training period | Test period |
|---|---|---|
| 1 | Start through 2018 | 2019 |
| 2 | Start through 2019 | 2020 |
| 3 | Start through 2020 | 2021 |
| … | All preceding seasons | Next season |

Treat unusual seasons as explicit regimes. Do not hide regime failures by reporting only a pooled average.

### Weekly simulation

Within each test season:

1. Freeze all information before the weekly cutoff.
2. Update ratings and feature snapshots.
3. Generate every game prediction for the slate.
4. Store predictions before attaching outcomes.
5. Advance one week.

Keep the whole football week together. Using a Thursday result to update a Saturday forecast must be a declared intraweek policy, not accidental access.

### Inner validation

Inside each outer training fold, perform:

- Feature construction and selection.
- Imputation and scaling.
- Window and shrinkage selection.
- Hyperparameter tuning.
- Probability calibration.
- Betting-threshold tuning, if included.

Nested validation is intended to keep feature selection and model choices within training data while preserving the outer fold for assessment.[cite:214][cite:217]

## Feature tournament

### Stage A: integrity

Check:

- Coverage by season, week, and team.
- Impossible and extreme values.
- Source-availability timestamps.
- Missingness reasons.
- Correlated-variable clusters.
- Definition stability.
- Football rationale and expected sign.

A correlation with points is useful for QA but cannot promote a feature.

### Stage B: football increment

Compare a locked football baseline with and without the candidate family. Require paired out-of-sample improvement, reasonable worst-fold behavior, and performance above negative controls.

### Stage C: market increment

Compare the decision-time market baseline against market plus candidate. Alternatively, predict the residual around the market. Historical CFB studies have reached different conclusions about whether rating systems add information beyond betting spreads, so the answer must be tested by era and timestamp.[cite:174][cite:179]

### Stage D: betting confirmation

Freeze the forecast, probability conversion, de-vigging, threshold, book universe, and staking. Only then examine CLV, ROI, drawdown, and fill realism.

## Paired ablation protocol

For family \(G\):

\[
M_0=\text{locked baseline}
\]

\[
M_1=\text{locked baseline}+G
\]

For each outer-fold game, store:

\[
d_g=L(y_g,\hat y_{g,M_1})-L(y_g,\hat y_{g,M_0}).
\]

When lower loss is better, negative mean \(d_g\) indicates improvement. Use the same games, folds, preprocessing policy, seeds, and tuning budget for both models.

Run two complementary tests:

- **Add-one-family:** Does the family improve a compact baseline?
- **Drop-one-family:** Does the completed model depend on the family after substitutes are included?

A family can pass the first and fail the second because another feature group absorbs the same signal.

## Correlated statistics

CFB features commonly overlap:

- PPA/EPA and yards per play.
- Success rate and first-down rate.
- Points per drive and offensive efficiency.
- Havoc, sacks, and tackles for loss.
- Recruiting talent and prior program strength.
- Plays per game and pace.

Permutation importance measures the score loss caused by shuffling a feature, but correlated substitutes can make important variables appear individually weak.[cite:157][cite:158] Conditional importance instead asks whether a feature adds information given related predictors.[cite:216][cite:222][cite:227]

Use this sequence:

1. Cluster variables by football meaning and correlation.
2. Test the whole family.
3. Compare compact representatives inside successful families.
4. Run grouped or conditional permutation importance on outer-fold predictions.
5. Prefer the simpler and more deployable representation when performance is effectively tied.

## Priority experiments

### Efficiency

**Hypothesis:** opponent-adjusted offensive and defensive PPA improve margin prediction beyond scoring margin and simple ratings.

Test:

- Overall PPA.
- Pass/rush split.
- Early-down split.
- Standard/passing-down split.
- Season-to-date, recency-weighted, and prior-blended versions.

PPA values plays in expected-points terms, but observed PPA remains descriptive and requires shrinkage and game-state treatment for future prediction.[cite:250][cite:251]

### Success and explosiveness

CFBD defines success rate as the share of plays meeting down-specific thresholds and explosiveness as average PPA on successful plays.[cite:194] Compare:

1. PPA only.
2. PPA plus success rate.
3. PPA plus explosiveness.
4. PPA plus both.
5. PPA plus both and a constrained interaction.

Evaluate whether additions improve the predicted mean, residual scale, or both. Explosiveness may matter more for distribution tails than average margin.

### Pace and possessions

For totals, derive:

- Neutral seconds per play.
- Plays per competitive drive.
- Pass rate and incompletion tendency.
- Fourth-down aggressiveness.
- Opponent-adjusted expected possessions.
- End-of-half pace.

Raw plays per game mix intrinsic pace with opponents, turnovers, overtime, field position, and game script. Test it only as a benchmark against context-adjusted possession features.

### Finishing drives

Compare raw and shrunk:

- Points per scoring opportunity.
- Touchdown rate in scoring territory.
- Fourth-down conversion and decision profile.
- Field-goal attempt profile.
- Distance-adjusted kicker value.

CFBD provides a field-goal expected-points endpoint, supporting difficulty-adjusted kicker evaluation instead of raw conversion percentage.[cite:231]

### Havoc and turnover process

Compare:

1. Realized turnover margin.
2. Havoc components.
3. Expected-turnover estimate.
4. Turnover-luck residual.

The objective is to determine whether process variables survive future folds better than volatile realized outcomes. Do not assume the luck residual must reverse in the next game; test its horizon empirically.

### Roster and priors

Test:

- Returning usage and PPA.
- QB continuity and prior performance.
- Recruiting talent.
- Incoming and outgoing transfer production.
- Offensive-line and defensive-position continuity.
- Coach/coordinator continuity.
- Prior latent unit strength.
- Prior quality multiplied by continuity.

A study using 2006–2018 major-conference teams found previous Sagarin strength, recruiting, returning starters, and returning-QB status predictive of season performance; previous performance was its strongest single selected predictor.[cite:173] Re-estimate these effects for game-level targets and the modern transfer environment rather than importing old coefficients.

## Early-season state model

Weeks 0–4 deserve a dedicated prior/current blend. For feature family \(k\):

\[
\theta_{t,k}=w_{t,k}\hat{\theta}_{current,k}+(1-w_{t,k})\theta_{prior,k}.
\]

Estimate \(w_{t,k}\) inside training seasons as a function of plays, drives, opponent quality, week, and roster continuity. Passing efficiency, kicking, havoc, and explosiveness do not need to share one fade schedule.

Attach uncertainty to each team estimate. New quarterbacks, coordinator changes, major portal churn, and few observed possessions should widen the predictive distribution rather than only alter the mean.

## Model the variance

A betting model should estimate:

\[
Y_g\sim\mathcal{D}(\mu_g,\sigma_g).
\]

Potential predictors of \(\sigma_g\) include:

- Absolute expected margin.
- Combined explosiveness.
- Expected possessions.
- Quarterback uncertainty.
- Early-season status.
- Turnover-prone profiles.
- Weather uncertainty.
- FBS/FCS mismatch.
- Coaching transition.

Evaluate CRPS, log likelihood, interval coverage, and sharpness. A feature can be useful because it improves uncertainty even when MAE barely moves.

## Interaction budget

Use a small, hypothesis-driven set:

| Interaction | Rationale | Likely target |
|---|---|---|
| Pass offense × pass defense | Passing matchup | Spread/total |
| Rush offense × front defense | Run-game matchup | Spread/team total |
| Explosiveness × explosive plays allowed | Tail risk | Variance/alternates |
| Pace × opponent pace | Joint possessions | Total |
| Havoc × QB experience | Pressure vulnerability | Spread/turnovers |
| OL continuity × defensive havoc | Cohesion against disruption | Early spread |
| Wind × passing tendency | Weather exposure | Total |
| Prior quality × returning production | Value of retained production | Early-season mean |

An all-pairs interaction search creates too many trials. Use regularization or hierarchical shrinkage even for the predeclared set.

## Missingness taxonomy

| Type | Example | Treatment |
|---|---|---|
| Structural | No current-season games | Prior plus sample-size flag |
| Coverage | Historical PBP absent | Hierarchical estimate plus coverage flag |
| Not applicable | No field-goal attempts | Opportunity-aware prior, not zero |
| Delayed | Status unknown at cutoff | Preserve unknown state |
| New entity | Transfer QB without FBS history | Player/team prior with wide uncertainty |
| Source error | Corrupt clock or duplicate play | Repair/exclusion flag |

A missingness indicator can be useful only if the same missing state would exist in production. Historical backfill quirks must not become predictors.

## Feature selection tools

Preferred:

- Group add-one and drop-one ablation.
- Nested forward selection among feature families.
- Regularized linear models.
- Group lasso or hierarchical shrinkage.
- Conditional/grouped permutation importance.
- Stability selection inside training folds.

Sequential forward selection greedily adds the feature producing the best cross-validated score, while backward selection removes features from a full set; they can yield different subsets.[cite:260][cite:261] Feed these methods feature groups and chronological folds, not individual raw columns with random CV.

Supporting but insufficient alone:

- SHAP.
- Partial dependence or accumulated local effects.
- Coefficient paths.
- Mutual information.
- Univariate correlations.
- Tree impurity importance.

SHAP explains use inside one fitted model; it does not prove incremental, stable, market-relative value.

## Negative controls

Include controls designed to fail:

- Gaussian noise matched to candidate variance.
- Candidate values permuted within season.
- Random team labels.
- Random rolling windows.
- Arbitrary threshold indicators.
- A deliberately leaked future feature as a sentinel.

Compare every candidate with the empirical distribution of control improvements. If noise frequently passes, tighten the promotion gate. If the leakage sentinel does not dominate, investigate whether the test pipeline is functioning correctly.

## Stability grid

Report every candidate by:

- Season and outer fold.
- Week band: 0–3, 4–7, 8–conference championship, bowls.
- FBS–FBS versus FBS–FCS.
- Conference or competition tier.
- Home, away, and neutral.
- Favorite/underdog and spread band.
- Total band.
- Prediction horizon.
- Market provider or consensus definition.
- Weather regime.
- Returning-QB status.
- Expected mismatch level.

A feature useful only in one declared segment can be retained as `KEEP_TARGETED`, but the segment must be chosen within training data and confirmed later.

## Candidate scorecard

Do not hide everything in one number. Display:

| Dimension | Measurement |
|---|---|
| Predictive gain | Paired OOS change in primary loss |
| Uncertainty | Block-bootstrap interval |
| Market increment | Gain beyond same-time market |
| Temporal consistency | Positive-fold proportion |
| Worst case | Worst fold and lower confidence bound |
| Definition stability | Share of reasonable variants improving |
| Selection stability | Inner-fold selection frequency |
| Calibration effect | Slope/intercept and local reliability change |
| Data quality | Coverage, lag, revision rate |
| Complexity | Compute, latency, and number of inputs |
| Economics | Frozen-policy CLV and ROI confirmation |

For a sortable research score, use a multiplicative form so data-quality or robustness failure cannot be averaged away:

\[
S_j=G_j\times C_j\times R_j\times D_j,
\]

where \(G\) is predictive gain, \(C\) confidence, \(R\) robustness, and \(D\) deployability. Keep market increment as a separate hard gate for features labeled as betting signals.

## Promotion gates

### Integrity

Required:

- Point-in-time audit passes.
- Formula reproduces from versioned raw data.
- Missingness and coverage are documented.
- No final-test information enters construction.

Failure: `INVALID`.

### Predictive increment

Required:

- Average paired outer-fold loss improves.
- Improvement exceeds typical negative-control gains.
- Signal is not confined to one season.
- Worst-fold harm is acceptable.

Failure: `REJECT` or `MONITOR`.

### Redundancy

Required:

- Family adds value after a compact baseline.
- A simpler representative captures most stable value.
- Contribution survives grouped/conditional importance.

Failure: `REDUNDANT`.

### Market increment

Required for betting classification:

- Improvement beyond the decision-time market.
- No material calibration harm in wagered regions.
- Result survives reasonable consensus/de-vig variants.

Failure: retain as a football-rating feature only.

### Economic confirmation

Required:

- Frozen-policy CLV and ROI are directionally consistent.
- Profit is not dominated by a few games.
- Realistic slippage does not erase the edge.
- Prospective performance remains plausible.

Failure: `RESEARCH_ONLY`.

## Promotion matrix

| Forecast gain | Market gain | Economic evidence | Decision |
|---|---|---|---|
| Positive | Positive | Positive or uncertain | Prospective candidate |
| Positive | Positive | Negative, small sample | Keep forecast feature; inspect variance/execution |
| Positive | None | Any | Rating feature, not demonstrated betting edge |
| None | Positive | Positive | Investigate timing, line shopping, or leakage |
| Negative | Positive CLV only | Mixed | Execution signal, weak forecast feature |
| Negative | Negative | Positive | Likely outcome noise; reject pending replication |

## Experiment manifest

```yaml
experiment_id: cfb_margin_efficiency_0042
hypothesis: >
  Opponent-adjusted pass and rush PPA add margin information
  beyond SRS and Wednesday consensus spread.
target:
  name: home_margin
  distribution: student_t
horizon:
  name: wednesday_1800_et
sample:
  start_season: 2014
  end_season: 2025
  classifications: [fbs]
outer_validation:
  method: expanding_season
  group: football_week
  untouched_season: 2025
inner_validation:
  method: rolling_week
  gap_weeks: 1
baseline:
  version: margin_market_baseline_v3
candidate_groups:
  - adj_off_pass_ppa
  - adj_off_rush_ppa
  - adj_def_pass_ppa
  - adj_def_rush_ppa
models: [ridge, lightgbm]
primary_metric: crps
secondary_metrics: [mae, rmse, calibration_slope]
market:
  provider_set_version: consensus_v2
  devig_method: multiplicative
negative_controls:
  - within_season_permutation
  - gaussian_noise_matched_variance
promotion_policy: feature_gate_v2
```

Store the manifest hash with every prediction and result.

## Research database

Suggested experiment tables:

```text
experiment_run
- experiment_id
- manifest_hash
- created_at
- hypothesis
- target
- horizon
- baseline_version
- candidate_version
- code_commit
- data_snapshot
- trial_number
- status

fold_prediction
- experiment_id
- fold_id
- game_id
- prediction_ts
- y_true
- baseline_prediction
- candidate_prediction
- baseline_loss
- candidate_loss
- market_line
- market_price

feature_result
- experiment_id
- feature_family
- primary_loss_delta
- ci_low
- ci_high
- positive_fold_rate
- worst_fold_delta
- market_loss_delta
- calibration_delta
- clv_delta
- roi_delta
- final_decision
```

## Dashboard

### Leaderboard

Show:

- Feature family/version.
- Target and horizon.
- Baseline.
- OOS loss delta and interval.
- Market-relative delta.
- Calibration delta.
- Positive-fold share.
- Worst season.
- Data-quality grade.
- Trial count.
- Status.

### Feature detail

Include:

1. Definition and lineage.
2. Coverage and missingness.
3. Distribution by season/week.
4. Correlation cluster.
5. Add-one and drop-one results.
6. Fold-level paired loss.
7. Market-conditioned result.
8. Calibration diagnostics.
9. Parameter-neighborhood stability.
10. Negative-control percentile.
11. CLV/ROI confirmation.
12. Decision history.

## Twelve-week build plan

### Weeks 1–2

- Define margin, total, probability, and movement targets.
- Choose one decision timestamp.
- Build immutable CFBD ingestion.
- Audit line history and timestamp semantics.

### Weeks 3–4

- Build game, team-game, drive, play, and quote grains.
- Reconcile neutral sites and overtime.
- Implement play exclusions and game-state labels.
- Add data-quality tests.

### Weeks 5–6

- Build point-in-time team-week snapshots.
- Implement sequential offense/defense ratings.
- Add preseason priors and prior/current blending.

### Weeks 7–8

- Fit structural, football-only, and market baselines.
- Implement probabilistic margin/total scoring.
- Lock outer and inner folds.

### Weeks 9–10

- Test efficiency, success, explosiveness, pace, havoc, and roster families.
- Add negative controls.
- Produce paired intervals and redundancy analysis.

### Weeks 11–12

- Convert forecast distributions into betting probabilities.
- Build de-vigged market comparisons.
- Freeze selection policies.
- Evaluate CLV, ROI, drawdown, and execution assumptions.
- Register survivors for prospective monitoring.

## Definition of done

The system is operational when it can reproduce this chain:

1. Raw response and ingestion metadata.
2. Canonical game/play/quote record.
3. Point-in-time team and market snapshot.
4. Exact feature formula and version.
5. Fold-specific training information.
6. Model and hyperparameters.
7. Game-level prediction and loss.
8. Paired baseline comparison.
9. Market-relative comparison.
10. Feature decision and trial history.
11. Frozen betting translation.
12. Prospective monitoring result.

The governing rule is simple: **promote a college football statistic only when its incremental value survives chronology, correlated alternatives, the betting market, reasonable specification changes, and later data.**
