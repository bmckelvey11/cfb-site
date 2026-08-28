---
id: 260828-p9k
slug: postseason-backtest-impact
date: 2026-08-28
status: complete
---

# Results — what postseason did to the backtests

Implements `ANALYSIS-PLAN.md`, which was written before any hit rate was computed.
Re-runnable via `analysis.py`. Every number carries its uncertainty.

## Estimand (A) — the shift from adding 550 priced postseason games

| system | sample | n | hit % | 95% Wilson | ROI % | shift |
|---|---|---|---|---|---|---|
| neutral-site-indoor-unders | all | 234 | 55.98 | [49.6, 62.2] | +6.85 | |
| | regular | 109 | **63.30** | [53.9, 71.8] | +20.66 | |
| | postseason | 125 | 49.60 | [41.0, 58.2] | −5.31 | **−7.32 pp** |
| nonconference-away-dogs | all | 3734 | 50.19 | [48.6, 51.8] | −4.11 | |
| | regular | 3421 | 50.34 | [48.7, 52.0] | −3.83 | |
| | postseason | 313 | 48.56 | [43.1, 54.1] | −7.20 | −0.15 pp |
| spread-home-favorites | all | 3773 | 49.67 | [48.1, 51.3] | −5.08 | |
| | regular | 3657 | 49.58 | [48.0, 51.2] | −5.25 | |
| | postseason | 116 | 52.59 | [43.6, 61.4] | +0.39 | +0.09 pp |
| total-unders-high-lines | all | 6040 | 51.71 | [50.4, 53.0] | −1.28 | |
| | regular | 5767 | 51.81 | [50.5, 53.1] | −1.07 | |
| | postseason | 273 | 49.45 | [43.6, 55.3] | −5.53 | −0.11 pp |

**Three of four systems barely move** (≤0.15 pp) — postseason is 2–8% of their sample.

**`neutral-site-indoor-unders` moves −7.32 pp, from 63.30% to 55.98%.** Not a coincidence:
bowls *are* neutral-site games, so a neutral-site filter is precisely the one postseason
floods. Its sample more than doubles, 109 → 234, and the postseason half hits 49.60%
against the regular half's 63.30%. The headline "63% system" is now a 56% system.

**That system's regular-only 63.30% was always thin** — n=109 with a Wilson interval of
[53.9, 71.8], nearly 18 points wide. The two halves' intervals overlap substantially, so
this is *not* a demonstration that bowls behave differently. A formal regular-vs-postseason
contrast was **not pre-specified** and is not run here; treating a post-hoc split as a
finding is the exact move the plan exists to prevent. What can be said: the pooled estimate
is now better identified than the 109-bet one, and it is much less impressive.

## Estimand (B) — is there a postseason edge?

Break-even at −110 is 52.38%. One-sided upper tail, BH across the family of 8.

| system | n | hit % | raw p | BH q | verdict |
|---|---|---|---|---|---|
| neutral-site-indoor-unders | 125 | 49.60 | 0.733 | 0.912 | no evidence |
| nonconference-away-dogs | 313 | 48.56 | 0.912 | 0.912 | no evidence |
| spread-home-favorites | 116 | 52.59 | 0.482 | 0.912 | no evidence |
| total-unders-high-lines | 273 | 49.45 | 0.834 | 0.912 | no evidence |

**These nulls are not evidence of no edge, and were declared uninformative before the
run.** Pre-computed MDE was 7.9–13.4 pp against a realistic edge of 2–4 pp — every
subsample is 2–5x too small. `spread-home-favorites` at 52.59% sits just above break-even
and means nothing: its interval is [43.6, 61.4].

The binding constraint is clusters, not bets. Postseason gives **13–16 clusters** per
system on a `(season, season_type, week)` key — bowls are one slate per season, so 14
seasons is close to the ceiling. The repo's own machinery warns below 40. More seasons is
the only fix; more bowls per season is not available.

## What this does and does not license

- **Does**: adding postseason is safe for the three broad systems and materially changes
  the one selecting bowl-like conditions. Report pooled numbers, not regular-only ones.
- **Does not**: support any claim that bowls are a distinct betting regime. That is the
  motivating intuition (layoffs, opt-outs, motivation) and it remains **untested** —
  nothing here identifies it, and this sample cannot.
- Predictive association only. No causal language.

## Caveat on the whole table

All four systems sit at or below break-even once postseason is included. Nothing here is a
profitable system, and none of these numbers should be read as one.
