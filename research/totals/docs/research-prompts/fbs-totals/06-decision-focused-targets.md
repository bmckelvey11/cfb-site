# FBS Totals Research: Decision-Focused Targets

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

Determine what an FBS totals system should predict and optimize.

Compare final combined points, separate team scores, possessions and points per possession, market residual, over/under/push probability, full joint score distribution, quantiles, conditional variance, closing total, future movement, probability of beating close, expected future price, wager expected value, and portfolio utility.

For each target, analyze decision relevance, suitable loss functions, calibration, outlier sensitivity, vig, pushes, market inputs, and whether target supports raw accuracy, CLV, or expected value.

Compare squared, absolute, Huber, quantile, log, Brier, CRPS, discrete proper-scoring, decision-weighted, utility-based, and multi-objective losses.

Investigate:

- Whether direct residual regression differs materially from predicting points with line included.
- Whether optimizing closing movement learns market behavior rather than scoring.
- Whether lower point error improves betting decisions.
- Whether direct EV or policy learning is defensible with available sample.
- Whether multi-task targets regularize predictions or create negative transfer.

Use common chronological benchmark with identical games, timestamps, prices, and inputs. Recommend primary target, secondary diagnostic targets, calibration layer, and wagering-decision layer.
