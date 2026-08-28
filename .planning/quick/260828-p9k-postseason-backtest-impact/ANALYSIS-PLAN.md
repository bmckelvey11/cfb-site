---
id: 260828-p9k
slug: postseason-backtest-impact
date: 2026-08-28
status: plan
---

# Analysis plan — what postseason does to the backtests

Written before any hit rate was computed. Sample sizes, cluster counts and ICC were
inspected first (design inputs, not outcomes); no win/loss number was.

## 1. Estimand

Two, per system:

- **(A) Shift**: change in ATS/total hit rate when the 550 priced postseason games join
  the sample — `hit_rate(all) − hit_rate(regular-only)`.
- **(B) Postseason edge**: hit rate on postseason bets alone, against the −110 break-even
  of 52.38%.

Population: CFBD games 2012–2025 carrying a consensus line. **Predictive /
conditional-association only — no causal claim.**

## 2. Specification

No model is fit. These are proportions with the existing grading rule
(`team_points + side_spread − opponent_points > 0`). The 4 bundled example systems are
taken as-is; no filter is tuned, so there is no specification search.

## 3. Dependence structure

Bets cluster on `(season, season_type, week)` — shared market, weather and scheduling
shocks. Measured ICC on the postseason subsamples is 0.000–0.022 against 13–16 clusters.
**Cluster counts are far below the repo's own <40 warning threshold**, so asymptotic
cluster-robust intervals are not trustworthy here; Wilson intervals are reported with
the design effect applied, and the small cluster count is stated with every postseason
number rather than buried.

## 4. Primary metric + benchmark

Hit rate against **break-even at −110 (52.38%)** — the market, not a 50% coin flip.
Profit/ROI are descriptive only and never the decision.

## 5. Multiplicity budget

4 systems × 2 estimands = **8 tests**, all pre-specified. Benjamini-Hochberg across the
family of 8. No system was selected on results, so there is no winner's curse to correct
beyond BH.

## 6. Pre-run MDE (computed before any outcome)

At α=0.05, power=0.80, with the design effect applied:

| system | postseason n | clusters | ICC | DEFF | **MDE** |
|---|---|---|---|---|---|
| neutral-site-indoor-unders | 125 | 13 | 0.000 | 1.00 | **12.5 pp** |
| nonconference-away-dogs | 317 | 16 | 0.000 | 1.00 | **7.9 pp** |
| spread-home-favorites | 117 | 16 | 0.010 | 1.06 | **13.4 pp** |
| total-unders-high-lines | 276 | 15 | 0.022 | 1.38 | **9.9 pp** |

**A realistic betting edge is 2–4 pp. Every postseason MDE is 2–5x that.** Estimand (B) is
therefore uninformative by construction: a significant result would be luck and a null is
not evidence of no edge. This is recorded *before* running, per the skill's rule that a
null from an underpowered test is not evidence of absence. Estimand (B) is reported as
descriptive only and **explicitly not gated on**.

Estimand (A) is better posed — it is a shift in a 3.8k–6.1k sample from adding 2–8% more
games — but its magnitude is bounded by that share and is expected to be small.

## 7. Stop rule

One look. Seasons fixed at 2012–2025, all of them, decided in advance. No re-running with
different filters after seeing results.

## 8. Identification

Predictive association only. Bowls differ from regular games in layoff, opt-outs,
motivation and market attention; **none of that is identified here** and no causal
language is used about why any difference exists.
