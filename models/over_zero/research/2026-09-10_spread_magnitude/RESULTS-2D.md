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

**The recommended rule is the fixed `spread <= 50` cap.** It is what gets
implemented, so it is what gets quoted here; the picked-forward family test below
is supporting evidence for the *idea* of capping, not the rule itself.

**What the cap moves.** Before/after on the same bets, with a season-cluster
bootstrap (9,999 reps) on the difference:

| window | n → capped | hit rate | Δ hit | ROI | Δ ROI | flat units |
|---|---|---|---:|---|---:|---|
| 2016–2025 | 234 → 196 | 64.53% → 67.35% | +2.82pp [+1.01, +4.23] | +23.19% → +28.57% | +5.38pp [+1.93, +8.07] | +54.27 → +56.00 |
| 2018–2025 | 224 → 186 | 65.18% → 68.28% | +3.10pp [+1.54, +4.56] | +24.43% → +30.35% | +5.92pp [+2.94, +8.71] | +54.73 → +56.45 |
| 2021–2025 | 186 → 158 | 62.90% → 66.46% | +3.55pp [+2.26, +4.71] | +20.09% → +26.87% | +6.78pp [+4.31, +8.98] | +37.36 → +42.45 |

**Read those intervals narrowly.** The two samples are nested — the capped one is
the uncapped one minus a slice — so this is arithmetic, not a test, and the
bootstrap only says the arithmetic is stable when seasons are resampled. It cannot
undo the fact that the cap was chosen knowing these seasons. The test is the
kept-vs-dropped 2×2 below, and it is the underpowered one.

**And note the units column.** Ten seasons of capping is worth **+1.73 units**
(+54.27 → +56.00). The ROI gain is almost entirely denominator: 38 units of risk
removed, ~0 profit forgone. On 2021–2025 the absolute gain is larger (+5.09) but
still small. A +5 to +7pp ROI headline here means "less capital at risk for the
same money," not "more money."

Kept vs the disjoint slice the cap drops — the right 2×2, since "capped vs
uncapped" compares a sample to itself minus a slice:

| window | group | n | record | hit rate | 95% CI | ROI | flat units |
|---|---|---:|---:|---:|---|---:|---:|
| 2018–2025 | kept (≤50) | 186 | 127–59 | 68.28% | [61.4, 74.7] | +30.35% | +56.45 |
| | dropped (>50) | 38 | 19–19 | 50.00% | [34.6, 65.4] | −4.55% | −1.73 |
| | uncapped | 224 | 146–78 | 65.18% | [58.8, 71.2] | +24.43% | +54.73 |
| 2021–2025 | kept (≤50) | 158 | 105–53 | 66.46% | [58.9, 73.5] | +26.87% | +42.45 |
| | dropped (>50) | 28 | 12–16 | 42.86% | [26.0, 61.1] | −18.18% | −5.09 |
| | uncapped | 186 | 117–69 | 62.90% | [55.8, 69.6] | +20.09% | +37.36 |

Fisher two-sided p = 0.040 (2018–2025) and 0.021 (2021–2025).

**But neither gap clears its own MDE.** 18.3pp against 22.7pp at n=38; 23.6pp
against 26.4pp at n=28. Per `SKILL.md`'s interpretation rule that cuts both ways —
these are *not* adequately powered tests, and their p-values should be read as
suggestive rather than as establishing the effect.

**Supporting: the picked-forward family test.** Caps {none, 50, 45, 40} chosen on
seasons < t, graded on t. The per-season choice was `none` through 2020, `50` for
2021–2023, `40` for 2024–2025.

| window | rule | n | record | hit rate | ROI |
|---|---|---:|---:|---:|---:|
| 2018–2025 | picked forward | 149 | 106–43 | 71.14% | +35.81% |
| | uncapped | 224 | 146–78 | 65.18% | +24.43% |
| 2021–2025 (binding) | picked forward | 111 | 77–34 | 69.37% | +32.43% |
| | uncapped | 186 | 117–69 | 62.90% | +20.09% |

The 2018–2025 row of that table **overstates the case and should not be quoted**:
the cap picked for 2018–2020 was `none`, so those 38 bets are identical on both
sides, padding the kept column with games from which nothing could be dropped. On
the binding window alone — 2021–2025, the seasons where a cap actually bit — the
kept-vs-dropped test is 77–34 vs 40–35, Fisher p = 0.031, gap 16.0pp against an
MDE of 16.1pp. Right at the boundary, not past it.

**Net: every framing points the same direction, every framing lands at or just
inside its resolution limit.** That consistency across four independent cuts is
the argument; no single one of them is a passing test on its own.

**Total caps were tested as a second candidate family and rejected.** Walk-forward
over {none, 65, 63, 60}: 66.36% vs 65.18% uncapped — no material gain. A
`total <= 63` cap drops 14 bets, **13 of which `spread <= 50` already drops**.
Total is redundant given spread inside the gated region, exactly as §1 predicts.

## 6. Recommendation, and what would change it

**Adopt `|spread| <= 50` alongside `bias > 1.75`** — as the better of two
defensible choices, not as a result the data establishes. Three legs support it: a
favorite-leg sign flip that replicates out-of-period (§3), a market surface whose
gain is concentrated in 40–50 rather than beyond it (§2), and an out-of-sample
gate that points the same way in every framing (§5) while clearing its MDE in
none of them.

The reason to act on evidence this thin is the payoff asymmetry in the next
paragraph, not the strength of the test.

**Do not gate on the posted total.** Two reasons, and the weaker one first: its
coefficient is spec-dependent (§2), significant in spec B and not in spec A. The
decisive reason is independent of that — inside the deployed gate the total is
collinear with spread, a walk-forward total cap gains nothing (66.4% vs 65.2%),
and 13 of the 14 bets it would drop are already dropped by `spread <= 50`. Even
taking spec B's coefficient at face value, there is no separable rule to write.

**Size the decision honestly — this is why the call is easy despite the thin
test.** Over 2018–2025 the bets the cap drops returned **−1.73 units on 38 units
risked** (17% of volume); over 2021–2025, **−5.09 on 28** (15% of volume). They
are not big losers; they are non-earners carrying full variance. So the cap is an
*exposure-efficiency* change, not a loss-avoidance one, and the two ways of being
wrong are not symmetric: capping when the effect is illusory forgoes ~15% of
volume worth approximately zero, while not capping when it is real keeps paying
that variance for nothing. Small upside, smaller downside — which is what makes a
sub-MDE result actionable here and would not in a setting where the discarded
slice was genuinely profitable.

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

## 8. Is 50 the *optimal* cap? — added 2026-09-11

Asked directly after §6. Short answer: **the optimum is not identified as a point.
What is identified is a floor — do not cap below 50.** Four lines converge there,
and the evidence for the cap is stronger than §5 had it.

### 8a. The in-sample search, and why its winner is meaningless

Grid over caps 34–62 on the 234 bets. Two objectives, two different answers:

| objective | argmax | value at argmax | n kept |
|---|---:|---:|---:|
| ROI per bet | **38** | +43.18% | 48 |
| total flat units | **50** | +56.00 | 196 |

**ROI per bet is degenerate as a cap objective.** Tightening can only raise it,
because the bets a tighter cap removes are the ones nearest break-even. Its argmax
of 38 keeps 48 of 234 bets — that is not an optimum, it is the definition of the
statistic. Total units is the objective a bankroll actually has, and it says 50.
The two objectives disagreeing by 12 points of spread *is itself* the finding that
kills naive optimization here.

The units profile is also sawtoothed — 43: +27.4, 45: +36.7, 48: +40.1, 50: +56.0,
51: +49.7 — which is what noise looks like, not a peak.

### 8b. The argmax is not stable

2,000 season-resamples, re-optimizing each time:

| objective | full-sample argmax | resample 2.5–97.5 pct | modes |
|---|---:|---|---|
| units | 50 | **[50, 62]** | 50 (58%), 62 = no cap (31%) |
| ROI | 38 | [36, 50] | 38 (75%) |

On the units objective the data cannot distinguish "cap at 50" from "do not cap at
all" — those are the two modes. But note the lower bound: **across 2,000
resamples the units-optimal cap never lands below 50.** That is the floor. The
open question is whether to cap, not how tight.

### 8c. A fitted cap loses to a round number, out of sample

Cap fitted on seasons < *t*, graded on *t*, pooled 2019–2025:

| rule | n | record | hit rate | ROI | flat units |
|---|---:|---:|---:|---:|---:|
| cap fitted forward (units) | 208 | 134–74 | 64.42% | +22.99% | +47.82 |
| cap fitted forward (ROI) | 101 | 74–27 | 73.27% | +39.87% | +40.27 |
| **fixed cap 50** | 175 | 119–56 | **68.00%** | **+29.82%** | **+52.18** |
| no cap | 208 | 134–74 | 64.42% | +22.99% | +47.82 |

The units optimizer picks `none` every single year — it never caps, so it is
identical to no cap. The ROI optimizer tightens to 38 by 2023 and ends with the
best hit rate on the board (73.27%) while making **less money than not capping at
all** (40.27 units vs 47.82): it bought rate by discarding half the volume.

Fixed 50 beats both.

**What this does and does not establish.** It does *not* validate 50 — 50 came
from this same data and is not being held out. What it establishes is that
**fitting** the cap does worse than a mechanism-motivated round number. That is a
claim about the optimizers, and it is the one the design supports.

### 8d. The mechanism turns right at 50 — the strongest single number here

5-point bands, all 10,255 graded games, season-cluster bootstrap:

| band | n | total_err | 95% CI | fav_err | 95% CI | dog_err | 95% CI |
|---|---:|---:|---|---:|---|---:|---|
| 35–40 | 227 | +2.07 | [−0.3, +4.5] | +1.92 | [−0.4, +4.3] | +0.15 | [−0.8, +1.1] |
| 40–45 | 126 | +2.67 | [+1.0, +4.4] | +1.62 | [−0.2, +3.4] | +1.05 | [+0.1, +2.0] |
| **45–50** | 78 | **+4.29** | **[+2.2, +6.4]** | +2.35 | [+0.2, +4.5] | +1.94 | [+0.3, +3.5] |
| **50–55** | 35 | −2.14 | [−7.2, +2.9] | **−4.20** | **[−7.7, −0.7]** | +2.06 | [−0.4, +4.5] |
| 55–62 | 6 | — | — | — | — | — | — |

45–50 is the **best band in the entire sample**. In 50–55 the favorite error is
−4.20 with an interval that **excludes zero** — the first time this effect clears
its own uncertainty anywhere in this analysis. The dog leg goes on rising (+2.06)
straight through the turn, exactly as §3 said.

**This slice is exploratory and was not pre-registered.** `PLAN.md` §5 fixed the
bands at 30–40 / 40–50 / >50; these 5-point bands were cut afterwards, once the
coarse >50 band came back ambiguous ([−5.65, +0.78]). What the finer cut reveals is
why it was ambiguous: the coarse band pooled 50–55 with a 6-game cell above 55 that
happened to go 6–0. Legitimate, and second.

### 8e. How precisely is the boundary located?

Not precisely. Exact-spread cells near the line hold 1–17 games each; the sharp
drop between cap 50 and cap 51 rests on ~10 bets at spread 50.5. **The boundary is
resolvable to a band, not to a number.** Anything in 48–52 is consistent with this
data; 50 is the round number inside that range and the one the fine bands break at.

### 8f. Answer

**Cap at 50.** Not because a search found it — the searches either refuse to cap
or overtighten to 38 and lose money — but because it is the floor every resampled
optimization respects, the boundary where the favorite leg goes significantly
negative, and the only cap that beats both fitted alternatives on held-out seasons.

§6's recommendation stands, and its evidential basis is stronger than when it was
written: §6 rested on payoff asymmetry over a sub-MDE test, while §8d gives an
interval that excludes zero and §8c gives an out-of-sample win over the fitted
alternatives. The pre-registration caveat in §6 is unchanged, and §8d adds one of
its own.

---
`docs/backtest_bets.csv`, 10,255 graded games / 234 bets, 2016–2025 | −110 flat |
season-clustered wild bootstrap, 9,999 reps | plan pre-committed in `PLAN.md` |
reproduced by `edge_surface.py` | generated 2026-09-10
