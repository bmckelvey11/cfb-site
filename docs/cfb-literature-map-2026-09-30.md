**Status:** unverified Perplexity Deep Research output (prompt [01](research-prompts/cfb-literature-review/01-literature-map.md), run 2026-09-30). Citations are leads until the [09 synthesis](research-prompts/cfb-literature-review/09-final-synthesis.md) citation audit. Known errors: Fair (2002/03) is published as Fair & Oster (2007), *Journal of Sports Economics* 8(1), per reference 164; Golec & Tamarkin is linked to an unrelated paper at reference 63 (use 184/185); references 474-476 are this repo's own files, not literature.

# CFB Literature Review 01: Literature Map

The FBS literature is broad enough to support strong priors about team strength, scoring, home field, recruiting, and market efficiency, but it is surprisingly thin on genuinely deployable post-2018 ATS or totals systems. Most reported betting anomalies use pre-2018 data, and many prediction papers evaluate straight-up accuracy rather than fair-spread error, de-vigged probabilities, CLV, or walk-forward profitability.

## Scope and grading

This map includes peer-reviewed articles, working papers, theses, conference work, quantitative repositories, and selected practitioner systems. Evidence is labeled `[FBS]`, `[NFL – transfer]`, `[other sport – transfer]`, `[mechanism only]`, `[practitioner]`, `[abstract only]`, `[pre-2018]`, `[uncertain]`, or `[anecdotal]` as applicable.

A betting result is treated as **invalid as an actionable betting claim** when it demonstrably uses leaked information, an unavailable price, or a threshold selected on the reported test sample. Missing documentation instead receives **Untested**, because an inaccessible methods section does not prove that an error occurred.

The ATS break-even rate at standard -110 pricing is $110/(110+100)=52.38\%$. A 53% historical ATS rate is therefore not sufficient evidence without uncertainty intervals, a frozen selection rule, and protection against multiple testing.

______________________________________________________________________

## Topic map

### Betting markets

The foundational FBS point-spread literature generally finds that the closing line is difficult to improve on, but it also reports localized anomalies involving recent ATS performance, home teams, favorites, conference status, regional information, and mismatched major-versus-minor programs. Fair’s ranking-combination study found independent predictive information in multiple computer systems but no information beyond the final Las Vegas spread, while Sinkey and Logan reported overpriced favorites, underpriced home teams, and a bookmaker adjustment for recent ATS “hotness” over more than 14,000 games from 1985–2008.[^1_1][^1_2]

Conference-related results are less uniform. Paul, Weinbach, and Higger found that automatic-qualifying teams attracted disproportionate betting interest yet won ATS more often than efficiency would imply against non-AQ teams, while a later interconference study covering September 2003 through January 2016 rejected efficiency for some Power Five/AQ matchups but described the all-sample strategy as not especially profitable. These results contradict a simple “public overvalues brand-name teams” rule and suggest that conference effects depend on matchup direction, era, and incentive structure.[^1_3][^1_4]

The strongest totals-specific FBS contribution is Arscott’s work on censoring bias in college-football totals. Paul and Weinbach’s earlier football-total studies, Kelly and West, and the NFL-preseason AABRI paper supply additional totals-market context but are already in hand and are therefore only indexed below. Linna, Moore, Paul, and Weinbach provide the clearest event-study result: the 2006 clock rules reduced scoring faster than totals markets adjusted, while 2007 rule changes produced temporary volatility that diminished during the season.[^1_5]

The literature offers little verified FBS evidence on modern market microstructure. **No published FBS study found in searched sources** for first-half lines, team totals, per-book disagreement at DraftKings or FanDuel, timestamped open-to-close price discovery, or whether a model’s disagreement with the opener predicts CLV after controlling for news and limits. Likewise, no verified FBS paper jointly evaluates spread accuracy, ATS probability, CLV, vig, and bookmaker-specific availability.

Contrary evidence is substantial. Prediction Tracker results show that respected computer systems can predict winners at roughly 73%–75% while remaining around 50% ATS, and Fair found the final spread subsumed the systems’ independent information. Thus, better football ratings need not generate bettor surplus.[^1_2][^1_6]

### Game prediction

Published FBS prediction work begins with linear and least-squares systems. Harville developed linear-model methodology for rating high-school or college teams; Massey’s 1997 honors project applied least squares to all 111 Division I-A teams in the 1996 season; and Colley subsequently developed a wins-and-losses matrix method. These works established the schedule-adjusted network formulation that remains central to modern ratings.[^1_7][^1_8][^1_9]

Margin-aware systems appear more useful for forecasting than ranking systems based only on wins and losses. Sagarin’s public methodology distinguishes a score-based Predictor from Elo-style systems, while Massey explicitly models score differential through least squares. Prediction Tracker evidence and practitioner comparisons similarly indicate that systems incorporating margin and strength of schedule outperform pure win-loss rankings as forecasts, although they do not reliably beat the spread.[^1_10][^1_8][^1_11][^1_12]

Fair’s combination study is especially relevant to a panel-of-ratings model. It found that several ranking systems contain independent information, that estimated optimal weights outperform any one system, and that the final spread nevertheless absorbs the combination’s useful information. This supports using rating-panel dispersion and residuals as fair-spread features, but not treating panel consensus as an automatic ATS edge.[^1_2]

Machine-learning evidence is narrower. Delen, Cogdell, and Kasap studied 244 bowl games using 28 variables and compared CART, SVM, and neural networks; CART reached 86% under ten-fold cross-validation and 82.9% when earlier seasons trained a 2010–11 holdout. That is a meaningful winner-classification result, but it does not establish ATS profitability, and bowl-only samples are subject to selection, neutral-site, motivation, and regime problems.[^1_13][^1_14][^1_15]

Saunders developed three regression ranking systems and tested 2012–2013 predictions against the six BCS computers. One model recorded 66.2% and 66.5% in the two seasons, while Sagarin led the 2012 comparison at 73.7%. More recent work reports random-forest margin prediction, but accessible metadata do not adequately document preseason feature timing, game-level sample construction, or a true walk-forward design.[^1_16][^1_17]

The main contradiction to “use a more sophisticated learner” is that the broader team-sport review found feature design more important than simply increasing algorithmic complexity and recommended comparison across model families rather than relying on neural networks. FBS papers rarely compare models on identical seasons against closing-line MAE, calibration, and de-vigged market probabilities.[^1_15]

### Descriptive analytics

Recruiting is the best-covered structural predictor. Bergman and Logan assembled star-level recruiting records for every FBS school from 2002–2012 and found that school fixed effects reduced estimated recruit impacts by more than 25%, but the remaining relationship with wins and lucrative bowl appearances stayed statistically and economically significant. Their within-school estimate associated an additional five-star recruit with about 0.306 wins, versus 0.437 in between-school OLS.[^1_18][^1_19]

Other recruiting studies generally agree on direction but vary widely in magnitude. Mankin and Rivas reported that 247Sports recruiting ratings explained up to 36% of variation in final Sagarin ratings over a long panel, while a conference proceeding using 2006–2018 data found prior-year Sagarin rating to be the strongest single predictor and also identified returning starters, quarterback return, junior-class composition, and high-end recruits. These results imply that talent features should be residualized against persistent program quality rather than entered as raw rankings.[^1_20][^1_21]

Home-field evidence supports heterogeneity. Caudill and Mixon used the Iron Bowl’s neutral- and home-site history to study ticket allotments, stadium capacity, and win probability. A COVID-era natural experiment found that NCAA home teams were favored by 7.06 points on average in 2007–2019 games but 4.62 in 2020, and estimated that approximately 35% of NCAA home advantage came from spectators; it also reported that historical lines moved 0.28 points toward home teams before 2020 but 0.27 points toward visitors in 2020. Because average team quality and scheduling affect raw home spreads, these numbers are not interchangeable with a causal points-based HFA coefficient.[^1_22][^1_23][^1_24]

Efficiency, explosiveness, field position, finishing drives, and turnovers recur in practitioner analytics but have less rigorous FBS publication support. One 2016 project covering 857 FBS games reported win rates of 85.26% when a team won the yards-per-play comparison, 85.13% for success rate, 78.37% for field position, 74.65% for finishing drives, and 79.03% for turnover margin. These are contemporaneous descriptive associations—not pregame forecasts—so directly using same-game statistics to “predict” that game would be leakage.[^1_25]

Turnovers are a particularly important distinction between description and prediction. Practitioner evidence argues that fumble recovery and interception conversion regress substantially, while NFL research finds that turnovers are partly predictable conditional on play state but remain rare events. The model implication is to forecast expected turnovers from pressure, pass-breakup, fumble, quarterback, and game-state inputs rather than carry forward raw turnover margin.[^1_26][^1_27][^1_28]

FBS coaching evidence is mixed. Matching-based research covering coaching changes from 1997–2010 found little benefit for very poor teams and worse subsequent performance for middling programs that replaced their coach. Secondary synthesis reports that small-resource programs may improve after replacing poorly performing coaches, whereas large-resource programs exhibit smaller effects. Coach-change indicators therefore need interactions with inherited roster quality, prior performance, resources, coordinator continuity, and replacement circumstances.[^1_29][^1_30]

**No published FBS study found in searched sources** that fully documents an open, replicable expected-points or win-probability model with play-level training data, temporal validation, calibration, and comparisons against a sportsbook baseline. Public EPA and win-probability implementations exist through CFBD and cfbfastR, but they are primarily data products and practitioner methodology rather than peer-reviewed forecast evaluations.[^1_31][^1_32][^1_33]

### Structure and policy

Rule changes provide the clearest causal connection between policy and totals. The 2006 clock rules reduced average scoring and were not immediately incorporated into market totals; the 2007 reversal and kickoff changes created further volatility before the market adapted. Contemporary reporting estimated that average plays fell from 168 to 152 and scoring from 52.44 to 47.37 in 2006, but those raw numbers should be interpreted through the peer-reviewed market study rather than as an independent betting test.[^1_34][^1_5]

Conference realignment research has concentrated more on attendance, finances, and recruiting than game prediction. Groza found that teams changing conference after the 2004 season increased attendance even after controlling for competition quality. Hoffer and Pincin’s 2006–2011 panel of 227 public institutions found that moves into automatic-qualifying conferences raised revenue by about \$12.15 million and expenditures by \$10.12 million, while entry into any FBS conference raised them by approximately \$6.43 million and \$5.03 million.[^1_35][^1_36][^1_37]

A separate realignment study found a statistically significant aggregate increase in average recruit star rating from 2.86 to 2.92 and total player rating from 15.97 to 16.40, although the increase in individual player rating was not significant. These results support conference-membership interactions and structural-break handling, but they do not directly demonstrate spread or totals edge.[^1_38]

The BCS and CFP literature examines ranking fairness and competitive balance. Kotchen and Potoski’s analysis of 2005–2010 coaches’ ballots reported own-team, conference, and defeated-opponent favoritism, showing that human polls are endogenous rather than clean measures of team strength. A 2005–2022 difference-in-differences study concluded that the 2014 CFP transition reduced competitive balance, especially in Power Five conferences.[^1_39][^1_40][^1_41]

NIL findings are already contradictory. Li and Derdenger found wider talent dispersion and estimated that NIL was associated with spreads approximately 1.2 points smaller after controls, along with closer actual margins and more favored-team losses. An Applied Economics study instead concluded that NIL values help elite programs attract talent and are unlikely by themselves to allow less prominent programs to catch the top tier. Brown’s 2021–2024 thesis found no statistically significant direct football relationship between its NIL class-value proxy and win percentage after controls.[^1_42][^1_43][^1_44][^1_45]

The portal is less well covered than NIL. A theoretical model suggests that a transfer portal can reverse some competitive effects of NIL, but that is `[mechanism only]`, not an FBS game-level causal estimate. **No published FBS study found in searched sources** that isolates portal additions and losses by position and predicts game margins, totals, line movement, or ATS outcomes.[^1_46]

### Data and methods

CollegeFootballData is the dominant public API infrastructure in the accessible modern ecosystem. Its endpoints expose schedules, results, team and player box scores, weather, recruiting, historical lines, advanced box scores, EPA/PPA, and win-probability-related metrics; the historical lines endpoint permits filters by season, week, team, conference, and provider.[^1_47][^1_48][^1_49][^1_31]

The main limitation for betting research is timestamp granularity. The documented `/lines` endpoint provides historical providers and outcomes but does not, in the accessible documentation, establish complete intraday open-to-close quote histories equivalent to Action Network’s per-book feed. Consequently, a CFBD line labeled “consensus” or “provider” should not be assumed to be the exact price available when a model forecast was frozen.[^1_49]

`cfbfastR` is the primary open R package and supplies analysis-ready play-by-play workflows. Its formal citation identifies Saiem Gilani, Akshay Easwaran, Jared Lee, and Eric Hess; the associated data repository distributes rectangularized Parquet, CSV, and RDS files after enrichment for EPA, WPA, QBR, and advanced box scores. The Python analogue is `sportsdataverse.cfb`, but a package’s availability does not itself validate the embedded models.[^1_32][^1_33]

Forecast evaluation should separate four questions:

- **Margin accuracy:** MAE, RMSE, signed error, quantile coverage, and residual stability.
- **Probability quality:** log loss, Brier score, reliability, sharpness, and calibration slope.
- **Market-relative skill:** candidate score minus the contemporaneous, de-vigged market benchmark on identical games.
- **Betting performance:** fixed decision rule, actual available price, vig, confidence interval, drawdown, and multiplicity correction.

Proper scoring rules reward honest probabilities rather than only correct classifications. The forecasting literature debates Brier, ranked probability, and ignorance/log scores; Wheatcroft’s simulations favored the ignorance score over Brier and ranked probability for three-outcome association-football forecasts. For binary ATS or totals outcomes, Brier and log loss remain natural, but comparison must use the market price from the same timestamp and book.[^1_50][^1_51][^1_52]

Walk-forward evaluation is essential because FBS distributions shift through rules, conferences, coaching, roster movement, and NIL. Sagarin describes day-by-day retrospective prediction storage and argues that Bayesian starting values remain helpful even late in a season, but the proprietary implementation cannot be independently audited. Delen’s final-season holdout is stronger than cross-validation alone, although bowl-only classification still does not establish market-relative value.[^1_53][^1_13][^1_15]

### Review articles

Vandenbruaene, De Ceuster, and Annaert’s 2022 *Journal of Sports Economics* review is the most important betting-efficiency survey for this project. It catalogs college-football work including Sinkey and Logan and emphasizes that apparent profitable rules must be separated from robust efficiency rejection and trading feasibility.[^1_54][^1_55]

Stekler, Sendor, and Verlander’s 2010 *International Journal of Forecasting* article surveys sports forecasting and notes that much of the literature studies betting-market efficiency rather than the statistical properties of sports forecasts themselves. Its relevance is methodological: accuracy should be evaluated as forecasting, not merely as a count of winning bets.[^1_56][^1_57][^1_58]

The team-sport machine-learning review covers NCAA bowl prediction and reports Delen et al.’s CART result while warning that heterogeneous datasets and features make cross-study accuracy comparisons difficult. A newer systematic review of sports ML finds that ensemble trees dominate structured tabular applications, but its corpus is multisport and therefore provides transfer evidence rather than a specific endorsement for FBS.[^1_59][^1_13][^1_15]

### Research community

The economics literature is concentrated around Rodney Paul, Andrew Weinbach, Trevon Logan, Kenneth Linna, Daniel Kuester, Shane Sanders, and related collaborators. Recurrent outlets include the *Journal of Sports Economics*, *Journal of Economics and Finance*, *Eastern Economic Journal*, *Journal of Prediction Markets*, *Applied Economics*, and *International Journal of Forecasting*.[^1_54][^1_3][^1_1][^1_5]

The statistical-ranking lineage is associated with David Harville, Kenneth Massey, Wesley Colley, Jeff Sagarin, and later rating-combination or machine-learning work. Harville’s public implementation points to his *American Statistician* model-based prediction paper; Massey and Colley provide transparent mathematical formulations, while Sagarin’s operational system remains partly proprietary.[^1_60][^1_8][^1_9]

Author-lead results:

- **Rodney Paul and Andrew Weinbach:** Multiple verified FBS totals, bookmaker, conference, and rule-change studies.[^1_4][^1_3][^1_5]
- **David Harville:** Verified college-football rating and prediction work.[^1_7][^1_60]
- **Kenneth Massey:** Verified Division I-A least-squares rating work.[^1_8]
- **Wesley Colley:** Verified college-football matrix-ranking method.[^1_9]
- **Steven Levitt:** Verified NFL bookmaker-behavior work, but **no published FBS study found in searched sources**.[^1_61]
- **Richard Borghesi:** Verified NFL home-underdog work, but **no published FBS study found in searched sources**.[^1_62]
- **Mark Glickman and Hal Stern:** Verified NFL state-space score modeling; **no direct FBS paper verified in searched sources**.
- **Tobias Moskowitz:** **No published FBS study found in searched sources.**
- **Raymond Sauer:** **No direct FBS empirical study verified in searched sources.**
- **Brad Humphreys:** FBS sports-economics work exists on broader college-athletics topics, but **no direct FBS spread/totals prediction study verified in searched sources.**
- **Jeff Sagarin:** Extensive `[practitioner]` college-football ratings, but no fully reproducible peer-reviewed FBS betting test located.[^1_10][^1_53]

The volume rose from a small mathematical-rating literature in the 1970s–1990s to a sizable market-efficiency and BCS literature in the 2000s–2010s. Since 2020, public play-by-play infrastructure and policy shocks have expanded, but peer-reviewed FBS forecast-validation work has not grown as quickly as practitioner analytics.

______________________________________________________________________

## Timeline

### 1970s–1980s

The primary question was how to estimate latent team strength from an incomplete schedule graph. Harville’s linear-model approach established a statistical framework for rating high-school and college teams, while later proprietary systems such as Sagarin translated related concepts into weekly forecasts.[^1_7][^1_10]

Betting was not yet the center of this literature. Prediction meant ranking teams, adjusting for schedule, and forecasting winners or margins rather than evaluating prices, vig, or CLV.

### 1990s

The literature moved toward explicit efficiency testing and transparent least-squares ratings. Golec and Tamarkin examined both NFL and college point spreads over a long sample and found clearer named anomalies in the NFL than in college football, while Massey formalized a margin-based least-squares system for the 1996 Division I-A season.[^1_63][^1_8]

This decade supplied the mathematical backbone for schedule-adjusted ratings, but not modern forecast governance. Temporal splits, model registries, timestamped data, and multiple-testing adjustments were generally absent.

### 2000s

The BCS era generated work on rankings, market efficiency, totals, regional information, and postseason design. Fair found that combining computer ratings improved raw prediction but not beyond the final spread, while Paul and Weinbach examined football totals and Harville’s broader model-based prediction tradition continued.[^1_60][^1_2]

The 2006 clock-rule shock became a rare natural experiment where the totals market was measurably slow to adapt. Most results from this decade are `[pre-2018]` and should be treated as hypotheses for replication, not deployable strategies.[^1_5]

### 2010s

Research diversified into machine learning, bookmaker behavior, conference biases, recruiting, coaching, realignment, and review articles. Delen et al. applied CART, SVM, and neural networks to bowl games; Bergman and Logan used school fixed effects to estimate recruit quality; Sinkey and Logan documented hot-hand-related price setting; and Vandenbruaene’s later review consolidated this spread-market literature.[^1_19][^1_1][^1_15][^1_54]

This decade also exposed a persistent evaluation gap. Papers commonly reported straight-up accuracy, regression significance, or historical strategy returns without the full combination of walk-forward testing, actual prices, de-vigged market comparison, and threshold governance.

### 2020s

The post-PASPA, CFP, COVID, portal, and NIL eras create major structural breaks. COVID attendance supplied a natural experiment for spectator-driven HFA, while NIL work now reaches conflicting conclusions about talent concentration and competitive balance.[^1_24][^1_45][^1_42]

Open data have improved through CFBD and cfbfastR, but academic validation still lags implementation. The strongest current research opportunity is therefore not another isolated classifier; it is a fully reproducible market-relative forecast and CLV study using timestamped retail-book prices.[^1_48][^1_32]

______________________________________________________________________

## Evidence gaps

### No direct FBS study found

- First-half spreads or totals.
- Team-total efficiency.
- Same-game derivatives or alternate spreads/totals.
- DraftKings-versus-FanDuel price leadership.
- Per-book open-to-close price discovery.
- CLV as an evaluation target for public FBS models.
- Whether forecast disagreement with the opener predicts closing movement.
- Proper scoring against a contemporaneous, de-vigged FBS market probability.
- Open, calibrated FBS expected-points and win-probability model validation.
- Heavy-rain, snow, heat, and wind effects in a peer-reviewed FBS betting design; available current work is mainly `[practitioner]` or `[anecdotal]`.
- Position-specific portal value for fair spreads or totals.
- Returning-production metrics tested directly against closing spread error.
- Injury-report and suspension information value in FBS.
- Travel distance, time zones, altitude, and body-clock effects against FBS spreads.
- Referee effects on FBS scoring and penalties.
- Modern overtime-rule effects on closing totals.
- Twelve-team CFP effects on late-season incentives and spreads.
- Market treatment of opt-outs in bowls.
- Retail-limit and account-restriction effects on realizable FBS returns.
- Survivorship and revision bias in historical public ratings.
- A prospective comparison of SP+, FEI, FPI, Sagarin, Massey, and a 150-system panel under one frozen protocol.


### Pre-2018 only or dominated

- Hot-hand and recent-ATS pricing.[^1_1]
- Regional-information inefficiency.
- AQ/non-AQ and most Power-conference wagering rules.[^1_3][^1_4]
- Classic home-underdog and favorite biases.
- The 2006–2007 rule-change totals anomaly.[^1_5]
- BCS-era computer-ranking comparisons.[^1_17][^1_2]
- Most recruiting-performance panels before NIL and the portal.[^1_19]
- Most sportsbook-behavior tests based on Las Vegas or offshore consensus lines.
- Almost all direct evidence about whether closing lines subsume computer ratings.

______________________________________________________________________

## Model hypotheses

These are ranked by **expected research value**, not promised betting profitability. “High” means strong prior plausibility plus feasible modern testing; it does not mean a positive expected monetary return has already been established.


| Rank | Hypothesis | Expected research value | Supporting evidence | Required test |
| --: | :-- | :-- | :-- | :-- |
| 1 | The residual between a panel ensemble and the opener predicts CLV better than ATS outcomes. | High | Rating systems contain independent information, but the close tends to subsume it.[^1_2] | Freeze panel and opener timestamps; regress per-book close movement on residual, dispersion, week, and liquidity proxies. |
| 2 | Panel dispersion contains information beyond panel mean. | High | Optimal combinations outperform individual systems, indicating nonredundant signals.[^1_2] | Walk-forward stacking with mean, median, trimmed mean, dispersion, and system-family clusters. |
| 3 | Rule changes first affect plays and scoring, then market totals with a lag. | High | The 2006 clock change lowered scoring before totals fully adjusted.[^1_5] | Event-study by week around 2023 and future rules, using open and close separately. |
| 4 | HFA should vary by attendance, stadium, opponent travel, and crowd regime rather than use a fixed three points. | High | Stadium/ticket-allotment and COVID evidence supports crowd-sensitive HFA.[^1_22][^1_24] | Hierarchical team-season HFA with partial pooling and neutral-site treatment. |
| 5 | Raw turnover margin should regress toward expected turnover margin. | High | Turnover outcomes contain a large luck component even if some play-level risk is predictable.[^1_26][^1_28] | Replace turnover margin with expected interceptions and fumble recoveries. |
| 6 | Margin-aware ratings outperform win-loss-only ratings for spread MAE. | High | Massey, Sagarin, and practitioner benchmarks favor margin plus schedule strength.[^1_8][^1_64][^1_11] | Same-game, same-date walk-forward comparison with no end-of-season ratings. |
| 7 | Recruiting affects baseline strength but adds less after program and prior-rating controls. | High | Fixed effects reduce recruiting coefficients by more than 25%, but do not eliminate them.[^1_19] | Hierarchical roster-talent model with school effects, class age, attrition, and portal changes. |
| 8 | Returning quarterback and starter continuity matter most early in the season. | High | Returning QB and starter variables entered multiple performance models.[^1_20] | Week-varying coefficients that decay as current-season snaps accumulate. |
| 9 | Early-season priors should remain Bayesian rather than being discarded after a few games. | High | Sagarin reports better prediction when starting ratings persist even later in the season.[^1_53] | Optimize prior half-life strictly inside rolling training windows. |
| 10 | Market inefficiency, if present, is concentrated at the opener rather than close. | High | Fair found the final spread absorbed rating information; line movement studies remain missing.[^1_2] | Compare model skill versus opener, snapshot ladder, and close. |
| 11 | Recent ATS “hotness” is overincorporated into subsequent spreads. | Medium-high | Sinkey and Logan found line inflation associated with recent ATS performance.[^1_1] | Replicate 2019–2026 with frozen rolling ATS variables and preregistered bins. |
| 12 | Conference-brand effects are interaction-specific, not a universal fade-the-public rule. | Medium-high | Major-conference evidence points in conflicting directions.[^1_3][^1_4] | Conference-pair random effects with rolling eras and no test-sample thresholding. |
| 13 | Crowd effects are stronger in communication-sensitive situations. | Medium-high | Spectator and stadium evidence supports a partial crowd channel.[^1_23][^1_24] | Interact attendance with false starts, delay penalties, third downs, and late-game drives. |
| 14 | Team-specific HFA estimates need strong shrinkage. | Medium-high | Average HFA is estimable, but individual stadium effects are noisy.[^1_65] | Hierarchical posterior with conference and venue pooling. |
| 15 | Success rate and yards per play are stronger latent-strength indicators than raw yards. | Medium-high | Descriptive FBS evidence finds high contemporaneous associations with winning.[^1_25][^1_66] | Use opponent-adjusted, garbage-time-filtered rolling values in walk-forward forecasts. |
| 16 | Finishing-drives performance regresses more than between-the-20s efficiency. | Medium-high | Finishing drives correlate with winning but may contain red-zone variance.[^1_25] | Decompose expected versus actual points inside the 40. |
| 17 | Tempo affects totals through play count but has nonlinear interactions with efficiency and game script. | Medium-high | Rule changes altering play volume materially changed scoring.[^1_5][^1_34] | Joint model of possessions, plays per possession, and points per drive. |
| 18 | NIL and portal changes require era-specific priors and faster roster updates. | Medium-high | NIL studies report structural changes but disagree on concentration and success.[^1_42][^1_43][^1_45] | Interactions beginning in 2021, plus portal-weighted roster continuity. |
| 19 | New conference membership causes an adjustment period not captured by historical conference ratings. | Medium | Realignment affects recruiting, revenue, attendance, and opponent composition.[^1_35][^1_36][^1_38] | Event-time indicators around entry, with roster and schedule controls. |
| 20 | Coaching-change effects depend on inherited quality and reason for departure. | Medium | Average effects are mixed and conditional on initial performance.[^1_29][^1_30] | Matched or synthetic-control coach transitions, then use estimated residual effects prospectively. |
| 21 | Bowl games require a separate model. | Medium | Delen’s bowl-specific model performed well, but bowl selection and motivation make transfer uncertain.[^1_15] | Separate regular-season and bowl estimators with opt-outs, venue, layoff, and coaching changes. |
| 22 | Heavy wind lowers totals, but the close prices most of the effect. | Medium-low | Current FBS evidence is practitioner work rather than peer-reviewed validation.[^1_67] | NOAA/game-window weather joined to per-book open and close; preregister nonlinear thresholds. |
| 23 | Heavy rain matters more than a binary rain indicator. | Medium-low | Practitioner evidence reports effects only at heavier rain levels.[^1_67] | Use measured precipitation intensity, field type, drainage, and forecast revision timestamps. |
| 24 | Models selected on ATS percentage will overfit relative to models selected on margin error and calibration. | High methodological value | Prediction Tracker shows approximately 50% ATS despite strong winner accuracy, while market forecasts remain hard to beat.[^1_6] | Nested selection: tune on MAE/log loss, evaluate ATS only once on untouched seasons. |
| 25 | A rating panel should be clustered before averaging to avoid overweighting methodologically similar systems. | High methodological value | Systems have useful but correlated information.[^1_2] | Cluster forecast residuals; weight families rather than raw system count. |
| 26 | Closing-line residuals should be evaluated conditionally on spread size. | Medium | Favorite and home-team biases may vary across market segments.[^1_1] | Predefined spline or bins, with multiplicity-adjusted inference. |
| 27 | Market accuracy may deteriorate in sudden-information regimes. | Medium | The 2020 season produced unusually large changes from opener to midweek and higher errors.[^1_6] | Identify COVID, quarterback, weather, coaching, and cancellation shocks prospectively. |
| 28 | Classification accuracy is a poor model-selection target for fair spreads. | High methodological value | Bowl classifiers can post high winner accuracy without establishing ATS or margin superiority.[^1_15] | Select by margin likelihood, CRPS/log score, and calibration—not winner accuracy. |
| 29 | Forecast distributions should be heteroskedastic by spread, total, team style, and roster uncertainty. | Medium-high | Straight-up and ATS results diverge, implying point estimates omit important uncertainty.[^1_6] | Model residual scale separately and evaluate interval coverage. |
| 30 | Any apparent subgroup ATS edge will shrink materially after accounting for all tried rules. | High methodological value | The literature repeatedly tests favorites, home teams, conferences, streaks, and thresholds. | Maintain a trial registry and use false-discovery control, reality checks, or a final untouched season block. |


______________________________________________________________________

## Reading priority

1. **Fair, “College Football Rankings and Market Efficiency.”** Best direct bridge between multiple rating systems, forecast combination, home field, and the closing spread.[^1_2]
2. **Vandenbruaene, De Ceuster, and Annaert, “Efficient Spread Betting Markets: A Literature Review.”** Best map of efficiency claims, simple strategies, and recurring methodological weaknesses.[^1_55][^1_54]
3. **Arscott, “Market Efficiency and Censoring Bias in College Football Totals Betting.”** Most directly relevant modern FBS totals paper and already in hand.
4. **Sinkey and Logan, “Does the Hot Hand Drive the Market?”** Large FBS sample and a concrete hypothesis about bookmaker adjustment to recent ATS performance.[^1_1]
5. **Linna, Moore, Paul, and Weinbach, “The Effects of the Clock and Kickoff Rule Changes…”** Strongest rule-change and totals-market event study.[^1_5]
6. **Delen, Cogdell, and Kasap, “A Comparative Analysis of Data Mining Methods in Predicting NCAA Bowl Outcomes.”** Most prominent peer-reviewed FBS machine-learning comparison, including a final-season holdout.[^1_14][^1_15]
7. **Bergman and Logan, “The Effect of Recruit Quality on College Football Team Performance.”** Strong fixed-effects treatment of recruiting and program heterogeneity.[^1_19]
8. **Massey, “Statistical Models Applied to the Rating of Sports Teams.”** Transparent mathematical foundation for margin-based schedule adjustment.[^1_8]
9. **Harville, “The Use of Linear-Model Methodology to Rate High School or College Football Teams.”** Foundational statistical rating formulation.[^1_7]
10. **Harville, “The Need for More Emphasis on Prediction.”** Model-based forecast philosophy and treatment of score discreteness and overtime.[^1_60]
11. **Paul, Weinbach, and Higger, “The ‘Large-Firm’ Effect?”** Important contradiction to simplistic major-team fade strategies.[^1_4]
12. **The 2019 interconference efficiency study, “Efficiency, Profitability, and College Football.”** Extends conference-market questions into the 2003–2016 period.[^1_3]
13. **The COVID spectator natural experiment, “How Much of Home Field Advantage Comes from the Fans?”** Useful for decomposing HFA into crowd and non-crowd components.[^1_24]
14. **Stekler, Sendor, and Verlander, “Issues in Sports Forecasting.”** Essential distinction between forecast evaluation and betting-market efficiency.[^1_57][^1_56]
15. **Li and Derdenger, “Does Personalized Pricing Increase Competition? Evidence from NIL in College Football.”** Most directly relevant policy-era work connecting NIL to spreads, actual margins, and favored-team losses.[^1_42]

______________________________________________________________________

## Master table

“NR” means not reported in the accessible record. Entries marked “already in hand” are indexed without repeating their conclusions.


| Citation (authors, year, title, link) | Venue | Peer-reviewed (Y/N) | Evidence label | Seasons and n | Line used (n/a if none) | Target | Method | Main result, with the number | Validation | Leakage risk | Status (Holds / Decayed / Contradicted / Untested / Invalid) |
| :-- | :-- | --: | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **Betting — Golec \& Tamarkin (1991), football point-spread efficiency study** | Journal article | Y | `[FBS] [NFL – transfer] [pre-2018]` | 15 years; n NR | Point spreads; source NR | ATS efficiency | Bias and year-to-year tests | Unspecified college bias; named NFL biases were clearer.[^1_63] | Historical retrospective | Low feature leakage; price timing unclear | Untested post-2018 |
| **Betting — Paul \& Weinbach (2002), “Market Efficiency and a Profitable Betting Rule: Evidence from Totals on Professional Football”** | *Journal of Sports Economics* | Y | `[NFL – transfer] [pre-2018]` | Already in hand | Totals | Total result | Market-efficiency/rule test | Already in hand; not re-summarized | See original | See original | Untested |
| **Betting — Levitt (2004), “Why Are Gambling Markets Organised So Differently from Financial Markets?”** | *Economic Journal* | Y | `[NFL – transfer] [mechanism only] [pre-2018]` | 2001–02 NFL; 19,770 bets, 285 bettors, 242 games | Online book/contest prices | Bookmaker behavior | Price-and-quantity analysis | Bookmakers exploited bettor biases and increased gross profit relative to balancing action.[^1_61][^1_68] | One-season retrospective | No FBS leakage; transfer risk high | Untested in FBS |
| **Betting — Paul \& Weinbach (2005), “Bettor Preferences and Market Efficiency in Football Totals”** | *Journal of Economics and Finance* | Y | `[FBS/NFL as defined in paper] [pre-2018]` | Already in hand | Totals | Total result | Efficiency/bettor preference | Already in hand; not re-summarized | See original | See original | Untested post-2018 |
| **Betting — Sinkey \& Logan (2010), “Betting Markets and Market Efficiency: Evidence from College Football”** | AEA conference paper | N/conference | `[FBS] [pre-2018]` | Already in hand | Point spreads | ATS | Market efficiency | Already in hand; not re-summarized | See original | See original | Superseded by later article |
| **Betting — Kuester \& Sanders (2011), “Regional Information and Market Efficiency…”** | *Journal of Economics and Finance* | Y | `[FBS] [pre-2018]` | Seasons/n NR in accessible record | Spread | ATS | Regional-information efficiency | Verified existence; full numerical result not recoverable.[^1_3] | NR | Price timing NR | Untested |
| **Betting — author metadata not recovered (2012), “Sportsbook Behavior in the NCAA Football Betting Market”** | Article record | Unclear | `[FBS] [abstract only] [pre-2018]` | NR | Spread | Bookmaker behavior | Traditional-versus-Levitt model tests | Existence verified; numeric findings unavailable.[^1_69] | NR | NR | Untested |
| **Betting — Coleman (2013), “The Power of Wagering on Power Conferences”** | *Journal of Prediction Markets* | Y | `[FBS] [pre-2018]` | NR | Spread | ATS | Conference betting rules | Verified existence; accessible record does not support exact return claims.[^1_3] | NR | Threshold selection unclear | Untested |
| **Betting — Paul, Weinbach \& Higger (2013), “The ‘Large-Firm’ Effect?”** | *Journal of Prediction Markets* | Y | `[FBS] [pre-2018]` | BCS/AQ era; n NR | Spread; betting percentages | ATS and bettor demand | AQ/non-AQ comparison | AQ teams attracted disproportionate bets and won ATS more often than efficiency implied.[^1_4] | Retrospective | Conference rule may be sample-derived | Untested post-BCS |
| **Betting — Sinkey \& Logan (2014), “Does the Hot Hand Drive the Market?”** | *Eastern Economic Journal* | Y | `[FBS] [pre-2018]` | 1985–2008; more than 14,000 games | Spread; source NR | ATS and line setting | Bias and hot-hand tests | Favorites overpriced, home teams underpriced, recent ATS performance incorporated into lines.[^1_1] | Historical retrospective | Threshold/multiplicity detail requires full text | Untested post-2018 |
| **Betting/Policy — Linna, Moore, Paul \& Weinbach (2014), “Effects of Clock and Kickoff Rule Changes…”** | *International Journal of Financial Studies* | Y | `[FBS] [pre-2018]` | 2006–2007; n NR | Market totals | Total result and scoring | Rule-change event study | 2006 scoring decline was not fully priced; 2007 volatility subsided during season.[^1_5] | Natural experiment, retrospective | Low leakage; exact bet timing needs review | Decayed after adaptation |
| **Betting — author metadata not shown (2019), “Efficiency, Profitability, and College Football…”** | *Atlantic Economic Journal* | Y | `[FBS] [pre-2018 data]` | Sep. 2003–Jan. 2016; n NR | Spread | ATS | Interconference efficiency tests | Rejected efficiency for subsets; all-sample rule was not particularly profitable.[^1_3] | Retrospective | Subset multiplicity unclear | Untested post-2018 |
| **Betting — authors not recovered (2019), “Beating the House…”** | arXiv | N | `[FBS] [uncertain]` | Multiple sports including NCAAF; n NR | Betting-market prices | ROI/positive-EV bets | Nonparametric probability model | Claimed above-market returns across several sports; accessible record lacks sufficient FBS audit detail.[^1_70] | NR | High trial/selection uncertainty | Invalid as deployable FBS claim |
| **Betting/HFA — authors not recovered (2022), “How Much of Home Field Advantage Comes from the Fans?”** | *Gaming Research \& Review Journal* | Y | `[FBS]` | NCAA 2007–2020; 2020 included 531 games, 130 empty | Opening and closing spreads | HFA and movement | COVID natural experiment | Estimated 35% of NCAA HFA from spectators; 2020 movement reversed toward visitors.[^1_24] | Quasi-experimental | Scheduling/COVID confounding remains | Holds as mechanism |
| **Review — Vandenbruaene, De Ceuster \& Annaert (2022), “Efficient Spread Betting Markets”** | *Journal of Sports Economics* | Y | `[review]` | Prior literature | Various | Efficiency/profitability | Literature review | Reviews FBS studies including Sinkey–Logan and stresses robustness issues.[^1_54][^1_55] | Review | n/a | Holds |
| **Betting — Arscott (2023), “Market Efficiency and Censoring Bias in College Football Totals Betting”** | *Journal of Sports Economics* | Y | `[FBS]` | See original | Totals | Total result | Censoring-bias/efficiency analysis | Already in hand; not re-summarized | See original | See original | Holds subject to replication |
| **Betting — Kelly \& West, “Bettor Biases and Market Efficiency in the NFL Totals Market”** | Journal article | Y | `[NFL – transfer]` | Already in hand | Totals | Total result | Bias/efficiency | Already in hand; not re-summarized | See original | See original | Untested in FBS |
| **Betting — AABRI NFL preseason totals paper** | AABRI | Unclear | `[NFL – transfer]` | Already in hand | Preseason totals | Total result | Efficiency test | Already in hand; not re-summarized | See original | See original | Untested in FBS |
| **Prediction — Harville (1977), “Use of Linear-Model Methodology to Rate High School or College Football Teams”** | Statistics/OR literature | Y | `[FBS/all college]` | Historical games; n NR | n/a | Margin/rating | Linear model | Foundational score-difference rating framework.[^1_7] | In-sample/application | End-of-season use can leak if backcast | Holds methodologically |
| **Prediction — Massey (1997), “Statistical Models Applied to the Rating of Sports Teams”** | Undergraduate honors project | N | `[FBS]` | 1996; 111 Division I-A teams | n/a | Rating/margin | Least squares | Demonstrated multiple least-squares models on all Division I-A games.[^1_8] | In-sample ratings | High if final ratings predict earlier games | Holds as method |
| **Prediction — Colley (2002), “Colley’s Bias Free College Football Ranking Method”** | Technical monograph | N | `[FBS/all college]` | NR | n/a | Ranking | Linear system based on wins/losses | Transparent schedule-adjusted matrix rating.[^1_9] | Descriptive | Final-season leakage if backcast | Holds for ranking; weak forecast evidence |
| **Prediction — Fair (2002/03), “College Football Rankings and Market Efficiency”** | Cowles discussion paper | N | `[FBS] [pre-2018]` | Seasons/n NR | Final Las Vegas spread | Margin/winner/market efficiency | Optimal rating combination | Combined ratings beat individuals but added no information beyond final spread.[^1_2] | Out-of-sample details require paper | Potential rating-date leakage must be audited | Holds as market-efficiency prior |
| **Prediction — Delen, Cogdell \& Kasap (2012), “Comparative Analysis of Data Mining Methods…”** | *International Journal of Forecasting* | Y | `[FBS bowls] [pre-2018]` | 2002–2010/11; 244 games, 28 features | n/a | Winner and margin | CART, SVM, ANN | CART: 86% ten-fold CV; 82.9% final-season holdout.[^1_13][^1_15] | CV plus holdout | Feature timing must be audited | Holds for bowl winner classification; ATS untested |
| **Prediction — Harville (2014), “Need for More Emphasis on Prediction”** | *The American Statistician* | Y | `[FBS methodology]` | NR | n/a | Margin and prediction | Latent-variable model | Handles overtime and score lumpiness in model-based forecasts.[^1_60] | Model-based; details in paper | Low if forecasts archived prospectively | Holds |
| **Prediction — Saunders (2014), “Predictive Ranking Systems for American College Football”** | Thesis | N | `[FBS] [pre-2018]` | 2012–2013 | n/a | Winner/rating | Three regression systems | Reg-2: 66.2% and 66.5%; Sagarin led 2012 at 73.7%.[^1_17] | Two-season test and CV | Potential same-season/end-date ambiguity | Untested |
| **Prediction/Description — authors not recovered (2024), “Statistical Analysis and Machine Learning in College Football”** | Institutional publication | Unclear | `[FBS] [abstract only]` | 2013–2023 | n/a | Wins/margin | OLS, clustering, random forest | Reported margin RMSE 6.82 and offensive efficiency as important.[^1_16] | Insufficiently documented | Material feature-timing risk | Untested |
| **Prediction — Danoff \& Battiste (2026), “Open-Source College Football Championship Prediction Model”** | Conference proceedings/chapter | Y/unclear | `[FBS] [abstract only]` | CFP seasons; n NR | n/a | Champion/ranking | Quantitative ranking model | Prospectively selected the 2025 champion and ranked runner-up above committee.[^1_71] | One highlighted postseason | Selection and small-n risk | Untested |
| **Description — Caudill \& Mixon (2007), “Stadium Size, Ticket Allotments and HFA”** | *Social Science Journal* | Y | `[FBS] [pre-2018]` | Iron Bowl history; n NR | n/a | Win probability | Rivalry natural setting/regression | Larger relative home attendance and capacity linked to HFA.[^1_22][^1_23] | Case study | Narrow external validity | Holds as mechanism |
| **Description — Adler, Berry \& Doherty (2013), coaching replacement study** | *Social Science Quarterly* | Y | `[FBS] [pre-2018]` | 1997–2010; n NR | n/a | Program performance | Matching | Poor teams gained little; middling teams replacing coaches did worse than controls.[^1_29] | Matched observational | Residual treatment selection | Holds conditionally |
| **Description — Bergman \& Logan (2016), “Effect of Recruit Quality…”** | *Journal of Sports Economics* | Y | `[FBS] [pre-2018]` | 2002–2012; all FBS schools | n/a | Wins/bowl appearance | OLS and school fixed effects | Five-star coefficient fell from 0.437 to 0.306 wins under school FE.[^1_18][^1_19] | Panel/in-sample inference | Outcome-prediction timing manageable | Holds |
| **Description — UND project (2016), “Most Important Statistics in Football”** | Student research | N | `[FBS] [descriptive]` | 2016; 857 games | n/a | Winner/descriptive | Game-level comparisons | YPP and success-rate winners each won about 85%.[^1_25] | In-sample descriptive | Same-game variables create total leakage for pregame use | Invalid as direct pregame claim |
| **Description — Mankin \& Rivas et al. (c. 2020/21), recruiting ratings study** | AABRI/academic paper | Unclear | `[FBS]` | 17 recruiting years, 14 performance years | n/a | Final Sagarin rating | Longitudinal regression | Recruiting explained up to 36% of Sagarin variation.[^1_21] | Historical panel | Program-quality confounding | Holds directionally |
| **Description — Singleton et al. conference study (2021), team-performance models** | NCUR proceedings | N/conference | `[FBS major conferences]` | 2006–2018 | n/a | Standardized Sagarin rating | Multiple regression/selection | Prior Sagarin strongest; returning QB/starters and recruiting also entered models.[^1_20] | Historical model comparison | Forward-selection optimism | Untested |
| **Description — 2026 “Offensive Efficiency, Defensive Containment and Winning…”** | Zenodo | N | `[college football] [abstract only]` | Multiple seasons; n NR | n/a | Win percentage | Correlation, OLS, ANOVA, factor analysis | Offensive efficiency reported as strongest component, with no single sufficient statistic.[^1_72] | In-sample descriptive | High for pregame use without lags | Untested |
| **Policy — Groza (2010), “NCAA Conference Realignment and Football Game Day Attendance”** | *Managerial and Decision Economics* | Y | `[FBS] [pre-2018]` | Realignment around 2004–05 | n/a | Attendance | Panel/regression | Conference movers increased attendance after competition-quality controls.[^1_35] | Historical panel | n/a for betting | Holds for attendance |
| **Policy — Crow (2010), BCS competitive-balance study** | Journal article | Y | `[FBS] [pre-2018]` | BCS era; n NR | n/a | Competitive balance | Before/after balance metrics | Within-season balance improved in six BCS conferences; between-season improvement in only three.[^1_73][^1_74] | Before/after | Other era trends | Untested under CFP |
| **Policy — Kotchen \& Potoski (2011), coaches-poll bias study** | NBER working paper | N | `[FBS] [pre-2018]` | 2005–2010 coaches’ ballots | n/a | Rankings | Ballot-versus-computer comparisons | Bias up to about two places for own team, one for conference teams, half for defeated teams.[^1_40] | Historical panel | Rankings endogenous | Holds as poll-bias evidence |
| **Policy — Hoffer \& Pincin (2015), “Effects of Conference Realignment…”** | *Applied Economics Letters* | Y | `[Division I/FBS] [pre-2018]` | 2006–2011; 227 public schools | n/a | Revenue/expenditure | Panel analysis | AQ move: +\$12.15m revenue and +\$10.12m expense.[^1_36][^1_37] | Panel | n/a for game prediction | Holds financially |
| **Policy — authors not recovered (2018), “Impact of Competitive Markets on Recruiting…”** | Management/sport research | Y/unclear | `[FBS] [pre-2018]` | 2010–2013 realignment era | n/a | Recruiting quality | Before/after comparisons | Average star rating rose 2.86 to 2.92; individual rating change nonsignificant.[^1_38] | Before/after | Selection into conferences | Untested |
| **Policy — authors not recovered (2024), “Impact of the BCS on Competitive Balance…”** | SSRN/working paper | N | `[FBS]` | 2005–2022 | n/a | Competitive balance | Difference-in-differences | CFP transition reduced balance; reported 65.75% Power Five HHI increase.[^1_39][^1_41] | DiD | Parallel-trend and concurrent-shock risk | Untested |
| **Policy — Li \& Derdenger (2025), NIL competition study** | Accepted at *Management Science* | Y | `[FBS]` | Pre/post 2021; n NR | Betting spreads | Recruiting, spread, margin, upset | Panel/econometric analysis | NIL associated with about 1.2-point smaller spreads after controls.[^1_42] | Pre/post with controls | Portal and era confounding | Untested/contested |
| **Policy — Brown (2025), “Buying Wins?”** | CMC senior thesis | N | `[FBS]` | 2021–2024; 132 FBS programs/321 football observations stated in text | n/a | Win percentage | OLS with NIL proxies | NIL class-value coefficient insignificant, p=0.661; model $R^2=0.2255$.[^1_43][^1_44] | Cross-sectional/panel OLS | Proxy measurement error | Contradicts simple NIL-spending effect |
| **Policy — authors not recovered (2025), “Impact of NIL Contracts on NCAA Football Recruiting Outcomes”** | *Applied Economics* | Y | `[FBS]` | Post-NIL recruiting; n NR | n/a | Recruit choices | Multistage choice model | Prior school NIL value predicted choices; counterfactual favored elite programs.[^1_45] | Structural/counterfactual | NIL-value measurement risk | Contradicts dispersion interpretation |
| **Policy — authors not recovered (2025), “Financial Contracting and Allocation of Skill and Talent”** | Working paper | N | `[mechanism only]` | Theoretical/calibrated | n/a | Competitive balance | Dynamic matching model | NIL can improve balance under some parameters; portal can reverse it.[^1_46] | Theoretical | n/a | Untested empirically |
| **Data — Gilani, Easwaran, Lee \& Hess (2026), `cfbfastR`** | CRAN package | N/software | `[practitioner/data]` | Historical play-by-play | Includes downstream line/data access | EPA/WPA/data access | Package/data pipeline | Public R interface and enriched analysis-ready data.[^1_32][^1_33] | Software tests, not forecast test | Derived-metric methodology must be versioned | Holds as infrastructure |
| **Data — CollegeFootballData API** | Public API | N/software | `[practitioner/data]` | Historical and current seasons | Historical provider lines | Data provision | REST/GraphQL/API | Games, PBP, box scores, weather, recruiting, lines, advanced metrics.[^1_48][^1_31][^1_49] | n/a | Revision/timestamp risk | Holds as infrastructure |
| **Methods — Glickman \& Stern, NFL state-space score model** | *JASA* | Y | `[NFL – transfer]` | Already in hand | n/a | Scores/margins | State-space model | Already in hand; not re-summarized | See original | See original | Holds as transfer method |
| **Methods — Romer (2002/06), “It’s Fourth Down…”** | NBER/*Journal of Political Economy* lineage | Y | `[NFL – transfer]` | 1998–2000 NFL | n/a | Fourth-down decisions | Dynamic programming | Found large, significant departures from optimal go/kick choices.[^1_75][^1_76] | Historical structural analysis | NFL transfer only | Untested in FBS |
| **Methods — Stekler, Sendor \& Verlander (2010), “Issues in Sports Forecasting”** | *International Journal of Forecasting* | Y | `[review]` | Prior sports literature | Various | Forecast evaluation | Review | Separates sports forecasting from market-efficiency research.[^1_56][^1_58] | Review | n/a | Holds |
| **Methods — Wheatcroft (2023 publication; 2019 preprint), probabilistic football forecasts** | *JQAS* | Y | `[other sport – transfer]` | Simulations | Odds/probabilities conceptually | Probability forecasts | Scoring-rule comparison | Ignorance score outperformed Brier and RPS in simulations.[^1_50][^1_52] | Simulation | Transfer from soccer | Holds methodologically |
| **Methods — Bunker/Thabtah et al., team-sport ML review** | *Journal of AI Research* | Y | `[review]` | 1996–2019 studies | Various | Match prediction | Systematic/narrative review | Feature selection often more important than algorithm complexity; datasets impede comparisons.[^1_15] | Review | n/a | Holds |


______________________________________________________________________

## Coverage log

| Sub-question | Source classes searched | Representative queries | Usable sources found | Missing or inaccessible |
| :-- | :-- | :-- | --: | :-- |
| 1. Betting markets | Journal indexes, publisher pages, RePEc/IDEAS, SSRN, Semantic Scholar, arXiv, conference records, practitioner archives | “college football point spread market efficiency”; “NCAA football betting market”; “college football totals”; “home underdog college football”; “sportsbook behavior NCAA football” | 18 direct/indexed items plus transfer studies | Several full texts paywalled; exact seasons, books, open/close definitions, and rule counts unavailable for some papers. No first-half or team-total study located. |
| 2. Game prediction | Statistics journals, IJF, theses, arXiv, university repositories, rating-author sites, Prediction Tracker discussions | “college football rating system prediction accuracy”; “predicting college football games regression”; “machine learning college football prediction”; author searches for Harville, Massey, Colley, Sagarin | 12 direct works/systems | Few studies report ATS probability, CLV, or de-vigged market scoring. Some theses lacked complete metadata. |
| 3. Descriptive analytics | Sports-economics journals, JSA, university repositories, conference proceedings, practitioner analytics | “recruiting rankings team performance college football”; “home field advantage college football”; “turnover margin college football”; “college football coaching change performance” | 14 direct or closely related items | No fully documented peer-reviewed FBS EPA/WP validation found. Weather, travel, returning production, and fourth-down work was mostly practitioner or transfer evidence. |
| 4. Structure and policy | RePEc, SSRN, Management Science working papers, Applied Economics, university repositories, NCAA/news archives | “college football clock rule change scoring”; “conference realignment college football performance”; “NIL competitive balance college football”; “transfer portal team performance” | 13 direct items | Portal-specific game-margin studies and modern overtime/betting studies not found. Some NIL papers were working papers or theses. |
| 5. Data and methods | CRAN/package documentation, GitHub, CFBD documentation, forecasting journals, arXiv | “cfbfastR citation”; “CollegeFootballData API”; “evaluating probabilistic football forecasts”; “sports betting backtest methodology” | 9 core infrastructure/methods sources | No academic audit of CFBD completeness, revision history, or historical-line timestamps located. |
| 6. Reviews | *Journal of Sports Economics*, *International Journal of Forecasting*, ML-review journals, arXiv | “sports betting market efficiency literature review college football”; “football forecasting literature review”; “team sport machine learning review” | 4 substantive reviews | Most ML-betting reviews focus on soccer or basketball rather than FBS. |
| 7. Community | Author pages, Google Scholar-indexed records, RePEc, NBER, journal archives, practitioner sites | Searches for Paul, Weinbach, Humphreys, Sauer, Levitt, Harville, Stern, Glickman, Colley, Massey, Moskowitz, Borghesi | Verified direct FBS work for Paul, Weinbach, Harville, Massey, Colley; transfer work for Levitt, Borghesi, Glickman/Stern | No direct FBS study verified for Moskowitz, Levitt, Borghesi, or Glickman/Stern. Conference archives yielded limited accessible FBS papers. |
| Cross-cutting | MIT Sloan, NESSIS, Carnegie Mellon sports-analytics materials; ProQuest and university repositories | Variants of all supplied queries plus author/title searches | Several theses and proceedings | ProQuest records were partially inaccessible; no definitive exhaustive export was available. Some conference websites did not expose historical full-text search. |

## Cutoff and limitations

Research cutoff: **2026-09-30**.

The most important limitation is full-text access. Several publisher pages exposed only abstracts or citation metadata, preventing reliable extraction of exact game counts, sportsbook sources, opening-versus-closing definitions, statistical intervals, number of attempted rules, and feature-timing details. Those fields are marked NR or Untested rather than inferred.

The master table is a breadth-first map of verified and indexed material found in the searched sources, not a claim that no unindexed dissertation, conference manuscript, or proprietary report exists. Where the search did not locate a relevant paper, the wording is deliberately limited to **“No published FBS study found in searched sources.”**

<span style="display:none">[^1_100][^1_101][^1_102][^1_103][^1_104][^1_105][^1_106][^1_107][^1_108][^1_109][^1_110][^1_111][^1_112][^1_113][^1_114][^1_115][^1_116][^1_117][^1_118][^1_119][^1_120][^1_121][^1_122][^1_123][^1_124][^1_125][^1_126][^1_127][^1_128][^1_129][^1_130][^1_131][^1_132][^1_133][^1_134][^1_135][^1_136][^1_137][^1_138][^1_139][^1_140][^1_141][^1_142][^1_143][^1_144][^1_145][^1_146][^1_147][^1_148][^1_149][^1_150][^1_151][^1_152][^1_153][^1_154][^1_155][^1_156][^1_157][^1_158][^1_159][^1_160][^1_161][^1_162][^1_163][^1_164][^1_165][^1_166][^1_167][^1_168][^1_169][^1_170][^1_171][^1_172][^1_173][^1_174][^1_175][^1_176][^1_177][^1_178][^1_179][^1_180][^1_181][^1_182][^1_183][^1_184][^1_185][^1_186][^1_187][^1_188][^1_189][^1_190][^1_191][^1_192][^1_193][^1_194][^1_195][^1_196][^1_197][^1_198][^1_199][^1_200][^1_201][^1_202][^1_203][^1_204][^1_205][^1_206][^1_207][^1_208][^1_209][^1_210][^1_211][^1_212][^1_213][^1_214][^1_215][^1_216][^1_217][^1_218][^1_219][^1_220][^1_221][^1_222][^1_223][^1_224][^1_225][^1_226][^1_227][^1_228][^1_229][^1_230][^1_231][^1_232][^1_233][^1_234][^1_235][^1_236][^1_237][^1_238][^1_239][^1_240][^1_241][^1_242][^1_243][^1_244][^1_245][^1_246][^1_247][^1_248][^1_249][^1_250][^1_251][^1_252][^1_253][^1_254][^1_255][^1_256][^1_257][^1_258][^1_259][^1_260][^1_261][^1_262][^1_263][^1_264][^1_265][^1_266][^1_267][^1_268][^1_269][^1_270][^1_271][^1_272][^1_273][^1_274][^1_275][^1_276][^1_277][^1_278][^1_279][^1_280][^1_281][^1_282][^1_283][^1_284][^1_285][^1_286][^1_287][^1_288][^1_289][^1_290][^1_291][^1_292][^1_293][^1_294][^1_295][^1_296][^1_297][^1_298][^1_299][^1_300][^1_301][^1_302][^1_303][^1_304][^1_305][^1_306][^1_307][^1_308][^1_309][^1_310][^1_311][^1_312][^1_313][^1_314][^1_315][^1_316][^1_317][^1_318][^1_319][^1_320][^1_321][^1_322][^1_323][^1_324][^1_325][^1_326][^1_327][^1_328][^1_329][^1_330][^1_331][^1_332][^1_333][^1_334][^1_335][^1_336][^1_337][^1_338][^1_339][^1_340][^1_341][^1_342][^1_343][^1_344][^1_345][^1_346][^1_347][^1_348][^1_349][^1_350][^1_351][^1_352][^1_353][^1_354][^1_355][^1_356][^1_357][^1_358][^1_359][^1_360][^1_361][^1_362][^1_363][^1_364][^1_365][^1_366][^1_367][^1_368][^1_369][^1_370][^1_371][^1_372][^1_373][^1_374][^1_375][^1_376][^1_377][^1_378][^1_379][^1_380][^1_381][^1_382][^1_383][^1_384][^1_385][^1_386][^1_387][^1_388][^1_389][^1_390][^1_391][^1_392][^1_393][^1_394][^1_395][^1_396][^1_397][^1_398][^1_399][^1_400][^1_401][^1_402][^1_403][^1_404][^1_405][^1_406][^1_407][^1_408][^1_409][^1_410][^1_411][^1_412][^1_413][^1_414][^1_415][^1_416][^1_417][^1_418][^1_419][^1_420][^1_421][^1_422][^1_423][^1_424][^1_425][^1_426][^1_427][^1_428][^1_429][^1_430][^1_431][^1_432][^1_433][^1_434][^1_435][^1_436][^1_437][^1_438][^1_439][^1_440][^1_441][^1_442][^1_443][^1_444][^1_445][^1_446][^1_447][^1_448][^1_449][^1_450][^1_451][^1_452][^1_453][^1_454][^1_455][^1_456][^1_457][^1_458][^1_459][^1_460][^1_461][^1_462][^1_463][^1_464][^1_465][^1_466][^1_467][^1_468][^1_469][^1_470][^1_471][^1_472][^1_473][^1_474][^1_475][^1_476][^1_477][^1_478][^1_479][^1_480][^1_481][^1_482][^1_483][^1_484][^1_485][^1_486][^1_487][^1_488][^1_489][^1_490][^1_491][^1_492][^1_493][^1_494][^1_495][^1_496][^1_77][^1_78][^1_79][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://ideas.repec.org/a/pal/easeco/v40y2014i4p583-603.html

[^1_2]: https://cowles.yale.edu/node/140186

[^1_3]: https://ideas.repec.org/a/kap/atlecj/v47y2019i2d10.1007_s11293-019-09616-7.html

[^1_4]: https://scispace.com/papers/the-large-firm-effect-bettor-preferences-and-market-prices-4782qcjip5

[^1_5]: https://ideas.repec.org/a/gam/jijfss/v2y2014i2p179-192d35174.html

[^1_6]: https://fivethirtyeight.com/features/losing-money-betting-on-college-football-this-year-youre-not-alone/

[^1_7]: https://alpha.rankless.org/authors/david-a-harville

[^1_8]: https://masseyratings.com/theory/massey97.pdf

[^1_9]: https://search.r-project.org/CRAN/refmans/comperank/html/colley.html

[^1_10]: http://sagarin.com/sports/cfsend.htm

[^1_11]: https://thepowerrank.com/guide-cfb-rankings/

[^1_12]: https://www.collegefootballpoll.com/news/congrove-outperforms-bcs-computer-component-rankers/

[^1_13]: https://ar5iv.labs.arxiv.org/html/1912.11762

[^1_14]: https://www.sciencedirect.com/science/article/abs/pii/S0169207011000914

[^1_15]: https://dl.acm.org/doi/pdf/10.1613/jair.1.13509

[^1_16]: https://nchr.elsevierpure.com/en/publications/statistical-analysis-and-machine-learning-in-college-football-ins/

[^1_17]: https://digitalcommons.ncf.edu/cgi/viewcontent.cgi?article=5840\&context=theses_etds

[^1_18]: https://www.asc.ohio-state.edu/logan.155/pdf/Bergmen_Logan.pdf

[^1_19]: https://journals.sagepub.com/doi/10.1177/1527002514538266

[^1_20]: https://libjournals.unca.edu/ncur/wp-content/uploads/2021/02/2913-Singleton-Sydney-FINAL.pdf

[^1_21]: http://aabri.com/manuscripts/182841.pdf

[^1_22]: https://aquila.usm.edu/fac_pubs/1788/

[^1_23]: https://www.sciencedirect.com/science/article/abs/pii/S0362331907001176

[^1_24]: https://oasis.library.unlv.edu/cgi/viewcontent.cgi?article=1468\&context=grrj

[^1_25]: https://commons.und.edu/cgi/viewcontent.cgi?article=1004\&context=es-showcase

[^1_26]: https://www.espn.com/college-football/story/\_/id/24142400/coaches-their-everlasting-quest-coach-turnovers

[^1_27]: https://www.espn.com.au/college-football/story/\_/id/48288665/college-football-2026-turnovers-lucky-bounces

[^1_28]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5969004/

[^1_29]: https://statmodeling.stat.columbia.edu/2013/04/15/how-effective-are-football/

[^1_30]: https://core.ac.uk/download/pdf/169420034.pdf

[^1_31]: https://collegefootballdata.com/api-tiers

[^1_32]: https://github.com/sportsdataverse/cfbfastR-cfb-data

[^1_33]: https://cfbfastr.sportsdataverse.org/authors.html

[^1_34]: https://www.latimes.com/archives/la-xpm-2006-dec-29-sp-rules29-story.html

[^1_35]: https://ideas.repec.org/a/wly/mgtdec/v31y2010i8p517-529.html

[^1_36]: https://ideas.repec.org/a/taf/apeclt/v22y2015i15p1209-1223.html

[^1_37]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2578333

[^1_38]: https://reference-global.com/download/article/10.1515/mosr-2018-0002.pdf

[^1_39]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4927133

[^1_40]: https://yaledailynews.com/blog/2011/12/07/researchers-tackle-allegations-of-bias-in-college-football-ranking/

[^1_41]: https://jewlscholar.mtsu.edu/server/api/core/bitstreams/a86eb3a1-7306-4de3-bded-22e4d810b5aa/content

[^1_42]: https://tepperspectives.cmu.edu/wp-content/uploads/2025/08/Does-Personalized-Pricing-Increase-Competition-Evidence-from-NIL-in-College-Football-compressed.pdf

[^1_43]: https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=5171\&context=cmc_theses

[^1_44]: https://scholarship.claremont.edu/cmc_theses/3999/

[^1_45]: https://www.studocu.com/en-us/document/university-of-mississippi/advanced-composition/the-impact-of-nil-contracts-on-ncaa-football-recruiting-outcomes-eco-2025/140632593

[^1_46]: https://faculty.marshall.usc.edu/Gerard-Hoberg/FOM/papers2025/paper11.pdf

[^1_47]: https://api.collegefootballdata.com/api/stats

[^1_48]: https://api.collegefootballdata.com/api/games

[^1_49]: https://api.collegefootballdata.com/api/betting

[^1_50]: https://arxiv.org/html/1908.08980v1

[^1_51]: https://axi.lims.ac.uk/paper/1908.08980

[^1_52]: https://colab.ws/articles/10.1515/jqas-2019-0089

[^1_53]: https://www.si.com/college/2013/08/26/verbatim-jeff-sagarin

[^1_54]: https://journals.sagepub.com/doi/10.1177/15270025211071042

[^1_55]: https://repository.uantwerpen.be/docman/irua/f3c2d2/188493.pdf

[^1_56]: https://cer.columbian.gwu.edu/working-papers

[^1_57]: https://www.grafiati.com/en/literature-selections/forecasting-in-sports/journal/

[^1_58]: https://scispace.com/journals/international-journal-of-forecasting-3m3vf93y/2010

[^1_59]: https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1883327/full

[^1_60]: https://davidharville.com/collegefootballratingspredictions/methodology/

[^1_61]: https://www.nber.org/papers/w9422

[^1_62]: https://ideas.repec.org/a/taf/applec/v39y2007i15p1889-1903.html

[^1_63]: https://www.academia.edu/69658223/Integrity_Fees_in_Sports_Betting_Markets

[^1_64]: https://bleacherreport.com/articles/1444427-why-jeff-sagarin-doesnt-deserve-to-have-a-hand-in-the-bcs

[^1_65]: https://wsb.wharton.upenn.edu/who-has-the-biggest-home-field-advantage-its-not-who-you-think/

[^1_66]: https://athlonsports.com/college-football/everything-you-need-know-about-college-football-analytics

[^1_67]: https://overunderweather.com/research

[^1_68]: https://acawiki.org/Why_are_Gambling_Markets_Organised_So_Differently_from_Financial_Markets%3F

[^1_69]: https://www.semanticscholar.org/paper/ae2a6650d230470b8d273ce614f0b1438a7a1238

[^1_70]: https://ideas.repec.org/p/arx/papers/1910.08858.html

[^1_71]: https://link.springer.com/chapter/10.1007/978-3-032-27272-0_27?error=cookies_not_supported\&code=60f48540-e4e5-4ec3-8182-742ab4f9b0e0

[^1_72]: https://zenodo.org/records/21680897

[^1_73]: https://www.academia.edu/62961234/A_Comparison_of_Potential_Playoff_Systems_for_NCAA_I_A_Football?f_ri=122286

[^1_74]: https://www.newswise.com/articles/bowl-championship-series-has-mixed-effect-on-competitive-balance

[^1_75]: https://www.nber.org/system/files/working_papers/w9024/w9024.pdf

[^1_76]: https://www.nber.org/papers/w9024

[^1_77]: cfb-warehouse-catalog.html

[^1_78]: fbs-totals-frontier-models.md

[^1_79]: FBS College Football Pregame Totals Betting System Research Report.md

[^1_80]: https://ideas.repec.org/a/taf/intgms/v9y2009i1p55-66.html

[^1_81]: https://www.abacademies.org/articles/examining-ncaanfl-market-efficiency.pdf

[^1_82]: https://cowles.yale.edu/sites/default/files/2022-08/d1381.pdf

[^1_83]: https://ideas.repec.org/a/spr/jecfin/v29y2005i3p409-415.html

[^1_84]: https://www.ubplj.org/index.php/jpm/article/view/888

[^1_85]: http://www.accessecon.com/Pubs/EB/2022/Volume42/EB-22-V42-I3-P139.pdf

[^1_86]: https://www.tandfonline.com/doi/full/10.1080/13504851.2020.1795063

[^1_87]: https://ideas.repec.org/a/sae/jospec/v22y2021i3p251-273.html

[^1_88]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4197428

[^1_89]: https://honors.libraries.psu.edu/catalog/10296odm5057

[^1_90]: https://ideas.repec.org/a/buc/jpredm/v8y2014i2p29-42.html

[^1_91]: https://ideas.repec.org/a/spr/jecfin/v43y2019i4d10.1007_s12197-019-09479-3.html

[^1_92]: https://fae.uprrp.edu/wp-content/uploads/sites/13/2018/02/JimmyTorrezbonus2010.pdf

[^1_93]: https://www.aeaweb.org/conference/2010/retrieve.php?pdfid=406

[^1_94]: https://ideas.repec.org/a/sae/jospec/v24y2023i5p664-689.html

[^1_95]: https://journals.sagepub.com/doi/abs/10.1177/22150218251365223

[^1_96]: https://journals.sagepub.com/doi/10.3233/JSA-190314

[^1_97]: https://content.iospress.com/download/journal-of-sports-analytics/jsa190314?id=journal-of-sports-analytics/jsa190314

[^1_98]: https://journals.sagepub.com/doi/full/10.1177/22150218251365223

[^1_99]: https://cs.brown.edu/media/filer_public/2b/77/2b7792b0-3559-44fa-b7d9-f7572e1c3db5/chungjohn.pdf

[^1_100]: https://pure.ulster.ac.uk/ws/portalfiles/portal/213544031/2024156785.pdf

[^1_101]: https://eprints.soton.ac.uk/446078/1/NFL_ML_IJCSS.pdf

[^1_102]: https://ideas.repec.org/a/eee/intfor/v28y2012i2p543-552.html

[^1_103]: https://www.stat.berkeley.edu/~aldous/157/Papers/dubbs.pdf

[^1_104]: https://discovery.researcher.life/article/a-predictive-metamodel-for-college-football/2f60b334c4fa3bb8a022551b630bda0f

[^1_105]: https://www.math.vu.nl/~sbhulai/papers/paper-bosch.pdf

[^1_106]: http://snap.stanford.edu/class/cs224w-2015/projects_2015/A_Network-Based_Approach_to_Ranking_College_Football_Teams.pdf

[^1_107]: https://www.smcvt.edu/wp-content/uploads/2021/08/SpanningTrees3rdAnnualConf.pdf

[^1_108]: https://cs229.stanford.edu/proj2010/LiuLai-BeatingTheNCAAFootballPointSpread.pdf

[^1_109]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=8e1c43b5408c932e48ec6506f699f35c1999ca60

[^1_110]: https://arxiv.org/html/2207.13747v1

[^1_111]: https://www.espn.com/college-football/recruiting/story/\_/id/48503376/2027-college-football-recruiting-class-rankings-top-teams-schools

[^1_112]: https://digitalcommons.molloy.edu/cgi/viewcontent.cgi?article=1068\&context=bus_fac

[^1_113]: http://www.aabri.com/manuscripts/182841.pdf

[^1_114]: https://www.degruyter.com/document/doi/10.1515/jqas-2024-0016/html

[^1_115]: https://public.websites.umich.edu/~bwest/inpress_063008.pdf

[^1_116]: https://ideas.repec.org/a/wly/soecon/v90y2024i4p1060-1098.html

[^1_117]: https://bluechipanalytics.com/college-football/methodology/

[^1_118]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7861217/

[^1_119]: https://www.sciencedirect.com/science/article/pii/S1877050914011181/pdf

[^1_120]: https://wsb.wharton.upenn.edu/wp-content/uploads/2022/09/2022_Football_Kessman_Development.pdf

[^1_121]: https://libres.uncg.edu/ir/asu/f/Singleton_Sydney_2019_Thesis.pdf

[^1_122]: https://athleticdirectoru.com/articles/do-football-recruiting-ratings-matter/

[^1_123]: https://ar5iv.labs.arxiv.org/html/2212.08116

[^1_124]: https://ideas.repec.org/a/taf/apeclt/v31y2024i8p779-782.html

[^1_125]: https://www.tandfonline.com/doi/abs/10.1080/00031305.2025.2475801

[^1_126]: https://ruscio.pages.tcnj.edu/files/2021/01/Fourth-Down-Decisions.pdf

[^1_127]: https://statsbylopez.com/wp-content/uploads/2018/01/quantifying-causal-effects.pdf

[^1_128]: https://wsb.wharton.upenn.edu/fourth-down-conversion-frequencies-are-higher-than-you-think/

[^1_129]: https://arxiv.org/html/2311.03490v4

[^1_130]: https://forum.huskermax.com/threads/turnover-margin-importance.147628/

[^1_131]: https://mtsunews.com/2020/01/21/roach-on-the-record-jan2020/

[^1_132]: https://thesportjournal.org/article/predictive-modeling-of-4th-down-conversion-in-power-5-conferences-football-data-analytics/

[^1_133]: https://mtsunews.com/roach-on-the-record-jan2020/

[^1_134]: https://www.charlotteobserver.com/sports/college/football/article9160847.html

[^1_135]: https://digitalcommons.du.edu/duurj/vol2/iss1/6/

[^1_136]: https://pdfs.semanticscholar.org/1785/929d0ef6e068bcb515b54efec60470080aac.pdf

[^1_137]: https://pure.psu.edu/en/publications/decision-making-on-the-hot-seat-and-the-short-list-evidence-from-

[^1_138]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3114242

[^1_139]: https://thesportjournal.org/article/competitive-balance-and-conference-realignment-the-case-of-big-12-football/

[^1_140]: https://thesportjournal.org/article/big-12-football-competitive-balance-before-and-after-realignment/

[^1_141]: https://thesportjournal.org/article/structural-competitive-inequality-in-fbs-football-governance-finance-and-market-forces/

[^1_142]: https://thesportjournal.org/article/author/administrator/page/63/

[^1_143]: https://business-news.ucdenver.edu/2017/10/02/economics-behind-college-football-conference-realignment/

[^1_144]: https://pdfs.semanticscholar.org/e8dd/dfe10a6860aca703a089f64648df476b258a.pdf

[^1_145]: https://oaks.kent.edu/\_flysystem/ojs/journals/4/articles/137/submission/137-37-561-1-2-20200103.pdf

[^1_146]: https://pages.charlotte.edu/wp-content/uploads/sites/866/2014/11/UOH12.pdf

[^1_147]: https://www.econstor.eu/bitstream/10419/103573/1/789994895.pdf

[^1_148]: https://trace.tennessee.edu/cgi/viewcontent.cgi?article=1398\&context=jasm

[^1_149]: https://www.semanticscholar.org/paper/Competitive-Balance-and-Conference-Realignment-in-Rhoads/b15e454527cd61aee3ca1ccbed4c0942353ca35c

[^1_150]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=2b0749292950f1e98a63a9d912f4d3400bde5afc

[^1_151]: https://soar.wichita.edu/bitstreams/bdc82bb1-598c-469b-a662-5f85a44882f2/download

[^1_152]: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00061/pdf

[^1_153]: https://ideas.repec.org/a/inm/ormnsc/v72y2026i5p4247-4281.html

[^1_154]: https://etotty.github.io/assets/pdf/Totty26_CompetitiveBalance.pdf

[^1_155]: https://journals.ku.edu/jis/article/download/24024/22530/99892

[^1_156]: https://static1.squarespace.com/static/5de5182fe743cb648d87d098/t/67db77e9f2fe023fef8101fc/1742436329500/Pifer1_CSRI2025.pdf

[^1_157]: https://www.tandfonline.com/doi/full/10.1080/00036846.2024.2331425

[^1_158]: https://www.tandfonline.com/doi/abs/10.1080/00036846.2024.2331425

[^1_159]: https://www.ebsco.com/articles/sports-and-leisure/dcd76bc1-d57f-5ec9-b54f-d88aa14178a9/show-me-the-money-the-immediate-impact-of-name-image-and-likeness-on-college-football-recruiting

[^1_160]: https://news.uoregon.edu/content/ncaa-football-transfer-portal-shows-mixed-results-teams

[^1_161]: https://phys.org/news/2025-09-image-policies-boost-college-football.pdf

[^1_162]: https://blogs.iu.edu/iuindysii/2024/05/15/ncaa-transfer-portal-analysis/

[^1_163]: https://www.myweb.ttu.edu/jkemper/research.html

[^1_164]: https://sports.yahoo.com/articles/transfer-portal-nil-changing-college-150000167.html

[^1_165]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4722358

[^1_166]: https://jhss.scholasticahq.com/article/168462.pdf

[^1_167]: https://cran.csail.mit.edu/web/packages/cfbfastR/index.html

[^1_168]: https://github.com/sportsdataverse/cfbfastR

[^1_169]: https://api.collegefootballdata.com/getting-started

[^1_170]: https://sportsdataverse.r-universe.dev/cfbfastR

[^1_171]: https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-iii.html

[^1_172]: https://www.stat.cmu.edu/cmsac/conference/2021/assets/pdf/SaiemGilani.pdf

[^1_173]: https://arxiv.org/html/2506.03057v1

[^1_174]: https://cfbfastr.sportsdataverse.org/articles/intro.html

[^1_175]: https://cfbfastr.sportsdataverse.org/reference/index.html

[^1_176]: https://rdrr.io/cran/cfbfastR/man/cfbfastR-package.html

[^1_177]: https://github.com/sportsdataverse

[^1_178]: https://www.rdocumentation.org/packages/cfbfastR/versions/3.0.0/topics/cfbd_pbp_data

[^1_179]: https://cfbfastr.sportsdataverse.org/

[^1_180]: https://rdrr.io/cran/cfbfastR/man/

[^1_181]: https://www.degruyterbrill.com/document/doi/10.2202/1559-0410.1172/html

[^1_182]: https://ww3.math.ucla.edu/camreport/cam13-08.pdf

[^1_183]: https://ideas.repec.org/a/bpj/jqsprt/v5y2009i2n3.html

[^1_184]: https://ideas.repec.org/a/inm/orinte/v35y2005i6p483-496.html

[^1_185]: https://cs229.stanford.edu/proj2005/Wisne-FootballRankingSystem.pdf

[^1_186]: http://tbeck.freeshell.org/fb/lit.txt

[^1_187]: https://ideas.repec.org/a/sae/jospec/v8y2007i1p3-18.html

[^1_188]: https://ww2.amstat.org/mam/2010/essays/PasteurRetrodictive.pdf

[^1_189]: https://ideas.repec.org/p/ysm/wpaper/amz2377.html

[^1_190]: https://dl.acm.org/doi/10.1287/inte.25.4.44

[^1_191]: https://digitalcommons.unf.edu/cgi/viewcontent.cgi?article=1000\&context=bmgt_facpub

[^1_192]: https://ideas.repec.org/a/bpj/jqsprt/v9y2013i2p187-202n7.html

[^1_193]: https://optimization-online.org/wp-content/uploads/2011/10/3199.pdf

[^1_194]: https://www.dimers.com/cfb/predictions

[^1_195]: https://ideas.repec.org/a/sae/jospec/v23y2022i7p907-949.html

[^1_196]: https://brendanwhit.github.io/ds1-final-project/lit-review/boulier2003.pdf

[^1_197]: https://journals.sagepub.com/doi/10.1177/1527002520975837?icid=int.sj-full-text.similar-articles.5

[^1_198]: https://articlegateway.com/index.php/AJM/article/download/6051/5729/10497

[^1_199]: https://ditraglia.com/erm/Fair-Oster-2007.pdf

[^1_200]: https://www.ubplj.org/index.php/jpm/article/view/598

[^1_201]: https://cfbreports.com/

[^1_202]: https://ideas.repec.org/a/spr/jecfin/v42y2018i4d10.1007_s12197-018-9431-4.html

[^1_203]: https://sports.yahoo.com/articles/reviewing-big-ten-preseason-predictions-183035252.html

[^1_204]: https://www.semanticscholar.org/paper/The-Economics-of-Wagering-Markets-Sauer/4a9d5e932571954853c65f49b234d826eb3e15cb

[^1_205]: https://journals.sagepub.com/doi/10.1177/1527002520975837?int.sj-abstract.similar-articles.6=

[^1_206]: https://www.semanticscholar.org/paper/The-degree-of-inefficiencyin-the-football-betting-Golec-Tamarkin/9ddf1cbaf31d1a44e1ce134c91db8a114a08267e

[^1_207]: https://www.sciencedirect.com/science/article/abs/pii/0304405X9190034H

[^1_208]: https://ideas.repec.org/a/eee/jfinec/v30y1991i2p311-323.html

[^1_209]: https://blogs.colgate.edu/economics/files/2013/05/Xu_Econ490_Thesis.pdf

[^1_210]: https://www2.gwu.edu/~forcpgm/2007-001.pdf

[^1_211]: https://www.redalyc.org/journal/1551/155139753005/html/

[^1_212]: https://scholar.google.com/citations?user=RaMBq34AAAAJ\&hl=en

[^1_213]: https://creativematter.skidmore.edu/cgi/viewcontent.cgi?article=1026\&context=econ_studt_schol

[^1_214]: https://helda.helsinki.fi/server/api/core/bitstreams/db1e1612-b57e-4d2b-84d2-4c2c68962e29/content

[^1_215]: https://researchrepository.wvu.edu/cgi/viewcontent.cgi?article=1080\&context=econ_working-papers

[^1_216]: https://wp.hse.ru/data/2019/06/26/1490722922/216EC2019.pdf

[^1_217]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=429f269b82e98af374c08d7c080d4e4a10a52255

[^1_218]: https://www.academia.edu/88675517/Efficient_Spread_Betting_Markets_A_Literature_Review?uc-sb-sw=64896858

[^1_219]: https://falk.syracuse.edu/news/betting-and-college-football-viewership/

[^1_220]: https://sports.yahoo.com/articles/syracuse-university-researchers-strong-between-163800465.html

[^1_221]: https://www.ubplj.org/index.php/jpm/article/view/2646

[^1_222]: https://econpapers.repec.org/RAS/pwe198.htm

[^1_223]: https://scholar.google.com/citations?user=oUxMUggAAAAJ\&hl=en

[^1_224]: https://www.ubplj.org/index.php/jpm/article/view/460

[^1_225]: https://link.springer.com/article/10.1007/bf02827221

[^1_226]: https://scispace.com/journals/the-journal-of-prediction-markets-bfnu28sx/2013

[^1_227]: https://cloud.usf.edu/ucm/experts/topic/sports-business

[^1_228]: https://ideas.repec.org/e/pwe198.html

[^1_229]: https://ideas.repec.org/a/kap/atlecj/v47y2019i1d10.1007_s11293-019-09611-y.html

[^1_230]: https://scispace.com/pdf/college-football-bettors-and-the-wisdom-of-crowds-50apong59x.pdf

[^1_231]: https://arxiv.org/html/1211.4000v1

[^1_232]: https://dash.harvard.edu/server/api/core/bitstreams/24950429-b1b7-4372-a029-1b68de1872e3/content

[^1_233]: https://www.collegefootballwinning.com/blog/college-football-predictions/

[^1_234]: https://bluechipanalytics.com/research/what-moves-college-football-betting-lines/

[^1_235]: https://www.arfjournals.com/image/catalog/Journals Papers/IJEFI/2022/No 1 (2022)/2_Ladd%20Kochman.pdf

[^1_236]: https://www.scribd.com/document/361683226/are-sports-betting-markets-prediction-markets-evidence-from-a-new-test

[^1_237]: https://staff.um.edu.mt/dominic.cortis/RePEC/buc/jpredm/Volume7.rdf

[^1_238]: https://ideas.repec.org/a/spr/jecfin/v50y2026i1d10.1007_s12197-026-09786-6.html

[^1_239]: https://www.semanticscholar.org/paper/079e0f5cc88c84d5a111f7aeae99f3bdfcab511f

[^1_240]: https://link.springer.com/article/10.1007/s11293-019-09616-7?error=cookies_not_supported\&code=e75098b2-d5af-4c51-b071-8500d1acce36

[^1_241]: https://www.collegefootballwinning.com/blog/efficient-markets-in-sports-betting/

[^1_242]: https://www.colleyrankings.com/matrate.pdf

[^1_243]: https://utstat.utoronto.ca/keith/papers/colley.pdf

[^1_244]: https://sburer.github.io/papers/038-rankings.pdf

[^1_245]: https://www.tandfonline.com/doi/abs/10.1080/01621459.1977.10480991

[^1_246]: https://titan.dcs.bbk.ac.uk/~ale/dsta/dsta-7/Massey_ranking/lm-ch2-massey.pdf

[^1_247]: http://www.davemease.com/papers/football.pdf

[^1_248]: https://www.colleyrankings.com/method.html

[^1_249]: https://arxiv.org/pdf/2411.09085.pdf

[^1_250]: https://titan.dcs.bbk.ac.uk/~ale/dsta+dsat/dsta+dsat-3/lm-ch3-colley.pdf

[^1_251]: https://arxiv.org/html/1701.03363v1

[^1_252]: https://reference-global.com/download/article/10.2478/ijcss-2026-0001.pdf

[^1_253]: https://ww2.amstat.org/mam/2010/essays/PasteurPredictive.pdf

[^1_254]: https://www.scribd.com/document/114809711/Mat-Rate

[^1_255]: https://en.wikipedia.org/wiki/Colley_Matrix

[^1_256]: https://www.math.purdue.edu/~peterson/research/Manschot_SeniorThesis.pdf

[^1_257]: https://www.tandfonline.com/doi/abs/10.1080/00031305.2025.2539998

[^1_258]: https://cs229.stanford.edu/proj2015/101_report.pdf

[^1_259]: https://www.qu.edu/academics/experiential-learning/course-projects-and-capstones/student-projects/predicting-nfl-total-score-and-point-spread-bets/

[^1_260]: https://www.atiner.gr/presentations/Theodore-Trafalis.pdf

[^1_261]: https://cs229.stanford.edu/proj2015/101_poster.pdf

[^1_262]: https://scholarworks.uvm.edu/bitstreams/cf900724-b503-4245-975d-f4eb1cd7dde0/download

[^1_263]: https://www.stat.berkeley.edu/~aldous/157/Papers/goddard.pdf

[^1_264]: https://ar5iv.labs.arxiv.org/html/2207.13747

[^1_265]: https://journals.sagepub.com/doi/10.1177/22150218251365223

[^1_266]: https://pdfs.semanticscholar.org/ae31/7f5a2757988cf464d38ee7297d60c6b29fc1.pdf

[^1_267]: https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1638446/full

[^1_268]: https://honors.libraries.psu.edu/files/final_submissions/7162

[^1_269]: http://constantinou.info/downloads/papers/pi-model12.pdf

[^1_270]: https://www.stat.cmu.edu/cmsac/conference/2020/assets/pdf/Robinson.pdf

[^1_271]: https://journals.sagepub.com/doi/10.3233/JSA-220613

[^1_272]: https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2026.1754408/full

[^1_273]: https://discovery.ucl.ac.uk/id/eprint/10110616/1/gavin_Paper.pdf

[^1_274]: https://dacemirror.sci-hub.se/journal-article/94d2f0ea9e70c80c6eb5f056d7caf4c9/david2011.pdf

[^1_275]: https://www.tandfonline.com/doi/full/10.1080/14413523.2026.2689228

[^1_276]: https://academic.oup.com/sleep/article/44/Supplement_2/A115/6260573

[^1_277]: https://academic.oup.com/aje/article/194/9/2499/8158079

[^1_278]: https://sites.dartmouth.edu/sportsanalytics/2022/02/15/big-12-big-country-how-greater-travel-impacts-home-field-advantage-in-college-football/

[^1_279]: https://bluechipanalytics.com/college-football/home-field-advantage/

[^1_280]: https://www.psychreg.org/time-direction-travel-football-performance/

[^1_281]: https://www.ensani.ir/file/download/article/6745ca6729abf-10693-1403-1.pdf

[^1_282]: https://fbschedules.com/numbers-home-field-advantage-college-football-over-last-decade/

[^1_283]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3187688

[^1_284]: https://kuscholarworks.ku.edu/server/api/core/bitstreams/31262367-c8d5-45dc-9833-63cb0caf0c3f/content

[^1_285]: https://www.colorado.edu/asmagazine-archive/node/1114

[^1_286]: https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6237.2012.00929.x

[^1_287]: https://www.colorado.edu/today/2012/11/14/new-study-examines-record-football-teams-after-coaching-changes

[^1_288]: https://journals.ku.edu/jis/article/download/21131/20148

[^1_289]: http://www.dukesportsanalytics.com/cfb_coach

[^1_290]: https://serjournal.wordpress.com/2020/01/22/what-happens-after-a-coaching-change-the-implications-for-ncaa-di-football-and-basketball-programs/

[^1_291]: https://journals.indianapolis.iu.edu/index.php/sij/article/download/25995/24368/51057

[^1_292]: https://jewlscholar.mtsu.edu/server/api/core/bitstreams/df2ca282-7c11-4cb5-a268-da4d3fed1dae/content

[^1_293]: https://www.espn.com/college-football/insider/story?id=44138328

[^1_294]: https://onlinelibrary.wiley.com/doi/full/10.1111/sjpe.12369

[^1_295]: https://scholarworks.montana.edu/server/api/core/bitstreams/028d53dd-372e-4e75-9e73-fc32162bef43/content

[^1_296]: https://mural.maynoothuniversity.ie/id/eprint/19100/1/AlexanderFarnellSpecial2023.pdf

[^1_297]: https://ww2.amstat.org/meetings/proceedings/2017/data/assets/pdf/593967.pdf

[^1_298]: https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-ii.html

[^1_299]: https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-i.html

[^1_300]: https://github.com/sportsdataverse/cfbfastR/blob/main/vignettes/college-football-expected-points-model-fundamentals-part-ii.Rmd

[^1_301]: https://github.com/sportsdataverse/cfbfastR/blob/main/vignettes/college-football-expected-points-model-fundamentals-part-iii.Rmd

[^1_302]: https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-vi.html

[^1_303]: https://zackgottesman.me/fair-catch/paper.pdf

[^1_304]: https://cfbfastr.sportsdataverse.org/articles/index.html

[^1_305]: https://datafield.dev/college-football-analytics/part-02/chapter-11/

[^1_306]: https://libraetd.lib.virginia.edu/downloads/x633f1952?filename=Klein_Darren_2022_STS_Research_Paper.pdf

[^1_307]: https://cfbfastr.sportsdataverse.org/articles/college-football-expected-points-model-fundamentals-part-iv.html

[^1_308]: https://rdrr.io/github/saiemgilani/cfbfastR/f/vignettes/college-football-expected-points-model-fundamentals-part-i.Rmd

[^1_309]: https://ideas.repec.org/a/spr/jecfin/v42y2018i4d10.1007_s12197-018-9437-y.html

[^1_310]: https://www.ubplj.org/index.php/jpm/article/download/2283/2113/8846

[^1_311]: https://ideas.repec.org/a/sae/jospec/v3y2002i3p256-263.html

[^1_312]: https://link.springer.com/article/10.1007/BF02761585

[^1_313]: https://link.springer.com/article/10.1007/s12197-009-9113-3

[^1_314]: https://ideas.repec.org/a/taf/apeclt/v18y2011i2p193-197.html

[^1_315]: https://www.ubplj.org/index.php/jpm/article/view/976

[^1_316]: https://econpapers.repec.org/RePEc:buc:jpredm:v:8:y:2014:i:2:p:29-42

[^1_317]: https://econpapers.repec.org/RAS/ppa514.htm

[^1_318]: https://www.semanticscholar.org/paper/National-television-coverage-and-the-behavioural-of-Weinbach-Paul/2e86f0a06a9ec6bcd9c848029c526eddd0f50613

[^1_319]: https://www.semanticscholar.org/paper/d5a3159c54952d6e4e5b75921027039fc7c43e81

[^1_320]: https://journals.sagepub.com/doi/10.1177/15270025211071042?int.sj-full-text.similar-articles.7

[^1_321]: https://ideas.repec.org/r/ucp/jnlbus/v41y1968p203.html

[^1_322]: https://www.seesports.net/research-insights

[^1_323]: https://ideas.repec.org/a/buc/jpredm/v3y2009i2p21-37.html

[^1_324]: https://www.grafiati.com/en/literature-selections/betting-market-efficiency/

[^1_325]: https://ideas.repec.org/p/nbr/nberwo/0507.html

[^1_326]: https://falk.syr.edu/wp-content/uploads/PaulCV.pdf

[^1_327]: https://www.coastal.edu/media/2024siteassets/contentassets/documents/wallcollegeofbusiness/facultycvs/financeandeconomics/Weinbach_CV_Jan_2025.pdf

[^1_328]: https://www.coastal.edu/media/2015ccuwebsite/contentassets/documents/wallcollege/facultyvita/econandfin/Weinbach_CV_August_2020_CCU.pdf

[^1_329]: https://www.grafiati.com/en/literature-selections/betting/

[^1_330]: https://ideas.repec.org/a/aop/jijoes/v10y2021i1p53-70.html

[^1_331]: https://ideas.repec.org/f/ppa514.html

[^1_332]: https://ideas.repec.org/a/bpj/jqsprt/v8y2012i3n3.html

[^1_333]: https://arxiv.org/abs/1403.7642

[^1_334]: https://ww2.amstat.org/mam/2010/essays/Mattingly.pdf

[^1_335]: https://scispace.com/journals/journal-of-quantitative-analysis-in-sports-11mz15l2/2012

[^1_336]: https://www.linkedin.com/in/andrewtkarl

[^1_337]: http://r.meteo.uni.wroc.pl/web/packages/mvglmmRank/mvglmmRank.pdf

[^1_338]: https://reference-global.com/2/v2/download/article/10.1515/ijcss-2017-0014.pdf

[^1_339]: https://reference-global.com/download/article/10.1515/ijcss-2017-0014.pdf

[^1_340]: https://reference-global.com/article/10.1515/ijcss-2017-0014

[^1_341]: https://www.semanticscholar.org/paper/A-Logistic-Regression-Markov-Chain-Model-for-Kolbush-Sokol/f541df4e280670e7fa23dc742b3c5cc147d26af3

[^1_342]: https://www.semanticscholar.org/paper/Journal-of-Quantitative-Analysis-in-Sports-Hybrid-,-Annis/73d088aefc2de1bfb36a0da01e7eaa1c6de88dcc

[^1_343]: https://www.semanticscholar.org/paper/The-Perron-Frobenius-Theorem-and-the-Ranking-of-Keener/b1a2ae3f890edd029b0ed88b91b9a5817f3a6ea1

[^1_344]: http://carlmeyer.com/pdfFiles/OffenseDefenseModel.pdf

[^1_345]: https://ideas.repec.org/a/wly/navres/v61y2014i1p17-33.html

[^1_346]: https://onlinelibrary.wiley.com/doi/abs/10.1002/nav.21563

[^1_347]: https://scispace.com/journals/journal-of-quantitative-analysis-in-sports-11mz15l2/2005

[^1_348]: https://econpapers.repec.org/RePEc:bpj:jqsprt:v:1:y:2005:i:1:n:3

[^1_349]: https://www.degruyterbrill.com/\_language/de?uri=/de/document/doi/10.2202/1559-0410.1000/html

[^1_350]: https://www.semanticscholar.org/paper/Minimizing-Game-Score-Violations-in-College-Coleman/88f8284b51455bd780cc16f25d3c2e920c4c5464

[^1_351]: https://masseyratings.com/theory/bib.htm

[^1_352]: https://ideas.repec.org/a/bpj/jqsprt/v6y2010i3n10.html

[^1_353]: https://citeseerx.ist.psu.edu/document?repid=rep1\&type=pdf\&doi=2d792c8d5016cee4070de4c9ee6eb344997b3b02

[^1_354]: http://netprophetblog.blogspot.com/p/papers.html

[^1_355]: https://ideas.repec.org/a/bpj/jqsprt/v6y2010i2n7.html

[^1_356]: https://www.semanticscholar.org/paper/Hybrid-Paired-Comparison-Analysis,-with-to-the-of-Annis-Craig/73d088aefc2de1bfb36a0da01e7eaa1c6de88dcc

[^1_357]: https://ideas.repec.org/a/bpj/jqsprt/v1y2005i1n3.html

[^1_358]: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00061/full

[^1_359]: https://www.ubplj.org/index.php/jpm/article/view/2283

[^1_360]: https://public-pages-files-2025.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00061/text

[^1_361]: https://mgoblog.com/mgoboard/overtime-going-2nd-really-better

[^1_362]: https://deadspin.com/let-both-offenses-touch-the-ball-in-playoff-overtime-1848420586/

[^1_363]: https://www.bettoredge.com/post/college-football-totals-betting

[^1_364]: https://www.reddit.com/r/CFB/comments/16l5su4/how_many_teams_in_the_history_of_cfb_overtime/

[^1_365]: https://www.cbssports.com/college-football/news/college-football-betting-guide-trends-to-consider-before-making-picks-predictions-for-the-2025-season/

[^1_366]: https://www.reddit.com/r/CFB/comments/b4ib2d/examining_the_differences_in_the_college_and_nfl/

[^1_367]: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID1646523_code1350147.pdf?abstractid=1646523\&mirid=1

[^1_368]: https://www.cbssports.com/college-football/news/college-football-betting-guide-trends-to-consider-before-making-picks-predictions-for-the-2024-season/

[^1_369]: https://www.bettingpros.com/articles/college-football-week-1-picks-predictions-bogmans-best-bets-2023/

[^1_370]: https://www.elevenwarriors.com/ohio-state-football/2023/09/140825/easy-bucks-spread-point-total-betting-lines-ohio-state-vs-western-kentucky-osu-wku-buckeyes-hilltoppers-2023

[^1_371]: https://managementjournal.info/index.php/IJAME/article/download/406/346/1271

[^1_372]: https://accessecon.com/Pubs/EB/2022/Volume42/EB-22-V42-I3-P139.pdf

[^1_373]: https://www.managementjournal.info/index.php/IJAME/article/view/406

[^1_374]: https://www.scribd.com/document/425306625/1-s2-0-S0169207011000914-main-pdf

[^1_375]: https://www.academia.edu/128764335/A_Consistent_Weighted_Ranking_Scheme_With_an_Application_to_NCAA_College_Football_Rankings

[^1_376]: https://www.academia.edu/8000619/Validating_a_division_IA_college_football_season_simulation_system

[^1_377]: https://scispace.com/journals/international-journal-of-forecasting-3m3vf93y/2012

[^1_378]: https://www.jair.org/index.php/jair/article/download/13509/26786/30289

[^1_379]: https://link.springer.com/article/10.1007/s10479-022-05063-x

[^1_380]: https://www.cs.vu.nl/~sbhulai/papers/paper-bosch.pdf

[^1_381]: https://www.academia.edu/98228390/Estimating_the_Strength_of_the_Impact_of_Rushing_Attempt_in_NFL_Game_Outcomes

[^1_382]: https://scispace.com/papers/a-comparative-analysis-of-data-mining-methods-in-predicting-1evs5t90jl

[^1_383]: https://www.studocu.com/row/document/addis-ababa-university/art-history/1-s2-bi-dm-preliminary/44546436?origin=related-document

[^1_384]: https://ar5iv.labs.arxiv.org/html/1601.00574

[^1_385]: https://ww2.amstat.org/meetings/proceedings/2014/data/assets/pdf/314074_91283.pdf

[^1_386]: https://web.stanford.edu/class/stats50/projects16/Houghton-BerryParkPierce-paper.pdf

[^1_387]: https://vsin.com/college-football/college-football-home-field-advantage-rankings-for-2026/

[^1_388]: https://weatherimpactonnflbet.com/articles/nfl-weather-ml-models-academic/

[^1_389]: https://www.unipa.it/persone/docenti/d/paolo.dibetta/.content/documenti/2010-you-can-even-walk-alone.pdf

[^1_390]: https://collegebettips.com/articles/home-field-advantage/

[^1_391]: https://sites.duke.edu/djepapers/files/2016/10/willoughbydjepaper.pdf

[^1_392]: https://www.stat.berkeley.edu/~aldous/157/Old_Projects/gonda.pdf

[^1_393]: https://surface.syr.edu/cgi/viewcontent.cgi?article=1057\&context=sportmanagement

[^1_394]: https://vsin.com/college-football/determining-college-football-true-home-field-advantage/

[^1_395]: https://www.nytimes.com/athletic/7084991/2026/03/04/college-football-coaches-analytics-fourth-down-the-book/

[^1_396]: https://www.footballstudyhall.com/2013/5/10/4318494/college-football-fourth-down-runs

[^1_397]: https://digitalcommons.du.edu/cgi/viewcontent.cgi?article=1031\&context=duurj

[^1_398]: https://www.fromtherumbleseat.com/2024/1/19/24028303/georgia-tech-football-to-be-or-not-to-be-aggressive-analytics-ncaa-fourth-downs-nfl-big-data-bowl

[^1_399]: https://www.si.com/college/olemiss/football/how-lane-kiffins-analytical-4th-down-decision

[^1_400]: https://www.nytimes.com/athletic/4906351/2023/09/28/college-football-fourth-down-decision-book/

[^1_401]: https://ideas.repec.org/p/nbr/nberwo/9024.html

[^1_402]: https://economics.virginia.edu/sites/economics.as.virginia.edu/files/2025-05/KanishkNazareth_0.pdf

[^1_403]: https://econ.appstate.edu/RePEc/pdf/wp2416.pdf

[^1_404]: https://digitalcommons.csp.edu/cgi/viewcontent.cgi?article=1080\&context=kinesiology_masters_science

[^1_405]: https://people.maths.ox.ac.uk/porterm/papers/bcsnotices.pdf

[^1_406]: https://static1.squarespace.com/static/50649559e4b01978906affcd/t/5d7fb89bcbe44c4fbe0e9ae1/1568651419818/explanation.pdf

[^1_407]: https://www.theringer.com/2021/12/03/college-football/college-football-playoff-bcs-computer-formulas-ranking-system

[^1_408]: https://www.theringer.com/2021/12/3/22815192/college-football-playoff-bcs-computer-formulas-ranking-system

[^1_409]: https://africa.espn.com/college-football/story/\_/id/8065826/transparency-selection-process

[^1_410]: https://scholarship.law.marquette.edu/cgi/viewcontent.cgi?httpsredir=1\&article=1620\&context=sportslaw

[^1_411]: https://www.academia.edu/55239332/College_Football_Rankings_Do_the_Computers_Know_Best

[^1_412]: https://sports.yahoo.com/articles/turnover-margin-affects-win-probability-195200724.html

[^1_413]: https://vsin.com/college-football/locating-predictive-stats-in-college-football/

[^1_414]: https://www.espn.com/college-football/story/\_/id/44951827/2025-college-football-team-luck-index-clemson-auburn/

[^1_415]: https://coachesinsider.com/football/using-stats-and-analytics-in-our-program/

[^1_416]: https://harvardsportsanalysis.org/2014/10/how-random-are-turnovers/

[^1_417]: https://journals.sagepub.com/doi/abs/10.1177/0569434516672768

[^1_418]: https://www.semanticscholar.org/paper/f84b97c51feddbba1a44ab4d65b529faf747f0f5

[^1_419]: https://www.semanticscholar.org/paper/Test-Are-Sports-Betting-Markets-Prediction-Markets:-Kain-Logan/ff08256fe47adbb2e799da23668f7d2f00ff7dc1

[^1_420]: https://www.econbiz.de/Record/nfl-betting-biases-profitable-strategies-and-the-wisdom-of-the-crowd-shank-corey/10012156161

[^1_421]: https://www.linkedin.com/in/eric-higger-cfp®-6721a025

[^1_422]: https://researchrepository.wvu.edu/context/econ_working-papers/article/1084/viewcontent/13_07.pdf

[^1_423]: https://scholar.google.com/citations?user=PI6vA6sAAAAJ\&hl=en

[^1_424]: https://researchrepository.wvu.edu/cgi/viewcontent.cgi?article=1084\&context=econ_working-papers

[^1_425]: https://www.nber.org/system/files/working_papers/w9422/w9422.pdf

[^1_426]: https://davidharville.com/collegefootballratingspredictions/

[^1_427]: http://pricetheory.uchicago.edu/levitt/Papers/LevittWhyAreGamblingMarkets2004.pdf

[^1_428]: https://pricetheory.uchicago.edu/levitt/Academics.html

[^1_429]: https://davidharville.com/collegefootballratingspredictions/predictions/

[^1_430]: https://en.wikipedia.org/wiki/Jeff_Sagarin

[^1_431]: https://www.chronicle.com/article/the-numbers-guy/

[^1_432]: https://colleyrankings.com/foot2002/rank09.pdf

[^1_433]: https://www.soa.org/globalassets/assets/Library/Newsletters/Predictive-Analytics-and-Futurism/2016/july/paf-2016-iss13-larson.pdf

[^1_434]: http://users.dimi.uniud.it/~massimo.franceschet/teaching/datascience/network/massey.html

[^1_435]: https://www.si.com/college/2013/08/27/verbatim-stats-guru-jeff-sagarin

[^1_436]: https://api.collegefootballdata.com/api/info

[^1_437]: https://graphqldocs.collegefootballdata.com/

[^1_438]: https://collegefootballdata.com/

[^1_439]: https://github.com/CFBD/cfb-api-v2

[^1_440]: https://d-nb.info/1367424771/34

[^1_441]: https://davidxia3.github.io/docs/predictability_paper.pdf

[^1_442]: https://cse.aua.am/wp-content/uploads/2026/08/paper_Edelweiss_Gevorgyan.pdf

[^1_443]: https://eecs.qmul.ac.uk/~norman/papers/assessing_probabilistic_football_forecast_models.pdf

[^1_444]: https://dl.icdst.org/pdfs/files/4e69a965af6ffb7db429e964094b1ccb.pdf

[^1_445]: https://arxiv.org/html/2101.02104v1

[^1_446]: https://www.sportmonks.com/glossary/brier-score/

[^1_447]: https://www.uni-bamberg.de/fileadmin/xai/studies/theses/2026/2026_Bachelorthesis_Di_Bao.pdf

[^1_448]: https://ueaeprints.uea.ac.uk/id/document/72655

[^1_449]: https://impliedscore.com/football-probability-calibration/

[^1_450]: https://ar5iv.labs.arxiv.org/html/2107.08827

[^1_451]: https://statistiques.public.lu/en/a-propos/bibliotheque/fonds-documentaire-periodiques/abonnements-numeriques-open-access/i/international_journal_forecasting/2010.html

[^1_452]: https://www.lukebornn.com/papers/yuan_jqas_2014.pdf

[^1_453]: https://www.nytimes.com/athletic/7626688/2026/09/24/college-football-week-4-score-projections-model/

[^1_454]: https://www.cbssports.com/betting/news/college-football-score-predictions-picks-for-week-5-2026/

[^1_455]: https://pdfs.semanticscholar.org/383b/895d3118e8bb605ed7e3421e8bd6c85699ac.pdf

[^1_456]: https://www.proquest.com/docview.pagelayout.checksession:set-cleared-client-storage;jsessionid=4B188995CBBA16C9DB88E0DF39B49859.i-075d3eecd19c47612?\_csrf=aaeee8e8-7d55-4425-a529-a4e1469ed8ab\&t:ac=2438124655

[^1_457]: https://arxiv.org/html/2603.10916v1

[^1_458]: https://arxiv.org/html/1404.2885v1

[^1_459]: https://search.proquest.com/openview/c027f7dba819d22752486fa9d0f2293a/1.pdf?pq-origsite=gscholar\&cbl=18750\&diss=y

[^1_460]: https://arxiv.org/html/2410.21484v1

[^1_461]: https://arxiv.org/html/2309.14807

[^1_462]: https://arxiv.org/html/1704.00197v3

[^1_463]: https://search.proquest.com/openview/65aff24671603e96ad7e68bfbdb93856/1.pdf?pq-origsite=gscholar\&cbl=18750\&diss=y

[^1_464]: https://arxiv.org/html/2607.01722v1

[^1_465]: https://about.proquest.com/en/search/

[^1_466]: https://arxiv.org/html/2511.14035v1

[^1_467]: https://arxiv.org/html/2607.26061v1

[^1_468]: https://arxiv.org/pdf/1512.07208v1.pdf

[^1_469]: https://dl.acm.org/doi/abs/10.1145/47968.47970

[^1_470]: https://www.semanticscholar.org/paper/A-comparative-analysis-of-data-mining-methods-in-Delen-Cogdell/f847cd3f7be3b417aae659e4f3a339532f604b3e

[^1_471]: https://api.pageplace.de/preview/DT0400.9780135946558_A41359940/preview-9780135946558_A41359940.pdf

[^1_472]: https://ideas.repec.org/a/bpj/jqsprt/v10y2014i1p67-79n7.html

[^1_473]: https://www.cs.iusb.edu/technical_reports/TR-20240429-1_Goldstein.pdf

[^1_474]: https://ideas.repec.org/a/eee/intfor/v35y2019i1p297-312.html

[^1_475]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9684891/

[^1_476]: http://mcclendonmath.com/papers/cfbpaper.pdf

[^1_477]: https://ijsas.wordpress.com/wp-content/uploads/2025/05/han-park.pdf

[^1_478]: https://www.si.com/nfl/2013/02/04/recruiting-rankings-predictive-accuracy

[^1_479]: https://stars.library.ucf.edu/cgi/viewcontent.cgi?article=1666\&context=honorstheses

[^1_480]: https://content.iospress.com/download/journal-of-sports-analytics/jsa190362?id=journal-of-sports-analytics/jsa190362

[^1_481]: https://articlegateway.com/index.php/JMDC/article/download/2006/1907/3758

[^1_482]: https://scholars.fhsu.edu/cgi/viewcontent.cgi?article=1214\&context=sacad

[^1_483]: https://discovery.ucl.ac.uk/id/eprint/10179498/9/Bryson_Scottish%20J%20Political%20Eco%20-%202023%20-%20Bryson%20-%20Special%20ones%20%20The%20effect%20of%20head%20coaches%20on%20football%20team%20performance.pdf

[^1_484]: https://www.econstor.eu/bitstream/10419/147704/1/23322039.2014.918857.pdf

[^1_485]: https://journals.ku.edu/jis/article/view/21131

[^1_486]: https://digitalcommons.wku.edu/cgi/viewcontent.cgi?article=1085\&context=diss

[^1_487]: https://eprints.lancs.ac.uk/id/eprint/164790/1/2021farnellphd.pdf.pdf

[^1_488]: https://scholarcommons.sc.edu/cgi/viewcontent.cgi?article=1123\&context=jiia

[^1_489]: https://www.espn.com/college-football/columns/story?id=2731820

[^1_490]: https://www.cbssports.com/college-football/news/early-returns-show-change-in-first-down-rule-hasnt-resulted-in-feared-negative-impact-on-college-football/

[^1_491]: https://unabated.com/articles/offseason-rule-changes

[^1_492]: http://blogs.shu.edu/kurt-rotthoff/files/2024/03/Bankruptcy-Behavior.pdf

[^1_493]: https://www.nytimes.com/athletic/4235755/2023/02/21/college-football-clock-rules/

[^1_494]: https://www.madduxsports.com/blog/ncaa-football-rule-changes-miff-coaches-37/

[^1_495]: https://www.latimes.com/archives/la-xpm-2007-feb-15-sp-clock15-story.html

[^1_496]: http://fs.ncaa.org/Docs/PressArchive/2006/Playing+Rules/NCAA+Football+Rules+Committee+Approves+Instant+Replay+System+Addresses+Length+of+Game+Issues.html

