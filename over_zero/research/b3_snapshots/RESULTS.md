# B3: Open-to-close totals drift, from raw historical data — Results

Owner-approved deviation from the original plan's B3.1 (`capture_odds.py`,
live snapshot loop requiring `ODDS_API_KEY`) and B3.2 (`analyze_drift.py`).
See `research/BLOCKERS.md`, entry "2026-07-31 — B3.1 (odds snapshot capture)
— plan deviation, owner-approved", for the rationale. This driver computes
the same open-vs-close comparison directly from `../cfb-site/data/raw/lines_
{season}.json`, which already carries per-book `overUnderOpen`/`overUnder`
historically, instead of accumulating snapshots forward.

## Command

```
python research/b3_snapshots/drift_from_raw.py
```

## Output (verbatim)

```
season 2013:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,174
season 2014:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,190
season 2015:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,198
season 2016:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,225
season 2017:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,289
season 2018:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,887
season 2019:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=3,306
season 2020:  book-pairs kept(ALL)=0  kept(QUALIFYING)=0  skipped(null open/close)=2,634
season 2021:  book-pairs kept(ALL)=841  kept(QUALIFYING)=73  skipped(null open/close)=2,548
season 2022:  book-pairs kept(ALL)=811  kept(QUALIFYING)=50  skipped(null open/close)=3,323
season 2023:  book-pairs kept(ALL)=1,267  kept(QUALIFYING)=89  skipped(null open/close)=1,667
season 2024:  book-pairs kept(ALL)=1,660  kept(QUALIFYING)=112  skipped(null open/close)=1,370
season 2025:  book-pairs kept(ALL)=1,877  kept(QUALIFYING)=190  skipped(null open/close)=1,468

=== PER-SEASON BREAKDOWN ===
season 2013:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2014:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2015:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2016:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2017:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2018:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2019:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2020:
  ALL       : n=0 (insufficient data)
  QUALIFYING: n=0 (insufficient data)
season 2021:
  ALL       : n=841  mean=+0.1581  SE=0.0686  95% CI [+0.0237, +0.2926]
  QUALIFYING: n=73  mean=+0.0274  SE=0.1406  95% CI [-0.2482, +0.3030]
season 2022:
  ALL       : n=811  mean=-0.3872  SE=0.0846  95% CI [-0.5529, -0.2214]
  QUALIFYING: n=50  mean=-0.4600  SE=0.2951  95% CI [-1.0385, +0.1185]
season 2023:
  ALL       : n=1,267  mean=-0.6519  SE=0.0567  95% CI [-0.7631, -0.5407]
  QUALIFYING: n=89  mean=-0.4438  SE=0.2216  95% CI [-0.8782, -0.0094]
season 2024:
  ALL       : n=1,660  mean=-0.4289  SE=0.0488  95% CI [-0.5245, -0.3333]
  QUALIFYING: n=112  mean=+0.5134  SE=0.2058  95% CI [+0.1100, +0.9168]
season 2025:
  ALL       : n=1,877  mean=-0.3796  SE=0.0523  95% CI [-0.4822, -0.2770]
  QUALIFYING: n=190  mean=+0.3763  SE=0.1640  95% CI [+0.0550, +0.6977]

=== POOLED (all seasons) ===
  ALL       : n=6,456  mean=-0.3766  SE=0.0267  95% CI [-0.4290, -0.3243]
  QUALIFYING: n=514  mean=+0.1333  SE=0.0928  95% CI [-0.0486, +0.3151]
  total book-pairs skipped (null overUnderOpen or overUnder): 30,279
```

## 1. Pooled ALL-games drift stats

n = 6,456 book-game pairs. Mean drift = **-0.3766** points (total *fell*
toward close on average), SE = 0.0267, 95% CI **[-0.4290, -0.3243]** —
entirely below zero, i.e. statistically distinguishable from no drift.

## 2. Pooled QUALIFYING-games drift stats

n = 514 book-game pairs (games where the closing consensus line's implied
censoring bias exceeds 1.0). Mean drift = **+0.1333** points, SE = 0.0928,
95% CI **[-0.0486, +0.3151]** — straddles zero. Not statistically
distinguishable from no drift at this sample size.

## 3. Per-season breakdown (both populations)

| Season | ALL n | ALL mean | ALL 95% CI | QUAL n | QUAL mean | QUAL 95% CI |
|---|---|---|---|---|---|---|
| 2013–2020 | 0 | — | no data | 0 | — | no data |
| 2021 | 841 | +0.1581 | [+0.0237, +0.2926] | 73 | +0.0274 | [-0.2482, +0.3030] |
| 2022 | 811 | -0.3872 | [-0.5529, -0.2214] | 50 | -0.4600 | [-1.0385, +0.1185] |
| 2023 | 1,267 | -0.6519 | [-0.7631, -0.5407] | 89 | -0.4438 | [-0.8782, -0.0094] |
| 2024 | 1,660 | -0.4289 | [-0.5245, -0.3333] | 112 | +0.5134 | [+0.1100, +0.9168] |
| 2025 | 1,877 | -0.3796 | [-0.4822, -0.2770] | 190 | +0.3763 | [+0.0550, +0.6977] |

**Data availability caveat:** `overUnderOpen` is entirely `null` for every
book-game pair in seasons 2013–2020 in this raw data source (verified by
direct scan: 0 of 2,174–3,306 book entries per season carry a non-null
opening total). Opening-total coverage only begins in 2021, and even then is
provider-limited — only `Bovada` carries `overUnderOpen` in 2021–2022;
`DraftKings` joins in 2023; `ESPN Bet` joins in 2024–2025. So "per season"
here effectively means 2021–2025 (5 seasons), not 2013–2025 (13 seasons) as
originally scoped — the earlier 8 seasons contribute zero drift observations,
not a null result, because the field itself is absent from the source data
for that period. Separately: in 2023–2025 up to three books contribute a
drift observation per game, so book-game pairs are not fully independent
within a game and the nominal 95% CI is mildly anti-conservative in those
seasons (2021–2022 are single-book, so unaffected there). Since 76% of the
pooled QUALIFYING n = 514 comes from these multi-book seasons
(2023–2025: n = 89 + 112 + 190 = 391), this caveat also applies to the
pooled CI reported above, not just the per-season ones — the true pooled CI
is somewhat wider than reported. This widening only reinforces the null
conclusion, moving the CI further from significance rather than toward it.

**Stability across years:** the ALL-games sign is not stable — 2021 is
positive, 2022–2025 are all negative — and the QUALIFYING-games sign flips
too (2021–2023 negative or near-zero, 2024–2025 positive, both with wide
CIs). Neither population shows a consistent year-over-year direction, which
argues against reading either the pooled ALL or pooled QUALIFYING sign as a
reflection of one stable market phenomenon over time; it is more consistent
with season-level noise (and/or provider-mix composition changing year to
year, since which books contribute qualifying pairs changes across seasons).

**Selection-on-outcome caveat:** the QUALIFYING population is selected using
`pick_line(g)`'s **closing** total to compute the bias filter (bias > 1.0),
but the outcome being measured is `drift = close - open`, which also
contains that same closing total. This means the QUALIFYING sample is
conditioned on a function of the closing line while the closing line is
also part of the outcome — selection-on-outcome — which mechanically shifts
the QUALIFYING drift distribution relative to an unconditional one. This is
inherited from the original plan's B3.2 design (which computes the bias
filter "at the LAST snapshot," i.e. close), not a new defect introduced by
this raw-data driver. It does not change the reported null verdict below
(the CI already straddles zero), but the QUALIFYING drift distribution
should be understood as a design property of the conditioning, not a
directly comparable, unconditionally-sampled drift distribution.

## 4. Verdict (applying the fixed interpretation)

Per the brief's fixed interpretation: positive mean drift on **qualifying**
games means totals rise toward close, i.e. the early number was better for
the over bettor; negative means the close is the better number.

Pooled QUALIFYING result: mean drift **+0.1333**, 95% CI **[-0.0486,
+0.3151]** — straddles zero. This is a **null result**: at the pooled
n = 514 available (limited to 2021–2025, and further limited within those
years to games meeting the qualifying-bias filter), there is no
statistically or practically meaningful evidence that closing totals differ
from opening totals in either direction on qualifying games. The point
estimate's sign (positive, nominally favoring "early is better for the
over") should not be treated as a finding — the CI includes zero, and the
per-season breakdown shows the sign flipping between 2021–2023 (negative or
near-zero) and 2024–2025 (positive). The sign flip between 2021–2023 and 2024–2025 is consistent with
season-level noise given the small per-season n; provider mix also changes
across some years (DraftKings joins in 2023, ESPN Bet in 2024 — see the
data availability caveat above), but this hypothesis was never tested
against a provider-stratified breakdown. Notably, the 2021→2022 flip occurs
with no provider-mix change at all (both seasons are Bovada-only), so
provider mix cannot be the sole driver of the apparent shift.

The pooled ALL-games CI (entirely negative, [-0.4290, -0.3243]) is
statistically clean but is the wrong population for this interpretation —
it mixes in games with no meaningful censoring bias, where drift is
expected to reflect ordinary market movement (injuries, weather, sharp
money) unrelated to the bias phenomenon this plan is investigating. It is
reported for completeness (per the brief's "for both populations") but the
brief's fixed interpretation is scoped to QUALIFYING games specifically, and
that population's result is null.

**Bottom line: no usable open-to-close drift edge is detected on qualifying
games in this data.** This is reported plainly as the negative/null result
it is, per this plan's standing instruction that null results receive the
same care as positive ones.

## 5. Open question 5 (juice/price) — unanswered, remains open

This data source (`../cfb-site/data/raw/lines_{season}.json`) carries no
per-book price/juice field alongside `overUnderOpen`/`overUnder` — only
`awayMoneyline`, `formattedSpread`, `homeMoneyline`, `overUnder`,
`overUnderOpen`, `provider`, `spread`, `spreadOpen` exist per book entry (per
B1.1/B2.1's confirmed key inventory). There is no field recording the
odds/vig posted alongside the over or under side at either open or close.
Open question 5 — does the market already shade the over past -110? —
**cannot be answered from this data source** and is not estimated or
inferred here.

The original plan's `capture_odds.py` (live capture against
the-odds-api.com, requiring `ODDS_API_KEY`) plus `analyze_drift.py` (not
built under this deviation) remain a valid path to answer open question 5
if `ODDS_API_KEY` becomes available later — the-odds-api.com's odds
endpoints do return per-side price, which this historical raw-data source
does not.
