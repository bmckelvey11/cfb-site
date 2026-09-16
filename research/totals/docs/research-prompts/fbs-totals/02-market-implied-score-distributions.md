# FBS Totals Research: Market-Implied Score Distributions

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

Research how to recover market-implied FBS score and total distributions instead of treating sportsbook total as one point forecast.

Use main totals, alternate-total ladders, team totals, spreads, alternate spreads, moneylines, prices, and cross-book quotes.

Cover:

- De-vigging and alternative assumptions about sportsbook margin allocation.
- Monotonicity, coherence, and no-arbitrage constraints.
- Interpolation between quoted lines and tail extrapolation.
- Whole-number pushes and football scoring lattice.
- Overtime and score dependence.
- Recovering conditional mean, variance, skew, tail mass, and home-away covariance.
- Maximum-entropy, isotonic, spline, parametric, mixture, copula, discrete, and nonparametric constructions.
- Mapping spread and total markets into team-score distributions.
- Cross-book aggregation and weighting books by calibration or price-discovery leadership.

Investigate whether model-versus-market distribution disagreement contains more useful information than disagreement between point estimates.

Compare:

1. Market total as deterministic mean.
2. Normal distribution with fixed or rolling variance.
3. Empirically calibrated market distribution.
4. Distribution recovered from alternate prices.
5. Football-specific discrete distribution.
6. Joint team-score distribution.
7. Market-model blended distribution.

Evaluate log loss, Brier score, CRPS, calibration, PIT diagnostics, prediction-interval coverage, push calibration, tail calibration, directional CLV, and executable return.

Identify exact historical quote data required, affordable sources, minimum viable prototype, and cheapest test capable of rejecting this approach.
