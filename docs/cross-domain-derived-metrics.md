# Novel Cross-Domain Derived Metrics for FBS College Football Modeling

This catalog proposes 22 candidate metrics for descriptive and predictive modeling of FBS college football, each deliberately absent from the user's stated inventory (EPA/play, success rate, PPA, SP+, FPI, havoc, explosiveness, finishing drives, field position, adjusted pace, PFF grades, line yards, stuff rate, and standard market features). Every candidate is constructible from the held data (play-by-play 2014-present, drive/game results, team/season aggregates, PFF grades and snap/personnel rates, coach/venue/weather/travel, and multi-book timestamped lines). Each borrows a specific concept from outside football and states why it should add information orthogonal to EPA/success-rate/SP+.

Two structural cautions frame everything below. First, the underlying scoring machinery of football is already captured by expected points (EP), the same baseline-relative, state-value idea that powers golf's strokes gained and soccer's xG. Any metric that merely re-sums EPA differently is not novel — it is EPA in disguise. The genuinely additive candidates below capture **shape, dispersion, timing, sequencing, or market-microstructure** properties that a mean-EPA number discards. Second, baseball's stabilization literature is a hard constraint on ambition: EPA/play itself needs roughly 250-300 plays (about seven games of one unit) to stabilize, turnover rates barely stabilize within a season, and any metric built on rarer events (fourth downs, red-zone trips, explosive plays) stabilizes even slower and must be shrunk aggressively toward a prior.[^1][^2][^3][^4]

## How the ranking was built

Metrics are ranked by expected predictive lift per unit of implementation effort. The ranking rewards candidates that (a) are strictly pre-game computable from trailing data, (b) plausibly carry information the market total/spread does not already embed, (c) stabilize fast enough to be usable within a season, and (d) are cheap to build from existing columns. It penalizes candidates that require in-game data, are descriptive-only, stabilize slowly, or are likely to proxy the market line. A metric that is analytically elegant but only descriptive (uses a game's own outcome) is ranked low as a *feature* even if it is valuable for model diagnostics.

A critical distinction runs through the market-derived candidates: predicting the **closing line** is a fundamentally different task from predicting the **game outcome**, and a good closing-line predictor can have zero edge on the actual result — this is flagged per metric.[^5]

## Ranked candidate metrics

| # | Metric | Source concept | Predicts | Pre-game? | Stabilization | Why orthogonal to EPA/SR/SP+ |
|---|--------|---------------|----------|-----------|--------------|------------------------------|
| 1 | Drive-Survival Hazard Curve (DSHC) | Survival/competing-risk hazards[^6][^7] | Total, drive points | Yes (trailing) | ~40-60 drives (fast) | Encodes *where* on the field a unit fails, not average value |
| 2 | Market Microstructure Order-Flow Index (MOFI) | Finance order flow / price impact[^5][^8] | Closing line, CLV | Yes (intra-week) | ~1 season of games | Pure market-structure signal, no team-efficiency content |
| 3 | Realized Score-Path Volatility (RSV) | Finance realized variance[^9][^10] | Total variance, live-hedge, under/over dispersion | Yes (trailing) | ~6-8 games | Second moment of scoring; EPA is a first-moment mean |
| 4 | Pace-Neutral Tempo Elasticity (PNTE) | Physics damping / control systems | Total, plays | Yes (trailing) | ~5-7 games | How pace *responds* to score state, not average pace |
| 5 | Play-Call Surprisal / KL Divergence (PCS) | Information theory entropy/KL[^11][^12] | Margin, cover | Yes (trailing) | ~150-200 plays | Predictability of a scheme, not its efficiency |
| 6 | Kalman Latent-Strength Innovation (KLSI) | Kalman filtering[^13][^14] | Margin, spread | Yes (trailing) | Recursive (usable ~4 games) | Uncertainty-weighted update; SP+ is a point estimate |
| 7 | Finishing-over-Expected on Shot Quality (FoESQ) | Basketball qSI / soccer xGOT[^15][^16] | Regression flag, over/under | Yes (trailing) | Slow (~full season) | Separates chance *creation* from *conversion luck* |
| 8 | Football PDO (fPDO) | Hockey/soccer PDO luck index[^17] | Mean-reversion / regression flag | Yes (trailing) | Slow (luck by design) | Explicitly isolates luck EPA cannot |
| 9 | Special-Teams & Turnover Hidden Points (HP) | Hidden Game / DVOA hidden value[^18][^19] | Margin, spread | Yes (trailing) | ~8-10 games | Field-position value outside offense/defense EPA |
| 10 | Leverage-Weighted Efficiency (LWE) | Baseball WPA leverage index | Margin, cover | Yes (trailing) | ~6-8 games | Weights plays by situational importance, not equally |
| 11 | Garbage-Time-Stripped Core Efficiency (GTS) | Basketball possession filtering | Margin, total | Yes (trailing) | ~5-7 games | Removes non-representative snaps EPA/play includes |
| 12 | DIPS-Style Defense-Independent Rush Value (DIRV) | Baseball DIPS/FIP[^3] | Margin, regression flag | Yes (trailing) | Faster than raw rush EPA | Strips defense/luck from a noisy component |
| 13 | Explosive-Play Renewal Rate (EPRR) | Queueing/renewal processes[^6] | Total, explosiveness | Yes (trailing) | ~200+ plays | Time-between-events, not average magnitude |
| 14 | Cross-Book Lead-Lag Dislocation (CBLL) | Finance microstructure lead-lag[^20][^21] | Closing line, stale-price | Yes (intra-week) | ~1 season (2020+ only) | Inter-book dynamics, no team content |
| 15 | Momentum-Impulse Score Index (MISI) | Physics momentum/impulse | Live model, descriptive | **No (in-game)** | ~8-10 games | Sequencing of scoring runs |
| 16 | Zone-Diversity of Personnel Usage (ZDPU) | Ecology Simpson/Shannon diversity[^22][^23] | Margin, injury-robustness | Yes (trailing) | ~4-6 games | Roster concentration/fragility, not efficiency |
| 17 | Field-Position Potential Energy (FPPE) | Physics potential energy[^18] | Total, field position | Yes (trailing) | Fast (~4-5 games) | Non-linear yard-line value curve as a state |
| 18 | Coach Tendency Regime Stability (CTRS) | Change-point detection | Margin, early-season | Yes (trailing) | Event-driven | Detects scheme breaks EPA averages hide |
| 19 | Sharpe-Style Efficiency Ratio (SSER) | Finance Sharpe ratio[^9] | Margin, cover | Yes (trailing) | ~6-8 games | Risk-adjusted EPA (mean/vol), not mean alone |
| 20 | Hysteresis / Mean-Reversion Half-Life (HMRL) | Physics hysteresis / mean reversion | Regression flag, spread | Yes (trailing) | ~1 season | Speed a team reverts to baseline |
| 21 | Park-Factor Venue Adjustment (PFVA) | Baseball park factors[^2] | Total, home edge | Yes (pre-game) | Slow (multi-season) | Venue residual after team quality |
| 22 | Phase-Transition Blowout Threshold (PTBT) | Physics phase transitions | Live model, descriptive | **No (in-game)** | ~1 season | Non-linear score-state tipping point |

## Detailed specifications

### 1. Drive-Survival Hazard Curve (DSHC)

**Definition:** For each unit, the cause-specific hazard rate of a drive terminating in a touchdown, field goal, punt, or turnover as a function of yard-line "distance traveled," estimated as a piecewise-exponential competing-risks model.

**Source and analogy:** Directly adapts survival analysis with competing risks, treating a drive as an entity that "survives" across yard-line intervals until it "dies" by one of several causes. Weitzenfeld's hierarchical Bayesian NFL drive-survival model is a direct published precedent — so this adaptation has been done in the NFL but not, in the searched sources, at FBS scale as a pre-game feature.[^6][^7]

**Estimation:** Bin the field into intervals $\tau_k$; estimate baseline hazards $\lambda_{jk}$ for each termination cause $j$ in interval $k$, modeling failures as Poisson with mean $\mu_{ijk}=E_{ik}e^{\alpha_{jk}+x_i'\beta_j}$, and recover the conditional cause probability as $\pi_{jk}=e^{\alpha_{jk}+x'\beta_j}/\sum_r e^{\alpha_{rk}+x'\beta_r}$. Compute team-level trailing hazard curves entering each game from drives in prior completed games only.[^24][^6]

**Predicts:** Game total and drive-level scoring distribution; the shape of the hazard curve (e.g., a defense that fails early in its own territory vs. one that bends-but-holds in the red zone) carries total-points information a mean stop rate hides.

**Orthogonality:** EPA/play averages value per snap; DSHC captures the *conditional field-position geometry* of scoring and stalling, which two teams with identical mean defensive EPA can differ on sharply.

**Stabilization:** Roughly 40-60 drives (about six to eight games of one unit) because drive terminations are relatively frequent, faster than play-level EPA at ~250-300 plays.[^3]

**Confound / failure test:** Opponent quality contaminates raw hazards; must be opponent-adjusted. **Falsification:** if a simulated total built from DSHC hazards does not beat a direct total regression out-of-sample, abandon it — the same acceptance test the user's own frontier notes apply to competing-risk drive models.

**Pre-game:** Yes, strictly trailing.

### 2. Market Microstructure Order-Flow Index (MOFI)

**Definition:** A signed, magnitude-weighted index of intra-week line moves that distinguishes informed (steam, reverse-line-movement) from noise (public drift) flow, built from the timestamped multi-book quotes.

**Source and analogy:** Borrows the finance microstructure distinction between informed and uninformed order flow and price impact. A steam move — coordinated volume moving the line within minutes — is the sports analogue of informed order flow being absorbed into price, while late public drift toward favorites/overs is uninformed flow.[^8][^5]

**Estimation:** For each game, construct a time-ordered sequence of line changes across books; flag reverse line movement (line moves against public-ticket majority) and cross-book steam (near-simultaneous same-direction moves). Weight each move by size and speed; sum into a signed index. Where public-ticket percentages are unavailable, proxy informed flow by early/off-hours moves at low limits, which are rarely public-driven.[^21]

**Predicts:** The **closing line** and closing-line value (CLV) — explicitly a market-prediction task, not a game-outcome task; flag that MOFI edge on the close need not translate to edge on the result.[^5]

**Orthogonality:** Contains no team-efficiency content whatsoever; it is a pure market-structure signal, orthogonal to EPA/SP+ by construction.

**Stabilization:** Roughly one season of games to estimate stable flow-to-close relationships; noisy per-game.

**Confound / failure test:** Book-identity and timestamp fidelity in the stored data must be audited first — the user's own top-priority experiment — because misattributed opener/close fields would poison MOFI. **Falsification:** if MOFI has no incremental power over the current line in predicting the close across ≥2 chronological folds, kill it.[^5]

**Pre-game:** Yes, but only usable for FBS from mid-2020 forward given historical odds coverage limits.

### 3. Realized Score-Path Volatility (RSV)

**Definition:** The trailing realized variance of a team's within-game scoring-margin path, analogous to realized variance of an asset price series.

**Source and analogy:** Adapts finance realized volatility. Stern's implied-volatility-of-a-game model treats the score margin as Brownian motion $X(t)=\mu t+\sigma B(t)$ with drift $\mu$ and volatility $\sigma$; the market spread implies $\mu$ and the total implies scale, letting you compare a team's *realized* score-path volatility to the market-implied volatility.[^25][^9][^10]

**Estimation:** From play-by-play, reconstruct the score-margin time series per game; compute realized variance of margin increments per possession or per minute; average over trailing games. Compare to market-implied $\sigma_{IV}=\mu/\Phi^{-1}(p)$ derived from spread and moneyline.[^9]

**Predicts:** The variance of the total (not its mean) — directly useful for distinguishing two games with the same expected total but different tail risk, which is exactly where distributional models like NGBoost/GAMLSS earn their keep in the user's frontier plan.

**Orthogonality:** EPA and SP+ are first-moment (mean) quantities; RSV is a second-moment quantity and is close to orthogonal by construction.

**Stabilization:** Roughly six to eight games; variance estimates are noisier than means, so shrink toward league volatility.

**Confound / failure test:** Garbage time inflates late-game variance and must be stripped. **Falsification:** if predicted variance is uncorrelated with squared out-of-sample total residuals, discard — identical to the user's own NGBoost falsification criterion.

**Pre-game:** Yes, trailing; the *market-implied* companion is also pre-game, but any within-the-game realized path is descriptive-only.

### 4. Pace-Neutral Tempo Elasticity (PNTE)

**Definition:** The sensitivity of a team's snap rate to the current score margin — how much a team speeds up when trailing and slows when leading — estimated as a regression slope of seconds-per-play on score state.

**Source and analogy:** Borrows damping/control-system dynamics from physics: a team's tempo is a controlled variable that responds to the "restoring force" of the scoreboard. This is distinct from adjusted pace (already held), which is an *average* rate; PNTE is the *response function*.

**Estimation:** Regress seconds-per-play (or plays-per-minute) on signed score margin and time remaining within trailing games; the coefficient on margin is the elasticity. Opponent-adjust for the opponent's pace-forcing tendency.

**Predicts:** Game total and total plays, especially in games projected to be lopsided, where a high-elasticity favorite will bleed clock and suppress the total more than average pace implies.

**Orthogonality:** Average pace cannot distinguish a team that plays fast always from one that only plays fast when trailing; PNTE isolates the state-dependent component, adding information beyond adjusted pace.

**Stabilization:** Roughly five to seven games once enough varied score states are observed; teams rarely trailing give noisy estimates and need shrinkage.

**Confound / failure test:** Selection bias — good teams rarely trail, so their catch-up elasticity is barely observed. **Falsification:** if PNTE adds nothing to a total model already containing average pace and projected margin, drop it.

**Pre-game:** Yes, trailing.

### 5. Play-Call Surprisal / KL Divergence (PCS)

**Definition:** The situational unpredictability of a team's play-calling, measured as conditional Shannon entropy of the run/pass (and personnel) distribution by down-distance-field-position bucket, plus the KL divergence between a team's actual and situation-expected call distribution.

**Source and analogy:** Information theory. Higher entropy means less predictable play-calling; a 50/50 run-pass split is maximum binary entropy (1.0) while 90% pass drops to ~0.47. KL divergence measures how far a team's calls diverge from the league-average situational baseline — the "surprisal" a defense faces. Soccer research using event-distribution entropy found unpredictability positively associated with winning, giving an adjacent published precedent.[^11][^22][^23][^12]

**Estimation:** For each down-distance-field bucket, compute the team's call distribution and its Shannon entropy $H=-\sum p_i\log p_i$; average as conditional entropy, and compute $D_{KL}$(team ‖ league) per bucket. A reference Python implementation of exactly this conditional-entropy predictability score exists.[^26][^12][^11]

**Predicts:** Margin and cover; the hypothesis is that unpredictable offenses gain a small persistent edge, weakening late in games as they become more predictable — the same decay soccer studies observed.[^22]

**Orthogonality:** Two offenses with identical EPA/play can have very different predictability; PCS captures a game-theoretic property EPA is blind to.

**Stabilization:** Roughly 150-200 plays for the aggregate distribution; situational (conditional) entropy needs more because buckets are sparse, requiring smoothing.

**Confound / failure test:** Score state confounds calls (leading teams run); condition on neutral game states only. **Falsification:** if PCS has no relationship to margin after controlling for EPA and pace, discard.

**Pre-game:** Yes, trailing.

### 6. Kalman Latent-Strength Innovation (KLSI)

**Definition:** A recursively updated latent offense/defense/pace strength state per team, with the Kalman gain and innovation (surprise) term exposed as features — capturing both the current estimate and how much recent results *surprised* the model.

**Source and analogy:** State-space filtering. Team strength is a hidden state that drifts between games (a mean-reverting Ornstein-Uhlenbeck or random walk) and updates on each result via $R_{new}=R_{old}+K(S-E)$, where the gain $K$ is learned rather than fixed, so upsets between uncertain teams move ratings more than shocks between well-understood teams. Glickman-Stern's NFL state-space score model and multiple soccer Kalman ratings are direct precedents.[^13][^27][^14][^28]

**Estimation:** Fit a local-level or OU Kalman filter to a chosen efficiency series (e.g., opponent-adjusted points per drive), tracking state mean and covariance; expose the innovation $(S-E)$, the gain $K$, and the posterior variance $P$ as features. The covariance $P$ natively quantifies confidence — a feature SP+/FPI point estimates lack.[^29][^13]

**Predicts:** Margin and spread; the innovation term flags teams the market may be slow to reprice after a regime shift.

**Orthogonality:** SP+ and FPI are point estimates with fixed, opaque updating; KLSI's uncertainty-weighted, roster-churn-aware updates and its explicit *variance* are new information, and directly implement the user's own "dynamic Bayesian latent-state ratings" frontier priority.

**Stabilization:** Recursive — usable after about four games once the filter's variance contracts; early-season estimates carry wide, honestly-reported uncertainty.

**Confound / failure test:** Process-variance tuning is fragile and can overfit. **Falsification:** if one-step-ahead forecast error does not beat a simple four-game rolling average, abandon — the exact test in the user's frontier notes.

**Pre-game:** Yes, trailing.

### 7. Finishing-over-Expected on Shot Quality (FoESQ)

**Definition:** The gap between a team's actual points and the points an average team would score given the *quality* of scoring chances it generated, separating chance creation from conversion luck.

**Source and analogy:** Basketball's Quantified Shot Impact (shotmaking = eFG% minus expected shot quality) and soccer's xGOT-minus-xG, both of which isolate *execution/luck* from *chance quality*. The football analogue: build a per-drive "expected points from position/situation" (a chance-quality model) and subtract it from actual points scored.[^15][^16]

**Estimation:** For each drive, compute expected points from the drive's field-position and down-state trajectory (a chance-quality baseline), sum to a team "expected scoring" total; FoESQ = actual points − expected points, opponent-adjusted and trailing. This is conceptually the football version of xPoints-vs-actual overperformance.[^16][^30]

**Predicts:** Regression direction and over/under — a team scoring well above its chance quality is a mean-reversion (under) candidate, mirroring soccer teams whose actual points exceed xPoints.[^30]

**Orthogonality:** EPA rewards realized outcomes; FoESQ deliberately splits the *sustainable* (chance-quality) part from the *luck* part, information EPA blends together.

**Stabilization:** Slow — finishing/conversion luck stabilizes near a full season, like BABIP in baseball, so treat it primarily as a regression flag rather than a strength estimate.[^2][^3]

**Confound / failure test:** If the chance-quality model is just EPA relabeled, FoESQ collapses to noise. **Falsification:** if teams with large positive FoESQ do not underperform their scoring next games, kill it.

**Pre-game:** The trailing version is pre-game; using the current game's own finishing is descriptive-only and must be flagged.

### 8. Football PDO (fPDO)

**Definition:** A luck index summing a team's "finishing rate" and "prevention rate" components that, like hockey PDO, should regress toward a league-fixed constant.

**Source and analogy:** Hockey/soccer PDO, which sums shooting % and save % and regresses toward 1000 because every shot is either scored or saved. The football analogue sums complementary conversion rates (e.g., red-zone TD rate + opponent red-zone TD rate allowed, or points-per-drive scored + points-per-drive-allowed prevention) scaled so the league mean is fixed.[^17]

**Estimation:** Define two complementary rates whose league-wide sum is structurally near-constant; sum and scale. Deviations above the constant flag "lucky" teams due for negative regression.[^17]

**Predicts:** Mean reversion — a pure regression-to-the-mean flag for margin and total, not a strength estimate.

**Orthogonality:** EPA measures ability; fPDO is explicitly designed to isolate the *luck* component EPA cannot separate, making it orthogonal by intent.

**Stabilization:** Slow by design — PDO is a luck index, so its predictive content is precisely that it *has not* stabilized and will revert.[^17]

**Confound / failure test:** The two chosen rates may not actually sum to a constant in football's discrete-scoring regime (weaker mechanical fit than hockey's binary shot outcome). **Falsification:** if high-fPDO teams do not regress more than low-fPDO teams, the constant-sum assumption fails and the metric is void.

**Pre-game:** Yes, trailing.

### 9. Special-Teams & Turnover Hidden Points (HP)

**Definition:** The field-position value, expressed in expected points, created or surrendered by special teams and turnover-return field position, measured against a situation-adjusted league baseline.

**Source and analogy:** *The Hidden Game of Football* and DVOA's "hidden value," which price every yard line in points (own goal line ≈ −2, midfield ≈ +2, opponent goal line ≈ +6) and value punts, kickoffs, returns, and field goals as EP changes. The user holds field position and finishing drives but not this consolidated *hidden-points* ledger across special teams and turnover-return spots.[^19][^18]

**Estimation:** For each punt, kickoff, return, field goal, and turnover, compute the change in EP relative to the situation-adjusted baseline; sum into per-game special-teams and turnover-field-position points, trailing and opponent-adjusted.[^18][^19]

**Predicts:** Margin and spread; hidden points are a documented, often-mispriced margin driver.

**Orthogonality:** Offensive/defensive EPA typically excludes special teams and treats turnover-return field position inconsistently; HP captures a phase largely outside the user's current efficiency stack.

**Stabilization:** Roughly eight to ten games; field-goal and return events are sparse, so shrink kicking components heavily.

**Confound / failure test:** Field-goal luck and blocked-kick variance are high. **Falsification:** if HP adds nothing to a margin model containing offensive and defensive EPA, discard.

**Pre-game:** Yes, trailing.

### 10. Leverage-Weighted Efficiency (LWE)

**Definition:** EPA weighted by the win-probability leverage of each play, so high-stakes snaps count more than garbage-time snaps.

**Source and analogy:** Baseball's Leverage Index and Win Probability Added, which weight events by how much they can swing win probability. The football analogue multiplies each play's EPA by a pre-play leverage weight derived from a win-probability model.

**Estimation:** For each play, compute leverage as the sensitivity of win probability to outcome given the game state; weight EPA by leverage and average, trailing and opponent-adjusted. (The win-probability model uses only pre-play state, so no lookahead within a play.)

**Predicts:** Margin and cover; the hypothesis is that clutch-weighted efficiency predicts close-game outcomes better than flat EPA.

**Orthogonality:** EPA/play weights every snap equally; LWE re-weights by importance, potentially adding information about how teams perform when it matters.

**Stabilization:** Roughly six to eight games, similar to EPA but noisier because high-leverage plays are rarer.

**Confound / failure test:** Clutch performance is notoriously unstable and may be pure noise (the baseball "clutch" literature is skeptical). **Falsification:** if LWE has no year-over-year or within-season persistence beyond flat EPA, it is noise — kill it.

**Pre-game:** Yes, trailing.

### 11. Garbage-Time-Stripped Core Efficiency (GTS)

**Definition:** EPA/success-rate recomputed after removing plays in low-leverage blowout/running-clock states, yielding a cleaner team-ability estimate.

**Source and analogy:** Basketball possession-filtering and the widely used practice of excluding garbage time when building ratings; roughly 16% of points in one tally came in garbage time by one definition, making garbage-time-inclusive averages noisy ability proxies. The user holds EPA but the *filtered* version is a distinct construct; several public models (Gridpex) explicitly leave garbage time out.[^31]

**Estimation:** Define garbage time via win-probability and score-margin/clock thresholds; recompute trailing opponent-adjusted EPA and success rate on the surviving plays only.[^31]

**Predicts:** Margin and total; the cleaned estimate should forecast future scoring better than raw EPA for teams with many blowouts.

**Orthogonality:** It is a de-noised version of EPA, so it is only *partly* orthogonal — but the difference between raw and stripped EPA is itself an informative feature (how much of a team's rating is padding).

**Stabilization:** Roughly five to seven games; stripping plays reduces sample, so slightly slower than raw EPA.

**Confound / failure test:** Threshold-mining risk — the garbage-time definition can be tuned to fit. **Falsification:** if GTS does not beat raw EPA out-of-sample under a *pre-registered* threshold, discard.

**Pre-game:** Yes, trailing.

### 12. DIPS-Style Defense-Independent Rush Value (DIRV)

**Definition:** A rushing-efficiency estimate that strips out the components most controlled by the defense/blocking and luck, isolating the repeatable back/scheme skill — a football FIP.

**Source and analogy:** Baseball's DIPS/FIP, which showed pitchers control strikeouts, walks, and homers but have little control over balls in play (BABIP), so a defense-independent metric predicts future ERA better than ERA itself. The football analogue: decompose rushing into a line-controlled component (already partly captured by line yards, which the user holds) and a back/scheme component, and build the defense-independent residual.[^3]

**Estimation:** Regress rush EPA on opponent front quality, box count/personnel rates, and line-yards; the residual is the defense-independent rush value. Trailing and shrunk.

**Predicts:** Future rushing margin and a regression flag for teams whose rush output is defense/luck-inflated.

**Orthogonality:** Raw rush EPA blends line, back, scheme, and opponent; DIRV isolates the repeatable slice, which should stabilize faster and predict better — the core DIPS insight.[^3]

**Stabilization:** Faster than raw rush EPA precisely because the noisy, defense-controlled variance is removed, analogous to FIP stabilizing faster than ERA.[^3]

**Confound / failure test:** If line-yards already captures the separable signal, DIRV is redundant. **Falsification:** if DIRV does not predict next-game rush EPA better than raw rush EPA, drop it.

**Pre-game:** Yes, trailing.

### 13. Explosive-Play Renewal Rate (EPRR)

**Definition:** The rate and inter-arrival distribution of explosive plays, modeled as a renewal process, rather than the average magnitude of explosiveness (which the user already holds).

**Source and analogy:** Queueing/renewal-process theory — model explosive plays as events in a point process and study the *time (plays) between* events, not their size. This is the renewal-process complement to the survival framing in metric 1.[^6]

**Estimation:** Define explosive plays by an EPA or yardage threshold; compute the inter-arrival distribution (plays between explosives) per unit; expose the hazard/rate and its dispersion, trailing and opponent-adjusted.

**Predicts:** Total and tail scoring; a team that generates explosives at steady short intervals differs from one with rare huge bursts even at equal average explosiveness.

**Orthogonality:** The user's explosiveness metric is a magnitude average; EPRR captures the *frequency/timing* structure, a different moment of the same phenomenon.

**Stabilization:** Roughly 200+ plays because explosive plays are rare events; must be shrunk heavily early season.[^3]

**Confound / failure test:** Threshold choice drives everything and invites mining. **Falsification:** if EPRR adds nothing to a total model containing average explosiveness and pace, discard.

**Pre-game:** Yes, trailing.

### 14. Cross-Book Lead-Lag Dislocation (CBLL)

**Definition:** A measure of which sportsbooks move first and which lag, and the transient dislocations between books, used to detect stale prices and the direction of informed flow.

**Source and analogy:** Finance microstructure lead-lag analysis and the practitioner observation that when sharper books move but recreational books lag (or vice versa), the disagreement reveals where true opinion is forming. Prediction-market order-book work shows sharp money often moves price hours before public books respond.[^20][^21]

**Estimation:** Align timestamped quotes across books; estimate each book's lead-lag relationship to a consensus; flag persistent leaders and quantify transient cross-book spreads as dislocation signals.[^21][^20]

**Predicts:** The **closing consensus line** and stale-price opportunities — again a market-prediction task distinct from game outcome.[^5]

**Orthogonality:** Pure inter-book market dynamics, zero team content, orthogonal to all efficiency metrics.

**Stabilization:** Roughly one season to establish stable leader/laggard structure; FBS-usable only from mid-2020 given odds coverage.

**Confound / failure test:** Timestamp granularity and book-identity fidelity are the binding constraints (the user's audit prerequisite). **Falsification:** if identified "leader" books do not predict laggard moves out-of-sample, the lead-lag structure is spurious.[^5]

**Pre-game:** Yes, intra-week.

### 15. Momentum-Impulse Score Index (MISI)

**Definition:** A physics-style momentum/impulse measure of scoring runs — the accumulated signed scoring "impulse" and its decay — capturing streakiness within a game.

**Source and analogy:** Physics momentum and impulse; a scoring run is an impulse that imparts "momentum" to the score path, with damping. Real-time win-probability "flow" models formalize an analogous idea via a time-evolving dominance process.[^32]

**Estimation:** From the in-game score-margin path, compute run-length-weighted signed scoring impulses and an exponential decay; summarize a team's tendency to produce/absorb runs, trailing across games.

**Predicts:** Primarily a **live/in-game** model input; a trailing cross-game summary can be a weak pre-game feature.

**Orthogonality:** Captures sequencing/streakiness that any mean efficiency metric discards.

**Stabilization:** The trailing summary needs roughly eight to ten games; within-game momentum is famously fragile.

**Confound / failure test:** "Momentum" may be an artifact of underlying strength differences. **Falsification:** if MISI adds nothing after conditioning on strength and score state, it is illusory.

**Pre-game:** **No** — the core metric uses in-game score-path data; only a trailing aggregate is pre-game, and it is weak. Flagged as primarily descriptive/live.

### 16. Zone-Diversity of Personnel Usage (ZDPU)

**Definition:** A diversity index (Shannon or Simpson) over a team's target/carry/snap distribution across skill players, measuring concentration versus balance and thus roster fragility.

**Source and analogy:** Ecology's Simpson/Shannon diversity indices applied to usage distributions, and passing-network transition-entropy work in soccer where higher entropy (less concentration) related to winning. Given FBS's extreme transfer-portal roster churn, concentration/fragility is especially relevant.[^23][^22]

**Estimation:** Compute Shannon $H=-\sum p_i\log p_i$ or Simpson $1-\sum p_i^2$ over each player's share of targets/carries/snaps, trailing. Low diversity = star-dependent (fragile to injury); high diversity = distributed.[^23]

**Predicts:** Margin and injury-robustness; a highly concentrated offense is a larger downside risk if its star is unavailable, and diversity may proxy scheme flexibility.

**Orthogonality:** EPA measures output; ZDPU measures the *distribution* of who produces it — a structural property EPA ignores.

**Stabilization:** Roughly four to six games for usage shares to settle; portal-era early-season usage is unstable.

**Confound / failure test:** Concentration may simply reflect having one elite player (good), not fragility (bad). **Falsification:** if ZDPU has no relationship to performance variance or injury-driven swings, discard.

**Pre-game:** Yes, trailing.

### 17. Field-Position Potential Energy (FPPE)

**Definition:** A state variable encoding the non-linear expected-points value of current field position as "potential energy," aggregated over a team's typical starting-field-position distribution.

**Source and analogy:** Physics potential energy mapped onto the documented curved (non-linear) field-position value function — value rises steeply near both goal lines. The user holds "field position" as a feature but likely as average start yard-line, not as this non-linear EP-weighted potential.[^18]

**Estimation:** Map each starting field position through the curved EP value function; aggregate a team's trailing starting-field-position distribution into an average "potential energy" for offense and the negative it concedes on defense.[^18]

**Predicts:** Total and margin; better field-position potential mechanically raises scoring expectation beyond per-play efficiency.

**Orthogonality:** Captures the *starting-state advantage* (largely special-teams and turnover driven) that per-play EPA conditions away by starting each play from its actual spot.

**Stabilization:** Fast, roughly four to five games, since starting field position is observed every drive.

**Confound / failure test:** Overlaps with Hidden Points (metric 9); build one or the other, not both naively. **Falsification:** if FPPE adds nothing beyond HP and offensive EPA, drop it.

**Pre-game:** Yes, trailing.

### 18. Coach Tendency Regime Stability (CTRS)

**Definition:** A change-point signal flagging when a team's play-calling or tempo tendencies have structurally shifted (new coordinator, QB change), so pre-shift data is downweighted.

**Source and analogy:** Bayesian online change-point detection (BOCPD), which the user's frontier notes already flag as underexplored. The football use is to detect scheme regime breaks that mean-based trailing stats smear over.

**Estimation:** Run change-point detection on trailing play-call/tempo/personnel-rate series; expose "plays since last detected change" and a regime-stability score. Validate detected change points against known coordinator/QB-change dates.

**Predicts:** Margin, especially early-season and post-coaching-change, where the market may lean on stale priors.

**Orthogonality:** EPA/SP+ average across a regime break; CTRS explicitly identifies the break, adding information about *which* history is relevant.

**Stabilization:** Event-driven rather than sample-driven; useful the moment a credible change point is detected.

**Confound / failure test:** False positives from noise. **Falsification:** if detected change points do not correlate with real personnel/coaching events, the detector is fitting noise — the user's own BOCPD acceptance test.

**Pre-game:** Yes, trailing.

### 19. Sharpe-Style Efficiency Ratio (SSER)

**Definition:** A risk-adjusted efficiency ratio, mean EPA divided by EPA volatility, analogous to a Sharpe ratio.

**Source and analogy:** Finance's Sharpe ratio (return per unit risk) and the information ratio $\mu/\sigma$ that appears directly in the game-volatility literature, where a team's spread advantage is calibrated by dividing by score volatility.[^33][^9]

**Estimation:** Compute trailing mean EPA/play and its standard deviation; SSER = mean / std, opponent-adjusted.[^9]

**Predicts:** Margin and cover; a high-mean but high-variance offense is a different bet than a high-mean low-variance one, especially for spread coverage where consistency matters.

**Orthogonality:** Combines first and second moments; distinct from EPA (mean only) and from RSV (variance only), and closest in spirit to the market's own $\mu/\sigma$ calibration.[^9]

**Stabilization:** Roughly six to eight games; the volatility denominator is the slower-stabilizing part.

**Confound / failure test:** Low variance may just reflect weak schedule. **Falsification:** if SSER adds nothing to a model containing mean EPA and RSV separately, it is redundant.

**Pre-game:** Yes, trailing.

### 20. Hysteresis / Mean-Reversion Half-Life (HMRL)

**Definition:** The estimated half-life at which a team's performance reverts toward its own baseline after an over- or under-performance, plus a hysteresis term for path-dependence.

**Source and analogy:** Physics hysteresis and finance mean-reversion (Ornstein-Uhlenbeck) dynamics; the same mean-reverting process used in Kalman team-strength models governs how fast form decays. The half-life is a per-team parameter of that reversion.[^13]

**Estimation:** Fit an AR(1)/OU process to a team's trailing efficiency series; the persistence coefficient $\rho$ yields the reversion half-life; add a hysteresis feature for whether reversion speed differs after wins vs. losses.[^13]

**Predicts:** Regression flags for margin and spread — how quickly to expect a hot/cold team to normalize.

**Orthogonality:** SP+ applies a single global regression assumption to all teams; HMRL estimates *team-specific* reversion speed, which is new information.

**Stabilization:** Roughly one season per team; reversion parameters need many observations.

**Confound / failure test:** Team-specific $\rho$ may be indistinguishable from a global constant. **Falsification:** if per-team half-lives do not out-predict a single league-wide regression constant, use the constant and drop HMRL.

**Pre-game:** Yes, trailing.

### 21. Park-Factor Venue Adjustment (PFVA)

**Definition:** A venue-specific scoring residual, the persistent over/under-scoring of a stadium after controlling for the quality of teams that play there.

**Source and analogy:** Baseball park factors — Coors Field inflates offense independent of the teams. The football analogue estimates each venue's residual effect on total points and margin after removing team strength, using altitude, dome/roof, and observed venue history.[^2]

**Estimation:** Regress game totals/margins on both teams' strength and a venue random effect; the venue effect is the park factor. Blend altitude and roof indicators as priors for sparse-history venues.

**Predicts:** Total and home-field edge; a robust venue residual is a clean, low-cost total adjustment.

**Orthogonality:** SP+/FPI fold home advantage into a generic constant; PFVA isolates *venue-specific* residuals SP+ does not resolve.

**Stabilization:** Slow — multi-season, because each venue hosts limited games per year; requires pooling and strong priors.

**Confound / failure test:** Venue effects confound with the home team's persistent quality. **Falsification:** if venue random effects shrink to zero once team strength is included, there is no park factor.

**Pre-game:** Yes, known before kickoff.

### 22. Phase-Transition Blowout Threshold (PTBT)

**Definition:** A non-linear score-margin threshold beyond which game dynamics (pace, aggressiveness, scoring rate) shift regime, treated as a phase transition.

**Source and analogy:** Physics phase transitions and hysteresis — beyond a critical margin, teams change behavior abruptly (leaders drain clock, trailers gamble), a discontinuity in the scoring "phase." Win-probability flow models capture the analogous state dependence.[^32]

**Estimation:** Estimate, from in-game data, the margin/time thresholds at which per-possession scoring rate and tempo shift regime; summarize each team's trailing threshold sensitivity.

**Predicts:** A **live/in-game** total and pace input; only a trailing summary is weakly pre-game.

**Orthogonality:** Captures a non-linear game-state dynamic entirely absent from linear efficiency metrics.

**Stabilization:** Roughly one season for the trailing summary; the threshold itself is game-state-specific.

**Confound / failure test:** The "transition" may be a smooth function misread as a break. **Falsification:** if a smooth model fits the pace/scoring-vs-margin relationship as well as a threshold model, there is no phase transition.

**Pre-game:** **No** — inherently in-game; flagged as descriptive/live, with only a weak trailing pre-game proxy.

## The three to build first

The first three are chosen for the best combination of orthogonality to the existing stack, fast stabilization, low build cost from existing columns, and — critically — the honest separation between game-prediction and market-prediction tasks.

**1. Drive-Survival Hazard Curve (DSHC).** It is fully pre-game, stabilizes fast (drives are frequent, ~40-60 to signal), is built entirely from play-by-play the user already has, and has a published NFL precedent to borrow implementation details from. Most importantly it captures field-position *geometry* of scoring and stalling that EPA/play structurally averages away, so it is genuinely additive to the totals and margin models. It also plugs directly into the user's own priority experiment on garbage-time-adjusted possession/drive simulation and survival/competing-risk drive models, so it advances an already-planned line of work rather than opening a new one.[^6]

**2. Kalman Latent-Strength Innovation (KLSI).** It implements the user's top-ranked frontier experiment (dynamic Bayesian latent-state ratings) and delivers something SP+ and FPI cannot: a *self-quantified uncertainty* on each team's strength plus an *innovation* term that flags mispriced regime shifts. It stabilizes recursively (usable by about week four), has a clean falsification test (beat a four-game rolling average on one-step-ahead error), and its posterior variance is exactly the input a distributional totals model (NGBoost/GAMLSS) needs to widen intervals for uncertain teams.[^14][^13]

**3. Market Microstructure Order-Flow Index (MOFI).** This is the highest-orthogonality candidate — it contains zero team-efficiency content and therefore cannot be a re-expression of EPA/SP+. It targets the closing line and CLV, which is the correct, honest target for a market-structure signal and which the user's frontier notes already prioritize (multi-book quote-fusion/lead-lag). Its build cost is low once the mandatory line-field audit — already the user's number-one experiment — confirms timestamp and book-identity fidelity. The audit is a hard prerequisite: without trustworthy opener/close timestamps, MOFI (and its cousin CBLL) cannot be built, which is why the audit should precede both.[^8][^5]

A closing caution ties the whole catalog together: build the pre-game/market divide into validation from day one. DSHC and KLSI are game-prediction features and should be judged on margin/total error and, ultimately, cover and CLV; MOFI, CBLL, and the other market-structure metrics predict the *closing line* and must be judged on that task separately, because a signal that reliably beats the open to the close can still have no edge on the actual game outcome.[^5]

---

## References

1. [What Is EPA in College Football? Expected Points Added ...](https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-iv.html) - EPA (expected points added) is the change in expected points across a single play. How it is calcula...

2. [A Guide to Statistical Stabilization and Regression](https://birdlandmetrics.com/articles/stabilization-regression) - How to separate signal from noise when evaluating baseball performance, using FanGraphs regression m...

3. [Advanced stats for bettors - BetLets](https://betlets.com/advanced-stats) - Per-possession efficiency, expected goals, expected points added, true shooting, wRC+, WAR, Corsi - ...

4. [EPA in Football Explained: The Metric That Redefined the NFL](https://pickviz.com/epa-in-football-explained-the-metric-that-redefined-the-nfl/) - Expected Points Added (EPA) is the gold standard for football analytics. Here is the math behind EPA...

5. [Inside the Market Microstructure of a Sports Bet - Artha](https://norafi.ai/artha/guides/inside-the-market-microstructure-of-a-sports-bet-the-stadium-as-an-exchange) - Most bettors imagine a sportsbook as an opponent, an oddsmaker studying game film and quietly hoping...

6. [A Hierarchical Bayesian Drive-Survival Model of the NFL](http://danielweitzenfeld.github.io/passtheroc/posts/bayes-nfl.html) - Two posts ago, I implemented a Hierarchical Bayesian model of the Premier League. The model, introdu...

7. [Survival analysis in the presence of competing risks - PMC - NIH](https://pmc.ncbi.nlm.nih.gov/articles/PMC5326634/) - Survival analysis in the presence of competing risks imposes additional challenges for clinical inve...

8. [Sharp Money vs Public Money: What Betting Line Movement Data Reveals](https://dev.to/edgelab/sharp-money-vs-public-money-what-betting-line-movement-data-reveals-4c4n) - The opening kickoff of Super Bowl LVII was still three weeks away when sharp bettors began their...

9. [The Implied Volatility of a Sports Game](https://citeseerx.ist.psu.edu/document?repid=rep1&type=pdf&doi=62db46ab57d96d115bc8e63b1b60d64b3f41aaf2)

10. [Articles Stern | PDF | Volatility (Finance) | Normal Distribution - Scribd](https://www.scribd.com/document/868873124/Articles-Stern) - This paper presents a method for calculating the implied volatility of sports game outcomes using a ...

11. [Chapter 11: Chapter 11: Play Calling Analytics | NFL Analytics ...](https://nflanalytic.com/tutorials/chapter-11) - NFL play calling analytics and game theory. Understand optimal decision-making for predicting play c...

12. [Football prediction confidence: entropy, margin and stability](https://www.foresportia.com/en/blog/technical-note-3-entropy-confidence-football-predictions.html) - How Foresportia moves from raw football probabilities to Stable, Correct and Risk confidence signals...

13. [Tracking Football Team Strengths with a Bayesian Kalman ...](https://seanelvidge.com/articles/2025/Football_team_rankings/) - How a Bayesian extended Kalman filter estimates English football team strengths, uncertainty and mat...

14. [[PDF] A State-Space Model for National Football League Scores](https://www.glicko.net/research/nfl.pdf)

15. [An introduction to shot quality and the 'expected' results](https://www.nytimes.com/athletic/2351786/2021/01/29/nba-introduction-to-shot-quality-and-expected-results-seth-partnow/) - What is a good shot? It's a surprisingly complicated question, dependent on any number of factors: •...

16. [The Athletic’s football analytics glossary: explaining xG, PPDA, field](https://www.nytimes.com/athletic/2730755/2021/07/28/the-athletics-football-analytics-glossary-explaining-xg-ppda-field-tilt-and-how-to-use-them/) - Our analytics experts explain the terms they use in their data pieces, giving examples of what they ...

17. [PDO (Shooting % + Save %) Luck Index Calculator](https://metricgate.com/docs/pdo-shooting-save-percentage-sum/) - Compute PDO as shooting % plus save % (x1000). PDO regresses toward 1000, so values above 1000 flag ...

18. [What is DVOA? Football Stat Explainer](https://ftnfantasy.com/nfl/dvoa-explainer) - An explanation of FTN's DVOA, DYAR, and other advanced NFL stats widely used by NFL teams, commentat...

19. [Special Teams Analytics, Explained](https://nflanalytic.com/explainer-special-teams.html) - Why field position is "worth points": because the expected-points model assigns value to every yard ...

20. [For Sports Desks: Market Microstructure Models · Resolved ...](https://blog.resolvedmarkets.com/projects/resolvedmarkets/output/resolvedmarkets-for-sports-analysts-market-microstructure-models/) - Backtest Polymarket strategies with Market Microstructure Models data — Market Microstructure Models...

21. [Beating the Closing Line at Sharp Books - The Sharp Plays®](https://thesharpplays.com/beating-the-closing-line-at-sharp-books/) - What Actually Works — and What Doesn’t One of the most misunderstood concepts in sports betting is t...

22. [Putting sports stats to the test: Unpredictable play helps ...](https://phys.org/news/2026-02-sports-stats-unpredictable-play-winner.html) - Unpredictable play helps pick a winner in football. Football ... metric called Spatial Event Distrib...

23. [mathematics](https://pdfs.semanticscholar.org/18aa/7ac4ea0518a29926f2a26df529eb3578a998.pdf)

24. [fbs-totals-frontier-models.md](fbs-totals-frontier-models.md)

25. [FBS College Football Pregame Totals Betting System  Research Report.md](FBS College Football Pregame Totals Betting System  Research Report.md)

26. [Chapter 13: Pace and Play Calling | NFL Analytics | DataField.Dev](https://datafield.dev/nfl-football-analytics/part-03/chapter-13/) - Understanding tempo, play selection, and situational decision-making

27. [Estimating team strength in the NFL](https://glicko.net/research/nfl-chapter.pdf)

28. [Dynamic Rating of Sports Teams](https://academic.oup.com/jrsssd/article-abstract/49/2/261/7123397?redirectedFrom=fulltext) - Summary. We consider the problem of dynamically rating sports teams on the basis of categorical outc...

29. [[PDF] Keep Kalman Filter on - UCLA Mathematics](https://www.math.ucla.edu/~bertozzi/WORKFORCE/REU%202013/Sports%20Rankings%20Group/Final_Report.pdf)

30. [Expected Points (xP): From xG to Points Per Match](https://kiqiq.com/es/blog/expected-points-football-explained) - Expected Points (xP) translates per-shot xG into a probabilistic points-per-match figure: how many p...

31. [How the Gridpex Model Works — Methodology](https://gridpex.com/methodology) - College football analytics — drive efficiency, play-calling tendencies, playoff odds and recruiting ...

32. [Real-time Win Probability and Latent Player Ability via STATS X in ...](https://arxiv.org/html/2602.19513v1)

33. [Team EPA per Play 2026 — Offense and Defense | Muffed](https://muffed.ai/stats/team-epa) - 2026 team expected points added per play, offense and defense, all 32 NFL teams. The single best one...

