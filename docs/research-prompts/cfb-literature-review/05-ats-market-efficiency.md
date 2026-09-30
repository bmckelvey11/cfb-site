# CFB Literature Review 05: Against-the-Spread Market Efficiency

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

Determine whether the FBS point-spread market is efficient, which biases have been documented, and which betting rules survived after they were published.

Context from the developer's own backtest. It is their record, not a published study; use it only to steer the search:

- A consensus of Prediction Tracker's computer ratings, combined by ten walk-forward rules, went 50.31% ATS on 12,560 bets against the closing spread (2001–2025). That is below the -110 break-even.
- In games where the raw panel median disagreed with the closing spread by 5 or more points, it went 53.9% ATS against the opening line (1,641 games) but 49.0% against the close.
- Prediction Tracker publishes after the opener has already moved, so the opener figure is not a price that could have been bet. The open question is whether anything remains at a later, reachable price.

Answer each sub-question:

1. **Efficiency tests.** Weak-form tests of the FBS spread market, such as regressing the margin on the spread (slope and intercept tests) and simple betting-rule tests, and how the results change by era.
2. **Favorite-longshot bias.** Evidence in spreads and moneylines, including results for large favorites, large underdogs, and double-digit spreads.
3. **Home and away.** Home-underdog and road-favorite effects, and neutral-site games.
4. **Popularity and sentiment.** Ranked teams, AP poll position, national television games, big-brand programs, prior-week results (hot hand), and public betting percentages.
5. **Timing.** Early-season versus late-season inefficiency, bowl season, conference championship games, and rivalry games.
6. **Information.** Injuries, weather, coaching news, and sharp versus public money: whether news gets priced, and how fast.
7. **Model-based strategies.** Studies where a statistical model's disagreement with the line was bet, with results after the vig and out of sample.
8. **Betting rules.** Every rule reported as profitable after the vig, and each one's later out-of-sample record, replication, or decay after publication.
9. **Bookmaker behavior.** Whether books balance action or shade lines toward public bias in college football specifically (Levitt-style tests), and how setting lines for 130+ FBS teams differs from the NFL.
10. **The post-2018 market.** Evidence from legal US markets, differences between retail books and sharp books (for example Pinnacle and Circa), differences between books' lines, and the value of line shopping.
11. **FBS versus NFL.** Is the FBS spread market less efficient than the NFL market? Report evidence in both directions.

Representative queries (use these and variants):

- "college football point spread efficiency"
- "NCAA football betting market bias"
- "favorite longshot bias college football"
- "home underdog college football betting"
- "ranked teams point spread bias"; "AP poll betting market"
- "early season betting market inefficiency football"
- "bowl games betting market efficiency"
- "sportsbook balanced book college football"; "bookmaker shading public bias"
- "betting percentages college football"
- "point spread efficiency sports betting legalization"

Author leads (search each for college football work; report none found if none exists): Rodney Paul, Andrew Weinbach, Steven Levitt, Raymond Sauer, Joseph Golec, Maurry Tamarkin, William Dare, John Gandar, Brad Humphreys, Tobias Moskowitz.

## Deliver

1. A bias catalog: bias, direction, size, seasons, sample, status, and evidence label.
2. A rules ledger: rule, original study, reported ATS %, n, result after vig, out-of-sample record, and current status.
3. A verdict on efficiency by era (before 2000, 2000–2017, 2018 onward), with the evidence for each era.
4. An FBS-versus-NFL efficiency comparison.
5. Every testable hypothesis the evidence supports for the spread model, ranked by expected value, each with its supporting studies and the result that would falsify it. No cap on the number.
6. The master table, coverage log, and research cutoff.
