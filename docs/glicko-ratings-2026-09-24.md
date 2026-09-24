# Glicko-margin ratings vs Elo and the Bovada open — 2026-09-24

**Answer: NO-GO under the declared rule.**

- **G1 passes:** Glicko-margin beats Elo-MOV, CFBD's Elo, and Glicko-1 clearly. Against
  Elo-MOV it gains −0.33 CRPS and −0.42 MAE.
- **G3 passes:** its intervals are calibrated.
- **G2 fails:** its disagreement with the Bovada open carries no information the open lacks.
  The encompassing slope is β = 0.06 [−0.08, 0.20].
- **Against the open:** it sits 0.46 points of MAE behind, and it is worse in every season.
- **Stress:** every verdict holds in all 13 stress variants.
- **What that means:** it does not feed the fair spread. The gap to the open is widest in
  weeks 1–3 (+1.08 MAE) and narrows to +0.22 by week 8. That gap is the one thing here that
  points at a next step.

**Question.** Does a rating that carries each team's strength *and* its uncertainty from game
to game give a fair home margin that holds information the Bovada open lacks? It is a
candidate "new information source for the fair spread"
([`objective-review-2026-09-23.md`](../research/spread/docs/objective-review-2026-09-23.md),
item 3).

**Design, gates, and grids:**
[`superpowers/specs/2026-09-24-glicko-ratings-design.md`](superpowers/specs/2026-09-24-glicko-ratings-design.md).
The design was declared and approved before any code ran.

**Reproduce:**
`python -m scripts.glicko_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025`
([`scripts/glicko_ratings_eval.py`](../scripts/glicko_ratings_eval.py), model in
[`scripts/glicko_ratings.py`](../scripts/glicko_ratings.py)). It writes
`data/processed/ratings/glicko_eval.json`, which holds every number below, and
`glicko_snapshots.csv`. This was the one scoring run: `VERSION` 1.0, code at `be9d5692`. No
bug was found after scoring.

## Method

- **The model:**
  - Each team has a mean rating in neutral-field points and a variance, which is its RD.
  - A game's margin moves both teams by their Kalman gains.
  - Variance grows by τ² for each idle week.
  - Each offseason pulls ratings toward the subdivision mean with weight w and adds δ².
  - Win probability is Φ(M̂/√S).
- **Baselines**, on the same games and the same clock:
  - Home edge only.
  - CFBD's own pregame Elo, mapped to points on 2014–2019.
  - Elo with a log margin-of-victory multiplier (`elo_mov`).
  - Glickman's Glicko-1 on win/loss.
- **Clock:** every game is forecast at its week's cutoff (the week's earliest kickoff), from
  games that kicked off strictly before it. Results update the state at their own kickoff.
- **Data:** `games.csv` (median close), raw CFBD games JSON (neutral site, subdivision,
  CFBD Elo), and Bovada `spreadOpen` and moneylines from the raw lines JSON.
- **State:** runs from 2013, which is burn-in, through 2025. It includes FBS-vs-FBS and
  FBS-vs-FCS games, regular season and postseason. FCS-vs-FCS games were dropped: 2,389 of
  them, all from 2022–2025, because the tuning seasons have none.
- **Tuning:** on 2014–2019 regular-season FBS-vs-FBS games (4,367 games). The loss was CRPS
  for Glicko-margin, squared error for Elo-MOV, and log loss for Glicko-1.
- **Scoring:** 2021–2025 with every parameter frozen. 2020 updates the state but is neither
  tuned nor scored.
- **Primary population:** FBS vs FBS, regular season, with a Bovada open present. That is
  3,718 games in 77 season-week clusters.
- **Intervals:** a season-week cluster bootstrap, 10,000 draws, seed 20260922. MDE is 2.8 ×
  the bootstrap SE.

## Frozen picks

| Model | Pick | Tuning loss |
| --- | --- | --- |
| `glicko_margin_v1` | σ 13, τ 0.75, w 0.9, δ 6, C = ∞ (no cap), H 2.75, $u_0$ 14 | CRPS 9.274 |
| `elo_mov` | K 60 (**grid edge, flagged**), A 70, $w_e$ 1.0, b = 0.0338 pts per Elo pt | MSE 295.3 |
| `glicko1` | c 10, $\delta_g$ 150, A 65, $w_g$ 0.9 | log loss 0.545 |
| `hfa_only` | H 4.27, sd 21.5 | closed form |
| `cfbd_elo` | b 0.0432, H 3.25, sd 16.8 | closed form |

The FCS seed from 2013 is $m_0 = -27.3$: FBS teams beat FCS teams by 27.3 points on average
that season. The open's predictive sd, fit in sample as the market's best case, is 15.42.

### Tuning surface (2014–2019 only)

For each value of each Glicko-margin axis, the table shows the best tuning CRPS over every
other axis, minus the overall best (9.2745). Zero marks the pick.

| Axis | Values → CRPS above best |
| --- | --- |
| σ | 11: +0.081 · **13: 0** · 15: +0.001 · 17: +0.071 |
| τ (weekly drift) | 0: +0.0008 · **0.75: 0** · 1.5: +0.003 |
| w (offseason carry) | 0.5: +0.155 · 0.7: +0.019 · **0.9: 0** · 1.0: +0.006 |
| δ (offseason sd) | 3: +0.038 · **6: 0** · 9: +0.001 |
| C (margin cap) | 24: +0.162 · 38: +0.002 · **∞: 0** |
| H (home edge) | 2: +0.0004 · **2.75: 0** · 3.5: +0.023 |
| $u_0$ (new team sd) | 8: +0.011 · **14: 0** · 20: +0.002 |

- **Carry is the strong signal.** Keeping 90% of last season's rating beats keeping 50% by
  0.16 CRPS, and full carry (1.0) is close behind. That is consistent with the totals finding
  that priors should carry all of last season
  ([`prior-scale-2026-09-23.md`](prior-scale-2026-09-23.md)).
- **Capping hurts.** A 24-point cap costs 0.16, so blowouts carry information.
- **The dynamics question is unresolved.** τ = 0 is within 0.001 of the pick, so this
  surface cannot say whether within-season drift helps margins. For totals it did not
  ([`dynamic-ratings-2026-09-23.md`](dynamic-ratings-2026-09-23.md)).
- **Reproduce:** run every point of `GRIDS["glicko_margin"]` through `run(GlickoMargin(...))`
  on 2013–2019, as `tune()` does. Score CRPS on the 2014–2019 regular-season FBS-vs-FBS
  mask, then take the minimum per axis value.

## Results (primary population, 3,718 games)

### Margin accuracy

| Forecast | MAE | RMSE | Bias | CRPS |
| --- | --- | --- | --- | --- |
| Home edge only | 15.88 | 20.32 | −0.23 | 11.44 |
| CFBD Elo | 13.02 | 16.38 | −0.16 | 9.23 |
| Elo-MOV | 13.10 | 16.52 | −0.29 | 9.31 |
| **Glicko-margin** | **12.68** | **15.92** | +0.09 | **8.98** |
| Bovada open (decision-time) | 12.22 | 15.42 | +0.05 | 8.68 |
| Median close (not decision-time) | 12.10 | 15.28 | −0.08 | 8.60 |

Bias is forecast minus actual, in points of home margin.

### Paired differences (forecast − comparator; negative = forecast better)

| Pair | Loss | Diff | 95% CI | MDE | Verdict | Per season 2021→2025 |
| --- | --- | --- | --- | --- | --- | --- |
| Glicko-margin − Elo-MOV | CRPS | −0.331 | [−0.419, −0.242] | 0.126 | improves | −0.17, −0.30, −0.21, −0.50, −0.46 |
| Glicko-margin − Elo-MOV | MAE | −0.422 | [−0.564, −0.277] | 0.205 | improves | −0.29, −0.32, −0.23, −0.70, −0.56 |
| Glicko-margin − CFBD Elo | CRPS | −0.250 | [−0.344, −0.160] | 0.132 | improves | −0.15, −0.23, −0.20, −0.33, −0.34 |
| Glicko-margin − CFBD Elo | MAE | −0.333 | [−0.471, −0.200] | 0.196 | improves | −0.25, −0.30, −0.13, −0.46, −0.51 |
| Glicko-margin − home edge | CRPS | −2.462 | [−2.715, −2.203] | 0.365 | improves | all < −2.1 |
| Glicko-margin − Glicko-1 | log loss | −0.0230 | [−0.0325, −0.0133] | 0.0137 | improves | −0.008, −0.026, −0.021, −0.041, −0.019 |
| Glicko-margin − open | MAE | +0.463 | [+0.325, +0.614] | 0.207 | worse | +0.41, +0.61, +0.33, +0.54, +0.42 |
| Glicko-margin − open | CRPS | +0.300 | [+0.210, +0.399] | 0.134 | worse | +0.29, +0.41, +0.22, +0.31, +0.27 |
| Glicko-margin − open (spread-implied) | log loss | +0.0154 | [+0.0085, +0.0224] | 0.0099 | worse | +0.020, +0.028, +0.001, +0.018, +0.011 |
| Elo-MOV − open | MAE | +0.885 | [+0.701, +1.072] | 0.264 | worse | |
| CFBD Elo − open | MAE | +0.796 | [+0.590, +1.023] | 0.310 | worse | |

### Information beyond the open (encompassing slope β)

The model regresses the actual margin minus the open on the forecast minus the open. β > 0,
with an interval clear of 0, would mean the forecast's disagreement with the open predicts
where the margin lands.

| Forecast | β | 95% CI |
| --- | --- | --- |
| **Glicko-margin** | 0.059 | [−0.081, 0.198] |
| Elo-MOV | 0.002 | [−0.094, 0.097] |
| CFBD Elo | 0.048 | [−0.044, 0.141] |

The interval includes 0 for all three. The upper bound of 0.20 caps what this sample can
rule out. Even at that bound, a 5-point disagreement with the open would move the expected
margin by about 1 point toward the model.

### Win/loss

The open's probability is spread-implied: Φ(open/15.42). **No decision-time moneyline
exists.**

| Forecast | Log loss | Brier | Calibration intercept | Calibration slope |
| --- | --- | --- | --- | --- |
| Home edge only | 0.678 | 0.242 | −0.22 | 1.84 |
| CFBD Elo | 0.553 | 0.188 | 0.03 | 1.00 |
| Elo-MOV (native logistic) | 0.601 | 0.199 | 0.08 | 0.55 |
| Glicko-1 | 0.565 | 0.193 | 0.05 | 0.85 |
| **Glicko-margin** | **0.542** | **0.183** | 0.04 | 0.86 |
| Open, spread-implied | 0.527 | 0.177 | 0.02 | 1.01 |
| Median close, spread-implied (not decision-time) | 0.523 | 0.176 | 0.04 | 1.01 |

A calibration slope below 1 means the probabilities are too extreme. Glicko-margin's 0.86 is
mildly overconfident. Elo-MOV's native probabilities (0.55) are far too extreme. That is
consistent with its large tuned K = 60 spreading ratings wider than a 400-point logistic
scale expects. Its margin forecast goes through the fitted slope b, which is unaffected.

### Interval coverage (G3)

| Rating uncertainty √(u_h² + u_a²) | Games | 68% interval | 95% interval |
| --- | --- | --- | --- |
| q1: 5.55–6.05 | 744 | 63.4% | 92.1% |
| q2: 6.05–6.52 | 743 | 63.8% | 93.7% |
| q3: 6.52–7.20 | 744 | 65.1% | 92.9% |
| q4: 7.20–8.41 | 743 | 67.6% | 95.3% |
| q5: 8.41–15.28 | 744 | 67.5% | 93.7% |
| **Pooled** | 3,718 | **65.5%** | **93.5%** |

Both pooled figures sit inside the declared bands, but at their low edges: the 68% band
starts at 65% and the 95% band at 93%. The games the model is surest about (q1) are the most
overconfident, which is the same reading as the 0.86 calibration slope.

### By week bucket (MAE; CRPS in brackets)

| Weeks | Games | Glicko-margin | Elo-MOV | CFBD Elo | Open | Glicko-margin − open |
| --- | --- | --- | --- | --- | --- | --- |
| 1–3 | 735 | 13.40 (9.48) | 13.91 (9.88) | 14.43 (10.28) | 12.32 (8.70) | +1.08 |
| 4–7 | 1,079 | 12.36 (8.78) | 12.75 (9.09) | 12.49 (8.88) | 11.88 (8.51) | +0.48 |
| 8+ | 1,904 | 12.59 (8.91) | 12.99 (9.22) | 12.77 (9.03) | 12.37 (8.77) | +0.22 |

- **The gap to the open shrinks by a factor of five** as the season accumulates evidence.
- **Weeks 1–3 is where carry-over matters most**, and there Glicko-margin beats both Elo
  baselines by the most (−0.51 against Elo-MOV, −1.03 against CFBD Elo). It is also where
  the open is furthest ahead.
- **What the gap suggests:** the preseason state is the weak point. Last season's rating,
  regressed, is not what the market knows in September.
- **What it does not show:** no encompassing slope was declared per bucket, so this is a
  description, not a finding that late-season ratings hold information.

### By season (MAE)

| Season | Glicko-margin | Elo-MOV | CFBD Elo | Open | Median close |
| --- | --- | --- | --- | --- | --- |
| 2021 | 13.08 | 13.36 | 13.33 | 12.67 | 12.55 |
| 2022 | 12.69 | 13.01 | 13.00 | 12.08 | 11.98 |
| 2023 | 12.52 | 12.75 | 12.65 | 12.19 | 11.96 |
| 2024 | 12.85 | 13.55 | 13.31 | 12.31 | 12.17 |
| 2025 | 12.29 | 12.85 | 12.80 | 11.86 | 11.85 |

Each season is a walk-forward fold with frozen parameters. Glicko-margin beats both Elo
baselines and trails the open in all five.

## Declared gates

| Gate | Rule | Result |
| --- | --- | --- |
| G1 vs Elo | Paired CRPS against Elo-MOV *improves*, and paired MAE is not *worse* | **Pass.** CRPS −0.331 [−0.419, −0.242], negative in 5 of 5 seasons. MAE −0.422, *improves*. The caveat: Elo-MOV's K = 60 is on its grid edge after one extension, so the Elo baseline may be slightly under-tuned. The margin over CFBD's Elo (−0.250 CRPS), which has no tuned K, gives the same verdict |
| G2 vs open | Encompassing β lower bound > 0 | **Fail.** β = 0.059 [−0.081, 0.198] |
| G3 coverage | Pooled 68% in [0.65, 0.71], pooled 95% in [0.93, 0.97], every quintile's 95% in [0.90, 0.98] | **Pass.** 65.5%, 93.5%, quintiles 92.1–95.3%, all at the low edge |
| Stress | G1 and G2 verdicts unchanged when each parameter moves to a neighbouring grid value | **Stable.** 13 variants. G1 passes and G2 fails in every one; β ranges from 0.029 (C = 38) to 0.070 (w = 1.0), and every lower bound is below 0 |

**GO requires G1, G2, and G3 plus stability, so this is a NO-GO.** Nothing was re-tuned
after scoring.

## Secondary populations (not gated)

- **FBS vs FBS without the open requirement** (3,730 games): the numbers barely move.
  Glicko-margin MAE 12.70 against the close's 12.12, and CRPS against Elo-MOV −0.333
  [−0.420, −0.243].
- **FBS vs FCS** (580 games): the close is not decision-time.

  | Forecast | MAE | Bias |
  | --- | --- | --- |
  | Glicko-margin | 14.07 | −1.45 |
  | Elo-MOV | 16.10 | −7.98 |
  | Median close | 12.30 | −1.02 |

  Elo-MOV under-predicts FBS blowouts of FCS teams by about 8 points. Two explanations fit,
  and neither was tested:
  - Glicko-margin's per-team variance lets FCS teams, seen about once a season, absorb most
    of each surprise.
  - Elo-MOV's points-per-Elo slope b was fit on FBS-vs-FBS games only, so it may compress the
    wide rating gaps in FBS-vs-FCS games.
- **Bovada's closing moneyline, de-vigged** (3,504 games): not decision-time, with no capture
  time. Its log loss is 0.545, against 0.564 for Glicko-margin and 0.549 for the open's
  spread-implied probability on the same games.

## Trial count

- **Tuning:** 4,162 configurations on 2014–2019. That is 3,888 for Glicko-margin, 80 for
  Elo-MOV, 192 for Glicko-1, and 2 closed-form fits. The pre-score boundary step extended
  nine edge picks by one step each, and the declared grids are subsets of the final ones.
- **Stress:** 13 variants were scored.
- **Scoring:** 1 run.

## What this does not support

- **Any ATS or betting claim.** No wager was graded. A NO-GO on G2 means the ratings'
  disagreement with the open has no measurable value. That is the thing an ATS rule would
  try to exploit.
- **That Glicko-margin is a fair spread.** It is a better power rating than Elo (G1), not a
  better price than the open.
- **That the open is decision-time in a strict sense.** Bovada's open has no capture time,
  and the model's information set at the week cutoff is only an approximation of it.
- **Any claim about FCS-vs-FCS games.** They were excluded. FCS ratings come from about one
  FBS game a season, so they are coarse.
- **A holdout.** 2021–2025 served the archived spread-margin work and the Release B–F
  totals releases. 2026 is untouched.
- **A clean CFBD Elo comparison.**
  - CFBD computes its pregame Elo per game, so it may see earlier results from the same week
    that the week-cutoff rungs do not. That is unverified, and it would favour CFBD Elo.
  - Even with that possible advantage, Glicko-margin beats it.
- **The dynamics question.** See the tuning surface: a pick of τ = 0.75 is not evidence that
  within-season drift helps.

## Next steps

1. **The ATS amendment is not warranted by this result**, because G2 failed. Register it only
   for a rating that passes G2.
2. **Preseason prior.** The weeks 1–3 gap (+1.08 MAE to the open, against +0.22 late) is the
   one opening. Blend returning production, talent, and coaching or quarterback continuity
   into the offseason step. It needs its own declared rule, and it must be read next to
   [`weekly-priors-2026-09-23.md`](weekly-priors-2026-09-23.md), whose priors failed their
   stress rule for totals.
3. **Glicko-2 volatility and an offense/defense split.** These are deferred. Neither is
   likely to move G2 if the preseason state is the weakness.
4. **Include FCS-vs-FCS games** as a declared ablation, if FCS connectivity becomes a
   question.
