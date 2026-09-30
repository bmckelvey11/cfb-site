# CFB Literature Review 02: Rating and Outcome Models

## Shared research instructions

Research mode: Research (Deep Research), exhaustive, with inline citations. Research cutoff: 2026-09-30.

You are advising a solo developer who builds NCAA Division I FBS (formerly Division I-A) point-spread and totals models in Python and DuckDB. Their data: CollegeFootballData (CFBD) play-by-play, box scores, and betting lines; Action Network per-book odds history; and Prediction Tracker's panel of about 150 published computer ratings. They bet at US retail sportsbooks (DraftKings, FanDuel). The spread model's target is a fair spread graded against the spread (ATS) on game results. They also track whether a model predicts open-to-close line movement (closing line value, CLV).

This prompt is one of nine in a literature-review series. Stay inside this prompt's research assignment; the other prompts cover the other topics.

**Thoroughness**

- No word limit. Target at least 5,000 words. Prefer completeness over brevity, and keep each point concise.
- Answer every numbered sub-question. When nothing is found, write `No published FBS study found in searched sources.` Never claim universal absence.
- Find at least three independent sources per sub-question where they exist.
- Search every source class below, not only the first one that returns results.
- For each sub-question, search for evidence that contradicts your main finding, and report it.

**Source classes**

- Journals: Journal of Sports Economics; Journal of Quantitative Analysis in Sports; Journal of Sports Analytics; International Journal of Forecasting; Journal of Prediction Markets; Journal of Economics and Finance; Journal of Gambling Business and Economics; International Journal of Sport Finance; Applied Economics; Applied Economics Letters; Economic Inquiry; Journal of Economic Behavior & Organization; Journal of the American Statistical Association; The American Statistician; Chance; operations research and management science journals.
- Conferences: MIT Sloan Sports Analytics Conference research papers; New England Symposium on Statistics in Sports; Carnegie Mellon Sports Analytics Conference.
- Repositories: Google Scholar, Semantic Scholar, SSRN, RePEc/IDEAS, NBER, arXiv (stat.AP, stat.ML, econ), and ProQuest and university repositories for theses and dissertations.
- Practitioner methodology from rating-system authors (SP+, FEI, FPI, Sagarin, Massey, CFBD) is allowed, labeled `[practitioner]`. It does not count toward the three-source minimum.

**Evidence rules**

- Cite every empirical and numeric claim immediately beside the claim, with a DOI, RePEc, SSRN, or publisher link.
- Separate a study's publication year from the seasons its data covers.
- Label each piece of evidence: `[FBS]` for direct college football evidence, `[NFL – transfer]`, `[other sport – transfer]`, or `[mechanism only]`. Never present transfer evidence as FBS evidence.
- Label undocumented industry, blog, podcast, and forum claims `[anecdotal]`. Label studies read only at abstract level `[abstract only]`. Label weak, extrapolated, or conflicting claims `[uncertain]`.
- Flag any betting-market finding that uses only pre-2018 data `[pre-2018]`. Legal US sports betting expanded after the May 2018 PASPA repeal, so older market findings may no longer hold.
- Author names given in this prompt are search leads, not facts. Report an author's college football work if it exists; if none exists, say so. Never attribute an FBS study to anyone without a source.
- Never fabricate papers, authors, data coverage, results, ROI, CLV, win rates, effect sizes, or quotations. If you cannot verify that a paper exists, leave it out.
- Files attached to this Space or thread (warehouse catalogs, repo docs, earlier research reports) are the developer's own notes. Use them for context only. Never cite them as literature evidence.

**Already in hand: list these in the master table, but do not re-summarize them**

- Paul & Weinbach (2005), "Bettor preferences and market efficiency in football totals," Journal of Economics and Finance.
- Paul & Weinbach (2002), "Market Efficiency and a Profitable Betting Rule: Evidence from Totals on Professional Football," Journal of Sports Economics.
- Arscott (2023), "Market Efficiency and Censoring Bias in College Football Totals Betting," Journal of Sports Economics (DOI 10.1177/15270025221148991; SSRN 4197428).
- Shank (2018), "Is the NFL Betting Market Still Inefficient?," Journal of Economics and Finance.
- Kelly & West, "Bettor biases and market efficiency in the NFL totals market."
- An AABRI paper on market efficiency in the NFL preseason totals market.
- A 2010 AEA conference paper, "Betting Markets and Market Efficiency: Evidence from College Football."
- Glickman & Stern's state-space model of NFL scores (Journal of the American Statistical Association).

**Grade every study on**

- Data: seasons, number of games, and whether it covers FBS only or all of Division I.
- Line: open or close, which book or consensus source, and whether that line could actually have been bet at decision time.
- Target: straight-up winner, margin, ATS result, total result, line movement, or a descriptive outcome.
- Validation: in-sample only, holdout, or walk-forward; whether an interval or significance test is reported.
- Betting math: whether the vig is accounted for (52.38% break-even at -110), and whether probabilities are scored with a proper scoring rule against a de-vigged market probability from the same time.
- Trial count: how many rules, models, or thresholds were tried, and whether a threshold was chosen on the test data.
- Leakage: any feature built from information not available before kickoff, such as end-of-season ratings used to predict earlier games.
- Replication: later work that confirms it, contradicts it, or shows it decaying.
- Transfer: whether the result plausibly holds at post-2018 US retail books.

A betting claim that fails the leakage, bettable-price, or test-set-threshold check is invalid, whatever its reported ROI. Say so explicitly.

**Every report ends with**

- A master table, one row per study, with these columns: Citation (authors, year, title, link) | Venue | Peer-reviewed (Y/N) | Evidence label | Seasons and n | Line used (n/a if none) | Target | Method | Main result, with the number | Validation | Leakage risk | Status (Holds / Decayed / Contradicted / Untested / Invalid).
- A coverage log: for each sub-question, the source classes and representative queries searched, the number of sources found, and what could not be found or opened.
- The research cutoff date and any access limitations.

## Research assignment

Find and evaluate every published statistical model for predicting FBS game winners, margins, and scores, and establish how accurate each one is against the betting line when tested out of sample.

Context from the developer's own backtest. It is their record, not a published study; use it only to steer the search:

- Ten walk-forward rules for combining Prediction Tracker's panel of computer ratings, tested on 12,800–14,300 games from 2001–2025, went 50.31% ATS on 12,560 bets against the closing spread. That is below the -110 break-even.
- In games where the raw panel median differed from the closing spread by 5 or more points, the panel went 49.0% ATS against the close, but 53.9% against the opening line (1,641 games).
- Prediction Tracker publishes after the opener has already moved, so the opener figure is not a price that could have been bet. The open question is whether anything remains at a later, reachable price.

Find literature that explains or contradicts this pattern.

Answer each sub-question:

1. **Margin-based ratings.** Least-squares ratings (Massey-type and Harville-type), ridge or other regularized versions, and home-field terms: published formulations and their out-of-sample accuracy on FBS games.
2. **Win-loss ranking systems.** The Colley matrix, the BCS computer components, and Markov-chain and eigenvector rankings (Keener, PageRank-style): what they predict, and the evidence from the debate over excluding margin of victory.
3. **Dynamic models.** Elo, Kalman filter and state-space models, and Bayesian hierarchical models applied to FBS, and how each handles team strength changing within a season.
4. **Statistical and machine-learning models.** Regression, tree ensembles, and neural networks built on box-score, play-by-play, or recruiting inputs: their published accuracy against the line, and how each evaluation was split in time.
5. **Preseason priors and early season.** How published models set priors (prior season, recruiting, returning production), how fast they converge, and accuracy by week of season.
6. **Schedule sparsity.** How models handle FBS's thinly connected schedule (conference isolation, FCS opponents, few non-conference games), and the measured effect on accuracy.
7. **Margin-of-victory treatment.** Capping, diminishing returns, and garbage-time adjustment, and their measured effect on predictive accuracy.
8. **Head-to-head comparisons.** Published comparisons of computer ratings against each other and against the betting line, including analyses of Prediction Tracker or Massey comparison data. Does any model beat the closing line out of sample?
9. **Combining forecasts.** Evidence on ensembles or consensus of rating systems in football, the forecast-combination puzzle, and whether combining beats the market.
10. **Postseason.** Bowl and playoff prediction accuracy, and the published effects of motivation, player opt-outs, and long layoffs.

Representative queries (use these and variants):

- "college football rating system accuracy point spread"
- "least squares ratings college football"; "Massey ratings"
- "Colley matrix"; "BCS computer rankings margin of victory"
- "Elo college football"; "Bayesian state space model college football"
- "predicting college football point spread machine learning"
- "bowl game prediction model"
- "Prediction Tracker computer ratings accuracy"
- "forecast combination sports betting"

Author leads (search each for college football work; report none found if none exists): David Harville, Hal Stern, Mark Glickman, Wesley Colley, Kenneth Massey, Ray Stefani, James Keener.

## Deliver

1. A methods catalog table: model family, inputs, how it is fit, how it updates in season, published accuracy (straight-up %, mean absolute error, ATS %), result against the closing line, and evidence label.
2. A literature-supported explanation of why computer ratings do or do not beat the closing line, and why results against the opener differ from results against the close.
3. Accuracy by week of season, where published.
4. What transfers to a model built on CFBD data and priced against US retail lines, and what does not.
5. Every testable hypothesis the evidence supports for the spread model, ranked by expected value, each with its supporting studies and the result that would falsify it. No cap on the number.
6. The master table, coverage log, and research cutoff.
