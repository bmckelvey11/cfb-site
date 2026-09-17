# Pinnacle shade on Greenline unders, 2026-09-17

Reproduce: `python research/totals/scripts/pinnacle_shade.py --out research/totals/docs`.

## Question

Does where Pinnacle sits at capture (its juice lean, its line relative to PFF's, its distance from
PFF's projection, its limit) predict which Greenline under flags win?

## Data

- 2026 graded under flags with a Pinnacle capture: n = 38, weeks 2, record 22-16 (58%, 42–72%).
- Pinnacle numbers from `greenline_vs_pinnacle_<season>_w<week>.csv` (captured with the flag, before kickoff).
- The 2023-25 history has no Pinnacle capture and is not in this test.
- MDE for the whole sample: 72.5% against 52.38% break-even.

## Features, fixed before running

| feature | rule |
|---|---|
| lean | Pinnacle fair - Pinnacle line < 0 (juice leans under) |
| move | Pinnacle line - PFF line < 0 (market already below PFF's number) |
| disagree | PFF proj - Pinnacle fair (split at median; more negative = harder fade) |
| limit | Pinnacle limit (split at median; higher = sharper) |

## Records: below the cut vs at or above

| feature | n | cut | below | at/above | Fisher p | Holm p | Spearman rho | p | MDE below |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| lean | 38 | 0.00 | 8-7 (53%, 30–75%) | 14-9 (61%, 41–78%) | 0.743 | 1.000 | +0.11 | 0.504 | 84% |
| move | 38 | 0.00 | 9-2 (82%, 52–95%) | 13-14 (48%, 31–66%) | 0.078 | 0.310 | -0.28 | 0.094 | 90% |
| disagree | 38 | -1.48 | 11-8 (58%, 36–77%) | 11-8 (58%, 36–77%) | 1.000 | 1.000 | +0.07 | 0.685 | 81% |
| limit | 38 | 840.00 | 11-5 (69%, 44–86%) | 11-11 (50%, 31–69%) | 0.326 | 0.979 | -0.10 | 0.560 | 83% |

## Reading

- No Pinnacle feature survives Holm at 5%. None is a filter yet.
- Strongest raw split is `move` (Fisher p 0.078): below 9-2 (82%, 52–95%) vs at/above 13-14 (48%, 31–66%).
- For `lean` and `move`, 'below' is the half where Pinnacle already agrees with PFF's under. If that half
  wins more, the market is confirming PFF; if the other half wins more, PFF is adding something the
  market has not priced. Neither is readable until the sample clears its MDE.

Hand notes on this run (2026-09-17):

- `move` is the one to watch, and it points the other way from today's line-shopping calls. The 11
  flags where Pinnacle already sat below PFF's shown line went 9-2; the 27 where it did not went
  13-14. Today four flags were passed because the number had moved a point toward the under, priced
  through the pricing law at the new number. This split says the games the market moved first were
  the ones that won. n = 11, MDE 90%, Holm p 0.31: not a contradiction yet, but log it and rerun.
- `lean` (Pinnacle's own juice) carries nothing at this n. `disagree` splits exactly 11-8 / 11-8.

## What this does not support

- Any rule on the live slate. This is one to two graded weeks of one vendor's flags.
- Reading `limit` as anything but a proxy: Pinnacle limits scale with the game's profile, not with
  how sharp the number is on that game.

## What settles it

- Rerun after each graded week; the join picks up new `greenline_vs_pinnacle_*` files automatically.
- ~150 graded unders gives a halved split ~64% MDE per side.
