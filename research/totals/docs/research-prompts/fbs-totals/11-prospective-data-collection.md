# FBS Totals Research: Prospective Data Collection

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

Design prospective FBS totals dataset with immutable historical snapshots.

Specify collection for book-specific totals and prices, alternate totals, spreads, moneylines, team totals, quote timestamps, book availability, visible limits, weather forecasts and revisions, roof status, injuries, starting quarterbacks, depth charts, rosters, news, model forecasts, prediction intervals, candidate wagers, actual wagers, abstention reasons, closes, and results.

Define:

- Polling cadence by time before kickoff.
- UTC normalization and source time zones.
- Immutable raw versus normalized records.
- Game, team, venue, player, coach, and book identifiers.
- Source provenance and request metadata.
- Missingness reasons.
- Deduplication and late corrections.
- Schema versioning and audit hashes.
- Retry and rate-limit handling.
- Licensing, terms, and retention constraints.
- Data-quality monitoring.

Provide DuckDB-compatible schemas and example records. Map every collected field to specific future experiments.

Deliver minimum viable collector, ideal collector, source comparison, expected operational burden, validation tests proving snapshots were not overwritten, and staged implementation order.
