**Superseded by** [greenline-clv-all-eras-2026-09-23.md](../../research/totals/docs/greenline-clv-all-eras-2026-09-23.md) — the "corrupt" GraphQL closes this doc gates are in-game totals at every GraphQL-only book, and the book median it gates against is contaminated the same way.

# Greenline totals vs a real market close — and whether the feed needs filtering

2026-09-22

## Question

Two questions, and the second one had to be settled before the first could be trusted.

1. **Do PFF Greenline's totals flags beat a real market close?** Every CLV number in this
   tree so far is measured against PFF's *own* board close, which asks whether PFF agrees
   with itself. This is the first measurement against books.
2. **Does the Pinnacle feed need filtering, or is that caution theatre?** About one Pinnacle
   `total_close` row in nine disagrees wildly with every other book on the same game
   ([greenline-findings.md](greenline-findings.md), "Open question A"). Testing the gate
   rather than assuming it was the explicit ask.

**Answers: the gate is required, and once it is applied the CLV is zero.**

## The gate is required, and here is the proof

Four policies over the same 106 graded 2026 flags. They differ only in what they do with a
Pinnacle close the other books contradict.

| policy | what it does | scored | mean CLV (pts, 95%) | beat-lost-flat | worst single CLV |
| --- | --- | ---: | ---: | ---: | ---: |
| `none` | trust every Pinnacle close | 97 | **+0.24 ± 1.02** | 44-27-26 | **+27.0** |
| `drop` | exclude contradicted games | 79 | +0.06 ± 0.48 | 35-18-26 | −15.0 |
| `substitute` | fall back to the book median | 106 | −0.17 ± 0.44 | 45-31-30 | −15.0 |
| `consensus` | never use Pinnacle | 106 | −0.20 ± 0.44 | 41-28-37 | −15.0 |

**Ungated is the only row that looks like an edge, and it is manufactured.** The 18 flags the
gate removes carry a mean CLV of **+1.06** on their own — four times the ungated mean they
are inflating — and span −15.0 to +27.0 points. A game total does not move fifteen points,
let alone twenty-seven. These are feed bugs wearing the shape of enormous line value:

| matchup | side | capture | "Pinnacle close" | book median | CLV it would have scored |
| --- | --- | ---: | ---: | ---: | ---: |
| WKU @ UGA | over | 55.5 | 82.5 | 56.0 | **+27.0** |
| SDSU @ UCLA | under | 55.5 | 33.5 | 53.5 | **+22.0** |
| ASU @ TXAM | under | 50.5 | 65.5 | 51.5 | −15.0 |
| ODU @ VT | under | 49.5 | 63.5 | 55.0 | −14.0 |
| TT @ ORST | under | 53.5 | 40.5 | 52.5 | +13.0 |

The bad rows also inflate the error bar: **±1.02 ungated against ±0.48 gated**. Eighteen rows
out of ninety-seven double the width of the interval, which is what a handful of ±20-point
observations does to a mean.

**The gate is not sensitive to where it is set**, which is the other thing worth knowing —
the result is not an artefact of picking 1.0 points:

| tolerance (pts) | scored | mean CLV | beat rate |
| ---: | ---: | ---: | ---: |
| 0.5 | 72 | +0.06 | 67% |
| 1.0 | 79 | +0.06 | 66% |
| 2.0 | 83 | −0.04 | 63% |
| 3.0 | 86 | −0.02 | 63% |
| 5.0 | 88 | +0.09 | 65% |

Anywhere from half a point to five points of tolerance gives the same answer. Only *no* gate
gives a different one.

## The answer: no CLV clears its own detection floor, except one split that does

Default policy (`drop`, tolerance 1.0): **79 of 106 flags scored** — 18 dropped for
contradicting the books, 9 with no Pinnacle row at all. `mde` is the smallest true mean CLV
(pts) this split's n would detect 80% of the time, one-sided; a mean inside its own mde is a
bound, not a measurement of zero.

| split | n | mean CLV (pts, 95%) | mde (pts) | ~win prob | beat-lost-flat |
| --- | ---: | ---: | ---: | ---: | ---: |
| **all flags** | 79 | **+0.06 ± 0.48** | 0.61 | +0.2pp | 35-18-26 |
| unders | 65 | −0.02 ± 0.56 | 0.71 | −0.1pp | 30-15-20 |
| overs | 14 | +0.43 ± 0.77 | 0.97 | +1.7pp | 5-3-6 |
| week 2 | 24 | −0.62 ± 1.47 | 1.87 | −2.5pp | 9-10-5 |
| week 3 | 55 | +0.35 ± 0.25 | 0.31 | +1.4pp | 26-8-21 |

**+0.06 points, interval −0.42 to +0.54, mde 0.61.** The mean sits well inside its own
detection floor: this split could not have distinguished +0.06 from a true CLV as large as
0.61 points either way, so "zero" is a bound this n imposes, not a measured zero. Every
gated policy still agrees in sign and magnitude — −0.20, −0.17, +0.06 — none clears its own
mde, and the three policies bracket the answer tightly enough that the choice between them
does not matter.

**Week 3 alone does not fit that pattern.** +0.35 ± 0.25 against an mde of 0.31 means the
mean *exceeds* its own 80%-power threshold — one-sided p ≈ 0.003 on n=55, unadjusted. Week 2
is the opposite sign and larger (−0.62 ± 1.47, mde 1.87, itself uninformative). Two weekly
splits is not enough to call a trend, and no correction has been applied across them, so this
is registered as a thing to watch — not reweighted into the headline number — rather than
smoothed into "which is what noise looks like at this size." If week 4 lands positive again
at a similar magnitude, this stops being dismissible on multiplicity grounds alone.

**Beating the close does not predict winning the bet**: flags that beat the close went 20-15
(57.1%), flags that lost to it went 11-7 (61.1%). These are two views of the same picks, so
this is a consistency check rather than evidence — but a real CLV signal would not usually
run backwards.

## What this does not support

- **Not a refutation of the pooled 54.0% record.** CLV and hit rate are different
  measurements. This says the flags do not anticipate market movement; it does not say they
  lose.
- **Not a verdict on 2020 or 2022-23.** Pinnacle closes exist only from 2025 week 8. This is
  a 2026-weeks-2-and-3 measurement, 79 picks, and cannot reach the archive eras.
- **Not a clean read on the 27 unscored flags.** The 18 dropped are dropped *because* their
  close is unknown, not because it was extreme — if the underlying true closes were
  available the mean could move. The `substitute` and `consensus` rows, which score all 106
  by using the book median, are the check on that, and they come back slightly negative.
- **Not a statement about executable prices.** The close here is a number, not a price
  anyone was filled at.
- **Not independent of the loader bug.** A task is open to fix the corrupt Pinnacle rows at
  the source. If that lands, re-run and the gate should start dropping far fewer games.

## Method

`research/totals/scripts/greenline_clv.py`. 106 graded 2026 flags from
`greenline_graded.csv`, resolved to CFBD games through `pff_franchise.cfbd_team_id` (the
ledger's own resolver, reused rather than re-implemented — PFF and the books disagree on
dozens of abbreviations). Closes from `core.fact_game_line`, all providers, season 2026.

Sign convention, which is the easy thing to get backwards: positive CLV means the market
moved toward the flagged side, so the captured number beat the close. For an under that is
`capture − close`; for an over, `close − capture`. `--self-check` pins both directions plus
the push case, every gate policy against the known-good and known-bad shapes (Western
Kentucky at Georgia must never score under any policy but `none`), the NaN guard the
`stg_gql` feed requires, and that the gate's accounting adds back up to 106.

The `~win prob` column applies the unit's standing conversion — half a point of total is
worth about two points of win probability — and is a scale aid, not a measurement.

Reproduce:

```bash
python research/totals/scripts/greenline_clv.py --compare
```
