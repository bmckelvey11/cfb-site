# Line movement — results, version A (archive, opener anchor)

Run 2026-09-02 by `research/spread/scripts/eval_line_movement.py`, implementing version A of
`prereg-line-movement.md` (committed `c9bbab5` before the run). One run, registered grids,
2,000 bootstrap draws, season-cluster wild bootstrap throughout. Outputs
`{CFB_DATA_ROOT}/processed/pt_movement_preds.csv`, `pt_movement.json`.

Target: the **closing line**, in margin space. Anchor: the **opening line**. `lineca` and
`linemidweek` removed (the former *is* the close). 16,999 games with both lines; common
walk-forward support 14,068 games, 2006–2025. sd(close − open) = 2.48 points.

## The one-line result

**The screened consensus anticipates about 15% of the open→close move, and that survives
removing the most market-anchored columns** (amendment A3, below): E4 keeps 90% of its R²
(0.170 → 0.153), γ stays at 0.29, direction is right seven times in ten, and a bet on its side
at the opener earns 1.2 to 3.8 points of closing line value. The ridge's extra (R² 0.248) was
the mid-week line read back: decontaminated it falls to E4's level (0.163). **The opener is
the only price at which any of this is measured**, the archive's "close" is PT's last recorded
line (0.7 points from the consensus close on average, § target), and week 1 of 2026 showed the
opener is months gone by Monday. Whether anything is left at Monday's price is version B.

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
| E6 falls to E4's level or below | ✓ 0.163 vs 0.153 |
| E14 retains less than E4 | ✓ 79% vs 90% |

## The target — what PT's `line` is (checked 2026-09-08)

`check_pt_line_is_close.py` joins the 2024–25 archive rows to Action Network's consensus close
(book 15) on season and both team names, rematches dropped: **1,219 games matched**.

| | mean \|Δ\| | median | exact | within 0.5 | within 1 |
|---|---|---|---|---|---|
| PT `line` vs AN close | **0.69** | 0.50 | 31.4% | 66.7% | 83.6% |
| PT `lineopen` vs AN close | 1.58 | — | — | 33.3% | — |

PT's `line` is a late line, not the close: it sits 0.7 points from the consensus close on a
typical game, against 1.6 for the opener. Every "close" in this file is that number. The
movement it measures is therefore open → PT's last capture, roughly the first half to two
thirds of the full move; the R² and CLV above are on that shorter path. Version B grades
against the real close and is not affected.

## Version B — first read (2026-09-08, reported, not decided; amendment B1)

`eval_version_b.py` on the 2026 week-2 slate: 42 games with a Monday anchor (2026-08-31
19:05Z), graded against the AN consensus close. One week, so the SE is HC1, not clustered, and
the interval is optimistic.

| predictor | slope of close − Monday on pred − Monday | 95% | sd(x) | MDE (80%) |
|---|---|---|---|---|
| E4 (registered) | **+0.20** | [0.00, +0.40] | 1.17 | 0.28 |
| E6 | +0.43 | [+0.17, +0.70] | 1.07 | 0.36 |
| model median | +0.18 | [−0.03, +0.39] | 1.16 | 0.29 |

sd(close − Monday) = 0.81, mean +0.25. E4's side at |x| ≥ 1: 20 bets, CLV +0.47 [+0.09, +0.86],
beat the close on 55%; graded 2026-09-08 once `core.fact_game` carried the scores: **11–9 ATS
at Monday's number (55.0% [31, 79])**, an interval that says nothing yet. The dispersion of E4
against Monday's line (1.17) is far larger than the
0.45 assumed in amendment B1, so the n at which the MDE reaches 0.2 is about **80–140 games
before week clustering**, not a thousand — but that figure comes from a single week's HC1 SE,
not from cluster evidence, and **amendment B3 has since removed it from the stopping rule**.
It is reported, and it triggers nothing. The verdict waits for season end with ≥ 8 week
clusters.
