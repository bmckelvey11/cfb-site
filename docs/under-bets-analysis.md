# NCAAF under bets — full analysis

203 under bets, 2023-08 → 2025-12. **115-88 (56.7%), +18.9u on 212u risked = +8.9% ROI.**
Unders are 40% of your NCAAF volume and ~87% of all your totals bets — you are structurally
an under bettor, not a totals bettor who happens to land on unders.

## What the bets are NOT based on

Tested and rejected. Each of these would be a visible selection rule if it existed:

| Hypothesis | Finding | Verdict |
|---|---|---|
| Targets a total-line range | Buckets alternate +21/-12/+25/-5/+13/+9%, no monotonic trend | **rejected** |
| Team-specific reads | 114 distinct teams over 203 bets, max 9 bets on any team | **rejected** |
| Conference/level filter | G5-only +7.0%, mixed +6.5%, both-P5 +11.8% — flat | **rejected** |
| Price sensitivity / line shopping | 64% of bets at exactly -110, mean -109 | **rejected** |
| Selective spot-picking | 2.7 unders per active day, up to 10 on one slate | **rejected** — volume play |
| Kickoff-time or day-of-week angle | Noisy, all cells n<20 except Saturday | **rejected** |

Bet slips carry no reasoning text, so intent is inferred from selection profile only.

## What the bets ARE based on

**A blanket lean toward unders on medium-to-high totals, applied broadly across the slate.**

- Median total bet: **58.5** — the fat middle of the CFB market, not extremes
- 76% take a hook (.5), i.e. you accept the standard posted number rather than hunting key numbers
- 87% of your totals bets are unders — a persistent directional bias, not a per-game read
- Applied at 2.7 bets/day across 76 different game days

This is a thesis bet: *posted CFB totals are systematically too high.* Reasonable prior — public
money favors overs, books shade totals up to absorb it.

## The one real pattern: late-season unders

Splitting November/December/January from August-October:

| season | early (Aug-Oct) | late (Nov-Jan) |
|---|---|---|
| 2023 | 31-30, **-3.8%** | 11-7, **+18.8%** |
| 2024 | 13-10, +14.1% | 5-2, **+36.9%** |
| 2025 | 24-20, +3.7% | 31-19, **+18.4%** |

**Late unders: 47-28 (62.7%), p=0.047. Early unders: 68-60 (53.1%) — essentially breakeven.**

The split holds in all three seasons independently. Nearly all of your under profit comes from
the late window; the early-season unders are a coin flip paying -110.

Plausible mechanism: cold weather, wind, shortened playbooks, conservative bowl/rivalry
game-planning, and defenses that have caught up to early-season offensive scheme edges.
The market appears to underadjust totals for this.

Note: you do **not** appear to be exploiting this consciously — you bet *lower* totals late
(mean 56.0) than early (58.2), and your under share barely moves by month (83-91% all season).
The edge is falling out of a constant strategy meeting a seasonal effect.

## The 2023 → 2024-25 shift is not a selection change

| era | n | mean total | mean odds | bets/day | win% | ROI |
|---|---|---|---|---|---|---|
| 2023 | 79 | 56.5 | -110.0 | 2.5 | 53.2% | **+1.2%** |
| 2024-25 | 124 | 58.0 | -108.4 | 2.8 | 58.9% | **+13.4%** |

Every measurable *input* is nearly identical — same line range, same juice, same volume, same
under-share. Only the hit rate moved. Either the qualitative read behind the picks improved in a
way the CSV cannot capture, or 2024-25 is partly variance. **The data cannot distinguish these.**
2024-25 unders alone: p=0.087 — not significant.

## Statistical honesty

- Late unders p=0.047 is nominally significant but does **not** survive correction for the ~15
  hypotheses tested here (Bonferroni alpha ≈0.0033).
- 203 bets is thin. At these effect sizes you need roughly 1,000+ to separate a 57% bettor from
  a 52.4% one with confidence.
- The late-season split is the strongest claim available because it replicates across three
  independent seasons — replication is worth more than any single p-value.
- No closing-line data in the export, so no CLV check is possible. That remains the fastest
  route to confirming or killing this.

## Actionable

1. **Cut or reduce early-season unders.** 128 bets returning +2.1% is not worth the variance.
   Concentrating the same bankroll in the late window is the single highest-value change.
2. **Forward-test "Nov-Dec unders" on 2026** as a paper system before sizing up.
3. **Backtest the seasonal totals effect in `cfb_system_maker`** against the full 13k-game set —
   that has the sample size to settle in one run what 203 bets cannot.
4. Overs are +30% ROI in both windows on 31 bets. Too small to act on, but worth tracking rather
   than dismissing given your 87% under bias may be leaving over spots unplayed.
