# FBS Totals Research: Early-Season Cold Starts

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

Determine how to model FBS totals before teams accumulate useful current-season history.

Compare priors built from previous seasons, multi-season ratings, returning production, quarterback continuity and transfer history, offensive-line continuity, skill-position production, coaching and coordinator continuity, scheme history, portal movement, recruiting talent, participation, conference strength, and sportsbook markets.

Explore empirical Bayes, hierarchical Bayes, partial pooling, dynamic latent-state models, coach and player-unit effects, embeddings, matrix factorization, graph transfer, meta-learning, change-point detection, mixture priors for stable versus transformed programs, epistemic uncertainty, and abstention.

Compare:

1. Excluding sparse-history games.
2. Market-only forecast.
3. Prior-season carry-forward.
4. Regressed team priors.
5. Hierarchical roster-aware priors.
6. Dynamic weekly updating.

Test Week 0 through Week 4 separately without selecting best cutoff after seeing final results. Require historical as-of roster and personnel data. Identify fields unavailable retrospectively.

Primary question: Can cold-start modeling improve directional CLV beyond market-only baseline, or should system abstain until uncertainty falls?
