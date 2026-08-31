# Combination sweep — results

Run 2026-08-29 by `research/spread/scripts/eval_combination_sweep.py`, implementing
`prediction-tracker-model-eval-plan-addendum.md`, which was committed at `2fbc480`
before any of this was fit. Parent results: `prediction-tracker-model-eval.md`.

Nine estimators (E6–E14) drawn from the forecast-combination literature and run against
the measured diagnostics rather than in the abstract. Walk-forward 2006–2025, every
hyperparameter chosen on an inner split of the last three training seasons, inference by
season-level wild cluster bootstrap.

**Numbers here are not comparable to the parent run.** The parent scored on n=12,803; this
sweep's shared support is n=14,347 (opening) / n=14,353 (closing), because the residual
methods average available deviations instead of requiring complete rows. Every table below
is internally consistent and nothing in it should be set beside a parent-run figure.

---

## 1. The headline

**The panel beats the opening line. It does not beat the closing line.** Every other result
is a detail of that one.

| | opening line | closing line |
|---|---|---|
| Harvey–Newbold joint encompassing, Wald | **70.10** | 5.44 |
| bootstrap p | **0.0005** | 0.5595 |
| verdict | line does **not** encompass the panel | line encompasses the panel |

Against the opening number the 154 models carry information the market has not yet priced,
jointly and unambiguously. Against the closing number the same five pre-specified
directions are collectively indistinguishable from noise.

This is the same edge located in the parent analysis, seen from a different angle: whatever
the models know, the market learns it between open and close.

---

## 2. Against the opening line — several methods work

ΔMSE vs R0 (the recalibrated line), negative = better. `seas` = fraction of the 20 seasons
beating R0; `|corr|` = mean distance from R0.

**Read `RMSE` only against `mkt RMSE` on the same row.** E14 runs on its own reduced support,
so its raw RMSE is a different games' RMSE — setting it beside the shared market figure would
reproduce exactly the coverage-difficulty confound the parent plan names as threat #1.
(`sign_stability` is omitted: it is inert as specified — see §6.)

| | n | RMSE | mkt RMSE, same games | ΔvsR0 | 95% CI | p | Holm | \|corr\| | seas | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| market | 14347 | 15.7222 | 15.7222 | | | | | | | |
| R0 | 14347 | 15.7212 | 15.7222 | — | reference | | | | | |
| **E4** (parent primary) | 14347 | 15.6582 | 15.7222 | −1.976 | [−3.314, −0.648] | 0.0030 | — | 0.96 | 0.85 | pass |
| **E6** market-residual ridge | 14347 | 15.6088 | 15.7222 | **−3.521** | [−5.448, −1.597] | **<0.0001** | — | 1.89 | 0.90 | pass |
| E7 K by rule | 14347 | 15.6903 | 15.7222 | −0.971 | [−2.220, +0.283] | 0.1350 | 0.555 | 0.79 | 0.70 | pass |
| E8 SW shrinkage | 14347 | 15.7159 | 15.7222 | −0.165 | [−0.349, +0.018] | 0.0900 | 0.540 | 0.03 | 0.15 | fail |
| E9 residual PCs | 14347 | 15.7038 | 15.7222 | −0.548 | [−1.824, +0.743] | 0.3980 | 1.000 | 0.86 | 0.55 | fail |
| E10 peLASSO | 14347 | 15.6840 | 15.7222 | −1.168 | [−2.523, +0.242] | 0.1110 | 0.555 | 0.89 | 0.70 | pass |
| E11 trimmed consensus | 14347 | 15.6846 | 15.7222 | −1.150 | [−2.353, +0.066] | 0.0610 | 0.427 | 0.76 | 0.70 | pass |
| E12 elastic net | 14347 | 15.7128 | 15.7222 | −0.263 | [−0.649, +0.136] | 0.5120 | 1.000 | 0.17 | 0.15 | fail |
| E13 online (Hedge) | 14347 | 15.7153 | 15.7222 | −0.185 | [−0.547, +0.161] | 0.3480 | 1.000 | 0.28 | 0.55 | fail |
| **E14** screened CSR | 14347 | 15.6378 | 15.7222 | **−2.615** | [−3.596, −1.583] | **<0.0001** | **<0.0001** | 0.61 | **1.00** | pass |

Clark-West against R0 rejects for every single-direction corrector: E4 +3.721 (p<0.0001),
E11 +2.250 (p<0.0001), E10 +2.646 (p=0.0008), E7 +2.132 (p=0.0003), E13 +0.362 (p=0.0203).

**E14 is the only exploratory method to survive Holm** (adjusted p < 0.0001), and it beats R0
in **every one of the 20 seasons**. Two caveats that stood in the first run are now gone: it
covers the full common support (§10 fixed the filter that starved it of models before 2011),
and §9 shows its effect is not market proxying — dropping the 15 most market-like columns
retains 49% and it stays at p < 0.0001.

The caveats that remain are not optional. It is the winner of an eight-member family, and §0
of the addendum ruled out any confirmation window. **−2.615 is a selection estimate with no
second look available to shrink it**, and the honest reading is that CSR is a candidate for
pre-registration, not a result.

---

## 3. Against the closing line — nothing works

| | n | RMSE | mkt RMSE, same games | ΔvsR0 | 95% CI | p | Holm | \|corr\| | seas | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| market | 14353 | 15.5516 | 15.5516 | | | | | | | |
| R0 | 14353 | 15.5527 | 15.5516 | — | reference | | | | | |
| E4 | 14353 | 15.5486 | 15.5516 | −0.128 | [−0.313, +0.050] | 0.1530 | — | 0.29 | 0.65 | pass |
| **E6** | 14353 | 15.5882 | 15.5516 | **+1.106** | [+0.033, +2.232] | **0.0480** | — | 1.31 | 0.45 | fail |
| E7 | 14353 | 15.5529 | 15.5516 | +0.004 | [−0.136, +0.137] | 0.9515 | 1.000 | 0.18 | 0.55 | fail |
| E8 | 14353 | 15.5527 | 15.5516 | +0.000 | — | — | — | 0.00 | 0.00 | none |
| E9 | 14353 | 15.5540 | 15.5516 | +0.041 | [−0.058, +0.135] | 0.3715 | 1.000 | 0.12 | 0.45 | fail |
| E10 | 14353 | 15.5547 | 15.5516 | +0.060 | [−0.149, +0.262] | 0.5500 | 1.000 | 0.22 | 0.45 | fail |
| E11 | 14353 | 15.5522 | 15.5516 | −0.018 | [−0.144, +0.109] | 0.7685 | 1.000 | 0.16 | 0.55 | fail |
| E12 | 14353 | 15.5527 | 15.5516 | +0.000 | — | 0.6300 | 1.000 | 0.00 | 0.20 | none |
| E13 | 14353 | 15.5537 | 15.5516 | +0.030 | [−0.012, +0.073] | 0.1890 | 1.000 | 0.04 | 0.35 | fail |
| E14 | 14353 | 15.5476 | 15.5516 | −0.159 | [−0.327, +0.014] | 0.0695 | **0.4865** | 0.21 | 0.65 | pass |

E14's row is the clearest illustration of why the paired column exists. Its raw RMSE of
15.4181 looks a full 0.13 better than the market's 15.5516 -- but on **E14's own games**
the market is 15.4187. It drew easier games. The honest gap is -0.023, which is nothing.

Every Holm-adjusted p is 1.000. Clark-West still rejects for E4 (+0.271, p=0.0020) — the
signal is there in population — and for nobody else. Nine additional estimators, several of
them explicitly designed for the "signal exists but estimation variance destroys it"
regime, recover none of it.

---

## 4. The selection rule ran to the wall — every method, every season

The single most informative output of the sweep is not in the tables above. It is that the
1-SE rule chose **the most conservative value on its grid in 20 of 20 seasons, for every
method, on both benchmarks.**

| method | selected | nature of the endpoint |
|---|---|---|
| E6 ridge λ | 10 000 | grid edge |
| E7 K | all | **parameter-space edge** — least screening possible |
| E8 ψ | 0 | **parameter-space edge** — apply no correction at all |
| E9 components | 1 | **parameter-space edge** |
| E10 LASSO λ | 1.0 | grid edge |
| E11 trim τ | 0.4 | grid edge |
| E12 elastic net | (1000, 0.9) | grid edge |
| E13 η | 0.001 | grid edge |
| E14 subset k | 1 | **parameter-space edge** |

The addendum's §3 committed in advance to reporting endpoint clipping rather than widening
the grid, so the registered run stops here. But the distinction matters: four of these are
the edge of the parameter space itself, not of a grid I chose. **E8 chose ψ = 0 — Stock–Watson
shrinkage, handed a free scalar and asked how much of the panel correction to keep, kept
none of it in 85% of seasons.** E12's elastic net independently zeroed every coefficient just
as often.

Against the **closing** line both collapse onto R0 exactly (|corr| = 0.000), which is why they
are marked `none` there rather than given a verdict. Against the **opening** line, where signal
exists, they occasionally keep a sliver — E8's mean correction is 0.03 points, E12's 0.17 —
which is the entire difference between the two benchmarks expressed as a hyperparameter.

### The widened-grid appendix — exploratory, outside every gate

`--wide` extends the five clipped grids. This is post-hoc, outside the registered search
space, and excluded from all gates; it answers one question only — would the rule have gone
further?

It would. E6's λ runs to **10⁷**, E13's η to **10⁻⁵**, E12's α to **10⁵**, E11's τ to 0.45.
Given a free hand, E6's mean distance from R0 falls to **0.019 points** on the closing line.
The rule does not want a smaller correction than the grid allowed; it wants no correction.

**One honest complication.** On the *opening* line — where signal genuinely exists — the
widened E6 scored −0.210 against R0, far worse than the clipped E6's −2.383. The extra
shrinkage the rule chose destroyed a real gain, because inner-validation could not
distinguish λ=10⁴ from λ=10⁷ within one standard error. The 1-SE rule is well-calibrated
for the closing line and too conservative for the opening one. It is a rule for the regime
the parent analysis measured, and it behaves as such.

---

## 5. The repair — E6 vs E5

E5 penalized raw forecasts and treated the market as one more shrunk-toward-zero column.
E6 residualizes against the line and shrinks the correction toward zero instead. Paired on
E5's own complete-row support:

| benchmark | n | E5 RMSE | E6 RMSE | ΔMSE(E6−E5) | p |
|---|---|---|---|---|---|
| opening | 12798 | 15.6033 | 15.5573 | **−1.431** [−3.021, +0.100] | 0.0730 |
| closing | 12803 | 15.5051 | 15.5371 | **+0.993** [+0.102, +1.966] | 0.0385 |

E5 is held on the *legacy* coverage filter here deliberately (§10): the comparison is about
E6's centring, not about its larger regressor set, and handing E5 the corrected filter would
give it 37 columns under a complete-row requirement and measure the repair against a strawman.

**The repair helps against the opening line and significantly hurts against the closing one.**
That is not a contradiction — it is the sweep's central finding in one row. Where signal
exists, correct centring plus more regressors extracts it; where it does not, the same extra
regressors are pure estimation variance and cost about 1.0 MSE. Expectation 2 said E6 would
beat E5 on both benchmarks; that is **wrong on the closing line**.

---

## 6. Scorecard against the pre-committed expectations

The addendum recorded four expectations before the run so that a confirmed one could not be
reported as a discovery and a violated one could not be quietly dropped.

**1. "E7 will most likely score worse than E4" — correct, wrong reason.** E7 did score worse
(−0.971 vs −1.976 opening; +0.004 vs −0.128 closing). But the reasoning was that a 1-SE
rule would select a K different from 20 and thereby expose K=20 as selection-inflated. What
actually happened is sharper: the rule selected **K = all, in 20 of 20 seasons, on both
benchmarks** — meaning inner-validation could not separate K=5 from K=all at one standard
error. K is **not identifiable out-of-sample here.** That does not vindicate K=20; it means
K=20 was never validated by anything, which is the original concern arrived at by a
different route. It also exposes a flaw in my own pre-registration: I declared *larger* K
the conservative direction (fewer selection parameters), and larger K drags in the bad tail
the parent analysis had already identified. The direction was defensible when written and
looks wrong now, and it is recorded rather than revised.

**2. "E6 will beat E5 and still not beat R0" — confirmed on the closing line, wrong on the
opening line.** E6 beats E5 both times (§5). It does not beat R0 on closing (−0.152,
p=0.51). It emphatically does beat R0 on opening (−2.383, p=0.0020).

**3. "E13 and E14 will not help" — half wrong, and this is the sweep's real surprise.** E13
(online aggregation) failed as predicted, exactly as the 0.775 skill-rank persistence
implied. **E14 (screened CSR) was the only exploratory method to survive Holm on either
benchmark.** I expected complete subset regression to be a waste and it was the strongest
exploratory result on the opening line. The caveats in §2 stand and are load-bearing.

**4. "No method will pass the stability gate" — wrong, and the gate is weaker than
designed.** Seven methods clear it on the opening line (E4, E6, E7, E9, E10, E11, E14).

But the gate is not doing what the addendum's §5 said it would. It has two components and
**one of them is inert.** `sign_stability` is computed as `max(pos, n−pos) / n`, which is
bounded below at 0.50 and returns 1.00 for a coefficient that is consistently +0.001 just
as readily as for one that is consistently +0.8. It measures whether a sign flips, not
whether a correction is meaningfully sized, so with a coefficient that never changes sign
it is constant at 1.00 across every method in both tables — which is exactly what the
`sign` column shows. The gate is therefore effectively `frac_seasons ≥ 0.60` plus the
degeneracy check, and the degeneracy check is what actually caught E8 and E12.

This is a flaw in the metric as I specified it, not a property of the data. A useful
version would compare the coefficient's mean to its across-window standard deviation.
Recorded rather than retrofitted.

---

## 7. Decision value — still no bet

Every method's disagreements with the **closing** line, graded at −110 (break-even 0.5238):

| method | anchored on | threshold | bets | hit | ROI |
|---|---|---|---|---|---|
| E6 | opening | \|edge\|>3 | 1877 | 0.5147 | −0.0175 |
| E6 | closing | \|edge\|>3 | 108 | 0.5556 | **+0.0606** |
| E6 | closing | \|edge\|>1 | 4248 | 0.5214 | −0.0046 |
| E4 | opening | \|edge\|>2 | 4073 | 0.4996 | −0.0462 |
| E14 | opening | \|edge\|>3 | 1248 | 0.4832 | −0.0776 |

The one positive cell is 108 bets. At that sample a 0.5556 hit rate is roughly one standard
error above break-even and should be read as noise, not as an edge. Nothing else clears
−110, including the methods that beat the opening line most convincingly.

The pattern is coherent: a method can beat the opening number by two full MSE points and
still not beat the closing number by enough to pay vig, because the closing number has
already absorbed what the models knew.

---

## 8. What this changes, and what it does not

**Changes.** Three things are now measured rather than assumed:

1. The panel's information is real and jointly significant against the opening line
   (Harvey–Newbold Wald 70.1, p=0.0005), and jointly insignificant against the closing line
   (Wald 5.44, p=0.56). Pairwise Clark-West could not have established either.
2. Nine estimators spanning shrinkage, screening, factors, robust averaging, subset
   averaging and online aggregation do not recover a closing-line edge. The parent
   conclusion was one estimator's result; it is now a family's.
3. Every selection rule, given the choice, shrinks the correction toward zero — and keeps
   shrinking when the grid is widened. That is a stronger statement than any single p-value
   in the tables.

**Does not change.** E4 remains the only pre-registered primary claim. Nothing here is
confirmatory: the addendum established up front that no usable confirmation window exists
(2021–25 MDE is 0.161 RMSE, roughly double the resolvable effect), so E14's Holm-significant
opening-line result is a candidate for future pre-registration and not a finding to deploy.
And none of it touches the open question — whether the parent analysis's opening-line edge
survives at a price you could actually take. That still waits on
`docs/line-timing-collector.md`.

---
## 9. Robustness: is the opening-line result skill, or proxying?

`research/spread/scripts/diag_market_proxy.py`. §1's claim is that the panel carries information the opening
line has not priced. The alternative is a tautology: a column that is really "the line plus my
adjustment," published mid-week, beats the opening number mechanically.

**It found something worse than proxying — two columns that are not forecasts at all.**
`lineca` reproduces the closing line *exactly* on 65.6% of its games; `linemidweek` on 43.3%.
Full write-up in `prediction-tracker-model-eval.md` §10, which retracts the parent
analysis's single-model claims.

Dropping the top decile by `corr(f_i − open, close − open)` — 15 columns, including both:

Opening line, ΔMSE vs R0:

| | all 154 | minus 15 | retained |
|---|---|---|---|
| E4 vs R0 (consensus) | −1.976 [−3.314, −0.648] p=0.0030 | −1.446 [−2.804, −0.043] p=0.0415 | **73%** |
| E11 vs R0 (consensus) | −1.150 [−2.358, +0.077] p=0.0665 | −0.867 [−1.974, +0.253] p=0.1420 | **75%** |
| **E14 vs R0** (subset regression) | −2.615 [−3.666, −1.558] p<0.0001 | −1.285 [−1.948, −0.641] **p<0.0001** | **49%** |
| **E6 vs R0** (ridge) | −3.521 [−5.448, −1.597] p<0.0001 | **−0.966** [−2.561, +0.640] **p=0.2560** | **27%** |
| Harvey–Newbold Wald | 70.10, p<0.0001 | 29.09, p=0.0115 | still rejects |

**The families separate sharply, and this is the most important row in the document.**

- The **consensus family** (E4, E11) retains ~three quarters and E4 stays significant. Its
  opening-line effect is genuine model information.
- **E14** retains half and stays at p < 0.0001. Also genuine.
- **E6 retains 27% and stops being significant.** Its headline −3.521 is substantially market
  proxying. A ridge with 37 regressors can load on the partially market-anchored columns
  (movement correlations 0.49–0.76) that the consensus family dilutes to a twentieth each.
  **E6's opening-line figure should not be quoted as model skill.**

§3's closing-line null needs no adjustment in direction — proxying can only push a test
*toward* rejecting, and that test did not reject.

**One lead, and it is only a lead.** On the closing line E14 *strengthens* under
decontamination: −0.159 (p=0.0695) becomes **−0.193 [−0.344, −0.045], p=0.0125**. That is a
post-hoc variant of the winner of an eight-member family, with no confirmation window; Holm
across that family would put it near 0.10. Per addendum §0 it is a candidate for future
pre-registration, **not** a closing-line edge.

Two further checks, both clean:

- **Zero-fill exposure.** The residual design zero-fills absent models before projecting, so a
  game with *no* screened model would get a spurious correction proportional to the market
  number. Count: **0 of 14,347 rows (opening), 0 of 14,353 (closing).**
- **Harvey–Newbold without the full-sample components.** The test mixes a walk-forward target
  with full-sample PCs. Dropping the PCs: opening Wald 41.92 (p<0.0001), closing 2.48
  (p=0.3475). Same verdict on both benchmarks — the result is consensus-driven and the PCA
  never mattered.

---
## 10. Correction: the coverage filter was a tenure test

Found 2026-08-29 while writing the consolidated findings, and fixed. Every number in §2, §3,
§5 and §9 above is post-fix; the first published version of this document was not.

`regressor_cols` required a model to cover **80% of all prior training games**. Because
missingness in this panel is season-level, that is not a completeness test — it is a test of
*when a model launched*. A forecaster that began in 2015 covers well under 80% of games since
2001 no matter how perfect its record, so it could never become a regressor.

At the 2025 season the filter kept **14 of 39** active models, median entry year 2002, and
excluded `lineespn` and `lineteamrank` — the two best forecasters in the panel (§6 of
`prediction-tracker-recency-screen.md`). Measuring coverage over the seasons a model actually
published in keeps **37 of 39**.

Fixing it is a bug repair, not a re-specification: the parent plan specifies "the model set
**active in that season**", and the code did not implement that.

### What it affected

The **regression family only** — E6, E9, E10, E12, E14. The consensus family (E4, E7, E11,
E13) reads the active set directly and never touched the filter, so **every consensus result,
the entire recency analysis, and the §11.1 decontamination figure are unchanged.**

| | before fix | after fix |
|---|---|---|
| E6, opening | −2.383 | −3.521 |
| E6, closing | −0.152 | **+1.106** (significantly *worse* than R0) |
| E14, opening | −1.344, Holm 0.0245, **15 of 20 seasons** | −2.615, Holm <0.0001, **20 of 20** |
| E14, closing | −0.023 | −0.159 |
| E8 / E12, opening | 0.000 (degenerate) | −0.165 / −0.263 |

Two consequences worth stating plainly:

1. **E14's largest caveat is gone.** The filter was what starved complete subset regression of
   models before 2011; it now runs on the full common support. §9 then shows its effect is not
   market proxying. It is a much stronger result than first published.
2. **E6 inverts on the closing line.** Given 37 regressors instead of 14 it goes from −0.152 to
   +1.106 (p = 0.048) — significantly *worse* than the recalibrated line. That is the sweep's
   thesis stated as a sign flip rather than an argument: the same estimator on the same
   regressors gains 3.5 MSE where signal exists and loses 1.1 where it does not. §9 then shows
   most of the opening-line gain was market content anyway.

`rebuild_e5` is deliberately pinned to the **legacy** filter, because the E6-vs-E5 repair
comparison in §5 is about centring, not regressor count.
