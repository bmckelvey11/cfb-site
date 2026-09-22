**Superseded by** [opponent-adjustment-priors-model-comparison.md](../../research/totals/docs/opponent-adjustment-priors-model-comparison.md)

# Opponent Adjustment and Preseason Priors for College Football Betting Models

This review separates **documented evidence** from **implementation judgment**. The strongest immediately reproducible method is a point-in-time ridge offense/defense decomposition; the strongest small-sample extension is hierarchical partial pooling; and the most important totals-specific addition is a separate opponent- and game-state-adjusted pace model. Public SP+ and FPI descriptions are useful prior-design blueprints, but neither system publishes enough current implementation detail to reproduce exactly.

## 1. Opponent-adjustment methods

**Iterative/additive adjustment — summary:** repeatedly estimate each team relative to the opponents it faced until ratings stabilize. **Procedure:** initialize team effects, compute performance above/below opponents’ current ratings, recenter to the FBS mean, and iterate to convergence. A published FBS pace algorithm follows exactly this pattern: each team’s pace is updated from observed possessions minus the sum of opponents’ estimated paces until the maximum change is below 0.0001. SP+ publicly identifies itself as tempo- and opponent-adjusted, but its exact current iteration and weighting formula are not public; describing a particular algorithm as “the SP+ formula” would therefore be **[unverified]**.[^1][^2]

**Ridge offense + defense — summary:** estimate all offensive, defensive, and home-field effects simultaneously with L2 shrinkage. **Equation:** `stat = intercept + offense_team + defense_team + beta_HFA × venue + error`, minimizing squared error plus `lambda × sum(coefficients²)`. The CFBD implementation supplies working Python, codes home offense as +1, away offense as −1, neutral as 0, and tunes `alpha` with `RidgeCV`.[^3]

**Bayesian hierarchical — summary:** use the same offense/defense decomposition but draw team effects from shared population distributions. **Equation:** `y ~ likelihood(mu)`, with `mu = intercept + offense_i + defense_j + HFA`, `offense_i ~ Normal(mu_off, sigma_off)`, and `defense_j ~ Normal(mu_def, sigma_def)`. Partial pooling shrinks sparse teams more strongly and quantifies parameter uncertainty; this is well documented in sports models, though direct FBS totals evidence is limited.[^4]

**Elo-style updates — summary:** update one latent team-strength number after every game according to surprise. **Procedure:** `E_A = 1/(1+10^((R_B−R_A)/400))`; `R'_A = R_A + K(S_A−E_A)`. CFBD’s public tutorial starts teams at 1500 and uses `K=25`, while stressing that K controls responsiveness.[^5]

## 2. FCS, venue, garbage time

**Ridge has the clearest documented choices.** The CFBD example drops every non-FBS-versus-FBS game, includes an explicit venue regressor, and reports full-season `alpha` commonly around 150–200—175 in its example grid—with larger selected penalties in partial seasons. Its posted preprocessing removes undefined PPA but does not implement a garbage-time filter, so adding one must be an explicit modeling decision rather than attributed to the source. CFBD’s current definition flags a play when the pre-play margin exceeds 38 points in Q2, 28 in Q3, or 22 in Q4, and allows a game to leave garbage time if the margin contracts.[^6][^3]

**Iterative systems** can either exclude FCS, rate FCS in a connected second tier, or treat FCS performance as censored/downweighted; SP+ publishes FCS ratings, but the exact cross-division linkage and shrinkage are not documented in the sources reviewed. Venue can enter each game observation before iteration. Early-season estimates should be blended with preseason priors, but a universal shrinkage constant is **[unverified]**.[^7]

**Hierarchical models** handle these issues structurally: place FBS and FCS teams in separate but linked population distributions, include HFA as a fixed or varying coefficient, and let posterior pooling govern early samples. Published multilevel sports work shows that offense/defense partial pooling reduces overfit in small samples, but a validated FBS-specific prior scale for EPA/play or success rate was not found.[^4]

**Basic Elo** uses only game outcome, so play-level garbage time is irrelevant unless margin-of-victory enters the update. FCS can share the rating pool or receive a lower-tier prior; home field can be added inside the expected-score calculation. CFBD’s tutorial documents `K=25` but does not document an FCS rule, HFA term, or early-season variable-K schedule. Those choices must be tuned walk-forward, not copied from chess or the NFL.[^5]

## 3. Efficiency versus pace

Adjust **both**, but do not force them through one rating. EPA/play, success rate, finishing drives, explosiveness, and pressure-related measures describe scoring efficiency; plays, drives, seconds per play, pass rate, and clock behavior describe opportunity volume. SP+’s older public glossary explicitly distinguishes adjusted pace from opponent-adjusted efficiency and notes that pass-heavy teams can create more plays because incompletions stop the clock.[^8]

For totals, a useful structural identity is `expected total = expected drives × expected points per drive`, with plays per drive and scoring components layered beneath it. A published FBS model defines pace as expected possessions against an average-tempo opponent and obtains it through a recursive opponent adjustment, then averages the two teams’ pace estimates to project remaining possessions. That is stronger evidence for opponent-adjusting possession pace than simply using raw plays per game.[^1]

**Documented recommendation:** estimate separate offense and defense effects for efficiency and a separate iterative or regularized pace model. For pace, remove kneels, untimed downs, and obvious garbage-time snaps; also condition seconds/play on clock state, score state, quarter, down, and play type so that hurry-up while trailing is not mistaken for a team’s neutral identity. The latter feature specification is **common practitioner judgment [unverified]**, not a published universal standard.[^3][^1]

For implementation, retain multiple volume layers: neutral-situation seconds/play, drives per game, plays per drive, and opponent-adjusted possession pace. Do not opponent-adjust raw seconds/play mechanically without controlling for incompletions, first-down clock rules, and game script. The 2023 clock change materially altered the league environment, so season normalization or rule-era effects are necessary.[^9]

## 4. Circularity, clustering, leakage

**Circularity is inherent, not automatically fatal.** Offense is inferred partly through opposing defenses while defense is inferred through opposing offenses; iteration, ridge constraints, or hierarchical priors identify a joint solution, but they do not create information absent from the schedule. Ridge regularization reduces coefficient instability and multicollinearity, while Bayesian pooling regularizes through population priors.[^3][^4]

**Conference clustering creates weak links.** NCAA FBS schedules are strongly clustered by conference, producing poor algebraic connectivity in the game graph; ratings across conferences therefore depend disproportionately on relatively few interconference edges. A globally connected graph permits identification, but weak connectivity can still yield high uncertainty and conference-level drift. Diagnose this with graph components, algebraic connectivity, coefficient standard errors/posterior intervals, and leave-one-conference-out sensitivity. Conference random effects can stabilize estimates, but they can also preserve bias if the prior is too strong.[^10][^11]

**Leakage is the dominant operational risk.** A Week 5 feature must be rebuilt from games completed before that game’s kickoff; a season-end opponent adjustment applied backward leaks every later opponent result into earlier predictions. The same rule applies to SP+/FPI snapshots, PFF grades, roster status, recruiting corrections, weather, and betting lines. A published CFB modeling study explicitly used chronological holdout data because training on later games would distort generalization error.[^12]

For opener-to-close movement, freeze the feature timestamp at the opener being predicted. Closing spread/total, late injury confirmations, and ratings recomputed after those updates belong only in the target or evaluation layer. Store `as_of_timestamp`, source publication time, and maximum included game date on every feature table; this data-lineage prescription is **implementation judgment**, but it directly enforces the stated no-lookahead constraint.

## 5. Preseason-prior construction

**SP+ — documented blueprint:** combine last season’s opponent-adjusted rating with returning production, recent recruiting/transfer talent, and a smaller recent-history component. In spring 2025, Connelly said last year’s SP+ plus returning-production adjustments formed about two-thirds of the preseason projection. The initial 2025 description put this combined factor above 60%; contemporary descriptions placed recruiting near 14% and recent three-year history a little above 20%, but the exact final-August mixture and unit-specific coefficients were not fully published.[^13][^14][^15]

SP+ returning production is position weighted rather than a starter count. The 2025 offensive formula assigned 40% to returning OL snaps, 35% to WR/TE receiving yards, 22% to QB passing yards, and 3% to RB rushing yards; defense used 66% returning snaps, 19% tackles, and 15% tackles for loss. Incoming-transfer production enters both numerator and denominator, while lower-division transfers receive half credit in the published procedure.[^16][^17][^18]

**FPI — documented blueprint:** ESPN’s official methodology starts with prior offense, defense, and special-teams opponent-adjusted EPA, weights the latest season most, then adds returning starters, extra value for quarterback continuity or experienced transfer quarterbacks, four-year recruiting averages, and coaching tenure. ESPN did not publish reproducible coefficient weights, interaction terms, or current code; exact modern FPI weights are therefore **[unverified]**.[^19]

**Implementation implication:** build separate offense, defense, and pace priors. Predict next-year latent ratings from lagged opponent-adjusted performance, returning player production/PFF snaps, incoming and outgoing transfer production, roster talent, and coach/coordinator changes. Estimate every coefficient only inside past-season training folds rather than adopting SP+ percentages as fixed truths.

## 6. In-season prior decay

Public schedules show that the prior should remain heavy through September, but the exact optimal decay is model- and target-dependent. In a 2021 SP+ discussion, Connelly reported roughly 78% preseason weight after three games and about 55% after four; this is a documented historical snapshot, not a guaranteed current schedule. Older SP+ descriptions said the preseason component was completely gone after seven games, while current 2026 descriptions say only that it is slowly phased out week by week. Treat “gone by Week 7” as historical, not current.[^20][^21][^22]

FEI provides a cleaner contemporary benchmark based on FBS opponents played: 100% preseason with zero FBS games, 82% after one, 67% after two, and 54% after three. This supports the broad proposition that current-season information begins to rival the prior around a team’s third or fourth FBS game, although it does not establish that the same curve is optimal for EPA, pace, totals, or line movement.[^23]

A defensible empirical blend is `rating_t = w_t × preseason_prior + (1−w_t) × inseason_estimate`, where `w_t` is tuned by walk-forward log loss or squared error against the chosen target. Use effective sample size rather than calendar week: offensive EPA may accumulate rapidly, defensive explosives slowly, and pace may stabilize differently. Allow faster decay after quarterback or coordinator changes and slower decay for returning systems, but these interaction rules are **[unverified practitioner hypotheses]** until tested.

Do not select decay by final-score fit alone. Compare nested curves against closing-total residual, opener-to-close direction/probability, calibration, and CLV magnitude, with seasons held out in chronological order. A retained prior is justified only if it improves those market-relative out-of-sample metrics.

## 7. Regression and stability

The best public broad result found is Connelly’s historical analysis: one season’s F/+ rating correlated 0.742 with the next season’s rating, and a weighted five-year history increased that to 0.747. That supports substantial—but far from complete—carryover in composite opponent-adjusted team quality. The same analysis reported lower correlations between returning offensive starters and next-year offensive ratings (0.290) and between returning defensive starters and next-year defensive ratings (0.271), which helps explain why prior performance remains the base and continuity acts as an adjustment.[^24]

Noise is much more severe in turnover outcomes. One six-season study reported year-to-year `R²` of 0.057 for interceptions gained, 0.049 for interceptions lost, 0.016 for offensive fumbles, 0.001 for defensive fumbles, and 0.003 for fumble-recovery rate; offensive and defensive yards per game were around 0.243 and 0.275. SP+ documentation likewise treats raw turnover margin as luck-sensitive and emphasizes expected turnover components rather than observed recoveries. Explosiveness matters greatly in realized games but has been described as less reliable predictively than efficiency.[^25][^26][^27]

No primary public source was found that reports clean FBS year-over-year correlations for opponent-adjusted EPA/play, success rate, neutral seconds/play, plays per drive, and pace under one consistent garbage-time and rule-era definition. Numeric claims for those metrics should therefore be marked **[unverified]** until computed from the available CFBD panel.

The practical shrinkage answer is empirical: regress each prior-season metric on next-season point-in-time outcomes in rolling historical folds, with separate offense, defense, pace, coach-continuity, and 2021+ portal-era interactions. Expected ordering—composite efficiency most stable, success/pace intermediate, finishing/turnovers/explosive tails least stable—is partly supported but remains **[unverified]** as an exact FBS ranking.

## 8. Transfer-portal era

Public model design has changed materially. SP+ began incorporating both the quality and volume of incoming transfers in its recruiting component and now folds an incoming player’s previous production into the new team’s returning-production numerator and denominator. Its 2025 methodology also shortened the performance-history emphasis to the past three seasons because a five-year history had become less effective amid changes in the sport. These are model adaptations, not proof that every prior-season statistic has lost a specific percentage of predictive value.[^28][^17][^13]

The best empirical evidence located is a study covering roughly 7,000 FBS football and Division I men’s basketball transfers. After controlling for prior team performance and coaching pedigree, greater playing time for talented transfers was associated with higher team performance, while increased freshman minutes were negatively associated with performance. A separate FBS study of 4,245 effective transfers from 2019–2024 found that autonomous programs often lost transfer volume but gained relative talent and experience quality. Neither study directly estimates incremental prediction error for SP+, EPA, totals, or CLV.[^29][^30]

The COVID/portal transition also warns against treating raw returning percentages as stationary. Teams returning at least 85% had historically improved by 11.2 adjusted points in a cited 2014–20 sample, but the much larger 2021 high-return group improved only 3.9 points on average. COVID eligibility confounds that contrast, so it cannot isolate a portal effect.[^31]

Implement era-aware priors: value *who and what returns*, credit incoming FBS production with context translation, shrink lower-division production more heavily, and model net transfer quality by position. Re-estimate coefficients using 2021+ folds and test pre/post-2021 interactions; any exact “portal discount” is **[unverified]** until this backtest is run.

## Evidence matrix

| Method | Handles small samples? | Leakage risk | Evidence of out-of-sample value | Source |
|---|---|---|---|---|
| Iterative/additive adjustment | Only with explicit priors or damping; otherwise unstable early | High if final-season opponent ratings are backfilled | Published FBS pace procedure; no market-relative OOS result in that paper | [^1] |
| Ridge offense + defense + HFA | Yes, via L2 shrinkage; partial-season `alpha` can rise | High if weekly design matrix includes later games | Working CFBD code; no published totals/CLV OOS test | [^3] |
| Bayesian hierarchical offense/defense | Yes; posterior partial pooling is its main advantage | High if posterior is fit with future games or priors use future roster data | Strong transferable sports rationale; limited direct FBS betting evidence | [^4] |
| Dynamic Bayesian ratings | Yes; previous posterior becomes the next prior | Moderate if updated strictly chronologically | NFL walk-forward study found mixed ATS results across 2003–04; transfers methodologically, not as CFB proof | [^32] |
| Elo-style updates | Yes, through inherited rating and K; basic model has one team-strength dimension | Low when updated game by game; high if season-end Elo is backfilled | Reproducible CFBD tutorial, but no OOS betting evidence reported | [^5] |
| SP+ preseason blend | Yes; designed specifically for sparse early weeks | High if current/final SP+ is substituted for archived weekly values | Historical year-to-year F/+ correlation 0.742; exact current coefficients/code unavailable | [^24][^14] |
| FPI preseason blend | Yes; prior EPA, continuity, talent, and coaching stabilize Week 0 | High without archived timestamped snapshots | Official predictive design documented; public reproducible OOS betting validation not found | [^19] |
| Market-line benchmark | Yes—the market aggregates broad information | Low if the correct opener/close timestamp is preserved | Closing lines were more accurate than openers in college spread and total markets in a historical study | [^33] |

## What to implement first

1. **Build the point-in-time feature store and audit first.** Persist every weekly rating, roster input, PFF cutoff, opener, close, and feature with an `as_of_timestamp`; rerun walk-forward snapshots exactly as they would have existed before kickoff.
2. **Fit ridge offense/defense opponent adjustments for efficiency.** Start with EPA/play, success rate, explosive-play measures, and drive efficiency; tune `alpha` inside each training window, include venue, compare FBS-only against a sensitivity model with shrunk FCS observations, and publish coefficient stability diagnostics.[^3]
3. **Build a separate totals pace engine.** Iteratively or regularly adjust drives, neutral seconds/play, and plays per drive; remove garbage time and model rule era/game state. Combine projected possessions with efficiency rather than asking one latent rating to represent both.[^6][^1]
4. **Estimate preseason priors and decay rather than hard-coding them.** Use lagged opponent-adjusted unit ratings, position-weighted returning production, transfer production/quality, talent, and coaching continuity; tune separate decay curves for offense, defense, and pace in season-held-out folds.[^18][^19]
5. **Model the market-relative targets and run challengers.** For totals, predict closing-total residual or a calibrated over/under probability against the de-vigged close; for opener-to-close movement, predict direction and magnitude using opener-time features only. Benchmark ridge against hierarchical Bayes and Elo, report calibration and CLV by season/week/line bucket, and retain complexity only when it adds out-of-sample value.

---

## References

1. [5.2 Dynamic Bayesian...](https://arxiv.org/html/2207.13747v1)

2. [College football's final 2025 preseason SP+ rankings, takeaways](https://www.espn.com/college-football/story/_/id/45966848/college-football-2025-preseason-sp+-rankings) - Conference title odds : Kansas State 14%, Utah 9%, Arizona State 9%, TCU 9%, Texas Tech 8%, Iowa Sta...

3. [SP+ rankings after conference championship games](https://www.espn.com/college-football/story/_/id/28251219/sp+-rankings-conference-championship-games) - It's College Football Playoff and bowl season. Here's how SP+ sees everyone stacking up heading into...

4. [Bayesian analysis of home advantage in North American professional sports before and during COVID-19](https://www.nature.com/articles/s41598-021-93533-w) - Home advantage in professional sports is a widely accepted phenomenon despite the lack of any contro

5. [Talking Tech: Calculating Elo Ratings for College Football](https://blog.collegefootballdata.com/talking-tech-elo-ratings/) - Given the Elo rating of a team as well as its opponent, this function will calculate the team's prob...

6. [Metrics and definitions | CFBD - College Football Data API](https://api.collegefootballdata.com/metrics-and-definitions) - Documentation and API reference for the College Football Data API.

7. [College football Week 12 recap: Breaking down 25 great games](https://www.espn.com/college-football/story/_/id/46988962/college-football-week-12-recap-texas-oklahoma-alabama) - From A&M's historic comeback to heart-stoppers at all levels, Week 12 was packed with games to remem...

8. [An Advanced College Football Stats Glossary](https://www.footballstudyhall.com/2013/2/19/3980438/advanced-college-football-stats-glossary) - This was long overdue.

9. [Ohio State-Miami and what changes you'll see in 2026 ...](https://africa.espn.com/college-football/story/_/id/49577220/college-football-2026-trends-see-ohio-state-miami) - Sequencing, fourth down, slow games, fewer points. Coaches explain the changes.

10. [Recent advances in the Bradley–Terry Model: theory, algorithms ...](https://arxiv.org/html/2601.14727v2)

11. [Journal of Machine Learning Research 15 (2014) 2981-3012](https://jmlr.org/papers/volume15/osting14a/osting14a.pdf)

12. [Beating the NCAA Football Point Spread](https://cs229.stanford.edu/proj2010/LiuLai-BeatingTheNCAAFootballPointSpread.pdf)

13. [Where Does Georgia Tech Land in the Initial SP+ Rankings For the 2025 Season?](https://www.si.com/college/georgiatech/football/where-does-georgia-tech-land-in-the-initial-sp-rankings-for-the-2025-season-01jn49jaw8j3) - Although the 2025 college football season is still six months away, spring football is right around ...

14. [Spring update of 2025 college football SP+ rankings for every FBS ...](https://www.espn.com/college-football/story/_/id/45254341/spring-update-2025-college-football-sp+-rankings-every-fbs-team) - How the spring portal and other changes have impacted the numbers for the coming season.

15. [Initial 2025 college football SP+ rankings for every FBS team - ESPN](https://www.espn.com/college-football/insider/story/_/id/44011175/initial-2025-college-football-sp+-rankings-every-fbs-team) - In fact, this factor accounts for more than 60% of the overall projection at this point. it accounts...

16. [Spring update of 2025 college football SP+ rankings for ...](https://6abc.com/post/spring-update-2025-college-football-sp-rankings-every-fbs-team/16504408/) - It is determined by the past few years of recruiting rankings in diminishing order (meaning the most...

17. [College football 2025 returning production for all 136 FBS teams](https://6abc.com/post/college-football-2025-returning-production-136-fbs-teams/15951013/) - What teams have the most (and least) coming back, and what will it all mean next season?

18. [College football 2025 returning production for all 136 FBS teams](https://www.espn.com/college-football/insider/story/_/id/43952974/2025-college-football-returning-production-rankings-136-teams) - What teams have the most (and least) coming back, and what will it all mean next season?

19. [Introducing ESPN's Preseason FPI 1.0](https://www.espn.com/blog/statsinfo/post/_/id/114555/introducing-espns-preseason-fpi-1-0) - It's never too early to look ahead to the college football season. Our first iteration of preseason ...

20. [SP+ Predicts the Final Score For Virginia-NC State's Week Zero Matchup](https://www.si.com/college/virginia/what-is-virginia-s-sp-outlook-against-nc-state-01m0tn4fkcw8) - Virginia is favored to win Saturday against NC State, according to Fanduel. Multiple beat writers ha...

21. [Bill Connelly on X: "I've updated the results in the SP+ doc ...](https://x.com/ESPN_BillC/status/1442096817030660115) - I've updated the results in the SP+ doc (https://t.co/7doj8dyz4I). Through 3 weeks, SP+ was at 70% A...

22. [2026 college football SP+ rankings for all 138 FBS teams](https://abc7chicago.com/post/2026-college-football-sp-rankings-138-fbs-teams/19826490/) - The updated SP+ rankings, plus strength of schedule and résumé SP+, after this weekend's results.

23. [Post](https://x.com/bcfremeau/status/2099604522251248100) - FEI ratings, supporting stats, and F+ ratings (combining FEI and SP+) have been updated through Week...

24. [The Four-Step Guide to (Almost) Perfect College Football ...](https://athlonsports.com/college-football/four-step-guide-almost-perfect-college-football-predictions) - We think we know. We act like we know. But we do really know what makes a team good?

25. [On Turnovers and Randomness](https://mgoblog.com/diaries/turnovers-and-randomness) - (tl;dr? Skip to the Conclusion at the bottom) After a lot of discussion on this site about how rando...

26. [2015 Advanced Stats Glossary](https://www.footballstudyhall.com/2015/2/9/8001137/college-football-advanced-stats-glossary) - Here is a glossary for the terms used in the 2015 college football season previews at SB Nation.

27. [The 2018 advanced college football stats glossary](https://www.footballstudyhall.com/2018/2/2/16963820/college-football-advanced-stats-glossary) - Here is a glossary for the terms used in the 2018 college football season previews at SB Nation.

28. [College football's preseason SP+ rankings and takeaways](https://www.espn.co.uk/college-football/insider/story/_/id/39511969/college-football-2024-preseason-sp+-rankings-takeaways) - With the 2024 recruiting cycle in the books and spring practice starting soon, it's time to look at ...

29. [Talent Flow in the NCAA Transfer Portal and Its Associations ...](https://static1.squarespace.com/static/5de5182fe743cb648d87d098/t/67db77e9f2fe023fef8101fc/1742436329500/Pifer1_CSRI2025.pdf)

30. [[PDF] Transfer Networks and Talent Flow in the Football Bowl Subdivision ...](https://journals.ku.edu/jis/article/download/24024/22530)

31. [Who brings back the most production out of BYU, Utah and Utah State?](https://www.deseret.com/2022/2/8/22923703/who-brings-back-the-most-production-byu-utah-or-utah-state-football-cougars-aggies-utes-fbs/) - The Cougars, Utes and Aggies all return above 50% of their production from successful 2021 campaigns...

32. [https://digital.wpi.edu/downloads/x346d423k](https://digital.wpi.edu/downloads/x346d423k)

33. [Forecasting Accuracy and Line Changes in the NFL and College Football Betting Markets](https://blogs.colgate.edu/economics/files/2013/05/Xu_Econ490_Thesis.pdf)

