# Pre-registration — retarget the panel at line movement, not margin

**Committed before anything is fitted.** Draft 2026-09-02; expectations may be tightened once,
before the first fit, and that edit is recorded here.

## Why the sweep answered a different question

Every method in `prediction-tracker-model-eval-plan-addendum.md` predicted the **game margin**
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
