# CFB Literature Review 07: Line Movement, Closing Line Value, and Bookmaker Behavior

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

Find what has been published about how FBS lines move from opener to close, whether that movement is predictable, whether beating the close predicts profit, and how bookmakers set and move lines.

Context from the developer's own backtest. It is their record, not a published study; use it only to steer the search:

- A screened consensus of Prediction Tracker's computer ratings anticipated about 15% of the open-to-close spread move. The out-of-sample R² was 0.15 on 14,068 games (2006–2025), and it called the direction of the move correctly about 7 times in 10.
- The standard deviation of close minus open was 2.48 points.
- The opener was the only price at which this was measured.
- Prediction Tracker publishes after the opener has already moved, so the opener figure is not a price that could have been bet. The open question is whether anything remains at a later, reachable price.

Answer each sub-question:

1. **Opener versus close.** Is the closing line more accurate than the opener in FBS? Label NFL evidence as transfer. How was accuracy measured?
2. **What moves lines.** Informed (sharp) money, public money, injuries, weather, and news: the FBS evidence for each.
3. **Predictable movement.** Published models that predict the direction or size of line movement, and evidence of momentum or reversal in movement.
4. **Speed of price discovery.** How fast information is incorporated, by market size (Power versus Group of Five games) and by time to kickoff.
5. **CLV as a skill measure.** Evidence that beating the closing line predicts long-run profit, and any academic validation of CLV as an evaluation metric.
6. **How books set lines.** Market making versus balancing the book; Levitt's hypothesis and later tests; line originators and books copying each other; how retail books set lines since 2018.
7. **Limits and liquidity.** How betting limits vary by market and by time before kickoff, and what that implies for efficiency in small-conference games.
8. **Cross-book dispersion.** Price differences between books, stale lines, and the measured value of line shopping.
9. **The opening line.** Who opens FBS lines, opener limits, and how efficient the opener is compared with later lines.
10. **Exchanges and prediction markets.** Any evidence on college football pricing from betting exchanges or event-contract markets.

Representative queries (use these and variants):

- "opening line closing line accuracy football"
- "point spread line movement informed traders"
- "closing line value predicts profit"
- "sports betting price discovery"
- "bookmaker pricing balanced book Levitt"
- "sportsbook betting limits market efficiency"
- "line movement college football"
- "sharp money reverse line movement"
- "betting exchange college football"

Author leads (search each for college football work; report none found if none exists): Steven Levitt, Rodney Paul, Andrew Weinbach, Tobias Moskowitz, Raymond Sauer, Brad Humphreys.

## Deliver

1. A movement-evidence table: question, finding, seasons, sample, source, and evidence label.
2. CLV evidence: studies that link beating the close to profit, and how each was validated.
3. Bookmaker-behavior findings: balancing versus positioning, originators, copying, and limits.
4. Movement questions with no FBS evidence.
5. Every testable hypothesis the evidence supports for predicting or exploiting line movement, ranked by expected value, each with its supporting studies and the result that would falsify it. No cap on the number.
6. The master table, coverage log, and research cutoff.
