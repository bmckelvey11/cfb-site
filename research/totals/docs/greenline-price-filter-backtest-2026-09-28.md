# Greenline price filter — backtest on 2026 weeks 2-4

2026-09-28

## Question

The week-5 bet rule bets a PFF positive-edge under only when the best DraftKings/FanDuel
total is **above PFF's displayed line and at or above Pinnacle's fair total**. Its premise:
at PFF's own number the under list grades near break-even (55-49), so any edge has to come
from the price. Does the rule hold up on the weeks already graded?

## Answer

**The record cannot say, as registered in advance; the price mechanism checks out.**

- **Record: noise.** The adopted rule picks 12 bets over three weeks, 5-7, −22% ROI with a 95%
  bootstrap interval of −69% to +25%. Its detectable win rate at this n is 89%.
- **Price: as designed.** Its bets beat the REST-backed close by **+1.04 ± 0.73 pts**, and all 8
  that moved moved toward the under (4 flat), against +0.36 for the flags it rejected. The
  books' higher totals were real, not the leading edge of a market about to move up.
- **The Pinnacle leg alone is fragile.** Betting every flag at or above Pinnacle fair (D) reads
  −9.1% on the Pinnacle snapshot before capture and +2.4% on the one after. Its sign depends
  on a few hours of Pinnacle movement.

## Method

Registered in `greenline_price_filter.py`'s docstring and committed (`a33e859e`) before any
result was printed. Four variants, trial count 4:

- A: every positive-edge under at the best DK/FD number
- B: best total above PFF's line
- C: B and at or above Pinnacle fair (the adopted rule)
- D: at or above Pinnacle fair only

Prices are rebuilt at decision time: DK/FD from the odds-api snapshot at each capture
(`CAPTURE_SNAPSHOTS`), Pinnacle from the last oddspapi snapshot at or before PFF's capture.
The weekly CSVs were not used, because two were priced after their capture. The flag
population comes from each week's `pff_greenline` capture with `greenline_unders.unders()`
defaults, not the published lists (week 3's had a spread filter). Best book means the highest
total, then the better price. Graded at the book's total and price against finals in
`greenline_graded.csv`. CLV is the book total at capture minus the median REST-backed close
(span gate).

## Data

2026 weeks 2-4: 126 positive-edge unders. DK and FD priced every one; Pinnacle matched 124.
Snapshots: odds-api `20260909T200531Z`, `20260916T180004Z`, `20260923T180008Z`; Pinnacle
`20260909T212120Z`, `20260916T120004Z`, `20260923T120013Z`.

## Numbers

| split | bets | W-L | win% | Wilson 95% | break-even | ROI (95%) | CLV pts |
| --- | ---: | --- | ---: | --- | ---: | --- | --- |
| A: all positive-edge unders | 126 | 66-60 | 52.4% | 44–61% | 52.3% | +0.0% (−17 to +17) | +0.42 ± 0.22 |
| B: above PFF line | 13 | 6-7 | 46.2% | 23–71% | 53.2% | −13.8% (−57 to +43) | +1.13 ± 0.66 |
| **C: B and ≥ Pinnacle fair** | **12** | **5-7** | 41.7% | 19–68% | 53.2% | −22.2% (−69 to +25) | **+1.04 ± 0.73** |
| D: ≥ Pinnacle fair only | 75 | 36-39 | 48.0% | 37–59% | 52.6% | −9.1% (−30 to +11) | +0.58 ± 0.26 |
| rejected by C | 114 | 61-53 | 53.5% | 44–62% | 52.2% | +2.4% (−16 to +19) | +0.36 ± 0.20 |

C by week: 2-0, 2-3, 1-4. Sensitivity with the first Pinnacle snapshot after capture:
C 6-7 (−13.8%), D 41-35 (+2.4%).

**What "PFF's line" is, and a timing check added after the first run.** PFF's line is the
market total PFF displays beside its pick at capture (`market_over_under`; no book named — it
equals DraftKings' number on 37 of 49 week-5 games, FanDuel's on 39). The DK/FD numbers come
from the odds snapshot *before* the capture, up to 3 hours earlier, so a book sitting above
PFF's line can be the market falling in between rather than a soft book. In the first odds
snapshot after each capture, **10 of the 12 selected numbers were still above PFF's line**
(4-6, CLV +1.05, 6-0 on moved closes); 2 had fallen to it (HOU @ TT, NDSU @ SAC, both week 3,
within 49 minutes; 1-1). The price finding holds on the 10; the record stays noise.

Two further readings:

- **Volume.** C selects about 4 bets a week here, against 9 in week 5.
- **The whole list at the best book** (A, 66-60, +0.0%) is where the under list sits at PFF's
  number: break-even, with shopping DK/FD adding nothing measurable over 126 bets.

## What this does not support

- **Not that the rule loses.** A true 56% bettor goes 5-7 or worse over 12 bets 24% of the
  time (binomial); the ROI interval spans −69% to +25%.
- **Not that it wins.** Positive CLV is what the rule selects for — a number above the market
  mostly closes below it. That is evidence the price is real, not that the price is large
  enough to overcome the juice on these games.
- **Not a Pinnacle rule.** D's sign depends on snapshot timing. Row 10 of
  [greenline-findings](greenline-findings.md) closed Pinnacle as a *ranking* of PFF's picks;
  this reopens Pinnacle as a *price check* on the retail book, a different question, and it
  is logged there as open question G, graded prospectively.
- **Not a reason to change the live rule.** Three weeks, 12 bets, no mechanical fault found.
  The one live consequence of the timing check: confirm the book still shows the higher
  total when placing the bet, since 2 of 12 were gone within an hour.

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4
python research/totals/scripts/greenline_price_filter.py
```

Prospective test: the bet ledger (`research/bankroll/scripts/greenline_bet_log.py`), week 5
on, graded at the line actually taken.
