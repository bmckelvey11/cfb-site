# How much edge does PFF's total projection carry?

2026-09-28

## Question

PFF publishes its own projected total (the **PFF projection**) beside the market total it
displays (the **PFF market line**). How much does the projection know that the line does
not — in points per game, and in win probability against the −110 break-even?

## Answer

**About the vig, and a bound rather than a measurement.**

- **Pooled (2020 plus 2026 weeks 2-3, 516 games):** 63% of PFF's disagreement with the line
  turns out real (b = 0.63, 95% CI −0.72 to +1.98). PFF sits 0.89 points off the line on
  average, so the point estimate is worth about **0.56 points, or 2.2 percentage points of win
  probability, per game** — against the 2.38 points −110 needs. The upper bound is 1.76
  points, 7.0 pp. Zero cannot be excluded.
- **2020 alone (410 games):** b = 0.42 (−1.34 to +2.17); the projection's side of the line went
  209-189 (52.5%), and PFF's under probabilities score *worse* than 0.5 at the line (Brier
  0.2529 vs 0.2500).
- **2026 weeks 2-3 alone (106 games):** b = 2.95 (+0.43 to +5.47) and a Brier of 0.2467 — the
  one sample where PFF looks strong. Discount it: it sits on 5 slate dates (the cluster SE is
  unreliable at that count), a b near 3 would mean the market under-reacts to PFF threefold,
  it is the sample the Greenline enthusiasm was built on, and it differs from 2020 at p 0.106.
- **2026 level:** PFF shaded the market line down by 0.92 points on average across weeks 2-4,
  while the games landed 0.52 above it. The average shade pointed the wrong way.

## Method

Registered in `pff_projection_skill.py`'s docstring and committed (`b84b8818`) before any
output was printed.

- **Slope.** `(actual − line) = a + b·(projection − line)` with an intercept, SEs clustered
  by game date and never allowed below iid. b is the share of PFF's disagreement with the
  line that turns out real: 0 means the projection adds nothing, 1 means PFF was fully right.
  Converted to points per game as b times the mean absolute disagreement, and to win
  probability at 4 pp per point.
- **Level**, kept apart from the slope: the mean of (projection − line) against the mean of
  (actual − line). A systematic shade that games do not follow is bias, not information.
- **Proper score:** Brier and log loss of PFF's under probability at the line
  (`match_greenline_books.p_under`) against 0.5, the de-vigged probability of a two-sided
  −110 market at its own line.
- **Line and projection are taken at the same moment:** 2020 from the `open_greenline`
  snapshot (the close snapshot's projection was updated after the market moved); 2026 from
  each week's capture.

## Data

- **2020:** `greenline_history_archive.csv`, PFF_hist totals, 410 games, one row per game (the
  archive is two-sided and is deduplicated by game_id), 57 game dates; 4 dropped for a
  missing value.
- **2026:** `greenline_graded.csv`, every Greenline totals flag. Level and MAE use weeks 2-4
  (164 games, 8 dates). The slope and the proper score use weeks 2-3 only (106): a fit on
  the size of PFF's disagreement is the continuous form of a win/loss-by-`value` split, and
  week 4 onward is open question C's embargo window.

## Numbers

| sample | n | dates | b | 95% CI | edge at the point estimate, pts / pp | upper-bound edge, pts / pp |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 2020 | 410 | 57 | +0.42 | −1.34 to +2.17 | 0.32 / 1.3 | 1.64 / 6.6 |
| 2026 weeks 2-3 | 106 | 5 | +2.95 | +0.43 to +5.47 | 4.13 / 16.5 | 7.66 / 30.6 |
| **pooled** | **516** | **62** | **+0.63** | **−0.72 to +1.98** | **0.56 / 2.2** | **1.76 / 7.0** |

| era | PFF shade (proj − line) | games landed (actual − line) | MAE proj | MAE line | W-L, projection's side | Brier PFF / market |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 2020 | +0.27 | +0.20 ± 1.66 | 13.54 | 13.53 | 209-189 (52.5%) | 0.2529 / 0.2500 |
| 2026 | −0.92 | +0.52 ± 2.29 | 11.65 | 11.71 | 85-79 (51.8%) | 0.2467 / 0.2500 (weeks 2-3) |

Pre-outcome power: the smallest b a 5% test could detect 80% of the time was 1.44 in 2020,
3.14 in 2026 weeks 2-3 and 1.23 pooled, computed from the spread of (projection − line)
alone. As stated before running, this sample cannot tell b = 0 from b = 1.

Already on record and not re-derived here: 2026 calibration (stated 55.0% vs actual 51.8%;
`greenline_season_review.py`) and the pooled betting record (`pool_totals_record.py`).

## What this does not support

- **Not that PFF's projection is worthless.** The pooled interval runs to 1.98, and the point
  estimate is positive.
- **Not that it beats −110 by itself.** The point estimate is worth 2.2 pp against 2.38 needed;
  the records (52.5%, 51.8%) agree. Any profit has to come from the price — a better number
  than PFF's market line — which is what the week-5 bet rule is built on.
- **Not the 2026 weeks 2-3 slope.** Five dates, an implausible b, and the discovery sample.
- **Not a statement about week 4 onward's slope.** Deliberately unfit until question C is read.

## Reproduce

```
python research/totals/scripts/pff_projection_skill.py
```
