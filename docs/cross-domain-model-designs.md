# Cross-Domain Predictive Model Designs for College Football

## Scope and ranking logic

This catalog proposes **21 model designs**, not renamed algorithms. The statistical classes—state-space models, competing-risk survival models, mixture-of-experts, analog ensembles, conformal inference, and others—are established. The proposed contribution is their **college-football-specific state definition, component coupling, targets, and leakage-safe training design**. Dynamic state-space modeling has already been applied to NFL score differences, and play/drive resampling has already been used for NFL strategy simulation; those precedents are identified rather than claimed as new inventions.[^1][^2][^3]

Models are ranked by expected incremental out-of-sample lift per unit of implementation effort. “Lift” means improvement over a serious baseline containing SP+, FPI, market prices, rolling efficiency, roster quality, venue, and weather—not improvement over a naive model. The ratings are hypotheses to test with rolling-origin evaluation, not empirical claims.

All game forecasts must be frozen at a declared timestamp, such as Sunday 08:00, Wednesday 12:00, or five minutes before kickoff. Features, ratings, injuries, weather, and prices must use only information observed by that cutoff. Closing-line targets may be used to train a market forecast made earlier in the week, but the realized close cannot enter that model as a feature.

## Ranked catalog

| Rank | Model | Main target | Source concept | Lift | Effort | Pregame? |
|---:|---|---|---|---:|---:|---|
| 1 | Four-Axis Dynamic Team State | Margin, total, win | State-space/Kalman filtering | 5 | 3 | Yes |
| 2 | Competing-Risk Drive Renewal Simulator | Full score distribution | Survival, reliability, renewal theory | 5 | 4 | Yes |
| 3 | Latent Consensus Market Nowcaster | Closing line and next move | Financial microstructure/state-space | 5 | 3 | Yes, at timestamp |
| 4 | Market-Anchored Residual Distribution | Margin, cover, over | Residual learning/control variates | 5 | 2 | Yes |
| 5 | Analog Matchup Ensemble | Margin/total distribution | Meteorological analog forecasting | 4 | 2 | Yes |
| 6 | Multi-Fidelity Strength Fusion | Margin, total, early season | Co-kriging/measurement models | 4 | 3 | Yes |
| 7 | Coherent Joint Score Model | Team scores, margin, total | Multivariate distributional forecasting | 4 | 3 | Yes |
| 8 | Regime-Gated Expert Ensemble | Margin, total, cover | Mixture-of-experts | 4 | 3 | Yes |
| 9 | Player-Unit Partial-Pooling Model | Margin, sacks, explosive plays | RAPM/hierarchical effects | 4 | 4 | Yes |
| 10 | Hidden Durability-State Model | Second-half scoring, total | Reliability HMM/remaining useful life | 4 | 4 | Yes |
| 11 | Distributional Quantile Forecaster | Alt spreads/totals, tails | Quantile/distributional regression | 4 | 3 | Yes |
| 12 | Dynamic Expert-Weight Aggregator | Margin, total, close | Online learning/forecast combination | 3 | 2 | Yes |
| 13 | Defense-Independent Execution Model | Future offense/defense efficiency | Baseball DIPS/measurement decomposition | 4 | 4 | Yes |
| 14 | Scheme-Response Causal Forest | Matchup residual | Heterogeneous treatment effects | 4 | 5 | Yes |
| 15 | Low-Rank Interaction Factor Model | Matchup residual | Collaborative filtering/matrix factorization | 3 | 3 | Yes |
| 16 | Era-and-Conference Transport Model | Cross-era/generalization | Optimal-transport domain adaptation | 3 | 4 | Yes |
| 17 | Selective Conformal Edge Model | Bet/no-bet, calibrated intervals | Conformal selective prediction | 3 | 2 | Yes |
| 18 | Recurrent Frailty Game Simulator | Total, possession count, score paths | Epidemiological recurrent events | 3 | 4 | Yes |
| 19 | Tail-Spliced Blowout Model | Alt lines, large margins/totals | Extreme-value theory | 2 | 3 | Yes |
| 20 | Cross-Level Forecast Reconciliation | Team scores, margin, total | Hierarchical forecast reconciliation | 2 | 2 | Yes |
| 21 | Functional Season-Trajectory GP | Team strength, late-season performance | Functional data analysis | 2 | 4 | Yes |

## Model specifications

### 1. Four-Axis Dynamic Team State

**Definition.** A time-varying latent model that estimates each team’s offensive strength, defensive strength, pace propensity, and outcome-variance propensity separately, with posterior uncertainty carried into every forecast.

**Estimation procedure.** For team $i$ before week $t$, define latent state $z_{i,t}=(o_{i,t},d_{i,t},p_{i,t},v_{i,t})$. Evolve it as

$$
z_{i,t}=A z_{i,t-1}+B r_{i,t}+u_{i,t}, \qquad u_{i,t}\sim N(0,Q),
$$

where $r_{i,t}$ contains returning production, recruiting, coaching continuity, and preseason priors. For game $g=(i,j,t)$, jointly model margin $M_g$, total $T_g$, and log possessions $N_g$:

$$
M_g=o_{i,t}-d_{j,t}-o_{j,t}+d_{i,t}+h_g+\beta_M X_g+\epsilon_{M,g},
$$

$$
T_g=o_{i,t}+d_{i,t}+o_{j,t}+d_{j,t}+\beta_T X_g+\epsilon_{T,g},
$$

$$
\log N_g=\mu_N+p_{i,t}+p_{j,t}+\beta_N X_g+\epsilon_{N,g}.
$$

Let the residual covariance depend on $v_{i,t}+v_{j,t}$, weather, and pace. Fit by Bayesian filtering/smoothing or variational state-space inference, then issue forecasts from the filtered—not smoothed—state available at the cutoff. Glickman and Stern’s NFL model is the direct precedent for time-varying latent team strength; the four-axis state and heteroskedastic coupling are the proposed extension.[^2][^1]

**Why it may add information.** EPA and SP+ largely summarize conditional means. Separate latent pace and variance states can change totals, tail probabilities, and favorite-cover behavior without changing expected efficiency.

**Targets.** Margin, total, win probability, cover probability, alternate-line probabilities.

**Stabilization.** Useful immediately through priors; expect meaningful in-season updating after roughly 2–4 games and reasonably stable latent means after 5–7 games. Variance state will require stronger pooling and approximately 8–15 games across seasons.

**Primary failure mode.** The four states may not be separately identifiable, especially offense versus opponent defense and variance versus schedule strength.

**Kill test.** In season-forward folds, remove pace and variance states one at a time. Kill the extensions if neither improves log score/CRPS nor calibration over the two-axis offense-defense state in at least two held-out seasons.

**Pregame status.** Strictly pregame when filtering uses only prior games and cutoff-time covariates.

### 2. Competing-Risk Drive Renewal Simulator

**Definition.** A generative game model that treats each drive as a time-to-termination process with competing endpoints: touchdown, field goal attempt/make, punt, turnover, downs, safety, and half expiration.

**Estimation procedure.** Construct one row per live offensive play. Estimate cause-specific discrete hazards

$$
h_k(s)=P(K=k\text{ on next play}\mid K\text{ not yet observed},s),
$$

where state $s$ contains offense, defense, down, distance, yard line, clock, score, drive-play count, personnel, weather, and latent team ratings. Fit a multinomial hazard model or gradient-boosted survival model with team-season random effects. Separately estimate the transition kernel $P(s_{n+1}\mid s_n,\text{play family})$, including clock runoff and field-position change. Simulate alternating drives until game expiration; draw kickoff field position and possession changes from empirical conditional distributions. Competing-risk models explicitly handle mutually exclusive terminal events, while football play/drive resampling already has an NFL implementation precedent.[^4][^5][^3]

**Why it may add information.** It models nonlinear conversion chains, drive length, clock consumption, and score-state interactions. Two teams with identical EPA/play can have different score distributions because one creates short drives and the other sustains long, low-variance possessions.

**Targets.** Full joint score distribution, margin, total, team totals, possession count, alternate lines.

**Stabilization.** Shared transition functions can train on the full FBS sample. Team random effects should begin contributing after approximately 80–150 offensive plays or 12–20 drives, with terminal-event-specific effects requiring 30–50 drives unless heavily pooled.

**Primary failure mode.** Simulation compounds small transition-model errors and may create unrealistic state occupancy.

**Kill test.** On held-out seasons, compare simulated and observed distributions of possessions, drive length, starting field position, scoring type, margin, and total. Kill the simulator if it cannot beat direct margin/total baselines on CRPS or if posterior predictive checks fail systematically by score state.

**Pregame status.** Strictly pregame when team parameters and covariates are frozen before kickoff.

### 3. Latent Consensus Market Nowcaster

**Definition.** A multi-book state-space model that infers the efficient latent spread/total and predicts the next consensus move and closing price from asynchronous book updates.

**Estimation procedure.** At timestamp $t$, convert each book quote to a common home-team spread, total, and de-vigged probability. Model quote $q_{b,t}$ as

$$
q_{b,t}=m_t+\alpha_b+\ell_b\Delta m_t+\eta_{b,t},
$$

where $m_t$ is latent consensus, $\alpha_b$ is book bias, and $\ell_b$ captures lead-lag sensitivity. Evolve consensus as

$$
m_t=m_{t-1}+\gamma' n_t+\omega_t,
$$

where $n_t$ contains weather/news/roster changes available at $t$. Add a marked update-intensity model for which book moves first, direction, size, and time since last move. Estimate with a Kalman filter plus discrete-time hazard or a switching state-space model. Train separate spread and total systems; output $E[m_{close}\mid \mathcal F_t]$, probability of the next half-point move, and predicted close distribution.

**Source and analogy.** This is financial price discovery translated to sportsbooks: books are venues, quote revisions are price changes, and lead-lag structure approximates informed versus reactive flow. It is not a game-outcome model unless its forecasted price innovations are subsequently tested against results.

**Why it may add information.** Standard line movement collapses the book panel to one difference. This model uses update ordering, staleness, cross-book disagreement, and time-to-close.

**Targets.** Closing spread/total, next move, move direction, expected CLV from a current quote.

**Stabilization.** Book-level latency and bias may stabilize after roughly 500–1,500 synchronized game-time series. Team/news coefficients require multiple seasons and hierarchical pooling.

**Primary failure mode.** Apparent sharp-book leadership may be a timestamp or scraping artifact.

**Kill test.** Randomly jitter timestamps within the measured collection latency and rerun. Kill lead-lag features if their out-of-sample edge disappears under plausible jitter or fails on a second data vendor.

**Pregame status.** Pregame at every declared snapshot; the closing line is a future target, never a feature.

### 4. Market-Anchored Residual Distribution

**Definition.** A two-stage model that treats the current market forecast as an offset and learns only where football information predicts a conditional residual.

**Estimation procedure.** At cutoff $t$, let $S_{g,t}$ be the market-implied home margin and $U_{g,t}$ the market total. Fit cross-fitted residual models

$$
M_g=S_{g,t}+f_M(X_{g,t})+\epsilon_{M,g}, \qquad T_g=U_{g,t}+f_T(X_{g,t})+\epsilon_{T,g},
$$

with aggressive regularization and distributional output. Use blocked season folds to create honest residual targets. Train separate residual experts for matchup, personnel, weather, travel, and market microstructure; combine only if they improve proper scoring rules. For cover prediction, integrate the residual distribution at the available number rather than classify cover directly.

**Source and analogy.** This borrows the control-variate/residual-learning idea: begin with a strong low-variance forecast and model only systematic discrepancy. It also resembles multi-fidelity modeling, where lower-fidelity outputs are scaled and corrected by a discrepancy process.[^6][^7]

**Why it may add information.** It prevents the model from wasting capacity relearning consensus and makes incremental edge attribution explicit.

**Targets.** Actual margin and total; cover/over probabilities at the cutoff quote. A separate version may predict close-minus-current line.

**Stabilization.** Approximately 2,000–5,000 games for a modest feature set; substantially more for interaction-rich learners. Evaluate by season and by timestamp.

**Primary failure mode.** Residual patterns are tiny, unstable, and vulnerable to overfit; training against close while using near-close information can disguise leakage.

**Kill test.** Require improvement over the untouched market in log score or CRPS in at least three consecutive forward seasons, with bootstrap confidence intervals clustered by week. Kill any feature family whose gain disappears when timestamps are shifted to the true availability time.

**Pregame status.** Strictly pregame at the selected market snapshot.

### 5. Analog Matchup Ensemble

**Definition.** A nonparametric predictive distribution built from historically similar pregame matchup states rather than from one global response surface.

**Estimation procedure.** Build standardized game-state vector $x_g$: offense-defense latent ratings, pace, explosiveness profile, line strength, personnel rates, QB experience, weather, altitude, travel, market spread/total, and rating uncertainty. Learn a diagonal or low-rank Mahalanobis distance inside each training fold. For new game $g$, find $K$ nearest prior games subject to date $<g$, and weight them

$$
w_i=\frac{\exp(-d(x_g,x_i)^2/h)}{\sum_{j\in N_K}\exp(-d(x_g,x_j)^2/h)}.
$$

Use the weighted empirical distribution of market residual margin and total as the forecast. Tune $K$, bandwidth, features, and conference/era constraints only through rolling validation. Meteorological analog ensembles similarly find historical states close to the current forecast and use the corresponding observations as a nonparametric predictive distribution; kernel-weighted ensembles improve on single analogs.[^8][^9][^10]

**Why it may add information.** It captures local nonlinear interactions and naturally returns skewness/multimodality. It is especially attractive as a challenger or calibration layer rather than the sole production model.

**Targets.** Margin residual, total residual, cover, over, upset probability.

**Stabilization.** Requires a broad archive; 2014-present FBS is likely enough for coarse analogs, but rare personnel/weather regimes may have fewer than 30 credible neighbors.

**Primary failure mode.** Distance concentration produces superficially similar but strategically irrelevant analogs.

**Kill test.** Compare against randomly selected games matched only on market spread/total and season. Kill the full analog system if learned distances do not improve CRPS or analog residual homogeneity over that simple comparator.

**Pregame status.** Strictly pregame.

### 6. Multi-Fidelity Strength Fusion

**Definition.** A latent-variable model that treats recruiting, returning production, PFF grades, play efficiency, and market ratings as noisy measurements of the same underlying unit strengths at different fidelities.

**Estimation procedure.** For each team-unit-week latent strength $\theta_{u,t}$, define observation models such as

$$
EPA^{obs}_{u,t}\sim N(a_E+b_E\theta_{u,t},\sigma^2_E/n_{plays}),
$$

$$
PFF^{obs}_{u,t}\sim N(a_P+b_P\theta_{u,t},\sigma^2_P/n_{snaps}),
$$

$$
Recruit_{u,t}\sim N(a_R+b_R\theta_{u,t},\sigma_R^2),
$$

with source-specific bias, heteroskedastic error, and missingness. Evolve $\theta$ dynamically and use it in the game outcome model. A higher-fidelity observation is represented as a scaled lower-fidelity process plus a discrepancy function, following co-kriging; Bayesian measurement-error models similarly separate outcome, measurement, and latent-variable submodels.[^11][^12][^6]

**Why it may add information.** It uses snap/play sample size and source reliability explicitly instead of treating every aggregate as error-free. The largest expected benefit is Weeks 0–4 and after QB/coach turnover.

**Targets.** Margin, total, early-season strength, unit-level future efficiency.

**Stabilization.** Source calibration requires multiple seasons; team posterior strength exists immediately and tightens with every game. At least 3–5 seasons are advisable for source-by-position reliability estimates.

**Primary failure mode.** Inputs do not measure one common latent construct; PFF, recruiting, and EPA may have different structural biases.

**Kill test.** Compare against simple ridge stacking of the same inputs. Kill the latent model if it fails to improve early-season log score and posterior interval coverage, or if estimated source loadings are unstable across adjacent training windows.

**Pregame status.** Strictly pregame.

### 7. Coherent Joint Score Model

**Definition.** A single probabilistic model for home points and away points whose draws automatically yield coherent margin, total, team-total, win, and cover probabilities.

**Estimation procedure.** Model $(Y_H,Y_A)$ with a bivariate negative-binomial, copula count model, or conditional normalizing flow. Parameterize conditional means from dynamic offense/defense and context, dispersion from pace/volatility, and dependence from expected possessions and game script. Generate posterior samples $(Y_H^{(s)},Y_A^{(s)})$, then derive $M^{(s)}=Y_H^{(s)}-Y_A^{(s)}$ and $T^{(s)}=Y_H^{(s)}+Y_A^{(s)}$. Use randomized probability-integral transforms for discrete calibration.

**Source and analogy.** Basketball and soccer score models separate attack and defense and issue posterior predictive score distributions. Bayesian hierarchical sports models are valuable because they pool sparse teams and propagate parameter uncertainty.[^13][^14][^15]

**Why it may add information.** Separate margin and total regressions can imply impossible or mutually inconsistent team scores. Joint dependence also matters for same-game and alternate markets.

**Targets.** Exact/team scores, margin, total, moneyline, team totals, correlated derivatives.

**Stabilization.** Approximately 3,000–6,000 games for parametric versions; flexible flow/copula variants need more. Team effects borrow strength immediately.

**Primary failure mode.** Count distributions may fit football’s clustered scoring increments poorly.

**Kill test.** Compare score, margin, and total CRPS jointly against independent direct models. Kill any count family that improves exact-score likelihood while worsening margin/total calibration.

**Pregame status.** Strictly pregame.

### 8. Regime-Gated Expert Ensemble

**Definition.** A mixture-of-experts in which a gating model assigns game-specific weights to specialist forecasters for trench mismatch, pace, QB uncertainty, weather, travel, market, and talent disparity.

**Estimation procedure.** Train specialists $f_k(x_k)$ on disjoint or intentionally limited feature families. Compute weights

$$
\pi_k(x)=\frac{\exp(g_k(x))}{\sum_j\exp(g_j(x))}, \qquad \hat p(y\mid x)=\sum_k\pi_k(x)p_k(y\mid x_k).
$$

Use out-of-fold specialist predictions to train the gate, with entropy regularization to prevent one expert from dominating and a minimum-weight floor for the market expert. Train separate gates for margin and total. Sports implementations have used contextual gates to change specialist weights by matchup conditions, though these examples are commercial rather than peer-reviewed evidence.[^16][^17]

**Why it may add information.** One global model assumes the same data-generating mechanism for a service-academy game, a high-altitude shootout, and a QB-injury game. The gate tests whether regimes truly require different models.

**Targets.** Margin, total, win/cover probability.

**Stabilization.** Experts may train with 3,000+ games; gates need thousands of honest out-of-fold predictions. Rare regimes require strong gate regularization.

**Primary failure mode.** The gate learns noise or proxies team identity, creating impressive in-sample specialization without forward lift.

**Kill test.** Compare to a convex ensemble with constant weights. Kill the gate if context-varying weights do not improve forward log score, or if gains vanish when team IDs and conference labels are excluded.

**Pregame status.** Strictly pregame.

### 9. Player-Unit Partial-Pooling Model

**Definition.** A hierarchical player-to-unit model that estimates how the expected on-field combination of QB, OL, receivers, front, and secondary contributes to future team performance.

**Estimation procedure.** For each play $n$, form sparse participation vector $a_n$ from player snap data and personnel. Model a residualized play outcome—preferably expected-play quality or pressure/coverage events rather than raw EPA—as

$$
y_n=\alpha_{team,season}+a_n'\beta+X_n'\gamma+\epsilon_n.
$$

Use position-specific hierarchical priors, ridge regularization, and player aging/transfer transitions. Aggregate expected game-active player effects by projected snap share. If exact participation is unavailable, fit unit-level random effects using PFF player grades and snap-weighted roster composition.

**Source and analogy.** This is basketball RAPM translated from lineups to football personnel packages. The key change is much stronger positional priors because football substitutions, responsibilities, and collinearity make unconstrained player effects poorly identified.

**Why it may add information.** Team-season aggregates react slowly to injuries, transfers, and new starters. A roster-based latent model can update before the next team-level sample exists.

**Targets.** Margin, sack/pressure rate, explosive pass rate, rushing efficiency, total.

**Stabilization.** QB effects may emerge within 150–300 dropbacks; OL/coverage player effects likely require 500–1,500 snaps or multi-season pooling. Unit-level effects should stabilize faster than individual non-QB effects.

**Primary failure mode.** Assignment and teammate collinearity make player coefficients non-causal and unstable.

**Kill test.** Evaluate injury/transfer natural holdouts: forecast games immediately after a starter change. Kill player-level complexity if snap-weighted PFF plus team effects matches or beats it.

**Pregame status.** Pregame only if projected availability and snap shares are timestamped; realized game snaps are forbidden.

### 10. Hidden Durability-State Model

**Definition.** A hidden semi-Markov model that infers whether an offense or defense is fresh, stressed, or degraded and forecasts second-half performance from pregame workload and depth.

**Estimation procedure.** Define latent state $D_{i,t}\in\{fresh,stressed,degraded\}$ with duration-dependent transition probabilities. Weekly emissions include first/second-half efficiency split, late-drive pressure, missed tackles or PFF decline, prior-game snaps, overtime, short rest, travel, altitude, and depth-weighted snap concentration. Estimate with EM or Bayesian forward-backward inference. Feed the pregame filtered probability $P(D_{i,t}\mid \mathcal F_{t-1})$ into quarter-level scoring or drive hazards. Reliability engineering uses HMMs to infer unobserved degradation from noisy observations and to estimate time to absorption or remaining useful life.[^18][^19]

**Why it may add information.** EPA averages do not encode latent durability or state duration. This model asks whether workload carries over asymmetrically into late-game defense and totals.

**Targets.** Second-half points, late-drive success, full-game total, favorite margin.

**Stabilization.** Conference-level transition dynamics need several thousand team-games. Team-specific durability should be heavily pooled and may need 1–2 seasons.

**Primary failure mode.** “Fatigue” states may merely relabel opponent quality, garbage time, or injuries.

**Kill test.** Match plays on score state, opponent rating, possession length, and starter availability. Kill the latent state if it adds no forward lift for second-half residuals after those controls.

**Pregame status.** Strictly pregame when only prior workload is used. Updating the state with current-game drives would create a separate live model.

### 11. Distributional Quantile Forecaster

**Definition.** A model that estimates the full conditional margin and total distributions directly rather than assuming constant-variance Gaussian residuals around point forecasts.

**Estimation procedure.** Fit quantiles $Q_Y(\tau\mid X)$ for $\tau\in\{0.01,0.025,0.05,\ldots,0.95,0.975,0.99\}$ with gradient-boosted quantile trees, distributional forests, or a monotone neural quantile function. Optimize pinball loss, impose non-crossing quantiles, and calibrate with rolling out-of-fold residual ranks. Include variance/skew drivers: spread magnitude, pace, pass rate, explosiveness concentration, weather, QB uncertainty, and depth.

**Source and analogy.** Finance separates conditional mean from volatility and tail risk. In football, the same expected margin can imply very different cover and alternate-line probabilities.

**Why it may add information.** It targets heteroskedasticity and skew, which are not contained in mean EPA or SP+. It can improve decision quality even if MAE is unchanged.

**Targets.** Alternate spreads/totals, upset tails, cover/over probability, expected shortfall-style loss.

**Stabilization.** Central quantiles may train with 3,000–5,000 games. The 1% and 99% tails require much more data or strong parametric pooling.

**Primary failure mode.** Extreme quantiles overfit sparse regimes and quantile crossing corrections hide instability.

**Kill test.** Require uniform PIT/rank calibration and lower weighted interval score than a heteroskedastic Gaussian baseline. Kill unsupported tail levels when empirical coverage misses nominal coverage materially in multiple forward seasons.

**Pregame status.** Strictly pregame.

### 12. Dynamic Expert-Weight Aggregator

**Definition.** An online ensemble whose weights shift over time according to each component model’s recent proper-scoring performance.

**Estimation procedure.** Let models $k$ produce predictive densities $p_{k,t}$. Update weights only after outcomes resolve:

$$
w_{k,t+1}\propto w_{k,t}\exp(-\eta_t L(y_t,p_{k,t})),
$$

with log score or CRPS loss, forgetting factor, minimum weight, and conference/market-target-specific pools. Use weekly batch updates to avoid within-week leakage. Online learning with expert advice explicitly permits time-varying weights over heterogeneous predictive models, while performance-weighted aggregation can outperform equal weighting when calibration data are relevant.[^20][^21]

**Why it may add information.** Model reliability changes after rule changes, transfer-portal shifts, quarterback injuries, and early-season uncertainty.

**Targets.** Any model density: margin, total, close, win.

**Stabilization.** Start from equal or historically optimized weights. Target-specific weights need roughly 100–300 resolved games to move meaningfully without excessive variance.

**Primary failure mode.** Short-term leaderboard chasing creates weight oscillation and selection on noise.

**Kill test.** Compare against equal weights and static stacking over every forward season. Kill dynamic updates if turnover-adjusted gain is absent or if weights respond more to one-week noise than persistent model degradation.

**Pregame status.** Strictly pregame.

### 13. Defense-Independent Execution Model

**Definition.** A DIPS-inspired latent model that separates offense-controlled execution, defense-controlled disruption, and jointly/noisily determined realization for passes, runs, and kicks.

**Estimation procedure.** Build linked submodels rather than one EPA regression. For dropbacks: (1) pre-snap play-family/target-area intent, (2) pressure probability from OL, front, personnel, and time-to-throw proxies, (3) accuracy/completion quality conditional on pressure and depth, (4) yards after catch conditional on catch location/personnel, and (5) turnover realization conditional on turnover-worthy indicators/PFF grades where available. For runs: intended gap/personnel, backfield penetration, contact location proxy, then post-contact realization. Forecast future offense and defense through posterior component effects, then simulate their interaction.

**Source and analogy.** Baseball DIPS/FIP separates pitcher-controlled events from defense and ball-in-play realization. Football has no perfectly defense-independent outcome, so the translation is explicitly a **degree-of-control decomposition**, not a claim that quarterback or defense can be isolated absolutely.

**Why it may add information.** Raw EPA confounds repeatable process with opponent, field position, and high-variance realization. Component models may regress interceptions, long touchdowns, and broken tackles more intelligently.

**Targets.** Future pass/run efficiency, sacks, interceptions, explosives, margin and total through simulation.

**Stabilization.** Intent and pressure components may become useful after 100–250 relevant plays; turnover realization needs 500+ dropbacks and strong pooling.

**Primary failure mode.** Missing tracking variables—separation, true pressure timing, intended gap—make the supposed control decomposition wrong.

**Kill test.** Predict next-game and next-season component outcomes. Kill any decomposition whose latent “controlled” estimate is less stable or less predictive than simple opponent-adjusted rolling rates.

**Pregame status.** Strictly pregame when all component effects use prior plays.

### 14. Scheme-Response Causal Forest

**Definition.** A heterogeneous-treatment model estimating which team profiles systematically gain or lose when changing personnel, tempo, run-pass balance, or defensive structure.

**Estimation procedure.** Define treatment at team-game level, such as an above-expected shift to 12 personnel, tempo, blitz rate, or pass rate. Estimate propensity $e(X)=P(W=1\mid X)$ and baseline outcome $m(X)=E[Y\mid X]$ using only pregame and prior-history variables. Fit an honest orthogonal causal forest to residualized treatment and outcome, producing $\hat\tau(X)$. For forecasting, combine the opponent’s historically stable scheme policy distribution with the estimated response surface; do not assume the future realized scheme is known. Causal forests were designed for heterogeneous treatment effects and use honest splitting and orthogonalization; sports work has applied them to strategy effects in basketball.[^22][^23]

**Why it may add information.** This targets matchup responsiveness, not average quality. It could identify that a defense’s apparent strength is conditional on opponents not forcing it into a specific personnel or tempo regime.

**Targets.** Matchup residual margin/total, unit efficiency under probable schemes.

**Stabilization.** Likely 10,000+ team-games or play-level treatment observations, with treatments pooled into a few high-support families.

**Primary failure mode.** Coaching choices are endogenous responses to private injury information, opponent weakness, or game script; overlap may be poor.

**Kill test.** Enforce overlap and negative-control tests, then evaluate predicted treatment heterogeneity in untouched seasons as recommended for causal-forest applications. Kill the model if high-versus-low predicted treatment-effect groups do not separate out of sample.[^24]

**Pregame status.** Pregame only through a forecast distribution over scheme choices. Using the actual game’s realized scheme would be post-kickoff leakage.

### 15. Low-Rank Interaction Factor Model

**Definition.** A matrix-factorization model that learns latent offensive-style and defensive-vulnerability vectors from opponent-adjusted game residuals.

**Estimation procedure.** After removing dynamic team mean strength, market, venue, weather, and roster covariates, model residual unit performance as

$$
r_{i,j,t}=u_{i,t}'v_{j,t}+\alpha_i+\delta_j+\epsilon_{i,j,t},
$$

where $u_i$ is an offense-style embedding and $v_j$ a defense-vulnerability embedding. Regularize rank to 2–8 dimensions and anchor interpretation by regressing factors on personnel, target distribution, run concepts, pressure, and coverage proxies. Permit slow temporal evolution.

**Source and analogy.** Collaborative filtering predicts an interaction from latent user and item tastes; here, offense is the “user,” defense the “item,” and residual performance the rating.

**Why it may add information.** Additive ratings cannot represent rock-paper-scissors interactions. The low-rank restriction is far more data-efficient than explicit team-pair effects.

**Targets.** Margin residual, offensive points, explosives, sacks, total.

**Stabilization.** Requires multiple seasons and connected schedules; expect weak early estimates until each team has faced 6–10 diverse opponents, mitigated by feature-informed priors.

**Primary failure mode.** Factors encode conference schedule and team quality rather than true interaction.

**Kill test.** Hold out entire cross-conference matchup blocks and newly promoted coordinators. Kill the interaction term if it cannot beat additive offense-defense models on these out-of-block games.

**Pregame status.** Strictly pregame.

### 16. Era-and-Conference Transport Model

**Definition.** A domain-adaptation model that reweights or transports historical games so they resemble the current season, conference, rules, and roster environment before fitting the predictor.

**Estimation procedure.** Define source distribution from older seasons and target distribution from current pregame covariates. Estimate density-ratio weights or an entropically regularized optimal-transport plan $\Gamma$ minimizing feature-distribution distance while preserving labels locally. Train the outcome model on transported/reweighted observations; compare global, conference-specific, and coach-era targets. Optimal transport domain adaptation learns a map or coupling between source and target feature distributions to improve prediction under shift.[^25][^26]

**Why it may add information.** FBS data from 2014 are abundant but may be structurally less relevant after tempo, transfer, clock-rule, and conference changes. This model trades sample size for relevance systematically.

**Targets.** Margin, total, team efficiency, calibration under current-season distribution shift.

**Stabilization.** Needs enough current-season unlabeled games/features to estimate target distribution—approximately 100–300 games—while outcomes remain strictly lagged.

**Primary failure mode.** Covariate alignment cannot repair conditional-label shift; transport may discard valuable rare cases.

**Kill test.** Conduct leave-one-season-out tests with artificial source/target splits. Kill if transport does not improve the known held-out target season over simple recency weighting.

**Pregame status.** Strictly pregame because target-domain covariates need not include outcomes.

### 17. Selective Conformal Edge Model

**Definition.** A wrapper that issues bets or narrow forecasts only when rolling conformal calibration indicates reliable conditional uncertainty at the chosen market snapshot.

**Estimation procedure.** Fit any base margin/total model on past seasons. On a later calibration window, compute nonconformity scores $a_i=|y_i-\hat y_i|/\hat\sigma_i$, optionally within Mondrian groups such as spread bucket, season phase, QB uncertainty, and weather. For a new game, obtain interval

$$
C_t(x)=[\hat y_t-q_{1-\alpha}\hat\sigma_t,\hat y_t+q_{1-\alpha}\hat\sigma_t].
$$

Bet only if the entire relevant conformal set lies beyond the market break-even threshold, or use selection-conditional conformal methods to recalibrate specifically on selected games. Conformal win probabilities have been applied in college basketball, and selection-conditional methods address the fact that ordinary marginal coverage need not survive a data-driven pick rule.[^27][^28]

**Why it may add information.** It does not necessarily improve the mean forecast; it improves **decision selectivity and uncertainty honesty**, which standard accuracy metrics miss.

**Targets.** Bet/no-bet, prediction interval, win/cover probability calibration.

**Stabilization.** Calibration windows need at least several hundred games; conditional groups generally need 100+ examples or pooled quantiles.

**Primary failure mode.** Exchangeability fails across seasons, and selecting only apparent edges invalidates ordinary conformal coverage. Adaptive conformal methods exist for sequential nonstationarity but still require empirical sports validation.[^29]

**Kill test.** Measure interval coverage and calibration specifically among selected bets, not all games. Kill the selector if selected-set coverage misses target or if edge concentration does not improve utility after vig.

**Pregame status.** Strictly pregame.

### 18. Recurrent Frailty Game Simulator

**Definition.** A possession-count and scoring model with team-game random frailty that induces correlation among repeated drives beyond observed covariates.

**Estimation procedure.** Treat each drive as a recurrent event with shared game-level frailties $z_O,z_D$. Conditional drive termination/scoring hazard is

$$
\lambda_{k}(t\mid X,z)=z\lambda_{0k}(t)\exp(X'\beta_k),
$$

where $k$ indexes scoring and non-scoring endpoints. Draw frailty at game start from a distribution whose variance depends on pace disagreement, weather uncertainty, and QB uncertainty. Simulate recurrent drives and clock jointly. Epidemiological recurrent-event models use frailty to represent unobserved susceptibility shared across repeated event times, while multi-state models estimate transition intensities among intermediate states.[^30][^31]

**Why it may add information.** Independent-drive simulations understate between-game heterogeneity and within-game correlation. A hot/cold latent environment can widen total and margin tails without changing average EPA.

**Targets.** Possession count, team scores, total variance, same-game dependence.

**Stabilization.** Baseline hazards use all plays; frailty variance likely needs 3,000+ games and careful pooling.

**Primary failure mode.** Frailty becomes a catch-all for model misspecification rather than a transferable pregame uncertainty source.

**Kill test.** Compare held-out within-game residual correlation and total-tail coverage with and without frailty. Kill if estimated frailty improves in-sample fit but not predictive distributions.

**Pregame status.** Strictly pregame when frailty is drawn from its pregame distribution, not inferred from current-game outcomes.

### 19. Tail-Spliced Blowout Model

**Definition.** A predictive density that uses a flexible central model for ordinary outcomes and generalized-Pareto tails for extreme margins or totals.

**Estimation procedure.** Fit central residual density $H(r\mid X)$. Choose thresholds $u_L,u_U$ using training data only, then fit conditional generalized Pareto distributions to exceedances $u_L-r$ and $r-u_U$, with scale depending on talent disparity, pace, explosiveness, QB uncertainty, and depth. Splice the densities continuously and calibrate tail probability with rolling folds. Extreme-mixture forecasting similarly uses a regular bulk distribution and GPD components for rare lower and upper values.[^32][^33][^34]

**Why it may add information.** Gaussian residuals often misprice 95th–99th percentile outcomes. Tail shape matters for alternate lines, large favorites, and correlated parlays more than for median spread prediction.

**Targets.** Blowout probability, very high/low totals, alternate spreads, tail expected loss.

**Stabilization.** Tail estimation is data hungry: at a 90th-percentile threshold, 10,000 games yield only about 1,000 combined tail cases before conditioning. Hierarchical pooling is mandatory.

**Primary failure mode.** Threshold choice and nonstationary blowout behavior dominate the estimated tail.

**Kill test.** Require improved extreme-quantile coverage and tail-weighted CRPS over Student-t and skew-t baselines. Kill GPD complexity if simpler heavy-tailed distributions match it.

**Pregame status.** Strictly pregame.

### 20. Cross-Level Forecast Reconciliation

**Definition.** A post-model layer that reconciles independently generated play/drive, team-score, margin, and total forecasts into one coherent minimum-variance system.

**Estimation procedure.** Stack base forecasts $\hat y$ for home points, away points, margin, total, and where available expected drive points. Define linear aggregation matrix $S$ so coherent forecasts satisfy margin $=H-A$ and total $=H+A$. Estimate base forecast-error covariance $W$ from rolling out-of-fold predictions and compute

$$
\tilde y=S(S'W^{-1}S)^{-1}S'W^{-1}\hat y.
$$

For full densities, reconcile Monte Carlo draws or use Gaussian probabilistic reconciliation. MinT is designed to minimize total forecast-error variance under coherence and unbiasedness; probabilistic reconciliation extends the idea to predictive distributions.[^35][^36][^37]

**Why it may add information.** Specialized models may each be strongest at one level, yet their raw outputs conflict. Reconciliation can exploit correlated errors without replacing the base models.

**Targets.** Coherent team scores, margin, total, and derivative probabilities.

**Stabilization.** Needs 1,000–3,000 honest out-of-fold games for a stable shrinkage covariance matrix; diagonal approximations need less.

**Primary failure mode.** MinT’s unbiasedness/covariance assumptions fail and reconciliation damages the strongest forecast to satisfy weaker ones.

**Kill test.** Compare every individual target before and after reconciliation. Kill or constrain reconciliation if aggregate gain comes at unacceptable degradation to the primary betting target.

**Pregame status.** Strictly pregame.

### 21. Functional Season-Trajectory GP

**Definition.** A multi-task Gaussian-process model that forecasts a team’s evolving offense, defense, pace, and player-unit form as smooth but uncertain season trajectories.

**Estimation procedure.** Treat each team’s weekly latent performance as an irregularly observed function $f_i(t)$. Fit a multi-output GP with shared population kernel plus team, coach, and roster-change components:

$$
f_i(t)=\mu_{conference}(t)+g_{coach}(t)+h_i(t)+\epsilon_{i,t}.
$$

Observations are opponent-adjusted game or play aggregates with known sampling variance. Add changepoint kernels at QB changes, coordinator changes, and bye weeks. Multi-task functional GP models share information across individuals and quantify uncertainty in future performance curves; functional sports forecasting has been used for athlete career trajectories.[^38][^39]

**Why it may add information.** Rolling averages impose arbitrary windows and react poorly to irregular schedules. A GP can express uncertainty, smooth noisy games, and model different rates of improvement or decay.

**Targets.** Next-game latent strength, late-season performance, margin and total through downstream models.

**Stabilization.** Population kernels require several seasons; team trajectories can update after each game but remain prior-dominated through roughly Week 3.

**Primary failure mode.** Smoothness is wrong: injuries and tactical changes produce abrupt jumps, while GP uncertainty may be expensive and poorly calibrated at FBS scale.

**Kill test.** Compare to an exponentially weighted state-space model with the same inputs. Kill the GP if it cannot improve next-week log likelihood or changepoint recovery enough to justify computational cost.

**Pregame status.** Strictly pregame.

## Evaluation protocol

Every candidate should face the same nested, timestamp-aware tournament:

1. **Outer folds:** Train through season $s-1$, tune without season $s$, then predict every game in $s$. Never random-split games.
2. **Timestamp panels:** Evaluate fixed snapshots separately—open, Sunday night, midweek, game day, and final pre-kick. A model that predicts the close at Sunday is solving a different task from a model predicting outcomes at kickoff.
3. **Baselines:** Market-only; SP+/FPI-only; market plus linear football features; market-anchored gradient boosting; current production ensemble.
4. **Proper scores:** MAE/RMSE for point location, log score and CRPS for distributions, Brier/log loss for binary markets, weighted interval score and empirical coverage for uncertainty.
5. **Betting diagnostics:** CLV and expected log growth are secondary diagnostics; realized ROI is too noisy to serve as the primary model-selection loss.
6. **Dependence-aware uncertainty:** Bootstrap by week or game slate, not individual game, and report season-by-season deltas rather than only pooled averages.
7. **Ablation:** For every complex model, compare the smallest nested version: static versus dynamic, additive versus interaction, direct versus simulated, constant versus gated weights.
8. **Calibration:** Check probability calibration by market bucket, favorite size, total bucket, season phase, conference, QB uncertainty, and weather regime.
9. **Leakage audit:** Persist `available_at`, `observed_at`, and `effective_at` for every source. Reconstruct each historical forecast from the data snapshot that would actually have existed.
10. **Promotion rule:** Require positive proper-score improvement in multiple forward seasons, acceptable worst-season degradation, stable calibration, and a documented mechanism—not just pooled significance.

## First three builds

### Four-Axis Dynamic Team State

Build this first because it becomes the shared latent backbone for nearly every later model. It converts offense, defense, pace, and variance into filtered distributions with explicit uncertainty; that supports margin, total, simulations, and early-season shrinkage. The NFL state-space precedent reduces implementation risk, while separate pace and variance states create a clear test of information not already summarized by SP+ or EPA.[^1][^2]

### Market-Anchored Residual Distribution

Build this second because it is the fastest honest test of whether the existing data stack contains incremental edge. It is simple, difficult to fool if timestamping is correct, and produces interpretable ablations by feature family. If this model cannot beat the cutoff-time market in forward proper scores, more elaborate architectures should be treated as research rather than production.

### Competing-Risk Drive Renewal Simulator

Build this third because it changes the output from one point estimate to a structurally generated score distribution. It directly supports totals, team totals, alternate lines, and game-path analysis, while creating reusable drive hazards and transition kernels. The crucial gate is posterior predictive realism: the simulator earns promotion only if it reproduces drive, possession, clock, and scoring distributions before betting performance is considered.[^5][^3][^4]

The **Latent Consensus Market Nowcaster** should move ahead of the drive simulator if the immediate business objective is predicting close/CLV rather than game outcomes. Its prerequisite is a passed audit of book identity, quote normalization, timestamp precision, suspended markets, and stale-line handling.

---

## References

1. [[PDF] A State-Space Model for National Football League Scores](https://www.glicko.net/research/nfl.pdf)

2. [How often does the best team win?A unified approach to ...](https://arxiv.org/pdf/1701.05976.pdf)

3. [Simulation-Based Decision Making in the NFL using ...](https://arxiv.org/html/2102.01846v3)

4. [Discrete-time Survival Analysis with Competing Risks](https://tomer1812.github.io/projects-pydts/) - Time-to-event analysis (survival analysis) is used when the outcome of interest is the time until a ...

5. [A competing risk survival analysis of the impacts of team ...](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1323930/full) - by S Le Coz · 2024 · Cited by 6 — Competing risks data occurs when there are multiple possible outco...

6. [Multi-fidelity Gaussian process regression for prediction of ...](https://arts.units.it/retrieve/e2913fde-9adf-f688-e053-3705fe0a67e0/2903585_1-s2.0-S0021999117300633-main-PostPrint.pdf)

7. [Multi-fidelity modelling via recursive co-kriging and Gaussian–Markov random fields | Proceedings of the Royal Society A: Mathematical, Physical and Engineering Sciences](https://royalsocietypublishing.org/doi/10.1098/rspa.2015.0018) - We propose a new framework for design under uncertainty based on stochastic computer simulations and...

8. [Analog ensemble data assimilation in a quasigeostrophic coupled model](https://repository.library.noaa.gov/view/noaa/68131/noaa_68131_DS1.pdf)

9. [Analog Forecasting with Dynamics-Adapted Kernels](https://arxiv.org/abs/1412.3831) - by Z Zhao · 2014 · Cited by 112 — Here, we introduce a suite of forecasting methods which improve tr...

10. [Geosci. Model Dev., 12, 2915–2940, 2019](https://gmd.copernicus.org/articles/12/2915/2019/gmd-12-2915-2019.pdf)

11. [CORRECTING FOR MEASUREMENT ERROR IN LATENT VARIABLES USED AS ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC4787301/) - This paper represents a methodological-substantive synergy. A new model, the Mixed Effects Structura...

12. [A Bayesian Approach to Modeling Measurement Errors](https://ww2.amstat.org/meetings/proceedings/2014/data/assets/pdf/311698_87978.pdf)

13. [Bayesian statistics meets sports: a comprehensive review](https://www.degruyterbrill.com/document/doi/10.1515/jqas-2018-0106/html?lang=en) - Bayesian methods are becoming increasingly popular in sports analytics. Identified advantages of the...

14. [Bayesian hierarchical model for the prediction of football ...](https://discovery.ucl.ac.uk/16040/1/16040.pdf) - We propose in this paper a Bayesian herarchical model for the number of goals scored by the two team...

15. [Bayesian hierarchical model for the prediction of football ...](https://www.tandfonline.com/doi/abs/10.1080/02664760802684177) - by G Baio · 2010 · Cited by 286 — We propose a Bayesian hierarchical model to fulfil both these aims...

16. [NCAA Basketball Betting System - Algorithmic.co](https://www.algorithmic.co/works/ncaa-basketball-sports-betting/) - Predictive ML system across 350+ college basketball programs. Tournament auto-scaling, real-time inf...

17. [NBA Betting Engine - Algorithmic.co](https://www.algorithmic.co/works/nba-sports-betting-platform/) - ML engine processing 3,000+ features with sub-minute refresh. 9% ROI across moneyline, spread, and o...

18. [Hidden Markov model with auto-correlated observations for ...](https://ideas.repec.org/a/eee/reensy/v184y2019icp123-136.html) - In this paper, a hidden Markov model with auto-correlated observations (HMM-AO) is developed to hand...

19. [Robust HMM-Based Remaining Useful Life Estimation Using a Ridge-Regularized EM Algorithm](https://pmc.ncbi.nlm.nih.gov/articles/PMC12944381/) - Estimating the remaining useful life (RUL) of engineering systems is crucial for maintenance plannin...

20. [Mathematically aggregating experts' predictions of possible ...](https://minerva-access.unimelb.edu.au/server/api/core/bitstreams/4020e850-dc05-5b16-b470-4d9772070b25/content)

21. [Machine Learning and Financial Crises](https://www.nber.org/system/files/working_papers/w28302/revisions/w28302.rev0.pdf)

22. [The Causal Effect of the Two-For-One Strategy in the National Basketball Association](https://ar5iv.labs.arxiv.org/html/2412.08840) - This study evaluates the effectiveness of the “two-for-one” strategy in basketball by applying a cau...

23. [Estimation and Inference of Heterogeneous Treatment Effects using ...](https://arxiv.org/abs/1510.04342) - Many scientific and engineering challenges -- ranging from personalized medicine to customized marke...

24. [Using Causal Forests to Predict Treatment Heterogeneity](https://www.aeaweb.org/articles?id=10.1257/aer.p20171000) - by JMV Davis · 2017 · Cited by 309 — Our application highlights some limitations of the causal fores...

25. [Joint Distribution Optimal Transportation for Domain Adaptation](https://arxiv.org/abs/1705.08848) - This paper deals with the unsupervised domain adaptation problem, where one wants to estimate a pred...

26. [Optimal Transport for Domain Adaptation](https://arxiv.org/abs/1507.00504) - Domain adaptation from one data space (or domain) to another is one of the most challenging tasks of...

27. [Using Conformal Win Probability to Predict the Winners of ...](https://par.nsf.gov/servlets/purl/10481258)

28. [Confidence on the focal: conformal prediction with selection-conditional coverage](https://academic.oup.com/jrsssb/advance-article/doi/10.1093/jrsssb/qkaf016/8113856?searchresult=1) - Abstract. Conformal prediction builds marginally valid prediction intervals that cover the unknown o...

29. [Adaptive Conformal Inference by Betting](https://arxiv.org/html/2412.19318v1) - Conformal prediction is a valuable tool for quantifying predictive uncertainty of machine learning m...

30. [Modelling recurrent events: a tutorial for analysis in epidemiology](https://academic.oup.com/ije/article/44/1/324/654595) - Abstract. In many biomedical studies, the event of interest can occur more than once in a participan...

31. [[PDF] Multistate event history analysis with frailty - Demographic Research](https://www.demographic-research.org/volumes/vol30/58/30-58.pdf)

32. [Deep extreme mixture model for time series forecasting](https://pureadmin.qub.ac.uk/ws/files/364690713/accepted_version.pdf)

33. [[PDF] Extreme Value Mixture Modelling: evmix Package and Simulation ...](https://www.math.canterbury.ac.nz/~c.scarrott/evmix/EVA2013.pdf)

34. [Modeling Censored Losses Using Splicing: A Global Fit Strategy with Mixed Erlang and Extreme Value Distributions](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2872107) - In risk analysis, a global fit that appropriately captures the body and the tail of the distribution...

35. [Optimal forecast reconciliation for hierarchical and grouped ...](https://robjhyndman.com/papers/MinT.pdf)

36. [Coherent Probabilistic Forecasts for Hierarchical Time Series](http://proceedings.mlr.press/v70/taieb17a/taieb17a.pdf)

37. [Probabilistic Forecast Reconciliation under the Gaussian Framework](https://www.tandfonline.com/doi/full/10.1080/07350015.2023.2181176) - Forecast reconciliation of multivariate time series maps a set of incoherent forecasts into coherent...

38. [Multi-task learning models for functional data and application to the prediction of sports performances](https://theses.hal.science/tel-03226194v1) - The present document is dedicated to the analysis of functional data and the definition of multi-tas...

39. [Forecasting basketball players' performance using sparse functional data](https://scispace.com/pdf/forecasting-basketball-players-performance-using-sparse-49mr1d42eh.pdf)

