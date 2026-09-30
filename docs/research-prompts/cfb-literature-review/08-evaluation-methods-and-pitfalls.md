# CFB Literature Review 08: Evaluation Methods and Pitfalls

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

Find the published standards for evaluating football prediction models and betting systems, and the published critiques of how such research goes wrong. The developer will use the result to judge every other study in this series and their own backtests.

Answer each sub-question:

1. **Data snooping and multiple testing.** White's reality check, Hansen's superior predictive ability test, false discovery rate control, and Holm-type corrections, as applied to sports betting systems.
2. **Decay after publication.** Evidence that betting anomalies weaken after they are published, and analogous evidence from asset-pricing anomalies.
3. **Statistical power.** How many bets it takes to tell a 53–56% ATS bettor from break-even, confidence intervals for win rates, and how correlation within a week or season changes the answer.
4. **Evaluation metrics.** Proper scoring rules (log loss, Brier score) versus ATS win rate versus ROI versus CLV: which is most informative at small sample sizes.
5. **Walk-forward validation and leakage.** Time-series cross-validation in sports models, and common leakage sources in college football: end-of-season ratings, data revised after the fact, and closing lines used as features.
6. **Line data quality.** How sources define opening and closing lines, lines constructed after the fact, and survivorship in odds datasets.
7. **The market as a benchmark.** Evaluating a model against de-vigged market probabilities, and forecast-encompassing tests of whether a model adds information beyond the line.
8. **Research governance.** Pre-registration and similar practices in betting and sports-analytics research.

Representative queries (use these and variants):

- "data snooping sports betting"; "reality check betting strategies"
- "multiple testing betting systems"
- "anomaly decay after publication"
- "sample size betting win rate statistical significance"
- "proper scoring rules sports forecasts Brier log loss"
- "closing line value betting skill evaluation"
- "forecast encompassing test point spread"
- "look-ahead bias sports prediction"
- "pre-registration sports analytics"

Author leads (search each for work on sports forecasting or betting; report none found if none exists): Halbert White, Peter Hansen, R. David McLean, Jeffrey Pontiff, Ray Fair, Robert Shiller, Tilmann Gneiting, Adrian Raftery.

## Deliver

1. An evaluation checklist: each standard, why it matters, and its source.
2. A pitfalls table: pitfall, how it arises in football betting research, how to detect it, and studies documented to have fallen into it.
3. A power table: bets needed to separate true win rates of 53%, 54%, 55%, and 56% from 52.38%, at 80% power and 5% significance, with the formula shown and the effect of within-week correlation.
4. Which metric (ATS %, ROI, log loss, CLV) to use at which sample size, with sources.
5. Every recommendation the evidence supports for the developer's evaluation protocol, ranked by importance, each with its source. No cap on the number.
6. The master table, coverage log, and research cutoff.
