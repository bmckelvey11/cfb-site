# Combination sweep — results

Run 2026-08-29 by `scripts/eval_combination_sweep.py`, implementing
`docs/prediction-tracker-model-eval-plan-addendum.md`, which was committed at `2fbc480`
before any of this was fit. Parent results: `docs/prediction-tracker-model-eval.md`.

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
| **E4** (parent primary) | 14347 | 15.6582 | 15.7222 | **−1.976** | [−3.314, −0.648] | 0.0030 | — | 0.96 | 0.85 | pass |
| **E6** market-residual ridge | 14347 | 15.6452 | 15.7222 | **−2.383** | [−3.834, −0.863] | 0.0020 | — | 1.33 | 0.85 | pass |
| E7 K by rule | 14347 | 15.6903 | 15.7222 | −0.971 | [−2.220, +0.283] | 0.1350 | 0.675 | 0.79 | 0.70 | pass |
| E8 SW shrinkage | 14347 | 15.7212 | 15.7222 | +0.000 | — | — | — | 0.00 | 0.00 | none |
| E9 residual PCs | 14347 | 15.7032 | 15.7222 | −0.566 | [−1.630, +0.499] | 0.2800 | 0.840 | 0.70 | 0.65 | pass |
| E10 peLASSO | 14347 | 15.6944 | 15.7222 | −0.842 | [−2.017, +0.381] | 0.1735 | 0.694 | 0.82 | 0.70 | pass |
| E11 trimmed consensus | 14347 | 15.6846 | 15.7222 | −1.150 | [−2.353, +0.066] | 0.0610 | 0.366 | 0.76 | 0.70 | pass |
| E12 elastic net | 14347 | 15.7212 | 15.7222 | −0.000 | — | 0.4550 | 0.840 | 0.00 | 0.05 | none |
| E13 online (Hedge) | 14347 | 15.7153 | 15.7222 | −0.185 | [−0.547, +0.161] | 0.3480 | 0.840 | 0.28 | 0.55 | fail |
| **E14** screened CSR | 10755 | 15.6754 | **15.7187** | **−1.344** | [−2.320, −0.384] | 0.0035 | **0.0245** | 0.66 | 0.87 | pass |

Clark-West against R0 rejects for every single-direction corrector: E4 +3.721 (p<0.0001),
E11 +2.250 (p<0.0001), E7 +2.132 (p=0.0003), E10 +2.040 (p=0.0020), E13 +0.362 (p=0.0208).

**E14 is the only exploratory method to survive Holm** (adjusted p=0.0245). Caveats attach
and none of them are optional: it runs on its own reduced support (10,755 games, 15 of 20
seasons — screening to ten models is impossible in the early years), it is the winner of an
eight-member family, and §0 of the addendum ruled out any confirmation window. Its −1.344
is a **selection estimate** with no second look available to shrink it.

---

## 3. Against the closing line — nothing works

| | n | RMSE | mkt RMSE, same games | ΔvsR0 | 95% CI | p | Holm | \|corr\| | seas | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| market | 14353 | 15.5516 | 15.5516 | | | | | | | |
| R0 | 14353 | 15.5527 | 15.5516 | — | reference | | | | | |
| E4 | 14353 | 15.5486 | 15.5516 | −0.128 | [−0.312, +0.052] | 0.1495 | — | 0.29 | 0.65 | pass |
| E6 | 14353 | 15.5478 | 15.5516 | −0.152 | [−0.638, +0.304] | 0.5115 | — | 0.68 | 0.60 | pass |
| E7 | 14353 | 15.5529 | 15.5516 | +0.004 | [−0.139, +0.138] | 0.9605 | 1.000 | 0.18 | 0.55 | fail |
| E8 | 14353 | 15.5527 | 15.5516 | +0.000 | — | — | — | 0.00 | 0.00 | none |
| E9 | 14353 | 15.5536 | 15.5516 | +0.027 | [−0.041, +0.090] | 0.3980 | 1.000 | 0.08 | 0.50 | fail |
| E10 | 14353 | 15.5533 | 15.5516 | +0.019 | [−0.164, +0.189] | 0.8245 | 1.000 | 0.18 | 0.50 | fail |
| E11 | 14353 | 15.5522 | 15.5516 | −0.018 | [−0.144, +0.113] | 0.7635 | 1.000 | 0.16 | 0.55 | fail |
| E12 | 14353 | 15.5527 | 15.5516 | +0.000 | — | 0.6350 | 1.000 | 0.00 | 0.20 | none |
| E13 | 14353 | 15.5537 | 15.5516 | +0.030 | [−0.012, +0.072] | 0.1875 | 1.000 | 0.04 | 0.35 | fail |
| E14 | 9234 | 15.4181 | **15.4187** | −0.023 | [−0.120, +0.074] | 0.6225 | 1.000 | 0.21 | 0.62 | pass |

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
the edge of the parameter space itself, not of a grid I chose. **E8 chose ψ=0 — Stock–Watson
shrinkage, handed a free scalar and asked how much of the panel correction to keep, kept
none of it.** E12's elastic net independently zeroed every coefficient. Both collapse onto
R0 exactly (|corr| = 0.000), which is why they are marked `none` rather than given a verdict.

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
| opening | 12798 | 15.6033 | 15.5979 | −0.168 [−0.425, +0.107] | 0.2185 |
| closing | 12803 | 15.5051 | 15.4978 | −0.225 [−0.545, +0.102] | 0.1450 |

The repair helps in the predicted direction on both benchmarks and is significant on
neither. Expectation 2 was that correct centring would recover most of what ridge lost
without manufacturing signal — that is what happened, and the recovery is not large enough
to claim.

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

`scripts/diag_market_proxy.py`. §1's claim is that the panel carries information the opening
line has not priced. The alternative is a tautology: a column that is really "the line plus my
adjustment," published mid-week, beats the opening number mechanically.

**It found something worse than proxying — two columns that are not forecasts at all.**
`lineca` reproduces the closing line *exactly* on 65.6% of its games; `linemidweek` on 43.3%.
Full write-up in `docs/prediction-tracker-model-eval.md` §10, which retracts the parent
analysis's single-model claims.

Dropping the top decile by `corr(f_i − open, close − open)` — 15 columns, including both:

| | all 154 | minus 15 | retained |
|---|---|---|---|
| E4 vs R0 | −1.976 [−3.314, −0.648] p=0.0030 | −1.446 [−2.804, −0.043] p=0.0415 | 73% |
| E6 vs R0 | −2.383 [−3.834, −0.863] p=0.0020 | −1.713 [−3.254, −0.188] p=0.0355 | 72% |
| E11 vs R0 | −1.150 [−2.358, +0.077] p=0.0665 | −0.867 [−1.974, +0.253] p=0.1420 | 75% |
| Harvey–Newbold Wald | 70.10, p<0.0001 | 29.09, p=0.0115 | still rejects |

**§1 survives at about three quarters of its size.** Roughly a quarter of the opening-line
effect was market content leaking in; the rest is genuine model information. §3's closing-line
null needs no adjustment at all — proxying can only push a test *toward* rejecting, and that
test did not reject.

Two further checks, both clean:

- **Zero-fill exposure.** The residual design zero-fills absent models before projecting, so a
  game with *no* screened model would get a spurious correction proportional to the market
  number. Count: **0 of 14,347 rows (opening), 0 of 14,353 (closing).**
- **Harvey–Newbold without the full-sample components.** The test mixes a walk-forward target
  with full-sample PCs. Dropping the PCs: opening Wald 41.92 (p<0.0001), closing 2.48
  (p=0.3475). Same verdict on both benchmarks — the result is consensus-driven and the PCA
  never mattered.
