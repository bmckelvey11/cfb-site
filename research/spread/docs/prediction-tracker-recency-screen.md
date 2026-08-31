# Recency-weighted screening — results

Run 2026-08-29 by `scripts/eval_recency_screen.py`, implementing
`docs/prediction-tracker-model-eval-plan-addendum.md` **§11**, committed at `3bedfc6` before
any of this was fit. Prior results: `docs/prediction-tracker-combination-sweep.md`.

152 models — `lineca` and `linemidweek` excluded throughout as market lines (parent §10).
Walk-forward 2006–2025, season-level wild cluster bootstrap, 2000 draws.

---

## 1. The decisive diagnostic answers itself

§11.6 asked one question: **does the validation-selected retention factor beat ρ = 1.00 in
genuinely forward, season-by-season validation?**

> **ρ = 1.00 was selected in 20 of 20 seasons, on both benchmarks.**

Not a majority — every season, unanimously. The branch closes.

The raw grid says the same thing more loudly. Scoring every ρ at every k, ΔMSE vs R0
(negative = better), **opening line**:

| k | ρ=0.80 | 0.85 | 0.90 | 0.95 | 0.975 | 1.00 | grid-best |
|---|---|---|---|---|---|---|---|
| 5 | −1.871 | −1.818 | −1.742 | −1.726 | −1.887 | **−1.950** | 1.00 |
| 8 | **−2.100** | −2.076 | −2.004 | −1.890 | −1.892 | −1.857 | 0.80 |
| 12 | −1.725 | −1.735 | **−1.838** | −1.776 | −1.740 | −1.752 | 0.90 |
| 16 | −1.678 | **−1.680** | −1.655 | −1.643 | −1.610 | −1.611 | 0.85 |
| 20 | −1.527 | −1.572 | **−1.585** | −1.554 | −1.557 | −1.524 | 0.90 |
| 30 | −1.302 | −1.302 | −1.299 | −1.284 | −1.290 | **−1.309** | 1.00 |

**Closing line**:

| k | ρ=0.80 | 0.85 | 0.90 | 0.95 | 0.975 | 1.00 | grid-best |
|---|---|---|---|---|---|---|---|
| 5 | −0.227 | −0.276 | −0.260 | −0.262 | **−0.301** | −0.294 | 0.975 |
| 8 | −0.287 | **−0.291** | −0.273 | −0.276 | −0.276 | −0.268 | 0.85 |
| 12 | −0.154 | −0.136 | −0.156 | −0.166 | −0.160 | **−0.179** | 1.00 |
| 16 | **−0.163** | −0.144 | −0.124 | −0.111 | −0.111 | −0.130 | 0.80 |
| 20 | **−0.117** | −0.106 | −0.096 | −0.104 | −0.102 | −0.102 | 0.80 |
| 30 | **−0.072** | −0.060 | −0.061 | −0.058 | −0.054 | −0.052 | 0.80 |

The grid-best column is **noise**. It lands on 1.00, 0.80, 0.90, 0.85, 0.90, 1.00 for six
adjacent values of k on one benchmark — a real decay signal does not reverse direction as the
screen widens by four models. The spread across the whole ρ row is smaller than the spread
across k, and both are far inside the confidence intervals in §3.

This is precisely the case §11.6 named in advance: *"if the gain from decay is unstable and
concentrated, college football changed in level but not in the relative skill ordering of its
forecasters."* The measured 0.775 skill-rank persistence was already the answer.

---

## 2. Stability: nothing to adapt to

Giacomini–Rossi fluctuation test on the screened consensus's loss differential vs R0, rolling
windows of one third the evaluation span, bootstrap critical values:

| benchmark | statistic | p | verdict |
|---|---|---|---|
| opening | 1.281 | 0.7145 | no detected instability |
| closing | 0.966 | 0.9170 | no detected instability |

Relative performance is stable over time on **both** benchmarks. That is coherent with ρ = 1
winning: if the ordering does not drift, discounting old evidence only discards information.

---

## 3. Every specification, and none of them moves the closing line

k = 20 throughout. ΔMSE vs R0.

| specification | opening | | closing | |
|---|---|---|---|---|
| | Δ | p | Δ | p |
| **primary** (ρ=1, κ=1000, η=0, c=0.5, q=0) | **−1.524** [−2.921, −0.136] | **0.0280** | −0.102 [−0.303, +0.109] | 0.3135 |
| ρ = 0.90 | −1.585 [−2.911, −0.251] | 0.0190 | −0.096 | 0.3460 |
| two-window blend η = 0.5 | −1.490 | 0.0270 | −0.079 | 0.4150 |
| 5-season rolling | −1.532 | 0.0240 | −0.102 | 0.2755 |
| 10-season rolling | −1.580 | 0.0200 | −0.111 | 0.2860 |
| cohort-adjusted | −1.295 [−2.671, +0.051] | 0.0700 | −0.037 | 0.6690 |
| λ = 0 (no gap penalty) | −1.518 | 0.0305 | −0.112 | 0.2790 |
| λ = 0.5 | −1.540 | 0.0315 | −0.110 | 0.2705 |
| post-2014 only | −0.745 [−2.533, +1.083] | 0.5445 | +0.011 | 0.9280 |
| post-2021 only | +0.040 [−2.790, +2.871] | 0.9430 | +0.112 | 0.2555 |

**Closing line: nothing, in any specification.** Best is −0.112 at p = 0.28. This was stated
in advance (§11.0) as arithmetic rather than prediction — recency reorders the input to a
multiplication by a coefficient the validation drives to zero.

**Opening line: the effect holds at −1.52, p = 0.028**, consistent with the decontamination
check's −1.640. Every recency variant lands within ±0.09 of the primary. The machinery does
nothing that ρ = 1 with plain averaging did not already do.

### Coordinate refinements: all flat

At k = 20, opening line, each grid with the others at their defaults:

- **κ** (credibility) 500 → 4000: −1.559, −1.524, −1.530, −1.519
- **η** (recent blend) 1.0 → 0: −1.437, −1.510, −1.490, −1.525, −1.524
- **c** (uncertainty penalty) 0 → 1.0: −1.564, −1.524, −1.532
- **q** (new-entrant sleeve) 0.20 → 0: −1.439, −1.489, −1.509, −1.524

Every one is monotone-ish toward its conservative end and flat within noise. **The
new-entrant sleeve actively hurts at every size tested** — young models let into the
correction dilute it.

---

## 4. The cohort adjustment is the surprising failure

§11.4 fit persistent ability after removing season effects and an entry-year linear trend,
then ranked on that. The premise: a 2024 entrant has only operated in the current environment
and might look good for that reason alone.

**The data say the opposite, and the adjustment is destructive.**

| | opening Δ | closing Δ |
|---|---|---|
| plain screen | −1.524 (p=0.028) | −0.102 |
| cohort-adjusted | −1.295 (p=0.070) | −0.037 |

It also does not merely nudge the ordering — it replaces it. Overlap of the cohort-adjusted
top 8 with the plain top 8:

| season | overlap | plain top 3 | cohort top 3 |
|---|---|---|---|
| 2015 | 5/8 | linepibias, lineatom, linepimean | linepig, linebihl, lineash |
| 2020 | **1/8** | lineespn, lineteamrank, linepimean | linemass, linedokter, linesag |
| 2025 | 2/8 | lineespn, lineteamrank, linedokter | linedokter, linebihl, linesag |

The mechanism is legible. The plain screen's best models are **recent entrants** — `lineespn`
joined in 2015, `lineteamrank` in 2016. The entry-year trend treats their advantage as a
cohort effect and adjusts it away, promoting long-tenured models (`linesag`, `linemass`,
`linebihl`) that are simply worse. Newer models here are not flattered by an easier era; they
are genuinely better, and correcting for entry year discards real skill.

---

## 5. k, reported and not selected

§11.3 refused to tune k, because the sweep showed it is unidentifiable out-of-sample. Reported
across the grid, at ρ = 1:

| k | 5 | 8 | 12 | 16 | 20 | 30 |
|---|---|---|---|---|---|---|
| opening Δ | −1.950 | **−2.100** | −1.752 | −1.611 | −1.524 | −1.309 |
| closing Δ | −0.294 | −0.268 | −0.179 | −0.130 | −0.102 | −0.052 |

The opening-line effect is **strongest at a narrow screen and decays monotonically past k = 8**
— consistent with the panel having a genuinely poor tail. It is reported as a shape, not a
recommendation: the confidence intervals in §3 are ±1.4 wide and easily contain the whole row,
and the point of §11.3 was that inner validation cannot separate these values.

---

## 6. What the screen contains once the market lines are gone

Most recent top five: **`lineespn`, `lineteamrank`, `linedokter`, `linepimean`, `linepibias`.**

| model | entry | seasons |
|---|---|---|
| lineespn | 2015 | 10 |
| lineteamrank | 2016 | 10 |
| linedokter | 2006 | 20 |
| linepimean | 2013 | 13 |
| linepibias | 2013 | 13 |

These are the actual best forecasters in the panel, visible for the first time — every
previously published screen had the closing line ranked above all of them.

Fitted correction weight γ on the screened consensus, last three seasons: **0.404 / 0.362 /
0.367** against the opening line, **0.115 / 0.090 / 0.100** against the closing line. The
market absorbs roughly three quarters of what the panel knows.

---

## 7. Scorecard against §11.8

**1. "ρ = 1.00 will be selected in a majority of seasons" — confirmed, emphatically.** 20 of 20,
both benchmarks.

**2. "No recency scheme will change the closing-line null" — confirmed.** Best closing-line
figure across every specification is −0.112 at p = 0.28.

**3. "Giacomini–Rossi will reject stability on the opening line and not on the closing line" —
wrong.** It rejects on neither (p = 0.71 and 0.92). I expected the open/close asymmetry in
*level* to show up as instability over *time*; those are different things, and only the first
is present. The panel's advantage over the opening line is steady across 20 seasons, not
concentrated in an era.

**4. "The cohort trend will be small and will not reorder the top of the screen" — wrong on both
clauses.** It reorders the top 8 almost completely (1/8 overlap in 2020) and costs 15% of the
opening-line effect. §4 above.

---

## 8. What this changes

**Nothing about the headline, and that is the finding.** No recency scheme, rolling window,
credibility shrinkage, two-window blend, new-entrant sleeve or cohort adjustment moves the
closing-line result off zero. The 2001–2025 archive was never a stale-weights problem.

Three things are now measured rather than assumed:

1. **ρ = 1 was not a hidden assumption doing work.** Every published result implicitly used it;
   forward validation picks it unanimously when offered five alternatives.
2. **Relative forecaster skill is stable over 25 seasons** — Giacomini–Rossi finds no
   instability on either benchmark, matching the 0.775 rank persistence.
3. **Newer models are better, not luckier.** The cohort correction built to guard against
   era-flattered entrants removes genuine skill instead.

**One caveat that is not resolved and cannot be here.** The opening-line effect is −0.745
(p = 0.54) post-2014 and +0.040 (p = 0.94) post-2021. That is *consistent* with a fading
advantage, and also entirely consistent with noise — those windows carry intervals of roughly
±2.5 and ±2.9, which is the same underpowered-holdout problem the parent plan §6 documented.
Giacomini–Rossi, which is designed for exactly this question and uses the full span, finds no
instability. The honest statement is that the recent era cannot resolve an effect of this size,
not that the effect has gone.
