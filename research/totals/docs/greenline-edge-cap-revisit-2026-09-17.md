# Revisiting the PFF edge cap, 2026-09-17

Reproduce: `python research/totals/scripts/greenline_edge_window.py`.

## Question

The week 3 under list was built with a 2–4% window on PFF's stated `value`, carried over from
week 2. Does the graded record support any cap or floor on PFF's number?

## Data

Graded 2026 under flags with a positive stated edge: n = 36, week 2 only, 21-15. Pinnacle join
n = 35. `value` is PFF's win probability minus 52.38%. Same data as
`greenline-season-review-2026-09-16.md`.

## Numbers

| edge bin | record | win% | 95% CI |
|---|---|---:|---|
| 0–2% | 1-1 | 50% | 9–91% |
| 2–3% | 4-2 | 67% | 30–90% |
| 3–3.5% | 4-2 | 67% | 30–90% |
| 3.5–4% | 9-4 | 69% | 42–87% |
| 4–5% | 2-5 | 29% | 8–64% |
| 5%+ | 1-1 | 50% | 9–91% |

- Logistic win ~ edge: slope −0.33 per point, se 0.39, p 0.40. Quadratic term p 0.33.
- Best contiguous window (2–4%): 17-8, Wilson floor 48.4%, does not clear 52.4%. Picked as the best of
  21 ranges, so the floor is optimistic by construction.
- The bucket the cap rests on (4%+) is 3-6, nine games, CI 12–65%.
- Stated edge correlates −0.54 with projection-minus-Pinnacle-fair: a big PFF edge is mostly PFF
  sitting far below Pinnacle. The shade bins do not order outcomes either (100% / 54% / 50% / 63%).

## Decision

The edge window is dropped from the week 3 list (2026-09-17). Cutting on PFF's number removed 11
flags on nine games' worth of evidence. The list now filters on spread only (`--max-spread 13.5`,
see `greenline-under-filters-2026-09-17.md`).

## What this does not support

- That the 4%+ bucket is fine. It is 3-6; that is not evidence of anything at n = 9.
- Any floor either. 0–2% is two games.

## What settles it

Rerun `greenline_edge_window.py` after each graded week. The logistic slope is the number: a cap is
justified only when the quadratic term is negative and clears p 0.05 with the interval away from zero.
