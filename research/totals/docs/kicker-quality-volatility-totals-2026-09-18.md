# Kicker quality and volatility vs the over/under — 2026-09-18

**Question.** Does a team's kicker — how good they are, and how erratic — move a game's
realized total relative to the closing sportsbook total? Two separate channels:

- **A, mean shift.** Do good kickers push games over and bad kickers under? That is a claim
  that the market misprices kickers.
- **B, dispersion.** Do volatile kickers widen the spread of outcomes around the number,
  regardless of direction?

**Answer: there is nothing bettable here, and the bound is tight enough to say so.** Neither
channel is significant, but the useful result is not the null — it is the interval. The
95% CI on kicker quality tops out at **+0.60 points per standard deviation**, and even that
most-favourable value the data permits buys only a **50.8% over rate** against a **52.38%**
break-even at −110. The ceiling that kicking physics actually allows is smaller still
(+0.24 pts, a 49.9% over rate). Breaking even would take a **+1.23-point** shift — five times
the ceiling. Every value consistent with this data loses money.

Both channels are also underpowered against their own ceilings — 3× on the mean, 11× on
dispersion — so this is a *bound*, not a demonstration that the effect is zero. The
distinction matters and is spelled out in
[What this does not support](#what-this-does-not-support).

Reproduce:

```bash
python research/totals/scripts/kicker_totals_effect.py
```

`--self-check` recovers a known injected effect on synthetic data and confirms a null panel
is not flagged. `--cache <dir>` caches the loaded frames to parquet so a concurrent
warehouse rebuild does not block a re-run.

---

## Method

### Sample

| | |
|---|---|
| Seasons | 2018–2025 (book totals begin 2018; `stg.kicker_paar` begins 2016) |
| Games | 5,776, both teams FBS with a prior-season kicker on record |
| Team-seasons | 1,034 |
| Outcome | `resid = home_points + away_points − closing total` |
| Residual | mean +0.36, SD 16.02 |

The drop from 8,920 games carrying a book total to 5,776 is division coverage, not a join
failure: from 2022 CFBD's `fact_game` includes FCS-vs-FCS games (the per-season count jumps
1,623 → 3,705), and those teams have no FBS kicker record. Before that expansion the merge
keeps nearly everything — 685/693 in 2018 (98.8%), 765/765 in 2019 (100%), 525/546 in 2020
(96.2%) — while from 2022 roughly a third of games have *neither* team in the FBS kicker
table, which is the FCS bulk.

### Price

**A note on "closing."** `core.fact_game_line.total_close` is CFBD's `overUnder` field
(`duckdb_core.py:611`), paired with a separate `total_open` from `overUnderOpen`. It is the
last total CFBD recorded for that provider, not a timestamped close. Read every "closing
total" below as "last recorded pre-game total." The market-relative claim survives either
reading — a last-recorded line is if anything *closer* to the close than an opener, so it is
the harder benchmark of the two available.

The price is the **median `total_close` across real sportsbooks only** — bovada,
caesars, draftkings, fanduel, betmgm, circa, pinnacle, bet365, william hill, espn bet and
the regional Caesars/SugarHouse books.

`core.fact_game_line` also carries **teamrankings** (7,411 rows) and **numberfire** (5,943),
which are projection sites, not prices. Including them would make this a model-vs-model
comparison rather than a market-relative one, failing the
[evaluation standard's](../../../docs/model-evaluation-standard.md) requirement that prices
be reconstructible at decision time. For the same reason `core.fact_game.selected_total` is
**not** used: it resolves to `teamrankings` for 3,079 games and `numberfire` for 25.

`consensus` is excluded from the primary price because its constituent books are not
recorded; it covers 2017–2022 only and would not extend the sample forward.

Median books per game is 2, which is thin — but it is real history, not a warehouse defect.
Book count by season rises 4 → 5 → 8 → 7 → 5 → 7 → 8 → 9 across 2018–2025; the early seasons
are the Bovada/Caesars era, and 2024–25 carry the full modern board. (Checked explicitly:
`core` was rebuilt by a concurrent process mid-analysis, and the known failure mode where
`fact_game_line` collapses to two books did **not** occur. All numbers below are from a
single post-rebuild run.)

### Features — prior season only

Both features are computed from **season *s* and attached to games in season *s+1***. This
is the leakage gate: a season-level kicker statistic joined to games *within* that season
includes the kicks from the game being predicted, which would invalidate the result
regardless of how it came out.

**Quality.** The team's primary kicker (most FG attempts that season) and their CFBD
**PAAR** — points above average replacement, already adjusted for kick distance and
situation, which raw FG% is not. PAAR-per-attempt is empirical-Bayes shrunk toward the
season mean with weight `n/(n+n₀)`, then rescaled to points per game.

**Volatility.** Pearson **overdispersion φ** of per-game FG makes against a
Binomial(attempts, season rate) baseline. φ = 1 is exactly binomial; φ > 1 is streakier than
chance. This construction matters: raw game-to-game FG% variance is dominated by attempt
count, so a kicker taking one kick a game looks maximally volatile for purely mechanical
reasons. A raw FG-points-per-game SD is reported as a volume-contaminated sensitivity.

Both kickers contribute to a total, so the regressors are the **sums** — `q_sum =
quality_home + quality_away`, `v_sum = φ_home + φ_away` — standardized, so coefficients read
as points per 1 SD.

| Feature (prior season, per team) | mean | SD | p10 | p90 |
|---|---|---|---|---|
| quality — pts/game above an average kicker | 0.10 | 0.09 | −0.01 | 0.22 |
| volatility — overdispersion φ | 1.05 | 0.38 | 0.61 | 1.53 |
| secondary — FG pts/game SD | 2.97 | 0.79 | 2.01 | 3.99 |

### Estimator

OLS of the outcome on the two standardized sums, **two-way cluster-robust** on
home-team-season and away-team-season. A team's kicker feature is constant across its ~12
games in a season, so iid standard errors would be too small.

### Known measurement error

The primary kicker is assigned by prior-season attempt volume. Mid-season kicker changes,
transfers, and true freshmen are all misassigned. This is classical measurement error in the
regressor, which **attenuates toward the null** — it makes a real effect harder to see, never
manufactures one. Not corrected in v1.

---

## Power, computed before the estimates

### Channel A — mean

CFBD PAAR has a year-over-year correlation of **r = 0.159** (n = 1,160 team-season pairs) —
a season of kicking barely predicts the next.

The ceiling is estimated directly rather than assumed: regress a team's *current*-season
kicker value (raw PAAR per game) on its *prior*-season shrunk quality, and multiply the slope
by SD(`q_sum`). It is a *ceiling* because it assumes the market prices none of the kicker's
value at all.

| | |
|---|---|
| Prior shrunk quality → current PAAR/game, slope | 1.036 ± 0.151 (n = 1,160) |
| Mechanical ceiling, pts/game per 1 SD of `q_sum` | **0.183** (upper 95%: 0.235) |
| MDE, 80% power, α = 0.05, iid | 0.590 pts |
| MDE with clustering (m = 5.6, ICC = 0.02, d_eff = 1.09) | **0.617 pts** |
| **MDE ÷ ceiling (upper 95%)** | **3×** |

The slope near 1.0 says the shrinkage is roughly calibrated — one unit of the shrunk prior
feature buys about one unit of next-season kicking value. The ceiling is small anyway, because
the feature itself has an SD of only 0.18 points per game.

### Channel B — dispersion

Field-goal points are 3 × Binomial(attempts, rate), so their per-game variance is
9·a·p·(1−p)·φ. At the observed **1.45 attempts per team-game** and a **75.1% make rate**, one
SD of `v_sum` adds 1.34 to the residual *variance*.

| | |
|---|---|
| Ceiling, change in residual SD | +0.042 pts |
| Ceiling in model B's units (E\|resid\| = √(2/π)·SD) | **+0.033 pts** |
| MDE, 80% power, from the clustered SE | **0.354 pts** |
| **MDE ÷ ceiling** | **11×** |

---

## Results

### A — mean shift

`resid ~ q_sum + v_sum`, n = 5,776, points per 1 SD:

| term | coef | SE | 95% CI | p |
|---|---|---|---|---|
| const | 0.363 | 0.195 | [−0.018, 0.745] | 0.062 |
| **q_sum** (quality) | **0.230** | 0.186 | [−0.135, 0.595] | 0.216 |
| **v_sum** (volatility) | **−0.036** | 0.198 | [−0.423, 0.351] | 0.854 |

The point estimate (0.230) sits almost exactly on the mechanical ceiling (0.183–0.235). The
data is entirely consistent with the ceiling effect being real and completely unpriced. It is
also entirely consistent with zero. It cannot separate them — that is the 3× power gap.

**The economic translation is what settles it.** The over rate is anchored on the
**empirical** base of 49.28%, not on Φ(0): the residual is right-skewed (median −0.25 against
a mean of +0.36, skew 0.34), so a normal model evaluated at the sample mean returns 50.9%
where the sample actually shows 49.3% — it would flatter the result by 1.6pp. The local slope
is the kernel density of the residual at zero, **2.52pp of over rate per point of shift**
(the normal φ(0)/σ gives 2.49pp, so the slope is not the problem; the base is). Break-even at
−110 is 52.38%:

| | shift | over rate | |
|---|---|---|---|
| mechanical ceiling (upper 95%) | +0.235 | 49.88% | below break-even |
| fitted coefficient | +0.230 | 49.86% | below break-even |
| **CI upper bound on the coefficient** | **+0.595** | **50.78%** | **below break-even** |
| shift needed to break even | **+1.227** | 52.38% | 5× the ceiling |

Even the most favourable value in the confidence interval loses to the vig. Resolving the
power gap would not change the decision, because the entire interval is on the losing side.

### B — dispersion

`|resid| ~ v_sum + q_sum`, n = 5,776:

| term | coef | SE | 95% CI | p |
|---|---|---|---|---|
| const | 12.694 | 0.129 | [12.441, 12.947] | <0.001 |
| **v_sum** (volatility) | **−0.188** | 0.126 | [−0.435, 0.060] | 0.137 |
| q_sum (quality) | −0.211 | 0.127 | [−0.460, 0.038] | 0.096 |

Residual SD by volatility tercile: low 16.23, mid 16.04, high 15.78. Levene (median-centred)
W = 0.580, p = 0.560. The point estimate runs the *wrong* way — games with more volatile
kickers were marginally more predictable, not less — which is what noise around zero looks
like. With an 11× power gap this is a bound, not a finding: the design could not have seen the
+0.033-point effect that kicking physics allows.

**Sensitivity.** Swapping φ for the volume-contaminated raw FG-points SD gives
+0.159 [−0.107, +0.425], p = 0.241 — the opposite sign, also null.

### Descriptive — cover rates by tercile

Thresholding into terciles discards information, so these are descriptive, not the decision.
Pushes are excluded from the rate and counted separately. Intervals are Wilson.

**Quality**

| tercile | n | pushes | over % | 95% CI | mean resid |
|---|---|---|---|---|---|
| low | 1,925 | 24 | 47.8% | [45.5%, 50.0%] | −0.14 |
| mid | 1,926 | 20 | 50.1% | [47.9%, 52.3%] | +0.46 |
| high | 1,925 | 22 | 50.0% | [47.7%, 52.2%] | +0.77 |

**Volatility**

| tercile | n | pushes | over % | 95% CI | mean resid |
|---|---|---|---|---|---|
| low | 1,926 | 22 | 49.7% | [47.4%, 51.9%] | +0.64 |
| mid | 1,924 | 31 | 49.2% | [47.0%, 51.5%] | +0.21 |
| high | 1,926 | 13 | 48.9% | [46.7%, 51.2%] | +0.24 |

Six tests against 50%; raw minimum p = 0.054 (low-quality tercile). **Holm-corrected at
α = 0.05: none reject.** Every interval contains 50%, and all six sit inside the 52.38%
break-even at −110.

---

## Why the effect is this small

Field goals are **6.45 points of a 54.7-point game, 11.8%** — and most of that is scored at
rates that barely differ between kickers. A one-SD swing in prior-season kicker quality is
0.18 points per game against a residual SD of 16. The signal is below the half-point
granularity of a totals line.

The more interesting negative is the persistence number, not the regression. **CFBD PAAR does
not persist year to year (r = 0.16).** Whatever a season of kicking measures, it is mostly not
a stable attribute of the kicker — which is also why an in-season kicker-form feature is
unlikely to pay, for the same reason.

---

## What this does not support

- **This is not "kicker quality has no effect on the total."** The fitted coefficient sits on
  the mechanical ceiling, and the design is underpowered by 3× against that ceiling. A real
  effect of ceiling size would look exactly like this. The defensible claim is the bound: the
  effect is **not large enough to beat −110 anywhere in its confidence interval**.
- **The dispersion null is weaker still.** An 11× power gap means channel B is close to
  uninformative about a physically-sized effect. It rules out a large one, nothing more.
- **It does not rule out a within-season or injury-driven effect.** A kicker lost in week 6, or
  a true freshman taking over, is a same-season event this prior-season design cannot see. A
  rolling in-season feature would test that, though r = 0.16 makes a large effect unlikely
  there too.
- **It does not test the extreme tail.** Terciles are a blunt cut; the bottom ~2% of kickers by
  PAAR were not examined separately. At n ≈ 115 games per arm nothing short of a ~10-point
  effect would surface there.
- **It says nothing about spreads, team totals, first-half lines, or live markets.** Only the
  full-game over/under against the closing number was tested.
- **The price data is thin early.** Median 2 books per game, 2018–2025 only. A denser closing
  line would tighten the residual slightly; it cannot move a 3× power gap.
- **PFF is not the source here.** `stg.pff_field_goal` carries distance buckets, which would be
  a better volatility measure, but covers only 2025–2026 (2,166 rows) — too short to use.
  Revisit once it has four or five seasons.

## Trials run

Three regression specifications (A, B, and the raw-SD sensitivity), two tercile tables of
three cells each, and one Levene test. The primary specification was fixed before any estimate
was read. The six tercile tests are Holm-corrected above; the three regressions are reported
uncorrected because each addresses a distinct pre-registered channel rather than competing for
one claim. No threshold, season range, or provider set was chosen after seeing an outcome.

**One method revision, disclosed.** The channel-A ceiling was first computed as
`persistence_r × SD(q_sum)` from the raw PAAR year-over-year correlation. That construction is
attenuated by measurement error in *both* seasons, and it was replaced mid-analysis with a
direct regression of current-season value on the prior shrunk feature. The revision raised the
ceiling roughly 6× (0.028 → 0.183 pts) and cut the power gap from ~22× to 3×. It argues
**against** this doc's conclusion, not for it.

A second revision went the other way. The economic bound was first computed from a normal
model, `Φ(d/σ)`; checking the residual's right skew showed that overstates the over rate by
1.6pp, so it was replaced with the empirical base rate plus a density slope. That moved the
CI-upper-bound over rate from 51.48% to 50.78% — i.e. it *strengthened* the conclusion. Both
revisions are reported because the corrected numbers are the ones above, and the direction of
each is stated so the sequence can be judged rather than taken on trust.
