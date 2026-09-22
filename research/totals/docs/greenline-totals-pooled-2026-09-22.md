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

**A fourth stratum was added on request** — the 201 personal book unders of 2023-25, 114-87,
56.7%. It is reported beside the pool and not inside it, because checking the overlap for
the first time found 3 of the 12 checkable bets took the side Greenline flagged *against*.
Details in [Fourth stratum](#fourth-stratum--the-2023-25-personal-unders).

## Data

324 graded picks, 3 pushes excluded, 327 rows in all. Every pick graded **at the line in
its own capture**, per the unit's standing rule.

| era | source | picks | dates |
| --- | --- | ---: | --- |
| 2020 PFF_hist | `greenline_history_archive.csv`, `snapshot='open_greenline'` | 131 | 2020-09 → 2020-12 |
| 2022-23 exports | `greenline_history_archive.csv`, `snapshot='export'` | 91 (88 graded) | 2022-09-30→10-02, 2023-10-17→22, 2023-11-02→05 |
| 2026 flags | `greenline_graded.csv`, weeks 2-3 | 106 | 2026-09-11 → 2026-09-19 |
| *(compared, not pooled)* 2023-25 personal unders | `bet_history/history.csv` via `personal_totals()` | 201 | 2023-08-26 → 2026-01-02 |

Finals for the two archive eras are the CFBD scores carried on the archive rows, after the
join repair in [`greenline-archive-join-audit-2026-09-21.md`](greenline-archive-join-audit-2026-09-21.md).
2026 finals are whatever `grade_greenline.py` recorded — PFF's schedule on 96 rows, the
warehouse fallback on 10, including the two TBD-kickoff week-3 games
([`greenline-w3-grade-2026-09-21.md`](greenline-w3-grade-2026-09-21.md) graded those by
hand; the warehouse has since backfilled them and the script now agrees).

**Grading the archive from finals is validated, not assumed.** On the 2020 era, where PFF
published its own `bet_result`, the same rule reproduces it on all 131 picks. That is what
licenses applying it to the exports, where PFF published no result column at all.

The rule grades at `market_line`, and the check is only worth something where that choice
bites. `market_line` and `greenline_line` differ on 126 of the 131 2020 picks, and on
**three** of them the final lands so that the two numbers grade differently. `market_line`
matches PFF's published result on all three. So the agreement is not an artifact of the two
lines rarely mattering — it is the discriminating cases going the right way. This matters
because the exports carry no `greenline_line` at all, so `market_line` is the only number
available there.

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

The pooled win-rate SE is 2.77pp iid and 1.98pp clustered by game day (51 distinct days).
Clustering does not widen the interval here, so the iid Wilson above stands as the headline
and is the conservative choice. Read nothing further into it: these "days" span 2020, 2022,
2023 and 2026, which are not exchangeable clusters, so the tightening is a property of the
cluster definition rather than a fact about same-day football.

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

## Fourth stratum — the 2023-25 personal unders

Added on request as a fourth stratum, and reported **beside** the pool rather than inside
it. The 201 book unders of 2023-25 carry the price actually paid, so unlike the exports they
can carry a return.

| population | n | W-L | hit% | Wilson 95% | mde% |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-25 personal unders | 201 | 114-87 | 56.7% | 49.8 – 63.4 | 61.1% |
| Greenline pool | 324 | 175-149 | 54.0% | 48.6 – 59.4 | 59.3% |
| Greenline pool, unders only | 270 | 146-124 | 54.1% | 48.1 – 59.9 | 59.9% |

Head to head, chi-square 0.37 on 1 df, **p 0.545** — the personal record is 2.6 points
better and that gap is well inside noise. All four strata together: chi-square 0.51 on 3 df,
p 0.916. The 30 personal *overs* of those seasons are excluded; the standing question about
this set has always been an unders question.

### Why beside and not inside — the overlap, measured

This tree's standing caveat says the 2023-25 unders "were mostly the same Greenline flags,
taken as bets." That has never been measured. It can be, on exactly the days where a
Greenline board and a book bet both exist: the three 2022-23 export slates, ten slate days.
2024 and 2025 have no flag archive at all, so nothing there is checkable in either
direction. Both sides resolve to a CFBD team-id pair first, because the book and PFF
disagree on dozens of abbreviations.

| of the 12 personal unders on those days | n |
| --- | ---: |
| Greenline flagged the same side | 7 |
| Greenline flagged the **opposite** side | 3 |
| Greenline never flagged the game | 2 |
| team abbreviation unresolvable | 0 |

**Three of twelve took the side Greenline flagged against** — MINN@IOWA under 30.5 against a
flagged over 32.5, AFA@NAVY under 37.5 against a flagged over 37.5, ARMY@AFA under 34.0
against a flagged over 31.5. A bet opposing the vendor is not that vendor's pick at a
different price; it is a different selector. Folding the set into the pooled row would
average Greenline's skill with that selector's, and would leave the homogeneity test in
*Is the pool one thing?* testing the wrong hypothesis. So the pooled 324 is unchanged and
this stratum sits next to it.

The measurement cuts both ways and both should be said: 7 of 12 **is** a real overlap, so
the set is not independent evidence either, and the half-pooled (κ=0.5) treatment the
bankroll unit already applies to it remains the right handling. What is now measured rather
than assumed is that the overlap is partial, on one season, on a sample of twelve.

## Money — price-bearing rows only

237 of the 327 pooled picks carry a price (236 after the one priced push drops out, which is
the `n` in the table below). The personal unders carry the price actually paid and are shown
for contrast, outside the pool. The **2022-23 exports carry none** (`breakeven_prob` NULL
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
| **2023-25 personal unders (not pooled)** | 201 | +16.41u (-10.1 to +43.0) | **+8.2%** | -5.0 to +21.4 |
| priced pool at flat -110 | 236 | +10.27u (-18.4 to +38.9) | +4.4% | -7.8 to +16.5 |
| 2020 at flat -110 | 130 | +5.55u (-15.5 to +26.5) | +4.3% | -11.9 to +20.4 |

The personal unders are the only line here priced at money that actually changed hands, and
they are also the best return in the table. Their interval still reaches -5.0%.

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
- **The personal 2023-25 unders are neither independent evidence nor a fourth era.** Where
  the overlap is checkable they are 7 of 12 the same Greenline pick, 3 of 12 the opposite
  side. Too entangled to be a second opinion, too different to be pooled in. They stay a
  comparison stratum and the bankroll unit's κ=0.5 half-pooling stays the right discount.
  56.7% on 201 picks is the best single record in this doc and it is still 4.4 points under
  its own floor.
- **Multiplicity, and it is worse than the eleven splits printed here.**
  `greenline_bet_stats.py` already carries `SPLITS_EXAMINED = 24` for the looks taken across
  this tree — bands, value buckets, edge bins, sides and sources. These eleven are additional
  to those and fall on largely the same picks, so the pooled 54.0% is being read after
  roughly 35 looks. That does not move any number, and it cuts against the pool rather than
  for it. The best single split here (2026 overs, 66.7% on 18 picks) is the one to discount
  hardest.

## Method

`research/totals/scripts/pool_totals_record.py`, `--self-check` pins: the grading rule on
four hand-checked boundaries, the three 2020 picks where `market_line` and `greenline_line`
grade differently (all three must match PFF's published result, or the line choice carried
to the exports is unvalidated), the 2020 record against PFF's own `bet_result` (71-59-1), the
export record against
[`greenline-export-picks-graded-2026-09-21.md`](greenline-export-picks-graded-2026-09-21.md)
(46-42-2), the 2026 flag record (58-48), both published under-list records (21-15 and 11-11)
against their own grade docs, that the under lists are a strict subset of the flags rather
than additive rows, that no export row carries a price, and that MDE falls as n grows.
For the fourth stratum it pins the personal record (114-87), that the set is unders-only and
fully priced, that no personal row ever enters the pool, and the overlap counts themselves
(7 same side, 3 opposite, 2 unflagged, 0 unresolved) — so a later reparse that quietly
changes the overlap fails loudly instead of rewriting the caveat.

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
