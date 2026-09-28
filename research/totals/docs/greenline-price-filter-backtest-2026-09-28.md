# Greenline price filter — backtest on 2026 weeks 2-4

2026-09-28

## Names

Two PFF numbers are easy to confuse, and this record keeps them apart:

- **PFF market line** — `market_over_under`, the market total PFF displays beside its pick at
  capture. No book is named; it equals DraftKings' number on 37 of 49 week-5 games and
  FanDuel's on 39. It is not PFF's opinion.
- **PFF projection** — `greenline_total_projection`, PFF's own forecast of the total.
- **Projection edge** — PFF's win probability for the under at the *book's* total, from its
  projection (`match_greenline_books.edge_at`), minus the book price's break-even. Reported,
  never a gate.

## Question

The week-5 bet rule, as first used (C), bet a PFF positive-edge under only when the best
DraftKings/FanDuel total was **above the PFF market line and at or above Pinnacle's fair
total**. Later the same day it was replaced (E) by **at least 2.0 points above the PFF
projection and at or above Pinnacle fair**. The premise of both: at the PFF market line the
under list grades near break-even (55-49), so any edge has to come from the price. Do they
hold up on the weeks already graded?

## Answer

**The record cannot say, as registered in advance; the price mechanism checks out.**

- **Record: noise.** C picks 12 bets over three weeks, 5-7, −22% ROI (95% bootstrap −69% to
  +25%); E picks 11, 5-6, −15% (−66% to +36%). Detectable win rates at these n are ~90%.
- **Price: as designed.** C's bets beat the REST-backed close by **+1.04 ± 0.73 pts** and E's
  by +0.84 ± 0.47; every close that moved, moved toward the under (8-0 and 7-0), against
  +0.36 for the flags C rejected. The books' higher totals were real.
- **PFF's projection overstates its edge by about 4 points.** Across all 126 flags the
  projection edge at the book's number averaged +3.9%; the flags returned +0.0%. E's bets
  carried +6.9% by the projection and returned −15%.
- **The Pinnacle leg alone is fragile.** Betting every flag at or above Pinnacle fair (D) reads
  −9.1% on the Pinnacle snapshot before capture and +2.4% on the one after.

## Method

Registered in `greenline_price_filter.py`'s docstring and committed before any result was
printed. A-D in `a33e859e`. E in `11f811b3`, after C's result had been seen; its 2.0-point
margin was chosen from pass counts in weeks 2-4 (12 of 126 flags; 95 at 1.5, all 126 at 0),
never from outcomes, to match C's volume. Trial count 5:

- A: every positive-edge under at the best DK/FD number
- B: best total above the PFF market line
- C: B and at or above Pinnacle fair (week-5 rule as first used)
- D: at or above Pinnacle fair only
- E: at least PFF projection + 2.0 and at or above Pinnacle fair (adopted)

A zero margin over the projection would filter nothing: every positive-edge under sits above
PFF's projection, by 1.7 points at the median.

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

| split | bets | W-L | win% | Wilson 95% | break-even | ROI (95%) | projection edge | CLV pts |
| --- | ---: | --- | ---: | --- | ---: | --- | ---: | --- |
| A: all positive-edge unders | 126 | 66-60 | 52.4% | 44–61% | 52.3% | +0.0% (−17 to +17) | +3.9% | +0.42 ± 0.22 |
| B: above PFF market line | 13 | 6-7 | 46.2% | 23–71% | 53.2% | −13.8% (−57 to +43) | +6.7% | +1.13 ± 0.66 |
| C: B and ≥ Pinnacle fair | 12 | 5-7 | 41.7% | 19–68% | 53.2% | −22.2% (−69 to +25) | +6.7% | +1.04 ± 0.73 |
| D: ≥ Pinnacle fair only | 75 | 36-39 | 48.0% | 37–59% | 52.6% | −9.1% (−30 to +11) | +3.7% | +0.58 ± 0.26 |
| **E: ≥ projection + 2.0 and ≥ Pinnacle fair** | **11** | **5-6** | 45.5% | 21–72% | 53.3% | −15.1% (−66 to +36) | +6.9% | **+0.84 ± 0.47** |
| rejected by C | 114 | 61-53 | 53.5% | 44–62% | 52.2% | +2.4% (−16 to +19) | +3.6% | +0.36 ± 0.20 |
| rejected by E | 115 | 61-54 | 53.0% | 44–62% | 52.2% | +1.5% (−17 to +18) | +3.6% | +0.38 ± 0.23 |

By week — C: 2-0, 2-3, 1-4; E: 2-0, 2-2, 1-4. Sensitivity with the first Pinnacle snapshot
after capture: C 6-7 (−13.8%), D 41-35 (+2.4%), E 6-6 (−6.6%).

**Timing check, added after the first run.** The DK/FD numbers come from the odds snapshot
*before* PFF's capture, up to 3 hours earlier, so a number that passes can be the market
moving in between rather than a soft book. In the first odds snapshot after each capture,
**10 of C's 12 numbers still passed** (4-6, CLV +1.05, 6-0 on moved closes); 2 had fallen to
the PFF market line within 49 minutes (HOU @ TT, NDSU @ SAC, week 3; 1-1). For E, 9 of 11
still passed (4-5). The price finding holds on the survivors; the record stays noise.

Two further readings:

- **Volume.** C and E each select about 4 bets a week here; in week 5, C selected 9 and E 8.
- **The whole list at the best book** (A, 66-60, +0.0%) is where the under list sits at the
  PFF market line: break-even, with shopping DK/FD adding nothing measurable over 126 bets.

## What this does not support

- **Not that either rule loses.** A true 56% bettor goes 5-7 or worse over 12 bets 24% of the
  time (binomial); both ROI intervals span roughly −65% to +30%.
- **Not that either wins.** Positive CLV is what these rules select for — a number above the
  market mostly closes below it. That is evidence the price is real, not that it is large
  enough to overcome the juice on these games.
- **Not a reading of PFF's projection edge at face value.** It ran about 4 points above what
  the flags returned; treat it as a ranking PFF believes, not a probability.
- **Not a Pinnacle rule.** D's sign depends on snapshot timing. Row 10 of
  [greenline-findings](greenline-findings.md) closed Pinnacle as a *ranking* of PFF's picks;
  this reopens Pinnacle as a *price check* on the retail book, a different question, and it
  is logged there as open question G, graded prospectively.
- **Not evidence for E over C.** E was adopted after C's result was seen, and in weeks 2-4 it
  is C minus one bet (LAT @ BAY, 53 against a 53.5 book total); the backtest cannot separate
  them. They diverge live: in week 5, E drops EMU @ MASS (1.9 points over the projection).

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4
python research/totals/scripts/greenline_price_filter.py
```

Prospective test: the bet ledger (`research/bankroll/scripts/greenline_bet_log.py`), week 5
on, graded at the line actually taken.
