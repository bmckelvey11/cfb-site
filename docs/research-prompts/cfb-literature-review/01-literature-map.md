# CFB Literature Review 01: Literature Map

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

Build a complete, breadth-first map of the published academic and quantitative literature on predictive and descriptive statistical analysis of FBS college football, with emphasis on predicting results against the spread and on game totals. This report is the index for the rest of the series, so favor breadth: find every study you can and grade each one briefly. Later prompts go deep on each topic. This report must also stand alone as a complete annotated bibliography.

Answer each sub-question:

1. **Betting markets.** Find every study of FBS point-spread, totals, moneyline, first-half, or team-total markets: efficiency tests, documented biases, betting rules, line movement, and bookmaker behavior.
2. **Game prediction.** Find every published model that forecasts FBS winners, margins, or scores: rating and ranking systems, bowl and playoff forecasts, regression, and machine learning.
3. **Descriptive analytics.** Find studies of which statistics explain FBS results: efficiency metrics, expected points and win probability, recruiting and talent, returning production, turnovers, home-field advantage, travel, weather, coaching, and fourth-down and play-calling decisions.
4. **Structure and policy.** Find studies of rule changes (clock and overtime rules), conference realignment, the BCS-to-College Football Playoff transition, and the transfer-portal and NIL eras, and their measured effects on scoring, competitive balance, or betting markets.
5. **Data and methods.** Identify the public datasets and R or Python packages used in academic college football work (for example cfbfastR and CollegeFootballData), and the methods papers on evaluating football forecasts or betting systems.
6. **Review articles.** Find existing surveys or literature reviews of sports-betting market efficiency or football forecasting that cover college football, and report what each concluded about FBS.
7. **The research community.** Identify which authors, research groups, journals, and conferences produce most of this work, how the volume of work changed by decade, and which topics are well covered versus thin.

Representative queries (use these and variants):

- "college football point spread market efficiency"
- "NCAA football betting market"
- "college football over/under totals betting"
- "college football wagering bias"
- "bowl game betting efficiency"
- "home underdog college football"
- "college football rating system prediction accuracy"
- "predicting college football games regression"; "machine learning college football prediction"
- "expected points added college football"; "win probability model college football"
- "recruiting rankings and team performance college football"
- "home field advantage college football"
- "college football clock rule change scoring"

Author leads (search each for college football work; report none found if none exists): Rodney Paul, Andrew Weinbach, Brad Humphreys, Raymond Sauer, Steven Levitt, David Harville, Hal Stern, Mark Glickman, Wesley Colley, Kenneth Massey, Tobias Moskowitz, Richard Borghesi.

## Deliver

1. A master table covering every study found, sorted by topic and then year. No cap on rows.
2. A topic map: for each sub-question, a paragraph on the state of the evidence and its most important studies.
3. A timeline: by decade, the questions the literature asked and what it concluded.
4. A gap list: questions with no FBS study, and questions answered only with pre-2018 data.
5. Every testable hypothesis the literature suggests for an FBS spread or totals model, ranked by expected value, each with its supporting studies. No cap on the number.
6. A reading priority: the 15 studies a model builder should read in full, ranked, with a one-line reason for each.
7. The coverage log and research cutoff.
