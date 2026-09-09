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
| A4 (queued) | Finer ridge grid | **E6 chose λ = 10⁴, the grid edge, in 19 of 20 seasons** | **Yes** |
| A5 (queued) | Whether E4's disagreement with PT's `line` predicts the residual move | PT's `line` measured 0.69 off the close | Partly — the measurement prompted it, no slope was seen |
| A6 (below) | Walk-forward decontamination screen | A3's screen was fit on the full sample | No — a defect correction |
| B2 (queued) | Slope decay across weekday captures | Registered as part of the version B design | No |
| B3 (below) | The stopping rule | An adversarial review of B1's gate | No — no read informed it |

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
