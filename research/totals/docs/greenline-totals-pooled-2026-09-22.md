# PFF Greenline totals, every graded era pooled — through 2026 week 3

2026-09-22

## Question

Three graded Greenline totals corpora now exist, and each has been reported on alone: the
2020 `PFF_hist` archive, the 2022-23 export slates, and the 2026 weekly captures, the last
of which just added week 3. Every one of them landed below the win rate its own sample
could detect. **Pooled, do they clear that floor — and are the three eras alike enough that
pooling them means anything?**

Short answer: **175-149, 54.0%, against a 52.38% break-even.** The eras are statistically
indistinguishable from one another, so the pool is legitimate, and it is the first Greenline
totals number whose 95% interval has a floor worth quoting (48.6%). It still does not clear
the detection threshold this n requires (59.3%), and the money interval still contains zero.
Nothing here licenses a bet-sizing change.

## Data

324 graded picks, 3 pushes excluded, 327 rows in all. Every pick graded **at the line in
its own capture**, per the unit's standing rule.

| era | source | picks | dates |
| --- | --- | ---: | --- |
| 2020 PFF_hist | `greenline_history_archive.csv`, `snapshot='open_greenline'` | 131 | 2020-09 → 2020-12 |
| 2022-23 exports | `greenline_history_archive.csv`, `snapshot='export'` | 91 (88 graded) | 2022-09-30→10-02, 2023-10-17→22, 2023-11-02→05 |
| 2026 flags | `greenline_graded.csv`, weeks 2-3 | 106 | 2026-09-11 → 2026-09-19 |

Finals for the two archive eras are the CFBD scores carried on the archive rows, after the
join repair in [`greenline-archive-join-audit-2026-09-21.md`](greenline-archive-join-audit-2026-09-21.md).
2026 finals are whatever `grade_greenline.py` recorded — PFF's schedule on 96 rows, the
warehouse fallback on 10, including the two TBD-kickoff week-3 games
([`greenline-w3-grade-2026-09-21.md`](greenline-w3-grade-2026-09-21.md) graded those by
hand; the warehouse has since backfilled them and the script now agrees).

**Grading the archive from finals is validated, not assumed.** On the 2020 era, where PFF
published its own `bet_result`, the same rule reproduces it on all 131 picks. That is what
licenses applying it to the exports, where PFF published no result column at all.

Reproduce with:

```bash
python research/totals/scripts/pool_totals_record.py
```

## Record

`mde%` is the smallest true win rate the sample could separate from 52.38%, one-sided,
α 0.05, 80% power.

| population | n | W-L | hit% | Wilson 95% | mde% | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2020 PFF_hist | 130 | 71-59 (1P) | 54.6% | 46.0 – 62.9 | 63.3% | below floor |
| 2022-23 exports | 88 | 46-42 (2P) | 52.3% | 42.0 – 62.4 | 65.6% | below floor |
| 2026 flags | 106 | 58-48 | 54.7% | 45.2 – 63.9 | 64.4% | below floor |
| **pooled** | **324** | **175-149 (3P)** | **54.0%** | **48.6 – 59.4** | **59.3%** | **below floor** |

- One-sided exact binomial against break-even: **p 0.297**.
- Flat-prior posterior that the true rate beats break-even: **72%** (median 54.0%, 5th
  percentile 49.4%).

## Is the pool one thing?

**Chi-square across the three eras: 0.15 on 2 df, p 0.929.** Six years, three different
capture formats, and the win rates are as alike as random draws from one rate. Pooling is
defensible on this evidence — which is the *only* reason the pooled row above is quoted at
all.

The pooled win-rate SE is 2.77pp iid and **1.98pp clustered by game day** (51 distinct
days). Clustering *tightening* the estimate means same-day results are not positively
correlated in this sample, contrary to the usual worry about slate-wide weather shocks. The
Wilson interval quoted above is the iid one, so the headline interval is the conservative
one either way.

## Side splits

| split | n | W-L | hit% | Wilson 95% | mde% |
| --- | ---: | ---: | ---: | ---: | ---: |
| all eras, unders | 270 | 146-124 (2P) | 54.1% | 48.1 – 59.9 | 59.9% |
| all eras, overs | 54 | 29-25 (1P) | 53.7% | 40.6 – 66.3 | 69.3% |
| 2020, unders | 125 | 69-56 (1P) | 55.2% | 46.5 – 63.6 | 63.5% |
| 2022-23, unders | 57 | 31-26 (1P) | 54.4% | 41.6 – 66.6 | 68.8% |
| 2026, unders | 88 | 46-42 | 52.3% | 42.0 – 62.4 | 65.6% |
| 2026, overs | 18 | 12-6 | 66.7% | 43.7 – 83.7 | 81.7% |

**Under vs over: chi-square 0.00 on 1 df, p 0.960.** Whatever the pool is measuring, it is
not specific to the under side. The board is 83% unders (270 of 324), so the pooled number
is overwhelmingly an unders number by composition — but the 54 overs land at the same rate,
which is evidence against treating "the under tilt" as the thing that wins. The 2026 overs
at 66.7% are 18 picks and the one split here anybody would be tempted to read; its floor is
81.7%.

## The published 2026 under lists — nested, not added

These 58 picks are already inside the 2026 flag row. They are the positive-edge subset PFF
ranked and published, so they answer the *slate* question, not the *board* question, and
adding them to the pool would double-count.

| population | n | W-L | hit% | Wilson 95% | mde% |
| --- | ---: | ---: | ---: | ---: | ---: |
| weeks 2-3 under list | 58 | 32-26 | 55.2% | 42.5 – 67.3 | 68.7% |
| week 2 | 36 | 21-15 | 58.3% | 42.2 – 72.9 | 73.1% |
| **week 3 (graded last week)** | 22 | 11-11 | 50.0% | 30.7 – 69.3 | 78.9% |

**Week 3 did not change the picture.** 11-11 on the published list and 31-26 on the full
board are both inside the pooled interval; the week moved the pooled hit rate by well under
a point and the pooled MDE by about two points. That is what one week is worth at this n,
and it is the argument for continuing to capture rather than for acting.

## Money — price-bearing rows only

237 of 327 picks carry a price. The **2022-23 exports carry none** (`breakeven_prob` NULL
on every row), which is an integrity-gate failure under
[`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md), so they are
excluded from every number below rather than defaulted to -110. Bootstrap resamples bets,
4,000 reps.

| population | n | units (95%) | ROI | ROI 95% |
| --- | ---: | ---: | ---: | ---: |
| priced pool | 236 | +12.25u (-16.4 to +41.2) | +5.2% | -7.0 to +17.4 |
| 2020 PFF_hist | 130 | +7.52u (-14.0 to +28.9) | +5.8% | -10.8 to +22.2 |
| 2026 flags (assumed -110) | 106 | +4.73u (-14.4 to +23.8) | +4.5% | -13.6 to +22.5 |
| 2026 under lists (nested) | 58 | +3.09u (-10.3 to +16.5) | +5.3% | -17.7 to +28.4 |
| priced pool at flat -110 | 236 | +10.27u (-18.4 to +38.9) | +4.4% | -7.8 to +16.5 |
| 2020 at flat -110 | 130 | +5.55u (-15.5 to +26.5) | +4.3% | -11.9 to +20.4 |

**The 2020 leg is priced at PFF's own claim.** Its published break-evens run better than
-110 on 75 of 131 picks, median implied price about -107, which no observed book number
backs. The flat -110 rows are the sensitivity: the pooled ROI drops from +5.2% to +4.4% and
both intervals still straddle zero.

## What this does not support

- **Not a cleared floor.** 54.0% against a 59.3% MDE. The pooled interval is consistent with
  a real edge, with break-even, and with a small loss. A 72% posterior is not a green light;
  it is a 28% chance the sign is wrong before any vendor-selection bias is priced in.
- **Not a staking change.** The bankroll unit's planning prior (half-pooled, κ=0.5) already
  discounts this evidence deliberately. Nothing here argues for raising it; the pooled ROI
  interval reaches -7%.
- **Not a verdict on the under tilt.** Overs match unders. Any story that requires the edge
  to live on the under side is unsupported by this pool.
- **Not a return on 2022-23.** Record only. Those 88 picks contribute to hit rate and to
  nothing financial.
- **No CLV and no proper score.** The three eras do not share a closing-line convention, and
  the exports have no break-even, so neither a de-vigged Brier nor a cross-era CLV is
  computable here. Both remain 2026-only questions.
- **Not independent of the personal 2023-25 unders.** Those were mostly the same Greenline
  flags taken as bets and are deliberately absent from this pool; they are prior evidence,
  not a fourth era.
- **Multiplicity.** Eleven splits are printed above. The best of them (2026 overs, 66.7%)
  is the one to discount hardest.

## Method

`research/totals/scripts/pool_totals_record.py`, `--self-check` pins: the grading rule on
four hand-checked boundaries, the 2020 record against PFF's own `bet_result` (71-59-1), the
export record against
[`greenline-export-picks-graded-2026-09-21.md`](greenline-export-picks-graded-2026-09-21.md)
(46-42-2), the 2026 flag record (58-48), both published under-list records (21-15 and 11-11)
against their own grade docs, that the under lists are a strict subset of the flags rather
than additive rows, that no export row carries a price, and that MDE falls as n grows.

Wilson, MDE, exact binomial, Beta posterior, bootstrap, chi-square heterogeneity, and
day-clustered SE are imported from `greenline_season_review.py` and `greenline_bet_stats.py`
rather than reimplemented, so this doc and the weekly reviews cannot drift apart.

## Supersedes nothing

[`greenline-totals-season-2026-09-16.md`](greenline-totals-season-2026-09-16.md) answers the
2026-season-to-date question and remains the record for it;
[`greenline-archive-2026-09-17.md`](greenline-archive-2026-09-17.md) and
[`greenline-export-picks-graded-2026-09-21.md`](greenline-export-picks-graded-2026-09-21.md)
remain the records for their own eras. Cross-era pooling is a new question, so this is a new
dated doc and none of them is superseded.
