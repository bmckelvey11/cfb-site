# Pre-registration — retarget the panel at line movement, not margin

**Committed before anything is fitted.** Draft 2026-09-02; expectations may be tightened once,
before the first fit, and that edit is recorded here.

## Why the sweep answered a different question

Every method in `archive/spread-margin-era/prediction-tracker-model-eval-plan-addendum.md` predicted the **game margin**
and measured itself against the closing line. That asks whether the panel out-forecasts the
market. It does not (Harvey–Newbold p = 0.56, best Holm p = 0.49, 50.3% ATS).

The panel publishes early. The question that matches how it would be used is whether it
forecasts **where the line goes**: target = the close, anchored on the line available when the
forecasts appear. On the archive, same 24 seasons, unshrunk all-model median:

| | margin target (sweep) | movement target (this) |
|---|---|---|
| noise: sd of target minus anchor | 15.61 | **2.37** |
| variance ratio | | **43×** |
| corr(model-median deviation, target) | −0.008 | **+0.395** (0.546 for the screened E4 consensus) |
| slope of target on model-median deviation | ≈ 0 | **0.29**, positive in **24 of 24** seasons |

Weight-estimation noise was the whole problem in the sweep; on this target it is roughly forty
times smaller. Which models lead the market becomes estimable. That is a new question, not a
rerun.

## Two versions, one of them tradeable

**A. Archive, opener anchor.** `y = close − open`, `d_i = f_i − open`, 2001–2025, ≈ 17K games.
Learns which models lead the market and by how much. **Not tradeable** as-is: PT's archive
carries no publication time, and week 1 of 2026 showed the opener is months old by game week.

**B. Live, Monday anchor.** `y = close − line_Monday`, `d_i = f_i − line_Monday`, from the
timestamped snapshots (`pt_snapshots/`) joined to Action Network closes. Roughly 45–60 games a
week from week 2 onward. **Tradeable** if the movement is predictable at Monday's price. This is
the forward test, given a target.

A trains the model; B calibrates its one scalar and decides whether anything is bettable.

## Estimators (A), all in residual space, walk-forward by season

Grids fixed here. Hyperparameters by the 1-SE rule on the last three training seasons, as the
addendum did; endpoint hits are reported, not widened.

| | method | free parameters |
|---|---|---|
| M0 | no movement (`ŷ = open`) | — |
| M1 | market's own drift: `α` only | 1 |
| M2 | screened residual consensus `α + γ·mean(d over top-k by prior *movement* skill)`, k ∈ {5, 10, 20} | 2 |
| M3 | ridge on `d_i` over the active set, λ ∈ {10, 100, 1000, 10⁴} | ~40 |
| M4 | screened CSR, k=1 over the top 10 | few |

Skill for screening is **prior-season movement skill**: corr(d_i, move) on prior seasons,
not margin skill. That is the point of retargeting — a model can be a poor margin forecaster and
still lead the market.

## Outcomes

Primary, version A:
1. Out-of-sample R² of `move` for each method, by season; 95% season-cluster wild bootstrap CI
   on the pooled ΔMSE against M0 and M1; Holm across M2–M4.
2. Direction hit rate on games where the line moved and |predicted move| ≥ 1, vs 50%.
3. **Decay curve** (as `model-eval.md` §8): enter at `open + f·(close − open)`, f ∈ {0, .25, .5,
   .75, 1}; ATS win rate of the M2 side at the entry price, re-selected at each f. This says how
   much of the move must be unexploited for the bet to pay.

Primary, version B, once ≥ 300 graded games exist (about week 8):
4. Slope of `close − line_Monday` on the M2 correction, with CI. **This is the number that
   decides everything.** Zero means Monday already is the close and the tree is finished.
5. CLV of a Monday bet on the M2 side, |predicted move| ≥ 1, against the consensus close; and its
   ATS rate at Monday's number vs 52.38%.

## Expectations, recorded now

- A1: M2 R² **0.15–0.30** out of sample; M3 within 0.05 of M2, not better; M4 ≈ M2. The 1-SE
  rule will *not* run to the grid edge this time, because the target is estimable.
- A2: direction **62–68%** on moved games with |pred| ≥ 1.
- A3: profitable only at f ≤ 0.25, as before; the retarget sharpens selection but does not
  change the timing arithmetic.
- **B4: slope between 0.0 and 0.15.** Week 1 said Monday ≈ close for early-season games; in-season
  Sunday openers may leave more. If the slope is under 0.1 with a CI excluding 0.2, close this.
- B5: CLV positive but under 0.3 points; ATS at Monday's number within noise of 50%.

If B4 comes back ≥ 0.3, the right move is to bet earlier than PT publishes: pull the leading
models from their own sites Sunday night, since the model consensus's constituents are public before
PT compiles them.

## Stopping rules

One run of A. B is evaluated once at 300 games and once at season end; no interim looks.
No re-thresholding, no switching anchors, no adding models to the screen after seeing A.

## Amendment A2 — the rest of the library, same target (committed before running)

Version A registered E4, E6, E7, E14. The user's instruction on 2026-09-02: prior nulls targeted
a different question and must not gate methods here. A2 therefore runs, once, on the same
target (close), anchor (open), support and inference:

- **E8** Stock–Watson shrinkage, **E9** residual PCs, **E10** market-anchored peLASSO,
  **E11** trimmed consensus, **E12** elastic net, **E13** Hedge — registered grids from the
  addendum, unchanged.
- **E6 ridge with a wider grid** λ ∈ {10, 10², 10³, 10⁴, 10⁵, 10⁶}. Version A hit 10⁴ in 19 of
  20 seasons; this asks whether the rule wanted more shrinkage or was clipped. Reported as its
  own row (E6w) beside the registered E6.

Holm across the seven new rows. Same outputs as A1/A2 plus the opener-CLV table (pred move ≥ 1
and ≥ 2) for every method that produces a distinct forecast.

**Expectations.** E8 and E12 will not collapse to zero this time (ψ > 0, nonzero coefficients)
because the signal is estimable; E9 with 1–2 components will land near E4 (R² 0.15–0.20); E10
and E11 near E4; E13 below E4; E6w R² within 0.02 of E6 — the wider grid changes little either
way. No method beats E6 by more than 0.03 R². Stopping rule: one run; anything further is a new
amendment.

## Amendment A3 — decontamination (run 2026-09-08, one run)

The panel's values are recorded mid-week; a column that reprints the mid-week line predicts
`close − open` mechanically. Before anything is fitted, drop the top decile of models by
`ρ_i = corr(f_i − open, close − open)` on the model's own games (the margin-era market-proxy
discriminator, applied here for the first time). Rerun A and A2 on the reduced panel; report
each method's retention of R² and of opener CLV. Expectation, recorded before the run: E4
retains ≥ 60%; E6 falls to E4's level or below; E14 retains less than E4. Result in
`line-movement-results.md` § decontamination.

## Amendment B1 — the version B read (committed 2026-09-08, before any in-season close exists)

**Power.** SE(slope) ≈ σ_resid / (σ_x √n). With σ_resid ≈ 1.0 (Monday → close) and
σ_x ≈ 0.45 (E4 − Monday line, from the week-2 snapshots), n = 300 gives SE ≈ 0.13 and an
80%-power MDE ≈ 0.36. The B4 rule "under 0.1 with a CI excluding 0.2" needs SE ≈ 0.07, i.e.
n ≈ 1,000–1,200 before clustering by week. The 300-game read cannot decide it.

**Rule, replacing B4's timing.** At every read `eval_version_b.py` reports the slope, its
season-week cluster CI, the observed σ_resid and σ_x, the MDE at the current n and the n at
which the MDE reaches 0.2. **No verdict before that n or season end, whichever comes first;**
at that point B4's thresholds apply unchanged. Reads are not looks: nothing is changed on the
strength of an interim read.

**Fixed now, before data.** Anchor = the earliest snapshot captured on or after Monday 00:00
ET of the game's kick week. Close = Action Network consensus (book 15), last full-game spread
tick before kickoff. Scores = CFBD via the archive build's name matching. Predictor graded =
E4 (registered); E6 and the model median are reported beside it with no selection among them.
Grader = `research/spread/scripts/eval_version_b.py`, committed with this amendment.

## Amendment ledger and analysis families (committed 2026-09-08, before A6 and B3 run)

Registered because the count of amendments is itself a forking-paths risk. Each amendment below
was pre-registered before its own run, which is the right pattern; what was missing was any
statement of which of them can support a confirmatory claim. **Motivation "data-driven" means the
amendment exists because of something seen in an earlier result.**

| amendment | what it changed | motivation | data-driven? |
|---|---|---|---|
| A2 | Ran E8–E13 and a wider ridge grid on the same target | The registered set was a subset of the library | No — the user's instruction of 2026-09-02, before A ran |
| A3 | Dropped the top decile of market-proxying models before fitting | The 2026-09-08 audit's blocker finding | No — a defect correction, and it *lowered* every estimate |
| B1 | Replaced B4's 300-game read with an MDE gate | The audit showed 300 games cannot decide B4 | No — a power calculation, no outcome seen |
| A4 (below) | Finer ridge grid, run on the walk-forward (A6) panel | **E6 chose λ = 10⁴, the grid edge, in 19 of 20 seasons — on both A3's full-sample screen and A6's walk-forward screen** | **Yes** |
| A5 (queued) | Whether E4's disagreement with PT's `line` predicts the residual move | PT's `line` measured 0.69 off the close | Partly — the measurement prompted it, no slope was seen |
| A6 (below) | Walk-forward decontamination screen | A3's screen was fit on the full sample | No — a defect correction |
| B2 (queued) | Slope decay across weekday captures | Registered as part of the version B design | No |
| B3 (below) | The stopping rule | An adversarial review of B1's gate | No — no read informed it |
| A7 (below) | Ridge grid widened to where the curve must turn over, plus the λ→R² curve itself | **A4 hit its own new edge: λ = 5e4 in 19 of 19 seasons, after A hit 1e4 in 19 of 20** | **Yes** |

**One confirmatory family.** There is exactly one confirmatory hypothesis in this tree: **the
version B E4 slope at the Monday anchor**. Every archive result (A1, A2, A3, A4, A5, A6) and all
line-shopping work is **exploratory** and its section must say so. Holm applies within a family;
no across-family correction is attempted, because with a single confirmatory hypothesis none is
needed.

**A4 is an engineering decision, not an inferential one.** It chooses which λ `weekly_slate.py`
serves. It is reported without a p-value and licenses no claim that the ridge works. Its
motivation is data-driven, which is exactly why it may not carry an inferential claim.

## Amendment A6 — walk-forward decontamination screen (committed 2026-09-08, before the run)

**Names and amends A3.** A3 computed `ρ_i = corr(f_i − open, close − open)` over all of
2001–2025 and dropped the top decile before fitting. The screen therefore saw the evaluation
seasons: the retained panel's identity was chosen with knowledge of its own test set, so A3's
p-values are conditional on that screen. The direction of the bias on R² is conservative — the
screen removes the *most* target-correlated columns — but "conservative" is not "fixed in
advance", and until this amendment runs every citation of A3 must say **conditional on a
full-sample screen**.

**The run.** Recompute the drop list walk-forward: for evaluation season *s*, build it from
seasons < *s* only. Rerun A and A2 on the reduced panel. Report, per method, R² on the full
panel, under the full-sample screen, and under the walk-forward screen, plus both drop lists and
their overlap.

**Expectation, recorded before the run.** The walk-forward drop list overlaps the full-sample one
substantially and E4's retention stays within a few points of 90%. Exploratory, one run.

## Amendment B3 — the stopping rule, replacing B1's timing (committed 2026-09-08)

**Names and replaces B1's "Rule, replacing B4's timing" paragraph only.** B1's power arithmetic,
its anchor, close, score and predictor definitions all stand unchanged.

B1 made the verdict fire when the observed MDE reached 0.2. That is a **data-dependent stopping
time** — the MDE is estimated from the same data the slope is — and the weekly reads make it a
sequential test in practice. B1's own power arithmetic also used the iid form
`σ_resid/(σ_x √n)`, while `eval_version_b.py` falls back to HC1 below `MIN_WEEKS`; the
`n_for_mde_0.2 ≈ 80` printed from the first read came from one week's un-clustered SE and is not
cluster evidence.

**The rule, in these words:**

> No verdict before season end; at season end, confirmatory inference requires ≥ 8 week
> clusters, and with fewer the read is reported as inconclusive.

At season end with ≥ 8 clusters, B4's thresholds apply unchanged. The observed MDE is reported
at every read and **triggers nothing**. Reads are not looks, and this rule — not discipline — is
what makes that true.

**MDE from the cluster SE.** The MDE and any `n_for_mde` figure are computed from the
season-week cluster SE. While the HC1 fallback is active the grader emits them marked
`se_kind: "hc1"` and informational; they may not be quoted as the n a clustered design needs.

## Amendment A5 — the move remaining after PT's last capture (committed 2026-09-08, before the run)

**Motivated by the PT-line-vs-AN-close measurement**, not by any A5 result: on the 1,219 matched
2024–25 games, PT's `line` sits a mean 0.69 points from the Action Network consensus close,
exact on 31%. That gap is a residual move — `AN_close − PT_line` — that happens after PT's last
capture. The question A5 answers: does the panel's disagreement with PT's `line` predict that
residual, i.e. does the panel carry information the market had not yet priced when PT last
looked? This is the only archive evidence that could distinguish "the panel leads the market"
from "the panel reports the line after it moved" — the distinction the 2026-09-08 audit found
unsupported.

**The run.** On the matched 2024–25 games from `check_pt_line_is_close.py`, regress
`y = AN_close − PT_line` on `x = E4 − PT_line`, both in PT sign, using the **walk-forward**
decontaminated predictions (amendment A6, `pt_movement_preds_decon_wf.csv`) — not the
full-sample `_decon` file, whose screen saw its own test set. E6 and E14 reported beside E4, no
selection among them. Clustered by season-week via `cluster_ols`
(`research/spread/scripts/eval_version_b.py`).

**Conditional CI, stated now.** E4's (and E6's, E14's) prediction is itself a fitted quantity
from a first-stage model; `cluster_ols`'s cluster-robust SE does not propagate that first
stage's uncertainty. Every A5 interval carries `conditional_on_fitted_predictor: true` in the
script's output and must be read as conditional on the fitted predictor, not as an unconditional
inference.

**Expectation, recorded before the run.** n ≈ 1,100 (games with a walk-forward E4 prediction
inside the matched 2024–25 set). Slope between 0.0 and 0.10, CI including 0 — the panel's edge
is expected to live in the earlier part of the move, largely absorbed by the market before PT's
last capture. A slope ≥ 0.2 with a CI excluding 0 would be the first archive evidence of
information the market had not priced by PT's last look, and would raise the prior on version B.

**Exploratory, not confirmatory.** A5 is not the tree's one confirmatory hypothesis — the
version B E4 slope at the Monday anchor. A positive A5 result does not by itself license "the
panel leads the market" as a settled claim; it would be one piece of evidence, on an archive
whose "close" is itself a proxy (PT's `line`, matched to AN's consensus close, not a verified
true close — see amendment A5's own gap measurement above).

## Amendment A4 — finer ridge grid on the walk-forward panel (committed 2026-09-08, before the run)

**Names A3's queued A4 and moves its baseline to A6.** A3's original text compared a finer ridge
grid against the full-sample decontaminated panel. Amendment A6 replaced that screen with a
walk-forward one before this ran, and the plan of record (§4, decision 4) requires A4 to run on
whichever panel is current — the full-sample one bakes A3's leak into a serving decision. So A4
runs against `--decontaminate-wf`, and its baseline is A6's numbers, not A3's.

**What is already on the record, from A6 (`pt_movement_decon_wf.json`, coarse default grid
`[0.1, 1, 10, 100, 1000, 10⁴]`):** R²(E4, A6) = **0.1537**; R²(E6, A6) = **0.2009**, chosen
λ = 10⁴ (the grid edge) in 19 of 20 walk-forward evaluation seasons. The grid-edge problem A3
flagged is not an artifact of the full-sample screen — it reproduces on the walk-forward one.

**The run.** `FINE_LAMBDA = [1000, 2000, 5000, 1e4, 2e4, 5e4]` — extending past 10⁴ in both
directions around the edge that A3 and A6 both hit — E6 only, same support, inference and 1-SE
rule, run once with `--decontaminate-wf --fine-ridge`. Output `pt_movement_decon_wf_a4.json`.
Report the chosen-λ distribution across the 20 walk-forward seasons and whether the grid edge
(now 5×10⁴, the top of `FINE_LAMBDA`) is still hit.

**A4 is exploratory and its output is an engineering decision, not an inferential claim**, per
the amendment ledger above: it chooses which λ `weekly_slate.py` serves for E6. Report R² without
a p-value; it licenses no claim that the ridge works. It does **not** touch which predictor is
graded — that stays E4 by decision 2 of the plan of record, regardless of how E6 scores here.

**Decision rule, fixed now, before the fine-grid numbers exist:**

> If R²(E6, A4) − R²(E4, A6) ≤ 0.02, ridge is E4 with more parameters bought for less than 0.02
> R² and is **retired** from `weekly_slate.py`: removed from `PARAMS` and `MODEL_COLS`, the
> docstring's column list updated, and `pred_close` (the median of the served model columns)
> stops including it. If R²(E6, A4) − R²(E4, A6) > 0.02, E6 is **kept**, served at the modal A4
> λ (the most common chosen value across the 20 walk-forward seasons), and the `PARAMS` comment
> cites `pt_movement_decon_wf_a4.json`. Either way the model set is versioned
> (`model_set_version`) in the forward log and in `version_b.json`, and every existing
> `movement_forward_log.csv` row is recomputed under the new definition before any read quotes
> `pred_close` — a predictor that changes mid-forward-test silently redefines the graded
> quantity, and E4 stays the graded predictor in either branch.

**Expectation, recorded before the run.** Given R²(E6, A6) already clears R²(E4, A6) by 0.047 on
the coarse grid, the fine grid is expected to land in the same regime (R² difference > 0.02) and
the keep branch is expected to fire; the fine grid's purpose is to see whether the 1-SE choice
moves off the coarse grid's edge value (10⁴) now that finer steps exist nearby, and whether R²
changes materially — not to re-litigate whether E6 clears E4, which A6 already shows on the
coarse grid.

## Amendment A7 — a ridge grid wide enough to be decisive (committed 2026-09-08, before the run)

**Why a third widening is not just more of the same.** Version A ran λ ∈ {10 … 10⁴} and chose the
top value, 10⁴, in 19 of 20 seasons. A2 widened to 10⁶ and over-shrank. A4 ran a finer grid to
5×10⁴ on the walk-forward panel and chose *its* top value, 5×10⁴, in 19 of 19 seasons. Widening
has now moved the edge twice without ever placing the choice in the interior, and E6 is currently
served at a bound. Repeating the same move a third time, on its own, would be expected to produce
the same outcome.

**The mechanism this amendment tests.** The 1-SE rule selects the *most-shrunk* λ whose
validation error is within one standard error of the best. If the validation curve is flat across
a wide range of λ, that rule will run to the top of whatever grid it is given, no matter where the
top is — the choice would then be an artifact of the grid bound, not evidence that the data want
more shrinkage. The diagnostic that separates these two explanations is the **shape of the
λ → R² curve**, which no run so far has reported. A7 reports it.

**Why this grid must be decisive.** As λ → ∞ the ridge coefficients go to zero, E6's correction
goes to zero, and E6 degenerates to R0, the recalibrated opener, whose R² of the move is ≈ 0.0005.
E6 at λ = 5×10⁴ scores ≈ 0.20. The curve therefore *must* turn over somewhere above 5×10⁴, and a
grid that reaches far enough brackets the turnover by construction. This is the first version of
this question that cannot come back "hit the edge again" without also telling us something.

**Grid, fixed here.** λ ∈ {10³, 3×10³, 10⁴, 3×10⁴, 10⁵, 3×10⁵, 10⁶, 3×10⁶, 10⁷, 3×10⁷, 10⁸,
3×10⁸, 10⁹}. Same panel (A6 walk-forward), same support, same inference, same 1-SE selection as
every prior ridge run — only the grid changes.

**Runnable sanity check, before any decision is read.** R² at λ = 10⁹ must be within 0.01 of R0's
R². If it is not, the ridge is not collapsing to the anchor as λ grows and the implementation is
wrong; the run stops and nothing is decided from it.

**Reported outputs.** For every λ: out-of-sample R² of the move, the validation error, and its
standard error; the argmax λ and the 1-SE λ, separately, per season and modally; and the count of
seasons whose 1-SE choice equals the grid's top value.

**Decision rule, fixed before the run.** Let *L* be the modal 1-SE λ.

1. **Identified** — *L* is in the grid interior and the validation curve rises by more than one
   SE above it. The ridge is identified; serve E6 at *L*.
2. **Flat** — *L* is interior but the curve stays within one SE across three or more decades of λ.
   The 1-SE rule is acting as a tie-breaker, not selecting a value the data identify. **Retire E6
   from the served slate**; `weekly_slate.py` serves E4 and the model median. Report the argmax λ
   and its R² beside the decision.
3. **Still at the edge** — *L* = 10⁹. Given the turnover argument this should be unreachable, so
   it would indicate a defect rather than a finding. **Retire E6 from the served slate** and open
   a defect investigation into the fitter.

Branches 2 and 3 both retire E6 from serving. That is deliberate: a served parameter that is an
artifact of where the grid stopped is not a defensible production setting, and A4 already
established that E6's R² advantage over E4 does not depend on which of these branches obtains.

**Expectations, recorded now.** The curve is flat from roughly 10³ to 10⁵ and declines
appreciably beyond ≈ 10⁶. The argmax λ lands low, near 10³–10⁴, with R² within 0.01 of A4's
0.2002. The 1-SE λ lands far above it, ≥ 10⁶. **Branch 2 fires** — the divergence between the
argmax and the 1-SE choice is the diagnosis, and E6 leaves the served slate.

**Scope.** Exploratory, like every archive amendment: the one confirmatory hypothesis remains the
version B E4 slope at the Monday anchor. A7's output is an engineering decision about what
`weekly_slate.py` serves. No p-value is attached to it and it licenses no claim that the ridge
works. One run.

**If serving changes**, the model set is versioned to 3 and every existing
`movement_forward_log.csv` row is recomputed under it before any read quotes `pred_close`. **E4,
the graded predictor, is unaffected in every branch.**
