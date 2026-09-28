# Under list and stated edge against CLV, 2026-09-28

Reproduce: `python research/totals/scripts/greenline_flag_clv_contrast.py --weeks 2,3,4 --out research/totals/docs`.

## Question

Within the Greenline board, does the *published under list* or the *size of PFF's stated
edge* predict closing-line value? These are the two variables that vary inside the board,
which the flag dummy in [line movement](pff-line-movement-2026-09-22.md) did not.

## The answer is a bound, not a result

- 164 flags (weeks 2, 3, 4) with a REST-backed close. CLV SD 1.03 points, mean +0.293.
- Smallest effect this n detects 80% of the time: **0.47 points** for the list contrast, **0.23 points per SD** for the edge slope.
- A quarter-point effect — the size found on the close in the line-movement record — would need **133 flags** -- fewer than this sample holds.
- Worse, the flags sit on **8 slate dates**, 54 of them on one. So few
  effective clusters supports neither a cluster-robust SE nor a wild bootstrap, so the
  intervals below are iid and optimistic. The sensitivity table says by how much.

## Estimates

| contrast | n | estimate | 95% CI (iid) | p | Holm p | MDE |
|---|---:|---:|---|---:|---:|---:|
| on the under list vs not | 105 vs 59 | -0.026 pts | -0.35 to +0.30 | 0.876 | 0.876 | 0.47 |
| CLV per SD of `value` | 164 | +0.079 pts | -0.08 to +0.24 | 0.325 | 0.649 | 0.23 |

(`value` SD is 0.0196, so a one-SD move is about 2.0 points of stated win probability.)

## What slate clustering would do to those intervals

Kish design effect at this concentration, applied to the interval half-width.

| assumed slate ICC | design effect | list-contrast MDE | edge-slope MDE |
|---:|---:|---:|---:|
| 0.02 | 1.95 | 0.65 | 0.32 |
| 0.05 | 3.38 | 0.86 | 0.41 |
| 0.10 | 5.75 | 1.12 | 0.54 |

## Coupling sensitivity and the exploratory price-rule fit

Same CLV sign, but measured from the median capture total of odds-api books other than
DraftKings and FanDuel, so the PFF market line (x's reference) is not also y's. Reported,
not tested; the exploratory row is outside the Holm family.

| fit | n | estimate | 95% CI (iid) | p | Holm p | MDE |
|---|---:|---:|---|---:|---:|---:|
| list contrast, decoupled y | 105 vs 59 | +0.033 pts | -0.29 to +0.35 | 0.840 | not in family | 0.46 |
| CLV per SD of `value`, decoupled y | 164 | +0.113 pts | -0.04 to +0.27 | 0.153 | not in family | 0.22 |
| exploratory: per SD of best DK/FD total − PFF projection | 126 | +0.135 pts | -0.04 to +0.31 | 0.136 | not in family | 0.25 |
| exploratory, out of sample (week 4 only) | 46 | +0.032 pts | -0.21 to +0.28 | 0.797 | not in family | 0.35 |

## Reading

- Neither registered contrast survives Holm. **This is a bound on the question, not an answer to it**: an effect inside the MDE column could not have been seen.
- The bound rules out large effects: a list that moved the close by more than about 0.5 points, or an edge slope above 0.2 points per SD, would have shown up.
- Point estimates: list -0.03, edge slope +0.08 (coupled) vs +0.11 (decoupled). A slope that shrinks on the decoupled y was partly the shared market line.
- **This is the scheduled look** (164 flags against a ~133-flag stop rule). It is the second look at the same contrasts: a p that clears 0.05 here alone is not a finding.

## What this does not support

- Any claim about win rate. This is a movement test; open question C owns the `value`
  win-rate question and is embargoed until 56 prospective picks have graded.
- Reading either null as evidence of absence. See the MDE column.
- A third contrast on this sample. The budget was two looks.
- Weekly re-looks. The stop rule is ~133 scored flags (first set at ~596 on the
  contaminated close's SD). The slate-date count, not n, is what stays binding: a
  handful of Saturdays cannot support a clustered interval at any flag count.

