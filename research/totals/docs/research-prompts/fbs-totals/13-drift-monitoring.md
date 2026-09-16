# FBS Totals Research: Drift Monitoring

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

Design live monitoring for FBS totals data, predictions, calibration, market relationships, and execution.

Monitor input distributions, missingness, feature freshness, team and book coverage, prediction distributions, market residuals, calibration, CLV, realized results, wager rate, average edge, abstention, execution, and segment performance.

Research distribution-distance measures, sequential change detection, CUSUM, Page-Hinkley, Bayesian change points, rolling calibration, online conformal diagnostics, control charts, adaptive forgetting, online learning, and champion-challenger systems.

Distinguish pipeline failure, covariate drift, outcome drift, calibration drift, market adaptation, regime change, and random variation.

Design:

- Monitoring cadence.
- Baselines and comparison windows.
- Alert logic.
- Minimum evidence before intervention.
- Investigation sequence.
- Retraining triggers.
- Rollback rules.
- Safeguards against reacting to short losing streaks.
- Dashboard layout.
- DuckDB queries or pseudocode for each diagnostic.

Backtest monitoring system itself across historical rule, roster, and market changes where possible. State which alerts would have fired and whether response would have helped without future knowledge.
