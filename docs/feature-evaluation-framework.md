# College Football Feature Research: Framework and Implementation Blueprint

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

Scoring of any result produced under this framework is governed by the [model evaluation standard](model-evaluation-standard.md); where the two disagree, the standard wins. This doc covers what the standard does not: which features to build, how to test them, and the machinery that keeps those tests honest.

The first half of this document is the **evaluation framework**: what counts as predictive and how to test it. The second half is the **implementation blueprint**: the warehouse, registry, validation calendar, and promotion machinery that make those tests reproducible.

## Notation

Symbols reused throughout. Each equation below also declares its own variables.

| Symbol | Meaning |
| --- | --- |
| $g$ | A single game (rows are indexed by game, and by prediction timestamp if multiple forecasts per game). |
| $i$ | One team. |
| $t$ | A prediction cutoff (for example, Wednesday 18:00 ET of a given week). |
| $y_g$ | The realized outcome for game $g$: margin, total, or a 0/1 event, depending on the target. |
| $\hat{y}_g$ | A model's forecast of $y_g$. |
| $L_g$ | The market spread, expressed as the market's expected **home margin**. |
| $T_g$ | The market total (over/under line). |
| $^{decision}$, $^{close}$ | Superscripts: the line at the moment the bet decision is made, and the closing line. |
| $X_g$ | The feature vector available for game $g$ at the decision timestamp. |

---

# Part I — Evaluation framework

## Define "predictive" precisely

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

Do not collapse these into one "feature importance" value. A feature can pass the first two and fail the market test. That is still useful for team ratings, simulations, and missing-line games, but it should not be labeled a betting edge.

## Choose targets first

### Spread and margin

**Outcome.** The margin target is the home team's final scoring margin:

$$
\begin{gathered}
y_g = \text{home points}_g - \text{away points}_g \\[1em]
\begin{array}{rl}
\text{where}\quad g: & \text{one game} \\
\text{home points}_g,\ \text{away points}_g: & \text{final points scored, overtime included} \\
y_g: & \text{home margin in points; } y_g > 0 \text{ means the home team won}
\end{array}
\end{gathered}
$$

For neutral-site games, "home" is whichever team the data source lists as home. Keep that assignment fixed across the features, the line, and the outcome, or the signs will disagree.

**What $L_g^{decision}$ is.** It is the market spread for game $g$ at the moment the bet decision is made, **converted into the market's expected home margin**. Books quote spreads from the favorite's side with a minus sign, so a quoted "home −7" means the market expects the home team to win by 7, and $L_g = +7$. In general:

$$
L_g = -\,(\text{quoted home spread}_g)
$$

That sign flip is what lets $y_g$ and $L_g$ sit on the same scale. The same three rules as the totals line below apply: pick one book or consensus definition, use a price that was actually available at the decision time, and never substitute the close for an earlier decision.

**Market-residual target.**

$$
\begin{gathered}
r_g^{margin} = y_g - L_g^{decision} \\[1em]
\begin{array}{rl}
\text{where}\quad y_g: & \text{realized home margin (points)} \\
L_g^{decision}: & \text{market's expected home margin at the decision time} \\
r_g^{margin}: & \text{how far the result beat } (+) \text{ or missed } (-) \text{ the line, from the home side}
\end{array}
\end{gathered}
$$

$r_g^{margin} > 0$ means the home side covered, $r_g^{margin} < 0$ means the away side covered, and $0$ is a push. Example: home −7 ($L = 7$), home wins by 10 ($y = 10$), so $r = +3$ and the home side covered by 3.

Modeling $r_g^{margin}$ instead of $y_g$ forces the model to earn credit only for what the spread missed. The same logic is spelled out for totals below.

Use MAE and RMSE for point forecasts. Prefer log likelihood or CRPS if the model estimates a full predictive distribution, because cover probability depends on both the mean and the uncertainty.

### Totals

**Outcome.** For game $g$, the quantity being predicted is the combined final score:

$$
\begin{gathered}
y_g = \text{home points}_g + \text{away points}_g \\[1em]
\begin{array}{rl}
\text{where}\quad g: & \text{one game} \\
\text{home points}_g,\ \text{away points}_g: & \text{final points scored, overtime included} \\
y_g: & \text{combined final score (points)}
\end{array}
\end{gathered}
$$

Overtime points count, because the book grades totals on the final score including OT.

**What $T_g^{decision}$ is.** It is the market total (the over/under line) for game $g$, taken at the moment the bet decision is made. Examples: 55.5 at Tuesday's open, or 53.0 an hour before kickoff when you place the bet. Three things define it:

- **Which book.** This could be one named book, or a consensus or "book fair" line across several books. Pick one and use the same one for every game.
- **Which timestamp.** It must be a price you could actually have bet then, rebuilt from line history at that time. Using the closing line when the decision was made earlier is leakage. It also fails the hard gate in the [model evaluation standard](model-evaluation-standard.md) that prices be reconstructible at decision time.
- **What it means.** $T_g^{decision}$ is roughly the market's median forecast of $y_g$ at that moment. It is the line the over/under is priced so that each side wins about half the time, before the vig. It already contains everything the market knew then: team strength, pace, injuries, weather forecasts, and public money.

**Which total this repo uses.** The choice is set by what line data carries timestamps:

| Seasons | $T_g^{decision}$ | Source | Why |
| --- | --- | --- | --- |
| 2013–2025 | Median **opening** total across books, snapped to the half point | `ou_open` in the totals model; median total-open in `cfb_system_maker/normalize.py` (`median_line`) | CFBD lines have no timestamps, only open and current/close ([odds sources](odds-sources-an-vs-apis-2026-09-11.md)). The open is the only pre-close price whose place in time is known. The median across books survives the book turnover ([median line](median-line-2026-09-17.md)); a single named book loses whole seasons. |
| 2026 onward | Consensus total (Action Network book 15) at one fixed weekly time, e.g. Wednesday 18:00 ET | `stg.an_history_tick` | Every tick is timestamped back to the April opener, so the decision line can be the price actually available at the decision time. Switch once a full season is captured. |

The close is **not** the decision line unless the strategy bets at kickoff. Otherwise it contains information that arrived after the decision, which is leakage. It stays in the design as a second target (below).

Three caveats come with the historical choice:

1. **The open is soft.** Limits are low and opens move a lot. A feature can look predictive against the open only because it anticipates the move. Always report the close residual alongside.
2. **"Open" is not one moment.** Each book's open is its first posted number, and books post on different days. The median open is the typical opener, not a snapshot at a fixed time.
3. **Results from the two eras are not directly comparable.** An open-based residual (2013–2025) and a fixed-time residual (2026+) measure against different information sets. Report them separately.

**Market-residual target.**

$$
\begin{gathered}
r_g^{total} = y_g - T_g^{decision} \\[1em]
\begin{array}{rl}
\text{where}\quad y_g: & \text{realized combined score (points)} \\
T_g^{decision}: & \text{market total available at the decision time} \\
r_g^{total}: & \text{points above } (+) \text{ or below } (-) \text{ the bettable line}
\end{array}
\end{gathered}
$$

This is how far the actual score landed above or below the line you could bet. A game with a decision-time total of 55.5 that finished 48 has $r_g^{total} = -7.5$, so the under won.

**Why model the residual instead of $y_g$.** The market total already explains most of the variation in the actual total. A model trained on $y_g$ spends its capacity relearning what the line already knows. A model trained on $r_g$ only earns credit for information the market missed, and that is the only kind of information that wins bets. If $r_g$ cannot be predicted from pre-game features, the model has no edge, however well it predicts raw points.

**Close residual (secondary target).** Score every totals feature against the close as well:

$$
\begin{gathered}
r_g^{total,close} = y_g - T_g^{close} \\[1em]
\begin{array}{rl}
\text{where}\quad y_g: & \text{realized combined score (points)} \\
T_g^{close}: & \text{median closing total across books, same construction as the open} \\
r_g^{total,close}: & \text{points above } (+) \text{ or below } (-) \text{ the closing total}
\end{array}
\end{gathered}
$$

The two residuals differ by exactly the line move: $r_g^{total} - r_g^{total,close} = T_g^{close} - T_g^{decision}$. So a feature can predict the decision residual in two ways. It can know something the market learns before kickoff, in which case it also predicts the move but not $r_g^{total,close}$; that is a bet-timing signal. Or it can know something the market never prices, in which case it predicts $r_g^{total,close}$ too; that is a fundamental edge. Example: open 55.5, close 52.5, final 48. The decision residual is $-7.5$ and the close residual $-4.5$; 3 of the 7.5 points were the market moving toward the under before kickoff.

**What totals features need to capture.** Totals features usually need to describe some of these:

- **Possessions:** tempo, plays per game, clock management.
- **Points per possession:** offensive and defensive efficiency.
- **Explosiveness:** long-play rate.
- **Finishing:** red-zone touchdown vs. field-goal rate.
- **Weather:** wind and precipitation.
- **Game-script interaction:** a lopsided spread means the leader runs clock and the trailer speeds up.

**Mean vs. variance.** Turning a residual forecast into an over/under probability takes two parts:

1. **Mean.** The expected residual: which side of the line the model leans, and by how much.
2. **Spread.** How uncertain that residual is, usually as the variance or the full distribution.

Under a normal approximation, the two combine like this:

$$
\begin{gathered}
P(\text{under}_g) = \Phi\!\left(\frac{-\hat{m}_g}{\hat{\sigma}_g}\right), \qquad P(\text{over}_g) = 1 - P(\text{under}_g) \\[1em]
\begin{array}{rl}
\text{where}\quad \hat{m}_g: & \text{predicted residual } E[r_g^{total}] \text{ (points; negative leans under)} \\
\hat{\sigma}_g: & \text{predicted standard deviation of } r_g^{total} \text{ (points)} \\
\Phi: & \text{standard normal cumulative distribution function}
\end{array}
\end{gathered}
$$

The formula ignores pushes and the discreteness of football scores; a production model should use the fitted distribution directly. It still shows why the spread matters. Take two games where each forecast is 3 points under the line ($\hat{m}_g = -3$):

- With $\hat{\sigma}_g = 10$: $P(\text{under}) = \Phi(0.30) \approx 0.618$.
- With $\hat{\sigma}_g = 16$: $P(\text{under}) = \Phi(0.19) \approx 0.574$.

Same lean, different probability, different edge against a −110 price, different Kelly stake.

A variable can improve the mean forecast and do nothing for the variance model. It can also do the reverse: wind barely moves the mean after the market adjusts, but it may change the variance. So test each feature on both parts separately:

- **Mean:** MAE or RMSE of $r_g$.
- **Variance:** out-of-sample correlation of predicted variance with $r_g^2$, or CRPS and interval coverage.

### Win and cover probabilities

For binary outcomes, evaluate probability forecasts with log loss and Brier score, then inspect calibration intercept, calibration slope, and reliability by probability band. Betting research has found calibration-based model selection more economically useful than accuracy-based selection in an NBA experiment, illustrating why classification accuracy alone is a poor betting-model objective.[cite:51][cite:54]

Cover labels discard useful information: winning by 1 point and missing by 30 points are both zeroes. A stronger pipeline usually models margin or its distribution first, then converts it into cover and moneyline probabilities.

### Line movement

Create a separate target for information discovery:

$$
\begin{gathered}
r_g^{move} = L_g^{close} - L_g^{decision} \\[1em]
\begin{array}{rl}
\text{where}\quad L_g^{close}: & \text{closing line, as expected home margin} \\
L_g^{decision}: & \text{line at the decision time, same book or consensus definition} \\
r_g^{move}: & \text{points the market moved after the decision; } (+) \text{ toward the home side}
\end{array}
\end{gathered}
$$

For totals, substitute the total line: $r_g^{move} = T_g^{close} - T_g^{decision}$, where a positive value means the total went up. Both lines must come from the same source definition, or a change in book mix will show up as fake movement.

This target does not involve the score at all. It asks whether a feature anticipates where the market is going, which is a different question from whether it predicts the game. Keep both outcomes because:

- A feature predicting line movement may be useful for bet timing.
- A feature predicting results after controlling for the line may represent fundamental residual signal.
- A feature predicting both is especially promising.
- A feature predicting neither should not survive because of an attractive in-sample narrative.

## Point-in-time data contract

Feature research is invalid unless each row can answer: **What was known for this game at this prediction timestamp?** CFBD itself warns that training features should include only games before the prediction week.[cite:187] Feature selection, preprocessing, imputation, scaling, and tuning must also occur inside training folds; selection on the complete dataset leaks test information and inflates performance.[cite:214][cite:215][cite:217]

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

Each family below lists what to build and, where relevant, the predeclared comparison ladder to run.

### Efficiency

**Hypothesis:** opponent-adjusted offensive and defensive PPA improve margin prediction beyond scoring margin and simple ratings.

Start with opponent-adjusted offensive and defensive PPA/EPA per play. Split into passing and rushing, but test the total family first. Efficiency features often subsume traditional box-score variables because they account for down, distance, field position, and scoring value. PPA values plays in expected-points terms, but observed PPA remains descriptive and requires shrinkage and game-state treatment for future prediction.[cite:250][cite:251]

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

**Success/explosiveness comparison ladder:**

1. PPA only.
2. PPA plus success rate.
3. PPA plus explosiveness.
4. PPA plus both.
5. PPA plus both and a constrained interaction.

Evaluate whether additions improve the predicted mean, the residual scale, or both. Explosiveness may matter more for distribution tails than for average margin.

### Pace and possessions

For totals, pace is not simply seconds per play. Build an expected-possession layer using:

- Neutral seconds per play, by game state.
- Plays per competitive drive.
- No-huddle rate if reliably observed.
- Pass rate and incompletion tendency.
- Fourth-down aggressiveness.
- Expected turnover on downs.
- Opponent-adjusted expected possessions and opponent pace interaction.
- End-of-half behavior.

Separate **intrinsic pace** from **observed play volume**. Raw plays per game mix intrinsic pace with opponent pace, overtime, field position, turnovers, and game script. Estimate pace in neutral situations and test whether it improves expected possessions after controlling for opponent behavior. Use raw plays per game only as a benchmark against the context-adjusted possession features.

### Finishing drives

Test scoring conditional on reaching scoring territory, comparing raw and shrunk versions of:

- Points per scoring opportunity.
- Touchdown rate inside the opponent 40 or red zone.
- Field-goal attempt and conversion profile.
- Fourth-down conversion and decision profile.
- Opponent finishing defense.
- Distance-adjusted kicker value.

These variables can be noisy because each team gets relatively few qualifying drives. Compare raw season rates with shrunk estimates and multi-year priors. For kickers, distance-adjusted expected value is preferable to raw field-goal percentage because attempt difficulty varies; CFBD provides a distance-based field-goal expected-points endpoint for this purpose.[cite:193][cite:231]

### Havoc and turnovers

CFBD defines havoc through tackles for loss, forced fumbles, interceptions, and pass breakups.[cite:194] Test stable and unstable components separately:

- Pressure/sack proxies and tackles for loss.
- Passes defended.
- Forced fumbles.
- Interceptions.
- Fumble recoveries.
- Turnover-worthy events if available.
- Expected versus realized turnovers.

Raw turnover margin is highly outcome-linked but mixes repeatable skill with randomness. Prefer process features—pressure, passes defended, forced-fumble opportunities—and regress realized recoveries and interceptions toward expectation.

**Turnover comparison ladder:**

1. Realized turnover margin.
2. Havoc components.
3. Expected-turnover estimate.
4. Turnover-luck residual.

The objective is to determine whether process variables survive future folds better than volatile realized outcomes. Do not assume the luck residual must reverse in the next game; test its horizon empirically.

### Field position and special teams

Candidate features include:

- Starting field position by offense and defense.
- Punt net value and opponent-adjusted punt value.
- Kickoff touchback and return value.
- Distance-adjusted field-goal value.
- Return efficiency with strong shrinkage.
- Hidden-yardage contribution.

Special-teams samples are small and individual personnel matter. Start with a group test; retain granular components only if their out-of-sample contribution persists.

### Personnel, priors, and continuity

College football differs from professional leagues because talent and continuity change sharply between seasons. Test:

- Returning offensive and defensive production, including returning usage and PPA.
- Quarterback starts, attempts, efficiency, transfer status, and prior performance.
- Offensive-line starts or snap continuity if available.
- Returning receiving usage concentration.
- Defensive returning production by position group.
- Incoming and outgoing transfer usage, rating, and prior performance.
- Recruiting talent by position and class age.
- Head-coach and coordinator continuity.
- Prior latent unit strength.

Returning production should interact with previous quality. Returning 80% of a poor unit does not imply the same benefit as returning 80% of an elite one. Build separate `prior_quality`, `continuity`, and `quality × continuity` variables.

A study using 2006–2018 major-conference teams found previous Sagarin strength, recruiting, returning starters, and returning-QB status predictive of season performance; previous performance was its strongest single selected predictor.[cite:173] Re-estimate these effects for game-level targets and the modern transfer environment rather than importing old coefficients.

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

Home-field research indicates that crowd effects, familiarity, weather, and travel can operate through different scoring channels, so home-field adjustments can be modeled separately for the home offense and away offense rather than as one constant margin shift.[cite:203] Avoid generic "situational trends" created by trying many arbitrary combinations.

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

### Shrinkage and the early-season blend

A raw team rate computed from a few games is mostly noise. Shrinkage pulls it toward a prior in proportion to how little data stands behind it:

$$
\begin{gathered}
\tilde{x}_{i,t} = w_{i,t}\, x_{i,t} + \left(1 - w_{i,t}\right) \mu_{i,t} \\[1em]
\begin{array}{rl}
\text{where}\quad i: & \text{team} \\
t: & \text{prediction cutoff} \\
x_{i,t}: & \text{raw observed statistic for team } i \text{ using games before } t \\
\mu_{i,t}: & \text{prior mean: preseason projection, conference average, or national average} \\
w_{i,t} \in [0, 1]: & \text{reliability weight on the observed value} \\
\tilde{x}_{i,t}: & \text{shrunk estimate used as the feature}
\end{array}
\end{gathered}
$$

When $w = 1$ the feature is the raw rate; when $w = 0$ it is the prior. A common empirical-Bayes form makes the weight a function of sample size:

$$
\begin{gathered}
w_{i,t} = \frac{n_{i,t}}{n_{i,t} + n_0} \\[1em]
\begin{array}{rl}
\text{where}\quad n_{i,t}: & \text{effective sample size behind } x_{i,t} \text{ (plays, drives, or attempts)} \\
n_0: & \text{sample size at which data and prior get equal weight}
\end{array}
\end{gathered}
$$

$n_0$ is large for noisy statistics (turnovers, field goals) and small for stable ones (success rate). Estimate it, or the whole weighting function, inside training data rather than choosing a visually attractive fade schedule on the final sample.

Weeks 0–4 deserve a dedicated version of this blend, fit separately per feature family:

$$
\begin{gathered}
\theta_{t,k} = w_{t,k}\,\hat{\theta}_{current,k} + \left(1 - w_{t,k}\right)\theta_{prior,k} \\[1em]
\begin{array}{rl}
\text{where}\quad k: & \text{feature family (passing efficiency, kicking, havoc, ...)} \\
t: & \text{prediction cutoff (week of season)} \\
\hat{\theta}_{current,k}: & \text{current-season estimate for family } k \\
\theta_{prior,k}: & \text{preseason prior for family } k \\
w_{t,k}: & \text{weight on current-season data at cutoff } t \\
\theta_{t,k}: & \text{blended estimate used by the model}
\end{array}
\end{gathered}
$$

This is the same formula as above, with the team index dropped and a family index added. The point of the index is that families do not share one fade schedule: passing efficiency stabilizes faster than kicking, havoc, or explosiveness. Estimate $w_{t,k}$ inside training seasons as a function of plays, drives, opponent quality, week, and roster continuity.

Attach uncertainty to each team estimate. New quarterbacks, coordinator changes, major portal churn, and few observed possessions should widen the predictive distribution rather than only alter the mean.

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

Fit opponent adjustments only with games available before the prediction timestamp. End-of-season opponent quality cannot be used retrospectively in a Week 3 forecast unless it was generated through an honest sequential model (see [Sequential ratings](#sequential-ratings)).

### Game-state treatment

Test at least:

- All eligible plays.
- Competitive-game-state plays.
- Neutral-script plays.
- Score/time weighted plays.
- Excluding kneels and obvious clock-kill plays.

Garbage-time filters can remove contamination but may also discard information about depth and mismatch ability. Treat the definition as a tunable research choice selected inside training folds, not a universal truth.

## Experimental design

### Outer walk-forward evaluation

Ordinary random cross-validation can train on future observations and test on the past. Time-series splitting preserves order and can insert a gap between training and test periods.[cite:256] Walk-forward validation repeatedly fits on the past and forecasts the future.[cite:224] Random game-level cross-validation is inappropriate because later-season team information can leak into earlier games and observations from the same team-season are dependent. College football needs a calendar-aware implementation because Saturday games share an information set and offseasons create large temporal gaps.

Use expanding, leave-one-season-forward tests:

| Fold | Training period | Test period |
| --- | --- | --- |
| 1 | Start through 2018 | 2019 |
| 2 | Start through 2019 | 2020 |
| 3 | Start through 2020 | 2021 |
| … | All preceding seasons | Next season |

Alternatively, train through Week $W-1$ and test Week $W$, grouped across seasons. In either design:

- Preserve the newest complete season as an untouched final confirmation set.
- After launch, add a prospective-only evaluation stream.
- Treat unusual seasons as explicit regimes. Do not hide regime failures by reporting only a pooled average.

### Weekly simulation

Within each test season:

1. Freeze all information before the weekly cutoff.
2. Update ratings and feature snapshots.
3. Generate every game prediction for the slate.
4. Store predictions before attaching outcomes.
5. Advance one week.

Keep the whole football week together. Using a Thursday result to update a Saturday forecast must be a declared intraweek policy, not accidental access.

### Inner model selection

Inside each outer training set:

1. Construct only point-in-time features.
2. Fit imputation and scaling.
3. Select features or families.
4. Tune hyperparameters.
5. Choose windows, transformations, and shrinkage.
6. Fit probability calibration.
7. Choose betting thresholds if economic evaluation is part of the experiment.

Nested validation keeps all data-dependent decisions inside training data and reserves the outer fold for model assessment.[cite:214][cite:217][cite:223]

### Paired ablation tests

For each candidate family $G$, fit two models that differ only by that family:

$$
\begin{gathered}
M_0 = \text{locked baseline} \qquad M_1 = \text{locked baseline} + G \\[1em]
\begin{array}{rl}
\text{where}\quad G: & \text{the candidate feature family (a group of related columns)} \\
M_0: & \text{frozen comparator: same features, tuning budget, folds, seeds} \\
M_1: & \text{the same model with family } G \text{ added and nothing else changed}
\end{array}
\end{gathered}
$$

Generate both predictions for exactly the same outer-fold games, then store the loss difference game by game:

$$
\begin{gathered}
d_g = L\!\left(y_g, \hat{y}_{g,M_1}\right) - L\!\left(y_g, \hat{y}_{g,M_0}\right), \qquad \bar{d} = \frac{1}{n}\sum_{g=1}^{n} d_g \\[1em]
\begin{array}{rl}
\text{where}\quad L(\cdot,\cdot): & \text{loss function, lower is better (absolute error, squared error, log loss, CRPS)} \\
y_g: & \text{realized outcome for game } g \\
\hat{y}_{g,M_0},\ \hat{y}_{g,M_1}: & \text{forecasts from the baseline and the candidate model} \\
d_g: & \text{per-game loss change; negative means the candidate did better on game } g \\
n: & \text{number of out-of-sample games} \\
\bar{d}: & \text{average loss change across all out-of-sample games}
\end{array}
\end{gathered}
$$

The loss function $L(\cdot,\cdot)$ is not the spread line $L_g$; the notation is standard in both places, so read it from context. Here it takes two arguments.

Negative $\bar{d}$ means the candidate improves forecasts. Pairing matters because most of the variation in loss comes from the games themselves (some games are just unpredictable); subtracting on the same game removes that shared noise and leaves only the difference the family made.

The $d_g$ are not independent: games in the same week share weather and information, and games in the same season share team estimates. Build the confidence interval for $\bar{d}$ with a **block bootstrap**—resample whole weeks or seasons, recompute $\bar{d}$, repeat—rather than treating every game as independent. Use the same games, folds, preprocessing policy, seeds, and tuning budget for both models.

Run both:

- **Add-one-family:** does the family improve a compact baseline?
- **Drop-one-family:** does the final model rely on it after all substitutes are present?

The two answers can differ. A family can be useful when added early but redundant in the completed model, because another feature group absorbs the same signal.

### Correlated features

College football metrics are heavily redundant:

- EPA/PPA and yards per play.
- Success rate and first-down rate.
- Points per drive and offensive efficiency.
- Sacks, tackles for loss, and havoc.
- Recruiting talent and prior team strength.
- Plays per game and pace.

Standard permutation importance measures loss increase after shuffling a feature, but correlated substitutes can make important variables appear individually weak.[cite:157][cite:158] Conditional permutation methods preserve relationships with other variables and ask for importance given the remaining features.[cite:216][cite:222][cite:227]

Recommended order:

1. Cluster correlated variables by football concept and empirical correlation.
2. Test the entire family.
3. If useful, compare compact representatives inside that family.
4. Use conditional or grouped permutation importance on held-out folds.
5. Prefer the cheapest, most stable, most interpretable representative when performance is tied.

### Model-family robustness

A real feature should not exist only because one algorithm happens to exploit noise. Test candidates in at least:

- Regularized linear or generalized linear model.
- Tree boosting model.
- Optional Bayesian or hierarchical model aligned with the problem.

Linear models reveal stable signed relationships and provide a difficult simplicity benchmark. Boosting can capture thresholds and interactions. Hierarchical models are useful for partial pooling across teams, conferences, and seasons.

Do not require identical importance rankings across algorithms. Require the feature family to improve honest forecasts often enough that its value is not an artifact of one flexible learner.

### Feature selection tools

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

## Model the variance

A betting model should estimate a full predictive distribution, not just a point forecast:

$$
\begin{gathered}
Y_g \sim \mathcal{D}\!\left(\mu_g, \sigma_g\right), \qquad \mu_g = f_\mu(X_g), \qquad \log \sigma_g = f_\sigma(X_g) \\[1em]
\begin{array}{rl}
\text{where}\quad Y_g: & \text{outcome for game } g \text{ (margin, total, or its market residual)} \\
\mathcal{D}: & \text{distribution family: normal, Student-}t\text{, or a discrete score distribution} \\
\mu_g: & \text{location, the expected outcome} \\
\sigma_g: & \text{scale, the uncertainty around } \mu_g \\
X_g: & \text{features available at the decision time} \\
f_\mu,\ f_\sigma: & \text{separate models for the mean and for the scale}
\end{array}
\end{gathered}
$$

The log on $\sigma_g$ keeps the predicted scale positive. A Student-$t$ family is a common choice for margins because blowouts produce heavier tails than a normal allows.

The point of writing $\sigma_g$ with a subscript is that uncertainty differs by game. Potential predictors of $\sigma_g$ include:

- Absolute expected margin.
- Combined explosiveness.
- Expected possessions and tempo.
- Quarterback uncertainty.
- Early-season status.
- Turnover-prone profiles.
- Weather uncertainty.
- FBS/FCS mismatch.
- Coaching transition.

Evaluate CRPS, log likelihood, interval coverage, and sharpness, not just mean RMSE. A feature can be useful because it improves uncertainty even when MAE barely moves (see the totals worked example in [Totals](#totals)).

## Interaction budget

Only after main effects are stable, test a small, hypothesis-driven set of football-motivated interactions:

| Interaction | Rationale | Likely target |
| --- | --- | --- |
| Pass offense × pass defense | Passing matchup | Spread/total |
| Rush offense × front defense | Run-game matchup | Spread/team total |
| Explosiveness × explosive plays allowed | Tail risk | Variance/alternates |
| Pace × opponent pace | Joint possessions | Total |
| Havoc/pressure × QB experience | Pressure vulnerability | Spread/turnovers |
| OL continuity × defensive havoc | Cohesion against disruption | Early spread |
| Wind × passing tendency/explosive passing | Weather exposure | Total |
| Prior quality × returning production | Value of retained production | Early-season mean |
| Travel/rest × depth or tempo | Fatigue exposure | Spread/total |

An all-pairs interaction search creates too many trials. Register hypotheses before evaluation, and use regularization or hierarchical shrinkage even for the predeclared set.

## Missingness taxonomy

| Type | Example | Treatment |
| --- | --- | --- |
| Structural | No current-season games | Prior plus sample-size flag |
| Coverage | Historical PBP absent | Hierarchical estimate plus coverage flag |
| Not applicable | No field-goal attempts | Opportunity-aware prior, not zero |
| Delayed | Status unknown at cutoff | Preserve unknown state |
| New entity | Transfer QB without FBS history | Player/team prior with wide uncertainty |
| Source error | Corrupt clock or duplicate play | Repair/exclusion flag |

A missingness indicator can be useful only if the same missing state would exist in production. Historical backfill quirks must not become predictors.

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

These regressions ask one question: **given the market's own forecast, does the feature still explain anything?**

For binary outcomes (win, cover, over):

$$
\begin{gathered}
\operatorname{logit} P(Y_g = 1) = \alpha + \beta \operatorname{logit}\!\left(p_{market,g}\right) + \gamma\, z_{feature,g} \\[1em]
\begin{array}{rl}
\text{where}\quad Y_g \in \{0, 1\}: & \text{binary outcome for game } g \\
\operatorname{logit}(p) = \log\frac{p}{1-p}: & \text{log-odds transform} \\
p_{market,g}: & \text{de-vigged market probability of } Y_g = 1 \text{ at the decision time} \\
z_{feature,g}: & \text{candidate feature, standardized to mean 0 and SD 1 within training data} \\
\alpha: & \text{intercept; nonzero means the market is biased toward one side} \\
\beta: & \text{market slope; } \beta = 1 \text{ means market probabilities are well scaled} \\
\gamma: & \text{incremental effect of the feature beyond the market}
\end{array}
\end{gathered}
$$

If the market is efficient and the feature is useless, the fit comes out $\alpha = 0$, $\beta = 1$, $\gamma = 0$: the model reproduces the market probability. $\gamma \neq 0$ out of sample is the evidence of incremental information. $\beta < 1$ would mean the market is overconfident (its probabilities should be pulled toward 50%), and $\beta > 1$ that it is underconfident.

For margins or totals:

$$
\begin{gathered}
y_g = \alpha + \beta L_g^{decision} + f(X_g) + \varepsilon_g \\[1em]
\begin{array}{rl}
\text{where}\quad y_g: & \text{realized margin or total} \\
L_g^{decision}: & \text{decision-time line (use } T_g^{decision} \text{ for totals)} \\
\alpha: & \text{intercept, a constant bias relative to the line} \\
\beta: & \text{how much of the line carries through; } \beta = 1 \text{ means one-for-one} \\
f(X_g): & \text{the candidate features' contribution, linear or learned} \\
\varepsilon_g: & \text{unexplained error}
\end{array}
\end{gathered}
$$

This is the same test in points. When $\alpha = 0$ and $\beta = 1$, subtracting the line from both sides gives $y_g - L_g^{decision} = f(X_g) + \varepsilon_g$, which is exactly the market-residual target from [Choose targets first](#choose-targets-first). So fitting the residual model is the special case that assumes the market is unbiased and one-for-one; fitting $\alpha$ and $\beta$ freely tests that assumption instead of imposing it.

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

### Feature status

| Status | Standard |
| --- | --- |
| `KEEP_CORE` | Improves multiple targets or horizons, survives market conditioning, stable across folds |
| `KEEP_TARGETED` | Useful only for a declared market, week range, or matchup context |
| `MONITOR` | Directionally promising but uncertainty is too wide |
| `REDUNDANT` | Predictive alone but adds nothing beyond simpler features |
| `REJECT_UNSTABLE` | Improvement depends on one season, subgroup, or parameter |
| `REJECT_HARMFUL` | Worsens forecast score or calibration |
| `RESEARCH_ONLY` | Forecast gain holds but frozen-policy economics do not |
| `INVALID` | Leakage, unavailable timestamp, bad lineage, or irreproducible result |

## Stability requirements

Report every candidate's contribution by:

- Season and outer fold.
- Week band: 0–3, 4–7, 8–conference championship, bowls.
- FBS–FBS versus FBS–FCS.
- Conference or competition tier.
- Home, away, and neutral site.
- Favorite/underdog and spread band.
- Total band.
- Prediction horizon.
- Market provider or consensus definition.
- Weather regime.
- Returning-quarterback status.
- Expected mismatch level (close game versus blowout environment).

A global average can hide that a feature helps only large favorites or only September totals. That does not require rejection; it requires a predeclared targeted role (`KEEP_TARGETED`), a segment chosen within training data, and new out-of-sample confirmation.

## Negative controls

Every feature-research harness should include controls designed to fail:

- Gaussian noise matched to the candidate's variance.
- Candidate values permuted within season.
- Random team labels.
- Random rolling windows.
- Arbitrary threshold indicators.
- A deliberately leaked future statistic as a pipeline sentinel.

Compare every candidate with the empirical distribution of control improvements. If noise frequently passes, the selection threshold is too permissive; tighten the promotion gate. If the leakage sentinel is not overwhelmingly predictive, the pipeline may not be testing what is intended.

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

"Ranked road underdogs after a bye in conference night games" can look profitable because many combinations were searched. A football explanation does not repair multiple testing.

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

---

# Part II — Implementation blueprint

## Purpose

This part turns the evaluation framework into an implementable research system. The goal is an auditable chain from raw CFBD data to point-in-time features, chronological predictions, market-relative tests, and production decisions.

The platform is not complete when it can display correlations or feature importance. It is complete when any claimed signal can be reconstructed, challenged, and evaluated without contaminating future tests.

## Separate research tracks

Maintain three linked but separately scored models:

| Track | Primary output | Question | Benchmark |
| --- | --- | --- | --- |
| Team strength | Latent offense, defense, special teams | How good is each unit now? | Prior and opponent-adjusted rating |
| Game forecast | Margin, total, and uncertainty | What outcome distribution is expected? | Football baseline and market |
| Betting decision | Bet, side, price, stake, or pass | Is the offered price actionable? | No-bet and incumbent policies |

CFBD describes PPA, WEPA, Elo, SRS, CORE, and win probability as models answering different questions rather than interchangeable ratings.[cite:242] Apply that principle internally: a play metric can improve team estimation without improving ATS predictions, and a strong game forecast can still fail after vig or poor execution.

## CFBD source map

CFBD and cfbfastR expose games, lines, drives, plays, advanced statistics, PPA, returning production, usage, transfers, coaches, venues, ratings, and other building blocks.[cite:230][cite:231][cite:232] CFBD documents advanced team/game statistics from 2001, havoc from 2004, and play-level player/success data from 2012, so sample periods will differ by feature family.[cite:191]

| Domain | Source | Derived features | Main risk |
| --- | --- | --- | --- |
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
| --- | --- | --- |
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

`prediction_ts` is the historical decision cutoff. `prediction_created_at` records when the system generated the row, separating reconstructed backtests from genuine prospective forecasts. `margin_mean`/`total_mean` and `margin_scale`/`total_scale` are the $\mu_g$ and $\sigma_g$ of [Model the variance](#model-the-variance).

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

Compare a locked football baseline with and without the candidate family using the [paired ablation tests](#paired-ablation-tests). Require paired out-of-sample improvement, reasonable worst-fold behavior, and performance above negative controls.

### Stage C: market increment

Compare the decision-time market baseline against market plus candidate, or predict the residual around the market (see [Market-conditioned metrics](#market-conditioned-metrics)). Historical CFB studies have reached different conclusions about whether rating systems add information beyond betting spreads, so the answer must be tested by era and timestamp.[cite:174][cite:179]

### Stage D: betting confirmation

Freeze the forecast, probability conversion, de-vigging, threshold, book universe, and staking. Only then examine CLV, ROI, drawdown, and fill realism.

## Candidate scorecard

Do not hide everything in one number. Display:

| Dimension | Measurement |
| --- | --- |
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

For a sortable research score, use a multiplicative form so a data-quality or robustness failure cannot be averaged away:

$$
\begin{gathered}
S_j = G_j \times C_j \times R_j \times D_j \\[1em]
\begin{array}{rl}
\text{where}\quad j: & \text{candidate feature family} \\
G_j \in [0, 1]: & \text{predictive gain, rescaled so no improvement} = 0 \\
C_j \in [0, 1]: & \text{confidence, e.g. how far the interval for } \bar{d} \text{ sits from zero} \\
R_j \in [0, 1]: & \text{robustness: positive-fold share, definition stability, worst fold} \\
D_j \in [0, 1]: & \text{deployability: data quality, latency, complexity} \\
S_j: & \text{sortable research score}
\end{array}
\end{gathered}
$$

Multiplying instead of adding is the design choice. With a weighted sum, a huge gain can paper over a feature that is undeployable ($D_j = 0$) or confined to one season ($R_j \approx 0$). With a product, any single zero sends the score to zero. That requires each component to be rescaled onto $[0, 1]$ first; a negative gain must map to $0$, not to a negative number, or two failures would multiply into a positive score.

Keep market increment out of $S_j$ and treat it as a separate hard gate for features labeled as betting signals.

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

Failure: `REJECT_UNSTABLE`, `REJECT_HARMFUL`, or `MONITOR`.

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
| --- | --- | --- | --- |
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

### Experiment tables

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

In `fold_prediction`, `candidate_loss − baseline_loss` is the per-game $d_g$ from [Paired ablation tests](#paired-ablation-tests); `feature_result.primary_loss_delta` is $\bar{d}$ and `ci_low`/`ci_high` its block-bootstrap interval.

### Experiment summary table

One row per candidate–baseline–target combination:

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

### Feature report card

For each feature family, display:

1. Hypothesis and expected direction.
2. Definition, lineage, data source, and first available season.
3. Information timestamp and lag.
4. Coverage and missingness by season/week.
5. Distribution by season/week.
6. Correlated feature cluster.
7. Standalone predictive score.
8. Add-one-family improvement and drop-one-family deterioration.
9. Fold-level paired loss and fold/season heatmap.
10. Market-conditioned improvement.
11. Calibration effect.
12. Parameter-neighborhood stability.
13. Conditional permutation importance.
14. Negative-control percentile.
15. CLV and ROI confirmation.
16. Trial count, selection history, and decision history.
17. Final status and allowed use cases.

## Research program

### Stage 1: construct the dataset

Build one row per game and prediction timestamp with home-minus-away feature differences and selected interactions. Begin with CFBD sources for games, lines, opponent-adjusted WEPA, advanced metrics, talent, and returning production.

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

Run the predeclared set from [Interaction budget](#interaction-budget).

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

## Implementation checklist

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
