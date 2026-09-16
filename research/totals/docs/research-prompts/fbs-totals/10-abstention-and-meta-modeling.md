# FBS Totals Research: Abstention and Meta-Modeling

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

Research when an FBS totals model should decline to wager.

Explore reject-option classification, selective regression, selective prediction, meta-labeling, cross-fitted error prediction, conformal risk control, out-of-distribution detection, ensemble disagreement, regime detection, data-quality gates, market-disagreement gates, and cost-sensitive classification.

Possible meta-targets include whether base model beats market, earns directional CLV, predicts correct side, remains within error tolerance, resembles training data, survives model disagreement, or retains executable quote.

Prevent leakage: base predictions must be out of fold and chronological; meta-model, coverage, and thresholds must be tuned before outer test; realized ROI cannot become unrestricted filter-mining target.

Evaluate coverage-risk curves, wager fraction, CLV by coverage, calibration, returns, uncertainty, and stability across seasons. Check whether methods merely select familiar teams, common totals, or better-covered games.

Compare every advanced meta-model with transparent gates based on sample history, missingness, uncertainty, price, and market disagreement. Recommend complexity only if it produces stable chronological improvement.
