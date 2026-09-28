# Do any of the fourteen PFF grade slopes reject zero?

**Question.** For the slopes in [pff-grade-total-residual-2026-09-22.md](pff-grade-total-residual-2026-09-22.md), which ones reject a slope of zero once seasons are the cluster and the fourteen tests are counted together?

**Method.** Same sample and same seven entering grades. The test is a wild cluster bootstrap-t with the null imposed (Cameron, Gelbach, Miller). Weights are Webb's six-point set, because both fits have fewer than ten seasons. The open fit has five seasons, so all 7,776 patterns are enumerated. The close fit has seven seasons, so the p-value is 9,999 Monte Carlo draws. Holm adjustment is across all fourteen tests. A p-value that stays large is not evidence the grade is unrelated to the residual.

**Numbers.** The smallest unadjusted p-value is run defense against the open residual: 0.035. Holm across the fourteen tests moves it to 0.50. Run defense against the close is 0.105 unadjusted and 1.00 after Holm. Every other test is larger, and every Holm p-value other than that 0.50 is 1.00. The open tests rest on five seasons, which is too few for a fine tail probability.

**What this does not support.** Treating the open run-defense interval as a result that survived the screen. A bet. A claim that the other grades are zero.

Reproduce with `python research/totals/scripts/pff_residual_screen.py`. The p-values are `p_wild` and `p_holm` in `data/exports/pff_residual_screen.csv`.
