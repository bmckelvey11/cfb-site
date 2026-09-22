# Under list and stated edge against CLV, 2026-09-22

Reproduce: `python research/totals/scripts/greenline_flag_clv_contrast.py --out research/totals/docs`.

## Question

Within the Greenline board, does the *published under list* or the *size of PFF's stated
edge* predict closing-line value? These are the two variables that vary inside the board,
which the flag dummy in [line movement](pff-line-movement-2026-09-22.md) did not.

## The answer is a bound, not a result

- 79 flags with a close surviving `usable_close()`. CLV SD 2.18 points, mean +0.057.
- Smallest effect this n detects 80% of the time: **1.46 points** for the list contrast, **0.69 points per SD** for the edge slope.
- A quarter-point effect — the size found on the close in the line-movement record — would need **595 flags**, about twelve more weeks at this board's volume.
- Worse, the flags sit on **4 slate dates**, 54 of them on one. Two
  effective clusters supports neither a cluster-robust SE nor a wild bootstrap, so the
  intervals below are iid and optimistic. The sensitivity table says by how much.

## Estimates

| contrast | n | estimate | 95% CI (iid) | p | Holm p | MDE |
|---|---:|---:|---|---:|---:|---:|
| on the under list vs not | 36 vs 43 | -0.360 pts | -1.38 to +0.66 | 0.489 | 0.978 | 1.46 |
| CLV per SD of `value` | 79 | -0.034 pts | -0.52 to +0.45 | 0.893 | 0.978 | 0.69 |

(`value` SD is 0.0178, so a one-SD move is about 1.8 points of stated win probability.)

## What slate clustering would do to those intervals

Kish design effect at this concentration, applied to the interval half-width.

| assumed slate ICC | design effect | list-contrast MDE | edge-slope MDE |
|---:|---:|---:|---:|
| 0.02 | 1.84 | 1.98 | 0.94 |
| 0.05 | 3.11 | 2.57 | 1.22 |
| 0.10 | 5.21 | 3.32 | 1.59 |

## Reading

- Neither contrast is distinguishable from zero, and neither could have been: both point
  estimates are far inside their own MDE. **This is a bound on the question, not an answer
  to it.** Nothing here says the under list is worthless; it says 79 flags on two Saturdays
  cannot tell a worthwhile list from a worthless one.
- The bound is still worth having: it rules out the *large* effects. A list that moved the
  close by more than about 1.5 points would have shown up, and none did.
- Both point estimates lean slightly negative, i.e. the listed flags and the bigger stated
  edges moved *away* from PFF's side. At these intervals that is noise and should not be
  described as a reverse effect.
- **This becomes answerable at the end of the 2026 season, not during it.** 595 scored flags at roughly forty a week is about thirteen more weeks, which is the rest of the
  regular season. Plan the look for then; there is nothing to see before it.

## What this does not support

- Any claim about win rate. This is a movement test; open question C owns the `value`
  win-rate question and is embargoed until 56 prospective picks have graded.
- Reading either null as evidence of absence. See the MDE column.
- A third contrast on this sample. The budget was two looks.
- Weekly re-looks. The stop rule is ~596 scored flags, which is also when the slate-date
  count stops being the binding problem.

