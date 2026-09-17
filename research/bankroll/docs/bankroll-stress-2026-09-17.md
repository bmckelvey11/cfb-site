# Stress test: does 0.5% survive a more skeptical uncertainty model?

Completed 2026-09-17, answering the outside review of
[mc-method-2026-09-17.md](mc-method-2026-09-17.md). Reproduce with
`python research/bankroll/scripts/bankroll_stress.py --paths 50000 --out research/bankroll/docs`
(`--self-check` pins the κ endpoints, the penalty direction, and the widened haircut).
Full table: [bankroll-stress-table-2026-09-17.md](bankroll-stress-table-2026-09-17.md).

## Question

The recommendation is Greenline 0.5% of bankroll per bet, over-zero 1%, re-sized
weekly, 6–12 unders a week. It passes P(−25%) ≤ 1% with no busts under both the
pooled and n49 priors. The review's point: those two priors, a deterministic
over-zero haircut, a volume that is a plan rather than evidence, and an assumed
ρ = 0.10 are each places the uncertainty model may be too confident. Does 0.5% still
pass when each of them, and all of them together, is made more skeptical? Does 1%?

## What was changed

Five knobs added to `mc_combined_totals.simulate`, all default-off so the base model
reproduces bit for bit:

| knob | what it does | review item |
|---|---|---|
| `oz_center` | moves the post-haircut over-zero mean (base 58.2%, stress 56.5%) | 1 |
| `oz_extra_sd` | adds N(0, sd) to each path's haircut so the selection correction is itself uncertain (stress 3–4 pts) | 1 |
| `gl_kappa` | discounted-history prior Beta(27.5 + κ·114, 22.5 + κ·87); κ = 0 is n49, κ = 1 is pooled | 2 |
| `gl_marginal_penalty` | Greenline bets beyond 6 a week win at p − d (stress 1–3 pts) | 3, 4 |
| `rho` (existing) | latent same-slate correlation, 0 to 0.5 | 5 |

Three combined cases stack them. Path-dependent measures added to every run:
maximum drawdown from the running peak, weeks ending below the start, expected
shortfall at 5% (mean of the worst 5% of endings). Busts are now reported as counts.

## Results

50,000 paths per cell, seed 20260917, both units.

**0.5%: passes 25 of 25.** **1%: passes 12 of 25.**

Selected rows (full table linked above):

| scenario | unit | median | 5th | ES5 | P(down) | P(−25%) | maxDD med / 95th | P(DD>20%) | passes |
|---|---:|---:|---:|---:|---:|---|---|---:|:---:|
| base, pooled | 0.5% | $20,945 | $18,598 | $18,039 | 26.0% | 0 / 50,000 | $794 / $1,996 | 0.0% | yes |
| base, n49 | 0.5% | $20,673 | $17,600 | $16,905 | 36.9% | 23 / 50,000 (0.05%) | $876 / $2,671 | 0.5% | yes |
| κ = 0.5 | 0.5% | $20,908 | $18,404 | $17,820 | 28.4% | 1 / 50,000 | $808 / $2,110 | 0.0% | yes |
| bets 7–12 at p−3pt, pooled | 0.5% | $20,741 | $18,428 | $17,865 | 30.5% | 0 / 50,000 | $846 / $2,108 | 0.0% | yes |
| ρ = 0.50, n49 | 0.5% | $20,658 | $17,085 | $16,321 | 38.9% | 116 / 50,000 (0.23%) | $1,308 / $3,381 | 2.0% | yes |
| combined: κ 0.5, p−2, oz 56.5%+sd3, ρ 0.2 | 0.5% | $20,702 | $18,040 | $17,426 | 33.8% | 3 / 50,000 | $970 / $2,458 | 0.2% | yes |
| **worst: κ 0, p−3, oz 56.5%+sd4, ρ 0.5** | **0.5%** | **$20,368** | **$16,865** | **$16,104** | **43.8%** | **164 / 50,000 (0.33%)** | **$1,397 / $3,565** | **2.7%** | **yes** |
| base, pooled | 1.0% | $21,714 | $17,296 | $16,310 | 27.3% | 221 / 50,000 (0.44%) | $1,571 / $3,795 | 3.9% | yes |
| base, n49 | 1.0% | $21,157 | $15,432 | $14,283 | 38.5% | 1,813 / 50,000 (3.63%) | $1,734 / $5,034 | 11.4% | no |
| κ = 0.25 | 1.0% | $21,503 | $16,511 | $15,458 | 32.6% | 637 / 50,000 (1.27%) | $1,636 / $4,255 | 6.5% | no |
| ρ = 0.35, pooled | 1.0% | $21,629 | $16,200 | $15,062 | 32.6% | 936 / 50,000 (1.87%) | $2,298 / $5,156 | 14.6% | no |
| worst | 1.0% | $20,503 | $13,942 | $12,702 | 45.8% | 4,581 / 50,000 (9.16%) | $3,038 / $6,962 | 32.1% | no |

## Reading

1. **0.5% is robust to every skeptical setting tried, including all of them at
   once.** In the worst combined case the median gain drops to +1.8%, P(down) rises
   to 44%, and 0.33% of paths end down 25%. Still inside the limit, no busts, and the
   95th-percentile drawdown is $3,565 on $20,000.
2. **1% is not.** It fails under the n49 prior alone, under κ ≤ 0.25, under ρ ≥ 0.35
   with the pooled prior, under ρ ≥ 0.2 with n49, and under every combined case.
   Where it passes, it passes on the pooled prior with modest stress. The upgrade to
   1% therefore needs the 2026 flags to carry the prior on their own, not more
   sensitivity runs.
3. **Which knob bites.** Ranked by how much it moves P(−25%) at 1%: ρ (0.44% → 3.2%
   from 0.10 to 0.50 under pooled), then the prior (0.44% → 3.6% from pooled to
   n49), then the marginal penalty (0.44% → 0.67% at 3 pts), then the over-zero
   haircut (0.44% → 0.47%; the leg is ~11 bets). At 0.5% none of them cross 0.35%.
4. **Over-zero uncertainty is nearly irrelevant to the decision.** Centering it at
   56.5% with a 4-point uncertain haircut moves the 0.5% median by $65 and P(−25%)
   by 0.00 points. The review's concern is right in principle and immaterial here
   because the leg is small for the rest of 2026. It will matter for a 2027
   projection.
5. **Drawdown is the number the fan chart hides.** At 0.5% under the base pooled
   prior, a 10% drawdown happens on 5% of paths and the median season spends two
   weeks below the start. Under n49, 13% and three weeks. At 1% under n49, a 10%
   drawdown happens on 43% of paths and a 20% drawdown on 11%.
6. **"0 busts" means 0 of 50,000.** Rule-of-three upper bound ≈ 0.006% under the
   model. The constraint's other half, P(−25%) ≤ 1%, has a binomial standard error of
   about 0.045 points at the boundary, so rows quoted at 0.86% and 1.27% (1% unit,
   ρ = 0.20 pooled and κ = 0.25) are one to six standard errors from the line, not
   ties.

## Kelly comparison

Asked after the review: does quarter Kelly agree with 0.5%? No. It is two to four
times larger and fails the stated tolerance.

Single-bet Kelly at −110: `f* = (p·b − (1−p)) / b`. Quarter of that, then a
simultaneous-bets adjustment `f / (1 + (n−1)·ρ_outcome)` for 9 bets at outcome
correlation ≈ 0.063.

| prior | full Kelly | quarter | quarter, 9 simultaneous | P(−25%) at that unit |
|---|---:|---:|---:|---:|
| pooled (56.4%) | 8.4% | 2.1% | 1.4% | 6.7% / 2.0% |
| n49 (55.0%) | 5.5% | 1.4% | 0.9% | 9.1% / ~2% |

Growth-optimal unit under the full simulator (max E[log(final/start)], 20k paths,
both legs, correlation and parameter uncertainty included): ≈ 4% under pooled,
≈ 3% under n49, with P(−25%) of 18% and 25% respectively. 0.5% is roughly
one-eighth Kelly under pooled and one-sixth under n49.

| unit | E[log growth] pooled / n49 | P(−25%) pooled / n49 | max drawdown 95th pooled / n49 |
|---:|---|---|---|
| 0.5% | +0.046 / +0.031 | 0.00% / 0.04% | $1,976 / $2,687 |
| 1.0% | +0.082 / +0.052 | 0.39% / 3.67% | $3,782 / $5,057 |
| 1.4% | +0.107 / +0.065 | 2.0% / 9.1% | $5,244 / $6,869 |
| 2.1% | +0.146 / +0.082 | 6.7% / 17.2% | $7,856 / $9,728 |
| 3.0% | +0.186 / +0.093 | 12.4% / 24.7% | $11,331 / $13,120 |

Reading: quarter Kelly maximizes growth under a tolerance the proposal does not
have. The proposal's rule is a 1% chance of losing a quarter of the money, under
the pessimistic prior; that binds at about 0.75% under n49 and 1% under pooled.
Kelly-fractional sizing would be the right frame for a bankroll that is meant to be
grown across seasons; for a gift being defended over twelve weeks, the drawdown
tolerance is the binding constraint and 0.5% is where it lands.

## What this does not support

- **Any of the skeptical settings as the true model.** They are stress cases. κ, the
  marginal penalty, and ρ above 0.10 are unmeasured; the point is that the decision
  does not depend on them.
- **1% as an eventual choice.** It fails the stated tolerance under the 2026-only
  prior and only that prior will grow. Whether it passes later depends on what the
  2026 flags do.
- **The negative cross-leg correlation as favorable.** The shared shock still has one
  sign (scoring environment). A common model-or-market-failure factor that hurts both
  legs together is not modeled. With ~11 over-zero bets it cannot change the 2026
  answer; it should exist before a 2027 projection.
- **Score-stratified edge.** Every Greenline bet still has the same p. The marginal
  penalty is a proxy for the review's "bets 7–12 are weaker" concern, not a model of
  which flags are strong.

## Review items and their disposition

| # | review item | done here | deferred |
|---|---|---|---|
| 1 | uncertain over-zero haircut | `oz_center`, `oz_extra_sd` | logit-normal δ; immaterial at 11 bets |
| 2 | partial pooling of the Greenline prior | κ continuum 0–1 | hierarchical logit model with group effects |
| 3 | score/edge stratification | marginal-bet penalty as proxy | regression on signal strength, total, era; needs graded 2026 flags with PFF value |
| 4 | volume tied to edge | same proxy | volume–quality dependence; needs the bet ledger |
| 5 | ρ grid and a second factor | ρ ∈ {0, .05, .1, .2, .35, .5} | common market-failure factor; date buckets |
| 6 | "zero bust" wording | counts everywhere; rule-of-three noted | |
| 7 | drawdown, time under water, ES | all three reported | recovery probability after −10% / −20% |
| — | 107.3 vs 107.1 | reviewer arithmetic: (6+7+8+9+9+9+9)/7 = 8.14, so 107.1 stands | |
| — | stake notation, 58.2% provenance, Poisson mixture, correlation approximation label | fixed in the method doc | |
| — | pre-specified updating rule | added to the proposal §8 | |
| — | freeze data and dependency versions | seed, slate query date and script versions are stated; a lockfile is not | pin with `pip freeze` at decision time |

## Data and dates

Same inputs as `mc_combined_totals.py`: 234 over-zero walk-forward bets 2016–25, 49
graded 2026 Greenline flags, 201 personal unders 2023–25, FBS-vs-FBS slate weeks 4–15
from `core.fact_game` (weeks 14–15 from 2025). 26 scenarios × 2 units × 50,000 paths.
Seed 20260917.
