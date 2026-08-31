# B7 — "55–65 totals line → bet the under": NULL (conclusive for the band)

Tests betting the under on totals lines in the 55–65 band, plus a pre-registered
feature scan inside it.

Run: `python research/b7_mid_total_under/test_mid_total_under.py`
Data: `data/raw/lines_{2013..2025}.json` + `games_{2013..2025}.json`, 12,493
usable games / 12,372 after pushes. Prices from `data/raw/actionnetwork_odds.csv`.

**Verdict: not a bettable edge, and for the band itself the null is conclusive
rather than underpowered.** The band comes in at **51.46%** — *below* break-even,
not above it. At N=4,559 this sample could have detected a true 54.20% rate; it
found nothing close.

One filter inside the band (spread 7–14) survives further than anything in B6
and is documented in [D] as an **open lead, not an edge** — it fails the same
MDE test that killed B6, but it fails it honestly rather than dissolving.

## The break-even is 52.36%, and that is measured, not assumed

B6 closed by noting its null assumed symmetric juice, and that per-book prices
could in principle lower the under's real hurdle. `actionnetwork_odds.csv` has
real consensus over/under **prices** (4,399 games with both sides). Checked
before running anything else:

| totals line | N | median under odds | median over odds | mean under break-even |
|---|---|---|---|---|
| ≤55 | 2515 | −110 | −110 | 52.36% |
| 55–59 | 805 | −110 | −110 | 52.37% |
| 59–62 | 429 | −110 | −110 | 52.35% |
| 62–65 | 291 | −110 | −110 | 52.36% |
| >65 | 359 | −110 | −110 | 52.34% |

**Books do not shade the under on high totals.** The hurdle is flat at ~52.36%
across every band. B6's open question is closed: that caveat does not rescue
either result.

*Coverage caveat:* the price file spans 2018–2019 and 2023–2025 — **5 of the 13
seasons** tested. The hurdle is measured on those and extrapolated to the other
eight. That is safe here only because it is flat across every band, and because
the band loses to it anyway; a lower true hurdle is the only thing that could
flip the sign, and nothing in the price data suggests one.

## [A] Sub-bins first — the band is an arbitrary slice

Computed disjoint sub-bins *before* the aggregate, because 55–65 straddles B6's
bin edges and could have been an average across two regimes.

| cell | N | under% | 95% CI | vs 52.36% |
|---|---|---|---|---|
| 55–59 | 2382 | 50.76% | [48.7, 52.8] | −1.60pp |
| 59–62 | 1167 | 51.16% | [48.3, 54.0] | −1.20pp |
| 62–65 | 1010 | 53.47% | [50.4, 56.5] | +1.11pp |
| **55–65 (aggregate)** | **4559** | **51.46%** | [50.0, 52.9] | **−0.90pp** |
| <55 (below band) | 6593 | 50.17% | [49.0, 51.4] | −2.19pp |
| >65 (above band) | 1220 | 53.28% | [50.5, 56.1] | +0.92pp |

The band is not a plateau. Under% **rises across the band (50.76 → 51.16 →
53.47) then flattens above it** — `>65` at 53.28% sits marginally *below* the
top sub-bin, and B6 documented non-monotonicity at the low end too (0–45 at
50.59% above 45–59 at 50.18%). So this is not a clean monotone gradient, but
55–65 is still an arbitrary cut: it bundles the losing 55–59 region with the
only sub-bin that clears, and averages to a loser. Only 62–65 clears break-even,
by +1.11pp, with a CI spanning [50.4, 56.5].

- vs break-even: z=−1.22, one-sided **p=0.888** (wrong direction entirely).
- Bonferroni over 26 comparisons (B6's 9 priors + 17 here): **p_adj=1.000**.
- Season block-bootstrap 95% CI **[49.49%, 53.23%]**.
- **MDE at N=4,559 is 54.20%.** The key number: the sample was powered to find a
  genuinely bettable edge in this band and did not.

## [B] Probit inside the band — flat

Restricted to 55–65: slope **+0.005108** per point (SE 0.006424), z=+0.80,
p=0.4265. B6's full-range slope (+0.003279/pt, z=+2.28) does not survive
restriction to this band. Whatever weak totals-level gradient exists is not
locatable inside 55–65.

## [C] Feature scan inside the band — all 13 cells reported

Candidate pool fixed before running, from `b4_features/INVENTORY.md` (week,
neutral_site, conference_game, home_dog) plus the two line-shape variables the
model already prices (spread, censoring bias). Every cell tested is listed, and
**every split family tiles its variable** — no unreported middle bucket.
`neutralSite` is joined from `games_*.json` (it is absent from `lines_*.json`
but present there, same join pattern as `b4_features/probit_features.py`).

| cell | N | under% | 95% CI | vs BE |
|---|---|---|---|---|
| week ≤ 4 (early) | 1450 | 50.34% | [47.8, 52.9] | −2.02pp |
| week > 4 (late) | 3109 | 51.98% | [50.2, 53.7] | −0.38pp |
| conference game | 2996 | 52.44% | [50.6, 54.2] | +0.08pp |
| non-conference | 1563 | 49.58% | [47.1, 52.1] | −2.78pp |
| home dog | 1592 | 52.83% | [50.4, 55.3] | +0.47pp |
| home favorite | 2967 | 50.72% | [48.9, 52.5] | −1.64pp |
| neutral site | 124 | 55.65% | [46.9, 64.1] | +3.29pp |
| non-neutral site | 4435 | 51.34% | [49.9, 52.8] | −1.02pp |
| spread ≤ 7 (close) | 1653 | 53.36% | [50.9, 55.8] | +1.00pp |
| **spread 7–14 (middle)** | **1116** | **54.12%** | [51.2, 57.0] | **+1.76pp** |
| spread > 14 (lopsided) | 1790 | 48.04% | [45.7, 50.4] | −4.32pp |
| censoring bias < 0.25 | 3653 | 52.92% | [51.3, 54.5] | +0.56pp |
| censoring bias ≥ 0.25 | 906 | 45.58% | [42.4, 48.8] | −6.78pp |

Six cells clear break-even in-sample, none with raw p < 0.11 (best: spread 7–14
at p=0.119), all at **p_adj = 1.000**. `neutral site` at 55.65% is on N=124 with
a CI 17 points wide — noise.

The two largest effects in the table are the *negative* ones, and both are the
floor-bias model talking: censoring bias ≥ 0.25 gives 45.58% under (i.e. a 54.4%
**over** rate) and spread > 14 gives 48.04%. This is B6 [C] again — the under
side of a high-bias game is the wrong side of the edge v1 already prices.

## [D] Walk-forward — one lead survives, and still misses

Every cell clearing break-even in-sample went through the repo's walk-forward
protocol (decide season t using only seasons ≤ t−1). Note the gate is
deliberately **generous**: it bets when the prior-seasons point estimate clears
break-even, not on a Wilson lower bound as `monitor/` does. A cell failing here
fails the easy version.

| cell | in-sample | walk-forward | WF Wilson 95% CI |
|---|---|---|---|
| conference game | 52.44% | never bet | — |
| home dog | 52.83% | 55.29% on 170 bets | [47.79, 62.57] |
| spread ≤ 7 (close) | 53.36% | 51.59% on 818 bets | [48.17, 55.00] |
| **spread 7–14 (middle)** | **54.12%** | **54.11% on 730 bets** | **[50.48, 57.69]** |
| censoring bias < 0.25 | 52.92% | 50.96% on 1144 bets | [48.07, 53.85] |

Three cells collapse. `spread ≤ 7` and `censoring bias < 0.25` both fall below
break-even out-of-sample with real volume. `home dog`'s 55.29% is **a single
season** (2025, N=170, p=0.222) off a series swinging 39.66%–60.33%.

**`spread 7–14` is the one genuine lead, and it is reported as a lead, not an
edge.** It holds its in-sample rate out-of-sample almost exactly (54.12% →
54.11%) across 730 bets, and it is not one hot season — 7 of 8 walk-forward
seasons clear break-even, and 10 of 13 seasons overall:

```
2013 50.00  2014 52.75  2015 47.62  2016 57.32  2017 62.86  2018 54.32  2019 54.67
2020 53.70  2021 57.97  2022 42.45  2023 60.61  2024 57.29  2025 57.26   (N=54-139/season)
```

Why it is still not bettable:

- **MDE at N=1,116 is 56.08%.** The observed 54.12% sits *below what this sample
  could confirm* even if the effect were real — the exact failure mode B6 [A]
  documented, reproduced at a different N.
- Season block-bootstrap 95% CI **[50.53%, 57.31%]** straddles break-even. The
  walk-forward Wilson lower bound (50.48%) is below it too, so it would not pass
  `monitor/`'s actual gate.
- Raw one-sided p=0.119; **p_adj=1.000** over 26 comparisons. It was found by a
  scan, and the scan is priced in.
- It does not generalize outside the band: spread 7–14 across *all* totals is
  51.93% (N=3,183), and 50.00% for totals<55. The cell is a spread×totals
  interaction found by search, which is precisely the shape that does not
  replicate.

## Conclusion

No model change. Consistent with B6 and with the paper's asymmetry claim:
censoring is one-directional, so the under gets nothing from the mechanism, and
the totals level is mostly a proxy for the *absence* of the over edge that
`biasTotals` already prices.

What B7 adds over B6:

1. **The juice question is closed.** Real prices show no under shading at any
   totals level — 52.36% is the true hurdle, so B6's "unless books tilt price"
   caveat is resolved against the lead.
2. **The band null is conclusive, not underpowered.** B6 could only say "no edge
   demonstrable at N=977." At N=4,559 with MDE 54.20%, B7 rules out an edge of
   bettable size in the 55–65 band.
3. **The band's framing does not survive.** 55–65 is an arbitrary cut that
   bundles the losing 55–59 region with the one sub-bin that clears.
4. **One open lead is on the record.** Spread 7–14 inside the band is the only
   filter in either study to hold its rate across 730 out-of-sample bets and 10
   of 13 seasons. It is below its own MDE and dies under multiplicity, so it is
   filed as a lead — not acted on, not buried.

Filed alongside `b6_high_total_under/` and `saturation_bias/` as a negative
result with one documented open thread.

**What would reopen this.** For the band itself: nothing in this data — the MDE
gap and the walk-forward collapse both point the same way. For spread 7–14: it
needs **out-of-sample seasons, not a re-cut** — roughly 1,000+ additional games
in the cell (~8 seasons at current volume) to get MDE under the observed rate.
It should be treated as pre-registered going forward: the 2026 season is a clean
forward test of a filter fixed today, and that is the only cheap way to learn
whether it is real.
