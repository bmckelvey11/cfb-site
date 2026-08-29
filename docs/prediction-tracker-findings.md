# Prediction Tracker analysis — consolidated findings

Entry point for the whole line of work, 2026-08-29. Each section points at the document that
carries the detail; nothing is restated here that those files already establish.

| Document | What it holds |
|---|---|
| `prediction-tracker.md` | The joined dataset: 154 model columns, 17,731 games, 2001–2025, column dictionary |
| `prediction-tracker-model-eval-plan.md` | Pre-registration, committed before any fitting |
| `prediction-tracker-model-eval.md` | Per-model leaderboard, the pre-registered ensemble, **§10 correction** |
| `prediction-tracker-model-eval-plan-addendum.md` | Pre-registration for the nine-method sweep, and **§11** for recency |
| `prediction-tracker-combination-sweep.md` | Results of the nine-method sweep |
| `prediction-tracker-recency-screen.md` | Results of recency weighting and cohort pooling |
| `line-timing-collector.md` | The forward collector, operational runbook |
| `research-prompt-forecast-combination.md` | First research prompt (answered, implemented) |
| `research-prompt-open-questions.md` | Second research prompt — what these results left open |

---

## 1. The three findings

### The closing line is not beatable with this panel

Not by any of the 154 models individually (0 beat it at BH q < 0.05), and not by any of ten
combination rules: screened consensus, market-residual ridge, Stock–Watson shrinkage, residual
principal components, partially-egalitarian LASSO, trimmed consensus, combination elastic net,
online Hedge aggregation, screened complete subset regression, and the original pre-registered
ensemble. **The best Holm-adjusted p is 0.4865**; every other one is 1.000. Best point estimate
across all of them: −0.159 MSE. One estimator (ridge) is significantly *worse* than the
recalibrated line, at +1.106.

This is a tight null, not an underpowered one. The design detects 0.078 RMSE at 80% power; the
interval rules out gains above roughly 0.02 RMSE.

Adding recency weighting, rolling windows, credibility shrinkage, two-window blends, a
new-entrant sleeve and cohort adjustment changes nothing: best closing-line figure across all
ten further specifications is −0.112 at p = 0.28.

### The same panel decisively beats the *opening* line

Harvey–Newbold joint encompassing test, five pre-specified directions:

| | opening | closing |
|---|---|---|
| Wald | **70.10** | 5.44 |
| bootstrap p | **0.0005** | 0.5595 |
| | line does **not** encompass the panel | line encompasses the panel |

The fitted weight on the model consensus is **0.37** against the open and **0.10** against the
close. The market absorbs roughly three quarters of what the panel knows between opening and
closing.

Two of the three method families survive removal of the market-like columns: the consensus
family retains ~73%, complete subset regression 49%, both still significant. **The ridge
retains 27% and stops being significant** — its opening-line figure is substantially market
proxying (§4).

**No method converts this into a bet.** Every ATS record against the closing line is below the
−110 break-even of 52.38%; the single positive cell in the whole analysis is 108 bets at one
standard error above break-even.

### Signal exists but does not survive estimation

Clark-West rejects against the recalibrated closing line (+0.271, one-sided p = 0.002) while the
plain paired difference does not (−0.128 [−0.312, +0.052], p = 0.15). The population signal is
real; the cost of estimating how much weight to give it destroys it out of sample.

The clearest single demonstration is not a p-value. **Every hyperparameter selection rule ran to
its most conservative setting, in 20 of 20 seasons, for every method, on both benchmarks.**
Widen the grids and they keep going — ridge λ to 10⁷, learning rate to 10⁻⁵, the mean correction
shrinking to 0.019 points. Stock–Watson shrinkage, handed a free scalar and asked how much of
the panel correction to keep, kept **none**. The elastic net independently zeroed every
coefficient.

---

## 2. Findings that were not the question but matter more than some answers

### Two "models" were the benchmark under another name

`lineca` reproduces the closing line **exactly on 65.6%** of its 15,003 games (RMSE-to-close
0.501, against a 6.20 panel median). `linemidweek` matches exactly on 43.3%. Both are market
lines reprinted inside the model panel.

`lineca` ranked **#1 in the top-20 skill screen in all 20 evaluated seasons.** Every
screened-consensus result published before the audit — including the pre-registered primary —
used a screen whose best member was the closing line.

It retracts the parent analysis's single-model claims: `lineca` tying the close and beating the
open by 5.089 MSE is arithmetic, and its "five times steadier than any other model" stability is
the same artifact. Removing both retains 83% of the opening-line effect, because an
equal-weighted top-20 dilutes any one member to a twentieth. **There is no single column in this
panel worth using on its own.**

### Relative skill is persistent and completely stable

Season-to-season Spearman rank correlation of model skill: **0.775**. Offered decay factors
ρ ∈ {0.80, 0.85, 0.90, 0.95, 0.975, 1.00}, forward validation chose **ρ = 1.00 — no decay — in
20 of 20 seasons on both benchmarks.** Giacomini–Rossi finds no instability on either
(p = 0.71, 0.92).

The raw grid agrees more loudly than the selection does: the best ρ lands on 1.00, 0.80, 0.90,
0.85, 0.90, 1.00 across six adjacent screen widths. A real decay signal does not reverse
direction because the screen got four models wider.

### Newer models are better, not luckier

A cohort correction was built on the standard premise — a recent entrant has only operated in the
current environment and might look good for that reason. **The data say the reverse.** Adjusting
ability for entry year replaced the top of the screen almost entirely (1 of 8 models in common
in 2020) and cost 15% of the opening-line effect. The best forecasters *are* recent entrants;
the trend read their genuine advantage as a cohort effect and removed it.

### What the panel's best forecasters actually are

With the market lines gone, the 2025 top five is `lineespn`, `lineteamrank`, `linedokter`,
`linepimean`, `linepibias`. These were invisible for the entire analysis because a market feed
outranked all of them.

---

## 3. Corrections to my own work

Every one of these was found during the analysis and is recorded rather than quietly fixed. Two
would have invalidated headline numbers.

| # | Defect | Consequence had it stood |
|---|---|---|
| 1 | **Clark-West sign** — spreads passed to a function taking margins | An absurd +23 adjusted mean where the correct value is +0.45. Caught by magnitude alone. |
| 2 | **Methods did not nest the benchmark** — fitting `y − mkt ~ deviations` pins the market coefficient at 1, so no method could reproduce the recalibrated line | Every comparison against R0, Clark-West included, formally invalid. Rebuilt on Frisch–Waugh anchoring, with a test asserting it reproduces the original estimator to 1e-8. |
| 3 | **Support collapse** — one method that cannot fit before ~2011 was silently deleting those seasons for every other method | n fell from 14,347 to 9,234 with no indication why. Short-coverage methods now scored on their own support with n shown. |
| 4 | **Coverage filter was a tenure test** — measured over the whole training history, so a model launched in 2015 could never qualify however complete its record | Regression methods fit on ~14 old models rather than the season's ~39 active ones, **excluding the two best forecasters in the panel**. See §4. |
| 5 | **Giacomini–Rossi statistic uncentred** while its bootstrap imposed the null by centring | Tested "is the difference nonzero", not "does it change over time" — a uniformly-better method would have tripped it. Found by writing its test. |
| 6 | **Misleading RMSE column** — a method on reduced support printed beside the shared market RMSE | Reproduced the coverage-difficulty confound the plan names as threat #1, inside a document whose §1 explains that confound. Every row now carries the market's RMSE on its own games. |
| 7 | **Stability gate half-inert** — `sign_stability` is bounded below at 0.50 and returns 1.00 for a consistently tiny coefficient as readily as a large one | The gate was effectively one criterion, not two. Recorded, not retrofitted. |

### Pre-registration scorecard

Eight expectations were written down and committed before fitting. **Four were wrong.**

| Round | Expectation | Outcome |
|---|---|---|
| Sweep | K-by-rule will score worse than K = 20, exposing the latter as selection-inflated | Correct, wrong reason — the rule chose "all" in 20/20 seasons, meaning K is **not identifiable out-of-sample at all** |
| Sweep | Market-residual ridge beats E5, still not R0 | **Wrong on both** after the §4 fix — it beats R0 on opening, and is significantly *worse* than both R0 and E5 on closing |
| Sweep | Online aggregation and CSR will not help | Half wrong — **CSR was the only exploratory method to survive Holm**, and after the §4 fix it does so on full support at p < 0.0001, beating the reference in all 20 seasons |
| Sweep | No method passes the stability gate | Wrong — seven did, and the gate was weaker than designed (defect 7) |
| Recency | ρ = 1.00 selected in a majority of seasons | Confirmed, unanimously |
| Recency | No recency scheme changes the closing-line null | Confirmed |
| Recency | Giacomini–Rossi rejects on opening, not closing | **Wrong** — rejects on neither. The open/close gap is a difference in level, not drift over time; I had conflated them |
| Recency | Cohort trend small, will not reorder the screen | **Wrong on both clauses** |

The pre-registration earned its keep in a way worth stating: K was fixed at 20 in advance, and
K = 20 later proved the single most favourable value tested — the effect vanishes at 5, 10, 40
and 80. Had it not been fixed first, a search would have found 20 and reported it as a finding.

---

## 4. The tenure-test defect, quantified

`regressor_cols` required a model to cover 80% of **all** prior training games. Because
missingness is season-level, that is a test of when a model launched, not of how complete its
record is.

At the 2025 season it kept **14 of 39** active models, median entry year 2002, and excluded
`lineespn` and `lineteamrank` — the two best forecasters in the panel. Measuring coverage over
the seasons a model actually published in keeps **37 of 39**.

This affected every regression-family method (market-residual ridge, residual PCs, elastic net,
LASSO screening, CSR). It did **not** affect the consensus family (screened consensus, trimmed
consensus, K-by-rule, online), which uses the active set directly.

Fixing it is a bug repair, not a re-specification: the pre-registered plan says "the model set
*active in that season*", and the code did not implement that.

### What the fix changed

| | before | after |
|---|---|---|
| E6 market-residual ridge, opening | −2.383 | −3.521 (p<0.0001) |
| E6, **closing** | −0.152 | **+1.106** (p=0.048) — significantly *worse* than the recalibrated line |
| E14 screened CSR, opening | −1.344, Holm 0.0245, on 15 of 20 seasons | **−2.615**, Holm <0.0001, on **all 20** |
| E14, closing | −0.023 | −0.159, Holm 0.4865 |
| E8 / E12, opening | 0.000 (degenerate) | −0.165 / −0.263 |

**E14's largest caveat disappeared.** The filter was what starved complete subset regression of
models before 2011. It now runs on full support, beats R0 in every one of 20 seasons, and — per
the decontamination check below — its effect is not market proxying.

**E6 inverts on the closing line.** Given 37 regressors instead of 14 it goes from −0.152 to
+1.106. That is the whole thesis as a sign flip: the same estimator on the same regressors gains
3.5 MSE where signal exists and loses 1.1 where it does not.

### And a second finding the fix exposed

Re-running the market-proxy check under the corrected filter separates the method families:

| opening line | all 154 | minus the 15 most market-like | retained |
|---|---|---|---|
| E4 (consensus) | −1.976 p=0.0030 | −1.446 p=0.0415 | **73%** |
| E11 (trimmed consensus) | −1.150 p=0.0665 | −0.867 p=0.1420 | **75%** |
| E14 (subset regression) | −2.615 p<0.0001 | −1.285 **p<0.0001** | **49%** |
| **E6 (ridge)** | −3.521 p<0.0001 | **−0.966 p=0.2560** | **27%** |

**E6's headline is substantially market proxying and must not be quoted as model skill.** With
a large regressor set, ridge loads on the partially market-anchored columns (movement
correlations 0.49–0.76) that an equal-weighted consensus dilutes to a twentieth each. The
consensus family and CSR both survive; the ridge does not.

**One lead, and only a lead.** On the *closing* line E14 strengthens under decontamination:
−0.159 (p=0.0695) becomes −0.193 [−0.344, −0.045], p=0.0125. This is a post-hoc variant of the
winner of an eight-member family with no confirmation window — Holm across that family puts it
near 0.10. It is a candidate for future pre-registration, not a closing-line edge.

---

## 5. What is still open

**The one question the archive cannot answer.** Prediction Tracker publishes mid-week and keeps
no publication timestamp, so it is impossible to know what price was available when a forecast
appeared. The opening-line edge is therefore an **unreachable upper bound**, not a strategy. A
forward collector has been running since 2026-08-29 to settle it prospectively
(`line-timing-collector.md`); it cannot produce an answer until roughly a season of snapshots
exists, and nothing it collects changes the verdict on 2001–2025.

**A fading advantage, or noise.** The opening-line effect is −1.52 (p = 0.028) on the full
window, −0.745 (p = 0.54) post-2014, and +0.040 (p = 0.94) post-2021. Consistent with decay, and
equally consistent with noise — those windows carry intervals of ±2.5 and ±2.9. Giacomini–Rossi,
which uses the full span and is built for the question, finds nothing. The honest statement is
that the recent era cannot resolve an effect of this size.

**Methodological questions the results raised**, written up as a second research prompt in
`research-prompt-open-questions.md`: selection-adjusted inference with no confirmation window;
why CSR survived where every shrinkage estimator collapsed; whether the 1-SE rule is
systematically wrong for a small correction to a strong benchmark; benchmark contamination as a
named problem in forecast panels; when cohort adjustment destroys signal; the power of stability
tests at 20 observations; whether squared error is the right loss for a betting decision; which
market number is the right benchmark; and whether closing line value actually predicts realised
profit.

---

## 6. What to use

- **If you have the closing line, use the closing line.** Nothing here improves on it, and the
  interval is tight enough to assert that rather than merely fail to reject it.
- **If you are forecasting before close** — grading an opener, setting a midweek number,
  reacting to a slow book — the panel is worth roughly 1.3–1.4 MSE once the market-like columns
  are removed. Use a screened consensus or complete subset regression; **do not use the ridge**,
  whose apparent advantage is 73% market proxying.
- **Drop `lineca` and `linemidweek` first.** They dominate any skill screen and add nothing a
  market feed does not.
- **There is no single column worth using alone.**
- **Do not average all the models** — 9.3 MSE worse than doing nothing.
- **Weight all seasons equally**, and do not adjust models for when they joined.
- **Keep the screen narrow** — the opening-line effect peaks around eight models and decays past
  it. A shape, not a tuned value: the intervals are far too wide to pick a winner.
- **Do not build a cleverer combiner.** Ten were tried.
