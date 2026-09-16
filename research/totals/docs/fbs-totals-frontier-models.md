# FBS Totals Betting System: Exhaustive Model Landscape and Frontier Methods

Research cutoff: September 8, 2026. This report extends the prior FBS totals research report, with expanded emphasis on Section 3 (established and underexplored models).

## 1. Feature ideas with evidence (condensed update)

No direct FBS totals evidence found for any individual tempo, efficiency, or matchup feature in isolation; all remain "mechanism-only" or "raw-score" evidence. The 2023 NCAA clock-rule change reduced plays per game by roughly 7.8% and game length by about 1.4% in early post-implementation analysis. Wind-threshold total-scoring claims from industry sources remain anecdotal. Returning production and recruiting-talent measures are raw team-strength proxies likely to substantially proxy market-embedded team-strength perception.

| Feature group | Scoring mechanism | FBS totals evidence | Incremental-to-market evidence | Historical as-of availability | Leakage risk | Cost | Priority |
|---|---|---|---|---|---|---|---|
| Tempo/possessions | More snaps -> more scoring chances | No direct FBS totals evidence found | Untested | Yes, if strictly trailing | Low-medium | Medium | High |
| Efficiency (EPA/success rate) | Point-value estimate per play | No direct FBS totals evidence found | Untested | Yes | Medium | Medium-high | High |
| Weather (wind/temp) | Passing/kicking disruption | No direct FBS totals evidence found; anecdotal thresholds | Untested | Only via paid forecast archive | High | Medium | Medium |
| Returning production/recruiting | Preseason roster-quality proxy | No direct FBS totals evidence found | Likely proxies market | Yes, preseason | Medium | Low | Medium |
| Market total/spread/price | Consensus forecast | Adjacent CFB team-totals bias evidence | Baseline by definition | Depends on field audit | High if close leaks | Low | Critical |

## 2. Market structure in FBS totals (condensed update)

Arscott (2023, Journal of Sports Economics) shows CFB team-totals lines are biased due to censoring at zero points, with a reported exploitable pattern exceeding a 55% win rate net of typical transaction costs -- profitable-after-vig evidence, but specifically for team totals, not confirmed for the combined game total. Paul and Weinbach's earlier CFB/arena-football totals work finds the over is systematically overpriced due to bettor scoring preference. NFL transfer-hypothesis evidence is mixed: Shank (2018) finds significant NFL totals inefficiency including extreme-total bias, while a separate NFL preseason totals study (1996-2019) finds a null result (efficient market, ~50.8% under-cover rate). These conflicting NFL results argue against assuming any universal totals bias transfers cleanly to FBS.

| Claim | Evidence | Seasons/sample | Line timing | Vig handled | Out of sample | Execution limits | Verdict |
|---|---|---|---|---|---|---|---|
| CFB team-totals censoring bias | Peer-reviewed | Not reported (secondary: ~20yrs to 2022/23) | Not reported | Addressed qualitatively | Yes | Not reported | Credible but scope-limited |
| CFB over systematically overpriced | Peer-reviewed (secondary) | Not reported | Not reported | Not reported | Not reported | Not reported | Directionally suggestive only |
| NFL extreme-total bias, over-momentum | Peer-reviewed | NFL through ~2018 | Not reported | Reported significant | Yes | Not reported | Transfer hypothesis, unconfirmed for CFB |
| NFL preseason totals efficient (null) | Peer-reviewed | NFL 1996-2019 | Not reported | Addressed (50.8%) | Yes | Not reported | Important null/conflicting finding |
| Wind >13-15mph favors under (CFB) | Industry blog | Unclear N, "since 2005" | Unclear | Not disclosed | Not disclosed | Not disclosed | Anecdotal; unverified |

## 3. Established and underexplored models

Evidence-level framework: (1) mechanism, (2) raw-score forecasting, (3) totals probability, (4) incremental-beyond-market, (5) CLV, (6) profitable-after-vig. Nearly every model family below has zero direct FBS totals evidence at levels 4-6.

### 3.1 Required baselines
Every model must be compared against: raw market total, calibrated market-only regression, regularized linear scoring model, simple opponent-adjusted rating model, simple residual model, and (for probability methods) market-implied probability baseline. All comparisons must share identical game universe, timestamps, line source, and chronological test window.

### 3.2 Established model families summary
OLS/ridge/lasso, logistic/ordinal, GAMs, hierarchical/Bayesian partial pooling, dynamic/state-space ratings, random forests, gradient boosting (XGBoost/LightGBM/CatBoost), quantile regression/forests, Poisson/negative-binomial/bivariate models, possession/drive/Monte Carlo simulation, and market-residual/market-as-prior ensembles all have no direct FBS totals evidence found. Poisson/bivariate score models have soccer-analogue adjacent evidence but weaker mechanical fit for football's discrete chunk-scoring. Market-residual ensembles are the priority candidate given direct linkage to Arscott's documented CFB team-totals bias.

### 3.3 Underexplored probabilistic models

**GAMLSS / distributional boosting (NGBoost)**: Underexplored. No published FBS totals application found (searched: "GAMLSS sports prediction application," "NGBoost sports betting total," cutoff Sept 8 2026). Closest adjacent: MLB Statcast swinging-strike BART modeling; sprint kayak/canoe BART time-correction. Mathematically suited to jointly estimating conditional mean+variance+skew of the total, useful for distinguishing games with same edge but different uncertainty. Prototype: fit NGBoost/GAMLSS on market-residual target, compare CRPS vs. linear baseline. Falsification: if predicted variance uncorrelated with squared residuals out-of-sample, abandon.

**BART / heteroskedastic BART**: Underexplored. Adjacent evidence: MLB pitch-quality BART; kayak/canoe race-time BART correction. Native Bayesian posterior uncertainty. Prototype: BART vs. linear baseline, compare interval coverage. Falsification: coverage indistinguishable from Normal-approx baseline.

**Copula / flexible joint-score models**: Underexplored for FBS; directly studied in soccer (bivariate copula goal models, PARX-Copula, CMP-copula HMM for momentum). Football's discrete chunk-scoring is a weaker mechanical fit than soccer's single-goal counting. Prototype: independent marginals + copula fit vs. independent-sum baseline. Falsification: copula dependence parameter statistically indistinguishable from zero.

**Normalizing flows / MDN**: Speculative. No FBS or clear sports analogue found. Sample-size mismatch (flows typically need more data than ~800-900 games/season) and discrete-score handling issues.

**Deep ensembles / Bayesian NN**: Poor fit. Sample-size mismatch for base neural net itself makes uncertainty-quantification wrapper premature.

### 3.4 Underexplored temporal and latent-state models

**Dynamic Bayesian latent-team models**: Underexplored. Kalman-filter-style weekly updating of offense/defense/pace states, handling roster churn as state innovations rather than rolling-window tuning. Prototype: local-level Kalman filter on one efficiency metric vs. 4-game rolling average, compare one-step-ahead forecast error.

**HMM/regime-switching**: Underexplored for FBS; adjacent soccer within-match momentum HMM using CMP-copula marginals. Prototype: 2-state HMM vs. known coaching/QB-change dates.

**Change-point models (BOCPD)**: Underexplored. No FBS application found. Same validation logic as HMM: check if detected change points correlate with real personnel/coaching events.

**Sequence models (RNN/transformer)**: Poor fit to speculative given ~12-15 games/team/season; soccer T-GNN work uses much more granular event-stream data, a weak structural analogue.

### 3.5 Underexplored event-process and structural models

**Marked point processes (Hawkes)**: Underexplored, with important self-excitation caveat -- football's discrete alternating-possession structure differs fundamentally from continuous-time settings where Hawkes excels; sign/magnitude of self-excitation should be treated as empirical, not assumed positive. Falsification: excitation parameter statistically indistinguishable from zero vs. plain renewal/Poisson process.

**Survival/competing-risk drive models**: Underexplored. Models drive terminal outcome (TD/FG/turnover/punt) as competing risks. Falsification: simulated total mean not better than direct-regression baseline.

**Semi-Markov possession models**: Underexplored, highest engineering cost in report; most mechanistically faithful representation of possession dynamics.

### 3.6 Underexplored relational and representation models

**Matrix factorization**: Underexplored. Latent stylistic offense/defense factors beyond scalar rating. Falsification: rank>1 factorization doesn't beat rank-1 (=scalar rating) on held-out prediction.

**Graph neural networks (temporal)**: Underexplored for pregame FBS; adjacent soccer player-interaction GNN and T-GNN work (different granularity). Requires strictly temporal-causal graph construction (no future-game edges influencing past embeddings). Falsification: no gain over simple SRS-style rating in sparse/early-season prediction.

**Multi-task learning**: Underexplored. Tests regularization-via-shared-tasks vs. negative transfer. Falsification: total-task accuracy not improved vs. single-task model.

**Player/coach embeddings**: Underexplored to poor fit -- severe cold-start for players given FBS roster turnover and no comprehensive historical depth-chart archive; coach-only embeddings more feasible.

### 3.7 Underexplored tabular and automated models

**TabPFN**: Underexplored. Nature paper reports strong performance on datasets up to 10,000 samples/500 features; TabPFN-2.5 claims scalability to 50,000 samples matching/beating tuned XGBoost. Independent evaluation notes real limitations at high-dimensional/large-scale tasks. CPU-only inference limited to a few thousand samples without GPU/hosted inference. Structurally well-matched to FBS's small-medium data regime, but in-context/transductive design creates a new leakage-risk category: must verify only chronologically-prior games are ever passed as context at each decision point. Falsification: accuracy statistically indistinguishable from XGBoost.

**Symbolic regression/genetic programming**: Underexplored. Tests whether possessions x efficiency-style formulas can be automatically rediscovered. Acceptance criterion should be stability across chronological folds, not single-fold fit.

### 3.8 Distribution-shift and robust-learning models

Underexplored across the family (DRO, IRM, Group DRO, meta-learning, conformal under shift). Most tractable entry point: simple era-segmented/weighted training around the 2023 clock-rule break and transfer-portal-era roster churn, plus conformal prediction for interval calibration (with honestly weak formal guarantees under unknown-magnitude shift).

### 3.9 Market as noisy sensor

Underexplored; data prerequisite (timestamped multi-book quotes) only confirmed available from mid-2020 forward via The Odds API. Industry commentary on sharp-vs-public line movement is anecdotal, undocumented. Critical distinction: predicting the closing total is a fundamentally different task from predicting the final game outcome -- a good closing-line predictor could have zero edge on the actual game.

### 3.10 Selective prediction and betting decisions

Meta-labeling, conformal risk control, and price-aware EV rules are underexplored for FBS but low-cost and directly relevant. Meta-labeling operationalizes "when to trust the forecast" via a secondary classifier. Reinforcement learning/contextual bandits remain a weak fit given ~800 one-shot annual decisions and no reliable counterfactual feedback loop.

### Frontier model summary table

| Model | FBS totals use found? | Priority |
|---|---|---|
| GAMLSS/NGBoost | No | Priority experiment |
| BART/heteroskedastic BART | No | Secondary candidate |
| Copula joint-score models | No | Secondary candidate |
| Normalizing flows/MDN | No | Weak fit |
| Deep ensembles/Bayesian NN | No | Poor fit |
| Dynamic Bayesian latent-state ratings | No | Priority experiment |
| HMM/regime-switching | No | Conditional candidate |
| Change-point (BOCPD) | No | Conditional candidate |
| Sequence models (RNN/transformer) | No | Weak fit |
| Marked point processes (Hawkes) | No | Conditional candidate |
| Survival/competing-risk drive models | No | Secondary candidate |
| Semi-Markov possession models | No | Conditional candidate |
| Matrix factorization | No | Secondary candidate |
| Graph neural networks | No | Secondary candidate |
| Multi-task learning | No | Conditional candidate |
| Player/coach embeddings | No | Weak fit (player), Conditional (coach) |
| TabPFN | No | Priority experiment |
| Symbolic regression | No | Secondary candidate |
| Distribution-shift-robust methods | No | Priority experiment (simple version) |
| Market-as-sensor (Kalman/VAR across books) | No | Conditional candidate |
| Meta-labeling/selective prediction | No | Priority experiment |
| RL/contextual bandits for staking | No | Not recommended |

## 4. Validation and leakage (reinforced)

All prior leakage categories apply. Frontier-specific additions: graph/embedding models require strictly temporal-causal graph construction; TabPFN's in-context design requires a dedicated unit test verifying no future game ever enters the context set; distributional models' calibration checks must be performed only on genuinely held-out folds. Nested chronological design (expanding/rolling train window, inner validation, frozen outer test season, weekly retraining, untouched final holdout) applies without exception. A research registry logging every attempted model/feature/threshold combination is recommended.

## 5. Free or cheap data beyond CFBD

Unchanged from prior report: CFBD (core), The Odds API (multi-book historical odds, NCAAF from mid-2020 only), Visual Crossing (observed weather free tier; historical-forecast paid tier ~$165/mo), Meteostat (free observed weather), ESPN returning production (preseason snapshot), recruiting ratings, transfer portal trackers (short history, inconsistent). No FBS historical injury/depth-chart archive identified; prospective collection required going forward. CFBD's own line-field metadata (sportsbook identity, opener/close designation, timestamp granularity) remains unverified at the field level and must be audited first.

## 6. Ranked experiments

| Rank | Experiment | Type | Hypothesis | Data burden | Evidence |
|---|---|---|---|---|---|
| 1 | CFBD line-field audit | Established (diagnostic) | Stored fields reliably represent claimed sportsbook/timing | Low | Foundational, self-verifying |
| 2 | Market-only calibration regression | Established | Market shows stable calibration bias in some subgroup | Low | Adjacent CFB team-totals bias |
| 3 | Market-plus-ML residual hybrid | Established | Engineered features add residual signal beyond market | Medium | No direct evidence found |
| 4 | Garbage-time-adjusted possession/drive simulation | Structural | Explicit possession mechanics beat aggregate regression | High | Mechanism-only |
| 5 | GAMLSS/NGBoost distributional model | Frontier | Conditional variance/skew improves calibration/filtering | Medium | No direct evidence found |
| 6 | Dynamic Bayesian latent-state ratings | Frontier | Kalman updating handles roster churn better than rolling windows | Medium | No direct evidence found |
| 7 | Meta-labeling/selective prediction | Frontier | Secondary "trust model" beats fixed edge threshold | Low-medium | No direct evidence found |
| 8 | TabPFN walk-forward prototype | Frontier | Foundation-model learner matches/beats boosting on small data | Low-medium | No direct evidence found |
| 9 | Multi-book quote-fusion/lead-lag (2020+) | Frontier | Cross-book dynamics predict closing direction/stale prices | Medium-high | Anecdotal only |
| 10 | Opener-vs-later-market timing comparison | Established (execution) | Later entry produces different realized CLV/ROI than opener | Medium | No direct evidence; general CLV heuristic (anecdotal) |

### Immediate roadmap (top 5)
1. CFBD line-field audit -- pass criterion: discrepancy rate below predeclared threshold vs. Odds API 2020+ overlap.
2. Market-only calibration regression -- pass criterion: stable non-zero bias across >=2 independent chronological folds.
3. Market-plus-ML residual hybrid -- pass criterion: residual RMSE improvement holds across >=2 outer seasons plus positive average CLV.
4. Meta-labeling/selective prediction layer -- pass criterion: ROI improvement vs. fixed threshold, stable across seasons.
5. GAMLSS/NGBoost distributional model -- pass criterion: meaningful CRPS improvement plus correct interval coverage.

### First experiment to run: CFBD line-field audit
Every downstream experiment depends on trusting stored opener/close fields. Uses only existing data plus a cross-check against The Odds API's 2020+ timestamped history. If fields prove unreliable, the result still redirects effort productively (restrict usable seasons/fields) rather than wasting months on an untrustworthy foundation. Deliverable: a DuckDB audit report quantifying discrepancy rate, missingness, and staleness, with an explicit go/no-go decision, with the acceptance threshold written down before running the comparison.

## Frontier research shortlist (full prototypes)

**1. GAMLSS/NGBoost distributional regression**: Model residual y = T_final - T_market as Normal(mu(x), sigma(x)^2) with both parameters as additive functions of features, trained via NGBoost's natural-gradient boosting or R gamlss via rpy2. Packages: ngboost, scikit-learn, duckdb. Train on proper scoring rule (NLL/CRPS). Calibrate via PIT/reliability diagrams on held-out folds. Ablate against constant-variance linear baseline. Fail if CRPS/coverage not meaningfully better.

**2. TabPFN walk-forward prototype**: In-context transformer-based predictor; "training set" = chronologically-prior games only, rebuilt fresh at each weekly decision point. Packages: tabpfn, pandas, duckdb. Must include a unit test verifying no future game appears in context. Calibrate via post-hoc isotonic recalibration. Ablate against XGBoost and linear baseline. Fail if accuracy indistinguishable from XGBoost.

**3. Meta-labeling/selective prediction layer**: Secondary binary classifier g(z) trained on primary model's historical edge/confidence features to predict whether a bet would be profitable; only bets above threshold are placed. Packages: scikit-learn or lightgbm. Train with profit-weighted loss. Nested walk-forward (meta-model trained only on strictly prior primary-model outputs). Fail if realized ROI not improved vs. fixed point-edge threshold.

## Search audit
Search tool: general web search aggregator. Cutoff: September 8, 2026. Every frontier family (GAMLSS, BART, copulas, normalizing flows, dynamic latent-state, HMM, change-point, Hawkes processes, matrix factorization, graph neural networks, multi-task learning, TabPFN) produced "no published FBS totals application found in searched sources" -- reported as a search outcome, not proof of universal absence.

## Key references
- Arscott, R. "Market Efficiency and Censoring Bias in College Football Totals Betting." Journal of Sports Economics. https://journals.sagepub.com/doi/10.1177/15270025221148991
- Paul, R.J. & Weinbach, A.P. "Bettor preferences and market efficiency in football totals." https://ideas.repec.org/a/spr/jecfin/v29y2005i3p409-415.html
- Shank, C.A. "Is the NFL Betting Market Still Inefficient?" https://ideas.repec.org/a/spr/jecfin/v42y2018i4d10.1007_s12197-018-9431-4.html
- AABRI. "Market efficiency in the NFL preseason totals betting market." https://www.aabri.com/manuscripts/203263.pdf
- Hollmann, N. et al. "Accurate predictions on small data with a tabular foundation model." Nature. https://www.nature.com/articles/s41586-024-08328-6
- PriorLabs. "TabPFN-2.5 Model Report." https://priorlabs.ai/technical-reports/tabpfn-2-5-model-report
- PyMC Labs. "Modeling Swinging Strikes with Bayesian Additive Regression Trees." https://www.pymc-labs.com/blog-posts/bayesian-additive-regression-tree-swinging-strikes
- Otting, M. et al. "A copula-based multivariate hidden Markov model." https://link.springer.com/article/10.1007/s10182-021-00395-8
- Richards, K.A. et al. "Score test for marks in Hawkes processes." https://link.springer.com/article/10.1007/s41060-024-00644-4
- The Odds API. Historical odds documentation. https://the-odds-api.com/historical-odds-data/
- NCAA.com. 2023 college football rule changes. https://www.ncaa.com/news/football/article/2023-08-25/
