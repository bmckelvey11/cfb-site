# FBS Totals Research: Price Discovery and Bet Timing

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

Determine how information enters FBS totals markets and when a model should bet.

Research:

- Which sportsbooks originate FBS totals, open earliest, lead subsequent moves, or follow other books.
- How leadership changes with market age, liquidity, limits, and game profile.
- Total movement versus price-only movement.
- Cross-book dispersion, stale quotes, suspensions, and quote disappearance.
- Market responses to weather, quarterbacks, injuries, coaches, and roster news.
- Whether early movement continues, reverses, predicts final score, or merely converges toward consensus.
- Tradeoff between early price and later information.

Explore lead-lag analysis, latent-consensus state-space models, Kalman filters, vector autoregression, cointegration where justified, Granger-style predictive tests without causal overclaiming, quote-change point processes, survival models for next move, optimal stopping, and book-specific reliability weighting.

Compare executable strategies:

1. Bet earliest opener.
2. Bet when forecast first crosses threshold.
3. Predict movement and wait.
4. Bet sharp-versus-recreational divergence.
5. Bet stale outlier.
6. Bet near kickoff with fuller information.
7. Line-shop across eligible books.

Require timestamped book-specific totals and prices. Address latency, limits, missing quotes, retrospective selection, and changing book coverage. Design prospective collection if historical data cannot answer question.
