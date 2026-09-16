# FBS Totals Research: Alternate and Derivative Markets

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

Determine whether related markets contain incremental information for full-game FBS totals.

Research team totals, first-half and first-quarter totals, alternate full-game totals, alternate spreads, moneylines, scoring props, and cross-book derivative disagreement.

Questions:

- Can team totals expose asymmetric expectations hidden by full-game total?
- Can first-half versus full-game pricing reveal second-half pace or game script?
- Can alternate ladders identify market-implied variance, skew, and tail mass?
- Can spread and team totals reveal inconsistent prices?
- Can correlated-market disagreement identify stale quotes?
- Do derivative markets lead or follow main total?
- Does adding derivatives improve distribution forecasts after controlling for main total and spread?
- Are limits, availability, or historical coverage too weak for valid inference?

Require exact timestamp alignment. Later derivative quotes cannot enter earlier decisions.

Design information-content tests, incremental prediction tests, cross-market coherence checks, closing-movement tests, executable simulations, and feature ablations. Distinguish true disagreement from differences caused by timestamps, juice, limits, or settlement rules.
