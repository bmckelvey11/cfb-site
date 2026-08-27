# Stat angles retested — pace, mismatch, and a full model

I previously wrote that "stat angles are dead." That claim was too broad. It rested on four
*averaged offensive* stats used as standalone quintile predictors. This document runs the three
tests that claim skipped.

**Revised verdict: stat angles are heavily but not completely priced. A properly built model
shows a small, real edge — roughly +3.7% ROI on ~25% of games — that survives walk-forward
validation but not strict multiple-comparison correction.**

---

## Setup

Built entering-game rolling features from `advanced_game_stats_*.json` (27,936 team-games,
2012-2025, 100% pace coverage). Each team's stats are an expanding mean **shifted by one game**,
so no game ever sees its own result. 8,779 games with ≥3 prior games for both teams.

---

## Test 1 — Pace / tempo

The most direct driver of totals, and untested before.

| quintile | combined plays/gm | posted total | under % | mean margin |
|---|---|---|---|---|
| Q1 slow | 122.8 | 50.21 | 50.54% | +0.53 |
| Q2 | 131.7 | 52.80 | 49.97% | +0.93 |
| Q3 | 136.9 | 54.27 | 51.22% | +0.52 |
| Q4 | 142.5 | 56.22 | 51.31% | +0.55 |
| Q5 fast | 152.1 | 59.39 | **53.53%** | +0.01 |

Fast-pace unders: 940-816, **+2.20% ROI, p=0.173.** Directionally interesting, not significant.

The reason is the same as before, and it is the central finding of this whole exercise:

| feature | corr with **posted total** | corr with **margin** |
|---|---|---|
| pace_plays | **+0.418** | -0.014 |
| pace_drives | +0.282 | -0.020 |

Pace is one of the strongest predictors of the *number the book posts* and one of the weakest
predictors of the *residual*. The market sees tempo clearly.

## Test 2 — Mismatch (offense vs opposing defense, not averaged)

This was the biggest gap in the original analysis — averaging both teams destroys mismatch signal.

| feature | corr with total | corr with margin | Q1 → Q5 under% |
|---|---|---|---|
| mm_tot_ppa | +0.127 | -0.003 | 52.79% → 52.79% |
| mm_tot_succ | +0.109 | -0.001 | 51.65% → 51.71% |

**Mismatch is flatter than the averaged stats were.** Zero spread between extreme quintiles.
De-averaging did not rescue the signal — it removed what little there was.

## Test 2b — Weather (bonus; 98% coverage, never tested)

| wind quintile | mean wind | under % | n |
|---|---|---|---|
| Q1 | 1.8 | 50.33% | 2,432 |
| Q2 | 5.1 | 49.25% | 2,534 |
| Q3 | 7.4 | 50.04% | 2,308 |
| Q4 | 10.0 | 50.44% | 2,403 |
| **Q5** | **15.5** | **54.44%** | 2,412 |

Top-quintile wind: p=0.023, and notably wind correlates only **-0.063** with the posted total —
the market barely prices it. That looked like the first genuine gap.

**It does not survive stress-testing.** Thresholds are non-monotonic:

| threshold | under % | p |
|---|---|---|
| wind ≥10 | 53.24% | 0.151 |
| wind ≥12 | 54.18% | 0.049 |
| **wind ≥15** | **52.37%** | **0.514** |
| wind ≥18 | 55.04% | 0.132 |
| wind ≥20 | 53.94% | 0.333 |

A real effect strengthens with dose. This wobbles. Only 7 of 13 seasons positive at wind≥15, and
windy-but-mild games (temp≥50) drop to 51.21%. **The quintile result was threshold luck.**
Cold games likewise show nothing (temp<40: 51.15%, temp<32: 53.08%, both n.s.).

---

## Test 3 — Full model, walk-forward validated

Gradient boosting, 42 features (pace + mismatch + weather + all registry numerics + the posted
total), predicting actual combined points. Bet the side the model disagrees with.

**Model does not beat the market at prediction:**

| | MAE vs actual | corr with actual |
|---|---|---|
| Model | 12.86 | 0.346 |
| Posted total | **12.80** | **0.356** |

The closing total is a better standalone predictor than the model. But that is the wrong test —
what matters is whether the model's *disagreements* are informative.

**Holdout (train ≤2022, test 2023-25):**

| edge threshold | record | hit % | ROI | p | n |
|---|---|---|---|---|---|
| any | 1649-1471 | 52.85% | +0.90% | 0.305 | 3,120 |
| ≥1 | 1337-1170 | 53.33% | +1.81% | 0.175 | 2,507 |
| ≥2 | 1038-893 | 53.75% | +2.62% | 0.118 | 1,931 |
| ≥3 | 755-624 | 54.75% | +4.52% | 0.041 | 1,379 |
| ≥5 | 315-245 | 56.25% | +7.39% | 0.036 | 560 |

Monotonic in edge size — the signature of real signal rather than a cherry-picked cutoff.

**Walk-forward (each season trained only on prior seasons):**

| season | n (edge≥3) | hit % |
|---|---|---|
| 2018 | 271 | 48.3 |
| 2019 | 287 | 57.5 |
| 2020 | 150 | 50.7 |
| 2021 | 236 | 54.2 |
| 2022 | 446 | 54.5 |
| 2023 | 373 | 58.4 |
| 2024 | 397 | 54.9 |
| 2025 | 464 | 53.0 |

**Pooled: 1425-1199 = 54.31%, ROI +3.68%, p=0.025, positive in 6 of 8 seasons.**
At |edge|≥5: 54.70%, +4.43%, p=0.055, 5 of 8 seasons.

### Where the signal comes from

| feature group | importance |
|---|---|
| **posted total** | **46.2%** |
| havoc rates (4 features) | 9.7% |
| mismatch features | 7.7% |
| weather | 4.7% |
| pace | 2.9% |

The model is 46% "trust the market" plus small corrections. The most useful *non-market* features
are **havoc rates** (defensive disruption — tackles for loss, forced fumbles, PBUs), which I never
tested individually. Pace contributes least, consistent with it being fully priced.

---

## Revised conclusion

**What I got wrong:** saying stat angles are dead. A multivariate model finds ~+3.7% ROI on the
quarter of games where it disagrees most with the line, and that holds up in walk-forward testing.

**What holds:** every *single* stat, used alone, is priced. Pace, mismatch, efficiency, talent,
weather — all correlate strongly with the posted number and ~zero with the residual. The edge only
appears when many weak signals are combined, and even then it is small.

**Honest limits:**
- p=0.025 does not survive Bonferroni across this project's ~30 tests (alpha ≈0.002).
- 2018 and 2020 were losing seasons; 2025 was barely above breakeven (53.0%).
- +3.68% ROI is thin. Real-world vig, line movement between model-run and bet placement, and
  limits would eat much of it.
- The model needs the *closing* total as an input (46% of its importance). Using an earlier line
  degrades it — untested here, and it matters because you cannot bet a closing number.

**How this fits the CLV result:** your measured CLV edge (+0.29 pts, p=0.0023) remains the
better-evidenced finding, and the two are complementary rather than competing. CLV says you get
good numbers; the model says there is a small amount of exploitable signal in game features. A
sensible combination is to use model disagreement as a *filter for which games to shop*, not as a
standalone system.

## Next step if you want to pursue this

Rerun with `overUnderOpen` instead of the closing total as the model input, on the 2021+ subset
where opening lines exist. If the edge survives using an *openable* number, it is tradeable. If it
only works with the closing total, it is not.
