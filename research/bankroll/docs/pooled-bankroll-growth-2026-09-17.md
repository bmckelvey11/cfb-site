# Bankroll growth by week, pooled Greenline prior only

Generated 2026-09-17 by `research/bankroll/scripts/pooled_growth_chart.py --paths 100000 --flat-stakes`.

**This chart conditions on one prior.** The unit rule is to bracket the pooled
(141–109) and 2026-only (27–22) readings; this was asked for as the pooled edge
charted on its own. The bracketed figures are in
[mc-combined-totals-2026-09-17.md](mc-combined-totals-2026-09-17.md) and
[bankroll-config-sweep-2026-09-17.md](bankroll-config-sweep-2026-09-17.md).

## Question

Starting from $20,000 before week 4, drawing the Greenline win rate from the pooled
posterior (mean 56.4%, P(below break-even) 10%), betting 6–12 unders a week with units
re-sized off the bankroll each Monday, what does the bankroll path look like week by
week at three unit sizes? And does re-sizing matter against flat stakes?

![Pooled bankroll growth](figs/pooled-bankroll-growth-2026-09-17.png)

## Numbers (100,000 paths, ρ = 0.10, over-zero at 1%)

Top row of the figure: units re-sized off the bankroll at the start of each week (the
simulator's default). Bottom row: flat units off the starting $20,000 (`--flat-stakes`).
Within a week stakes are flat either way, because Saturday kickoffs are simultaneous.
Greenline volume is 6–12 unders a week, uniform, capped by the FBS-vs-FBS slate
(~107 bets over weeks 4–15).

| config | staking | median | 5th | 25th | 75th | 95th | P(down) | busts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.5% unit, 6-12 unders/wk | weekly re-size | $20,945 (+4.7%) | $18,586 | $19,947 | $21,981 | $23,568 | 26.2% | 0.0% |
| 1.0% unit, 6-12 unders/wk | weekly re-size | $21,718 (+8.6%) | $17,280 | $19,782 | $23,818 | $27,141 | 27.6% | 0.0% |
| 1.5% unit, 6-12 unders/wk | weekly re-size | $22,444 (+12.2%) | $15,928 | $19,513 | $25,740 | $31,200 | 28.8% | 0.0% |
| 0.5% unit, 6-12 unders/wk | flat | $20,964 (+4.8%) | $18,579 | $19,985 | $21,933 | $23,342 | 25.3% | 0.0% |
| 1.0% unit, 6-12 unders/wk | flat | $21,788 (+8.9%) | $17,236 | $19,918 | $23,648 | $26,303 | 25.9% | 0.0% |
| 1.5% unit, 6-12 unders/wk | flat | $22,615 (+13.1%) | $15,806 | $19,815 | $25,382 | $29,333 | 26.4% | 0.0% |

## Reading

- The median grows close to a straight line either way. A 5–13% seasonal edge has
  almost nothing to compound over twelve weeks.
- **Weekly re-sizing changes almost nothing.** Median moves by −$20 to −$170
  (volatility drag on a small edge), the 95th percentile rises by $230 to $1,870,
  the 5th percentile is unchanged within $130, and P(down) rises one to two points
  because losing paths shrink their units and recover more slowly. It would matter
  across seasons, not within one.
- Doubling the unit doubles both the median gain and the 5th-percentile loss.
  P(down) barely moves. There is no free unit size.
- 1.5% is shown for the shape only. It fails the proposal's risk limit under the
  2026-only prior (P(−25%) 10.4%, sweep doc).

## What this does not support

- The pooled 56.4% as the true rate. It is the ceiling reading; the 2026-only prior
  gives 55.0% with a 35% chance of being below break-even.
- 6–12 a week as the population the record measures. Mean 9 is ~16% of a typical
  slate against the 13% the 201-bet record was earned at.
- Any per-bet compounding or Kelly figure.

## Data

Same inputs as `mc_combined_totals.py`: 234 over-zero walk-forward bets 2016–25,
49 graded 2026 Greenline flags, 201 personal unders 2023–25; FBS-vs-FBS slate per
week from `core.fact_game` (weeks 14–15 from 2025). Seed 20260917.
