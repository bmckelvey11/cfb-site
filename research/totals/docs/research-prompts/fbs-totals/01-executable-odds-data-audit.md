# FBS Totals Research: Executable Odds-Data Audit

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

Determine whether available historical FBS odds data can support honest, executable totals backtests. Audit CFBD plus every credible free or affordable alternative.

Investigate:

- Meaning of opening and closing in each source: first book quote, first market quote, first captured quote, consensus value, final quote, or aggregate.
- Sportsbook identity, quote timestamp, time zone, total, over price, under price, alternate totals, and limits where available.
- Whether price-only changes are preserved.
- Whether records are revised, overwritten, or constructed retrospectively.
- Coverage and missingness by season, book, conference, team, and game type.
- Book-composition changes across seasons.
- Duplicate games, neutral sites, postponements, cancellations, bowls, and overtime.
- Whether listed prices were realistically executable.
- Retrospective best-line, best-opener, stale-line, and consensus-selection bias.
- Differences among book opener, market opener, consensus opener, earliest captured quote, book close, and consensus close.

Inspect current CFBD documentation and representative API records where possible. Never infer semantics from field names alone.

Design DuckDB audit checks for coverage, missingness, book continuity, quote ordering, implausible movement, duplicates, incomplete prices, cross-source agreement, and manual spot checks.

Deliver:

1. Source-by-source audit table with direct URLs and verified coverage.
2. Fields safe for research, fields requiring caution, and fields unsuitable for executable backtesting.
3. Canonical timestamped odds schema.
4. Historical questions current data can and cannot answer.
5. Migration, repair, or prospective collection plan.
6. Ranked data-source recommendation.
