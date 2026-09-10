# Edge by spread and total level — recommendation: cap the rule at spread 50, leave total alone

Executes [`PLAN.md`](PLAN.md), which was written before any 2D estimate existed.
Follows [`RESULTS.md`](RESULTS.md), which found the >50 record and could not
explain it.

**Recommendation up front: add `|spread| <= 50` to the bet rule. Do not gate on
the posted total.** The evidence and its limits are below; §6 says what would
change the call.

Run:
```
python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py
python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py --since 2022
python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py
```
Data: `docs/backtest_bets.csv` (`monitor/roi_report.py`), **10,255 graded games**,
seasons 2016–2025, of which 234 qualify under the deployed rule (bias > 1.75,
walk-forward). Pushes dropped; ROI at −110 flat. Inference is season-clustered
(10 clusters) with a wild cluster bootstrap, 9,999 Rademacher reps.

## 1. The question cannot be answered on the bets, and why

Inside the bet set, `bias = f(spread, total)` and the 1.75 gate is a level curve
of that function. Spread and total therefore move together **by construction**:

| bet record by posted total | n | record | hit | mean spread |
|---|---:|---:|---:|---:|
| ≤55 | 126 | 82–44 | 65.1% | 39.0 |
| 55–60 | 73 | 49–24 | 67.1% | 47.0 |
| 60–65 | 31 | 18–13 | 58.1% | 52.5 |
| >65 | 4 | 2–2 | 50.0% | 52.9 |

The mean-spread column rises monotonically with the total band. "Splitting on
total" and "splitting on spread" are the same split. There are zero bets at
spread ≤ 35 with total > 50, and zero at spread > 50 with total ≤ 50. **Two
separate effects are not identified on the 234.**

Everything below is therefore fit on all 10,255 graded games, where the gate does
not restrict and the (spread, total) rectangle has full support. That buys a
statement about **where the market misprices totals** — the right input to a gate
— and *not* a statement about the model's record in a region, since outside the
gate the model does not bet. The two are kept apart throughout.

## 2. The mispricing surface (all games, well powered)

`total_err = actual_total − posted_total`. Zero means the market is right.

**Spec A, linear** (`total_err ~ spread + total + spread:total`), n=10,255:

| term | coef | boot p | boot 95% CI |
|---|---:|---:|---|
| spread | +0.2879 | 0.035 | [+0.040, +0.536] |
| total | −0.0485 | 0.154 | [−0.128, +0.031] |
| spread × total | −0.0043 | 0.070 | [−0.0089, +0.0003] |

**Spec B, spline in spread** (`cr(spread, df=4) + total`), n=10,255:

| term | coef | boot p | boot 95% CI |
|---|---:|---:|---|
| total | −0.1005 | **0.018** | [−0.175, −0.027] |

Both specs were declared in `PLAN.md` §2 before fitting; both are reported.

**Read:** the market under-prices totals more as the spread widens (+0.29 points
of realized-minus-posted per point of spread), and *less* as the posted total
rises (−0.10 points per point of total in spec B). The negative interaction says
the spread effect weakens at high totals.

The total coefficient is the one place the two specs disagree in significance:
spec A's interval contains zero ([−0.128, +0.031]), spec B's does not
([−0.175, −0.027]). Spec A splits the same variation between `total` and the
`spread × total` interaction, so neither term carries it alone. The §6
recommendation does not rest on this coefficient in either direction — it rests
on the spread dimension — and the disagreement is reported rather than resolved
by picking the spec that reads better.

By fixed band (`PLAN.md` §5 — bands set in advance, not searched):

| spread | n | mean total_err | 95% CI |
|---|---:|---:|---|
| 0–20 | 8,064 | +0.32 | [−0.20, +0.83] |
| 20–30 | 1,377 | +0.77 | [+0.01, +1.52] |
| 30–40 | 569 | +1.08 | [−0.26, +2.42] |
| **40–50** | **204** | **+3.29** | **[+1.99, +4.59]** |
| **>50** | **41** | **−0.15** | **[−5.96, +5.65]** |

## 3. The mechanism: the favorite leg flips, the dog leg does not

Same games, `total_err` split into the model's own implied legs:

| spread | n | favorite error | 95% CI | underdog error | 95% CI |
|---|---:|---:|---|---:|---|
| 0–20 | 8,064 | +0.17 | [−0.00, +0.34] | +0.15 | [−0.27, +0.57] |
| 20–30 | 1,377 | +0.22 | [−0.52, +0.96] | +0.54 | [+0.19, +0.89] |
| 30–40 | 569 | +0.57 | [−0.61, +1.75] | +0.51 | [−0.45, +1.47] |
| 40–50 | 204 | **+1.90** | [+0.07, +3.74] | +1.39 | [+0.49, +2.29] |
| >50 | 41 | **−2.40** | [−5.65, +0.78] | +2.26 | [−0.58, +5.06] |

The dog leg — the mechanism the model is actually built on — rises monotonically
and is *strongest* in the >50 band. Censoring at zero does not break. The favorite
leg is what turns: positive and growing through 40–50, then negative above it. The
model takes the favorite at its implied number; in a 50-plus-point mismatch the
favorite is censored from above (starters pulled, clock burned) and gives back
more than the dog's floor wins.

**This replicates on 2022–2025 alone** (`--since 2022`, n=5,802): favorite error
+1.77 at 40–50 and **−3.83** above 50, dog error +1.10 and +1.56. Not a pre-2021
artifact.

## 4. What the smooth cannot see — the honest limit

The spline's fitted `total_err` at the median total rises monotonically all the way
out: 2.22 at spread 40, 3.69 at 50, **5.42 at 60**. It never turns down. That is
not a finding — 41 of 10,255 games sit above 50 and have essentially no leverage
on a smooth. The fit sails straight over the band the question is about.

`PLAN.md` §6 stated this before fitting: **the >50 cell is power-dead and cannot
be widened.** 41 games is the entire ten-season population at that spread, not a
subsample. MDE there is 7.1 points of total error; the realized CI is
[−5.96, +5.65]. On the bets, MDE is 22.7pp of hit rate.

So the >50 dip is **not established by the >50 data**, and the smooth that would
borrow strength for it is exactly the thing that erases it. What carries the
recommendation is the leg decomposition (§3) — a sign flip in the favorite leg,
replicated out-of-period — plus the out-of-sample gate below. Not the cell mean.

## 5. The gate

Per `PLAN.md` §7, a cap is adopted only if a version of it fit on prior seasons
beats the unrestricted rule on held-out ones.

**Candidate family = spread caps {none, 50, 45, 40}, chosen on seasons < t, graded
on t, pooled 2018–2025:**

| rule | n | record | hit rate | ROI |
|---|---:|---:|---:|---:|
| cap picked forward | 149 | 106–43 | **71.14%** | +35.81% |
| uncapped | 224 | 146–78 | 65.18% | +24.43% |

Kept vs the disjoint slice it drops: 106–43 vs 40–35, **Fisher two-sided p =
0.011**, observed gap 17.8pp against an MDE of 16.1pp. Adequately powered and
significant. The per-season choice was `none` through 2020, `50` for 2021–2023,
`40` for 2024–2025.

**Fixed cap at 50** — the implementable version — over the same 2018–2025 window:

| group | n | record | hit rate | 95% CI | ROI | flat units |
|---|---:|---:|---:|---|---:|---:|
| kept (≤50) | 186 | 127–59 | 68.28% | [61.4, 74.7] | +30.35% | +56.45 |
| dropped (>50) | 38 | 19–19 | 50.00% | [34.6, 65.4] | −4.55% | −1.73 |
| uncapped | 224 | 146–78 | 65.18% | [58.8, 71.2] | +24.43% | +54.73 |

Fisher p = 0.040 — but the observed 18.3pp gap sits **below** the 22.7pp MDE at
n=38. The fixed-50 comparison is at the edge of what this sample resolves; the
picked-forward family test (more dropped bets, hence more power) is the stronger
evidence. Both point the same way.

**Total caps were tested as a second candidate family and rejected.** Walk-forward
over {none, 65, 63, 60}: 66.36% vs 65.18% uncapped — no material gain. A
`total <= 63` cap drops 14 bets, **13 of which `spread <= 50` already drops**.
Total is redundant given spread inside the gated region, exactly as §1 predicts.

## 6. Recommendation, and what would change it

**Adopt `|spread| <= 50` alongside `bias > 1.75`.** Three independent legs support
it: a favorite-leg sign flip that replicates out-of-period (§3), an out-of-sample
gate that clears its own MDE (§5), and a market surface whose gain is concentrated
in 40–50 rather than beyond it (§2).

**Do not gate on the posted total.** Two reasons, and the weaker one first: its
coefficient is spec-dependent (§2), significant in spec B and not in spec A. The
decisive reason is independent of that — inside the deployed gate the total is
collinear with spread, a walk-forward total cap gains nothing (66.4% vs 65.2%),
and 13 of the 14 bets it would drop are already dropped by `spread <= 50`. Even
taking spec B's coefficient at face value, there is no separable rule to write.

**Size the decision honestly.** Over eight seasons the dropped bets returned
**−1.73 units on 38 units risked**. They are not losers; they are non-earners. The
cap is an *exposure-efficiency* change — it removes about a sixth of the volume at
a near-zero expected cost — not a loss-avoidance one. If bet volume is worth more
than ROI per bet, keeping them is defensible and cheap.

**This is a predictive rule, not a causal one.** Spread >50 is nearly synonymous
with FBS-vs-FCS (Alabama State, Arkansas–Pine Bluff, The Citadel, Grambling,
Samford). The causal variable may be mismatch class, roster depth, or benching
convention. Spread is a usable proxy because it is posted pre-game; it is not
established as the cause. The follow-up that would separate them: grade
FBS-vs-FCS as a flag in its own right across all games, where both vary.

**One selection caveat that cannot be washed out.** The candidate cap set
{50, 45, 40} was written down in `PLAN.md` *after* `RESULTS.md` found the >50
record on these same seasons. The walk-forward protocol removes the in-sample
grading of a chosen cap; it does not remove the fact that the neighbourhood was
chosen with knowledge of this data. A genuinely clean confirmation is 2026 graded
forward under the capped rule, and that is the test worth waiting for.

**What would overturn it.** The >50 population grows ~4 games and ~4 bets a season.
Detecting a 5-point `total_err` difference at 80% power needs n≈84 games — about
**ten more seasons** at the current rate. Detecting a 12pp hit-rate difference
needs n≈136 bets, which is not reachable this decade. So the >50 cell will not
settle itself, and the monitoring trigger should be the **favorite leg**, not the
record: if `fav_err` in the >50 band turns positive and holds over a few seasons,
the mechanism in §3 is wrong and the cap should come off.

## 7. Live relevance

The 2026-09-10 board carries 12 picks; **3 exceed spread 50** — Florida A&M @
Miami (FL) (−59.5), Howard @ Indiana (−56.5), Southern U @ Houston (−51.0), all
FBS-vs-FCS, and two of them the top picks by bias. Under this recommendation those
three come off the board. **No code was changed and no board was re-run** — the
cap is a rule change, and that is the user's call, not this analysis's.

---
`docs/backtest_bets.csv`, 10,255 graded games / 234 bets, 2016–2025 | −110 flat |
season-clustered wild bootstrap, 9,999 reps | plan pre-committed in `PLAN.md` |
reproduced by `edge_surface.py` | generated 2026-09-10
