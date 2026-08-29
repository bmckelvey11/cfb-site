# Analysis plan, addendum — market-anchored combination sweep

Written 2026-08-29, **after** the results in `docs/prediction-tracker-model-eval.md` and
**before** fitting anything below. Extends
`docs/prediction-tracker-model-eval-plan.md`; every rule in the parent plan that this file
does not override still binds.

Motivated by a literature review of forecast-combination methods
(`docs/research-prompt-forecast-combination.md` and its answer), which was run against the
measured diagnostics rather than in the abstract.

## 0. Why this addendum exists, and what it cannot do

The parent plan pre-registered **E4** and got a clean answer: against the recalibrated
line, Clark-West rejects (+0.451, one-sided p=0.0005) while the paired difference does not
(−0.248 [−0.517, +0.002], p=0.063). Signal is present in the population and is destroyed
by the cost of estimating how much to weight it.

That is a statement about **one** estimator. It does not establish that no estimator
recovers the signal. This addendum runs the estimators the literature nominates for exactly
that regime.

**What this sweep cannot do, stated before it runs:** it cannot produce a new confirmed
primary claim. Parent plan §6 settled that there is no usable confirmation window — a
2021–25 holdout has MDE 0.161 RMSE, roughly double the effect the selection window can
resolve. Adding nine candidate estimators after seeing E4's result therefore buys
**exploratory breadth, not confirmatory strength.** The deliverable is a map of which
method families do and do not help, not a champion to deploy.

Consequences, binding:

- **E4 remains the sole pre-registered primary.** Nothing below can replace it as the
  headline claim, no matter how it scores.
- **The best performer among E6–E14 is a selection estimate** and will be labelled as such
  wherever it is quoted. Holm control (§4) governs the *tests*; it does not de-bias the
  winner's reported ΔMSE. There is no second window in which to shrink it.
- A method that wins here is a **candidate for future pre-registration**, not a result.

## 1. One repair, distinguished from the exploratory family

**E6 is a repair, not a candidate.** E5 as implemented fits

```python
Ridge(alpha=RIDGE_ALPHA).fit(-tr_sub[cols + [bench_col]], y)
```

which penalizes the raw forecasts and treats the market as one more shrunk-toward-zero
column. That centres the prior at "no forecast is informative, including the line," which
is not the substantive prior. The correct centring is "the market is right and the panel
supplies a small correction": residualize everything against the line and shrink the
correction toward **zero**, leaving the line unpenalized.

This is a specification defect identified from the estimator, **before** fitting E6. E6 vs
E5 is therefore interpretable without selection correction, and is reported separately from
the exploratory family.

**E7–E14 are exploratory**, subject to §4 and §0.

## 2. Specifications

Notation, per game: `mkt` = benchmark predicted margin, `fᵢ` = model *i*'s predicted
margin, `dᵢ = fᵢ − mkt` the deviation, `y` the actual margin. All fits are on `y − mkt` and
all predictions are `mkt + correction`. Intercept always unpenalized. As in the parent
plan, weights for season *t* use only seasons < *t*.

| ID | Specification | Family |
|---|---|---|
| **E6** | **Market-residual ridge.** `y − mkt ~ β₀ + Σᵢ wᵢ dᵢ` over the season's active set, ridge penalty on `w` only. Repair of E5. | repair |
| E7 | **E4 with K chosen by rule** instead of fixed at 20. Same two-slope form. | exploratory |
| E8 | **Stock–Watson generalized shrinkage.** Fit the unrestricted residual combination, then shrink the resulting *correction* toward zero by a scalar ψ chosen out-of-sample: `mkt + ψ·ĉ`. | exploratory |
| E9 | **Market-residual principal components.** PCs of the `dᵢ` on the active set; regress `y − mkt` on the first *r* scores. | exploratory |
| E10 | **Market-anchored peLASSO.** LASSO on the `dᵢ` to select a subset, then equal-weight the survivors' deviations and fit one scalar γ: `mkt + γ·mean(d over survivors)`. | exploratory |
| E11 | **Trimmed residual consensus.** Per game, drop the top and bottom τ of available `dᵢ`, average the rest, fit one scalar γ. | exploratory |
| E12 | **Combination elastic net.** E6 with an ℓ1+ℓ2 penalty. | exploratory |
| E13 | **Online residual aggregation.** Exponentially-weighted (Hedge-style) weights over active models' deviations, updated per settled game, combined with one scalar γ. | exploratory |
| E14 | **Complete subset regression after screening.** Screen to the 10 best by prior-season residual skill; average all `C(10,k)` k-variable residual regressions. | exploratory |

**E14 is a bounded check, and the bound is stated now.** Literal CSR at K≈60 is
infeasible — `C(60,5) = 5,461,512` and `C(60,10) ≈ 7.5×10¹⁰`. Screening to 10 first makes
`C(10,3) = 120` regressions, which is tractable. Any claim about "CSR" from this run is a
claim about screened CSR at small *k*, not about CSR on the full panel.

**E13 is expected to fail, and is run anyway.** Season-to-season skill rank Spearman is
0.775 and entry/exit is season-level, so there is little time-variation for an online
learner to exploit, and its regret guarantee is relative to the best expert in the pool —
none of which beat the market. Running it converts a citation-based expectation into a
measured one.

### Deliberately still excluded

Parent plan §2's exclusion of **row-level imputation of a missing model from its
co-forecasters** remains in force and is not relaxed by the appearance of factor methods
here. E9 extracts components from the **per-season active set** with no filling; EM-imputed
individual forecasts as regressors stay excluded. The reason is unchanged: an imputed
column is a function of its co-regressors, which launders the consensus into every
coefficient.

## 3. Hyperparameter selection — the rule, and the grids

**All selection nests inside the walk-forward.** For evaluated season *t*: inner-train =
seasons `< t−3`, inner-validation = seasons `t−3 … t−1`. The hyperparameter is chosen on
inner-validation MSE, then the model is **refit on all seasons `< t`** at that value and
used to predict *t*. No hyperparameter is ever chosen using any season ≥ *t*.

Selection rule: **the most conservative value within one standard error of the best**
inner-validation MSE, where "conservative" means more shrinkage / fewer free parameters.
Direction is fixed per parameter below so it cannot be chosen after the fact.

| Method | Parameter | Grid | Conservative direction |
|---|---|---|---|
| E6 | ridge λ | {0.1, 1, 10, 100, 1000, 10000} | **larger** λ |
| E7 | K | {5, 10, 20, 40, 80, all active} | **larger** K |
| E8 | ψ | {0, 0.1, 0.2, …, 1.0} | **smaller** ψ |
| E9 | r (PCs) | {1, 2, 3} | **smaller** r |
| E10 | LASSO λ | {0.001, 0.01, 0.1, 1.0} | **larger** λ |
| E11 | τ (each tail) | {0, 0.1, 0.2, 0.3, 0.4} | **larger** τ |
| E12 | λ × ℓ1-ratio | {0.1, 1, 10, 100, 1000} × {0.1, 0.5, 0.9} | **larger** λ, then larger ℓ1 |
| E13 | η | {0.001, 0.01, 0.1} | **smaller** η |
| E14 | k | {1, 2, 3} | **smaller** k |

If a grid's chosen value lands on an endpoint in a majority of seasons, that is reported —
it means the grid was too narrow and the result is a grid artifact, not a fit.

## 4. Multiplicity

| Family | Count | Control |
|---|---|---|
| Primary (E4 vs benchmark) | 1 | Unchanged. Pre-registered in the parent plan. |
| Repair (E6 vs E5) | 1 | None needed — a specification defect named before fitting. |
| Exploratory sweep (E7–E14) | 8 | **Holm** within the family, per benchmark. |
| Parent-plan secondaries (E1, E2, E3, E5) | 4 | Unchanged (Holm). |

Reported per method: raw p, Holm-adjusted p, and the §5 stability columns. As stated in §0,
Holm controls the family's error rate and does **not** correct the winner's effect size.

## 5. Stability — a column, not a footnote

Pooled ΔMSE alone cannot distinguish a small stable gain from noise that happened to land
negative. Two columns are reported for every method, and they are decision-relevant:

1. **`frac_seasons_beat_r0`** — fraction of evaluated seasons whose season-level MSE is
   below R0's. A method that improves the pooled number while losing most seasons is
   carried by a few years and is not deployable.
2. **`sign_stability`** — fraction of training windows in which the method's primary
   correction coefficient (γ, ψ, or the sum of residual weights) matches its modal sign.

**Pre-committed stop diagnostic** (adopted from the literature review): a method whose
correction coefficient changes sign across training windows, or that beats R0 in **fewer
than 60% of evaluable seasons**, is declared not viable **regardless of its pooled ΔMSE or
p-value.** In this regime a detectable population signal is not sufficient; the correction
must be small, same-direction, and stable before it can plausibly survive estimation cost.

## 6. Common support and comparability

Every ensemble is scored on the **same games** — the intersection of non-missing
predictions across all reported ensembles, as in the parent run. Adding E6–E14 will change
that intersection, so:

- The market, R0, E4 and E1–E5 are **re-scored on the sweep's own common support**, and the
  sweep's table is internally valid.
- A number from this sweep is **never** printed alongside a number from the parent run.
  The published E4 ΔMSE of −0.19 belongs to n=12,803 and is not comparable to anything
  here.
- Residual-space methods average **available** deviations on the active set rather than
  requiring complete rows, precisely so the intersection is not driven down by one greedy
  method. Where a method genuinely needs complete rows (E14), that is stated.

## 7. Benchmarking every new method against R0, not the raw line

In residual space an unpenalized intercept absorbs the line's mean bias — which is exactly
what R0 (`β₀ + β₁·mkt`, no models) already measures, and which the parent run found worth
+0.06 MSE (p=0.66). Reporting E6–E14 against the raw line would re-bundle recalibration
into "the models add information."

**Every method in this addendum reports its primary comparison against R0.** The raw-line
comparison is reported as a secondary column only.

## 8. Additional diagnostic — joint encompassing

Pairwise Clark-West asks whether one extra term carries signal. It cannot ask whether the
benchmark encompasses the panel **as a set**. Add the Harvey–Newbold multiple
forecast-encompassing test (Harvey & Newbold 2000, *J. Applied Econometrics* 15(5)) on a
**low-dimensional, pre-specified** set of directions:

> screened top-20 consensus deviation, top-5 consensus deviation, residual PC1, residual
> PC2, residual PC3.

Five directions, named here, fitted inside the walk-forward. A literal 154- or
60-dimensional Wald test would have poor power and an unstable covariance under season
clustering, so it is not run. Inference by the same season-level wild cluster bootstrap.

## 9. Stop rule

One pass, one look, as in the parent plan. The grids in §3 are the complete search space;
nothing is widened after seeing results. Anything discovered post hoc is labelled
exploratory and excluded from every gate.

## 10. Pre-committed expectations

Recorded before running so that a confirmed expectation cannot later be reported as a
discovery, and a violated one cannot be quietly dropped.

1. **E7 will most likely score worse than E4.** K=20 was already found to be the single
   most favorable value tested (the effect vanishes at 5/10/40/80). A 1-SE rule will
   probably select a different K. If so, that is the sweep's most informative result: it
   means E4's −0.19 is **selection-inflated despite K being pre-registered**, because the
   parent plan fixed K's *value* without fixing a *rule* for choosing it. This is reported
   as a finding about the parent estimate, not as a disappointment about E7.
2. **E6 will beat E5 and still not beat R0.** Correct centring should recover most of the
   distance ridge lost to the two-parameter fit, without manufacturing absent signal.
3. **E13 and E14 will not help**, for the reasons given in §2.
4. **No method will pass §5's stability gate.** If one does, that is the finding worth
   pre-registering next.

---
# §11 — Recency-weighted skill and cohort-aware pooling

Added 2026-08-29, **before** fitting any of it. Extends this addendum; §0's limits on what an
exploratory sweep can establish apply here unchanged.

## 11.0 What this can and cannot do — stated first

Recency weighting enters the pipeline at exactly one point: `prior_skill`, which orders models
for the screen. The screen feeds a consensus. The consensus is multiplied by a fitted
coefficient.

**Against the closing line that coefficient is already zero.** Every method in the sweep has
Holm p = 1.000, and E8 and E12 chose *literally* no correction. Re-ordering the input to a
multiplication by zero cannot change the product. **No recency scheme in this section can
produce a closing-line edge, and none of it should be read as another attempt at one.**

What it can legitimately change:

1. The **opening-line** effect size, where signal is real.
2. **Which models get screened** — a substantive question about the panel.
3. Whether the implicit ρ = 1 in every published result was doing hidden work.

A run where ρ = 1 keeps winning closes this branch cleanly and confirms that the measured
0.775 skill-rank persistence was already the answer. That is a result, not a failed run.

## 11.1 Prerequisite, already run: the screen was contaminated but not hollow

`lineca` and `linemidweek` are market lines (parent §10) and top **any** skill ranking. Every
screened-consensus result published so far — the parent plan's K = 20 E4, and E3/E7/E10/E14 in
this sweep — used a top-20 that included them. Measured by
`scripts/diag_screen_decontam.py`, before writing the rest of this section:

- **`lineca` ranked #1 in the screen in 20 of 20 seasons.** `linemidweek` ranked #2 from 2023.
  Both were present in 12 of 20 seasons; at least one in all 20.
- Removing exactly those two and changing nothing else:

| | all 154 | 152 | retained |
|---|---|---|---|
| E4 vs R0, opening | −1.976 [−3.314, −0.648] p=0.0030 | −1.640 [−2.985, −0.265] p=0.0170 | **83%** |
| E7 vs R0, opening | −0.971 p=0.1350 | −0.880 p=0.1535 | 91% |
| E4 vs R0, closing | −0.128 p=0.1430 | −0.119 p=0.1750 | 93% |
| E4 Clark-West, opening | +3.721 p<0.0001 | +3.218 p<0.0001 | still rejects |

**The screen was contaminated; the screened consensus was not merely reproducing the line.** An
equal-weighted top-20 dilutes any one member to 1/20, which is why the top-ranked column being
the closing line costs only 17% of the effect. The published structure holds and the recency
grid is worth searching. **Both market lines are excluded from the panel for everything below.**

## 11.2 Estimator

For target season *s*, discounted market-relative skill:

    δ̂ᵢ,ₛ(ρ) = Σ_{u<s} ρ^(s−u) Σ_{t∈u} [(yₜ−fᵢₜ)² − (yₜ−mₜ)²]  /  Σ_{u<s} ρ^(s−u) nᵢ,ᵤ

then empirical-Bayes shrinkage toward market parity, and a conservative rank score:

    μ̃ᵢ,ₛ = ωᵢ,ₛ · δ̂ᵢ,ₛ,     ωᵢ,ₛ = nᵉᶠᶠᵢ,ₛ / (nᵉᶠᶠᵢ,ₛ + κ)
    Scoreᵢ,ₛ = μ̃ᵢ,ₛ + c · σ̂ᵢ,ₛ          (lower is better)

Two-window blend, long window at the selected ρ, recent window over the last three seasons:

    μ̃ᵇˡᵉⁿᵈ = (1−η)·μ̃ˡᵒⁿᵍ + η·μ̃ʳᵉᶜᵉⁿᵗ

Forecast form is unchanged and stays low-dimensional: `ŷₜ = mₜ + γ·c_{k,t}`, γ fit on the same
discounted training data.

## 11.3 Grids, and the conservative direction of each

Selected by the same nested forward validation as the sweep (inner split = last three training
seasons), same 1-SE rule.

| Parameter | Grid | Conservative direction |
|---|---|---|
| ρ retention | {0.80, 0.85, 0.90, 0.95, 0.975, 1.00} | **larger ρ** — 1.00 is "no recency", the null |
| κ credibility | {500, 1000, 2000, 4000} effective games | **larger κ** — more shrinkage to parity |
| η recent blend | {0, 0.25, 0.50, 0.75, 1.00} | **smaller η** — 0 is long-window only |
| c uncertainty penalty | {0, 0.5, 1.0} | **larger c** |
| q new-entrant sleeve | {0, 0.05, 0.10, 0.20} | **smaller q** — 0 is no sleeve |

**k is deliberately NOT tuned.** The sweep established that k is not identifiable
out-of-sample here: the 1-SE rule hit its endpoint in 20 of 20 seasons, meaning inner validation
could not separate k = 5 from k = all. Re-running a selection rule on an unidentifiable
parameter would manufacture false precision. **k ∈ {5, 8, 12, 16, 20, 30} is reported as a
sensitivity — every value, side by side — and no value is selected.** This is the direct
correction of the mistake recorded in §6 expectation 1, where a defensible-sounding conservative
direction for k turned out to be the wrong one.

**λ, the post-gap inactivity penalty, is implemented but not tuned.** Only 25 of 154 models have
any gap season. λ is unidentifiable at that count and a fitted value would be noise. Fixed at
λ = 0.25, with {0, 0.5} reported as sensitivity, and labelled unidentifiable wherever quoted.

**Eligibility is fixed, not tuned:** ≥ 2 prior active seasons and ≥ 500 effective prior games to
enter the top-k screen. Ineligible models stay in the candidate pool and can reach the
correction only through the q sleeve.

## 11.4 Cohort adjustment — a trend, not dummies

Entry cohorts are **87 / 29 / 29 / 5 / 4** for 2001–06, 07–12, 13–17, 18–21, 22–25. The last two
cannot support dummies, and merging them into a nine-model bucket would be a dummy wearing a
cohort's name. Per the source spec's own fallback, entry year enters as a **linear trend**:

    ℓᵢₜʳᵉˡ = aᵢ + b·entry_year(i) + c_season(t) + εᵢₜ

fit only on pre-target-season data, models ranked on the partially-pooled aᵢ. Used for
**screening only** — the forecast stays `mₜ + γ·c_{k,t}`.

## 11.5 Stability diagnostic

Giacomini–Rossi fluctuation test (Giacomini & Rossi 2010, *J. Applied Econometrics* 25(4)),
applied to the market-relative loss differential of **pre-specified aggregates against R0** —
not to 154 individual model series, where it would have no power:

> top-k screened residual consensus (k = 20), trimmed residual consensus, residual PC1, residual PC2.

Rolling window one third of the evaluation span; critical values by the same season-level wild
cluster bootstrap. **The test establishes whether relative performance is unstable over time. It
does not select ρ** — only forward validation does that.

## 11.6 Decisive diagnostic

> **Does the validation-selected ρ beat ρ = 1.00 in genuinely forward, season-by-season
> validation, consistently rather than in a few seasons?**

If ρ settles at or near 1.00, or the gain from decay is unstable and concentrated, the
conclusion is that college football changed in level but not in the **relative skill ordering**
of its forecasters — and the long-history ranking stands with only modest shrinkage for new and
restarted models. If ρ ≈ 0.85–0.95 wins repeatedly *and* Giacomini–Rossi rejects stability,
recency belongs in the screen.

## 11.7 Robustness specifications

Reported together, none of them production candidates: 5-season rolling rank; 10-season rolling
rank; post-2014 expanding; post-2021 expanding; long/recent blended rank; cohort-adjusted
partially-pooled rank. These test whether the conclusion depends on assumptions about the pace
of change.

## 11.8 Pre-committed expectations

1. **ρ = 1.00 will be selected in a majority of seasons.** Skill-rank persistence is 0.775,
   which is high; strong decay would be discarding informative history.
2. **No recency scheme will change the closing-line null**, for the arithmetic reason in §11.0.
3. **Giacomini–Rossi will reject stability on the opening line and not on the closing line**,
   mirroring the encompassing split.
4. **The cohort trend will be small and will not reorder the top of the screen**, because the
   two youngest cohorts hold nine models between them.

*(An expectation about the decontamination result is deliberately absent: §11.1 was run before
this section was written, so it is reported as measured, not predicted.)*
