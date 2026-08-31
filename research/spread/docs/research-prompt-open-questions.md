# Research prompt — open questions after the model-panel analysis

For Perplexity or any deep-research tool. Second prompt in this line; the first
(`research-prompt-forecast-combination.md`) asked which combination methods to try, was
answered, and the methods were implemented and run. This one asks about the problems that
surfaced *from the results*.

Grounded in measured numbers throughout so the answer engages with this regime rather than
returning a survey. Paste everything below the line.

---

I have completed a pre-registered evaluation of a large panel of published point forecasts
against a betting-market benchmark, and I have specific methodological problems left over. I
want named methods, primary citations, and a judgement on applicability to my setup — not a
general survey. Where the evidence is thin or contested, say so explicitly.

## Setup, briefly

- **Target:** final margin of a college football game, ~N(4.6, 21²).
- **Panel:** 154 published computer models, 17,731 games, 25 seasons (2001–2025). Unbalanced;
  missingness is *season-level* (a model publishes in a season or does not). Median game has
  48 of 154 present. 42 models have fewer than 3 seasons; 62 have 10 or more.
- **Benchmark:** the betting market's closing spread (RMSE 15.62) and opening spread (15.77),
  reported separately throughout.
- All evaluation walk-forward (weights for season *t* fit only on seasons < *t*); inference by
  wild cluster bootstrap at season level (25 clusters); Benjamini–Hochberg or Holm as
  appropriate; everything pre-registered before fitting.

## What I found

1. **No individual model and no combination beats the closing line.** Ten combination rules —
   screened consensus, market-residual ridge, Stock–Watson shrinkage, residual principal
   components, partially-egalitarian LASSO, trimmed consensus, combination elastic net, online
   Hedge aggregation, complete subset regression. The best Holm-adjusted p against the closing
   line is **0.49**; every other one is 1.000. Best point estimate −0.159 MSE. One estimator
   (ridge) is significantly **worse** than the recalibrated line, at +1.106 (p = 0.048).
2. **The same panel decisively beats the *opening* line.** Harvey–Newbold joint encompassing:
   Wald 70.1, p = 0.0005 against the open; Wald 5.44, p = 0.56 against the close. The fitted
   weight on the model consensus is ~0.37 against the open and ~0.10 against the close.
3. **Every hyperparameter selection rule ran to its most conservative setting**, in 20 of 20
   seasons, for every method, on both benchmarks. Widening the grids post hoc, they keep going:
   ridge λ to 10⁷, learning rate to 10⁻⁵, mean correction shrinking to 0.019 points.
   Stock–Watson shrinkage, given a free scalar for how much of the panel correction to keep,
   chose exactly zero against the closing line. Elastic net independently zeroed every
   coefficient. Against the *opening* line both keep a sliver — 0.03 and 0.17 points — which is
   the entire open/close difference expressed as a hyperparameter.
4. **Clark-West rejects where the paired difference does not.** Against the recalibrated closing
   line, CW gives +0.271 (one-sided p = 0.002); the plain paired ΔMSE is −0.128 [−0.313, +0.050],
   p = 0.15. Population signal exists; it does not survive the cost of estimating its weight.
5. **Relative skill is highly persistent and completely stable.** Season-to-season Spearman
   rank correlation of model skill is 0.775. Offered decay factors ρ ∈ {0.80 … 1.00}, forward
   validation chose ρ = 1.00 (no decay) in 20 of 20 seasons on both benchmarks. A
   Giacomini–Rossi fluctuation test finds no instability on either (p = 0.71, 0.92).
6. **Two "models" were the benchmark under another name.** One column reproduced the closing
   line *exactly* on 65.6% of its 15,003 games (RMSE-to-close 0.501 against a 6.20 panel
   median); a second on 43.3%. The first ranked #1 in the top-20 skill screen in all 20 seasons.
   Removing both retained 83% of the opening-line effect.
7. **A cohort/vintage correction removed genuine skill.** Adjusting model ability for entry-year
   (linear trend, since cohorts are 87/29/29/5/4) replaced the top of the screen almost entirely
   (1 of 8 in common in one season) and cost 15% of the effect. The best forecasters are recent
   entrants; the trend read their advantage as a cohort effect and adjusted it away.
8. **Estimator families differ sharply in how much benchmark contamination they absorb.** Beyond
   the two outright market lines, a further ~13 columns are *partially* market-anchored
   (correlation 0.40–0.76 between their deviation from the opening number and the market's own
   open-to-close move). Dropping the top decile by that correlation, on the opening line:

   | method | all 154 | minus 15 | retained |
   |---|---|---|---|
   | screened consensus | −1.976 (p=0.003) | −1.446 (p=0.042) | **73%** |
   | trimmed consensus | −1.150 (p=0.067) | −0.867 (p=0.142) | **75%** |
   | complete subset regression | −2.615 (p<0.0001) | −1.285 (**p<0.0001**) | **49%** |
   | **market-residual ridge** | −3.521 (p<0.0001) | **−0.966 (p=0.256)** | **27%** |

   An equal-weighted consensus dilutes any one contaminated member to 1/k. A ridge with ~37
   regressors can put weight on exactly those columns, so most of its apparent advantage is
   market content. **This was invisible until I ran the check.**
9. **Complete subset regression was the only method to survive multiplicity correction**, at
   Holm p < 0.0001 against the opening line, beating the recalibrated benchmark in **all 20**
   seasons, on full support, and retaining half its effect after decontamination. Every
   shrinkage-type estimator on the same data collapsed toward zero correction.
10. **A specification defect that is itself a methodological question.** My regressor-eligibility
    filter required a model to cover 80% of *all* prior training games. Because missingness is
    season-level, that is a test of *when a model launched*, not of how complete its record is —
    a forecaster starting in 2015 covers well under 80% of games since 2001 however perfect its
    record. It kept 14 of 39 active models, median entry year 2002, and excluded the two best
    forecasters in the panel. Fixing it moved subset regression from 15 of 20 seasons to all 20,
    and flipped the ridge's closing-line result from −0.15 to **+1.11**.

## The questions

### 1. Selection-adjusted inference with no confirmation window (highest priority)

One method (complete subset regression after screening) survived Holm correction among an
eight-member family, at adjusted p < 0.0001, ΔMSE −2.615 against the opening line, beating the
recalibrated benchmark in all 20 seasons. I have **no usable holdout**: a 2021–25 confirmation
window has an MDE of 0.161 RMSE against a full-window 0.078, so it could not confirm the effect
it would exist to check. I therefore pre-registered the primary claim instead and reported the
winner as a selection estimate with no way to shrink it.

A related sub-case I am treating conservatively: on the *closing* line the same method moves
from −0.159 (p = 0.070) to −0.193 (p = 0.013) once the market-anchored columns are removed. That
is a post-hoc variant of the family winner, so I am calling it a candidate for pre-registration
rather than a result. Is that the right call, or is there a defensible way to evaluate it now?

Is that the best available? Specifically:

- Does **Andrews, Kitagawa & McCloskey, "Inference on Winners"** apply to a *paired forecast-loss
  differential* with clustered dependence, and would it give a usable median-unbiased or
  conditional estimate here?
- What about **post-selection inference** (Berk, Brown, Buja, Zhang & Zhao PoSI) or **selective
  inference** (Lee, Sun, Sun & Taylor)? These were developed for regression coefficient
  selection — do they transfer to selecting among *forecasting methods* by out-of-sample loss?
- Is there a literature specifically on **winner's-curse correction in forecast-comparison
  tournaments**, e.g. selecting the best of many models by out-of-sample MSE?
- Practical: with 25 season clusters, is a bootstrap-based selection adjustment feasible, or is
  the cluster count fatal to all of these?

### 2. Why did complete subset regression survive when the shrinkage estimators did not?

CSR (Elliott, Gargano & Timmermann 2013) after screening to 10 models at subset size k = 1–3
was the only exploratory method to clear multiplicity correction. Ridge, LASSO, elastic net,
Stock–Watson shrinkage and residual PCA all collapsed toward zero correction on the same data.
CSR also proved far more robust to benchmark contamination than the ridge (finding 8): it kept
49% of its effect where the ridge kept 27% and lost significance.

- Is there theory explaining when CSR's implicit shrinkage differs *in kind* from ridge-type
  shrinkage — particularly under a **strong external benchmark** that is not one of the
  regressors?
- Is my result plausible, or is it a multiplicity artifact I should discount? The reduced-support
  caveat I originally attached to it turned out to be my own filter bug (finding 10) and is gone;
  it now runs on full support and wins every season. That makes me *more* suspicious, not less,
  because it is now the single standout in a family where everything else is flat.
- Does the literature report CSR advantages that survive honest out-of-sample evaluation, as
  opposed to in-sample or pseudo-out-of-sample comparisons?
- Is the **averaging across subsets**, rather than the subset size, doing the work? CSR at k = 1
  was selected in every season, which makes it close to an equal-weighted average of many
  one-regressor corrections — is that a known special case, and does it explain the robustness?

### 3. Is the 1-SE rule the wrong selection rule for a small correction to a strong benchmark?

I used "most conservative value within one standard error of the best inner-validation MSE",
with the conservative direction fixed in advance. On the closing line it behaved sensibly. On
the **opening** line, where real signal exists, it cost a large amount: widening the ridge grid
let it pick λ = 10⁷ instead of 10⁴, and the out-of-sample ΔMSE went from −2.383 to −0.210. The
inner validation could not distinguish the two within one SE, so it took the conservative one
and discarded a genuine gain.

- Is the 1-SE rule known to be **systematically too conservative** when the estimand is a small
  correction on top of a dominant benchmark? What is the current view on 1-SE versus min-CV?
- Are there principled alternatives — a scaled c·SE rule, a decision-theoretic selection rule,
  or a rule that accounts for the *asymmetry* between over- and under-shrinkage in this setting?
- Is there work on selection rules where the null (no correction) is itself a strong,
  theoretically-motivated default rather than an arbitrary origin?

### 4. Benchmark contamination inside forecast panels

I found market lines masquerading as forecasts inside a published panel. My pre-registered plan
listed four threats and this was not among them; I had taken the panel's naming convention at
face value.

- Is this a **known and named problem** in the forecast-panel literature — Survey of
  Professional Forecasters, Blue Chip, Consensus Economics, or sports/prediction-market panels?
  Does anyone screen survey respondents for copying a public benchmark?
- What **detection methods** exist beyond the two I used (exact-match rate to the benchmark; the
  correlation between a forecaster's deviation from the opening number and the benchmark's own
  subsequent move)?
- After removal, ~13 columns remain intermediate — correlation 0.40–0.76 with the market's
  open-to-close move. Is there principled guidance for **partially** market-anchored forecasters,
  short of dropping them? Dropping by a decile threshold is arbitrary and I would prefer a rule.

### 4b. Why does an equal-weighted consensus resist contamination that a ridge amplifies?

This is the finding I least expected and can least explain (finding 8). With the same panel, the
same benchmark and the same walk-forward protocol, removing the 15 most market-like columns costs
a screened consensus 27% of its effect and a market-residual ridge **73%**, taking the ridge from
p < 0.0001 to p = 0.256.

- Is this a **named phenomenon**? The mechanism I assume is that equal weighting caps any one
  contaminated member at 1/k while a penalised regression is free to load on precisely the
  columns most correlated with the target. Is that the accepted explanation, and is it
  quantified anywhere?
- Does it imply a general **robustness argument for simple averaging** in panels of uncertain
  provenance — i.e. that the forecast-combination puzzle has a data-integrity component, not
  only a bias-variance one?
- Is there a diagnostic that detects this **without** having a contamination measure to test
  against? I only found it because I had a benchmark-similarity metric. In a panel where I could
  not construct one, what would have flagged it?

### 5. When does cohort/vintage adjustment destroy signal?

The correction was motivated exactly as the literature suggests: newer entrants have only
operated in the current environment and might look good for that reason. Empirically the reverse
held — newer entrants were genuinely better, and adjusting for entry year promoted worse,
longer-tenured models.

- Is there literature on **entry-cohort quality trends** among forecasters — evidence that later
  entrants are systematically better because methods improve?
- What diagnostics distinguish "this cohort had an easier environment" from "this cohort is
  genuinely better" in an unbalanced panel, *before* applying the correction?
- Is the failure mode I hit — a cohort covariate collinear with true quality — discussed
  anywhere?

### 5b. Eligibility rules in unbalanced forecaster panels

My filter (finding 10) silently became a tenure test: requiring coverage of 80% of *all* prior
observations excludes every late entrant regardless of record quality, because missingness is
season-level rather than observation-level. It cost me the two best forecasters in the panel and
I did not notice for two rounds of analysis.

- Is this a **known trap** in unbalanced-panel forecast evaluation, and does it have a name?
- What is the recommended way to decide **which forecasters are eligible to carry a coefficient**
  when tenure varies from 1 to 25 periods — a minimum effective sample, a within-active-period
  coverage rule, or something that handles both jointly with the shrinkage?
- Is there guidance on how eligibility thresholds interact with **entry-cohort composition**?
  Mine correlated eligibility with entry year almost perfectly, which is precisely the confound
  the cohort correction in finding 7 was supposed to address.

### 6. Detecting slow decay in relative performance with ~20 time-series observations

Giacomini–Rossi finds no instability (p = 0.71). But my post-2014 and post-2021 subsamples give
−0.745 (p = 0.54) and +0.040 (p = 0.94) against the opening line, versus −1.52 (p = 0.028) on
the full window — *consistent* with a fading advantage and equally consistent with noise, since
those windows carry intervals of roughly ±2.5 and ±2.9.

- What is the **power** of the Giacomini–Rossi fluctuation test with ~20 seasonal observations
  of clustered data? Is a null result at this length informative or merely uninformative?
- Are there better instruments for **gradual decay** as opposed to a break — Inoue & Rossi,
  Rossi & Sekhposyan, or time-varying-parameter approaches?
- How should I reconcile a stability test that finds nothing with subsamples that hint at a
  trend, when the subsamples are underpowered by construction?

### 7. Is squared error the right loss for this decision?

I evaluate with MSE (the consistent scoring rule for a conditional-mean point forecast) and
report against-the-spread record separately. They disagree in emphasis: methods with better MSE
do not have better ATS records, and no method clears −110 vig.

- What does the literature say about **decision-based forecast evaluation** for spread betting
  specifically — cover probability, or the asymmetric/economic loss functions of Elliott,
  Komunjer & Timmermann?
- Is an MSE-optimal combination known to be **decision-suboptimal** when the decision is a
  binary bet at a fixed price? Is there work on combining forecasts to maximise a betting
  criterion rather than to minimise squared error?
- Given a fixed −110 price, is there a principled minimum MSE improvement below which no
  strategy can profit, that I could compute and quote as a bar?

### 8. Which market number is the right benchmark?

My benchmark is a single recorded consensus closing spread. Real betting happens against many
books at different numbers.

- Is there literature on **market dispersion / best-line shopping** as the correct benchmark,
  rather than a consensus number? How much of an apparent edge typically survives moving from
  "beats the consensus close" to "beats the best available price"?
- Conversely, is "beats the consensus close" too *easy* a bar because the consensus is
  contaminated by slow books?

### 9. Does closing line value actually predict profitability?

My unresolved empirical question is whether an edge measured at the opening number survives at a
price I could have taken; I have a forward collector running to answer it.

- What is the **empirical** evidence that closing line value predicts realised ROI in sports
  betting markets? I am aware this is treated as folk wisdom by bettors; I want peer-reviewed or
  serious working-paper evidence, and evidence against it if it exists.
- Is there work on the **time path of market efficiency** within the open-to-close window in US
  sports markets — when does the number become efficient, and are early prices available at
  meaningful size?

### 10. Persistent skill without exploitable edge

Cross-sectional skill differences among my forecasters are large and persistent (rank
correlation 0.775 season to season), yet none beats the benchmark and no combination does
either.

- Is there a literature reconciling **persistent relative skill among forecasters with an
  efficient aggregate benchmark**? The obvious analogue is mutual-fund performance persistence
  versus index efficiency — does that framing transfer, and what does it predict?
- Should persistence itself have implied an exploitable edge, such that its absence is evidence
  of something specific about how this market aggregates?

### 11. Inference at 20–25 clusters

Everything rests on a wild cluster bootstrap-t at season level, with 25 clusters (20 in the
walk-forward window), Rademacher weights, null imposed by centring.

- Is that reliable at this cluster count for a **paired loss-differential mean**? What do
  MacKinnon & Webb recommend at G ≈ 20–25, and is the Rademacher distribution's limited support
  a problem here?
- Measured season-level ICC on the loss differential is 0.00023 (design effect 1.16) — very
  small. Does the near-absence of intra-cluster correlation make the cluster count less
  concerning, or is clustering still the right default?
- Would a different clustering level (season-week, ~500 clusters) be defensible, given that the
  economic argument for season-level clustering is about model rosters and rule changes rather
  than about measured residual correlation?

## Known limitations I am *not* asking you to solve

State if any of these invalidate an answer above, but I already regard them as settled:

- No confirmation window exists, by the power calculation given.
- Common support differs between analysis rounds; figures are never compared across them.
- The benchmark is the panel publisher's own recorded line, and its capture time is undocumented
  upstream.
- 0.8% of cells in the regression design are zero-filled for absent models; 0.1% of rows are more
  than half filled. Zero rows in either support lack a screened model entirely.
- Five specification defects were found and fixed during the analysis (sign error, a nesting
  failure, a support collapse, the eligibility filter, and an uncentred stability statistic). All
  numbers quoted above are post-fix. I mention this only so that a recommendation to "re-check
  the implementation" is understood to have been done.
- Survivorship: models that stopped publishing may have been dropped for being bad. The
  population is selected and this is not fixable in-sample.

## Output format

For each question: the named method or result, primary citation (author, year, venue), what it
would change about my analysis, and a one-line verdict on whether it is worth implementing given
the diagnostics above. Finish with a ranked shortlist of at most five things worth doing next,
most valuable first, and — for each — the single diagnostic that would tell me early it is not
going to work.

Prefer peer-reviewed econometrics, forecasting and sports-economics sources (*International
Journal of Forecasting*, *Journal of Econometrics*, *Journal of Applied Econometrics*, *Journal
of Business & Economic Statistics*, *Journal of Sports Economics*, *Quantitative Economics*) and
well-known working papers. Say plainly where the literature is thin, contested, or absent — a
confident answer where none exists is worse to me than "this has not been studied".
