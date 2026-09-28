# Under list and stated edge against CLV, 2026-09-28

Reproduce: `python research/totals/scripts/greenline_flag_clv_contrast.py --out research/totals/docs`.

## Question

Within the Greenline board, does the *published under list* or the *size of PFF's stated
edge* predict closing-line value? These are the two variables that vary inside the board,
which the flag dummy in [line movement](pff-line-movement-2026-09-22.md) did not.

## The answer is a bound, not a result

- 106 flags (weeks 2, 3) with a REST-backed close. CLV SD 1.04 points, mean +0.458.
- Smallest effect this n detects 80% of the time: **0.56 points** for the list contrast, **0.28 points per SD** for the edge slope.
- A quarter-point effect — the size found on the close in the line-movement record — would need **135 flags**, about 1 more week(s) of flags at ~50 gradeable a week.
- Worse, the flags sit on **5 slate dates**, 54 of them on one. So few
  effective clusters supports neither a cluster-robust SE nor a wild bootstrap, so the
  intervals below are iid and optimistic. The sensitivity table says by how much.

## Estimates

| contrast | n | estimate | 95% CI (iid) | p | Holm p | MDE |
|---|---:|---:|---|---:|---:|---:|
| on the under list vs not | 58 vs 48 | -0.011 pts | -0.40 to +0.38 | 0.956 | 1.000 | 0.56 |
| CLV per SD of `value` | 106 | +0.046 pts | -0.15 to +0.24 | 0.650 | 1.000 | 0.28 |

(`value` SD is 0.0186, so a one-SD move is about 1.9 points of stated win probability.)

## What slate clustering would do to those intervals

Kish design effect at this concentration, applied to the interval half-width.

| assumed slate ICC | design effect | list-contrast MDE | edge-slope MDE |
|---:|---:|---:|---:|
| 0.02 | 1.95 | 0.78 | 0.40 |
| 0.05 | 3.37 | 1.02 | 0.52 |
| 0.10 | 5.74 | 1.34 | 0.68 |

## Coupling sensitivity and the exploratory price-rule fit

Same CLV sign, but measured from the median capture total of odds-api books other than
DraftKings and FanDuel, so the PFF market line (x's reference) is not also y's. Reported,
not tested; the exploratory row is outside the Holm family.

| fit | n | estimate | 95% CI (iid) | p | Holm p | MDE |
|---|---:|---:|---|---:|---:|---:|
| list contrast, decoupled y | 58 vs 48 | +0.093 pts | -0.29 to +0.47 | 0.632 | not in family | 0.54 |
| CLV per SD of `value`, decoupled y | 106 | +0.090 pts | -0.10 to +0.28 | 0.361 | not in family | 0.28 |
| exploratory: per SD of best DK/FD total − PFF projection | 80 | +0.206 pts | -0.03 to +0.44 | 0.086 | not in family | 0.34 |

## Reading

- Neither registered contrast survives Holm. **This is a bound on the question, not an answer to it**: an effect inside the MDE column could not have been seen.
- The bound rules out large effects: a list that moved the close by more than about 0.6 points, or an edge slope above 0.3 points per SD, would have shown up.
- Point estimates: list -0.01, edge slope +0.05 (coupled) vs +0.09 (decoupled). A slope that shrinks on the decoupled y was partly the shared market line.
- **The next look is at ~135 scored flags** (the stop rule, recomputed on this close's SD). Nothing is to be read before it.

## What this does not support

- Any claim about win rate. This is a movement test; open question C owns the `value`
  win-rate question and is embargoed until 56 prospective picks have graded.
- Reading either null as evidence of absence. See the MDE column.
- A third contrast on this sample. The budget was two looks.
- Weekly re-looks. The stop rule is ~135 scored flags (first set at ~596 on the
  contaminated close's SD). The slate-date count, not n, is what stays binding: a
  handful of Saturdays cannot support a clustered interval at any flag count.

