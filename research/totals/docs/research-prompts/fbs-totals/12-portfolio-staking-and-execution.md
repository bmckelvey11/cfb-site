# FBS Totals Research: Portfolio, Staking, and Execution

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

Evaluate FBS totals system as portfolio of executable wagers rather than isolated predictions.

Research flat staking, Kelly and fractional Kelly, Kelly under parameter uncertainty, capped proportional sizing, drawdown-aware sizing, risk constraints, correlated wagers, weather-driven exposure, related full-game and derivative positions, book concentration, line shopping, rejected bets, partial fills, quote latency, changing prices, limits, voids, and settlement rules.

Design execution simulator using timestamped quotes, book eligibility, bankroll, limits, quote-expiration assumptions, price selection, pushes, voids, missing closes, and explicit prohibition on retrospective best-line selection.

Separate model advantage from execution advantage.

Evaluate CLV, price CLV, net return, yield, volatility, drawdown, exposure concentration, wager count, sensitivity to price degradation, reduced limits, missing books, and calibration error.

Compare flat stakes with increasingly complex sizing using identical wager selections. Determine whether sizing benefit survives estimation uncertainty and chronological testing. Provide minimum viable execution assumptions, stress scenarios, and conditions making historical ROI non-executable.
