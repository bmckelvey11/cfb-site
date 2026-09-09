# Line movement — results, version A (archive, opener anchor)

Run 2026-09-02 by `research/spread/scripts/eval_line_movement.py`, implementing version A of
`prereg-line-movement.md` (committed `c9bbab5` before the run). One run, registered grids,
2,000 bootstrap draws, season-cluster wild bootstrap throughout. Outputs
`{CFB_DATA_ROOT}/processed/pt_movement_preds.csv`, `pt_movement.json`.

Target: the **closing line**, in margin space. Anchor: the **opening line**. `lineca` and
`linemidweek` removed (the former *is* the close). 16,999 games with both lines; common
walk-forward support 14,068 games, 2006–2025. sd(close − open) = 2.48 points.

## The one-line result

**The screened consensus anticipates about 15% of the open→close move, and that survives a
decontamination screen that never sees its own test set** (amendment A6, the walk-forward
screen, below — superseding A3's full-sample screen as the citable number): E4 keeps 90.7% of
its R² (0.170 → 0.154), γ stays at 0.28, direction is right roughly seven times in ten, and a
bet on its side at the opener earns CLV at the opener (A6 CLV table, below). **What A3 got
wrong is not E4's number, it is E6's**: under A3's full-sample screen E6 looked like it fell to
E4's level (0.163); under A6 it does not — E6 retains 81.1% and its decontaminated R² (0.201)
stays *above* E4's (0.154). E4 is still graded, not because it scores higher (it doesn't), but
because prereg B1 fixed it before any of this was seen — see decision 2 / the A6 section for why
that still holds. A3 is retained as run (`--decontaminate` still reproduces it byte for byte).
**The opener is the only price at which any of this is measured**, the archive's "close" is
PT's last recorded line (0.69 points from the consensus close on average on 1,440 matched
games, § target), and week 1 of 2026 showed the opener is months gone by Monday. Whether
anything is left at Monday's price is version B.

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

Scale: the ATS-at-the-opener column is the measurement that matters; the CLV points are the
mechanism. (The line-shopping study's 3.2 win-rate points per point is an average dominated by
3/7 crossings on small spreads and does not transfer to these bets, which sit on larger
spreads; do not convert CLV to ROI with it.) 57.8% on 1,567 bets is +10% ROI at −110 **if the
opener is the price you get.**

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

---

## Amendment A3 — decontamination (run 2026-09-08, registered in `prereg-line-movement.md`)

The review of 2026-09-08 (`review-2026-09-08-tree-audit.md` §1.1) objected that the panel's
values are recorded mid-week, so a column that reprints the mid-week line predicts the move
mechanically, and that E6 — the headline — was already known to be 73% market-proxying on the
margin target. `eval_line_movement.py --decontaminate` drops the top decile of models by
`ρ_i = corr(f_i − open, close − open)` before anything is fitted, then reruns A and A2. Same
support (n = 14,068), inference and grids. Outputs `pt_movement_decon.json`,
`pt_movement_a2_decon.json` and the matching `_preds` files.

Dropped, ρ ≥ 0.365 (15 of 152): `linesprs3` 0.76, `linethocal` 0.74, `linethoats` 0.60,
`linethoavg` 0.53, `linegrinder` 0.49, `linethompson` 0.46, `lineteamrank` 0.41, `linecrunch`
0.41, `lineespn` 0.40, `linelabr` 0.40, `lineaustin` 0.39, `linekeep` 0.38, `linebemiss` 0.38,
`linebythen` 0.37, `linedokter` 0.37. Note that three of the margin era's "best forecasters"
(`lineespn`, `lineteamrank`, `linedokter`) are on this list: the columns that looked best against
the close were the ones that had seen it.

| method | R² full panel | R² decontaminated | retained | ΔMSE vs R0 | p | Holm | direction |
|---|---|---|---|---|---|---|---|
| **E4** screened consensus | 0.170 | **0.153** | **90%** | −0.94 [−1.68, −0.19] | 0.010 | — | 68.9% |
| E6 ridge, version-A grid | 0.248 | 0.163 | 66% | −1.00 [−1.78, −0.22] | 0.009 | 0.018 | 72.7% |
| E6w ridge, wide grid | 0.193 | 0.147 | 76% | −0.90 | <0.001 | 0.005 | 74.1% |
| E7 k by rule | 0.147 | 0.133 | 90% | −0.81 | 0.018 | 0.072 | 68.0% |
| E8 Stock–Watson | 0.112 | 0.047 | 42% | −0.29 | <0.001 | 0.005 | 72.0% |
| E9 residual PCs | 0.118 | 0.098 | 83% | −0.60 | 0.11 | 0.13 | 65.6% |
| E10 peLASSO | 0.197 | 0.160 | 81% | −0.99 | 0.005 | 0.030 | 71.6% |
| E11 trimmed | 0.148 | 0.128 | 86% | −0.78 | 0.028 | 0.083 | 67.5% |
| E12 elastic net | 0.133 | 0.090 | 68% | −0.55 | 0.006 | 0.030 | 73.5% |
| E13 Hedge | 0.085 | 0.052 | 61% | −0.32 | 0.064 | 0.13 | 61.1% |
| E14 screened CSR | 0.136 | 0.107 | 79% | −0.66 | <0.001 | 0.005 | 75.6% |

E4's γ on movement after decontamination: median **0.291**, range 0.19–0.32, positive in 20 of
20 seasons (was 0.30). E6 chose λ = 10⁴ in 19 of 20 seasons, as before.

Closing line value at the opener, decontaminated:

| rule | bets | mean CLV | 95% CI | beat close | ATS at the opener |
|---|---|---|---|---|---|
| E4, pred move ≥ 1 | 3,021 | +1.21 | [+0.77, +1.62] | 60.6% | 52.2% [49.4, 55.2] |
| E4, pred move ≥ 2 | 349 | +3.83 | [+2.07, +5.55] | 74.8% | 62.9% [54.3, 71.3] |
| E6, pred move ≥ 2 | 1,224 | +2.19 | [+1.55, +2.84] | 71.8% | 58.0% [53.5, 62.7] |
| E14, pred move ≥ 1 | 674 | +2.45 | [+1.41, +3.51] | 67.7% | 58.8% [52.9, 64.9] |

**Reading.** The consensus's share of the move is not the mid-week line read back: removing the
fifteen most market-anchored columns costs E4 a tenth of its R² and nothing of its γ or its CLV.
The ridge's advantage over E4 was exactly that contamination — it loaded on the anchored
columns, and without them it is E4 with more parameters. The registered E6 row stands as the
full-panel number; the decontaminated E4 is the number to quote for "what the panel knows
before the line moves", with the residual caveat that the remaining models are still recorded
mid-week and only version B can time-stamp them.

### A3 scorecard

| expectation | outcome |
|---|---|
| E4 retains ≥ 60% | ✓ 90% |
| E6 falls to E4's level or below | ✓ under A3's own (conditional) screen, 0.163 vs 0.153 — **A6 below reverses this** |
| E14 retains less than E4 | ✓ 79% vs 90% |

A3's screen saw the seasons it was later scored on. A6, next, is the fix and the citable number;
A3 stands as the run it was, not as the number to quote going forward.

## Amendment A6 — walk-forward decontamination screen (run 2026-09-08, registered in `prereg-line-movement.md`)

A3 computed `ρ_i = corr(f_i − open, close − open)` over the full 2001–2025 archive and dropped
the top decile before fitting — the screen saw every evaluation season, so A3's inference was
conditional on a full-sample screen. A6 fixes that: the drop list for evaluation season *s* is
built from seasons **< *s* only**, so it never sees its own test set. `--decontaminate` still
reproduces A3 byte for byte; A3 is retained as run, and **A6 is now the citable screen**.

| method | R² full panel | A3 full-sample screen | A6 walk-forward screen | A6 retention |
|---|---|---|---|---|
| **E4** screened consensus | 0.170 | 0.153 | **0.154** | **90.7%** |
| E6 ridge | 0.248 | 0.163 | **0.201** | 81.1% |
| E7 | 0.147 | 0.133 | 0.132 | 90.0% |
| E14 screened CSR | 0.136 | 0.107 | 0.113 | 82.9% |

E4's γ under A6: median **0.283**, range 0.182–0.323, positive in all 20 of 20 seasons.

**Drop lists.** A3's fixed list has 15 models. A6's final-season (2025) list has 14, and overlaps
A3's list on all 14 — the one difference is `linedokter`, which A3 dropped and A6 keeps. Across
all 20 walk-forward evaluation seasons, A6's union of dropped models is 33 (versus A3's constant
15), because early seasons have only 5–13 prior seasons to estimate ρ on and the estimate is
noisier there — more models get flagged in the thin early years, not fewer.

**A6 reverses a framing the tree carried.** Under A3, E6 retained 66% of its R² against E4's
90% — the basis for calling E6 "the bigger loser to decontamination". Under the honest,
walk-forward screen, E6 retains **81.1%**, and its absolute decontaminated R² (**0.201**) is
**higher** than E4's (0.154) — closer to the full-panel ordering, where E6 also led. E4 is still
the more robust estimator by retention (90.7% vs 81.1%), but that case is materially weaker than
A3 made it look.

**E4 stays the graded predictor anyway.** Prereg B1 fixed E4 as the predictor version B grades
*before any version B data existed*, with E6 and the model median reported beside it and no
selection among them. A6 showing E6 scores better on the archive is exactly the kind of
result-seen-after-the-fact information that selection is built on — switching now would be the
selection-on-outcome this tree exists to prevent. If E6 is genuinely the better predictor, the
way to establish that is a new pre-registration and its own forward test, not a substitution
into the one already running.

Closing line value at the opener, A6 walk-forward decontaminated:

| rule | bets | mean CLV | 95% CI | beat close | ATS at the opener |
|---|---|---|---|---|---|
| E4, pred move ≥ 1 | 2,902 | +1.24 | [+0.76, +1.70] | 60.8% | 52.0% [49.3, 54.6] |
| E4, pred move ≥ 2 | 338 | +3.72 | [+1.58, +5.85] | 72.2% | 60.4% [49.4, 72.4] |
| E6, pred move ≥ 2 | 1,088 | +2.39 | [+1.73, +3.05] | 73.9% | 57.9% [52.8, 63.2] |
| E14, pred move ≥ 1 | 519 | +3.10 | [+1.71, +4.51] | 71.9% | 57.4% [51.3, 63.5] |

### A6 scorecard

| expectation | outcome |
|---|---|
| walk-forward drop list overlaps the full-sample one substantially | ✓ 14 of 15 final-season models overlap; A6 keeps `linedokter` |
| E4's retention stays within a few points of 90% | ✓ 90.7% |

## Amendment A4 — finer ridge grid on the walk-forward panel (run 2026-09-08, registered in `prereg-line-movement.md`)

Baseline is A6, not A3 — A6 replaced the full-sample screen before A4 ran, and the plan of
record requires A4 to run on whichever screen is current. `FINE_LAMBDA = [1000, 2000, 5000,
1e4, 2e4, 5e4]`, E6 only, `--decontaminate-wf --fine-ridge`, same support, inference and 1-SE
rule, run once.

R²(E6, A4 fine grid) = **0.2002**, against R²(E4, A6) = 0.1537. The pre-registered decision rule
(retire E6 if the gap ≤ 0.02) does not fire — the gap is 0.046 — so **E6 is kept**, served at
the modal chosen λ.

**The decision is not the finding.** λ = 50,000 — the top edge of the new grid — was chosen in
**19 of 19** walk-forward evaluation seasons that produced a choice (the earliest walk-forward
season has no prior seasons to choose a λ from). The old coarse grid's edge was 10⁴; widening
the grid past it moved the edge to 5×10⁴ rather than resolving it — every season still wants
more shrinkage than the grid offers. **A ridge whose 1-SE choice runs to whatever bound the
grid is given is not well identified on this target.** The decision rule does not gate on that,
and it is not being overridden here — E6 is kept exactly per the rule as written — but it has
to be visible rather than a footnote under "E6 kept."

Per decision 2 of the plan of record and the amendment ledger, A4 is an engineering decision
about which λ `weekly_slate.py` serves, not an inferential claim, and it does not touch which
predictor is graded: **E4 stays the graded predictor** regardless of how E6 scores here.
`weekly_slate.py` now serves E6 at λ = 5×10⁴ (`MODEL_SET_VERSION = 2`), and every existing
`movement_forward_log.csv` row (350 of 350) was recomputed under the new definition — a
predictor that changes mid-forward-test silently redefines the graded quantity.

## Amendment A7 — is the ridge penalty identified? (run 2026-09-09, registered in `prereg-line-movement.md`)

**No. E6's advantage over E4 was an artifact of where the grid stopped.**

Version A chose λ = 10⁴, the top of its grid, in 19 of 20 seasons; A4 widened to 5×10⁴ and chose
*its* top value in 19 of 19. A7 asked whether the data want more shrinkage or whether the
selection rule is simply running to whatever bound it is given. `pick_1se` takes the
**most-shrunk** λ within one SE of the best, so a flat validation curve makes it a tie-breaker,
not an identification. Grid: λ ∈ {10³ … 10⁹}, run on the A6 walk-forward panel, E6 alone at each
point (`eval_ridge_curve.py`), n = 14,068.

**Registered sanity check — passed.** As λ grows the ridge coefficients go to zero and E6 must
degenerate to R0. R²(10⁹) = 0.0012 against R0's 0.0005, a gap of 0.0006 inside the registered
0.01 tolerance. The curve turns over, so a decision may be read from this run.

| λ | 10³ | 3×10³ | 10⁴ | 3×10⁴ | 10⁵ | 3×10⁵ | 10⁶ | 3×10⁶ | 10⁷ | 3×10⁷ | 10⁸ | 3×10⁸ | 10⁹ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R² | .198 | .199 | .201 | **.202** | .194 | .175 | .139 | .094 | .047 | .019 | .007 | .003 | .001 |

The estimator has a genuine interior optimum at λ = 3×10⁴ (R² 0.2019). **Its selection rule does
not find it.** The validation curve sits within one SE of its best across a median of **3.0
decades** of λ, so the 1-SE rule modally picks **λ = 3×10⁶** — where R² is 0.094, less than half
the peak. The modal validation argmin is 10⁵; only 4 of 19 seasons chose the grid's top value,
so this is not an edge hit.

**The number that matters.** Running E6 exactly as registered — the 1-SE rule, on a grid wide
enough to let it express itself:

| | R² of the move |
|---|---|
| E6, as reported under A4/A6 (grid stopped at 5×10⁴) | 0.2009 |
| **E6, registered estimator, honest grid** | **0.0655** |
| E4, same support | **0.1537** |

E6 never outscored E4. Every ridge grid this tree has run was truncated near the R² peak, which
flattered the method by preventing its own selection rule from wandering to the shrinkage it
actually prefers. The A6 finding that "E6 retains 81.1% and outscores E4" is withdrawn: it was a
property of the grid bound, not of the estimator.

**Branch fired: `flat`** — the pre-registered action. **E6 is retired from the served slate.**
`weekly_slate.py` serves E4 and the model median; `pred_close` no longer includes E6, the model
set is versioned to **3**, and all 350 forward-log rows were recomputed under it. E6 is still
computed and reported beside E4 in every version B read, because prereg B1 requires that and A7
retired it from *serving*, not from existence — now fitted at λ = 3×10⁶, the value its own rule
chooses, rather than A4's retired 5×10⁴.

**E4, the graded predictor, is unchanged** (version B slope +0.202, identical before and after).

### Scorecard against the pre-registration

| expectation | outcome |
|---|---|
| Curve flat ~10³–10⁵, declining beyond ~10⁶ | **Partial.** Flat 10³–10⁵ as predicted, but the decline starts earlier, at 3×10⁵. |
| Argmax low, near 10³–10⁴ | **Miss.** The R² peak is at 3×10⁴ and the modal validation argmin is 10⁵ — both above the predicted range. |
| R² at the argmax within 0.01 of A4's 0.2002 | **Hit.** 0.2019. |
| 1-SE λ lands ≥ 10⁶ | **Hit.** Modal 3×10⁶. |
| Branch 2 (`flat`) fires; E6 leaves the served slate | **Hit.** Median 3.0 decades within 1 SE. |

Not predicted, and the most consequential result: that E6's headline R² would collapse to 0.0655
once the rule was allowed to choose freely. The amendment was written to test whether the penalty
was identified, not to re-rank the methods; it did both.

## Amendment A5 — the move remaining after PT's last capture (run 2026-09-08, registered in `prereg-line-movement.md`)

Regress `y = AN_close − PT_line` on `x = pred − PT_line` for E4, E6, E14, on the matched
2024–25 archive games, using the **walk-forward decontaminated (A6)** predictions, clustered by
season-week (`cluster_ols`).

| predictor | slope | 95% CI (conditional) | n | clusters |
|---|---|---|---|---|
| E4 | −0.033 | [−0.059, −0.007] | 1,440 | 31 |
| E6 | −0.022 | [−0.049, +0.006] | 1,440 | 31 |
| E14 | −0.027 | [−0.051, −0.003] | 1,440 | 31 |

**Correction: 1,440 matched games, not the 1,219 this file recorded before this run** (see the
target section below, updated with this run). The matching logic (`check_pt_line_is_close.py`)
is unmodified and the merge loses zero rows to NaN; the difference is Action Network table
growth between measurements, not a join change — 1,219 was the same measurement on a smaller
table.

Every interval above carries `conditional_on_fitted_predictor: true` — E4/E6/E14 are themselves
fitted first-stage predictions, and `cluster_ols`'s cluster-robust SE does not propagate that
first stage's uncertainty (A5's own caveat, registered before the run).

**Result misses the pre-registered expectation on sign and by an order of magnitude.**
Pre-registered: slope 0.0–0.10 with a CI including zero; ≥ 0.2 excluding zero would have been
evidence of unpriced information. What came back is negative and small: sd(E4 − PT_line) ≈
1.79, so a full one-standard-deviation disagreement between E4 and PT's line predicts roughly a
−0.06 point shift, in the direction opposite the panel's read, against a mean residual move of
0.69 points. This was the only archive evidence that could distinguish "the panel leads the
market" from "the panel reports the line after it moved" — it does not produce that evidence.
Do not read the negative sign as a substantive finding either: a slope this small against a
0.69-point average gap is closer to noise than to a real negative effect, on an archive whose
"close" (PT's `line`) is itself a proxy, not a verified true close.

## The target — what PT's `line` is (checked 2026-09-08, updated with the A5 run)

`check_pt_line_is_close.py` joins the 2024–25 archive rows to Action Network's consensus close
(book 15) on season and both team names, rematches dropped: **1,440 games matched** (was 1,219
at first measurement — see amendment A5 above for why the count grew).

| | mean \|Δ\| | median | exact | within 0.5 | within 1 |
|---|---|---|---|---|---|
| PT `line` vs AN close | **0.69** | 0.50 | 31.7% | 66.9% | 83.3% |
| PT `lineopen` vs AN close | 1.57 | — | — | 33.6% | — |

PT's `line` is a late line, not the close: it sits 0.7 points from the consensus close on a
typical game, against 1.6 for the opener. Every "close" in this file is that number. The
movement it measures is therefore open → PT's last capture, roughly the first half to two
thirds of the full move; the R² and CLV above are on that shorter path. Version B grades
against the real close and is not affected.

## When the constituents publish (from snapshots, checked 2026-09-08)

The "get earlier than PT" idea (results doc "What follows" item 2, above) assumed the leading
movement forecasters post before PT's Monday compile. Three slates of 6-hourly snapshots exist
so far. **Not yet evaluable** — mechanically the `< 10 of 20 present Monday` branch fires for
all three, but the denominators explain why before the counts do:

| slate | top-20 (by prior movement skill) present at first Monday-window capture | first capture, hours after Monday 00:00 ET |
|---|---|---|
| 2026-08-24 | 0 of 6 | 129.7h |
| 2026-08-31 | 2 of 7 | 15.1h |
| 2026-09-07 | 0 of 3 | 39.2h |

Only **8 of the top-20** archive movement-ranked models appear as columns in the live scrape at
all (the live scraper carries 54 line-model columns, of which 28–45 are populated in any one
snapshot) — a schema difference between
the archive file and the live scraper, not a publication-timing signal — so these denominators
(6/7/3, not 20) are already capped low before the timing question is even asked. Two of the
three slates never had a real Monday capture: collection began mid-slate for 08-24 (first
capture 129.7h after its Monday), and the 09-04 collector outage pushed 09-07's first capture to
39.2h. Only the **08-31 slate (15.1h)** actually tests the question this branch is nominally
answering.

**Do not read the branch's stated consequence — re-anchoring amendment B2 to the first snapshot
with ≥ 15 of 20 present — as triggered.** It fires mechanically on thin, mostly-empty data (two
of three slates missing a real Monday capture), not on a measured finding that PT's Monday
compile is incomplete. Revisit once collection has run cleanly through several ordinary Mondays.

This does not affect E4 as currently served: `screened()` ranks by prior skill restricted to the
models actually active in a given snapshot, so live E4 takes the top 20 among the 28–45 model
columns the live scraper carries, not the 20 that a full archive panel would pick.

## Amendment B2 — capture buckets (first read 2026-09-08, registered in `prereg-line-movement.md`)

One capture per game per bucket — 0–24h "mon", 24–48h "tue", 48–72h "wed", ≥ 72h "thu+" after
the week's Monday 00:00 ET — on a fixed game set: a game missing from any populated bucket is
dropped from every bucket.

Currently populated buckets: `tue`, `wed`, `thu+`. **No snapshot has yet landed in the `mon`
bucket**, so `mon` is excluded from the fixed-set universe and **0 games are dropped** (42 of 42
week-2 games present in each of tue/wed/thu+). This is a fact about the current collector
cadence relative to Monday 00:00 ET, not the amendment failing — a future non-zero drop count is
B2 working as designed, not a regression.

| bucket | slope | 95% CI | n | week clusters |
|---|---|---|---|---|
| tue | +0.202 | [+0.004, +0.401] | 42 | 1 |
| wed | +0.174 | [−0.009, +0.357] | 42 | 1 |
| thu+ | +0.396 | [+0.114, +0.678] | 42 | 1 |

One week, HC1 SE — not the season-week clustered design B2 is registered for. The `tue` row is
the same games and the same slope as the version B anchor read below (the current collector's
first capture after Monday lands in the `tue` window). Decides nothing; read weekly alongside
B4, per B3's stopping rule.

## Version B — reads (updated 2026-09-08; amendment B1, stopping rule B3)

One row per Monday read. **No verdict before season end; at season end, confirmatory inference
requires ≥ 8 week clusters, and with fewer the read is reported as inconclusive** (amendment
B3, verbatim). The MDE the grader prints at every read is informational — derived from the same
un-clustered HC1 SE as the slope while under `MIN_WEEKS` — and triggers nothing.

| Monday | n graded | E4 slope | 95% CI | week clusters | SE kind | model_set_version | verdict |
|---|---|---|---|---|---|---|---|
| 2026-08-31 | 42 | +0.202 | [+0.004, +0.401] | 1 | HC1 | [2] | null |

`read_status: pre_season_end`. One week cluster is not clustered inference; the interval above
is optimistic and must not be read as evidence either way. E6 (+0.371 [+0.082, +0.660]) and the
model median `pred_close` (+0.181 [−0.029, +0.391]) are reported beside E4 with no selection
among them — E4 is graded per prereg B1, not because it scores highest here (it doesn't — see
amendment A6 above for the same pattern on the archive).

The dispersion of E4 against the anchor line (sd(x) = 1.17) is what makes the informational MDE
land where it does (`mde_80` 0.28, `n_for_mde_0.2` 80) — reported, and, per amendment B3,
triggering nothing.

Cumulative bet record, |x| ≥ 1, E4's side: 20 bets, CLV +0.47 [+0.09, +0.86], beat close on 55%;
graded once `core.fact_game` carried the scores: **11–9 ATS at the anchor price (55.0% [31.1,
78.9])** — an interval that says nothing yet. The verdict waits for season end with ≥ 8 week
clusters.
