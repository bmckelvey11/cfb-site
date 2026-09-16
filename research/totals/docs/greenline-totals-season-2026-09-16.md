# PFF Greenline totals, 2026 season to date

Generated 2026-09-16 by `research/totals/scripts/greenline_season_review.py`. Graded at the line in the capture, -110 on spreads and totals, market price on moneylines. Intervals are 95% Wilson. Pushes excluded from win% and calibration.

**Graded weeks:** 2. **Pending:** week 3 (57 flags)

## Record by market

| market | record | win% | 95% CI | units | ROI |
|---|---|---:|---|---:|---:|
| total | 27-22 | 55.1% | 41–68% | +2.55u | +5.2% |

Break-even at -110 is 52.4%. At n=49 pooled, the smallest true win rate a one-sided test would reliably detect is 70%; per market it is total 70%. Anything short of that is not evidence either way.

## By side

| market | side | record | win% | 95% CI | units | ROI |
|---|---|---|---:|---|---:|---:|
| total | over | 5-5 | 50.0% | 24–76% | -0.45u | -4.5% |
| total | under | 22-17 | 56.4% | 41–71% | +3.00u | +7.7% |

## Closing-line value (PFF board close)

- **total**: mean +0.36 ± 0.32 pts (n=44); beat close 19, lost 12, flat 13

Positive means the number moved toward PFF's side after the capture. This is the board PFF shows, not Pinnacle, so it measures whether PFF's flags lead their own displayed market.

## Does PFF's own ranking work?

| market | top half by value | bottom half |
|---|---|---|
| total | 13-11 | 54.2% | 35–72% | +0.82u | +3.4% | 14-11 | 56.0% | 37–73% | +1.73u | +6.9% |

## Calibration of PFF's stated probabilities

| market | n | mean stated p | actual win% | Brier (PFF) | Brier (market) |
|---|---:|---:|---:|---:|---:|
| total | 49 | 55.0% | 55.1% | 0.2478 | 0.2500 |

Market Brier uses 0.5 for spreads and totals (a flag is a bet against a -110 line) and the vig-free price for moneylines. PFF beating the market column means its stated probabilities carry information; a stated-p above the actual win% means the numbers are overconfident.

## Totals in depth

| split | record | win% | 95% CI | units | ROI |
|---|---|---:|---|---:|---:|
| week 2 | 27-22 | 55.1% | 41–68% | +2.55u | +5.2% |
| all weeks | 27-22 | 55.1% | 41–68% | +2.55u | +5.2% |

| under flags by market total | record | win% | 95% CI | units | ROI |
|---|---|---:|---|---:|---:|
| <50 | 4-7 | 36.4% | 15–65% | -3.36u | -30.6% |
| 50-54.5 | 4-6 | 40.0% | 17–69% | -2.36u | -23.6% |
| 55-59.5 | 12-4 | 75.0% | 51–90% | +6.91u | +43.2% |
| 60-64.5 | 1-0 | 100.0% | 21–100% | +0.91u | +90.9% |
| 65+ | 1-0 | 100.0% | 21–100% | +0.91u | +90.9% |

| under flags by PFF value | record | win% | 95% CI | units | ROI |
|---|---|---:|---|---:|---:|
| <2% | 2-3 | 40.0% | 12–77% | -1.18u | -23.6% |
| 2-3% | 4-2 | 66.7% | 30–90% | +1.64u | +27.3% |
| 3-4% | 13-6 | 68.4% | 46–85% | +5.82u | +30.6% |
| 4%+ | 3-6 | 33.3% | 12–65% | -3.27u | -36.4% |

## Pending: week 3

- 57 flagged games; totals 49 under / 8 over; spreads 36 away / 21 home; moneylines 21 away / 32 home.
- mean stated edge: totals +2.50%, spreads +4.07%.

## Reading

**Whole season means weeks 2 and 3.** PFF removes Greenline props once a game kicks off: probed weeks 0, 1 and 2 through a live premium session on 2026-09-16 and every `greenline_total_prop` came back null, including week 2 games we had captured live. Capture began 2026-09-10, so weeks 0-1 (102 games) are gone and cannot be backfilled. The season record is what was captured before kickoff, nothing else.

**Bottom line.** Totals 27-22 (55.1%, CI 41-68%), unders 22-17. Break-even sits inside the interval. The minimum win rate one graded week can detect is 70%; this is not evidence of edge, and it is not evidence of none.

**Structure that recurs, week to week**

- Under share: 39/49 (week 2), 49/57 (week 3). The projection sits below Pinnacle's fair total on 37/48 (w2) and 44/48 (w3) flagged games, median shade -1.35 and -1.53 points. That is a model with a low mean, not game-by-game reads.
- PFF's stated under probabilities were calibrated in week 2 (55.0% stated, 55.1% actual; Brier 0.248 vs 0.250 for a coin). Small information content, correctly sized.
- `value` does not rank outcomes: 4%+ bucket 3-6, 3-4% bucket 13-6, top half vs bottom half 13-11 vs 14-11.
- The 55-59.5 band went 12-4 and every other band under .500. Sixteen games; the CI on 12-4 is 51-90%.
- CLV on PFF's own board: +0.36 +/- 0.32 points, 19 beat / 12 lost / 13 flat. Barely excludes zero, and the reference is PFF's displayed number, not a sharp close.

**What this does not support**

- Betting Greenline unders as a system. One week, CI contains break-even.
- Sizing by PFF's edge number or filtering by band. Both are post-hoc splits on n < 20.
- Any claim about weeks 0-1.

**What settles it.** Four more graded weeks (n ~ 250) gives a fair chance of separating a true 56% from 52.4%; eight weeks does it reliably. Week 3 (49 unders, mean stated edge +2.5%) grades Monday.

**Reproduce**

```
python scripts/pull_pff_scoreboard.py --season 2026
python research/totals/scripts/greenline_season_review.py --totals --out research/totals/docs/greenline-totals-season-<date>.md
```
