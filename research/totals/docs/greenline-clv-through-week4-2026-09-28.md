# Greenline totals CLV through 2026 week 4 — the era gap no longer separates

2026-09-28

## Question

The [2026-09-23 record](greenline-clv-all-eras-2026-09-23.md) found pooled Greenline unders
beat the close, but that the eras disagreed: 2020 had no CLV, the 2026 flags about half a
point (2026 minus 2020 p 0.047), and the 2026 move held at a single book. That was two
graded weeks. Does it hold with week 4 added?

## Answer

**The pooled result holds; the era split and the half-point do not.** Pooled unders still
beat the close, +0.25 ± 0.18 pts (p 0.003, n=313). But 2026 falls from +0.50 to **+0.34**, and
2026 minus 2020 is now +0.29 ± 0.44, **p 0.195** — the eras can no longer be told apart at
this n. The single-book check survives at a smaller size: DraftKings at capture vs its own
close, unders +0.35 ± 0.26 (p 0.004, n=127). Every upper bound still sits below the 0.60 pts
that would pay for −110 on CLV alone.

Week 4 on its own: **+0.10 ± 0.24** (p 0.21, n=48). Weeks 2 and 3 re-score at +0.42 and
+0.53 on today's closes (+0.48 together, against +0.50 in the 09-23 record), so nearly all of
the drop is the new week, not re-scored closes. (First published in this record as "+0.05 by
subtraction"; replaced the same day by the direct per-week rows the script now prints.)

## Method

Unchanged from the 2026-09-23 record: each under scored at its graded capture against the
median REST-backed CFBD book close (`_source` ≠ `gql`), `span` gate (drop a game whose books
span more than 3 pts), SE the larger of iid and date-clustered. The GraphQL-only closes that
record found to be in-game totals stay excluded; that finding is not revisited here.

Two script fixes preceded this run (commit `36f34ca4`): the DraftKings same-book check had a
week→odds-snapshot map for weeks 2-3 only and skipped week 4 without saying so; week 4 now
uses `odds_americanfootball_ncaaf_20260923T180008Z.json`, the latest before the 19:49Z
capture. The "eras disagree" sentence printed regardless of p and is now conditional. The
script also prints one row per 2026 week, so a move in the 2026 row can be traced to new
data or to re-scored closes.

## Data

2020 PFF_hist, the 2022-23 exports, and 2026 Greenline flags weeks 2-4 (graded 2026-09-28
after a schedule refresh). 320 unders, 313 scored; 4 dropped for fewer than 2 books, 3 for a
book span above 3 pts.

## Numbers

| split | 2026-09-23 | 2026-09-28 |
| --- | --- | --- |
| all eras, unders | +0.29 ± 0.21, n=265, p 0.004 | +0.25 ± 0.18, n=313, p 0.003 |
| 2020 PFF_hist | +0.05 ± 0.38, n=121 | unchanged |
| 2022-23 exports | +0.46 ± 0.35, n=56 | unchanged |
| 2026 flags | +0.50 ± 0.22, n=88, 5 dates | **+0.34 ± 0.22, n=136, 8 dates** |
| 2026 minus 2020 | +0.45 ± 0.44, p 0.047 | **+0.29 ± 0.44, p 0.195** |
| DraftKings same-book, all flags | +0.51 ± 0.21, n=97, 5 dates | +0.29 ± 0.28, n=154, 8 dates, p 0.024 |
| DraftKings same-book, unders | +0.55 ± 0.23, n=80 | +0.35 ± 0.26, n=127, p 0.004 |
| DraftKings, PFF's number = DK's | +0.46 ± 0.22, n=84 | +0.25 ± 0.29, n=134, p 0.047 |

Upper 95% against the 0.60 break-even: pooled +0.44, 2026 +0.57 — both below.

## What this does not support

- **Not that the eras agree.** p 0.195 is a failure to separate them; the point estimates
  (+0.05 vs +0.34) still differ, and the test's resolution is ±0.44 pts.
- **Not a trend.** Week 4's +0.10 ± 0.24 overlaps week 2's +0.42 ± 0.39; at n≈45 per week,
  three weeks cannot distinguish decay from variance.
- **Not a bet on CLV.** No row's upper bound reaches 0.60 pts.
- **Not a Pinnacle result.** The Pinnacle-gated 2026 close remains contaminated by GraphQL rows.

## Reproduce

```
python research/totals/scripts/grade_greenline.py --week 2 --week 3 --week 4
python research/totals/scripts/greenline_clv_all_eras.py
```
