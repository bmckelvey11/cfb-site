**Superseded by** [totals-modeling-guide.md](../../research/totals/docs/totals-modeling-guide.md)

# A Starter Framework for a College Football Totals Model

## Purpose and scope

This framework describes how to stand up an FBS pregame full-game totals model from the ground up, using CFBD as the primary data source and DuckDB/MotherDuck as the warehouse. It assumes the market is a strong forecaster and treats the model's job as explaining variation the decision-time total leaves unexplained, not as reproducing the total from scratch.

The central design choice is to predict the total-points residual around an auditable decision-time line, not raw final points. This aligns the modeling target with the betting decision and prevents the model from being rewarded for re-deriving information the market already prices.

## Two philosophies, one recommended path

There are two coherent ways to build a totals model, and they differ in what the model is asked to learn.

| Approach | Target | What it must beat | Main risk |
|---|---|---|---|
| Direct total | Final combined points | Sportsbook total RMSE (roughly 13 in NFL studies) | Rebuilds market information; hard to beat closing number |
| Market-residual | Final points minus decision-time total | Zero (no residual signal) | Requires trustworthy line timestamps |

Studies that predict raw NFL totals report sportsbook RMSE near 13.22 and find only some models beat it, which illustrates how strong the market baseline is.[cite:285] Because the betting question is whether the offered total is wrong, the residual framing is the better primary target, with the direct total kept as a diagnostic and sanity check.

## The market is a hard baseline

College football totals research generally finds the market efficient or close to it. Opening and closing spreads and totals across thirteen seasons are generally efficient, with the closing total closer to the outcome than the opening total about 53% of the time.[cite:278] Reverse line movement occurs frequently but is not generally a profitable totals strategy in college football.[cite:278]

Evidence of inefficiency exists but is narrow and often specific. One study documents a censoring bias in jointly implied team scores that yields a naive strategy winning over 55% across two decades.[cite:281] Contrarian rules on very high totals have shown statistically significant edges in some samples, and behavioral work finds overs on high totals attract disproportionate betting interest.[cite:280][cite:284] These are pockets, not a general failure of the market, so the model should be built to detect and exploit specific residual structure rather than assuming broad mispricing.

## Design targets

Maintain three residual targets rather than one, because each answers a different question.

For the outcome relative to the decision-time total:

\[
r^{\text{final}}_g = T^{\text{final}}_g - L^{\text{decision}}_g
\]

For subsequent market movement:

\[
r^{\text{move}}_g = L^{\text{close}}_g - L^{\text{decision}}_g
\]

For a components view that supports team totals and censoring analysis:

\[
T^{\text{final}}_g = S^{\text{home}}_g + S^{\text{away}}_g
\]

A feature can predict the final outcome, predict the closing line, or predict one team's scoring, and those are not the same edge. Team-total and spread lines jointly imply team scores and expose a documented zero-censoring bias, which is why modeling components alongside the combined total is worthwhile.[cite:281]

## System architecture

Use the layered warehouse already established for the project: immutable raw CFBD responses, typed staging, conformed core dimensions and facts, point-in-time snapshots, versioned features, and separate experiment and betting schemas. The design must separate what CFBD reported from what the model derived so debugging and audits stay clean.

| Layer | Function | Example objects |
|---|---|---|
| `raw` | Exact CFBD responses plus ingestion metadata | `raw_games`, `raw_lines`, `raw_plays` |
| `stg` | Typed, normalized records | `stg_games`, `stg_lines`, `stg_drives` |
| `core` | Canonical game, team-game, drive, play grains | `fct_game`, `fct_team_game`, `fct_play` |
| `snap` | Point-in-time information sets | `snap_team_week`, `snap_total_line_ts` |
| `feat` | Versioned totals features | `feat_pace_v1`, `feat_eff_v1` |
| `mart_bet` | Predictions, edges, backtests | `mart_total_predictions`, `mart_total_backtest` |

## The line audit comes first

Before any modeling, verify what the stored line fields actually represent. The residual target is meaningless if `L^{decision}` is not a real, timestamped price. The audit must establish, for each line record:

- The sportsbook or consensus identity.
- Whether it is an opener, a close, or an arbitrary snapshot.
- The capture timestamp and time zone.
- Whether totals and moneylines share the same capture moment.
- Provider dispersion at that moment.

If timestamps and opener/close designations cannot be verified, the first deliverable is not a model but a line-capture pipeline that records totals at a fixed decision moment going forward. Every downstream residual, CLV, and profitability claim depends on this being correct.

## The scoring process to model

A totals model benefits from decomposing scoring into interpretable drivers, because final points are the product of how many possessions occur and how efficiently each team converts them. A useful mental model:

\[
E[T_g] \approx P_g \times \big(\text{points per possession}_{\text{home}} + \text{points per possession}_{\text{away}}\big)
\]

where \(P_g\) is expected possessions per team. This mirrors how established football projection systems build totals from per-drive or per-play efficiency combined with pace, then convert to a score distribution.[cite:286] Modeling possessions and efficiency separately makes the model diagnosable: an error can be traced to a pace miss or an efficiency miss rather than an opaque points error.

### Pace and possessions

Expected possessions drive the ceiling and floor of a total. Construct:

- Neutral seconds per play, adjusted for opponent.
- Plays per non-garbage drive.
- Pass rate over expectation, since incompletions stop the clock.
- No-huddle and tempo tendencies.
- Fourth-down aggressiveness, which extends drives.
- Opponent-adjusted expected possessions for the matchup.

Raw plays per game conflate intrinsic tempo with opponent, score script, overtime, and turnovers, so prefer opponent-adjusted possession estimates and validate them against raw pace as a benchmark.

### Efficiency

Points per possession is the second lever. Build opponent-adjusted offensive and defensive efficiency using CFBD PPA/EPA and success-rate concepts, split where the sample supports it:

- Overall and per-play PPA differentials.
- Pass and rush efficiency splits.
- Early-down versus passing-down efficiency.
- Points per drive and points per scoring opportunity, with shrinkage.
- Red-zone and finishing efficiency, heavily shrunk due to volatility.

Established projection models combine EPA/DVOA-style efficiency per drive with time-of-possession and run/pass ratios to project scores, which is a proven template for the efficiency-times-pace structure.[cite:286]

### Environment and context

Totals are sensitive to conditions that suppress or inflate scoring:

- Wind and precipitation, interacted with passing tendency.
- Temperature extremes.
- Altitude and surface.
- Neutral site and travel.
- Rest differential and short weeks.
- Divisional or rivalry familiarity, which research links to fewer overs in the NFL and may transfer to CFB.[cite:290]

Weather should enter through interactions with team style rather than as a standalone additive term, because wind matters far more for a pass-heavy offense than a run-first one.

## Regression to the mean

Volatile scoring components must be shrunk toward priors rather than trusted at face value, especially early in the season. For any team metric \(x\), estimate latent quality with partial pooling instead of using the raw current-season rate. Heavier shrinkage belongs on turnovers, explosive plays, red-zone conversion, and special teams, which are the least stable inputs.

The correct prior mean is rarely the national average; it is a team-specific preseason prior blended with opponent-adjusted current-year evidence. The success condition is that the shrunk version improves held-out residual accuracy or calibration in multiple future seasons and does not lose CLV relative to the raw-feature version.

## Early-season cold start

Rolling statistics are unavailable or unstable in Weeks 0 to 4, so the model needs a dedicated prior blend:

\[
\theta_{t,k} = w_{t,k}\,\hat{\theta}^{\text{current}}_{k} + (1 - w_{t,k})\,\theta^{\text{prior}}_{k}
\]

Build preseason priors for offense, defense, pace, and special teams from returning production, quarterback continuity, recruiting and transfer talent, coaching and coordinator continuity, and prior latent strength. Learn the weight \(w_{t,k}\) from historical seasons as a function of games played, opponent quality, and continuity, rather than hard-coding one fade schedule for every statistic; passing efficiency and field-goal reliability stabilize on different timelines.

## Predict a distribution, not a point

Over/under decisions require probabilities, so the model must output an outcome distribution, not just a mean total. Two viable routes:

| Method | Mechanics | Strengths | Cautions |
|---|---|---|---|
| Parametric mean plus variance | Predict mean total and a conditional scale, then integrate over the line | Simple, fast, easy to calibrate | Must check tails and key numbers |
| Score simulation | Model team scoring processes and simulate final scores | Captures team totals, correlation, key numbers | More complex; needs good scoring model |

Score-simulation approaches such as Poisson or negative-binomial team-score models are well established in football and soccer and naturally produce total, spread, and team-total probabilities from one engine.[cite:286][cite:287] Whatever route is chosen, estimate a conditional variance, because dispersion depends on pace, explosiveness, quarterback uncertainty, and mismatch level; a high-tempo, explosive matchup has a wider total distribution than a grind-it-out game with the same mean.

## Modeling methods

Start simple and add complexity only when it earns its place against the market residual.

1. Baseline: predict the residual as zero and record market-only loss.
2. Linear or regularized regression on a compact pace-plus-efficiency-plus-context feature block.
3. Gradient boosting for nonlinear interactions once the linear model is understood.
4. Score-simulation engine if team totals and key-number effects become priorities.

XGBoost is a reasonable fit for this tabular regression once features are engineered, but it should predict the residual or the total and then be converted to edges, validated with time-aware splits rather than random folds. Feature selection via forward selection or lasso has outperformed using all features in comparable NFL total-score work, so prune aggressively.[cite:285]

## Validation calendar

Random cross-validation leaks future information in a time-ordered problem, so use chronological validation throughout. Two complementary designs:

- Leave-one-season-forward: train on all prior seasons, test on the next, expanding the window each fold. This stresses cross-season transfer under roster and rule change.
- Rolling-week deployment: within a test season, update only through the previous completed week, predict the full upcoming slate together, then advance.

Keep an entire football week in the same fold, insert a purge gap where trailing windows overlap a boundary, and reserve the newest complete season as an untouched confirmation set. Once that season influences a modeling choice, a later period must replace it.

## Metrics that matter

Evaluate the model at three levels, because good forecasts do not guarantee profits.

| Level | Primary metrics | Secondary checks |
|---|---|---|
| Forecast quality | Residual MAE, RMSE, CRPS, log score | Predicted-versus-actual calibration |
| Market-relative | Improvement over market-only residual loss | Stability across seasons and line bands |
| Betting | Hit rate versus break-even, ROI, CLV, drawdown | Results by edge bucket and by over/under side |

Track calibration explicitly by plotting predicted total against actual total to diagnose systemic bias, rather than relying on RMSE or MAE alone. The break-even hit rate at standard vig is roughly 52.4%, so classification accuracy must clear that bar with a meaningful sample before any profitability claim is credible.[cite:285]

## Edge, staking, and filters

Convert the predicted distribution into an edge against the decision-time total, then apply disciplined selection:

- Compute over and under probabilities from the predicted distribution at the offered number.
- Require a minimum modeled edge before betting, since thresholds improved out-of-sample results in comparable work but shrink sample size.[cite:285]
- Track results by edge bucket to confirm larger modeled edges actually win more often.
- Respect key numbers and buy-point economics around common totals.
- Size stakes with a fractional-Kelly or flat-unit rule rather than full Kelly, given estimation uncertainty.

## Avoiding overfitting

The failure mode for a solo builder is discovering noise. Build fewer, broader systems, validate across independent chronological folds, and kill added complexity when residual improvements do not recur or when apparent gains vanish after line-timing audits. Concrete guardrails:

- Predeclare feature families and hypotheses before testing.
- Add negative-control features and require candidates to beat them.
- Log every experiment and count trials to keep multiple testing honest.
- Prefer effects stable across seasons over large in-sample effects.
- Confirm profitability survives realistic vig and slippage, not just closing-line theory.

## First build sequence

A practical order that reaches a testable model quickly:

1. Audit and lock the decision-time line source and timestamps.
2. Build core game, team-game, drive, and play tables from CFBD.
3. Construct point-in-time pace and efficiency snapshots with opponent adjustment.
4. Build preseason priors and the early-season blend.
5. Fit the market-only baseline and record its residual loss.
6. Add the compact feature block via regularized regression on the residual.
7. Convert predictions to a distribution and then to over/under edges.
8. Validate with leave-one-season-forward and rolling-week folds.
9. Measure forecast, market-relative, and betting metrics, including CLV.
10. Only then test gradient boosting, interactions, or a simulation engine.

## Definition of a viable first model

The first model is viable, not when it looks profitable in sample, but when it satisfies four conditions. Its residual target is built on an audited, timestamped line. It reduces held-out residual loss below the market-only baseline in more than one season. Its predicted-versus-actual totals are calibrated across the line range. And its edge, after realistic vig, produces stable directional CLV rather than profit concentrated in a handful of games. Meeting those conditions establishes a foundation worth extending; failing them signals that complexity should be removed rather than added.
