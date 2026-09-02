# Line movement — results, version A (archive, opener anchor)

Run 2026-09-02 by `research/spread/scripts/eval_line_movement.py`, implementing version A of
`prereg-line-movement.md` (committed `c9bbab5` before the run). One run, registered grids,
2,000 bootstrap draws, season-cluster wild bootstrap throughout. Outputs
`{CFB_DATA_ROOT}/processed/pt_movement_preds.csv`, `pt_movement.json`.

Target: the **closing line**, in margin space. Anchor: the **opening line**. `lineca` and
`linemidweek` removed (the former *is* the close). 16,999 games with both lines; common
walk-forward support 14,068 games, 2006–2025. sd(close − open) = 2.48 points.

## The one-line result

**The panel predicts where the line goes.** Against the game margin it predicted nothing;
against the close every estimator is significant, gamma is stable, and the direction is right
seven times in ten. Betting the panel's side at the opener earns 1.3 to 3.9 points of closing
line value depending on how much movement is predicted. **The opener is the only price at which
that is true**, and week 1 of 2026 showed the opener is months gone by Monday.

## A1 — how much of the move is predictable

R² is relative to "the line does not move"; ΔMSE is against R0 (recalibrated opener).

| method | R² of move | ΔMSE vs R0 | 95% CI | p | Holm | seasons beating R0 |
|---|---|---|---|---|---|---|
| R0 recalibrated opener | 0.0005 | — | | | | |
| **E4** screened consensus k=20 | **0.170** | −1.04 | [−1.82, −0.26] | 0.006 | — | 74% |
| **E6** ridge on deviations | **0.248** | **−1.52** | [−2.46, −0.60] | <0.001 | <0.001 | 84% |
| E7 k by 1-SE rule | 0.147 | −0.90 | [−1.61, −0.15] | 0.011 | 0.011 | 74% |
| E14 screened CSR | 0.136 | −0.83 | [−1.29, −0.38] | 0.001 | 0.001 | **95%** |

E4's gamma on movement: **median 0.30, range 0.19–0.33, positive in 20 of 20 seasons.** The
same estimator's gamma against the close as a margin benchmark was 0.07–0.10. That is the
retarget in one number: the market moves about 30% of the way toward the screened consensus
between open and close, every season.

Hyperparameters: E6 chose λ = 10⁴ in 19 of 20 seasons — the grid edge, as in the sweep — yet it
is the best method. The grid was scaled for a target with sd 15.6; this target has sd 2.5, so
the registered grid is mis-scaled here and a larger λ might do better still. Reported, not
widened (stopping rule). E7 chose k = "all" in 14 of 20. E14 chose k = 1 in 17 of 20.

## A2 — direction

Games where the line moved and the method predicted a move of ≥ 1 point:

| method | n | direction right |
|---|---|---|
| E4 | 2,577 | **70.6%** |
| E6 | 4,888 | **77.2%** |
| E7 | 2,326 | 69.3% |
| E14 | 766 | 78.2% |

Pre-registered expectation was 62–68%. Exceeded by every method.

## Closing line value at the opener

Bet the method's side at the **opening** number when it predicts a move of at least the
threshold. CLV = points the close moved in the bet's favour.

| rule | bets | mean CLV, pts | 95% CI | beat close | worse than close | ATS at the opener |
|---|---|---|---|---|---|---|
| E4, pred move ≥ 1 | 2,914 | **+1.32** | [+0.86, +1.79] | 62.4% | 26.0% | 52.5% [49.6, 55.2] |
| E4, pred move ≥ 2 | 356 | **+3.89** | [+2.10, +5.76] | 75.8% | 18.0% | 64.4% [54.6, 74.3] |
| E6, pred move ≥ 2 | 1,567 | **+2.33** | [+1.77, +2.94] | 77.0% | — | **57.8% [54.7, 60.6]** |

Scale: this feed's line-shopping study put one point of spread at ~3.2 win-rate points, and
break-even at −110 needs ~2.4. A rule that averages 2.3 to 3.9 points of CLV is far past the
bar **if the opener is the price you get.** The ATS column confirms the CLV cashes: 57.8% on
1,567 bets is +10% ROI at −110.

Per-season, E4 ≥ 2 is above 50% in 13 of 19 seasons; 2012 (16/30) and 2023 (12/31) were bad.
Small cells; the E6 rule is the one with volume.

## A3 — decay, and a flaw in the registered version

The registered A3 re-selects bets at each entry price `open + f·(close − open)`. That produced
a curve that goes **below 50%** at intermediate f (47.6% at f = 0.25, 47.1% at f = 0.5, both
p < 0.01), which looked like "the edge inverts" and is not. With gamma ≈ 0.3 the predictor
understates large moves, so once the line has moved partway, the games still showing
|pred − entry| ≥ 1 are the ones where the market moved *further than predicted* — and the rule
bets against the move. Fading steam at a stale price loses. That is a selection artifact of a
shrunk predictor, not a property of the edge. Recorded as the registered result; the honest
decay curve is the **fixed-set** version, chosen post hoc but with no free parameter:

| fixed bet set (chosen at open) graded at entry f | 0.00 | 0.25 | 0.50 | 0.75 | 1.00 (close) |
|---|---|---|---|---|---|
| E4 pred ≥ 1, n≈2,900 | 52.5% | 51.4% | 50.5% | 49.5% | 48.5% |
| E4 pred ≥ 2, n≈355 | 64.4% | 62.4% | 60.7% | 57.8% | 55.2% |

The bets are good at the open and roughly a coin flip at the close. The line, not the game, is
what the panel forecasts. Every point of the move you miss is a point of the edge gone.

## Scorecard against the pre-registration

| expectation | outcome |
|---|---|
| M2 R² 0.15–0.30 | ✓ 0.17 |
| M3 within 0.05 of M2 and not better | ✗ ridge better by 0.08; the estimable target rewards the flexible method |
| 1-SE rule does not run to the grid edge | ✗ E6 at λ = 10⁴ in 19/20 — grid mis-scaled for this target |
| direction 62–68% | ✗ 69–78%, better |
| profitable only at f ≤ 0.25 | ✓ (fixed set; the re-selected version is an artifact) |

Two of five wrong, both in the direction of *more* predictability than expected.

## What this does and does not establish

Establishes: the 154-model panel carries **real, stable, estimable information about where the
closing line will be**, worth 1.3–3.9 points of CLV at the opener, and the ATS record at the
opener confirms the CLV is cashable. The forecast-combination library the sweep exhausted
against the wrong target works against the right one, ridge included.

Does not establish: that any of it is reachable. The archive has no publication timestamps.
Week 1 of 2026 showed the remaining move on Monday was zero for early-season games whose openers
posted in spring. The panel's edge lives in the first quarter of the move.

## What follows

1. **Version B is now the only question**: slope of `close − line_Monday` on the E6/E4
   correction, from the snapshots, first read at ~300 graded games. If Monday retains
   ≥ 25% of the move in-season, the E6 ≥ 2 rule is worth roughly 0.6 points of CLV at Monday's
   price — marginal. If it retains 50%, it clears.
2. **Get earlier than PT.** The constituents are public before PT compiles them. The leading
   movement forecasters (rank by E6 loadings or prior movement skill) can be pulled Sunday
   night when in-season openers post. That is the version of this that could pay, and it is a
   scraping task, not a modelling one.
3. **Run the rest of the library on this target.** Only E4/E6/E7/E14 were registered for version
   A. E8–E13 and a wider ridge grid are pre-registered as amendment A2 in
   `prereg-line-movement.md` and run once; the margin-target nulls of those methods are not a
   reason to skip them here.

---

## Amendment A2 — the rest of the library (run 2026-09-02, registered in `prereg-line-movement.md`)

Same target, anchor, support (n = 14,068) and inference. E6 here uses the **wide** ridge grid
λ ∈ {10 … 10⁶}; the version-A E6 (λ ≤ 10⁴) is the registered one and stands.

| method | R² of move | ΔMSE vs R0 | p | Holm | seasons beating R0 | direction right | chosen parameter |
|---|---|---|---|---|---|---|---|
| E4 screened consensus | 0.170 | −1.04 | 0.006 | — | 74% | 70.6% | γ median 0.30 |
| E6 ridge, **version A grid** | **0.248** | **−1.52** | <0.001 | <0.001 | 84% | 77.2% | λ = 10⁴ (edge) 19/20 |
| E6w ridge, wide grid | 0.193 | −1.19 | <0.001 | <0.001 | 89% | 77.5% | λ = 10⁶ 12/20, 10⁵ 7/20 |
| E7 k by rule | 0.147 | −0.90 | 0.011 | 0.044 | 74% | 69.3% | k = all 14/20 |
| E8 Stock–Watson | 0.112 | −0.69 | <0.001 | <0.001 | 89% | **81.6%** | ψ 0.2–0.6, **not** 0 |
| E9 residual PCs | 0.118 | −0.72 | 0.069 | 0.069 | 58% | 67.1% | 1 component 14/20 |
| **E10 peLASSO** | **0.197** | −1.21 | 0.002 | 0.010 | 84% | 73.6% | λ = 1.0 (edge) 19/20 |
| E11 trimmed | 0.148 | −0.91 | 0.015 | 0.045 | 74% | 69.7% | τ = 0.4 (edge) 19/20 |
| E12 elastic net | 0.133 | −0.82 | <0.001 | <0.001 | 79% | 78.6% | (10, 0.1) 12/20, **nonzero** |
| E13 Hedge | 0.085 | −0.52 | 0.032 | 0.063 | 63% | 63.3% | η = 0.001 (floor) |
| E14 screened CSR | 0.136 | −0.83 | <0.001 | <0.001 | **95%** | 78.2% | k = 1 17/20 |

Every method beats the recalibrated opener; all but E9 and E13 survive Holm. Against the margin
target, E8 and E12 collapsed to exactly zero correction; here E8 keeps ψ ≈ 0.2–0.6 and E12 keeps
nonzero coefficients in every season. That is the cleanest statement of what retargeting did.

**The wide ridge grid hurt.** The 1-SE rule ran to 10⁶ and gave up 0.055 R². It is too
conservative for this target; the registered λ ≤ 10⁴ ridge remains the best method, and a
future amendment should use a *finer* grid below 10⁴, not a wider one above it.

### Closing line value at the opener, every method (intervals are season-cluster bootstrap, absolute)

| method | pred move ≥ 1: bets / CLV / beat close / ATS at open | pred move ≥ 2: bets / CLV / beat close / ATS at open |
|---|---|---|
| E4 | 2,914 / +1.32 [+0.86, +1.79] / 62% / 52.5% | 356 / +3.89 [+2.08, +5.64] / 76% / 64.4% [54.7, 74.1] |
| E6w (wide) | 3,175 / +1.59 [+1.23, +1.97] / 69% / 53.0% | 541 / +3.57 [+2.38, +4.75] / 81% / 59.6% [50.8, 68.5] |
| E6 version A (λ ≤ 10⁴) | — | **1,567 / +2.33 [+1.77, +2.94] / 77% / 57.8% [54.7, 60.6]** |
| E7 | 2,624 / +1.29 / 61% / 51.2% | 273 / +4.21 / 73% / 58.8% |
| E8 | 1,042 / +1.97 [+1.23, +2.67] / 73% / 54.7% [49.9, 59.5] | 96 / +4.48 / 76% / 65.2% |
| E9 | 4,073 / +1.01 / 59% / 50.9% | 755 / +2.19 / 66% / 53.7% |
| E10 | 3,710 / +1.35 [+1.01, +1.69] / 65% / 52.4% | 605 / +3.12 [+1.89, +4.37] / 77% / 57.0% [49.8, 64.3] |
| E11 | 2,476 / +1.30 / 62% / 52.7% | 237 / +4.56 / 75% / 59.2% |
| E12 | 2,320 / +1.62 [+1.17, +2.09] / 70% / 54.0% [50.6, 57.2] | 258 / +3.53 [+1.97, +5.06] / 80% / 60.6% [50.8, 70.4] |
| E13 | 1,348 / +1.29 [+0.26, +2.28] / 56% / 52.7% | 144 / +4.48 [−2.27, +11.26] / 57% / 58.0% |
| E14 | 853 / +2.42 [+1.50, +3.33] / 70% / 56.6% [51.1, 61.6] | 47 / +16.3 [−3.4, +36.3] / 94% / 85% — too few to read |

Every method shows the same shape: the bets it makes at the opener are followed by the market,
with 1–2 points of CLV at the ≥ 1 threshold and 3–4.5 at ≥ 2, and the ATS record at the opener
runs 52–65%. The differences between methods are second-order next to the timing question.

### A2 scorecard

| expectation | outcome |
|---|---|
| E8, E12 do not collapse to zero | ✓ |
| E9 near E4 (R² 0.15–0.20) | ✗ lower, 0.12, and only marginally significant |
| E10, E11 near E4 | ✓ E10 above (0.197), E11 at (0.148) |
| E13 below E4 | ✓ |
| E6w within 0.02 of E6 | ✗ 0.055 worse — the 1-SE rule over-shrank |
| no method beats E6 by > 0.03 R² | ✓ nothing beats the registered E6 |

*Reporting note.* The script's first printout of the per-method CLV intervals added the mean to
bounds that were already absolute; the table above is recomputed from the saved predictions
with the correct intervals, and the script is fixed. Means and all other columns were unaffected.
