# Analysis plan: crosswind vs head/tail wind and scoring

- **Date:** 2026-09-08
- **Author:** bmckelvey11
- **Status:** approved

Does a high wind's *orientation relative to the field* matter to scoring, and if
so does the market already price it? Motivated by the `wind_cross_mph` /
`wind_along_mph` features added in `af81970`.

## 1. Estimand

Two coefficients, `beta_cross` and `beta_along`, in points of game total per mph
of wind blowing sideline-to-sideline and goalpost-to-goalpost respectively, and
their difference `beta_cross - beta_along`.

Population: FBS-inclusive CFB games 2012-2025 that are played outdoors, have a
closing total from the selected provider, have a final score, and sit at a venue
whose field azimuth passes the orientation quality gate in
`cfb_system_maker/wind.py` (OSM match is a football pitch within 50m). n = 9,927.
That is roughly 72% of the 13,802 games in `games.csv`; the excluded games are
domes and venues with no trustworthy OSM pitch, not a scoring-related filter.

Conditioning set: closing total, temperature, precipitation, season.

**The estimand is conditional association, not a causal effect.** See section 8.

## 2. Model specification

Primary outcome is the **market residual**, `total_points - closing_total`. This
is the betting-relevant quantity: it asks whether wind orientation predicts
scoring *beyond what the closing line already priced*. A market that fully prices
wind gives `beta_cross = beta_along = 0` here even if wind hammers scoring.

```
total_points - closing_total ~ beta_cross * wind_cross_mph
                             + beta_along * wind_along_mph
                             + temperature + precipitation
                             + season fixed effects
```

Linear in both components, decided from the physics rather than from fit: the
components are already `speed * cos(angle)` and `speed * sin(angle)`, so the
speed-by-geometry interaction the question asks about is built into the
regressors. No separate `speed x class` interaction term is needed, and the
30/60-degree class cuts are not used in the primary spec at all.

Secondary outcome (descriptive): raw `total_points`, same regressors plus
`closing_total` as a control. This separates "wind suppresses scoring" from
"the market misses wind".

**"When the wind gets high"** is answered by a pre-specified stratification, not
by adding quadratic terms: refit within wind-speed buckets 0-7, 7-12, 12-18, 18+
mph and report `beta_cross` and `beta_along` per bucket with CIs. Bucket edges
chosen from the speed distribution (mean 8.0, p90 14.4) before fitting.

Controls deliberately excluded: team quality, pace, conference. The closing total
already prices all of them, and in the primary spec it is the baseline being
differenced away.

Build should check: residual normality is not required at this n, but report
RESET for functional form and VIF for `wind_cross_mph` vs `wind_along_mph`
(expected low — the two components are close to orthogonal by construction).

## 3. Dependence structure

Games are clustered by **venue**: field azimuth is venue-constant by definition,
and local wind climate is too, so two games at the same stadium share both the
regressor's construction and its weather-generating process. 210 venue clusters,
mean 47.3 games each — far above the ~40 where cluster-robust SEs get unreliable,
so CR1 sandwich SEs, no wild bootstrap needed.

Measured within-venue ICC of the market residual is 0.000 (one-way ANOVA), so the
design effect is near 1 and clustering will barely move the SEs. Cluster anyway:
the ICC being small is a finding, not an assumption to bake in.

Season enters as fixed effects, absorbing rule changes and league-wide scoring
drift.

## 4. Primary metric + benchmark

Primary decision statistic: `beta_cross` and `beta_along` from the market-residual
spec, each with a 95% cluster-robust CI, plus the CI on their difference.

Benchmark is the **closing total** — the strongest available. Beating a naive
"average total" baseline would prove nothing.

Secondary and explicitly descriptive, never the decision: the raw-points spec,
the per-bucket estimates, and any hit-rate or ROI figure.

## 5. Multiplicity budget

Pre-committed: **2 primary tests** (`beta_cross`, `beta_along` on the market
residual, full sample), Holm-corrected.

Everything else is descriptive and reported without a decision attached: 2
coefficients x 4 speed buckets = 8 bucket estimates, plus 2 coefficients on the
raw-points spec. Total 12 numbers, 2 of which carry a decision. No subgroup or
bucket result is promoted to a finding without a fresh out-of-sample test.

No repeated looks: one fit, one report.

## 6. Pre-run power / MDE

`power_calc.py --sd 16.34 --n 9927 --cluster-size 47.3 --icc 0.002`
gives design effect 1.09 and MDE 0.480 points on the mean scale. Converting to
the coefficient scale by SD(`wind_cross_mph`) = 4.20 mph:

**MDE at planned N:** 0.114 points of total per mph of crosswind
(equivalently 0.48 points per 1-SD swing in crosswind; 1.7 points across a
15 mph crosswind).

**Smallest effect worth shipping:** ~1 point of total across a strong (15 mph)
wind, i.e. 0.067 points per mph. That is *below* the MDE, so the full-sample
design can detect a 1.7-point effect but not a 1.0-point one. Stated before
fitting: a null here rules out large effects, not small ones, and the per-bucket
estimates (n per bucket well under 9,927) are underpowered by construction and
are descriptive only.

## 7. Stop rule / evaluation window

Seasons 2012-2025, fixed in advance, all of them. One fit per specification, no
peeking and re-cutting. If a bucket result looks interesting, the confirmation
plan is a fresh season, not a re-slice of these.

## 8. Identification status

**Conditional association.** No instrument, no cutoff, no randomization.

Wind speed is plausibly close to as-good-as-random within a venue-season, but
wind *orientation relative to the field* is not manipulated and correlates with
geography and time of season. Season FE and venue clustering handle some of it;
temperature and precipitation controls handle the obvious weather confounds. What
remains is a conditional correlation, and the writeup must say "associated with",
never "causes".

The market-residual outcome is a partial defense: any confounder that the betting
market already prices is differenced out of the primary spec.

---

## Results

Run 2026-09-08 via `python scripts/analyze_wind_totals.py`. n = 9,927 games,
210 venue clusters, seasons 2012-2025.

### Primary — market residual, full sample

| coefficient | estimate (pts/mph) | SE | 95% CI | Holm p |
|---|---:|---:|---|---:|
| `beta_cross` | -0.0667 | 0.0354 | [-0.1361, +0.0026] | 0.119 |
| `beta_along` | +0.0249 | 0.0399 | [-0.0534, +0.1032] | 0.534 |
| difference | -0.0916 | 0.0584 | [-0.2062, +0.0229] | — |

**Neither primary test rejects.** Crosswind points the physically expected way —
more crosswind, fewer points than the market priced — and its coefficient is
about 2.7x the along-axis one with the opposite sign, but the CI crosses zero.

Pre-registered MDE was 0.114 pts/mph. The observed `beta_cross` of 0.067 is
**below** it, exactly the case section 6 flagged in advance: this design can rule
out a crosswind effect larger than ~1.7 points across a 15 mph wind, and cannot
resolve one around 1 point. **This is not evidence of no effect.**

### Diagnostic — is the pipeline blind?

Same spec, raw wind speed instead of the two components:

| term | estimate | SE | 95% CI |
|---|---:|---:|---|
| `wind_speed` | -0.0265 pts/mph | 0.0308 | [-0.0869, +0.0339] |
| `temperature` | +0.0108 pts/degF | 0.0098 | [-0.0084, +0.0299] |
| `precipitation` | -18.50 pts/unit | 5.40 | [-29.09, -7.91] |

The pipeline is **not** blind: precipitation lands hard and well clear of zero on
the same outcome, same clusters. So the wind nulls are real nulls-in-the-noise,
not a broken join.

Two readings follow. First, **the market prices raw wind speed** — `wind_speed`
alone is ~0 against the closing total. Second, that is why the orientation split
is the only place a residual edge could hide: if the market conditions on speed
but not geometry, the miss shows up as `beta_cross != beta_along`, which is the
difference row above (-0.092, CI [-0.206, +0.023]). Suggestive, not established.

### Descriptive — raw points, closing total as control

`beta_cross` -0.0739, CI [-0.1442, -0.0036]; `beta_along` +0.0194, CI
[-0.0599, +0.0987]. The crosswind CI excludes zero here, but this is the same
9,927 games under a second specification, not independent confirmation, and per
section 4 it carries no decision.

### Descriptive — by wind-speed bucket

Answering "does it bite harder when the wind gets high":

| bucket | n | `beta_cross` | `beta_along` | difference (CI) |
|---|---:|---:|---:|---|
| 0-7 mph | 4,467 | +0.269 | +0.026 | +0.243 [-0.127, +0.612] |
| 7-12 mph | 3,654 | -0.212 | -0.072 | -0.140 [-0.322, +0.043] |
| 12-18 mph | 1,415 | +0.174 | +0.320 | -0.146 [-0.329, +0.037] |
| 18+ mph | 391 | +0.135 | +0.163 | -0.028 [-0.326, +0.269] |

**No.** Signs flip bucket to bucket, every difference CI spans zero, and the
strongest-wind bucket has the *smallest* orientation gap on 391 games. The one
CI that excludes zero (`beta_cross` at 0-7 mph, +0.269, [+0.004, +0.535]) is
positive at *low* wind — physically backwards, and 1 of 8 uncorrected descriptive
estimates. Noise.

Note the linear primary spec already lets the effect grow with speed: the
regressors are `speed * cos(angle)` and `speed * sin(angle)`. The buckets test
whether it grows *faster than linearly*, and nothing here says it does.

### Verdict

Crosswind is the right place to look and the sign is right, but at this sample
size the effect — if it exists — is smaller than the design can resolve. Do not
ship a wind-orientation filter on this evidence.

What would settle it, in rough order of cost:

1. **Recover the excluded games.** 3,875 of 13,802 games are dropped for a
   missing or untrustworthy field azimuth (301 venues with no OSM match). A
   proper Overpass puller for `data/raw/venue_orientation.json` would add roughly
   40% more sample and cut the MDE by about 15%. Still short of resolving a
   1-point effect on its own.
2. **A sharper outcome than game total.** Kicking is where crosswind should bite
   hardest, and field-goal attempts are individually noisy but numerous. FG rate
   or FG-distance-adjusted make rate against crosswind has far more events per
   game than one total, so the MDE falls a lot faster than sample-count alone
   suggests.
3. **Second-half / late-game splits**, where wind has had time to matter and the
   market's pregame number is staler.

Out of scope but worth its own look: **precipitation at -18.5 points per unit
against the closing total** is a much larger and cleaner signal than anything
wind-related here. That is a real finding this analysis was not designed to test
and did not correct for — treat it as a lead, not a result.
