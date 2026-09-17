# Bankroll growth by week, pooled Greenline prior only

Generated 2026-09-17 by `research/bankroll/scripts/pooled_growth_chart.py --paths 100000`.

**This chart conditions on one prior.** The unit rule is to bracket the pooled
(141–109) and 2026-only (27–22) readings; this was asked for as the pooled edge
charted on its own. The bracketed figures are in
[mc-combined-totals-2026-09-17.md](mc-combined-totals-2026-09-17.md) and
[bankroll-config-sweep-2026-09-17.md](bankroll-config-sweep-2026-09-17.md).

## Question

Starting from $20,000 before week 4, drawing the Greenline win rate from the pooled
posterior (mean 56.4%, P(below break-even) 10%), what does the bankroll path look like
week by week at three configs?

![Pooled bankroll growth](figs/pooled-bankroll-growth-2026-09-17.png)

## Numbers (100,000 paths, ρ = 0.10, over-zero at 1%)

| config | median | 5th | 25th | 75th | 95th | P(down) | busts |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.5% x 13% of flags  (recommended) | $20,721 (+3.6%) | $18,758 | $19,918 | $21,524 | $22,670 | 27.3% | 0.0% |
| 1.0% x 13% of flags | $21,306 (+6.5%) | $17,685 | $19,812 | $22,785 | $24,888 | 27.7% | 0.0% |
| 0.25% x every flag  (conditional on coverage) | $22,400 (+12.0%) | $17,597 | $20,429 | $24,323 | $27,083 | 20.6% | 0.0% |

## Reading

- Growth is linear in the median because stakes are flat off the starting bankroll.
  No compounding is modeled; simultaneous Saturday kickoffs make it unachievable.
- Doubling the stake at 13% coverage doubles the median gain and doubles the 5th
  percentile loss. P(down) does not move (27.3% → 27.7%).
- Betting every flag at a quarter stake is the only config that lowers P(down), to
  20.6%, because ~590 bets average out the draw of the win rate. That row assumes the
  56.4% applies to the 87% of flags the record never bet.

## What this does not support

- The pooled 56.4% as the true rate. It is the ceiling reading; the 2026-only prior
  gives 55.0% with a 35% chance of being below break-even.
- Any compounded or Kelly figure.
- The every-flag row as achievable without the coverage ledger confirming it.

## Data

Same inputs as `mc_combined_totals.py`: 234 over-zero walk-forward bets 2016–25,
49 graded 2026 Greenline flags, 201 personal unders 2023–25. Seed 20260917.
