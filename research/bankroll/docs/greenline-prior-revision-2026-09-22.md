# The Greenline planning prior has never seen the Greenline history — and the unit is too big

2026-09-22

## Recommendation

**Cut the Greenline unit from 1% to 0.6% of bankroll, and change the planning prior's
Greenline leg from 146-113 to 146-124.**

The reason is not a new opinion about Greenline. It is that the prior the unit is derived
from is built on 259 picks of which **201 are our own bets** and only 58 are vendor flags —
and there are 212 pure Greenline picks from 2020 and 2022-23 that the bankroll model has
never been given. Pooled, the vendor's own totals record across every era we have graded is
**54.1% on 270 unders**, not the 56.4% the current prior carries.

Under the unit rule this tree already uses — the smaller of quarter Kelly and the largest
unit under a 3% per-season chance of a 25% loss — that moves the binding constraint:

| prior | what it is | n | mean | quarter Kelly (9 simultaneous) | largest unit under the 3% cap |
| --- | --- | ---: | ---: | ---: | ---: |
| `n58` | the 2026 published under list | 58 | 55.1% | 0.94% | — |
| `pooled` *(current)* | that list + the 2023-25 personal unders | 259 | 56.4% | 1.38% | ~1.3% |
| `k0.5` *(planning)* | the same at κ=0.5 | 150 eff. | 56.1% | 1.30% | 1% (live) |
| **`gl-history`** *(proposed)* | **every graded Greenline under, all three eras** | **270** | **54.1%** | **0.59%** | ~1.2% |

Today the cap binds at 1%. Under `gl-history` **quarter Kelly binds first, at 0.59%**.

**The Kelly figure is evaluated at the posterior mean, and that is correct rather than
convenient.** Expected log growth for a single staked fraction is
`E[p]·log(1+bf) + (1−E[p])·log(1−f)` — linear in `p` — so the Bayesian answer for one
fraction under an uncertain rate *is* Kelly at the posterior mean, not something shrunk
below it. Averaging `kelly_unit` over 40,000 draws from `Beta(146.5, 124.5)` instead returns
0.77%, i.e. *higher*, but only because `kelly_unit` clips at zero: that average quietly
assumes you could stand down on the paths where the true rate is a loser. You cannot observe
which path you are on, so 0.59% is the number.

## Why this prior and not the current one

The current `pooled` prior is `n58` (32-26) plus the 2023-25 personal unders (114-87). Both
components are downstream of our own selection: 58 picks are the *published* under list —
PFF's board after a positive-edge filter and a value ranking — and 201 are bets we chose to
place. `mc_combined_totals.py` already says so in its own comment ("never independent
confirmation").

`gl-history` is 146-124 over 270 picks, and **212 of them predate any bet of ours**. Nothing
in that 212 was filtered by which flags we took, which list we published, or which number we
could get. It is the only Greenline prior available that is purely the vendor's own board.
Its composition and grading are in
[`greenline-totals-pooled-2026-09-22.md`](../../totals/docs/greenline-totals-pooled-2026-09-22.md);
the coverage audit there confirms it is every graded Greenline total in existence.

Two further reasons to prefer it over the κ=0.5 compromise:

- **κ=0.5 was a guess; the overlap is now measured.** Half-pooling the personal unders
  assumed they were "mostly the same Greenline flags". On the only days where a Greenline
  board and a book bet both exist, they are 7 of 12 the same pick, **3 of 12 the opposite
  side**, and 2 games Greenline never flagged. Partly the same signal, partly a different
  selector. That is an argument for keeping them *out* of the prior that sizes Greenline
  bets, not for weighting them at a half.
- **No filter justifies the narrower population.** The current plan bets 6-12 published
  unders a week, and the published list is PFF's board ranked by `value`. A full search over
  edge thresholds and totals bands
  ([`greenline-totals-rule-search-2026-09-22.md`](../../totals/docs/greenline-totals-rule-search-2026-09-22.md))
  finds no rule that survives: the best cell is matched by a within-era shuffle 54.7% of the
  time and nothing survives Holm. So the narrower list has no demonstrated advantage over
  the board it is drawn from — which means the board's rate, not the list's, is the honest
  input.

## What the change costs and buys

`mc_combined_totals.py`, 40,000 paths, weeks 4-15 of 2026, $20,000, over-zero leg unchanged.

| unit | prior | median end | P(end below start) | P(−25%) | P(+25%) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1.0% | `pooled` (current) | $21,699 (+8.5%) | 27.7% | 0.4% | 14.5% |
| 1.0% | `gl-history` | $20,736 (+3.7%) | 39.7% | 1.0% | 8.2% |
| **0.6%** | **`gl-history`** | **$20,527 (+2.6%)** | **38.0%** | **0.0%** | **0.9%** |
| 1.3% | `gl-history` | $20,861 (+4.3%) | 40.8% | **3.4%** | 14.9% |

Two things to read off it. First, **most of the drop is the prior, not the unit**: going
from `pooled` to `gl-history` at an unchanged 1% costs 4.8 points of median outcome and adds
12 points to the chance of finishing down. That is the correction, and it happens whether or
not the unit moves. Second, the 1.3% row is why the unit has to move too — under the honest
prior, 1.3% breaches the 3% drawdown cap this tree set for itself.

The probability that the *drawn* Greenline win rate sits below break-even rises from **10% to
29%** when the prior is swapped. That number is the whole argument in one figure — but read
it as a property of the prior, not a forecast: it is how much of the posterior lies below
52.38%, not the chance this season loses money. The season-level figure is the `P(end below
start)` column, and that one includes the over-zero leg.

## What this does not say

- **Not that Greenline is a loser.** 54.1% on 270 picks with a 48.1-59.9 interval is
  consistent with a real edge, with break-even, and with a small loss. The posterior still
  puts 71% on the true rate beating break-even.
- **Not that the projection was wrong.** It was right conditional on its prior. The prior
  was built from what had been graded at the time; 212 more picks have been graded since.
- **Not a case for standing down.** At 0.6% the median season is still positive and the
  chance of a 25% loss is ~0. The recommendation is to bet smaller, not to stop.
- **Not an argument that will resolve.** Clearing a 54% true rate against a 52.38%
  break-even needs roughly **5,900 graded picks** — eight-plus seasons at this board's
  volume. Waiting for significance is not a strategy; sizing for uncertainty is.
- **Nothing about the over-zero leg**, which is unchanged in every row above.

## Reproduce

```bash
python research/bankroll/scripts/mc_combined_totals.py --gl-prior gl-history --gl-unit 0.006
```

`gl-history` was added to `GL_PRIORS` in `mc_combined_totals.py` with its provenance in a
comment beside it. Nothing else in the bankroll tree changed: the planning prior, the
recommended unit in
[`seed-bankroll-proposal-2026-09-21.md`](seed-bankroll-proposal-2026-09-21.md) and every
dated record still say what they said. **This doc is a recommendation to change them, not the
change.** Adopting it means re-running `bankroll_config_sweep.py` with `gl-history` in its
`PRIORS` tuple and reissuing the proposal on the new unit. That tuple is hardcoded and the
sweep's `self_check()` asserts `len(rows) == len(PRIORS) * len(COVERAGES) * len(GL_UNITS)`,
so a fourth prior needs both the tuple and that row count updated in the same edit.

Every number here is the **unders-only** prior, 146-124 over 270 picks. The pooled doc's
headline 324 is the all-sides board; this tree bets unders, so the unders figure is the one
that belongs in a staking prior. Do not read the two as the same number.
