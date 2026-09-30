**Status:** unverified Perplexity Deep Research output (prompt [02](research-prompts/cfb-literature-review/02-rating-and-outcome-models.md), run 2026-09-30). Citations are leads until the [09 synthesis](research-prompts/cfb-literature-review/09-final-synthesis.md) citation audit. Its Fair & Oster numbers are checked against our own data in [fair-oster-massey-replication-2026-09-30.md](fair-oster-massey-replication-2026-09-30.md). References 1_27 and 1_349 are this repo's own files, not literature; neither is cited in the body.

# CFB Literature Review 02: Rating and Outcome Models

**Research cutoff: September 30, 2026**

The defensible bottom line is narrow: **no verified published FBS study in the searched literature demonstrates a model that beats a contemporaneously available closing spread out of sample after vig, leakage, model-selection, and price-timing checks.** The strongest direct test—Fair and Oster—finds that computer ratings predict winners and margins, but their information is subsumed by the final Las Vegas spread; that evidence covers 1998–2001 and is therefore **[pre-2018]** and not a modern retail-sportsbook validation.[^1_1][^1_2]

Direct FBS research supports margin-based ratings, score-differential methods, dynamic state-space ratings, preseason priors, and forecast combinations as useful **football forecasting tools**. It does not establish that any of them generate durable ATS alpha against post-2018 DraftKings or FanDuel closing prices.

## Evidence standards

The following distinctions govern the evaluation:

- **Predicting winners is not beating the spread.** A model can exceed 70% straight-up accuracy largely by identifying favorites and still be below 50% ATS.
- **Random cross-validation is not prospective validation.** Randomly withholding games from a completed season lets future games influence ratings used to “predict” earlier games.
- **A closing-line comparison is not an ATS test unless bets are explicitly graded.** Regressing realized margin on a model and the spread tests incremental information, but not net profitability.
- **A published rating is not a reachable price.** If the rating becomes available after an opener moves, its apparent performance against that opener is not actionable.
- **A profitable rule is invalid if its edge threshold was selected on the test set, the price was unavailable when the forecast was published, or features contained post-kickoff information.**
- **The -110 break-even rate is 52.38%.** Any ATS paper that reports only a win percentage without vig-aware confidence intervals, trial counts, and selection procedures is incomplete as betting evidence.
- **Pre-2018 results require revalidation.** Market participants, data availability, sportsbook competition, line dissemination, limits, and legal US retail betting changed materially after PASPA.


# Methods catalog

| Model family | Main inputs | Fitting and update | Published FBS accuracy | Closing-line result | Evidence |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Harville linear rating | Game margin, home field, dates; later versions allow temporal dependence | Linear model or mixed model; team effects may follow an autoregressive process | No prospective FBS ATS percentage verified in the accessible paper record | No verified closing-line test | **[FBS] [pre-2018]** Harville’s 1977 paper develops a linear-model procedure for high-school or college football point margins.[^1_3] |
| Massey least squares | Game-by-team incidence matrix and point differentials | Solve constrained least squares $X'Xr=X'y$; ordinarily refit as games arrive | Govan et al.: 67.71%–73.23% straight-up by season, weeks 6 through bowls, 2003–2007; n not reported in accessible text | Not tested | **[FBS] [pre-2018]** The original formulation is Massey’s 1997 undergraduate thesis.[^1_4][^1_5] |
| Regularized least squares / maximum posterior | Margins or win indicators plus an $L_2$ prior | Ridge-type system $(X'X+\gamma I)r=X'y$ | Barrow et al. find score-based least squares among the best winner-ranking methods across 56 seasons, but use random within-season cross-validation | Not tested | **[FBS] [pre-2018] [uncertain operational validity]**[^1_6] |
| Colley matrix | Wins, losses, opponents; no margin | Solve $Cr=b$, with Laplace-rule shrinkage toward .500 | Govan et al.: 66.14%–68.74% prospective straight-up from week 6, 2003–2007 | Not tested | **[FBS] [pre-2018]**[^1_7] |
| Keener eigenvector | Pairwise win or score matrix | Perron–Frobenius eigenvector; recomputed as games arrive | Govan et al.: 63.68%–70.29% prospective straight-up from week 6, 2003–2007 | Not tested | **[FBS] [pre-2018]**[^1_7] |
| PageRank / random walker | Directed results network, sometimes score-weighted | Stationary distribution of a stochastic transition process | Barrow et al. report score-based random walker and least squares as the strongest FBS methods in their comparison; exact average accuracy was not recoverable from accessible text | Not tested | **[FBS] [pre-2018] [uncertain operational validity]**[^1_6] |
| Elo | Ordered game outcomes or score-derived outcomes | Sequential logistic update with fixed $K$, or generalized dynamic update | Included in Barrow et al.; not the leading FBS method in their reported significance comparison | Not tested | **[FBS] [pre-2018] [uncertain operational validity]**[^1_6] |
| GLMM win/loss hierarchy | Binary outcomes, FBS/FCS identities | Probit or logit random team effects; shrinkage handles undefeated teams | Karl studies ranking sensitivity, not prospective game accuracy | Not tested | **[FBS] [pre-2018]**[^1_8] |
| Bayesian state-space margin model | Margins, home field, season-to-season team strength | Autoregressive latent team strengths with posterior updating | Yurko and Benz: 9,003 regular-season games, 2014–2024; 2023–2024 held out; exact RMSE unavailable in slides | No sportsbook comparison | **[FBS] [conference paper]**[^1_9] |
| Fixed-effects margin model | Margins and team indicators | OLS with team and home-field terms | Fair–Oster combined ratings explain 38.2% of margin variance and identify 72.9% of winners in 1,582 games | Final line raises explained variance to 44.5% and winner accuracy to 74.7%; rating variables jointly insignificant | **[FBS] [pre-2018] [in-sample]**[^1_1][^1_2] |
| Offense–Defense matrix balancing | Points scored by each team against each opponent | Iterative offensive and defensive ratings; aggregate $o_i/d_i$ | 64.43%–71.95% prospective straight-up, 2003–2007, beginning week 6 | Not tested | **[FBS] [pre-2018]**[^1_7] |
| ML upset classifiers | Team statistics, rankings, spread | Logistic regression, SVM, trees or related classifiers | Padron and Sinsay use one 2013 season; accessible report says models struggled when favorites were at least seven points, but no reliable ATS figure was verified | No valid closing-line ATS test | **[FBS] [student project] [uncertain]**[^1_10] |
| SP+ | Tempo- and opponent-adjusted efficiency; preseason history, returning production, recruiting and transfers | Proprietary predictive rating updated in season | No peer-reviewed FBS ATS evaluation located | No published closing-line validation located | **[practitioner]** SP+ describes itself as predictive rather than résumé-based.[^1_11] |
| FPI | Prior performance, returning personnel, quarterback, recruiting and coaching | Proprietary unit-level ratings and season simulation | No peer-reviewed FBS ATS evaluation located | No published closing-line validation located | **[practitioner]** The published methodology describes points above/below average on a neutral field.[^1_12] |
| Panel consensus | Many published computer ratings | Median, mean, trimmed mean or fitted forecast combination | Fair–Oster find an estimated combination improves on constituent ratings in sample | Final spread subsumes the combination; no modern out-of-sample ATS success verified | **[FBS] [pre-2018]**[^1_1][^1_2] |

# Margin-based ratings

## Least squares

The canonical Massey system treats each game as a linear equation in team ratings. If team $i$ beats team $j$ by $y_g$, the row for game $g$ has $+1$ for $i$, $-1$ for $j$, and the model seeks ratings satisfying

$$
r_i-r_j \approx y_g.
$$

Because all ratings can be shifted by a common constant without changing fitted margins, the system requires an identifying constraint such as $\sum_i r_i=0$. Massey introduced this sports-rating formulation in a 1997 undergraduate thesis; subsequent work characterizes it as the standard least-squares ranking method.[^1_4][^1_5]

**[FBS] [pre-2018]** Govan, Langville, and Meyer provide the cleanest accessible prospective comparison. They recomputed FBS-only ratings weekly, discarded FBS–FCS games, began predictions in week 6, and continued through bowls for the 2003–2007 seasons. Massey winner accuracy was 69.62%, 67.71%, 67.79%, 73.23%, and 69.89%, respectively; no lines, vig, MAE, or ATS records were reported.[^1_7]

That validation is meaningfully better than fitting and scoring the same completed season, but it remains incomplete:

- The exact number of predicted FBS games was not reported in the accessible text.
- Predictions begin only after five weeks, excluding the difficult and commercially important early season.
- Home-field treatment is not clearly integrated into every method’s winner rule.
- No uncertainty intervals compare the methods.
- Bowl games are included without a separate postseason regime.
- No bookmaker spread is used.

**Contrary evidence:** **[FBS] [pre-2018]** Barrow et al. compare win-only and score-based versions of eight ranking families over 56 seasons from 1956–2011. Their score-based least-squares method ranks among the strongest FBS winner predictors, supporting the use of margin rather than merely win/loss information. However, the paper’s 20-fold random cross-validation repeated 100 times within each season is not a deployable time split: later-season games can influence ratings used to score earlier games. Its comparative result is informative; its absolute accuracy is not an honest pregame backtest.[^1_6]

## Harville formulations

**[FBS] [pre-2018]** Harville’s 1977 formulation models observed margin as a home-field term plus the difference between team strengths, with stochastic team-performance deviations. It is the statistical ancestor of many current point-rating systems.[^1_3]

A generic version is

$$
Y_{ijt}=h_{ijt}\lambda+\theta_{it}-\theta_{jt}+\epsilon_{ijt},
$$

where $h_{ijt}$ records the site, $\lambda$ is home-field advantage, and $\theta_{it}$ is team strength. Dynamic extensions let strength evolve through an autoregression rather than treating a team as constant for an entire season.

**[practitioner]** Harville’s current implementation uses Division I games from the current and three preceding seasons, groups teams into power-FBS, non-power-FBS, and FCS populations, and connects annual team effects with a first-order autoregressive process. It also uses a latent-variable treatment of football’s discrete scoring distribution and overtime rather than treating raw margins as exactly Gaussian.[^1_13]

No prospective ATS percentage against an identified closing book was found for Harville’s FBS forecasts. Therefore the formulation is supported, but its market-beating accuracy is **untested** in the searched published literature.

## Ridge and shrinkage

A maximum-posterior or ridge version solves

$$
\hat r=(X'X+\gamma I)^{-1}X'y.
$$

The penalty stabilizes ratings for teams with few games and weak cross-conference connectivity. It also supplies an implicit preseason prior centered at the population mean.

**[FBS] [pre-2018]** Barrow et al. include a maximum-posterior method and explain its connection to Tikhonov regularization; their principal FBS finding is that score-based methods generally outperform corresponding win-only methods. The study does not show that ridge beats unregularized least squares against a closing spread, and its random-fold design does not establish week-by-week deployability.[^1_6]

**Contrary evidence:** Excessive shrinkage can erase real conference or talent differences, particularly early in a season. Karl’s GLMM sensitivity study shows that changing the assumed variance of team effects can materially reorder top teams even when continuous rating changes are small. Thus, shrinkage should be estimated inside each historical training window rather than selected by final-season ranking agreement.[^1_8]

## Home-field terms

**[FBS] [pre-2018]** Fair and Oster estimate a home advantage of 4.30 points with a standard error of 0.43 in their preferred computer-rating combination, based on 1,582 games from 1998–2001. When the final Las Vegas line enters the regression, the separate home term loses significance because the market line already embeds it.[^1_2]

That 4.30-point value is not a current constant. **[FBS] [mechanism only]** Karl’s analysis of 2000–2017 FBS scoring margins estimates a 2017 conference-level home advantage of 2.352 points and a time slope of -0.102 points per year; the slope’s p-value is 0.053, so the evidence of a systematic decline is suggestive rather than conclusive.[^1_14]

Karl also identifies a modeling hazard: stronger college teams disproportionately schedule home games against weaker opponents. In simulations preserving real FBS scheduling, a random-team-effects model estimates a 3.37-point home effect when the simulated truth is 3.00, whereas the fixed-effects model recovers 3.00 with 95% interval coverage.[^1_14]

**Implementation implication:** Do not impose one HFA across 2001–2026. Estimate a season-varying home term, consider conference interactions, identify neutral-site games carefully, and test whether a fixed-effects treatment is less biased than a naïve random-effects model.

# Win-loss ranking systems

## Colley matrix

The Colley method intentionally excludes margin. Ratings solve

$$
Cr=b,
$$

where diagonal entries reflect games played, off-diagonal entries reflect matchups, and $b$ is based on wins minus losses. The method shrinks teams toward .500 and yields unique ratings even with limited schedules.

**[FBS] [pre-2018]** In Govan et al.’s prospective week-6-forward comparison, Colley predicted 66.14%–68.74% of winners across 2003–2007. It lagged Massey in four of five seasons and never supplied a point-margin estimate suitable for direct comparison with a spread.[^1_7]

**[FBS] [pre-2018]** Fair and Oster’s 1998–2001 regression comparison also suggests that Colley’s rank differences were weaker standalone margin predictors than Sagarin, Massey, or Dunkel. Colley nevertheless sometimes received a significant **negative** coefficient in a multirating regression because its conditional information differed from the other highly correlated ratings.[^1_2]

This is not evidence that “negative Colley” is a tradeable factor. The weights were estimated and evaluated in the same sample, and no temporal holdout was used.

## BCS components

Fair and Oster evaluate Matthews/Scripps Howard, Sagarin, Billingsley, Anderson–Hester, Colley, Massey, Rothman, Wolfe, and Dunkel—systems overlapping the early BCS computer component set. The individual rank-difference variables were highly correlated, with correlations of 0.779–0.973 in the core sample.[^1_2]

**[FBS] [pre-2018]** The best individual systems predicted roughly 72% of winners in sample, while the fitted combination reached 72.9%; the final spread reached 74.7%. The fitted combination therefore improved ranking-based prediction but did not improve on the market.[^1_2]

The BCS decision to exclude margin addressed incentives to run up scores, not demonstrated predictive optimality. Two independent comparisons point the other way:

- **[FBS] [pre-2018]** Govan et al.’s score-based Massey system generally outperformed Colley and Keener’s win-oriented methods prospectively.[^1_7]
- **[FBS] [pre-2018]** Barrow et al. find that score-differential implementations usually outperform win-loss implementations for FBS and college basketball, with FBS least squares and score-based random walker among the strongest methods.[^1_6]

**Contrary evidence:** Colley’s best Govan season reached 68.74%, close to several margin systems, and hindsight rankings based only on wins can perform well after the full season is known. That does not establish equivalent prospective margin accuracy or ATS value.[^1_7]

## Keener and eigenvectors

Keener’s method constructs a nonnegative pairwise-performance matrix and takes its Perron–Frobenius eigenvector. Its appeal is indirect strength of schedule: beating a highly rated opponent contributes through the network structure.

**[FBS] [pre-2018]** Govan et al. report Keener foresight accuracy ranging from 63.68% to 70.29% across 2003–2007, below Massey in four of five seasons. Keener’s hindsight accuracy was substantially higher, demonstrating how same-season final ratings can overstate actionable predictive quality.[^1_7]

PageRank-style systems similarly define a stochastic transition matrix on the results graph. Their behavior depends heavily on damping, treatment of ties, score transformation, and what mass flows from winners to losers or vice versa.

**[FBS] [pre-2018]** Barrow et al. do not identify ordinary PageRank as the dominant FBS method; their score-based random-walker formulation performs better. This contradicts any broad claim that eigenvector sophistication itself guarantees superior prediction.[^1_6]

# Dynamic models

## Elo

Elo represents each team with a rating and updates it after each game according to the difference between observed and expected outcome:

$$
R_{i,t+1}=R_{i,t}+K(S_{it}-E_{it}).
$$

It naturally handles in-season change, but performance depends on $K$, preseason regression, home advantage, margin multiplier, and season-to-season carryover.

**[FBS] [pre-2018]** Barrow et al. include win-only and score-informed Elo variants across 56 FBS seasons. Elo was not the leading family in their FBS significance comparisons. Because their held-out games were randomly selected within each season, this is not a valid week-forward evaluation of a sequential rating.[^1_6]

No published FBS Elo study with a verified walk-forward closing-line ATS test was found in the searched sources.

## State-space ratings

A state-space model allows latent team strength to evolve:

$$
\theta_{i,t}=\rho\theta_{i,t-1}+u_{i,t},
$$

$$
Y_{ijt}=\lambda+\theta_{i,t}-\theta_{j,t}+\epsilon_{ijt}.
$$

Here $\rho$ controls persistence, while the innovation variance controls how quickly ratings can change. Filtering updates beliefs after each game; posterior variance expresses how uncertain each team’s current rating remains.

**[NFL – transfer] [pre-2018]** Glickman and Stern’s NFL score model is the foundational football state-space application. It establishes a coherent dynamic framework, but NFL schedule density, roster rules, competitive balance, and interconference connectivity differ materially from FBS. It should not be cited as direct FBS accuracy.

**[FBS] [conference paper]** Yurko and Benz apply a Bayesian state-space framework to 9,003 regular-season FBS games from 2014–2024, exclude bowls and playoffs, and treat FCS as one pooled opponent. Their evaluation trains through 2022 and holds out 2023–2024. The baseline Glickman–Stern-style model has the best game-level RMSE and expected log predictive density; a transfer-count variance model ranks next, while unrestricted stochastic volatility performs worst.[^1_9]

That is one of the strongest temporal validations found, but it has limitations:

- Exact holdout RMSE and uncertainty intervals were not recoverable from the conference slides.
- The model is not compared with opening or closing spreads.
- Transfer **counts**, not transfer quality, are modeled.
- Recruiting and NIL amounts are omitted.
- Only two seasons are held out.
- Bowls are excluded rather than modeled.

The evidence contradicts an intuitive claim that a more flexible volatility process must improve forecasts. In this sample, the simpler dynamic baseline performs best out of sample.[^1_9]

## Bayesian hierarchies

**[FBS] [pre-2018]** Karl models game winners with probit or logit generalized linear mixed models and random team effects. The hierarchy regularizes undefeated and winless teams and allows FBS and FCS to be modeled as one or two populations.[^1_8]

The empirical application covers the 2008–2011 regular seasons through conference championships and examines ranking sensitivity rather than future-game accuracy. Choices among link functions, Laplace approximations, random-effect distributions, and FCS treatments change postseason-relevant rankings; in some seasons they switch the teams ranked second and third.[^1_8]

The lesson is not that one approximation predicts better. It is that FBS win/loss data alone are too sparse to make top-team ordering robust. No closing-line comparison, proper probability score, or prospective winner test is reported.

# Statistical and ML models

## Regression

The credible regression literature is concentrated in team-effect and rating models rather than high-dimensional box-score ML. Harville, Massey, Fair–Oster, Gill–Keating, Karl, and Yurko–Benz all use regression-like structures with varying degrees of shrinkage and dynamics.[^1_15][^1_3][^1_1][^1_9][^1_8]

**[FBS] [pre-2018]** Fair and Oster’s OLS combination is the only verified peer-reviewed study found that directly places multiple computer-rating forecasts and a final Las Vegas spread in the same model. The spread coefficient is 1.030 and the hypothesis that every other predictor is zero is not rejected; the reported joint F statistic is 0.96.[^1_2]

This is strong evidence of encompassing but not a valid modern ATS backtest because:

- All coefficients are estimated and assessed on the same 1998–2001 sample.
- The line is the final Gold Sheet Las Vegas line, with no book-level timestamp.
- There is no holdout.
- No actual bet-selection rule is evaluated.
- Vig is not applied.
- No post-2018 replication is supplied.


## Trees and neural networks

No peer-reviewed published FBS study was found in the searched sources that simultaneously satisfies all of these conditions:

1. Uses pregame box-score, play-by-play, recruiting, or personnel features.
2. Predicts game margin or ATS result.
3. Splits training and testing chronologically.
4. Uses a reachable open, intermediate, or closing price.
5. Reports the number of model and threshold trials.
6. Accounts for -110 vig.
7. Evaluates a genuinely untouched test period.

**No published FBS study found in searched sources.**

**[FBS] [student project] [uncertain]** Padron and Sinsay use supervised learning to classify upsets from the 2013 season with betting spread and ranking features. The accessible paper indicates difficulty predicting upsets when the favorite was at least seven points, but the one-season design, unclear chronological split, and absence of a verified closing-line ATS record make it unsuitable as betting evidence.[^1_10]

**[FBS subset]** A peer-reviewed neural-network study achieves 75.3% on college-football overtime situations, but that is an in-game overtime-decision problem, not a pregame FBS margin or ATS model. It should not be transferred as evidence that a neural network predicts full-game spreads.[^1_16][^1_17]

The scarcity of valid results matters. Many online projects report high winner accuracy after using contemporaneous rankings or spreads as inputs, but accuracy relative to the winner does not test whether the model improves upon the market.

# Preseason and early season

## Published priors

The following prior structures are supported:

- **Previous-season team strength:** Harville’s practitioner model uses the current and three previous seasons and connects yearly effects through a first-order autoregression.[^1_13]
- **Population shrinkage:** Ridge, Colley, and hierarchical random-effects models shrink teams toward an average, reducing early-season variance.[^1_8][^1_7]
- **Recruiting and returning production:** A university thesis finds prior-year standardized Sagarin rating to be the best single predictor of next-season team performance, with returning offensive and defensive starters, returning quarterback, and recruiting variables entering multivariate models; the final models explain about 53.3% of variation in season performance, not game margins.[^1_18]
- **SP+ practitioner prior:** Recent performance, returning production, recent recruiting, incoming transfers, and coaching factors are combined according to predictive weights.[^1_11]
- **FPI practitioner prior:** Recent unit performance, returning starters and quarterbacks, recruiting, and head-coach tenure contribute to preseason offensive, defensive, and special-teams ratings.[^1_12]
- **Transfer-induced uncertainty:** Yurko and Benz model between-season innovation variance as a function of transfer count and NIL-era status, although the simpler baseline predicts the holdout games better.[^1_9]


## Convergence by week

No peer-reviewed FBS paper was found that publishes a complete week-by-week table of margin MAE, ATS percentage against a timestamped line, and preseason-prior weight.

**No published FBS study found in searched sources.**

Govan et al. implicitly acknowledge early-season instability by refusing to forecast until week 6. That design avoids evaluating the exact period when priors are most valuable, so it cannot establish how quickly each method converges.[^1_7]

A practical dynamic prior should decay according to accumulated possessions or effective game information, not merely calendar week. Games against FCS teams, garbage-time blowouts, weather games, overtime, and short possessions do not contribute equal information.

## Contrary evidence

The prior-year Sagarin result suggests persistence is substantial. Conversely, Yurko and Benz show that transfer activity is associated with changed between-season uncertainty, but their transfer-volatility model does not beat the simpler baseline overall. Thus the evidence supports preserving strong priors while allowing team-specific uncertainty—not automatically making every high-transfer roster’s mean rating jump.[^1_18][^1_9]

# Schedule sparsity

FBS is structurally difficult because teams play few games relative to the number of teams, conference schedules create clusters, FCS games connect different populations unevenly, and many pairs of teams have no short-path comparison.

**[FBS] [pre-2018]** Barrow et al.’s dataset averages 125.6 teams and 645.6 games per season after recursively deleting teams with fewer than four qualifying games. FBS has algebraic connectivity of 1.09, far below the NBA’s 52.5 in their comparison, indicating a much less informative schedule graph.[^1_6]

That sparsity has measurable consequences:

- Ranking methods differ more in FBS than in highly connected leagues.
- A few cross-conference games can disproportionately affect conference offsets.
- Ratings for undefeated teams can be weakly identified.
- Random-effect distributions and shrinkage assumptions materially affect rankings.
- FCS treatment can move highly ranked FBS teams.

**[FBS] [pre-2018]** Karl shows that treating every FCS opponent as one pooled team, a separate population with shared variance, or a separate population with its own variance changes top-team ordering in the 2008–2011 applications.[^1_8]

**[FBS] [mechanism only]** Karl’s home-field analysis also shows that full-season college schedules are nonrandom: stronger teams obtain more home games against weaker opponents, biasing certain mixed-model estimates.[^1_14]

## Recommended handling

For a CFBD model:

- Preserve each FCS team when sufficient history is available; otherwise use hierarchical FCS conference or population effects rather than one universal FCS rating.
- Include conference-level random effects but constrain them with cross-conference evidence.
- Track posterior or bootstrap uncertainty for every team rating.
- Include graph diagnostics such as component membership, algebraic connectivity, effective resistance, and distance to the opponent’s conference.
- Increase shrinkage for teams whose schedules provide weak cross-network identification.
- Do not estimate home advantage as the raw average home margin.
- Audit realignment years separately because conference graph structure changes.


## Measured effect on betting accuracy

No published FBS study found in searched sources quantifies the change in out-of-sample closing-line ATS accuracy caused specifically by correcting schedule sparsity.

# Margin-of-victory treatment

## Capping and diminishing returns

Raw margin contains predictive information but also coaching, pace, field position, end-game behavior, and opponent incentives. Common transformations include

$$
g(m)=\operatorname{sign}(m)\min(|m|,C),
$$

$$
g(m)=\operatorname{sign}(m)\log(1+|m|),
$$

or a hazard-based transformation that gradually reduces the marginal value of points beyond a threshold.

**[FBS] [pre-2018]** Harville proposes truncation or hazard-based scaling to reduce the incentive to run up the score. His current practitioner methodology combines a latent treatment of discrete margins with an explicit weight on “winning per se” and allows margin weight to increase when a mismatch was already expected.[^1_19][^1_13]

**[FBS] [pre-2018]** Gill and Keating evaluate ordinary and weighted least-squares college-football rankings and adjustments intended to reduce the influence of large margins. The accessible source did not expose the exact cross-validated error table, so no numeric superiority claim is made here.[^1_15][^1_8]

## Evidence for using margin

Two independent empirical comparisons support margin information:

- Govan et al.’s Massey method generally beats Colley and Keener prospectively in 2003–2007.[^1_7]
- Barrow et al. find score-differential versions usually outperform win-loss versions in FBS, with score-based least squares and random walker leading their tested set.[^1_6]

Fair and Oster provide a qualification. Once the final betting spread is included, no rating system—including margin-sensitive systems—contributes incremental information. Margin improves football prediction but does not necessarily improve market prediction.[^1_1][^1_2]

## Garbage time

No peer-reviewed FBS study was found that isolates a play-by-play garbage-time adjustment and reports its incremental, chronological closing-line MAE or ATS value.

**No published FBS study found in searched sources.**

That gap is particularly relevant to CFBD play-by-play. Existing published comparisons generally use final scores, so they cannot distinguish predictive scoring from possessions after win probability became extreme.

# Head-to-head comparisons

## Govan et al.

**[FBS] [pre-2018]** The 2003–2007 week-6-forward winner accuracies were:


| Season | Colley | Keener | Massey | Offense–Defense |
| :-- | --: | --: | --: | --: |
| 2003 | 66.30% | 70.29% | 69.62% | 69.18% |
| 2004 | 66.14% | 63.68% | 67.71% | 67.49% |
| 2005 | 67.34% | 64.21% | 67.79% | 64.43% |
| 2006 | 68.74% | 65.74% | 73.23% | 71.95% |
| 2007 | 67.10% | 68.82% | 69.89% | 68.60% |

The predictions exclude weeks 1–5 and FBS–FCS games, include bowls, and do not report lines or ATS outcomes.[^1_7]

The same paper reports hindsight accuracies near 74%–82%, illustrating severe optimism when final-season ratings are used to “predict” games from that season. Those hindsight results are invalid as pregame evidence.[^1_7]

## Barrow et al.

**[FBS] [pre-2018]** Barrow et al. cover 56 seasons from 1956–2011 and compare winning percentage, RPI, least squares, maximum posterior, Keener, PageRank, random walker, and Elo in win-only and score-based versions. They reject equal predictive ability at the 99% confidence level; score-based least squares and random walker are the strongest FBS methods in the reported Nemenyi comparison.[^1_6]

Their random 20-fold cross-validation is a major limitation. It answers “which method reconstructs omitted games from an otherwise nearly complete season?” more than “which method predicts next week from information then available?”

## Fair and Oster

**[FBS] [pre-2018]** Fair and Oster’s sample contains 1,582 games from weeks 6 onward in 1998–2001. Their combined rating regression reaches 72.9% winner accuracy and $R^2=0.382$; the final spread reaches 74.7% and $R^2=0.445$.[^1_2]

When both enter:

- Final spread coefficient: 1.030.
- Combined nonmarket variables: jointly insignificant.
- Joint F statistic: 0.96.
- Home-field term: insignificant after the spread.
- No ATS profit calculation.
- No holdout.
- No vig adjustment.
- No proper probability score.

This directly explains why a broad panel can forecast games well but still fail ATS: it estimates underlying strength, while the closing line already incorporates that common information.

## Prediction Tracker and Massey comparison data

No peer-reviewed FBS study was found that evaluates the modern Prediction Tracker panel against timestamped, reachable US retail prices with walk-forward model fitting.

**No published FBS study found in searched sources.**

Fair and Oster use Massey’s comparison archive as a source for historical rankings, but the systems are evaluated only for 1998–2001 and against a final Las Vegas line. That is the closest verified antecedent, not a modern Prediction Tracker backtest.[^1_2]

## Does any model win?

No verified study found meets the full standard:

- FBS games.
- Chronological holdout or walk-forward evaluation.
- Closing spread from a named or executable source.
- Forecast published before the line timestamp.
- ATS grading.
- Vig incorporated.
- Trial count reported.
- Threshold fixed before the test.
- No leaked final-season ratings.
- Positive and statistically credible net result.

Accordingly: **No published FBS study found in searched sources that validly beats the closing line out of sample.**

# Combining forecasts

## FBS evidence

**[FBS] [pre-2018]** Fair and Oster estimate optimal regression weights across several computer rankings. The combination improves fit over each constituent and reaches 72.9% winner accuracy, but the same observations are used to estimate and evaluate the weights.[^1_1][^1_2]

Some weights are negative, reflecting multicollinearity rather than a stable instruction to reverse a rating. Correlations among the rating predictors range from 0.779 to 0.973, so estimated unconstrained coefficients are highly sensitive to sampling variation.[^1_2]

When the spread is added, the ratings supply no jointly significant incremental information. The result supports combining ratings for football strength estimation but contradicts the claim that an optimized rating ensemble necessarily beats the market.

## Forecast-combination literature

**[other domain – transfer]** A broad forecast-combination literature finds that combining forecasts typically improves robustness because individual models use different information and suffer different misspecification and structural breaks.[^1_20][^1_21]

The “forecast-combination puzzle” is that an equal-weight average often beats weights estimated to be optimal. Finite-sample covariance and weight-estimation error are leading explanations, especially when the number of forecasts is large relative to the training sample.[^1_21][^1_22]

The transfer to Prediction Tracker is plausible but incomplete:

- The panel is large.
- Forecasts are highly correlated.
- Model membership and quality change over time.
- Missing forecasts are nonrandom.
- Several ratings may share the same game data and conceptual structure.
- Publication times differ.
- The median is robust to extreme or stale models.
- Estimated weights can overfit short historical windows.

**Contrary evidence:** Simple averages are not universally optimal. Poor or biased component forecasts can degrade them, and some regularized or selected combinations improve on equal weights. Therefore the correct benchmark set is median, trimmed mean, equal mean, nonnegative ridge, partially pooled model-family weights, and a market-anchored residual ensemble—not one unconstrained OLS fit.[^1_23][^1_24][^1_25]

## Market-anchored combination

The most defensible spread specification is not

$$
\widehat{M}=\sum_k w_k f_k,
$$

but

$$
\widehat{M}_{t}=L_t+\widehat{\Delta}_t,
$$

where $L_t$ is the reachable market spread at decision time and $\widehat{\Delta}_t$ is a heavily regularized estimate of residual mispricing.

This reframes the problem from predicting final margin to predicting the **market’s error**. Fair and Oster’s encompassing result implies that $\widehat{\Delta}$ should usually be small.[^1_1][^1_2]

# Postseason

## Bowl prediction studies

**[FBS] [abstract only] [pre-2018]** Trono’s 2010 JQAS paper examines rating and ranking systems against bowl-game spreads using a record extending back to 1983. Its abstract says an earlier study found two systems “outperformed” the Las Vegas line when model and market disagreed about the favored team, and the 2010 paper adds five seasons and another ranking system.[^1_26]

The betting claim cannot be accepted as valid from the accessible material because the following could not be verified:

- Exact bowl sample size.
- Line source and whether it is open, close, or another snapshot.
- Publication time of each rating.
- ATS win count and confidence interval.
- Vig-adjusted return.
- Number of systems and thresholds tried.
- Whether the disagreement rule was chosen before the added seasons.
- Whether the added seasons are a true untouched test set.

Status: **[uncertain] [pre-2018]** until the full tables and selection protocol are inspected.

## Other postseason evidence

**[FBS] [pre-2018]** Govan et al. include bowls in their weekly foresight accuracy but do not report bowl-only results. Barrow et al. include postseason bowls in their season-level cross-validation, but random folds and pooled reporting prevent a postseason-specific conclusion.[^1_6][^1_7]

**[FBS] [conference paper]** Yurko and Benz deliberately exclude bowls and playoffs because player participation differs, but they do not estimate an opt-out effect.[^1_9]

No published FBS study was found in the searched sources that quantifies, with a pre-specified temporal holdout:

- ATS effect of player opt-outs.
- Interaction between opt-outs and position value.
- Motivation differences.
- Coaching departures.
- Transfer-portal absences.
- Long layoffs.
- Bowl travel or venue.
- Playoff versus non-playoff regimes.

**No published FBS study found in searched sources.**

# Explaining opener versus close

The developer’s result—much better apparent performance against the opener than against the close—is consistent with the literature, not contradictory to it.

## Information incorporation

Fair and Oster show that a multirating combination contains useful information for predicting margins, yet contributes nothing after the final line is known. The natural interpretation is that the market incorporates the same public information between early price formation and close.[^1_1][^1_2]

A Prediction Tracker consensus can therefore be:

- Informative about team strength.
- Correlated with subsequent line movement.
- Better than an early line in retrospective comparison.
- Unable to beat the later line after the market has moved.
- Unbettable against the opener if the panel was published afterward.

The opening-line result is invalid as a profitability claim when the forecast timestamp follows the opener. It remains useful as a **price-discovery diagnostic**: the panel may resemble information that moved the market.

## Selection on disagreement

Selecting games where a rating median differs from the opener by at least five points conditions on:

- Stale or low-limit opener errors.
- Early injury and lineup information.
- Rating releases that followed early market moves.
- Book-specific outliers.
- Differences in home-field or FCS treatment.
- Models that indirectly ingest prior market information.
- Regression noise amplified by selecting extremes.

By close, many of those discrepancies disappear. If the rating remains five points away from the close, Fair and Oster suggest the market should generally receive more weight.[^1_2]

## CLV versus ATS

A model can predict open-to-close movement without beating the close. That can still be valuable if the forecast is available early enough to capture an intermediate line. The correct experiment is:

1. Record exact forecast publication time.
2. Match it to the first executable DraftKings or FanDuel quote after publication.
3. Predict subsequent consensus or same-book closing line.
4. Grade both CLV and ATS.
5. Evaluate whether CLV remains after accounting for stale quotes and limits.
6. Keep thresholds fixed across untouched seasons.

The literature does not establish that Prediction Tracker supplies reachable CLV. It establishes only the broader mechanism that ratings can contain information already represented in the final line.

# Transfer to CFBD and retail books

## What transfers

- **Margin ratings:** Least-squares and state-space team effects remain strong baselines.
- **Score information:** Score-based methods generally outperform win-only rankings for forecasting winners.[^1_7][^1_6]
- **Strong shrinkage:** FBS schedules are sparse and require regularization.
- **Dynamic strength:** Team ratings should evolve during and between seasons.
- **Preseason priors:** Prior performance is the strongest single preseason source; returning production and recruiting add information.[^1_18]
- **Uncertainty modeling:** Transfer activity may change between-season rating variance.[^1_9]
- **Market anchoring:** The reachable spread should be the primary benchmark and usually the strongest input.[^1_1][^1_2]
- **Robust ensembles:** Median and simple combinations are difficult benchmarks for fitted weighting schemes.[^1_20][^1_21]
- **Schedule diagnostics:** Conference isolation and FCS treatment should affect uncertainty.
- **Time-varying HFA:** A single historical home term is unsafe.[^1_14]
- **Garbage-time research:** CFBD play-by-play enables improvements not directly tested in the older final-score literature.


## What does not transfer

- Pre-2018 ATS or market-efficiency estimates without revalidation.
- Final-season ratings used to predict earlier games.
- Random within-season folds.
- Bowl results pooled with regular-season games.
- A universal 4.3-point home field.
- One pooled FCS team without sensitivity testing.
- Winner accuracy as evidence of ATS value.
- Consensus data published after the compared price.
- Closing consensus treated as an executable retail quote.
- Optimized disagreement thresholds chosen after seeing test results.
- Proprietary practitioner accuracy claims without reproducible forecasts.


# Accuracy by week

| Week range | Published result |
| :-- | :-- |
| Preseason | No peer-reviewed FBS game-level spread or ATS accuracy by week found |
| Weeks 1–5 | Govan et al. do not predict; no comparable table found |
| Week 6 onward | Govan et al. report season-level winner accuracy but not weekly accuracy.[^1_7] |
| Bowls | Included in Govan et al. and Barrow et al., but not separately reported.[^1_7][^1_6] |
| Modern 2023–2024 holdout | Yurko–Benz evaluate complete seasons, not week-by-week accuracy.[^1_9] |

**No published FBS study found in searched sources with complete week-by-week closing-line MAE and ATS percentages.**

# Ranked hypotheses

## Highest expected value

### Reachable-price residual model

**Hypothesis:** Predicting residual final margin around the first reachable retail line will outperform a standalone computer-rating fair spread in MAE and calibration.

**Support:** The final spread dominates computer ratings in Fair–Oster.[^1_1][^1_2]

**Test:** Walk forward by season; prediction at timestamp $t$:

$$
\widehat M_t=L_t+\widehat\Delta_t.
$$

Compare with raw panel median, standalone team model, and line-only baseline.

**Falsifier:** Residual model does not reduce holdout MAE or log score versus line-only, or its selected bets do not exceed 52.38% with a credible interval excluding break-even.

### Timestamped CLV

**Hypothesis:** The panel predicts line movement only when its release precedes the evaluated quote; retrospective opener edges disappear after price synchronization.

**Support:** Ratings add no information beyond the final line in Fair–Oster.[^1_2]

**Falsifier:** A timestamped panel release fails to predict same-book movement from the next executable quote, after excluding stale and low-limit observations.

### Strong preseason priors

**Hypothesis:** Prior-season strength plus returning quarterback/production and roster talent reduces weeks 1–5 MAE.

**Support:** Prior-year Sagarin is the strongest single preseason predictor in Singleton’s thesis; returning starters, quarterback and recruiting add information.[^1_18]

**Falsifier:** A current-season-only model has equal or lower untouched early-season MAE and proper probability scores.

### Conservative panel combination

**Hypothesis:** Median, trimmed mean, or ridge combination outperforms unconstrained OLS weights.

**Support:** Forecast-combination research attributes equal-weight robustness to weight-estimation error; Fair–Oster ratings are highly correlated.[^1_22][^1_21][^1_2]

**Falsifier:** Pre-specified unconstrained or adaptive weights deliver lower rolling-origin error across multiple untouched seasons without unstable coefficients.

## High expected value

### Team-specific dynamic variance

**Hypothesis:** Teams with coaching changes, quarterback changes, and heavy portal turnover need larger preseason state variance but not necessarily a shifted mean.

**Support:** Yurko–Benz associate transfer counts with innovation variance, though their simple baseline remains best overall.[^1_9]

**Falsifier:** Covariate-dependent variance fails to improve 2023+ holdout log predictive density, interval coverage, or early-season MAE.

### Schedule-connectivity uncertainty

**Hypothesis:** Ratings from weakly connected schedule regions should be shrunk more and receive wider prediction intervals.

**Support:** FBS has very low algebraic connectivity and high between-method variability.[^1_6]

**Falsifier:** Connectivity and effective-resistance features do not predict absolute rating error, calibration failure, or cross-conference residuals out of sample.

### Separate FCS hierarchy

**Hypothesis:** Hierarchical FCS conference/team effects outperform one universal FCS rating.

**Support:** Karl shows ranking sensitivity to FCS population treatment.[^1_8]

**Falsifier:** Pooled-FCS and hierarchical-FCS models have indistinguishable future FBS-margin error and uncertainty calibration.

### Dynamic HFA

**Hypothesis:** Season-, conference-, venue-, and travel-sensitive home advantage outperforms a fixed historical value.

**Support:** Fair–Oster estimate 4.30 points for 1998–2001, while Karl estimates 2.352 around 2017 and documents schedule-induced bias.[^1_14][^1_2]

**Falsifier:** A fixed HFA has equal or better rolling-origin MAE and calibration after neutral-site classification is audited.

### Market-regime interactions

**Hypothesis:** Any residual edge is concentrated in low-information or low-liquidity periods rather than near close.

**Support:** Computer ratings are encompassed by the final line in Fair–Oster.[^1_2]

**Falsifier:** Model-minus-market residuals show no relationship to time-to-kickoff, limits, book dispersion, or subsequent movement.

## Medium expected value

### Diminishing-margin transformation

**Hypothesis:** Capped, logarithmic, or hazard-scaled margins outperform raw final margin.

**Support:** Harville proposes explicit diminishing-return transformations; Gill–Keating compare related robust rating choices.[^1_19][^1_15]

**Falsifier:** Raw-margin ratings consistently win on future-game MAE and proper scores across pre-specified cap values.

### Garbage-time-adjusted margin

**Hypothesis:** Removing possessions after extreme pregame-adjusted win probability improves next-game strength estimates.

**Support:** Mechanism is consistent with Harville’s concern about running up scores, but no direct published FBS validation was found.[^1_13][^1_19]

**Falsifier:** Adjusted margins do not improve rolling-origin MAE, especially after excluding personnel development and backup-quarterback games.

### Offense/defense decomposition

**Hypothesis:** Separate offensive and defensive latent ratings improve total and margin forecasts versus one net rating.

**Support:** Govan’s offense–defense model is competitive with established rankings, though not consistently superior.[^1_7]

**Falsifier:** Separate components add no holdout likelihood or MAE improvement after pace and opponent adjustment.

### Score-state weighting

**Hypothesis:** Early competitive possessions should receive more team-strength weight than late possessions in decided games.

**Support:** Existing literature supports diminishing returns to final margin but does not identify the optimal play-level function.

**Falsifier:** Weighting by score state does not improve future-game margin prediction relative to raw opponent-adjusted EPA.

### Robust residual distribution

**Hypothesis:** Student-$t$ or mixture errors improve interval calibration relative to Gaussian errors.

**Support:** Harville’s practitioner implementation has used heavy-tailed residuals and empirical posterior residual distributions.[^1_13]

**Falsifier:** Gaussian errors deliver equal or better holdout log scores and nominal interval coverage.

## Postseason hypotheses

### Bowl-specific state reset

**Hypothesis:** Bowl games require a separate variance and mean adjustment based on opt-outs, portal entries, coaching changes, and layoff.

**Support:** Yurko–Benz exclude bowls because participation changes; Trono treats bowls as a distinct prediction problem.[^1_26][^1_9]

**Falsifier:** A pooled regular-season model has equal or better bowl MAE and calibration after roster availability is known.

### Position-weighted opt-outs

**Hypothesis:** Quarterback, offensive-line, cornerback and edge absences have larger spread effects than equal counts of lower-leverage absences.

**Support:** Mechanism only; no direct published FBS effect-size study found.

**Falsifier:** Position-weighted availability adds no incremental performance over total missing starts or market movement.

### Bowl motivation proxies

**Hypothesis:** Surprise selection, coaching departure, prior playoff contention and opponent quality affect bowl residuals.

**Support:** Anecdotal mechanism; no validated FBS market study found.

**Falsifier:** Pre-specified motivation variables have zero stable effect over multiple untouched bowl seasons.

# Master table

| Citation | Venue | Peer reviewed | Evidence | Seasons and n | Line used | Target | Method | Main result | Validation | Leakage risk | Status |
| :-- | :-- | --: | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Harville (1977), “The Use of Linear-Model Methodology to Rate High School or College Football Teams”[^1_3] | JASA | Y | [FBS] [pre-2018] | Historical football sample; n not recovered | n/a | Margin/rating | Linear/mixed model | Establishes margin-difference and HFA formulation | Primarily model development | Moderate if fitted season reused | Untested |
| Massey (1997), “Statistical Models Applied to the Rating of Sports Teams”[^1_4][^1_5] | Bluefield College thesis | N | [FBS] [pre-2018] | Application details not fully recovered | n/a | Rating/margin | Least squares | Canonical $X'Xr=X'y$ sports rating | Thesis examples | Depends on use | Untested |
| Keener (1993), “The Perron-Frobenius Theorem and the Ranking of Football Teams” | SIAM Review | Y | [FBS] [pre-2018] | Methodological examples | n/a | Ranking | Eigenvector | Establishes Perron ranking | Not a market test | High if final-season ranking used | Untested |
| Colley (2002), “Colley’s Bias Free College Football Ranking Method” | Method paper | N | [FBS] [pre-2018] | Methodological | n/a | Win-loss ranking | Linear system with shrinkage | Produces margin-free ratings | No prospective market validation | Low structurally; no margin target | Untested |
| Mease (2003), penalized-likelihood college-football ranking | Statistical methodology | Y | [FBS] [pre-2018] | Seasons/sample not recovered | n/a | Win-loss ranking | Penalized probit | Handles undefeated/winless teams | Ranking analysis | No prospective scoring | Untested |
| Fair \& Oster (2007), “College Football Rankings and Market Efficiency”[^1_1][^1_2] | Journal of Sports Economics | Y | [FBS] [pre-2018] | 1998–2001; n=1,582 | Final Gold Sheet Las Vegas line | Margin, winner, market encompassing | OLS forecast combination | 72.9% winners and $R^2=.382$; line 74.7% and $R^2=.445$; ratings jointly insignificant with line | In-sample | High for coefficient selection; no ATS rule | Untested |
| Gill \& Keating (2009), “Assessing Methods for College Football Rankings”[^1_15] | JQAS | Y | [FBS] [pre-2018] | 1930–2007 referenced; exact n unavailable | n/a | Winner/margin error | Least squares and robust variants | Large-margin treatment evaluated; exact table inaccessible | Leave-one-out CV | Non-temporal CV | Untested |
| Govan, Langville \& Meyer (2009), “Offense-Defense Approach to Ranking Team Sports”[^1_7] | JQAS | Y | [FBS] [pre-2018] | 2003–2007; n not reported | n/a | Winner | Colley, Keener, Massey, ODM | Foresight ranges: 63.68%–73.23%; Massey generally strongest | Weekly from week 6 | Low after week 6; bowls pooled | Holds |
| Trono (2010), “Rating/Ranking Systems, Post-Season Bowl Games, and ‘The Spread’”[^1_26] | JQAS | Y | [FBS] [abstract only] [pre-2018] | 1983 onward; n unavailable | “Las Vegas” spread; timing unavailable | Bowl ATS/disagreement | Multiple rating systems | Abstract reports prior “outperformance”; exact record unavailable | Extension adds five seasons | Threshold and line-timing unknown | Untested |
| Barrow et al. (2013), “Ranking Rankings”[^1_6] | Mathematical ranking paper | Y/working version located | [FBS] [pre-2018] | 1956–2011; 56 seasons; mean 645.6 games | n/a | Winner | 16 versions of 8 methods | Score-based L2 and random walker significantly strongest in FBS comparison | 20-fold CV repeated 100 times | High temporal leakage | Invalid for prospective accuracy |
| Karl (2012/2014), “The Sensitivity of College Football Rankings to Several Modeling Choices”[^1_8] | JQAS | Y | [FBS] [pre-2018] | 2008–2011; pre-bowl games | n/a | Ranking | Probit/logit GLMM | Link, approximation, variance and FCS treatment alter relevant ranks | In-sample sensitivity | No forecast test | Untested |
| Karl (2020), “Avoiding Bias Due to Nonrandom Scheduling…”[^1_14] | arXiv/statistical paper | N/version status uncertain | [FBS] [mechanism only] | 2000–2017; 18 seasons | n/a | HFA | Fixed and random effects | Random-effects HFA 3.37 when simulated truth 3.00; fixed effects recover 3.00 | Simulation + historical fits | None for mechanism | Holds |
| Padron \& Sinsay (2013), “Upset Prediction in College Football”[^1_10] | Stanford CS229 project | N | [FBS] [student project] | 2013 season | Betting spread; timing unclear | Upset/winner | Supervised classifiers | Difficulty with favorites of at least seven points | Unclear split | High | Invalid as betting evidence |
| Singleton (2019), “Using Recruiting Rankings and Returning Team Measurements…”[^1_18] | University thesis | N | [FBS] | Recruiting era sample; exact n unavailable | n/a | Season performance | Multiple regression | Prior Sagarin strongest single predictor; final $R^2\approx53.3\%$ | In-sample/model selection | Not game-level | Untested |
| Yurko \& Benz (2025), “College Football Volatility: A Bayesian State-Space Model…”[^1_9] | NESSIS conference | N | [FBS] | 2014–2024; n=9,003; 2023–24 holdout | n/a | Margin | Bayesian AR state-space | Baseline dynamic model best holdout RMSE/ELPD; transfer model next | Temporal holdout | Low; only two test seasons | Holds |
| Glickman \& Stern (1998), state-space model of NFL scores | JASA | Y | [NFL – transfer] [pre-2018] | NFL 1988–1993 | n/a | Score/margin | Bayesian state space | Foundational dynamic score model | Future-game prediction | Different league | Holds |
| Paul \& Weinbach (2005), “Bettor Preferences and Market Efficiency in Football Totals” | Journal of Economics and Finance | Y | Already in hand | Not re-summarized | Totals | Total | Market study | Already in hand | Already in hand | Already in hand | Untested |
| Paul \& Weinbach (2002), “Market Efficiency and a Profitable Betting Rule…” | Journal of Sports Economics | Y | [NFL – transfer] already in hand | Not re-summarized | Totals | Total | Market study | Already in hand | Already in hand | Already in hand | Untested |
| Arscott (2023), “Market Efficiency and Censoring Bias in College Football Totals Betting” | Journal of Sports Economics | Y | [FBS totals] already in hand | Not re-summarized | Totals | Total | Market/censoring | Already in hand | Already in hand | Already in hand | Holds |
| Shank (2018), “Is the NFL Betting Market Still Inefficient?” | Journal of Economics and Finance | Y | [NFL – transfer] already in hand | Not re-summarized | Spread | ATS | Market study | Already in hand | Already in hand | Already in hand | Untested |
| Kelly \& West, “Bettor Biases and Market Efficiency in the NFL Totals Market” | Metadata not reverified | Unclear | [NFL – transfer] already in hand | Not re-summarized | Totals | Total | Market study | Already in hand | Already in hand | Already in hand | Untested |
| AABRI NFL preseason totals paper | AABRI | Unclear | [NFL – transfer] already in hand | Not re-summarized | Preseason total | Total | Market study | Already in hand | Already in hand | Already in hand | Untested |
| 2010 AEA conference paper, “Betting Markets and Market Efficiency: Evidence from College Football” | AEA conference | N | [FBS] already in hand | Not re-summarized | Unverified | Market efficiency | Market study | Already in hand | Already in hand | Already in hand | Untested |

# Author-lead results

| Author lead | Verified college-football work |
| :-- | :-- |
| David Harville | Yes: 1977 linear-model football ratings; later model-based FBS methodology.[^1_3][^1_13] |
| Hal Stern | No distinct FBS predictive study verified in searched sources; coauthor of foundational NFL state-space work. |
| Mark Glickman | No published FBS application verified; NFL state-space work transfers methodologically. |
| Wesley Colley | Yes: Colley matrix methodology for college-football ranking. |
| Kenneth Massey | Yes: 1997 least-squares sports-rating thesis and historical comparison archive.[^1_4][^1_5] |
| Ray Stefani | Football-rating work exists, but no direct modern FBS closing-line study was verified. |
| James Keener | Yes: Perron–Frobenius football-ranking method. |
| Ryan Gill and Jerome Keating | Yes: 2009 JQAS comparison of college-football ranking methods.[^1_15] |
| John Trono | Yes: bowl ratings and spread study.[^1_26] |
| Andrew Karl | Yes: FBS GLMM ranking sensitivity and home-field/scheduling work.[^1_8][^1_14] |
| Ron Yurko and Luke Benz | Yes: 2025 FBS Bayesian state-space conference study.[^1_9] |

# Coverage log

| Sub-question | Source classes searched | Representative queries | Sources found | Gaps |
| :-- | :-- | :-- | --: | :-- |
| Margin ratings | Journals, Scholar/Semantic Scholar, repositories, practitioner methods | “least squares ratings college football”; “Massey ratings”; “Harville college football rating” | 8+ | Gill–Keating full numeric tables inaccessible; no modern ATS replication |
| Win-loss rankings | Journals, SIAM/mathematics, BCS methodology, repositories | “Colley matrix”; “Keener football ranking”; “BCS computer rankings margin victory” | 7+ | No modern closing-line test of Colley/PageRank located |
| Dynamic models | JASA leads, arXiv, conferences, repositories | “Elo college football”; “Bayesian state space model college football”; “Kalman filter FBS” | 5 direct/transfer | No direct published FBS Kalman-filter ATS study found |
| Statistical/ML | JSA, JQAS, arXiv, ProQuest/university projects, conference projects | “predicting college football point spread machine learning”; “college football neural network spread” | Several projects; few direct published studies | No qualifying chronological FBS closing-line ML test found |
| Preseason priors | University repositories, practitioner methods, conference paper | “college football recruiting returning starters prediction”; “preseason FPI methodology” | 6+ | No peer-reviewed accuracy-by-week table |
| Schedule sparsity | JQAS/mathematical ranking papers, GLMM papers | “college football schedule connectivity ranking”; “FCS handling ratings” | 4+ | No quantified incremental ATS effect |
| MOV treatment | JASA/TAS/JQAS, practitioner methodology | “college football margin cap rating”; “Harville hazard margin victory” | 5+ | Exact Gill–Keating error table unavailable |
| Head-to-head comparisons | JQAS, JSE, Massey archive references, repositories | “college football rating system accuracy point spread”; “Prediction Tracker accuracy” | 5 core comparisons | No peer-reviewed modern Prediction Tracker test found |
| Combining forecasts | JSE plus IJF/forecast-combination literature | “forecast combination sports betting”; “forecast combination puzzle simple average” | 8+ general; 1 core FBS | No out-of-sample FBS market panel ensemble study |
| Postseason | JQAS, repositories, conference studies | “bowl game prediction model”; “college football opt-out spread study” | 3 direct/partial | Trono full tables inaccessible; no quantified opt-out/motivation/layoff study found |
| Market explanation | JSE, RePEc, market-efficiency literature | “college football rankings market efficiency”; “computer ratings Las Vegas spread” | Fair–Oster plus already-in-hand market papers | No post-2018 retail-book replication |
| Author leads | Publisher pages, repositories, practitioner sites | Individual author names plus “college football” | Work verified for Harville, Colley, Massey, Keener, Gill, Trono, Karl, Yurko | No distinct Hal Stern or Mark Glickman FBS paper verified |

Source classes explicitly searched included peer-reviewed sports-economics and sports-analytics journals, mathematical and statistical journals, RePEc/IDEAS, SSRN leads, arXiv, Semantic Scholar, university repositories, conference material, practitioner documentation, and public project reports. No relevant MIT Sloan paper was verified for this assignment. ProQuest results were sparse or inaccessible, and Google Scholar could not be directly inspected as a complete result set.

# Access limitations

The research cutoff is **September 30, 2026**. Several publisher pages exposed only abstracts or metadata; some De Gruyter/JQAS PDFs were restricted, SSRN downloads were blocked, and the full numeric tables for Gill–Keating and Trono could not be recovered. Exact conclusions were therefore not inferred from inaccessible tables.

The literature itself has major coverage limitations: most direct market evidence is pre-2018; many ranking papers optimize retrospective ordering rather than prospective forecasts; random-fold validation is common; sportsbook, timestamp, vig, and trial-count documentation is usually absent; and modern proprietary systems such as SP+ and FPI lack peer-reviewed closing-line replications.

<span style="display:none">[^1_100][^1_101][^1_102][^1_103][^1_104][^1_105][^1_106][^1_107][^1_108][^1_109][^1_110][^1_111][^1_112][^1_113][^1_114][^1_115][^1_116][^1_117][^1_118][^1_119][^1_120][^1_121][^1_122][^1_123][^1_124][^1_125][^1_126][^1_127][^1_128][^1_129][^1_130][^1_131][^1_132][^1_133][^1_134][^1_135][^1_136][^1_137][^1_138][^1_139][^1_140][^1_141][^1_142][^1_143][^1_144][^1_145][^1_146][^1_147][^1_148][^1_149][^1_150][^1_151][^1_152][^1_153][^1_154][^1_155][^1_156][^1_157][^1_158][^1_159][^1_160][^1_161][^1_162][^1_163][^1_164][^1_165][^1_166][^1_167][^1_168][^1_169][^1_170][^1_171][^1_172][^1_173][^1_174][^1_175][^1_176][^1_177][^1_178][^1_179][^1_180][^1_181][^1_182][^1_183][^1_184][^1_185][^1_186][^1_187][^1_188][^1_189][^1_190][^1_191][^1_192][^1_193][^1_194][^1_195][^1_196][^1_197][^1_198][^1_199][^1_200][^1_201][^1_202][^1_203][^1_204][^1_205][^1_206][^1_207][^1_208][^1_209][^1_210][^1_211][^1_212][^1_213][^1_214][^1_215][^1_216][^1_217][^1_218][^1_219][^1_220][^1_221][^1_222][^1_223][^1_224][^1_225][^1_226][^1_227][^1_228][^1_229][^1_230][^1_231][^1_232][^1_233][^1_234][^1_235][^1_236][^1_237][^1_238][^1_239][^1_240][^1_241][^1_242][^1_243][^1_244][^1_245][^1_246][^1_247][^1_248][^1_249][^1_250][^1_251][^1_252][^1_253][^1_254][^1_255][^1_256][^1_257][^1_258][^1_259][^1_260][^1_261][^1_262][^1_263][^1_264][^1_265][^1_266][^1_267][^1_268][^1_269][^1_27][^1_270][^1_271][^1_272][^1_273][^1_274][^1_275][^1_276][^1_277][^1_278][^1_279][^1_28][^1_280][^1_281][^1_282][^1_283][^1_284][^1_285][^1_286][^1_287][^1_288][^1_289][^1_29][^1_290][^1_291][^1_292][^1_293][^1_294][^1_295][^1_296][^1_297][^1_298][^1_299][^1_30][^1_300][^1_301][^1_302][^1_303][^1_304][^1_305][^1_306][^1_307][^1_308][^1_309][^1_31][^1_310][^1_311][^1_312][^1_313][^1_314][^1_315][^1_316][^1_317][^1_318][^1_319][^1_32][^1_320][^1_321][^1_322][^1_323][^1_324][^1_325][^1_326][^1_327][^1_328][^1_329][^1_33][^1_330][^1_331][^1_332][^1_333][^1_334][^1_335][^1_336][^1_337][^1_338][^1_339][^1_34][^1_340][^1_341][^1_342][^1_343][^1_344][^1_345][^1_346][^1_347][^1_348][^1_349][^1_35][^1_350][^1_351][^1_352][^1_353][^1_354][^1_355][^1_356][^1_357][^1_358][^1_359][^1_36][^1_360][^1_361][^1_362][^1_363][^1_364][^1_365][^1_366][^1_367][^1_368][^1_369][^1_37][^1_370][^1_371][^1_372][^1_373][^1_374][^1_375][^1_376][^1_377][^1_378][^1_379][^1_38][^1_380][^1_381][^1_382][^1_383][^1_384][^1_385][^1_386][^1_387][^1_388][^1_389][^1_39][^1_390][^1_391][^1_392][^1_393][^1_394][^1_395][^1_396][^1_397][^1_398][^1_399][^1_40][^1_400][^1_401][^1_402][^1_403][^1_404][^1_405][^1_406][^1_407][^1_408][^1_409][^1_41][^1_410][^1_411][^1_412][^1_413][^1_414][^1_415][^1_416][^1_417][^1_418][^1_419][^1_42][^1_420][^1_421][^1_422][^1_423][^1_424][^1_425][^1_43][^1_44][^1_45][^1_46][^1_47][^1_48][^1_49][^1_50][^1_51][^1_52][^1_53][^1_54][^1_55][^1_56][^1_57][^1_58][^1_59][^1_60][^1_61][^1_62][^1_63][^1_64][^1_65][^1_66][^1_67][^1_68][^1_69][^1_70][^1_71][^1_72][^1_73][^1_74][^1_75][^1_76][^1_77][^1_78][^1_79][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://ideas.repec.org/a/sae/jospec/v8y2007i1p3-18.html

[^1_2]: https://ditraglia.com/erm/Fair-Oster-2007.pdf

[^1_3]: https://www.tandfonline.com/doi/abs/10.1080/01621459.1977.10480991

[^1_4]: https://search.r-project.org/CRAN/refmans/comperank/html/massey.html

[^1_5]: https://repository.usfca.edu/cgi/viewcontent.cgi?article=1039\&context=math

[^1_6]: https://www.semanticscholar.org/paper/Ranking-rankings:-an-empirical-comparison-of-the-of-Barrow-Drayer/c399edd12a4fe6f4f2877e0b8da9a6b830056410

[^1_7]: http://carlmeyer.com/pdfFiles/OffenseDefenseModel.pdf

[^1_8]: http://arxiv.org/pdf/1403.7642.pdf

[^1_9]: https://www.nessis.org/nessis25/Ron-Yurko.pdf

[^1_10]: https://cs229.stanford.edu/proj2013/PadronSinsay-UpsetPredictioninCollegeFootball.pdf

[^1_11]: https://www.espn.com/college-football/story/\_/id/48306284/2026-college-football-sp+-rankings-138-fbs-teams

[^1_12]: https://www.espn.com/blog/statsinfo/post/\_/id/129505/ohio-state-is-no-1-in-preseason-fpi-1-0

[^1_13]: https://davidharville.com/collegefootballratingspredictions/methodology/

[^1_14]: https://arxiv.org/html/1806.08059v2

[^1_15]: https://www.degruyterbrill.com/document/doi/10.2202/1559-0410.1172/html

[^1_16]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7861217/

[^1_17]: https://content.iospress.com/download/journal-of-sports-analytics/jsa190348?id=journal-of-sports-analytics/jsa190348

[^1_18]: https://libres.uncg.edu/ir/asu/f/Singleton_Sydney_2019_Thesis.pdf

[^1_19]: https://www.arxiv.org/pdf/1403.7642.pdf

[^1_20]: https://ar5iv.labs.arxiv.org/html/1505.00475

[^1_21]: https://arxiv.org/html/2205.04216v2

[^1_22]: https://journal.r-project.org/articles/RJ-2018-052/

[^1_23]: https://economics.ucr.edu/repec/ucr/wpaper/202514.pdf

[^1_24]: https://core.ac.uk/download/pdf/326834022.pdf

[^1_25]: https://www.diva-portal.org/smash/get/diva2:1585936/FULLTEXT01.pdf

[^1_26]: https://ideas.repec.org/a/bpj/jqsprt/v6y2010i3n6.html

[^1_27]: fbs-totals-frontier-models.md

[^1_28]: https://cowles.yale.edu/sites/default/files/2022-08/d1381.pdf

[^1_29]: https://discovery.researcher.life/article/a-predictive-metamodel-for-college-football/2f60b334c4fa3bb8a022551b630bda0f

[^1_30]: https://air.uniud.it/bitstream/11390/1113050/4/main.pdf

[^1_31]: http://users.dimi.uniud.it/~massimo.franceschet/teaching/datascience/network/massey.html

[^1_32]: https://cowles.yale.edu/node/140186

[^1_33]: https://arxiv.org/html/1701.03363v1

[^1_34]: https://www.academia.edu/51265238/Minimizing_Game_Score_Violations_in_College_Football_Rankings

[^1_35]: https://cowles.yale.edu/node/145231

[^1_36]: https://journals.sagepub.com/doi/abs/10.1177/22150218251365223

[^1_37]: https://digitalcommons.unf.edu/cgi/viewcontent.cgi?article=1000\&context=bmgt_facpub

[^1_38]: https://arxiv.org/pdf/2201.05249v1.pdf

[^1_39]: https://masseyratings.com/theory/massey97.pdf

[^1_40]: https://titan.dcs.bbk.ac.uk/~ale/dsta/dsta-7/Massey_ranking/lm-ch2-massey.pdf

[^1_41]: https://www.academia.edu/23844617/Assessing_Methods_for_College_Football_Rankings

[^1_42]: https://www.academia.edu/15262061/A_Consistent_Weighted_Ranking_Scheme_With_an_Application_to_NCAA_College_Football_Rankings

[^1_43]: https://www.smcvt.edu/wp-content/uploads/2021/08/SpanningTrees3rdAnnualConf.pdf

[^1_44]: https://ww2.amstat.org/mam/2010/essays/PasteurPredictive.pdf

[^1_45]: https://www.cbssports.com/college-football/news/sagarin-changes-formula-finally-removes-margin-of-victory/

[^1_46]: https://www.academia.edu/55239332/College_Football_Rankings_Do_the_Computers_Know_Best

[^1_47]: https://www.cbsnews.com/texas/news/throw-out-the-scores-the-bcs-does/

[^1_48]: https://bleacherreport.com/articles/94216-inside-the-bcs-computer-ranking-black-box

[^1_49]: https://ww2.amstat.org/mam/2010/essays/PasteurRetrodictive.pdf

[^1_50]: https://harvardsportsanalysis.org/2011/11/making-sense-of-the-chaos-a-bcs-prediction-model/

[^1_51]: https://public.websites.umich.edu/~bwest/inpress_063008.pdf

[^1_52]: https://reference-global.com/2/v2/download/article/10.1515/ijcss-2017-0014.pdf

[^1_53]: https://en.wikipedia.org/wiki/2007_BCS_computer_rankings

[^1_54]: https://statsinthewild.com/2026/07/28/bcs-methods-review/

[^1_55]: https://www.theringer.com/2021/12/03/college-football/college-football-playoff-bcs-computer-formulas-ranking-system

[^1_56]: https://en.wikipedia.org/wiki/2006_BCS_computer_rankings

[^1_57]: https://scholarcommons.sc.edu/cgi/viewcontent.cgi?article=1519\&context=senior_theses

[^1_58]: https://bigballsdata.com/docs/elo

[^1_59]: https://myweb.ecu.edu/robbinst/PDFs/Elo Model Convergence Final.pdf

[^1_60]: https://arxiv.org/pdf/2403.03862.pdf

[^1_61]: https://myweb.ecu.edu/robbinst/PDFs/Betting on FPI - DSI.pdf

[^1_62]: https://www.math.ucla.edu/~bertozzi/WORKFORCE/REU 2013/Sports Rankings Group/Presentation.pdf

[^1_63]: https://libres.uncg.edu/ir/asu/f/Andrews_Zachary_2019_Thesis.pdf

[^1_64]: https://cs229.stanford.edu/proj2015/101_poster.pdf

[^1_65]: https://github.com/reggiebain/cfb-modeling-erdos

[^1_66]: https://openjournals.maastrichtuniversity.nl/Marble/article/download/613/428

[^1_67]: https://www.math.ucla.edu/~bertozzi/WORKFORCE/REU 2013/Sports Rankings Group/Final_Report.pdf

[^1_68]: https://courses.cs.vt.edu/cs5824/Fall15/project_reports/sullivan_cronin.pdf

[^1_69]: https://gridpex.com/methodology

[^1_70]: https://www.atiner.gr/presentations/Theodore-Trafalis.pdf

[^1_71]: http://arno.uvt.nl/show.cgi?fid=160932

[^1_72]: https://publikacio.uni-eszterhazy.hu/8836/1/202_214_p%C3%A1l.pdf

[^1_73]: https://arxiv.org/html/2207.13747v1

[^1_74]: https://www.covers.com/ncaaf/college-football-ai-predictions-week-4-2026

[^1_75]: https://content.iospress.com/download/journal-of-sports-analytics/jsa190314?id=journal-of-sports-analytics/jsa190314

[^1_76]: https://www.growkudos.com/publications/10.3233%2Fjsa-190314/reader

[^1_77]: http://arxiv.org/pdf/physics/0607064.pdf

[^1_78]: https://www.espn.com/blog/statsinfo/post/\_/id/122612/an-inside-look-at-college-fpi

[^1_79]: https://www.nessis.org/nessis17/Egros.pdf

[^1_80]: https://scispace.com/papers/a-compound-framework-for-sports-results-prediction-a-29glfoncgn

[^1_81]: https://www.espn.com/blog/statsinfo/post/\_/id/109828/reintroducing-espns-college-football-power-index

[^1_82]: https://academic.oup.com/jrsssc/advance-article/doi/10.1093/jrsssc/qlag032/8704597

[^1_83]: https://en.wikipedia.org/wiki/Football_Power_Index

[^1_84]: http://constantinou.info/downloads/papers/smartDataFootball.pdf

[^1_85]: https://api.drum.lib.umd.edu/server/api/core/bitstreams/e23af22f-a2bb-47b5-9e19-7394d9ccedfc/content

[^1_86]: https://honors.libraries.psu.edu/files/final_submissions/9004

[^1_87]: https://cs229.stanford.edu/proj2016/report/WadsworthVera-PredictingPointSpreadinNFLGames-report.pdf

[^1_88]: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00061/full

[^1_89]: https://pdfs.semanticscholar.org/8494/a0cf105b3afb8b25c724e55ca90effd517e5.pdf

[^1_90]: https://cs229.stanford.edu/proj2010/LiuLai-BeatingTheNCAAFootballPointSpread.pdf

[^1_91]: https://iq.qu.edu/experiential-learning/course-projects-and-capstones/student-projects/predicting-nfl-total-score-and-point-spread-bets/

[^1_92]: https://www.semanticscholar.org/paper/Beating-the-NCAA-Football-Point-Spread-Liu/9976b09876dcfb4ce0aa36551e993ad20a49e06e

[^1_93]: https://www.frontiersin.org/articles/10.3389/fspor.2025.1638446/full

[^1_94]: https://link.springer.com/article/10.1007/s10479-022-05063-x

[^1_95]: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00061/pdf

[^1_96]: https://pdfs.semanticscholar.org/89bf/a529c355e09a9c7e8a1d4f5d1e6e08558c69.pdf

[^1_97]: https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1638446/full

[^1_98]: https://cfb.terranalytics.com/methodology/model_explainer.pdf

[^1_99]: https://journals.sagepub.com/doi/10.3233/JSA-190314

[^1_100]: https://ideas.repec.org/a/eee/intfor/v28y2012i2p543-552.html

[^1_101]: https://scispace.com/journals/journal-of-quantitative-analysis-in-sports-11mz15l2/2008

[^1_102]: https://dl.acm.org/doi/pdf/10.1613/jair.1.13509

[^1_103]: https://arxiv.org/pdf/1912.11762.pdf

[^1_104]: http://www.nessis.org/nessis09/Wigness.pdf

[^1_105]: http://jvlone.com/sportsdocs/AttendanceBowlGamesAnalysis2010.pdf

[^1_106]: https://www.scribd.com/document/830468672/Case-study-3-4-Exercise-1-by-group

[^1_107]: https://cs.iusb.edu/technical_reports/TR-20240429-1_Goldstein.pdf

[^1_108]: https://www.scribd.com/document/629678973/The-Application-of-Machine-Learning-for-Sport-Result-Prediction-A-Review

[^1_109]: https://scispace.com/papers/a-comparative-analysis-of-data-mining-methods-in-predicting-1evs5t90jl

[^1_110]: https://nimodian.com/sports/soccer/college-football-picks/

[^1_111]: https://datafield.dev/sports-betting-textbook/part-04/chapter-20/exercises.html

[^1_112]: https://datafield.dev/sports-betting-textbook/part-04/chapter-20/case-study-01.html

[^1_113]: https://bcsfootball.org/fpi-vs-sp-vs-elo-college-football-rankings-2026/

[^1_114]: https://gopherhole.com/boards/threads/is-it-a-bit-hard-for-minn-fans-to-stomach-espns-initial-college-football-power-index-fpi-ranking-of-63.121831/

[^1_115]: https://www.predictium.ai/cfb/about

[^1_116]: https://www.thepredictiontracker.com/awards2009.html

[^1_117]: https://libjournals.unca.edu/ncur/wp-content/uploads/2021/02/2913-Singleton-Sydney-FINAL.pdf

[^1_118]: https://247sports.com/college/minnesota/article/espn-released-its-new-fpi-rankings-this-week-heres-what-they-predict-for-maryland-in-2026-288244429/

[^1_119]: https://mfootballanalytics.com/2021/08/17/creating-a-college-football-win-totals-model/

[^1_120]: https://www.edgelabs.bet/cfb

[^1_121]: https://sports.yahoo.com/articles/espn-releases-college-football-power-155822202.html

[^1_122]: https://personal.denison.edu/~lalla/MCURCSM2011/4.pdf

[^1_123]: https://bcsfootball.org/eye-test-vs-analytics-college-football-rankings-2026/

[^1_124]: https://bcsfootball.org/espn-fpi-vs-sp-plus-vs-elo-college-football-rankings-2026/

[^1_125]: https://www.novakingsports.com/college-football/analytics/poll-factors

[^1_126]: https://www.espn.com/college-football/story/\_/id/49868647/2026-college-football-sp+-rankings-all-138-fbs-teams

[^1_127]: https://www.reddit.com/r/CFB/comments/1usrva1/on3_espn_fpi_ranks_college_footballs_toughest/

[^1_128]: https://en.wikipedia.org/wiki/Colley_Matrix

[^1_129]: https://sites.northwestern.edu/msia/2016/12/20/simple-college-football-rankings-system/

[^1_130]: http://www.tandfonline.com/doi/abs/10.1080/00036840903286331

[^1_131]: http://snap.stanford.edu/class/cs224w-2015/projects_2015/A_Network-Based_Approach_to_Ranking_College_Football_Teams.pdf

[^1_132]: https://thepowerrank.com/guide-cfb-rankings/

[^1_133]: https://collegefootballnews.com/college-football/college-football-strength-of-schedule-rankings-2026-spring

[^1_134]: https://www.reddit.com/r/CFB/comments/1o1f93b/starting_this_year_the_playoff_committee_will_use/

[^1_135]: https://www.jmlr.org/papers/volume15/osting14a/osting14a.pdf

[^1_136]: https://www.footballstudyhall.com/2019/1/30/18202607/2007-college-football-rankings

[^1_137]: https://www.ncaa.com/\_flysystem/public-s3/images/2024/10/30/massey.pdf

[^1_138]: https://www.footballstudyhall.com/2019/2/26/18241587/2011-college-football-rankings

[^1_139]: https://www.timetravelsports.com/colfb/

[^1_140]: https://www.secrant.com/rant/sec-football/can-someone-explain-the-sagarin-ratings/22447314/

[^1_141]: https://fbratings.com/index.php?id=david-rothman-rankings

[^1_142]: https://www2.gwu.edu/~forcpgm/2007-001.pdf

[^1_143]: https://masseyratings.com/faq.php

[^1_144]: https://www.footballstudyhall.com/2019/4/4/18295248/2015-college-football-rankings

[^1_145]: http://talismanred.com/ratings/cf/explain.shtml

[^1_146]: https://www.footballstudyhall.com/2019/2/8/18217388/2008-college-football-rankings

[^1_147]: https://www.nber.org/system/files/working_papers/w13596/w13596.pdf

[^1_148]: https://bcsfootball.org/margin-of-victory-college-football-rankings-2026/

[^1_149]: https://ideas.repec.org/p/ysm/wpaper/amz2377.html

[^1_150]: https://ditraglia.com/econ224/lab06.pdf

[^1_151]: https://fivethirtyeight.com/features/losing-money-betting-on-college-football-this-year-youre-not-alone/

[^1_152]: https://www.espn.com/college-football/insider/story/\_/id/32140951/how-sp+-computer-ratings-fared-vs-betting-spreads-cfb-week-1-games

[^1_153]: https://www.collegefootballpoll.com/news/congrove-outperforms-bcs-computer-component-rankers/

[^1_154]: https://www.footballstudyhall.com/2014/12/30/7464777/college-football-ratings-redesign-sandp-plus

[^1_155]: https://www.reddit.com/r/CFB/comments/18bq3il/2023_predictive_computer_performance_results_are/

[^1_156]: https://www.reddit.com/r/CFB/comments/574tgn/prediction_tracker_computer_accuracy_rankings_1/

[^1_157]: https://www.uni-bamberg.de/fileadmin/xai/studies/theses/2026/2026_Bachelorthesis_Di_Bao.pdf

[^1_158]: https://pdfs.semanticscholar.org/5335/8d185a9c95de83a9593fbea64608ea1f58ec.pdf

[^1_159]: https://documentserver.uhasselt.be/bitstream/1942/47164/1/7f3a1e02-5eb2-4db3-892f-e1740dda3333.pdf

[^1_160]: https://ouci.dntb.gov.ua/en/works/7XnRZxYl/

[^1_161]: https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2026.1754408/full

[^1_162]: http://arno.uvt.nl/show.cgi?fid=169754

[^1_163]: https://www.academia.edu/59346553/The_wisdom_of_ignorant_crowds_Predicting_sport_outcomes_by_mere_recognition

[^1_164]: https://link.springer.com/article/10.1186/s40537-026-01369-w

[^1_165]: https://www.lukebornn.com/papers/yuan_jqas_2014.pdf

[^1_166]: https://www.irjet.net/archives/V8/i3/IRJET-V8I3366.pdf

[^1_167]: https://kickoffpredictions.com/public/expert-match-insights/ncaa-football-predictions-usa-today-data-driven-analysis

[^1_168]: https://rsisinternational.org/journals/common/author/uploads/manuscripts/ms_1766789422_8359.docx

[^1_169]: https://footballproofai.com/guides/ai-football-prediction-models

[^1_170]: https://www.frontiersin.org/journals/applied-mathematics-and-statistics/articles/10.3389/fams.2026.1754408/pdf

[^1_171]: https://www.sciencedirect.com/science/article/abs/pii/S0148296316303952

[^1_172]: https://econpapers.repec.org/article/eeeintfor/v_3a39_3ay_3a2023_3ai_3a4_3ap_3a1518-1547.htm

[^1_173]: https://econweb.ucsd.edu/~gelliott/Combination.pdf

[^1_174]: https://www.sciencedirect.com/science/article/pii/S0169207022001480

[^1_175]: https://www.isidl.com/wp-content/uploads/2017/07/E4321-ISIDL.pdf

[^1_176]: https://warwick.ac.uk/fac/soc/economics/staff/academic/wallis/publications/wallis_afe_11.pdf

[^1_177]: https://journal.r-project.org/articles/RJ-2018-052/RJ-2018-052.pdf

[^1_178]: https://www.tandfonline.com/doi/full/10.1080/09603107.2011.523179

[^1_179]: https://shs.hal.science/halshs-01317974v3/document

[^1_180]: https://ideas.repec.org/a/eee/intfor/v32y2016i3p754-762.html

[^1_181]: https://warwick.ac.uk/fac/soc/economics/staff/academic/wallis/publications/smithwallis_obes_09.pdf

[^1_182]: https://g.espncdn.com/s/betting/SpannForecasting.pdf

[^1_183]: https://www.tandfonline.com/doi/full/10.1080/07350015.2026.2661980

[^1_184]: https://ideas.repec.org/a/eee/jbrese/v69y2016i10p3951-3962.html

[^1_185]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7996321/

[^1_186]: https://ideas.repec.org/a/sae/jospec/v22y2021i3p251-273.html

[^1_187]: https://www.semanticscholar.org/paper/Momentum-and-betting-market-perceptions-of-momentum-Salaga-Brown/bd8d0f8d527aac4a83c439586d47f7ad0d832567

[^1_188]: https://journals.sagepub.com/doi/10.1177/1527002520975837?icid=int.sj-full-text.similar-articles.5

[^1_189]: https://www.actionnetwork.com/ncaaf/college-football-bowl-betting-moneyline-underdogs-point-spread

[^1_190]: https://accessecon.com/Pubs/EB/2022/Volume42/EB-22-V42-I3-P139.pdf

[^1_191]: https://vsin.com/college-football/seven-motivational-factors-for-college-football-bowl-games/

[^1_192]: https://ideas.repec.org/a/spr/jecfin/v45y2021i4d10.1007_s12197-021-09557-5.html

[^1_193]: https://www.actionnetwork.com/ncaaf/college-football-bowl-game-betting-strategy-moneyline-underdogs-2019

[^1_194]: https://www.aeaweb.org/conference/2010/retrieve.php?pdfid=406

[^1_195]: https://cs229.stanford.edu/proj2015/101_report.pdf

[^1_196]: https://ideas.repec.org/a/taf/apeclt/v25y2018i19p1383-1388.html

[^1_197]: https://ideas.repec.org/a/spr/jecfin/v50y2026i1d10.1007_s12197-026-09786-6.html

[^1_198]: https://managementjournal.info/index.php/IJAME/article/download/406/346/1271

[^1_199]: http://www.accessecon.com/Pubs/EB/2022/Volume42/EB-22-V42-I3-P128.pdf

[^1_200]: https://link.springer.com/article/10.1007/s11162-022-09710-x

[^1_201]: https://www.cbssports.com/college-football/news/college-football-picks-bowl-game-spread-trends-and-betting-angles-from-proven-expert/

[^1_202]: https://www.mercurynews.com/2026/09/25/wilner-hotline-mailbag-cfp-expansion-blowouts-pac-12-tv-ratings/

[^1_203]: https://pubgdeal.com/bowl-game-predictions-for-2025-expert-analysis-ai-insights-must-watch-matchups/

[^1_204]: https://www.bettoredge.com/post/your-guide-to-betting-on-college-football-bowl-season

[^1_205]: https://journals.ku.edu/jis/article/view/22288/21412

[^1_206]: https://oddsindex.com/guides/college-football-betting-guide

[^1_207]: https://bcsfootball.org/bowl-opt-outs-nfl-draft-since-2016-2026/

[^1_208]: https://www.collegefootballpoll.com/news/from-kickoff-to-bowl-season-tracking-line-movement-in-college-football-odds/

[^1_209]: https://journals.ku.edu/jis/article/view/22288

[^1_210]: https://journals.ku.edu/jis/article/download/22288/21412/84844

[^1_211]: https://www.apu.apus.edu/area-of-study/nursing-and-health-sciences/resources/how-has-nil-changed-college-sports-like-college-football/

[^1_212]: https://coverfest.stanford.edu/talks/sterntalk.pdf

[^1_213]: https://davidharville.com/collegefootballratingspredictions/

[^1_214]: https://stassen.com/football/pointspread/

[^1_215]: https://davidharville.com/collegefootballratingspredictions/predictions/

[^1_216]: https://archive.inside.iastate.edu/1998/1009/Stern.html

[^1_217]: https://ideas.repec.org/a/bpj/jqsprt/v4y2008i3n3.html

[^1_218]: https://escholarship.org/content/qt8fq0v7hb/qt8fq0v7hb.pdf?t=nvfns1\&nosplash=524690be857a0b720ad3652d920c365b

[^1_219]: https://www.linkedin.com/in/raymond-stefani-a843a049

[^1_220]: http://faculty.fortlewis.edu/huggins_e/On%20the%20(Non-Linear)%20Probability%20of%20Winning.pptx

[^1_221]: https://scispace.com/papers/point-spread-and-odds-betting-baseball-basketball-and-48sjw5xd6f

[^1_222]: https://davidharville.com/collegefootballratingspredictions/ratings/

[^1_223]: https://ideas.repec.org/a/bpj/jqsprt/v3y2007i3n3.html

[^1_224]: https://people.stat.sc.edu/habing/courses/718S05.html

[^1_225]: https://www.glicko.net/research/nfl.pdf

[^1_226]: https://possiblywrong.wordpress.com/2015/11/28/college-football-bowl-confidence-pools/

[^1_227]: https://utstat.utoronto.ca/keith/papers/colley.pdf

[^1_228]: https://www.colleyrankings.com/matrate.pdf

[^1_229]: https://masseyratings.com/theory/index.htm

[^1_230]: https://www.colleyrankings.com/method.html

[^1_231]: https://www2.math.upenn.edu/~kazdan/312S14/Notes/Perron-Frobenius-football-SIAM1993.pdf

[^1_232]: https://people.computing.clemson.edu/~goddard/handouts/math3600/TEXT/E2.pdf

[^1_233]: http://carlmeyer.com/REU/REU2009Paper.pdf

[^1_234]: https://www.siam.org/publications/siam-news/articles/obituary-james-jim-keener/

[^1_235]: https://www.reddit.com/r/sportsbook/comments/14brxt/statistical_models_applied_to_the_rating_of/

[^1_236]: https://titan.dcs.bbk.ac.uk/~ale/dsta/dsta-8/Keener_ranking/lm-ch4-keener.pdf

[^1_237]: https://ideas.repec.org/a/bpj/jqsprt/v5y2009i2n3.html

[^1_238]: https://ww3.math.ucla.edu/camreport/cam13-08.pdf

[^1_239]: https://datafield.dev/sports-betting-textbook/part-04/chapter-15/

[^1_240]: https://www.renenunez.dev/cfb/methodology

[^1_241]: https://www.cfb-predictor.com/

[^1_242]: https://onlinelibrary.wiley.com/doi/10.1002/nav.21563

[^1_243]: https://ar5iv.labs.arxiv.org/html/1505.06918

[^1_244]: https://www.scribd.com/document/425306625/1-s2-0-S0169207011000914-main-pdf

[^1_245]: https://www.stat.berkeley.edu/~aldous/157/Papers/dubbs.pdf

[^1_246]: https://www.ramapo.edu/dmc/wp-content/uploads/sites/361/2023/05/MSDS-Byman.pdf

[^1_247]: https://ideas.repec.org/a/bpj/jqsprt/v9y2013i2p187-202n7.html

[^1_248]: https://trace.tennessee.edu/utk_graddiss/8297/

[^1_249]: https://scispace.com/pdf/college-football-bettors-and-the-wisdom-of-crowds-50apong59x.pdf

[^1_250]: https://www.cbssports.com/college-football/odds/FBS/2026/regular/week-4/

[^1_251]: https://www.vegasinsider.com/college-football/odds/las-vegas/

[^1_252]: https://betql.co/ncaaf/line-movement

[^1_253]: https://sportsbook.draftkings.com/leagues/football/ncaaf

[^1_254]: https://www.newgamenetwork.com/article/2957/how-college-football-odds-work-spreads-moneylines-and-totals-explained/

[^1_255]: https://www.cbssports.com/college-football/odds/

[^1_256]: https://www.betus.com.pa/help/how-to/sport/college-football/how-to-read-college-football-betting-trends-public-data/

[^1_257]: https://www.sharpfootballanalysis.com/sportsbook/clv-betting/

[^1_258]: https://www.oddsshopper.com/articles/betting-101/college-football-betting-strategies

[^1_259]: https://www.collegefootballwinning.com/blog/college-football-predictions/

[^1_260]: https://www.collegefootballwinning.com/blog/efficient-markets-in-sports-betting/

[^1_261]: https://blogs.colgate.edu/economics/files/2013/05/Xu_Econ490_Thesis.pdf

[^1_262]: https://www.mybookie.ag/sports-betting-guide/guide-how-to-read-college-football-odds/

[^1_263]: https://fae.uprrp.edu/wp-content/uploads/sites/13/2018/02/JimmyTorrezbonus2010.pdf

[^1_264]: https://dash.harvard.edu/server/api/core/bitstreams/24950429-b1b7-4372-a029-1b68de1872e3/content

[^1_265]: https://www.asc.ohio-state.edu/logan.155/pdf/JSE_2014.pdf

[^1_266]: https://ideas.repec.org/a/sae/jospec/v18y2017i4p388-425.html

[^1_267]: https://scholarship.claremont.edu/cgi/viewcontent.cgi?article=5145\&context=cmc_theses

[^1_268]: https://ideas.repec.org/a/sae/jospec/v15y2014i1p45-63.html

[^1_269]: https://ideas.repec.org/a/taf/apfiec/v15y2005i3p143-152.html

[^1_270]: https://www2.gwu.edu/~forcpgm/Sports_paper_GW1.pdf

[^1_271]: https://www.cs.vu.nl/~sbhulai/papers/paper-bosch.pdf

[^1_272]: https://thesis.eur.nl/pub/49906/Maasdam_457787.pdf

[^1_273]: https://www.cs.cornell.edu/courses/cs6780/2010fa/projects/warner_cs6780.pdf

[^1_274]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12463883/

[^1_275]: https://arxiv.org/html/2309.15253v2

[^1_276]: https://deepmetricanalytics.com/predictions/ncaa?season=2026\&week=4

[^1_277]: https://journals.sagepub.com/doi/10.1177/22150218251365223

[^1_278]: https://www.qu.edu/academics/experiential-learning/course-projects-and-capstones/student-projects/predicting-nfl-total-score-and-point-spread-bets/

[^1_279]: https://www.sciencedirect.com/science/article/pii/S1877050914011181/pdf

[^1_280]: https://www.studocu.com/row/document/addis-ababa-university/art-history/1-s2-bi-dm-preliminary/44546436

[^1_281]: https://ar5iv.labs.arxiv.org/html/1601.00574

[^1_282]: https://www.reddit.com/r/CFBAnalysis/comments/1n0zqfm/cfb_predict_app/

[^1_283]: https://www.academia.edu/101413057/NFL_and_NCAA_Football_Prediction_using_Artificial_Neural_Networks

[^1_284]: https://medium.com/@nwiatrek/college-football-machine-learning-958c69ff8145

[^1_285]: https://www.academia.edu/8000619/Validating_a_division_IA_college_football_season_simulation_system

[^1_286]: https://radsportsanalytics.com/blog/talking-tech-predicting-play-calls-using-a-random-forest-classifier/

[^1_287]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9684891/

[^1_288]: https://www.bettoredge.com/post/how-win-probability-models-work-in-college-football

[^1_289]: https://discovery.ucl.ac.uk/id/eprint/16040/1/16040.pdf

[^1_290]: https://discovery.ucl.ac.uk/16040/1/16040.pdf

[^1_291]: https://www.studocu.com/in/document/motilal-nehru-national-institute-of-technology/btech-computer-science/histogrammmmmin/100103866

[^1_292]: https://gianluca.statistica.it/research/football/

[^1_293]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11949986/

[^1_294]: https://www.rawbw.com/~deano/articles/kalman.html

[^1_295]: https://public-pages-files-2025.frontiersin.org/journals/behavioral-economics/articles/10.3389/frbhe.2024.1479832/pdf

[^1_296]: https://digital.wpi.edu/downloads/x346d423k

[^1_297]: https://ar5iv.labs.arxiv.org/html/1701.05976

[^1_298]: https://www.scribd.com/document/1001984800/2408-10867v1

[^1_299]: https://statsbylopez.netlify.app/post/a-state-space-model-to-evaluate-sports-teams/

[^1_300]: https://fivethirtyeight.com/features/heres-how-our-college-football-playoff-predictions-work/

[^1_301]: https://fivethirtyeight.com/methodology/how-our-college-football-playoff-predictions-work/amp/

[^1_302]: https://datafield.dev/nfl-football-analytics/part-04/chapter-19/

[^1_303]: https://fivethirtyeight.com/features/how-our-2017-college-football-playoff-predictions-work/

[^1_304]: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/amp/

[^1_305]: https://medium.com/@alexelfering/how-my-sports-forecasted-performed-and-where-to-improve-423a90f42ec7

[^1_306]: https://arxiv.org/html/2403.03862v1

[^1_307]: https://solr.pling.com/article/understanding-538-college-football-predictions

[^1_308]: https://core.ac.uk/download/86638968.pdf

[^1_309]: https://eric.ed.gov/?id=EJ1477885

[^1_310]: https://ideas.repec.org/a/wly/navres/v61y2014i1p17-33.html

[^1_311]: https://boris.unibe.ch/176073/2/1-s2.0-S0950705122000314-main.pdf

[^1_312]: https://ideas.repec.org/h/spr/spochp/978-3-031-76047-1_12.html

[^1_313]: https://ideas.repec.org/a/inm/orinte/v35y2005i6p483-496.html

[^1_314]: https://reference-global.com/download/article/10.2478/ijcss-2026-0001.pdf

[^1_315]: https://www.academia.edu/128764335/A_Consistent_Weighted_Ranking_Scheme_With_an_Application_to_NCAA_College_Football_Rankings

[^1_316]: https://digitalcommons.unf.edu/unf_faculty_publications/2666/

[^1_317]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4269436/

[^1_318]: https://www3.cs.stonybrook.edu/~skiena/591/final_projects/football/report.pdf

[^1_319]: https://ouci.dntb.gov.ua/en/works/4zxLraa9/

[^1_320]: https://www.semanticscholar.org/paper/Model-Development-for-an-Artificial-NCAA-Football-Lee-Kang/1f41d5eca6f64305a9019b2ceef671537bd5e97a

[^1_321]: https://bcsfootball.org/bcsfb/rankings/

[^1_322]: https://bcsfootball.org/bcs-computer-rankings-explained-1998-2013/

[^1_323]: https://www.si.com/college/2018/07/11/bcs-computer-rankings-polls-formula-sagarin-billingsley

[^1_324]: https://bcsfootball.org/bcsfb/standings/

[^1_325]: https://www.collegefootballpoll.com/news/how-computer-rankings-actually-score-college-football-teams/

[^1_326]: https://sports.yahoo.com/news/illegitimate-bcs-process-holds-game-041900104--ncaaf.html

[^1_327]: https://web.williams.edu/Mathematics/sjmiller/public_html/355Sp24/addcomments/'Death%20to%20the%20BCS%20'%20Nonsense%20rules%20-%20College%20Football%20-%20Rivals.com.htm

[^1_328]: http://www.davemease.com/papers/football.pdf

[^1_329]: https://dl.icdst.org/pdfs/files/2476377e7744471ceb30eeaac42f83e7.pdf

[^1_330]: https://arxiv.org/pdf/2401.16392v1.pdf

[^1_331]: http://siba-ese.unile.it/index.php/ejasa/article/download/16473/15604

[^1_332]: https://www.tandfonline.com/doi/full/10.1080/14413523.2026.2689228

[^1_333]: https://www.davidpublisher.com/Public/uploads/Contribute/5567dcb443df0.pdf

[^1_334]: https://bluechipanalytics.com/college-football/home-field-advantage/

[^1_335]: https://arxiv.org/html/1211.4000v1

[^1_336]: https://ideas.repec.org/a/wly/soecon/v90y2024i4p1060-1098.html

[^1_337]: https://library.ndsu.edu/server/api/core/bitstreams/adb8bd7b-e3d1-44b2-92d4-f51c15dd0868/content

[^1_338]: https://www.ensani.ir/file/download/article/6745ca6729abf-10693-1403-1.pdf

[^1_339]: https://beyondthescoresports.substack.com/p/breaking-down-home-field-advantage

[^1_340]: https://scispace.com/journals/journal-of-sports-analytics-1o9wcy9k/2025

[^1_341]: https://www.sportsline.com/college-football/odds/

[^1_342]: https://www.btb-analytics.com/college-football-previews-and-prediction

[^1_343]: https://cfbintelligence.com/analytics

[^1_344]: https://www.nytimes.com/athletic/7626688/2026/09/24/college-football-week-4-score-projections-model/

[^1_345]: http://lobello.dieei.unict.it/public_files/publications/avbetfa12.pdf

[^1_346]: https://www.yumpu.com/en/document/view/19452012/4-collegefootballdatadvdscom

[^1_347]: https://datafield.dev/nfl-football-analytics/part-04/chapter-22/case-study-01.html

[^1_348]: https://deepblue.lib.umich.edu/handle/2027.42/176935

[^1_349]: FBS College Football Pregame Totals Betting System Research Report.md

[^1_350]: https://alpha.rankless.org/authors/david-a-harville

[^1_351]: https://scispace.com/pdf/college-football-rankings-and-market-efficiency-18wvdp9gui.pdf

[^1_352]: https://davidharville.com/collegefootballratingspredictions/accuracy/

[^1_353]: https://www2.gwu.edu/~forcpgm/2009-002.pdf

[^1_354]: https://news.fbc.keio.ac.jp/~hayami/pdf/other/sports/Monks_2009_JSportsEcon.pdf

[^1_355]: https://scholarcommons.sc.edu/cgi/viewcontent.cgi?article=1025\&context=jiia

[^1_356]: https://content.iospress.com/download/journal-of-sports-analytics/jsa180331?id=journal-of-sports-analytics/jsa180331

[^1_357]: http://tbeck.freeshell.org/fb/lit.txt

[^1_358]: http://www.lukebornn.com/papers/yuan_jqas_2014.pdf

[^1_359]: https://masseyratings.com/theory/bib.htm

[^1_360]: https://www.semanticscholar.org/paper/Statistical-Models-Applied-to-the-Rating-of-Sports-Starnes-Massey/87d8c104567baf35d123ca79e48884de44a123c9

[^1_361]: https://www.smcvt.edu/directories/employee-directory/john-trono/

[^1_362]: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID1646523_code1350147.pdf?abstractid=1646523\&mirid=1

[^1_363]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=335801

[^1_364]: http://netprophetblog.blogspot.com/p/papers.html

[^1_365]: https://www.smcvt.edu/wp-content/uploads/2021/08/4thMathSport.pdf

[^1_366]: https://academic.oup.com/my-account/register?siteId=6519\&returnUrl=https://academic.oup.com/jrsssc/article-abstract/74/5/1372/8108436

[^1_367]: http://ftp.cs.ucla.edu/pub/stat_ser/r485.pdf

[^1_368]: http://www.matterofstats.com/mafl-stats-journal/tag/margin+prediction

[^1_369]: https://academics.smcvt.edu/jtrono/Papers/Titles.htm

[^1_370]: https://scispace.com/papers/applications-of-statistical-methods-to-american-football-4apgw7r2bd

[^1_371]: http://siba-ese.unisalento.it/index.php/ejasa/article/view/16473

[^1_372]: https://ideas.repec.org/a/bpj/jqsprt/v7y2011i4n10.html

[^1_373]: https://ideas.repec.org/a/bpj/jqsprt/v6y2010i2n7.html

[^1_374]: https://ideas.repec.org/s/bpj/jqsprt3.html

[^1_375]: https://www.degruyterbrill.com/document/doi/10.2202/1559-0410.1242/pdf?licenseType=restricted

[^1_376]: https://www.alexsietsema.com/files/ultimate_tas_12-1.pdf

[^1_377]: https://journals.library.brocku.ca/index.php/jess/article/download/3700/2783/12012

[^1_378]: http://www.inf.u-szeged.hu/~london/publ/LA-NJ-KM-SiKDD-final.pdf

[^1_379]: https://academics.smcvt.edu/jtrono/Papers/4thMathSport.pdf

[^1_380]: https://mississippitoday.org/topic/college-football/

[^1_381]: https://spreadspoke.com/

[^1_382]: https://academics.smcvt.edu/jtrono/OAF_CollegeFootballRatings/1983.htm

[^1_383]: https://academics.smcvt.edu/jtrono/DiscreteRatings/Discrete.htm

[^1_384]: https://evanalytics.com/ncaab/stats/spread

[^1_385]: https://evanalytics.com/ncaaf/stats/spread

[^1_386]: https://sports-statistics.com/nfl/historical-superbowl-ats-statistics/

[^1_387]: https://www.ijert.org/an-application-of-linear-regression-artificial-neural-network-model-in-the-nfl-result-prediction

[^1_388]: https://www.diva-portal.org/smash/get/diva2:1772002/FULLTEXT01.pdf

[^1_389]: https://www.covers.com/ncaaf/college-football-ai-predictions-week-3-2026

[^1_390]: https://www.cs.cmu.edu/~epxing/Class/10701-06f/project-reports/gimpel.pdf

[^1_391]: https://github.com/colettebarca/collegeFootball

[^1_392]: https://www.imperial.ac.uk/media/imperial-college/faculty-of-engineering/computing/public/distinguished-projects/1718-ug-projects/Corentin-Herbinet-Using-Machine-Learning-techniques-to-predict-the-outcome-of-profressional-football-matches.pdf

[^1_393]: https://search.proquest.com/openview/c027f7dba819d22752486fa9d0f2293a/1.pdf?pq-origsite=gscholar\&cbl=18750\&diss=y

[^1_394]: https://reelmind.ai/blog/cfb-ai-predicts-college-football-season-outcomes

[^1_395]: https://search.proquest.com/openview/135b3adab77ec34c15a098a5627a4326/1.pdf?pq-origsite=gscholar\&cbl=5455937

[^1_396]: https://reelmind.ai/blog/who-won-college-football-2025-ai-predicts-visualizes-outcomes

[^1_397]: https://search.proquest.com/openview/65aff24671603e96ad7e68bfbdb93856/1.pdf?pq-origsite=gscholar\&cbl=18750\&diss=y

[^1_398]: https://ar5iv.labs.arxiv.org/html/2207.13747

[^1_399]: https://github.com/fredrick/reiff

[^1_400]: https://www.nytimes.com/athletic/7604920/2026/09/17/college-football-week-3-score-projections-model-lsu-ole-miss/

[^1_401]: https://dsc.duq.edu/cgi/viewcontent.cgi?article=1986\&context=etd

[^1_402]: https://www.sportsline.com/insiders/college-football-score-predictions-picks-for-week-0-2026-from-proven-model/

[^1_403]: https://www.edgelabs.bet/cfb/power-ratings

[^1_404]: https://www.espn.com/college-football/story/\_/id/49593338/final-preseason-college-football-sp+-rankings-takeaways-2026

[^1_405]: https://247sports.com/college/maryland/article/espn-released-its-new-fpi-rankings-this-week-heres-what-they-predict-for-maryland-in-2026-288244429/

[^1_406]: https://247sports.com/college/notre-dame/article/espn-released-its-new-fpi-rankings-this-week-heres-what-they-predict-for-maryland-in-2026-288244429/

[^1_407]: https://www.glicko.net/research/nfl-chapter.pdf

[^1_408]: https://www.espn.co.uk/college-football/story/\_/id/45284359/2025-college-football-fpi-power-index-best-matchups-title-odds

[^1_409]: https://core.ac.uk/download/pdf/14921159.pdf

[^1_410]: https://www.stat.berkeley.edu/~aldous/Research/Ugrad/Xiaochen_Yang_write-up.pdf

[^1_411]: https://www.stat.berkeley.edu/users/aldous/Research/Ugrad/Xiaochen_Yang_write-up.pdf

[^1_412]: https://www.jstor.org/stable/2287640

[^1_413]: https://onlinelibrary.wiley.com/doi/10.1002/for.3029

[^1_414]: https://statmodeling.stat.columbia.edu/wp-content/uploads/2014/03/EBMA_conditions6.pdf

[^1_415]: https://shs.hal.science/halshs-01317974/document

[^1_416]: https://www.sas.upenn.edu/~fdiebold/NoHesitations/DieboldShin2019.pdf

[^1_417]: https://lirias.kuleuven.be/retrieve/385251

[^1_418]: https://crest.science/RePEc/wpstorage/2013-21.pdf

[^1_419]: https://scispace.com/journals/journal-of-sports-economics-hmtuygb5/2007

[^1_420]: https://fairmodel.econ.yale.edu/rayfair/pdf/2002B.PDF

[^1_421]: https://journals.ku.edu/jis/article/download/10026/21977/93077

[^1_422]: https://ideas.repec.org/p/nbr/nberwo/13596.html

[^1_423]: https://fairmodel.econ.yale.edu/ec438/index25.htm

[^1_424]: https://ideas.repec.org/r/ucp/jnlbus/v41y1968p203.html

[^1_425]: https://ideas.repec.org/p/gwc/wpaper/2009-002.html

