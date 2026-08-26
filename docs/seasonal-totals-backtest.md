# Backtest: seasonal totals effect — 13k games

**Verdict: the seasonal under effect does not exist. Hypothesis rejected.**

Data: `data/processed/games.csv`, 12,964 games 2013–2025. 12,459 have totals; 12,339 after
dropping pushes. Week 10+ used as the Nov–Jan boundary (verified against raw `startDate`:
weeks 1–9 are Aug–Oct, weeks 10+ are Nov–Dec).

---

## The headline test

| window | n | under record | under % |
|---|---|---|---|
| Early (wk 1–9) | 7,965 | 4062-3903 | **51.00%** |
| Late (wk 10+) | 4,374 | 2222-2152 | **50.80%** |

**Difference: -0.20 percentage points — in the *wrong* direction. z=-0.21, p=0.83.**

Late-season unders vs the -110 breakeven of 52.38%: **p=0.982**. Not close.

This test was well-powered: with 12k games it could detect a difference as small as **1.8pp** at
95% confidence. The observed 0.2pp is indistinguishable from zero. This is not an underpowered
null — it is a confident null.

## It doesn't replicate across seasons

Late beat early in **6 of 13 seasons** — a coin flip. Season-level differences swing from
-4.9pp (2021) to +4.7pp (2020) with no trend.

| season | early% | late% | diff |
|---|---|---|---|
| 2013 | 50.0 | 50.0 | 0.0 |
| 2014 | 51.3 | 51.4 | +0.2 |
| 2015 | 53.1 | 50.8 | -2.3 |
| 2016 | 52.0 | 49.8 | -2.2 |
| 2017 | 54.9 | 51.2 | -3.7 |
| 2018 | 49.0 | 53.4 | +4.4 |
| 2019 | 52.0 | 50.2 | -1.8 |
| 2020 | 47.6 | 52.3 | +4.7 |
| 2021 | 54.0 | 49.1 | -4.9 |
| 2022 | 48.8 | 49.4 | +0.6 |
| 2023 | 50.1 | 50.7 | +0.7 |
| 2024 | 51.5 | 48.4 | -3.0 |
| 2025 | 50.1 | 53.8 | +3.7 |

Your bet history covers 2023–2025, where the diffs were +0.7, -3.0, +3.7 — noise.

## Deeper into the season makes it *worse*, not better

If cold weather and conservative play-calling suppressed scoring, the effect should strengthen
in December. It reverses:

| cutoff | under % | n |
|---|---|---|
| wk ≥10 | 50.80% | 4,374 |
| wk ≥11 | 50.54% | 3,435 |
| wk ≥12 | 50.18% | 2,493 |
| wk ≥13 | **49.41%** | 1,524 |

Monotonic decline. The mechanism I proposed in the earlier analysis is not supported.

## The low-total cell also fails

Your sharpest observed cell was sub-50 totals late (13-3, 81%). Against 13k games:

| subset | under % | n |
|---|---|---|
| total <50, early | 50.05% | 2,154 |
| total <50, late | **49.61%** | 1,292 |

p=0.978 vs breakeven. The 13-3 was variance.

## Totals are fairly priced overall

Blanket under, all 12,339 games: **6284-6055 = 50.93%**, flat-bet ROI at -110 = **-2.77%**.

That 50.93% is nominally different from a 50% coin flip (p=0.040) — a whisper of an under lean —
but nowhere near the 52.38% needed to overcome vig. Mean margin (points minus total) is **+0.45**,
i.e. games land slightly *over* the number on average. The market is well calibrated.

Your exact zone — totals 55–62, week 10+: **639-600 (51.57%), ROI -1.54%.** Negative.

---

## Reconciling with your 47-28 record

Your 75 late-window unders went 47-28 (62.7%). Against the true base rate of 50.8%:

- Expected wins: 38.1
- Actual wins: 47
- **Excess: +8.9 wins**
- P(≥47 of 75 | true rate 50.8%) = **0.026**

So your result is unlikely-but-not-extraordinary under the null. At ~2.6%, and given you and I
tested roughly 20 subgroups looking for patterns, finding one cell at p=0.026 is close to what
pure noise produces. **This is textbook multiple-comparisons selection.**

Two readings remain, and this data cannot separate them:

1. **Variance.** 75 bets, one lucky cell found after extensive slicing. Most likely.
2. **Genuine selection skill within the late window** — you picked *which* late games to bet, and
   the 13k-game base rate for all late games says nothing about your ability to choose among them.
   The backtest kills the blanket rule, not necessarily your judgment.

What it definitively kills: **"bet unders late season" as a mechanical system.** There is no
seasonal edge to harvest.

---

## What this changes

- **Do not** build a Nov–Dec under system. Recommendation #2 from `under-bets-analysis.md` and
  #4 from `under-bets-summary.md` are withdrawn.
- **Do not** size up on low totals late. That cell is 49.61% over 1,292 games.
- The earlier docs' framing — "cut early-season unders, concentrate late" — was built on a
  pattern that does not survive. Concentrating into the late window buys nothing.
- **Still valid:** unders overall are near-breakeven-negative (-2.77% blanket), so your +8.9%
  on 203 bets came from selection, not from the under side being structurally mispriced. If
  there is an edge in your betting, it is in *which games you pick*, not *when* or *which side*.

## What would actually test your skill

Win rate needs thousands of bets to separate 57% from 52.4%. **CLV converges in ~100.** The
Action Network export has no closing lines. Getting them — via the API path we abandoned, or a
manual export if AN offers closing odds — is the single highest-value next step. It would settle
in one season what this backtest cannot answer about your selection.
