**Superseded by** [feature-evaluation-framework.md](../../docs/feature-evaluation-framework.md)

# Finding Predictive College Football Statistics

## Executive answer

The goal is not to identify statistics that merely describe good college football teams. It is to identify **point-in-time variables that repeatedly improve future predictions beyond information already contained in a strong baseline and the betting market**.

A statistic should earn production status only when it:

- Was genuinely available at the prediction timestamp.
- Improves an appropriate out-of-sample forecast score.
- Adds information beyond simpler, correlated statistics.
- Adds information beyond the betting line available at that time.
- Remains useful across seasons, weeks, conferences, and nearby definitions.
- Improves the probabilities or predictive distribution in the region where bets are actually placed.
- Eventually converts into realistic CLV or net return without relying on one season or a few outliers.

College football makes this difficult because teams play short seasons, schedules are highly unbalanced, roster turnover is substantial, early-season samples are thin, and there are many correlated ways to represent the same underlying team quality. CFBD's opponent-adjusted WEPA family is explicitly designed to separate performance from opponent quality and home-field context, while regularization limits extreme estimates from small or unbalanced samples.[cite:170] Historical research also shows that rating systems can predict outcomes individually while adding no information beyond the final betting spread, which is why market-conditioned testing is essential.[cite:179]

## Define “predictive” precisely

A feature does not have one universal predictive value. Its usefulness depends on five elements:

1. **Target:** straight-up win, margin, total, team total, cover, or a full score distribution.
2. **Forecast horizon:** preseason, Sunday open, midweek, game day, or live.
3. **Information set:** exactly what was known at the decision timestamp.
4. **Baseline:** naive average, football-only model, opening line, or existing production model.
5. **Loss function:** MAE, RMSE, log loss, Brier score, CRPS, or another metric tied to the target.

A statistic may predict final margin but not ATS returns. It may predict closing-line movement but not the game result. It may matter in Weeks 0–3 and become redundant after current-season efficiency stabilizes. It may help totals but hurt spreads. Every feature result should therefore be stored with its target, timestamp, baseline, model family, seasons, and validation design.

## Separate four questions

Each candidate statistic should face four distinct tests:

| Question | Comparison | What success means |
| --- | --- | --- |
| Does it describe team strength? | Naive model vs. naive + feature | It contains basic predictive signal |
| Does it improve a football model? | Football baseline vs. baseline + feature | It adds information beyond known football metrics |
| Does it beat the market information set? | Decision-time market vs. market + feature | It contains incremental information not yet priced |
| Can it support betting? | Locked forecast model plus bet policy | Its forecast value survives vig, thresholds, timing, and execution |

Do not collapse these into one “feature importance” value. A feature can pass the first two and fail the market test. That is still useful for team ratings, simulations, and missing-line games, but it should not be labeled a betting edge.

## Choose targets first

### Spread and margin

For a home-team margin target, where $g = game$


$$
y_g = \text{home points}_g-\text{away points}_g.

$$

The model can predict the conditional mean margin, a full margin distribution, or the residual around a decision-time home-team spread:

$$
r_g^{margin}=y_g-L_g^{decision}.
$$

Use MAE and RMSE for point forecasts. Prefer log likelihood or CRPS if the model estimates a full predictive distribution, because cover probability depends on both the mean and uncertainty.

### Totals

### Totals target

**Outcome.** For game *g*, the quantity being predicted is the combined final score:

$$
y_g = \text{home points}_g + \text{away points}_g
$$

Overtime points count, because the book grades totals on the final score including OT.

**What $T_g^{\text{decision}}$ is.** It is the market total (the over/under line) for game *g*, taken at the moment the bet decision is made. Examples: 55.5 at Tuesday's open, or 53.0 an hour before kickoff when you place the bet. Three things define it:

- **Which book.** This could be one named book, or a consensus or "book fair" line across several books. Pick one and use the same one for every game.
- **Which timestamp.** It must be a price you could actually have bet then, rebuilt from line history at that time. Using the closing line when the decision was made earlier is leakage. It also fails the hard gate in the [model evaluation standard](docs/model-evaluation-standard.md) that prices be reconstructible at decision time.
- **What it means.** $T_g^{\text{decision}}$ is roughly the market's median forecast of $y_g$ at that moment. It is the line the over/under is priced so that each side wins about half the time, before the vig. It already contains everything the market knew then: team strength, pace, injuries, weather forecasts, and public money.

**Market-residual target.**

$$
r_g^{\text{total}} = y_g - T_g^{\text{decision}}
$$

This is how far the actual score landed above (+) or below (−) the line you could bet. A game that closed at 55.5 and finished 48 has $r = -7.5$, so the under won.

**Why model the residual instead of $y_g$.** The market total already explains most of the variation in the actual total. A model trained on $y_g$ spends its capacity relearning what the line already knows. A model trained on $r_g$ only earns credit for information the market missed, and that is the only kind of information that wins bets. If $r_g$ cannot be predicted from pre-game features, the model has no edge, however well it predicts raw points.

### What features need to capture

Totals features usually need to describe some of these:

- **Possessions:** tempo, plays per game, clock management
- **Points per possession:** offensive and defensive efficiency
- **Explosiveness:** long-play rate
- **Finishing:** red-zone touchdown vs. field-goal rate
- **Weather:** wind and precipitation
- **Game-script interaction:** a lopsided spread means the leader runs clock and the trailer speeds up

### Mean vs. variance

Turning a residual forecast into an over/under probability takes two parts:

1. **Mean.** The expected residual: which side of the line the model leans, and by how much.
2. **Spread.** How uncertain that residual is, usually as the variance or the full distribution.

Take two games where each forecast is 3 points under the line. If one has a residual SD of 10 and the other 16, their $P(\text{under})$ values differ. That changes the edge and the Kelly stake.

A variable can improve the mean forecast and do nothing for the variance model. It can also do the reverse: wind barely moves the mean after the market adjusts, but it may change the variance. So test each feature on both parts separately:

- **Mean:** MAE or RMSE of $r_g$
- **Variance:** out-of-sample correlation of predicted variance with $r_g^2$, or CRPS and interval coverage

### Win and cover probabilities

For binary outcomes, evaluate probability forecasts with log loss and Brier score, then inspect calibration intercept, calibration slope, and reliability by probability band. Betting research has found calibration-based model selection more economically useful than accuracy-based selection in an NBA experiment, illustrating why classification accuracy alone is a poor betting-model objective.[cite:51][cite:54]

Cover labels discard useful information: winning by 1 point and missing by 30 points are both zeroes. A stronger pipeline usually models margin or its distribution first, then converts it into cover and moneyline probabilities.

### Line movement

Create a separate target for information discovery:

$$
r_g^{move}=L_g^{close}-L_g^{decision}.
$$

For totals, substitute the total line. This distinguishes a feature that anticipates the market from one that predicts the final result. Keep both outcomes because:

- A feature predicting line movement may be useful for bet timing.
- A feature predicting results after controlling for the line may represent fundamental residual signal.
- A feature predicting both is especially promising.
- A feature predicting neither should not survive because of an attractive in-sample narrative.

## Point-in-time data contract

Feature research is invalid unless each row can answer: **What was known for this game at this prediction timestamp?** CFBD itself warns that training features should include only games before the prediction week.[cite:187] Feature selection, preprocessing, imputation, scaling, and tuning must also occur inside training folds; selection on the complete dataset leaks test information and inflates performance.[cite:214][cite:215][cite:217]

For every feature, store:

| Field | Example |
| --- | --- |
| `game_id` | Stable CFBD game identifier |
| `prediction_ts` | Wednesday 18:00 ET |
| `source_available_ts` | First verified availability |
| `through_game_id` | Last game included in aggregation |
| `season` / `week` | Football calendar keys |
| `feature_version` | Formula and transformation version |
| `source_version` | API/raw-data snapshot |
| `window_definition` | Last 4 games, season-to-date, EWMA, etc. |
| `garbage_time_rule` | Exact filter version |
| `opponent_adjustment_version` | Rating algorithm and fit cutoff |
| `missing_reason` | Bye, no plays, unavailable field, bad feed |

Do not reconstruct a Week 5 feature using an end-of-season table, even if the table contains a `week` column. Recalculate from event-level data with a cutoff or use a verified historical snapshot.

## College football baseline ladder

Feature value should be measured against a ladder of increasingly difficult baselines.

### Baseline 0: structural

Include only:

- Home, away, and neutral site.
- Season and week.
- FBS/FCS matchup type.
- Rest days and bye indicators.
- A pooled home-field estimate.

Home advantage is real but variable; studies have estimated different magnitudes depending on era and specification, including an overall 4.1-point estimate in a 12-season channel-specific model, while broader work finds declining home advantage at high collegiate levels.[cite:203][cite:207] Treat team-specific home effects with shrinkage rather than raw averages.

### Baseline 1: team strength

Add a compact, opponent-adjusted team-strength layer:

- Offensive rating.
- Defensive rating.
- Special-teams rating if reliable.
- Recent prior-season strength.
- Schedule-adjusted scoring margin or SRS.

CFBD's SRS jointly reconciles scoring margins and opponent strength, caps extreme margins, adjusts home field, and yields a point-based descriptive team rating.[cite:197] This is useful as a baseline but should not automatically be included alongside many components derived from the same games without checking redundancy.

### Baseline 2: preseason priors

Add:

- Returning production by passing, rushing, and receiving.
- Multi-year recruiting talent.
- Transfer additions and losses.
- Quarterback continuity and projected starter quality.
- Coaching/coordinator continuity.
- Prior multi-year program strength.

College football's short schedule and roster churn make preseason priors especially important early. Public SP+ methodology has used returning production, recent recruiting, and recent program history, with returning production and the prior rating comprising most of the projection in the cited version.[cite:212] CFBD exposes returning PPA and usage components for passing, receiving, and rushing, allowing more granular continuity features than one headline percentage.[cite:190]

### Baseline 3: current-season efficiency

Add broad current-season families:

- Opponent-adjusted EPA/PPA per play.
- Opponent-adjusted success rate.
- Explosiveness.
- Run/pass efficiency splits.
- Standard-down and passing-down performance.
- Expected possessions or pace.

CFBD defines PPA as the change in predicted points attributable to a play, success rate using down-specific yardage thresholds, explosiveness as average PPA on successful plays, and havoc as defensive disruption events.[cite:194] Its WEPA output includes opponent-adjusted offense and defense for EPA, success rate, rushing-line measures, and explosiveness.[cite:170][cite:183]

### Baseline 4: decision-time market

Use the actual line available at the intended betting timestamp:

- Consensus spread and total.
- No-vig moneyline probability.
- Book dispersion.
- Opener-to-decision movement.
- Quote age and number of contributing books.

This is the decisive benchmark for betting research. In one historical analysis of 1,582 college football games, combinations of computer ratings predicted outcomes but lost joint significance after the final Las Vegas spread was included.[cite:179] A newer metamodel using 29 rating systems reported statistically significant information alongside the opening line, illustrating that the answer can depend on era, line timestamp, data, and model design.[cite:174]

### Baseline 5: production model

The final test is whether the feature improves the current system, not merely an intentionally weak comparison. Freeze the production feature set, hyperparameter policy, calibration method, and folds before testing a candidate.

## Candidate feature families

### Efficiency

Start with opponent-adjusted offensive and defensive PPA/EPA per play. Split into passing and rushing, but test the total family first. Efficiency features often subsume traditional box-score variables because they account for down, distance, field position, and scoring value.

Candidate definitions:

- Season-to-date opponent-adjusted offensive PPA/play.
- Season-to-date opponent-adjusted defensive PPA/play allowed.
- Passing and rushing components.
- Early-down PPA.
- Standard-down and passing-down PPA.
- Neutral-game-script PPA.
- Exponentially weighted recent PPA.
- Stable prior/current blend.

Test whether passing and rushing splits add value after total efficiency. If not, keep the compact total measure. If they help only through interactions with the opponent's defensive splits, label them matchup features rather than universal team-strength features.

### Consistency and success rate

Success rate captures how often an offense stays on schedule, while explosiveness captures the magnitude of successful plays.[cite:194] Test:

- Overall offensive and defensive success rate.
- Standard-down success.
- Passing-down success.
- Early-down success.
- Short-yardage power success.
- Stuff rate and opportunity rate.
- Drive success or first-down rate.

Evaluate whether success rate adds information after PPA. The two are related but conceptually different: a team can generate efficient averages through rare explosive plays while remaining inconsistent. Totals may respond differently to this tradeoff than spreads.

### Explosiveness and tails

Means alone can hide the variance relevant to alternate spreads and totals. Test:

- Explosiveness as PPA on successful plays.
- Explosive pass and rush rates.
- Explosive plays allowed.
- Distribution quantiles of play PPA.
- Rate of negative plays and very high-value plays.
- Variance or robust dispersion of play-level PPA.

Explosiveness should be paired with opportunity and success frequency. A team with one huge play in a small sample should not be treated like a consistently explosive offense. Apply empirical-Bayes or equivalent shrinkage to sparse rates.

### Pace and possessions

For totals, pace is not simply seconds per play. Build an expected-possession layer using:

- Plays per competitive drive.
- Seconds per play by game state.
- No-huddle rate if reliably observed.
- Pass rate and incompletion tendency.
- Fourth-down aggressiveness.
- Expected turnover on downs.
- Opponent pace interaction.
- End-of-half behavior.

Separate **intrinsic pace** from **observed play volume**. Raw plays per game are contaminated by opponent pace, overtime, field position, turnovers, and game script. Estimate pace in neutral situations and test whether it improves expected possessions after controlling for opponent behavior.

### Finishing drives

Test scoring conditional on reaching scoring territory:

- Points per opportunity.
- Touchdown rate inside the opponent 40 or red zone.
- Field-goal attempt and conversion profile.
- Fourth-down decision quality.
- Opponent finishing defense.

These variables can be noisy because each team gets relatively few qualifying drives. Compare raw season rates with shrunk estimates and multi-year priors. For kickers, distance-adjusted expected value is preferable to raw field-goal percentage because attempt difficulty varies; CFBD demonstrates a distance-based expected-points approach for this purpose.[cite:193]

### Havoc and turnovers

CFBD defines havoc through tackles for loss, forced fumbles, interceptions, and pass breakups.[cite:194] Test stable and unstable components separately:

- Pressure/sack proxies and tackles for loss.
- Passes defended.
- Forced fumbles.
- Interceptions.
- Fumble recoveries.
- Turnover-worthy events if available.
- Expected versus realized turnovers.

Raw turnover margin is highly outcome-linked but mixes repeatable skill with randomness. Prefer process features—pressure, passes defended, forced-fumble opportunities—and regress realized recoveries and interceptions toward expectation. Test whether a turnover-luck residual predicts reversion rather than extending the observed rate.

### Field position and special teams

Candidate features include:

- Starting field position by offense and defense.
- Punt net value and opponent-adjusted punt value.
- Kickoff touchback and return value.
- Distance-adjusted field-goal value.
- Return efficiency with strong shrinkage.
- Hidden-yardage contribution.

Special-teams samples are small and individual personnel matter. Start with a group test; retain granular components only if their out-of-sample contribution persists.

### Personnel and continuity

College football differs from professional leagues because talent and continuity change sharply between seasons. Test:

- Returning offensive and defensive production.
- Returning passing PPA and usage.
- Quarterback starts, attempts, efficiency, and transfer status.
- Offensive-line starts or snap continuity if available.
- Returning receiving usage concentration.
- Defensive returning production by position group.
- Incoming transfer usage, rating, and prior performance.
- Recruiting talent by position and class age.
- Coordinator and head-coach continuity.

Returning production should interact with previous quality. Returning 80% of a poor unit does not imply the same benefit as returning 80% of an elite one. Build separate `prior_quality`, `continuity`, and `quality × continuity` variables.

### Context and environment

Test these after the core team-quality model is stable:

- Rest and short week.
- Consecutive road games.
- Travel distance and time-zone change.
- Neutral-site indicator and venue familiarity.
- Temperature, wind, precipitation, and surface.
- Conference familiarity.
- Rivalry or rematch only with defensible definitions.
- Postseason and bowl indicators.

Home-field research indicates that crowd effects, familiarity, weather, and travel can operate through different scoring channels, so home-field adjustments can be modeled separately for the home offense and away offense rather than as one constant margin shift.[cite:203] Avoid generic “situational trends” created by trying many arbitrary combinations.

### Market features

Market variables can improve predictions while reducing interpretability about football fundamentals:

- Opening spread and total.
- Current spread and total.
- No-vig moneyline.
- Movement magnitude and velocity.
- Cross-book dispersion.
- Staleness and quote count.
- Difference between sharp and recreational books.

Create separate model tracks:

1. **Pure football model:** useful for power ratings and independent price discovery.
2. **Market-assisted model:** best forecast given current prices.
3. **Market-residual model:** predicts what remains after the decision-time line.

Do not mix these objectives when declaring a football statistic important.

## Feature construction variants

Each football concept should be tested through a small, predeclared set of reasonable estimators rather than dozens of mined variants.

### Time windows

For each family, compare:

- Prior season only.
- Current season-to-date.
- Last 3–4 games.
- Exponentially weighted history.
- Hierarchical prior plus current season.
- Multi-year decay.

Do not assume recent form is superior. Short windows react quickly but have high variance; expanding windows stabilize estimates but adapt slowly to quarterback changes, injuries, transfers, and coordinator changes.

### Shrinkage

For team statistic \(x_t\), a simple reliability blend is:

$$
\tilde{x}_t=w_t x_t+(1-w_t)\mu_t,
$$

where \(\mu_t\) is a preseason, conference, or national prior and \(w_t\) rises with effective sample size. Estimate the weighting inside training data rather than choosing a visually attractive fade schedule on the final sample.

Use stronger shrinkage for:

- Early-season rates.
- Explosive plays.
- Turnovers.
- Fourth downs.
- Field goals and returns.
- Team-specific home field.
- FCS teams or incomplete data.

### Opponent adjustment

Raw statistics often measure schedule as much as team ability. CFBD explicitly recommends opponent-adjusted EPA, success rate, and rushing measures for predictive modeling.[cite:188] Compare:

- Raw feature.
- Opponent-adjusted feature.
- Opponent- and venue-adjusted feature.
- Joint offense/defense network estimate.

Fit opponent adjustments only with games available before the prediction timestamp. End-of-season opponent quality cannot be used retrospectively in a Week 3 forecast unless it was generated through an honest sequential model.

### Game-state treatment

Test at least:

- All eligible plays.
- Competitive-game-state plays.
- Neutral-script plays.
- Score/time weighted plays.
- Excluding kneels and obvious clock-kill plays.

Garbage-time filters can remove contamination but may also discard information about depth and mismatch ability. Treat the definition as a tunable research choice selected inside training folds, not a universal truth.

## Experimental design

## Outer walk-forward evaluation

Use seasons or chronological week blocks as outer test folds. A practical design could be:

- Train through season \(Y-1\), test season \(Y\).
- Or train through Week \(W-1\), test Week \(W\), grouped across seasons.
- Preserve the newest complete season as an untouched final confirmation set.
- After launch, add a prospective-only evaluation stream.

Walk-forward validation repeatedly fits on the past and forecasts the future, preserving temporal order.[cite:224] Random game-level cross-validation is inappropriate because later-season team information can leak into earlier games and observations from the same team-season are dependent.

## Inner model selection

Inside each outer training set:

1. Construct only point-in-time features.
2. Fit imputation and scaling.
3. Select features or families.
4. Tune hyperparameters.
5. Choose transformations and shrinkage.
6. Fit probability calibration.
7. Choose betting thresholds if economic evaluation is part of the experiment.

Nested validation keeps all data-dependent decisions inside training data and reserves the outer fold for model assessment.[cite:214][cite:217][cite:223]

## Paired candidate tests

For each family \(G\):

$$
M_0 = \text{locked baseline},
$$

$$
M_1 = \text{locked baseline}+G.
$$

Generate both predictions for exactly the same outer-fold games. Store observation-level loss differences:

$$
d_g=L(y_g,\hat{y}_{g,M_1})-L(y_g,\hat{y}_{g,M_0}).
$$

Negative average \(d_g\) means the candidate improves a loss where lower is better. Use season- or week-block bootstrap intervals rather than treating every game as fully independent.

Run both:

- **Add-one-family:** tests whether the family improves a compact baseline.
- **Drop-one-family:** tests whether the final model relies on it after all substitutes are present.

The two answers can differ. A family can be useful when added early but redundant in the completed model.

## Correlated features

College football metrics are heavily redundant:

- EPA and yards per play.
- Success rate and first-down rate.
- Points per drive and offensive efficiency.
- Sacks, tackles for loss, and havoc.
- Recruiting talent and prior team strength.
- Plays per game and pace.

Standard permutation importance measures loss increase after shuffling a feature, but correlated substitutes can distort individual rankings.[cite:157][cite:158] Conditional permutation methods preserve relationships with other variables and ask for importance given the remaining features.[cite:216][cite:222][cite:227]

Recommended order:

1. Cluster correlated variables by football concept and empirical correlation.
2. Test the entire family.
3. If useful, compare compact representatives inside that family.
4. Use conditional or grouped permutation importance on held-out folds.
5. Prefer the cheapest, most stable, most interpretable representative when performance is tied.

## Model-family robustness

A real feature should not exist only because one algorithm happens to exploit noise. Test candidates in at least:

- Regularized linear or generalized linear model.
- Tree boosting model.
- Optional Bayesian or hierarchical model aligned with the problem.

Linear models reveal stable signed relationships and provide a difficult simplicity benchmark. Boosting can capture thresholds and interactions. Hierarchical models are useful for partial pooling across teams, conferences, and seasons.

Do not require identical importance rankings across algorithms. Require the feature family to improve honest forecasts often enough that its value is not an artifact of one flexible learner.

## Metrics and decision gates

### Forecast metrics

| Output | Primary | Supporting |
| --- | --- | --- |
| Margin mean | MAE, RMSE | Mean error, residual SD |
| Total mean | MAE, RMSE | Bias by total band and weather |
| Margin/total distribution | Log likelihood, CRPS | Interval coverage, sharpness |
| Win or cover probability | Log loss, Brier | Calibration slope/intercept |
| Line movement | MAE/RMSE or sign score | Calibration of move probability |

Use the metric that matches the output. Avoid selecting on ATS hit rate because it discards magnitude and depends on one line snapshot.

### Market-conditioned metrics

For binary outcomes, fit:

$$
\operatorname{logit}P(Y_g=1)=
\alpha+eta\operatorname{logit}(p_{market,g})+\gamma z_{feature,g}.
$$

For margins or totals:

$$
y_g=\alpha+eta L_g^{decision}+f(X_g)+\varepsilon_g.
$$

A candidate passes the market-conditioned stage when it produces repeatable out-of-sample score improvement, a stable directional effect, and no material calibration harm. Coefficient significance alone is insufficient.

### Economic confirmation

After forecast selection is complete, freeze the bet rule and evaluate:

- Net ROI after vig and realistic execution.
- Mean and median CLV.
- Positive-CLV rate.
- ROI and CLV by predicted-edge bin.
- Bet count and independent game count.
- Maximum drawdown.
- Profit concentration.
- Results under flat stake and proposed staking.

ROI should confirm forecast utility rather than select among hundreds of feature variants. Otherwise, winner's curse and threshold mining will dominate.

### Suggested feature status

| Status | Standard |
| --- | --- |
| `KEEP_CORE` | Improves multiple targets or horizons, survives market conditioning, stable across folds |
| `KEEP_TARGETED` | Useful only for a declared market, week range, or matchup context |
| `MONITOR` | Directionally promising but uncertainty is too wide |
| `REDUNDANT` | Predictive alone but adds nothing beyond simpler features |
| `REJECT_UNSTABLE` | Improvement depends on one season, subgroup, or parameter |
| `REJECT_HARMFUL` | Worsens forecast score or calibration |
| `INVALID` | Leakage, unavailable timestamp, bad lineage, or irreproducible result |

## Stability requirements

Report candidate contribution by:

- Outer fold and season.
- Week-of-season band.
- FBS–FBS versus FBS–FCS.
- Conference and conference tier.
- Home, away, and neutral site.
- Favorite/underdog and spread band.
- Total band.
- Prediction horizon.
- Book or consensus source.
- Weather regime.
- Returning-quarterback status.
- Close-game versus mismatch environment.

A global average can hide that a feature helps only large favorites or only September totals. That does not require rejection; it requires a predeclared targeted role and new out-of-sample confirmation.

## Negative controls

Every feature-research harness should include controls designed to fail:

- Random Gaussian noise.
- Permuted candidate values within season.
- Random team labels.
- Random rolling windows.
- Arbitrary threshold indicators.
- A deliberately leaked future statistic as a pipeline sentinel.

If many noise variables appear important, the selection threshold is too permissive. If the leakage sentinel is not overwhelmingly predictive, the pipeline may not be testing what is intended.

Also include placebo timing tests. For example, compare a legitimate Wednesday injury feature with its improperly backfilled game-day version. This helps quantify how much apparent signal can come from timestamp leakage.

## Multiple testing

Create an append-only trial ledger. A trial includes any material change to:

- Feature definition.
- Window length.
- Garbage-time rule.
- Opponent adjustment.
- Model family.
- Hyperparameter search.
- Interaction.
- Market timestamp.
- Betting threshold.
- Subgroup exclusion.

A final untouched season is no longer untouched after its results influence another design. Once used, move it into research history and create a new future confirmation period.

Use false-discovery controls during broad screening, but do not rely on adjusted p-values alone. Require replication across chronological folds, stability under neighboring specifications, and prospective evidence.

## A practical first research program

### Stage 1: construct the dataset

Build one row per game and prediction timestamp with home-minus-away feature differences and selected interactions. Begin with CFBD sources for games, lines, opponent-adjusted WEPA, advanced metrics, talent, and returning production; CFBD documents advanced team/game statistics from 2001, havoc from 2004, and play-level player/success data from 2012, so sample periods will differ by feature family.[cite:191]

Create separate snapshots for:

- Preseason.
- Before Week 1.
- Sunday/opening market.
- Midweek.
- Game day.

### Stage 2: lock core baselines

Create three initial models:

1. Structural plus opponent-adjusted team strength.
2. Structural, team strength, and preseason priors.
3. Decision-time market baseline.

Do not optimize candidate features until these baselines are versioned and reproducible.

### Stage 3: screen six families

Start with:

1. Opponent-adjusted efficiency.
2. Success and down-state efficiency.
3. Explosiveness and play-value tails.
4. Pace and expected possessions.
5. Havoc, turnovers, field position, and special teams.
6. Personnel, talent, and continuity.

For each family, run add-one and drop-one tests against both football and market baselines.

### Stage 4: decompose winners

If opponent-adjusted efficiency passes, compare:

- Total PPA only.
- Pass/rush split.
- Standard/passing-down split.
- Recent-versus-season blend.
- Offense/defense interaction.

Advance the smallest representation that retains almost all stable improvement.

### Stage 5: test interactions

Only after main effects are stable, test football-motivated interactions:

- Pass offense × pass defense.
- Rush offense × rush defense.
- Explosiveness × explosiveness allowed.
- Pace × opponent pace.
- Pressure/havoc × quarterback experience.
- Wind × pass tendency/explosive passing.
- Returning production × prior unit quality.
- Travel/rest × depth or tempo.

Keep the interaction budget small and register hypotheses before evaluation.

### Stage 6: calibrate distributions

For spreads and totals, estimate residual scale as a function of mismatch, tempo, explosiveness, quarterback uncertainty, and weather. Evaluate interval coverage and probabilistic scores, not just mean RMSE.

### Stage 7: freeze betting translation

After choosing the forecast model:

1. Convert the predictive distribution into win, cover, or over probabilities.
2. De-vig available prices.
3. Set a betting threshold inside training folds.
4. Freeze the rule.
5. Evaluate on the untouched period.
6. Continue with prospective logging.

## Experiment table

Use one row per candidate–baseline–target combination:

| Column | Purpose |
| --- | --- |
| `experiment_id` | Stable identifier |
| `hypothesis` | Football reason the feature should help |
| `feature_family` | Broad concept |
| `feature_version` | Exact implementation |
| `target` | Margin, total, probability, movement |
| `prediction_horizon` | Preseason/open/midweek/game day |
| `baseline_version` | Locked comparator |
| `outer_folds` | Chronological test periods |
| `inner_policy` | Tuning and selection process |
| `delta_primary_loss` | Paired OOS improvement |
| `delta_loss_ci` | Uncertainty interval |
| `delta_calibration` | Probability-quality effect |
| `market_increment` | Improvement beyond line |
| `positive_fold_rate` | Temporal stability |
| `worst_fold` | Downside case |
| `parameter_stability` | Nearby-definition result |
| `delta_clv` | Market-price confirmation |
| `delta_roi` | Economic confirmation |
| `trial_count_at_test` | Search burden |
| `decision` | Keep/target/monitor/reject |

## Feature report card

For each feature family, display:

- Hypothesis and expected direction.
- Data source and first available season.
- Information timestamp and lag.
- Missingness by season/week.
- Correlated feature cluster.
- Standalone predictive score.
- Add-one-family improvement.
- Drop-one-family deterioration.
- Market-conditioned improvement.
- Calibration effect.
- Fold and season heatmap.
- Parameter-neighborhood plot.
- Conditional permutation importance.
- CLV and ROI confirmation.
- Trial count and selection history.
- Final status and allowed use cases.

## Common false discoveries

### End-of-season opponent adjustment

Using opponent strength calculated from future games makes early-season features look far more stable than they were in real time. Refit sequentially.

### Backfilled injuries or starters

A depth chart known Friday cannot be attached to a Wednesday prediction. Version player availability by timestamp.

### Closing line in an opening model

The close is valid as a later evaluation benchmark but not as an input to a model claiming an opening-time edge.

### Raw per-game volume

Yards/game, points/game, and plays/game mix quality, pace, opponents, overtime, and game script. Prefer per-play or per-drive rates with opponent and context adjustment.

### Outcome stats masquerading as process

Win percentage, scoring margin, and turnover margin are predictive partly because they summarize prior outcomes. Compare them with underlying process metrics to determine whether granular features add anything.

### Overly specific situations

“Ranked road underdogs after a bye in conference night games” can look profitable because many combinations were searched. A football explanation does not repair multiple testing.

### SHAP as selection proof

SHAP explains how a fitted model used its inputs; it does not establish out-of-sample incremental value, independence from correlated features, or betting profitability.

### One final holdout reused repeatedly

Repeatedly checking the same holdout turns it into training data through researcher decisions. Preserve a genuinely new prospective period.

## Decision standard

A college football statistic should be called **predictively useful** only when the following sentence can be completed:

> At prediction horizon **H**, for target **Y**, feature version **V** improved locked baseline **B** by **D** on chronological out-of-sample folds, with uncertainty **C**, remained directionally stable across **S**, and added **M** beyond the available market without materially harming calibration.

It should be called **betting-useful** only after adding:

> Under a frozen, executable selection and staking rule, the improvement produced acceptable CLV, net ROI, drawdown, and capacity in an untouched or prospective period.

This standard prevents descriptive football statistics, market echoes, selected noise, and execution artifacts from being mislabeled as durable betting signal.

## Immediate implementation order

1. Define margin, total, and movement targets at one fixed weekly timestamp.
2. Build point-in-time game snapshots with strict source-availability metadata.
3. Lock structural, football-only, market, and production baselines.
4. Create grouped features from CFBD WEPA, advanced stats, returning production, talent, and lines.
5. Implement nested walk-forward folds with all transformations inside training.
6. Run paired add-one-family and drop-one-family experiments.
7. Store observation-level losses and dependence-aware intervals.
8. Decompose only the families that improve repeatedly.
9. Test winners against the decision-time market and across model families.
10. Freeze the forecast model before examining betting thresholds and ROI.
11. Confirm on an untouched season, then prospective data.
12. Promote only features with clear lineage, stable improvement, and a declared production role.
