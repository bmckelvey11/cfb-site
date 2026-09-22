# Scoring and evaluating models and systems

**Status: governing.** This is the repo's standard for how any model, system, or filter
is scored. Supplied by the user 2026-09-18 and adopted repo-wide; this copy is the
authority, not the download it came from. Living doc — edit in place.

Companion to [`methods.md`](methods.md), which holds the *formula* behind each number
the repo already computes (Wilson, MDE, Holm, best-of-k, Kelly). This file holds the
*standard*: which numbers must be reported, what counts as evidence, and what
invalidates a claim regardless of how good the headline looks.

Applies to anything whose ROI, CLV, hit rate, or forecast skill is reported — the
totals harness, over-zero, the spread research tree, vendor-pick grading, and saved
system-maker filters. Existing dated docs are records and are not re-scored; the
standard binds new work and any doc that supersedes an old one.

---


## Executive answer

Closing-line value should be treated as one important **market-relative leading indicator**, not as the sole score and not as proof of profitability. A credible evaluation framework must separately measure forecast quality, market-relative information, realized economics, bankroll risk, statistical certainty, robustness, and real-world execution.

The key distinction is between a **predictive model** and a **betting system**. A model outputs probabilities, distributions, spreads, totals, or prices; a system adds bet-selection rules, timing, available books, staking, bankroll constraints, and execution. A model can forecast well yet fail economically, while a profitable backtest can be produced by noisy outcomes, favorable prices that were not actually available, staking effects, or extensive strategy mining. Published sports-model work likewise finds that predictive quality and profitability are distinct objectives, and that market-implied forecasts can remain hard to beat even when model accuracy looks respectable.[^1][^2]

The recommended top-level design is therefore a **multi-pillar scorecard with hard validation gates**, not one metric and not a simple weighted average that allows exceptional ROI to hide leakage or fragility.

## What each layer answers

| Layer | Core question | Primary evidence |
|---|---|---|
| Forecast model | Are the probabilities or distributions accurate? | Log loss, Brier/RPS/CRPS, calibration, resolution, market-relative skill |
| Bet selector | Does the rule choose wagers whose prices are favorable? | Expected value, edge-decile monotonicity, no-vig CLV, positive-CLV rate |
| Staking policy | Does sizing convert edge into sustainable bankroll growth? | Log growth, bankroll return, drawdown, risk of ruin, tail loss |
| Execution process | Could the historical wagers actually have been placed? | Fill rate, slippage, limits, rejection rate, latency, book availability |
| Research process | Is the result likely real rather than selected noise? | Walk-forward performance, untouched holdout, trial count, DSR/PBO, sensitivity tests |
| Live system | Is the edge persisting after deployment? | Prospective ROI/CLV/calibration, drift, realized versus expected performance |

This separation prevents attribution errors. For example, weak ROI with good probabilities may be caused by a poor betting threshold or bad execution; positive ROI with weak forecasts may be short-term outcome variance; and positive CLV with weak calibration may indicate effective line shopping without a reliable estimate of true win probability.

## Metric hierarchy

A practical hierarchy has four levels:

1. **Integrity gates:** timestamp correctness, no leakage, executable prices, complete bet logging, fixed rules, and an honest count of research trials.
2. **Model evidence:** proper scoring rules, calibration, resolution, and incremental value beyond the market.
3. **Economic evidence:** net ROI after all costs, bankroll growth, risk-adjusted return, drawdown, and capacity.
4. **Persistence evidence:** fold stability, regime robustness, parameter stability, and prospective confirmation.

Any failure at the integrity layer should invalidate the financial score rather than merely reduce it. Backtest-overfitting research emphasizes that repeated strategy trials make a selected winner look better by chance, and that the number of attempted trials is necessary to interpret the winning backtest.[^3][^4][^5]

## Forecast quality

### Proper scoring rules

For a binary event with model probability $p_i$ and outcome $y_i \in \{0,1\}$, use:

$$
\begin{gathered}
\text{Brier}=\frac{1}{n}\sum_{i=1}^{n}(p_i-y_i)^2 \\[0.5em]
\text{LogLoss}=-\frac{1}{n}\sum_{i=1}^{n}\left[y_i\log(p_i)+(1-y_i)\log(1-p_i)\right] \\[1em]
\begin{array}{rl}
\text{where}\quad i: & \text{one forecast (one bet, game, or event)} \\
n: & \text{number of forecasts scored} \\
p_i \in (0,1): & \text{model probability that event } i \text{ happens} \\
y_i \in \{0,1\}: & \text{outcome; 1 if it happened, 0 if not} \\
\log: & \text{natural logarithm}
\end{array}
\end{gathered}
$$

Both are averages of a per-forecast penalty, and lower is better. Brier is the squared distance between the probability and the outcome: a 0.60 forecast on an event that happens costs $(0.60-1)^2 = 0.16$. Always saying 0.50 scores 0.25, so a binary model above 0.25 is worse than a coin. Log loss charges $-\log$ of the probability given to what actually happened: the same 0.60 forecast costs $-\log 0.60 \approx 0.51$, but a 0.99 forecast on an event that fails costs $-\log 0.01 \approx 4.6$. That unbounded penalty is why log loss punishes overconfidence harder than Brier.

Brier and logarithmic loss are strictly proper scoring rules, meaning that their expected value is optimized by reporting the true probability; log loss penalizes confidently wrong forecasts more heavily. Use both: Brier is interpretable and stable, while log loss is a stronger warning against dangerous overconfidence.[^6][^7][^8][^9]

For three-way ordered outcomes such as home/draw/away, report **Ranked Probability Score (RPS)** as well as multiclass log loss. For continuous predictive distributions—scores, margins, totals, or strokes gained—use **CRPS**, which compares the full predictive cumulative distribution with the realized observation.[^7][^6]

### Skill versus benchmarks

An absolute Brier score is hard to interpret across sports, seasons, and markets with different base rates. Convert it to a skill score against a stated benchmark:

$$
\begin{gathered}
\text{Brier Skill}=1-\frac{\text{Brier}_{model}}{\text{Brier}_{reference}} \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Brier}_{model}: & \text{model's Brier score on the scored events} \\
\text{Brier}_{reference}: & \text{benchmark's Brier score on the same events} \\
\text{Brier Skill}: & \text{fraction of the benchmark's error the model removes}
\end{array}
\end{gathered}
$$

A value above zero means improvement over the reference; one is perfect; a negative value means the model is worse. Example: a model scoring 0.240 against a de-vigged market scoring 0.250 has skill $1 - 0.240/0.250 = 0.04$, meaning it removes 4% of the market's squared error. Both scores must come from exactly the same events, or the ratio compares different samples, not different forecasters. For betting work, calculate skill against at least three references: a base-rate model, the de-vigged market probability available at decision time, and the incumbent production model.[^10][^11][^12]

The most important comparison is generally **incremental skill over the market at the same information timestamp**. Comparing a morning model with the closing market mixes forecasting skill with information that arrived later, while comparing it only with a naive base rate sets the bar too low.

### Calibration and resolution

Brier score can be decomposed into reliability, resolution, and uncertainty:

$$
\begin{gathered}
\text{Brier}=\text{Reliability}-\text{Resolution}+\text{Uncertainty} \\[1em]
\begin{array}{rl}
\text{where}\quad \text{Reliability}: & \text{average squared gap between forecast and observed frequency, per forecast bin (lower is better)} \\
\text{Resolution}: & \text{how far each bin's observed frequency sits from the overall base rate (higher is better)} \\
\text{Uncertainty}: & \bar{y}(1-\bar{y}) \text{, set by the base rate } \bar{y} \text{ alone; no model can change it}
\end{array}
\end{gathered}
$$

The signs are the point: reliability adds error, resolution subtracts it, and uncertainty is fixed by the data. For a roughly 50/50 market such as spreads, $\bar{y} \approx 0.5$ and uncertainty is $0.25$, the coin-flip score above. The exact decomposition holds when forecasts take a limited set of values; with continuous probabilities it is computed on bins and is approximate.

Reliability measures probability calibration, resolution measures the ability to separate events into meaningfully different risk groups, and uncertainty reflects the outcome's base-rate difficulty. This decomposition matters because two systems can have similar Brier scores for different reasons: one may be calibrated but timid, while another may be sharp but systematically overconfident.[^13][^14][^6]

Report these calibration diagnostics:

- **Calibration intercept:** ideal 0; nonzero values indicate average under- or overprediction.
- **Calibration slope:** ideal 1; below 1 generally indicates predictions are too extreme, a common overfitting signature.[^15][^16]
- **Reliability curve:** predicted probability versus observed frequency, with uncertainty bands.
- **Adaptive calibration error:** supporting diagnostic, not a selection objective.
- **Calibration by edge band, odds band, sport, market, bookmaker, and season:** global calibration can hide locally damaging errors.

Fixed-bin Expected Calibration Error is sensitive to bin definitions and can underestimate or mis-rank calibration quality, so it should not replace Brier/log loss or a full calibration curve. A constant model can also appear well calibrated while possessing no useful resolution, which is another reason to score calibration and discrimination separately.[^17][^18][^19]

### Discrimination

AUC, rank correlation, and concordance measure whether higher model probabilities tend to correspond to more frequent outcomes. They are useful diagnostics, but they do not establish probability accuracy or betting value; a model can rank games correctly while assigning unusably extreme probabilities.[^20][^9]

For spread or total point forecasts, also report MAE/RMSE against the realized margin or total, but keep them secondary to distributional scores when the model can produce a full predictive distribution. A point estimate cannot describe the uncertainty needed to price alternate lines, moneylines, or correlated portfolios.

## Market-relative value

### CLV done correctly

CLV asks whether the wager obtained a better price than a predefined later benchmark. The close is often a strong comparator because late prices tend to incorporate more information, and empirical work has found closing prices can forecast outcomes better than earlier prices. However, recent research also documents non-monotonic forecast quality and exploitable overreaction in some betting-line sequences, so the close is a powerful market benchmark—not revealed truth.[^21][^22][^23][^24]

For a binary market, de-vig both sides of the reference close and express CLV in economically comparable terms. Useful portfolio statistics are:

- **Probability CLV:** de-vigged close probability minus the break-even probability of the bet price.
- **Price-ratio CLV:** $o_{bet}/o_{close,fair}-1$ using decimal odds.
- **Expected return at close:** $p_{close,fair}o_{bet}-1$.
- **Beat-close rate:** proportion with positive CLV.
- **Median and stake-weighted CLV:** robust center and portfolio exposure.
- **CLV confidence interval:** preferably clustered or block-bootstrapped.

There is no universal closing line across books; a valid study must predefine the reference book or consensus, exact cutoff, de-vigging method, treatment of pushes, and stale/missing quotes. Soft-book closes, different limits, and post hoc choice of the most favorable benchmark can inflate apparent CLV.[^25]

### Why CLV is insufficient

Positive CLV does not by itself prove that:

- The model probabilities are calibrated.
- The betting rule has positive realized or true expected value.
- The reference close is efficient for that market and timestamp.
- The edge survives commissions, slippage, rejected bets, limits, and taxes.
- The strategy has enough capacity to matter.
- The same process will continue after market adaptation.
- The research sample is complete and free from selective logging.

CLV is therefore best viewed as a **price-acquisition and market-direction diagnostic**. The deeper question is whether the system has information incremental to the market. Test this by fitting an out-of-sample market-conditioned model such as

$$
\begin{gathered}
\operatorname{logit}P(Y=1)=\alpha+\beta\operatorname{logit}(p_{market})+\gamma z_{model} \\[1em]
\begin{array}{rl}
\text{where}\quad Y \in \{0,1\}: & \text{outcome of the bet's side (1 = it won)} \\
\operatorname{logit}(p) = \log\frac{p}{1-p}: & \text{log-odds transform} \\
p_{market}: & \text{de-vigged market probability at the decision time} \\
z_{model}: & \text{model's residual signal, or its log-odds difference from the market} \\
\alpha: & \text{intercept; nonzero means the market leans one way on average} \\
\beta: & \text{market slope; 1 means market probabilities are correctly scaled} \\
\gamma: & \text{information the model adds beyond the market}
\end{array}
\end{gathered}
$$

If the model only echoes the market, the fit returns $\alpha = 0$, $\beta = 1$, $\gamma = 0$. A stable, correctly signed $\gamma$, improved out-of-sample proper score, and better calibration show that the model contributes information beyond simply echoing market odds. Forecast-encompassing tests are designed to ask whether one forecast explains variation that the other cannot.[^26][^27]

Also test whether returns and win rates rise monotonically across **predeclared model-edge deciles**. If the model's 8% edges do not perform better than its 2% edges, its probability scale or selection logic is suspect even when aggregate ROI is positive.

## Profitability

### Core economic metrics

Use turnover ROI, commonly called yield in some markets, as the primary realized-efficiency statistic:

$$
\begin{gathered}
\text{ROI}_{turnover}=\frac{\sum_i \text{net profit}_i}{\sum_i \text{stake}_i} \\[1em]
\begin{array}{rl}
\text{where}\quad i: & \text{one settled bet} \\
\text{net profit}_i: & \text{amount won minus stake; } -\text{stake}_i \text{ on a loss, 0 on a push} \\
\text{stake}_i: & \text{amount risked on bet } i
\end{array}
\end{gathered}
$$

Example: 100 one-unit bets at −110 (decimal 1.909) going 55–45 return $55 \times 0.909 - 45 = 5.0$ units on 100 staked, a turnover ROI of 5.0%. Break-even at −110 is 52.4%.

Published betting studies commonly define ROI as net profit divided by total amount wagered. Report it with total turnover, net profit, number of independent events, and a confidence interval; a naked ROI percentage conceals both scale and uncertainty.[^28][^29][^30]

Do not combine these different return concepts under one label:

| Metric | Definition | Best use | Main limitation |
|---|---|---|---|
| Turnover ROI | Net profit / total staked | Purity of price edge | Ignores capital reuse and time |
| Bankroll return | Ending bankroll / starting bankroll minus 1 | Actual investor outcome | Highly staking- and path-dependent |
| Annualized growth | Compounded bankroll growth per year | Cross-period comparison | Unstable for short histories |
| Log growth | Mean change in log bankroll | Kelly-style long-run growth | Undefined at ruin; sizing-sensitive |
| Profit per bet | Net profit / wagers | Operational economics | Depends on stake convention |
| Profit per event/day | Net profit / event or day | Capacity and time scaling | Masks capital employed |

Also report **gross ROI and net ROI**. Net calculations should include commission, exchange fees, pushes/voids, price slippage, rejected or partially filled wagers, bonus exclusions, currency costs, and any operational cost that scales with betting.

### Break-even and edge capture

For each bet, compute break-even probability $p_{BE}=1/o_i$ from decimal odds and model expected return $EV_i=p_i o_i-1$. Aggregate:

- Mean and stake-weighted ex-ante EV.
- Realized ROI minus ex-ante EV.
- Calibration of estimated edge: realized return by predicted-EV bucket.
- Percentage of theoretical value lost to slippage.
- Percentage of qualifying bets successfully filled.
- Return relative to a matched market or random-selection control.

At American odds of -110, the break-even hit rate is approximately 52.38%, but the correct threshold varies with each wager's odds. Therefore, evaluate profit directly from odds and outcomes rather than using one universal win-rate hurdle.

### Profit concentration

A system should not receive a high profitability score merely because a few longshots won. Report:

- Median bet return and trimmed ROI.
- Share of total profit from the top 1, 5, and 10 wagers.
- ROI after removing the best event, week, and season.
- ROI by odds band and bet type.
- Longshot contribution and payout-tail exposure.
- Herfindahl-style concentration across sports, leagues, teams, books, and strategy families.

This is especially important because betting returns are discrete, asymmetric, and often heavy-tailed. Profit concentration is not automatically bad, but it means headline ROI has less evidentiary weight.

## Risk and bankroll quality

### Risk-adjusted returns

Sharpe ratio measures excess return per unit of total volatility, while Sortino replaces total volatility with downside deviation and therefore does not penalize favorable upside variability in the same way. In betting, calculate both from a predeclared aggregation unit—preferably daily or event-window bankroll returns—not from arbitrarily treating every correlated wager as an independent period.[^31][^32]

Also report:

- **Maximum drawdown:** largest peak-to-trough bankroll decline.
- **Drawdown duration:** time from peak through recovery.
- **Calmar ratio:** annualized return divided by maximum drawdown.
- **Ulcer or average drawdown statistics:** severity and persistence beyond the single worst episode.
- **Loss streak distribution:** operational and psychological stress.
- **Worst week/month/season:** regime-tail diagnostics.

Maximum drawdown and recovery duration capture path risk that ROI omits. Drawdown should be computed under the actual staking policy and under standardized flat staking, because otherwise model quality and staking aggressiveness are confounded.[^33][^31]

### Tail and ruin risk

Report historical or bootstrap **Value at Risk** and **Expected Shortfall** at stated horizons. Expected Shortfall measures average loss once the VaR threshold has been breached and, unlike VaR in general, is a coherent risk measure.[^34][^35][^36]

Estimate:

- Probability of a 10%, 20%, 30%, and 50% drawdown.
- Probability of bankroll ruin or violating a minimum-capital floor.
- Expected time under the high-water mark.
- Expected Shortfall for daily, weekly, and seasonal returns.
- Capital needed to keep ruin probability below a selected tolerance.

The Kelly criterion maximizes expected logarithmic wealth growth under correctly specified probabilities, but unconstrained Kelly can create unacceptable drawdown risk when probabilities are uncertain. Evaluate staking at flat units, fractional Kelly, and the proposed production policy; if results exist only under aggressive sizing, the evidence belongs to the staking policy rather than the underlying model.[^37][^38][^39]

## Statistical certainty

### Confidence intervals first

Every key outcome should have an interval or probability statement, not only a point estimate:

- ROI with 90% and 95% confidence intervals.
- Probability true ROI exceeds 0%.
- Probability true ROI exceeds a practical hurdle such as 1% or 2% after costs.
- CLV and proper-score differences with intervals.
- Drawdown distribution under resampling.
- Fold-to-fold and season-to-season dispersion.

Wagers from the same game, slate, week, team, or information shock are not independent. An ordinary row bootstrap destroys this structure; block bootstrap methods resample groups of consecutive observations to preserve dependence, and the stationary bootstrap was introduced for confidence regions under weak dependence. For sports systems, cluster at least by event and consider block resampling by day or week; use two-way clustering when shared game and time effects are both material.[^40][^41][^42]

### Paired model tests

Compare models on the exact same observations. Use observation-level proper-score differences and a dependence-robust Diebold–Mariano-style test to assess whether one forecast has significantly lower loss. Pairing is essential because the difficulty of the events should cancel in the comparison.[^43][^44][^45]

For return comparisons, use paired block-bootstrap differences between the candidate and benchmark strategy. Report effect size and uncertainty, not only a p-value; a statistically detectable advantage can still be too small to survive costs.

### Multiple testing

A filter builder, parameter sweep, or feature-search system can test thousands of correlated strategies. The final winner's ordinary p-value, Sharpe ratio, and ROI are then optimistic because they ignore the search that produced it. Deflated Sharpe Ratio adjusts for multiple trials and non-normal returns, while Probability of Backtest Overfitting estimates how often the in-sample winner falls below the out-of-sample median.[^46][^47][^4][^48]

Maintain an append-only **trial ledger** containing every materially distinct rule, feature set, threshold, model, calibration method, and staking variant tested. Apply false-discovery-rate control during exploration, then require untouched out-of-sample and prospective confirmation; research on betting-market strategies has shown that apparent significance can disappear under multiple-testing thresholds.[^49][^50]

## Robustness

### Time-respecting validation

Use nested, time-respecting walk-forward validation as the main sports deployment simulation:

1. Train only on information available before the fold.
2. Tune features, hyperparameters, thresholds, and calibration inside the training window.
3. Apply a purge or embargo when feature windows or market observations overlap the test period.
4. Lock the model and betting policy.
5. Score the next chronological block.
6. Advance and repeat.
7. Preserve a final untouched season or prospective period.

The entire pipeline—not only the estimator—must obey the historical information set. Combinatorially symmetric cross-validation and PBO can provide a secondary search-overfitting diagnostic, but they should not replace the chronological deployment simulation.[^51][^52][^46]

### Stability dimensions

Score both the average and dispersion across:

- Season, month, week, and validation fold.
- Sport, league, conference, tournament, and market.
- Favorite/underdog and over/under sides.
- Odds, line, liquidity, and model-edge bands.
- Bet timing and hours to start.
- Sportsbook and market-maker reference.
- Injuries, weather, postseason, and other regime tags.
- Home/away, team strength, and public-attention groups.

A robust system should not need every subgroup to be profitable, but failures must be explainable and predeclared exclusions must be validated out of sample. Report the proportion of folds and seasons with positive ROI, positive CLV, and positive market-relative scoring skill; also report worst-fold results and the gap between median and mean performance.

### Parameter and specification stability

Run local perturbations around every chosen threshold and parameter. A system that works only at spread >= 7.0 but fails at 6.5 and 7.5 has a fragile decision boundary; stable plateaus are more credible than isolated optima.

Required stress tests include:

- Shift every filter threshold up and down.
- Remove one feature or rule at a time.
- Vary training-window length and recalibration cadence.
- Use alternative reasonable de-vigging methods.
- Replace the chosen close with another predefined sharp-book or consensus benchmark.
- Delay bet time and worsen price by realistic slippage.
- Cap maximum stake and liquidity.
- Remove the best season and most profitable subgroup.
- Recalculate after correcting known data-quality issues.

## Execution and capacity

Backtested edge is not monetizable unless the quoted price was available for the required stake when the decision was generated. Execution should therefore be a scored pillar rather than an implementation footnote.

Track:

- Quote timestamp and maximum quote age.
- Decision-to-order latency.
- Requested, accepted, rejected, and partially filled stakes.
- Model price, displayed price, submitted price, and filled price.
- Slippage in probability and expected-return terms.
- Limits and available liquidity.
- Sportsbook concentration and account health.
- Percentage of turnover at sharp versus soft books.
- Capacity curve: expected profit as bankroll and stake size increase.
- Time required per wager and profit per unit of operational effort.

Line shopping can add economic value independently of predictive modeling, so attribute P&L among **model edge**, **price shopping**, **timing**, and **staking** where possible. Evaluate a matched-price version of the candidate and incumbent systems to avoid crediting the model for superior execution.

## Recommended scorecard

Use six visible pillars totaling 100 points, but place integrity gates in front of the score:

| Pillar | Weight | Core inputs |
|---|---:|---|
| Predictive quality | 20 | Market-relative Brier/log/RPS/CRPS skill, calibration slope/intercept, resolution |
| Market-relative value | 15 | No-vig CLV, expected return at close, incremental market-conditioned signal |
| Economic performance | 20 | Net turnover ROI, bankroll growth, profit concentration, edge-decile realization |
| Risk quality | 15 | Sharpe/Sortino, max drawdown, duration, Expected Shortfall, ruin probability |
| Robustness and certainty | 20 | Walk-forward stability, intervals, holdout, sensitivity, DSR/PBO, trial count |
| Execution and capacity | 10 | Fill rate, slippage, limits, liquidity, concentration, scalable expected profit |

This weighting intentionally prevents CLV from dominating. It also keeps profitability central without allowing raw ROI to overwhelm evidence quality.

### Hard gates

A system should be marked **invalid**, regardless of composite score, if any of these is true:

- Unresolved look-ahead leakage or impossible historical feature availability.
- Prices cannot be reconstructed at decision time.
- Materially incomplete bet or trial logging.
- Betting threshold or exclusions were chosen using the final test set.
- Costs, pushes, rejected bets, or limits are materially misstated.
- There is no chronological out-of-sample evaluation.

A system should remain **research-only** rather than production-ready when:

- Out-of-sample proper-score skill versus the market is negative without a compelling execution-only thesis.
- The ROI interval is extremely wide and prospective evidence is absent.
- Profit is dominated by a handful of outcomes.
- Performance collapses under nearby parameters or modest slippage.
- The live sample materially underperforms the predeclared expectation.

### Confidence modifier

Do not award full points from a noisy estimate. For each pillar, calculate a point score and then multiply it by an evidence-confidence factor based on:

- Effective sample size, not raw bet count.
- Out-of-sample share.
- Number of independent seasons and regimes.
- Width of the relevant confidence interval.
- Data-completeness and execution-reconstruction quality.
- Multiple-testing burden.
- Prospective share of the evidence.

A geometric mean across pillars is preferable to a plain arithmetic mean when the goal is to punish a zero in any essential dimension. Alternatively, retain the weighted arithmetic score but cap the total grade whenever a pillar falls below a minimum floor.

## Dashboard specification

### Primary system card

Show only the metrics needed for first-pass judgment:

- Overall grade and validation status.
- Independent events and total wagers.
- Out-of-sample and prospective share.
- Net turnover ROI with 95% interval.
- Net profit and turnover.
- Mean/median no-vig CLV with interval.
- Market-relative Brier or log skill.
- Calibration slope and intercept.
- Maximum drawdown and duration.
- Positive-season and positive-fold rate.
- Fill rate and realized slippage.
- Multiple-testing/trial count warning.

### Diagnostic pages

Use separate pages for:

- **Forecasts:** Brier/log/RPS/CRPS, decomposition, calibration curves, market-conditioned incremental value.
- **Economics:** equity curve, turnover ROI, bankroll return, profit concentration, edge-decile returns.
- **Risk:** drawdown path, loss streaks, Expected Shortfall, ruin simulations under actual and fractional-Kelly staking.
- **Robustness:** fold/season heatmaps, parameter surfaces, ablations, leave-one-group-out results.
- **Market:** CLV distribution, timing curves, reference-book comparison, movement attribution.
- **Execution:** quote freshness, accepted stakes, slippage, limits, capacity curve.
- **Research lineage:** model version, dataset hash, feature availability, trial ledger, validation boundaries, approval history.

## Metric tiers

### Tier 1: mandatory

- Net turnover ROI and profit.
- ROI confidence interval.
- Number of bets and independent events.
- Proper score against the same-time de-vigged market.
- Calibration slope/intercept and reliability plot.
- Mean, median, and positive-rate CLV against a fixed benchmark.
- Maximum drawdown and duration.
- Walk-forward fold and season stability.
- Trial count and final untouched holdout.
- Fill rate, slippage, and actual-price availability.

### Tier 2: strongly recommended

- Brier decomposition.
- Log loss plus RPS/CRPS where appropriate.
- Edge-decile monotonicity.
- Sharpe, Sortino, Calmar, and Expected Shortfall.
- Profit concentration.
- Parameter-neighborhood stability.
- DSR and PBO for large strategy searches.
- Probability that ROI exceeds zero and a practical hurdle.
- Capacity and book-concentration analysis.

### Tier 3: specialist diagnostics

- Forecast-encompassing tests.
- Local or subgroup calibration.
- Alternative de-vigging sensitivity.
- Hierarchical shrinkage of system-level ROI and CLV.
- Change-point and concept-drift detection.
- Causal attribution between model, line shopping, timing, and staking.
- Portfolio correlation and marginal contribution to bankroll risk.

## Filter-based systems

A filter system that does not emit probabilities cannot be evaluated fully with Brier or log loss. It should be treated as a **conditional selection policy**, with its core evidence coming from net ROI, price quality, conditional outcome rate relative to break-even, robustness, and execution.

A better design estimates a shrinkage-adjusted conditional probability for each saved system. Use a hierarchical model that partially pools thin systems toward their parent market or strategy family, then calculate posterior expected ROI, probability ROI exceeds zero, and probability the edge exceeds a practical hurdle. This prevents a 14-3 system from outranking a stable system with hundreds of independent events merely because the small sample's raw ROI is extreme.

For discovered filters, rate the **research process** as well as the final rule:

- Number of candidate systems searched.
- Effective number of distinct trials.
- Discovery-period result.
- Locked confirmation-period result.
- Prospective result.
- Parameter-neighborhood result.
- Leave-one-season-out result.
- Multiple-testing-adjusted evidence.

## Decision rules

A production candidate should satisfy all of the following conceptually:

1. Valid and reproducible historical information sets.
2. Positive out-of-sample market-relative forecast skill or a clearly isolated execution advantage.
3. Acceptable calibration, especially in the wagered region.
4. Positive net economic expectation after realistic costs and slippage.
5. Drawdown and tail risk within bankroll policy.
6. Stability across time and reasonable parameter perturbations.
7. Adequate evidence after accounting for trial count and dependence.
8. Executable capacity sufficient to justify deployment.
9. Prospective tracking that agrees directionally with backtest expectations.

No universal ROI, CLV, Sharpe, or bet-count threshold should define “good.” Required evidence depends on average odds, event dependence, market efficiency, edge size, turnover, and the number of strategies searched. The correct grade should be driven by confidence intervals, effective sample size, and replication rather than generic claims such as “1,000 bets proves an edge.”

## Recommended operating standard

The most defensible evaluation stack is:

- **Model score:** out-of-sample proper-score improvement over a same-time de-vigged market, with calibration and resolution diagnostics.
- **Market score:** fixed-reference no-vig CLV plus a market-conditioned incremental-information test.
- **Economic score:** net turnover ROI, bankroll growth, and edge realization, all with dependence-aware intervals.
- **Risk score:** drawdown, duration, downside-adjusted returns, tail loss, and ruin probability under the actual staking policy.
- **Robustness score:** chronological folds, untouched holdout, sensitivity surfaces, subgroup stability, and multiple-testing adjustment.
- **Execution score:** fill rate, slippage, quote freshness, limits, and capacity.

CLV remains useful because it usually resolves faster than realized outcomes and measures whether the process obtained a favorable market price. But the central question is broader: **Does the system produce calibrated, incremental information and convert it into repeatable, executable, risk-controlled net profit?**

---

## References

1. [Sports prediction and betting models in the machine ...](https://journals.sagepub.com/doi/10.3233/JSA-200463) - The accuracy of the models amounts to about 70% during the calibration and 69% during the prediction...

2. [1Introduction - arXiv](https://arxiv.org/html/2605.16066v1)

3. [[PDF] THE DEFLATED SHARPE RATIO: CORRECTING FOR SELECTION ...](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

4. [The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) - With the advent in recent years of large financial data sets, machine learning and high-performance ...

5. [The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest
               
               Overfitting, and Non-Normality](https://www.pm-research.com/content/iijpormgmt:::40:::5:::94.full.pdf?implicit-login=true&sigma-token=-qe3q8GbUspexC6f_33E65AeFQlY-T4alKKaEuOGB_Q)

6. [Proper Scoring Rules for Estimation and Forecast Evaluation](https://www.research-collection.ethz.ch/server/api/core/bitstreams/a56c57ea-9f4a-4340-a9f6-61016712cd02/content)

7. [Forecast Scoring and Calibration](https://www.stat.berkeley.edu/~ryantibs/statlearn-s23/lectures/calibration.pdf)

8. [[PDF] Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf)

9. [Stable reliability diagrams for probabilistic classifiers - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7923594/) - Probabilistic classifiers assign predictive probabilities to binary events, such as rainfall tomorro...

10. [Brier score - Wikipedia](https://en.wikipedia.org/wiki/Brier_score)

11. [[PDF] Glossary of Forecast Verification Metrics](https://www.weather.gov/media/owp/oh/rfcdev/docs/Glossary_Forecast_Verification_Metrics.pdf)

12. [mwre_132_721.1891_1895.tp](https://journals.ametsoc.org/view/journals/mwre/132/7/1520-0493_2004_132_1891_oucaar_2.0.co_2.pdf)

13. [Quarterly Journal of the Royal Meteorological Society](https://ore.exeter.ac.uk/rest/bitstreams/141507/retrieve)

14. [Simplifying and generalising Murphy's Brier score decomposition](https://ore.exeter.ac.uk/repository/handle/10871/34847?show=full) - The decomposition of the Brier score into Reliability, Resolution and Uncertainty has become a stand...

15. [Cox Calibration Slope and Intercept (GLM on Linear](https://metricgate.com/docs/calibration-slope-intercept-glm/) - Estimate the calibration slope (b) and intercept (a) of any binary risk model by fitting a logistic ...

16. [Towards reliable predictive analytics: a generalized ...](https://arxiv.org/pdf/2309.08559.pdf)

17. [Measuring Calibration in Deep Learning](https://openaccess.thecvf.com/content_CVPRW_2019/papers/Uncertainty%20and%20Robustness%20in%20Deep%20Visual%20Learning/Nixon_Measuring_Calibration_in_Deep_Learning_CVPRW_2019_paper.pdf)

18. [Journal of Machine Learning Research 24 (2023) 1-72](https://jmlr.org/papers/volume24/22-0320/22-0320.pdf)

19. [Understanding Model Calibration - A gentle introduction and visual ...](https://arxiv.org/html/2501.19047v4)

20. [sports-betting/docs/modeling/calibration.md at main · jedi ...](https://github.com/jedi-knights/sports-betting/blob/main/docs/modeling/calibration.md) - A repository to house general purpose code and documentation on sports betting. - jedi-knights/sport...

21. [[PDF] University of Southampton Research Repository ePrints Soton](https://eprints.soton.ac.uk/376060/1/Oikonomidis_2C_20Anastasios_20-_20final_20thesis.pdf)

22. [Information and Market Efficiency: Evidence From the Major ...](https://dash.harvard.edu/server/api/core/bitstreams/24950429-b1b7-4372-a029-1b68de1872e3/content)

23. [University of Southampton Research Repository](https://eprints.soton.ac.uk/376060/1/Oikonomidis%252C%2520Anastasios%2520-%2520final%2520thesis.pdf)

24. [Inefficient Forecasts at the Sportsbook: An Analysis of Real-Time Betting Line Movement | Management Science](https://pubsonline.informs.org/doi/10.1287/mnsc.2022.00456) - This paper tests the efficiency of a set of sports betting markets using detailed betting line movem...

25. [Using Closing Line Value for Historical Edge Testing](https://wagerproof.bet/blog/closing-line-value-sports-betting/) - Learn how to record and compare closing line value, why the exact market and timestamp matter, and w...

26. [the curious case of football match scorelines - CentAUR](https://centaur.reading.ac.uk/92563/1/strange_forecasts_rsb.pdf)

27. [Capturing Intransitive Dominance in Tennis Forecasting](https://arxiv.org/html/2510.20454v2)

28. [Data-Driven Decision Making in Sports Betting: An Empirical ...](https://www.uni-bamberg.de/fileadmin/xai/studies/theses/2026/2026_Bachelorthesis_Di_Bao.pdf)

29. [[PDF] Betting on a buzz, mispricing and inefficiency in online sportsbooks](https://www.reading.ac.uk/web/files/economics/emdp202110.pdf)

30. [Correction study of mispricing and inefficiency in online sportsbooks](https://arxiv.org/html/2306.01740v4)

31. [Risk-Based Performance Measures and Appraisal Ratio](https://analystprep.com/study-notes/cfa-level-iii/risk-based-measures-of-performance-appraisal-2/) - Learn risk-based performance measures, including appraisal and Sortino ratios, used to evaluate acti...

32. [IPM Newsletter_Kidd - CFA Institute](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/code/gips/the-sortino-ratio.pdf)

33. [Level 1 CFA® Exam: Performance Appraisal - Soleadea](https://soleadea.org/cfa-level-1/performance-appraisal)

34. [Measuring Market Risk Under the Basel Accords: VaR, Stressed VaR, and Expected Shortfall](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2252463) - Each of the most recent accords of the Basel Committee on Banking Regulation, known as Basel II, 2.5...

35. [Expected Shortfall - Definition & Example | EC Assets](https://www.ecassets.com/learn/expected-shortfall) - Expected shortfall, or conditional value-at-risk (CVaR), is the average loss in the cases where valu...

36. [On the coherence of expected shortfall - IDEAS/RePEc](https://ideas.repec.org/a/eee/jbfina/v26y2002i7p1487-1503.html) - Expected Shortfall (ES) in several variants has been proposed as remedy for the defi-ciencies of Val...

37. [Portfolio Choice and the Bayesian Kelly Criterion](https://business.columbia.edu/sites/default/files-efs/pubfiles/6343/bayes_kelly.pdf)

38. [Risk-Constrained Kelly Gambling - Stanford University](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)

39. [The Kelly Criterion in Blackjack Sports Betting, and the ...](https://gwern.net/doc/statistics/decision/2006-thorp.pdf)

40. [[PDF] Bootstrap Methods in Time Series Analysis - Stockholms universitet](https://kurser.math.su.se/pluginfile.php/20130/mod_folder/content/0/Kandidat/2018/2018_4_report.pdf?forcedownload=1)

41. [(PDF) The stationary bootstrap (1994) | Dimitris N. Politis](https://scispace.com/papers/the-stationary-bootstrap-2z9yfnpr2x) - (DOI: 10.1080/01621459.1994.10476870) This article introduces a resampling procedure called the stat...

42. [LECTURE ON BOOTSTRAP](https://homepage.ntu.edu.tw/~ckuan/pdf/Lec-Boot_0905.pdf)

43. [Proper Scoring Rule Comparison Calculator](https://metricgate.com/docs/scoring-rule-comparison-proper/) - Compare probabilistic forecasts using Brier, log, and spherical proper scoring rules with Diebold-Ma...

44. [[PDF] Proper Scoring Rules for Evaluating Density Forecasts with ...](https://air.unimi.it/retrieve/dfa8b9aa-3384-748b-e053-3a05fe0a3a96/document.pdf)

45. [[PDF] Forecaster's Dilemma: Extreme Events and Forecast Evaluation](https://www.ecb.europa.eu/press/conferences/shared/pdf/20160603_forecasting/Paper_7_Thoraninsdottir.pdf)

46. [(PDF) The Probability of Backtest Overfitting (2015)](https://scispace.com/papers/the-probability-of-backtest-overfitting-4ublh83xkm) - (DOI: 10.2139/SSRN.2326253) Most firms and portfolio managers rely on backtests (or historical simul...

47. [[PDF] The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality | Semantic Scholar](https://www.semanticscholar.org/paper/The-Deflated-Sharpe-Ratio:-Correcting-for-Selection-Bailey-Prado/950f37470615dc6ae6e1f45f735408af11c48251) - The Deflated Sharpe Ratio (DSR) corrects for two leading sources of performance inflation: Selection...

48. [[PDF] Lawrence Berkeley National Laboratory - eScholarship.org](https://escholarship.org/content/qt2329p290/qt2329p290.pdf)

49. [Chapter 8: Hypothesis Testing and Statistical Significance](https://datafield.dev/sports-betting-textbook/part-02/chapter-08/) - Every serious sports bettor eventually confronts the same uncomfortable question: Is my edge real, o...

50. [Faculty of Business and Economics](https://repository.uantwerpen.be/docman/irua/f3c2d2/188493.pdf)

51. [[PDF] The Probability of Backtest Overfitting | Semantic Scholar](https://www.semanticscholar.org/paper/The-Probability-of-Backtest-Overfitting-Bailey-Borwein/b1233b4f5384f003e85c2e0eec1a2dfc08f624c5) - It is shown that CSCV produces accurate estimates of the probability that a particular backtest is o...

52. [Backtesting & Research Methodology - Trading Strategy documentation](https://tradingstrategy.ai/docs/learn/backtesting.html) - Research papers and posts on backtesting methodology, overfitting, Sharpe ratio correction, walk-for...

