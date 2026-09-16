# FBS Totals Research: Joint Spread-Total Modeling

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

Research joint modeling of FBS spread, total, team scores, game script, and related markets.

Analyze expected margin, total, home and away scores, moneyline, team totals, possessions, covariance, favorite strength, blowout behavior, garbage time, and overtime.

Explore bivariate Poisson, multivariate negative binomial, shared latent factors, copulas, hierarchical score models, seemingly unrelated regression, multi-output Gaussian processes, Bayesian joint models, multi-task boosting and neural models, possession simulations, conditional score distributions, and market-implied joint distributions.

Examine dependence created by pace, turnovers, field position, trailing-team aggression, favorite clock-killing, weather, and overtime.

Compare:

1. Direct total model.
2. Separate independent team-score models.
3. Joint team-score model.
4. Total model conditioned on spread.
5. Market-implied joint distribution.
6. Structural possession simulation.
7. Joint market-model ensemble.

Evaluate total and team-score error, distribution calibration, CRPS, push probability, tail behavior, directional CLV, and executable returns. Determine whether margin modeling contributes incremental totals information or adds avoidable complexity.
