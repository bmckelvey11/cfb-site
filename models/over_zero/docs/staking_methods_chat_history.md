# Staking methods — chat history

Session date: 2026-09-01. Walks through sizing bets for the floor-bias over-zero
strategy: from naive per-bet quarter-Kelly, through a walk-forward backtest, to a
risk-constrained Monte Carlo optimization, stress-tested by an external review.

## 1. Running the model, sizing the current week's picks

`v1/predict_week.py --fetch` for 2026 week 1 (10-season fit, DraftKings lines):
15 of 132 games cleared bias > 1.75.

Naive per-bet quarter-Kelly, sized off each game's own probit-predicted `p_over`
(60-68%), summed to **90.2u** across the 15 simultaneous bets (1u = 1% bankroll)
at -110. That's committing ~90% of bankroll to one Saturday's slate — Kelly's
formula is derived per-bet, not as a portfolio, so naively stacking N independent
per-bet Kelly fractions overcommits fast. Using the conservative Wilson-lower-bound
win rate (58.1%, see below) instead of each game's raw curve brought the flat
per-bet stake to ~3.05u, summing to ~45.8u — still large for one slate. Practical
fix discussed: cap total same-day exposure (e.g. 15-20u) and scale every stake
down proportionally, rather than trust the naive per-bet sum.

## 2. Walk-forward backtest with quarter-Kelly

`monitor/run_walkforward.py --threshold 1.75`: train on seasons < t, bet season t,
236 qualifying bets 2016-2025, 64.41% win rate (Wilson95 [58.1, 70.2]).
`kelly_bankroll_roi()` compounds one bankroll bet-by-bet in chronological order at
quarter-Kelly, -110: **+1521.8% terminal ROI**.

Caveats flagged immediately:
- 2016 is a near-worthless bucket (2 bets, both lost) — model only useful from ~2017 on.
- The bet sequence is treated as strictly sequential; same-week bets are not
  actually simultaneous in reality, so this understates intra-week variance.
- The 64.41% point estimate is inflated by the same threshold-selection bias the
  model's own README already names — the Wilson lower bound (58.1%) is the
  honest number to plan around, not the point estimate.

## 3. Why terminal ROI alone is the wrong number: drawdown

Extended the backtest (`kelly_fraction_backtest.py`) to track **max drawdown**,
comparing Kelly fractions using both the raw per-game model probability and the
Wilson-floor (58.1%) flat probability:

| Fraction | p source | Final bankroll | Max drawdown |
|---|---|---|---|
| Full Kelly | model p | 874x | 83.3% |
| Full Kelly | Wilson floor | 150x | 55.9% |
| Half | Wilson floor | 18x | 32.3% |
| **Quarter** | **Wilson floor** | **4.64x** | **17.3%** |
| Eighth | Wilson floor | 2.2x | 9.0% |

Conclusion at that point: quarter-Kelly off the Wilson floor (not the raw
per-game curve) — ~17% drawdown, ~+364% over 10 seasons, ≈3.05u/bet at -110.

## 4. The Kelly hump: sweeping fraction 0-2.5x

Swept stake fraction from 0 to 2.5x full Kelly (Wilson-floor p) and plotted
drawdown vs. 10-year CAGR. The curve rises with fraction, then **bends
backward** past ~2.1x Kelly on this specific 236-bet historical path — profit
stops increasing while drawdown keeps climbing. Important catch: that 2.1x
"peak" is a **sample-path artifact**, not a target — the true Kelly-optimal
fraction (maximizes expected log growth) is 1.0x by definition; one historical
236-bet sequence can show a different empirical maximum purely from luck. This
is exactly why nobody should read "the empirical peak" off a single backtest
path.

## 5. Finding a risk-constrained optimum, properly

The right question isn't "what maximizes profit" (Kelly already answers that:
full Kelly, in the limit) — it's "what maximizes profit **given a stated risk
budget**," and that requires simulating many paths, not reading one.

Method:
1. State the risk budget in plain terms (e.g. "≤10% chance of a 25%+ drawdown").
2. Monte Carlo many simulated bet sequences per candidate fraction (not the one
   historical path).
3. Filter to fractions satisfying the constraint; take the max-median-growth
   survivor.

First pass — i.i.d. Bernoulli(58.1%) Monte Carlo, 3,000 sims x 236 bets, fraction
swept 0.02-1.0x full Kelly:

| Risk budget | Optimal fraction | Stake/bet | Median 10yr CAGR |
|---|---|---|---|
| P(drawdown > 25%) ≤ 10% | 0.14x | **1.68u** | 4.1%/yr |
| P(drawdown > 50%) ≤ 5% | 0.28x | 3.37u | 7.7%/yr |

Key finding: the single historical path had badly understated real risk. At
"quarter-Kelly" (0.24x), the realized backtest showed 16.7% drawdown, but across
simulated paths there's a **49.9% chance** of a 25%+ drawdown at that same
stake — one lucky path, not the distribution.

Rendered as a chart: P(drawdown > 25%) on x, median CAGR on y, traced over
fraction. Steep rise, then a hard flattening — most of the achievable growth
sits before the 10% risk-budget line; past it, growth increments shrink while
blow-up risk keeps climbing.

## 6. External review (Perplexity) of the methodology

Asked Perplexity to review the approach against Kelly-criterion literature.
Verdict: **"a sensible conservative risk-management prototype... but the
reported risk-constrained stake should be interpreted as conditional on a
simplified Bernoulli world, not a reliable estimate of live bankroll risk."**

Specific findings:
- **(a) Wilson lower bound as flat p:** defensible stress case, not standard
  practice — treats "uncertainty about the average" as "every bet has this
  exact p," discarding edge heterogeneity. Better: calibrated per-bucket
  probabilities, shrinkage toward market, Bayesian posterior over p.
- **(b) i.i.d. Bernoulli Monte Carlo:** answers a narrow question only. Misses
  parameter uncertainty, season/serial clustering, non-stationarity,
  simultaneous-bet exposure, selection bias in which bets qualified.
- **(c) Fractional Kelly pitfalls, confirmed:** Kelly maximizes E[log wealth],
  not median CAGR or P(drawdown > X) — a "risk-constrained Kelly" is a
  different optimization, not Kelly-optimal by definition. Picking a fraction
  because it satisfies a backtested drawdown rule is itself a form of
  overfitting. 236 bets is thin for tail-risk claims.
- **(d) What's missing:** out-of-sample calibration by probability bucket,
  block bootstrap instead of i.i.d. (to preserve season clustering), real
  historical odds instead of flat -110, and separating model validation from
  staking-rule validation instead of tuning both on the same 236 bets.

## 7. Incorporating the review: season block bootstrap

Rebuilt the Monte Carlo to resample whole real seasons with replacement
(2016's 0/2 disaster and 2019's 13/16 boom each keep their own weight) instead
of i.i.d. Bernoulli at one flat rate. 5,000 sims:

| Fraction | Stake | Median CAGR | P(DD>25%) | P(DD>50%) |
|---|---|---|---|---|
| 0.14x | 1.68u | 9.3% | **4.7%** | 0.0% |
| 0.18x | 2.17u | 11.8% | 14.5% | 0.0% |
| 0.24x | 2.89u | 15.7% | 33.4% | 0.9% |
| 0.28x | 3.37u | 18.7% | 47.2% | 2.3% |
| Full | 12.04u | 64.7% | 100.0% | 85.0% |

Result held up: **0.14x (1.68u/bet) stays optimal at the 10% risk budget**, and
actually looks *safer* under the more rigorous method (4.7% vs. 8.5% chance of
a 25%+ drawdown) — season-level resampling gives each real season equal weight
instead of letting bet-count size distort the pooled rate.

Still open, per the review: only 10 real seasons to bootstrap from (a genuine
regime break has never been observed); stake-sizing p is still fixed at 58.1%
rather than itself carrying posterior uncertainty; flat -110 assumed throughout;
same 236 bets used to both build the model and validate the staking rule.

## 8. Low/high risk range

| | Fraction | Stake | Median CAGR | P(DD>25%) | P(DD>50%) |
|---|---|---|---|---|---|
| **Low risk** | 0.10-0.14x | 1.2-1.7u/bet | 6.5-9.3%/yr | 0.6-4.7% | ~0% |
| **High risk** | 0.28-0.32x | 3.4-3.9u/bet | 18.7-20.9%/yr | 47-62% | 2.3-5.2% |

Hard ceiling regardless of taste: past ~0.4x (4.8u/bet), P(DD>50%) climbs into
double digits fast (12.5% at 0.4x, 27.6% at 0.5x) for shrinking CAGR gains —
nobody should be above there.

## 9. Why not size bets by edge magnitude (per-game bias)?

Checked the actual evidence (`monitor/bias_bins.py`, disjoint bins) instead of
assuming either way:

| Bias bin | N | Win% | Model's predicted p | Clears breakeven? |
|---|---|---|---|---|
| 0.50-1.00 | 367 | 52.46% | 51.92% | no |
| 1.00-1.75 | 447 | 52.08% | **55.93%** | **no** — [47.5, 56.6] |
| 1.75-2.50 | 158 | 64.56% | 61.27% | yes |
| >2.50 | 78 | 64.10% | 66.67% | yes |

Two problems with graduated sizing off the model's continuous curve:
1. The two bins that clear breakeven are statistically indistinguishable from
   each other (64.56% vs 64.10%, overlapping CIs, only 78 bets in the top bin)
   — the curve claims rising edge past bias 2.5, the data doesn't confirm it.
2. Below the operational cutoff the curve is wrong in the dangerous direction:
   bin 1.00-1.75 predicts 55.93% but realizes only 52.08% — doesn't clear
   breakeven once vig is priced in.

Conclusion: edge-proportional sizing is correct Kelly theory in principle, but
*this specific fitted curve* was built on the same data used to pick the 1.75
threshold, and the one test built to check it at finer resolution says the
curve doesn't hold up past the binary qualify/don't-qualify cut. Flat sizing
isn't ignoring real information — it's declining to act on a slope nobody's
shown is real. A defensible middle ground, if wanted: a two-tier split
(below/above 1.75), since that's the one cut with evidence behind it — a third
tier at 2.5 is not supported by the sample.

## Bottom line

**1.68u per qualifying bet** (0.14x full Kelly, sized off the 58.1% Wilson
floor) is the number that survived: a naive per-bet backtest, a drawdown sweep,
an i.i.d. Monte Carlo, an external methodology review, and a season-clustering
bootstrap re-run. Every layer of scrutiny either confirmed it or made it look
more conservative, not less. Open risk that hasn't been (and can't fully be)
closed: only 10 real seasons observed, no true out-of-sample regime break in
the sample, and the model/staking rule were both tuned on the same 236 bets.
