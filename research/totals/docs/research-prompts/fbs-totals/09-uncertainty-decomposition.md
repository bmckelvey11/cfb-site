# FBS Totals Research: Uncertainty Decomposition

## Shared research instructions

Research mode: exhaustive deep research with inline citations.

You are advising a solo developer building an FBS pregame full-game totals betting system with Python, DuckDB, CFBD data from 2012–2025, and free or affordable supplemental data.

- No word limit. Prefer depth, evidence quality, methodological detail, and implementation value.
- Cite every empirical and numeric claim immediately beside the claim.
- Prefer papers, official documentation, verified datasets, and reproducible backtests.
- Label undocumented industry, blog, podcast, and forum claims `[anecdotal]`.
- Label uncertain, extrapolated, weakly supported, or conflicting claims `[uncertain]`.
- Separate direct FBS totals evidence from NFL, other sports, and mechanism-only evidence.
- Never fabricate papers, data coverage, results, ROI, CLV, win rates, or effect sizes.
- For negative literature searches, write: `No published FBS totals application found in searched sources.` Never claim universal absence.
- For every backtest, report seasons, sample size, odds source, line timing, vig treatment, validation method, wager count, and uncertainty when available.
- Distinguish prediction accuracy, probability calibration, CLV, and realized profit.
- Enforce strict historical as-of availability and realistic wager execution.
- State research cutoff date, databases searched, representative queries, and access limitations.
- End with implementation-ready experiments, chronological validation, falsification criteria, and ranked recommendations.

## Research assignment

Determine whether separating game randomness from model uncertainty improves FBS total wagering.

Distinguish aleatoric uncertainty, epistemic uncertainty, distribution shift, data-quality uncertainty, lineup/weather uncertainty, market-price uncertainty, and model disagreement.

Research heteroskedastic regression, GAMLSS, NGBoost, distributional forests, quantile models, Bayesian hierarchical models, BART, Gaussian processes, deep ensembles, Bayesian neural approximations, bootstrap ensembles, conformal prediction, out-of-distribution detection, and structural-simulation variance decomposition.

Test whether uncertainty forecasts predict absolute error, calibration failure, negative CLV, unstable edges, early-season failures, roster-change failures, or cross-book disagreement.

Hold predicted mean fixed where possible and compare fixed point-edge thresholds, standardized edges, over/under probabilities, lower-confidence-bound EV, epistemic abstention, and market-model disagreement conditioned on uncertainty.

Require out-of-sample calibration of uncertainty itself. Check whether confidence only tracks total range, missingness, or model complexity. Identify simplest method retaining any benefit.
