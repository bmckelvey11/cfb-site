# FBS Totals Research: Market and Model Error Anatomy

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

Build diagnostic framework explaining when market, model, or both fail on FBS totals.

Classify games where market and model are accurate, model improves market, market improves model, both miss together, both miss oppositely, model predicts correct side without CLV, model earns CLV but loses result, or apparent edge comes from invalid line data.

Analyze errors by season, week, total, spread, conference, experience, quarterback or coaching change, pace, efficiency, weather, venue, travel, rest, overtime, turnovers, defensive scores, explosives, red-zone outcomes, fourth-down decisions, and garbage time.

Separate pregame-predictable error from realized-game randomness. Postgame variables may explain errors but cannot become features unless forecastable before wager.

Research residual decomposition, hierarchical residual models, conditional calibration, error clustering, influence diagnostics, simulation-based decomposition, model disagreement, ensemble attribution, and regime discovery.

Require shrinkage, chronological holdouts, and multiple-testing controls for subgroup findings.

Deliver:

1. Error taxonomy.
2. DuckDB-ready diagnostic fields.
3. Recommended plots and statistical tests.
4. Stable versus unstable error segments.
5. Process converting findings into feature, data, or model experiments.
6. Cheap diagnostic sequence before new model engineering.
