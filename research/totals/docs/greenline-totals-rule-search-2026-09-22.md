# Best edge threshold and totals band, overs and unders — searched and tested

2026-09-22

## Question

What edge threshold and market-total band should be bet, on each side? Searched over the
324-pick pooled corpus from
[`greenline-totals-pooled-2026-09-22.md`](greenline-totals-pooled-2026-09-22.md) — the first
sample large enough that the question is worth asking on more than one season at a time.

**Answer: there is no such rule to give, and this is not "we need more data" hedging — the
tests are specific.** The best cell in the grid is `under / 55-59.5 / Q4`, 14-8 (63.6%), and
a shuffle that destroys all cell-level signal produces a cell that good or better **54.7% of
the time**. The walk-forward cannot even be run, because the eras do not share cells. None
of four pre-registered splits survives Holm. Overs are not estimable at n=54.

The one thing worth carrying forward is a *hypothesis*, pre-registered here for the rest of
the season, not a filter to turn on: **PFF's own biggest edges are its worst picks.** Unders
in PFF's top within-era edge quintile went 29-34 (46.0%) while Q1–Q4 went 117-90 (56.5%).
Era-stratified p 0.192. That is a direction to test, not a number to bet.

## Method — the three choices that decide the answer

**Bands are pre-registered, not reused.** `greenline_unders.BANDS` is the obvious grid and
the wrong one: its boundaries carry the personal 2023-25 under record in the table itself,
and the boundaries were drawn looking at that record. That set overlaps the Greenline board
(7 of 12 where checkable), so reusing those cutpoints is a threshold chosen partly on the
evaluation sample — an invalidating failure under
[`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md). Round 5-point
bins here, chosen for being round.

**Edge is ranked within era, not cut at raw values.** PFF's `value` is not one scale across
eras — 2020 tops out at 0.029, 2026 reaches 0.053 — so raw bins smuggle in era. Raw bins are
printed as description with their era counts beside them; every verdict runs on within-era
quintiles.

**Nothing gets a verdict from a cell the search picked.** The grid is 2 sides × 6 bands × 5
quintiles = 60 cells over 324 picks; it *will* produce something near 65%. Two tests decide
whether it means anything: a max-cell permutation and a two-way walk-forward.

Reproduce with:

```bash
python research/totals/scripts/totals_rule_search.py
```

## The diagnostic that has to come first

| raw edge bin | 2020 | 2022-23 | 2026 | total |
| --- | ---: | ---: | ---: | ---: |
| <1% | 39 | 21 | 27 | 87 |
| 1-2% | 57 | 24 | 5 | 86 |
| 2-3% | 34 | 20 | 18 | 72 |
| 3-4% | **0** | 21 | 34 | 55 |
| 4%+ | **0** | 2 | **22** | 24 |

| market-total band | 2020 | 2022-23 | 2026 | total |
| --- | ---: | ---: | ---: | ---: |
| <45 | 3 | 23 | 6 | 32 |
| 45-49.5 | 3 | 6 | 29 | 38 |
| 50-54.5 | 12 | 7 | 36 | 55 |
| 55-59.5 | 41 | 23 | 30 | 94 |
| 60-64.5 | **53** | 19 | **4** | 76 |
| 65+ | 18 | 10 | 1 | 29 |

**The raw edge bins are largely era labels.** No 2020 pick reaches 3%, and 22 of the 24 picks
above 4% are 2026 weeks 2 and 3 — so "the 4%+ bucket collapses" is, in the raw grid, a
statement about two September weekends. Bands are as bad in the other direction: 60-64.5 is
53 of 76 from 2020 and has four 2026 picks in it.

This is the single most important table in the doc. Everything below is read against it.

## Unders — n=270

### Within-era edge quintile (Q5 = PFF's strongest edges that era)

| quintile | n | W-L | hit% | Wilson 95% | mde% |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q1 | 36 | 18-18 | 50.0% | 34.5 – 65.5 | 73.1% |
| Q2 | 47 | 24-23 | 51.1% | 37.2 – 64.7 | 70.5% |
| Q3 | 62 | 39-23 | 62.9% | 50.5 – 73.8 | 68.2% |
| Q4 | 62 | 36-26 | 58.1% | 45.7 – 69.5 | 68.2% |
| **Q5** | 63 | **29-34** | **46.0%** | 34.3 – 58.2 | 68.0% |

Non-monotone, and inverted at the top. Per era, Q5 runs 13-13, 8-8, 8-13 — flat in 2020 and
2022-23, negative in 2026. So the shape is driven by 2026 and is not yet a six-year pattern.

### Market-total band (pre-registered 5-point bins)

| band | n | W-L | hit% | Wilson 95% | mde% |
| --- | ---: | ---: | ---: | ---: | ---: |
| <45 | 1 | 1-0 | — | — | — |
| 45-49.5 | 27 | 13-14 | 48.1% | 30.7 – 66.0 | 76.3% |
| 50-54.5 | 47 | 22-25 | 46.8% | 33.3 – 60.8 | 70.5% |
| 55-59.5 | 92 | 51-41 | 55.4% | 45.3 – 65.2 | 65.3% |
| 60-64.5 | 76 | 44-32 | 57.9% | 46.7 – 68.4 | 66.6% |
| 65+ | 27 | 15-12 | 55.6% | 37.3 – 72.4 | 76.3% |

Every band's interval contains break-even, and every band's MDE is above every band's hit
rate. The apparent "55 and up is better" is 56.4% vs 48.0%, era-stratified p 0.295.

### Raw edge bins (descriptive only — read the era table first)

| bin | n | W-L | hit% | Wilson 95% |
| --- | ---: | ---: | ---: | ---: |
| <1% | 50 | 23-27 | 46.0% | 33.0 – 59.6 |
| 1-2% | 75 | 42-33 | 56.0% | 44.7 – 66.7 |
| 2-3% | 67 | 40-27 | 59.7% | 47.7 – 70.6 |
| 3-4% | 54 | 33-21 | 61.1% | 47.8 – 73.0 |
| 4%+ | 24 | **8-16** | 33.3% | 18.0 – 53.3 |

The tidy rise and the collapse at the top are the pattern anyone would trade on. Within 2026
alone — the only era with real coverage above 4% — it is 8-14 above 4% against 38-28 below,
Fisher p 0.093. In the exports it is 0-2. It is a shape, on one season, that does not reach
significance.

## Overs — n=54, and not answerable

| quintile | n | W-L | hit% | | band | n | W-L | hit% |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Q1 | 30 | 15-15 | 50.0% | | <45 | 31 | 16-15 | 51.6% |
| Q2 | 18 | 12-6 | 66.7% | | 45-49.5 | 11 | 4-7 | 36.4% |
| Q3 | 2 | 1-1 | — | | 50-54.5 | 8 | 6-2 | 75.0% |
| Q4 | 3 | 1-2 | — | | 55-59.5 | 2 | 2-0 | — |
| Q5 | 1 | 0-1 | — | | 65+ | 2 | 1-1 | — |

54 picks, largest grid cell 13. A cell that size would need roughly **87%** to be
distinguished from break-even; the whole over set needs 69.3%. **No overs rule is estimable
from this data**, and the output here is that bound rather than a rule with a caveat on it,
because a rule with a caveat gets bet. The tempting cells — raw 1-2% at 9-2, band 50-54.5 at
6-2 — are exactly what the permutation test below exists to kill.

## Does the best cell survive the search that found it?

Best qualifying cell (n ≥ 20): **under / 55-59.5 / Q4, 14-8, 63.6%**.

Shuffling results within era 4,000 times — which holds each era's win rate and every cell
size fixed, so the only thing destroyed is cell-level signal — the best cell is *typically*
**63.6%**, and reaches 63.6% or better in **54.7% of shuffles (p 0.547)**.

**A search over this grid finds a cell this good about as often when there is nothing
there.** The observed best cell is the search, not a rule. This is the number that answers
the question as asked.

## Pre-registered marginal splits, era-stratified

Four splits, named before reading the grid so Holm has a real denominator. Unders only.
Cochran-Mantel-Haenszel across the three eras rather than pooled, so a split that is really
era composition cancels instead of reporting itself as a finding.

| split | takes | leaves | CMH p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| PFF's top edge quintile vs the rest | 29-34 (46.0%) | 117-90 (56.5%) | 0.192 | 0.384 |
| middle quintiles Q3+Q4 vs the rest | 75-49 (60.5%) | 71-75 (48.6%) | 0.066 | 0.232 |
| market total 55+ vs below 55 | 110-85 (56.4%) | 36-39 (48.0%) | 0.295 | 0.384 |
| raw edge 4%+ vs below 4% | 8-16 (33.3%) | 138-108 (56.1%) | 0.058 | 0.232 |

**Nothing survives Holm**, smallest adjusted p 0.232.

## Walk-forward — and why it cannot be run

| direction | rule chosen | training half | held-out half | held-out n |
| --- | --- | ---: | ---: | ---: |
| 2020+exports → 2026 | under / 60-64.5 / Q4 | 13-8 (61.9%) | — | **0** |
| 2026 → 2020+exports | no cell reaches n=20 | — | — | — |

The rule chosen on the older eras lands on **zero** 2026 picks: 60-64.5 was 53 of 76 picks in
2020 and has four in 2026. Going the other way, no single 2026 cell reaches twenty picks at
all. This is worth stating plainly — the walk-forward did not *fail*, it was **not runnable**,
because the eras' boards do not overlap in the space the rule is defined over. Any rule fit
on one era is being asked to bet a slate the other era barely contains.

## What this does not support

- **No edge threshold.** Not 2%, not 3%, not "skip above 4%". The 4%+ collapse is 22 of 24
  picks from two September weekends and reaches p 0.058 raw, 0.232 after Holm.
- **No band.** Every band's interval covers break-even and every band's MDE exceeds its own
  hit rate.
- **No overs rule of any kind.** n=54 with a 13-pick largest cell.
- **Not a contradiction of the earlier nulls — a confirmation of them.**
  [`greenline-band-significance-2026-09-17.md`](greenline-band-significance-2026-09-17.md)
  withdrew the band ordering and
  [`greenline-edge-cap-revisit-2026-09-17.md`](greenline-edge-cap-revisit-2026-09-17.md)
  dropped the 2–4% window on a ninth of this sample. Tripling the data moved neither verdict.
  Both remain the records for the 2026-only version of the question; this is the pooled one.
- **Not "keep looking and it will appear."** The permutation p of 0.547 is a statement about
  the search procedure, not the sample size. A bigger pool makes cells estimable; it does not
  make a 60-cell max-pick honest.

## The one thing to carry forward, pre-registered

**Hypothesis, registered 2026-09-22:** unders PFF marks with `total_best_value` **≥ 0.04**
lose to unders below it.

**Stated as a raw cut, not a quintile, on purpose.** A quintile boundary is recomputed from
whatever picks exist when it is scored — a pick that is Q5 in September is Q4 by December —
so "Q5 went X-Y" has no fixed referent and the rule is not computable before kickoff, which
is the same gate the standard applies to prices. The 2026 weeks 2-3 Q5 boundary sits at
`0.040035`, which is PFF's displayed 4.0%, so the quintile split and this raw cut are the
same line. The raw one is the one a week-4 capture row can be classified by, in advance,
forever.

| | n | W-L | hit% |
| --- | ---: | ---: | ---: |
| unders at or above 0.04 | 24 | 8-16 | 33.3% |
| unders below 0.04 | 246 | 138-108 | 56.1% |

**That table is the prior, not the test.** It is the data the hypothesis was read off, so it
cannot also be its evidence.

**Stopping rule: no look until 56 prospective above-cut unders have graded**, counting from
2026 week 4 forward. Fifty-six powers the observed 23-point gap at 80% given the roughly 2:1
below:above split the board produces. Week 4's capture carries 18 under flags of which **9**
clear the cut, so this is a six-to-seven-week wait if that rate holds — and if the true gap
is 10 points rather than 23 it needs about 290 above-cut picks and no single season settles
it. That is the ceiling, not a reason to peek weekly. One split, no band interaction, tested
era-stratified exactly as the four above.

If it holds out of sample it is a genuine and slightly funny finding — the vendor's own
confidence ranking inverted at its top end. If it does not, it was the grid talking, and this
paragraph is the record that it was called in advance.

## Method notes

`research/totals/scripts/totals_rule_search.py`, `--self-check` pins: the band and raw-bin
boundaries; that quintiles are within-era, near-equal in size, and correctly ordered; that
the permutation restores the real results afterwards (a shuffle left in place would corrupt
every later number); that a planted 100% cell is actually detected, so a null verdict is not
just the detector failing to fire; that Holm is correct on hand-worked inputs; and that CMH
cancels a split which is purely era composition while still firing on the same effect present
inside both strata.
