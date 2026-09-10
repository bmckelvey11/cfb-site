# Spread magnitude vs. bet outcome: the edge is a dog-floor edge, and it stops at ~50

**Question, asked plainly:** in the backtest, what is the record on games with a
spread over 50?

**Answer: 19–19, 50.00%, −4.55% ROI on n=38.** Every other spread bucket is
profitable; this one is not. The record alone is underpowered, but the leg-level
decomposition behind it is not ambiguous, and it names a pre-game trigger the
[win-probability onset study](../2026-08-31_win_prob_onset/RESULTS.md) looked for
and did not find.

Run:
```
python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py
python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py --cut 45
```
Data: `docs/backtest_bets.csv` (written by `monitor/roi_report.py`), rows with
`passes_filter == 1` — the deployed rule, bias > 1.75, walk-forward
out-of-sample, seasons **2016–2025**, N=234, pushes dropped, every ROI priced at
−110 flat. The script's `ALL` row reproduces the pooled 234 / 151–83 / 64.53% /
+23.19% in [`docs/ROI_HITRATE.md`](../../docs/ROI_HITRATE.md), which is the check
that it is grading the same bets.

## [A] The record, by favorite-spread magnitude

Buckets are `(lo, hi]` and disjoint; the four rows sum to 234.

| spread | N | record | hit rate | hit-rate 95% | ROI |
|---|---:|---:|---:|---|---:|
| 0–30 | 8 | 5–3 | 62.50% | [29.5%, 88.1%] | +19.32% |
| 30–40 | 58 | 41–17 | 70.69% | [58.2%, 81.2%] | +34.95% |
| 40–50 | 130 | 86–44 | 66.15% | [57.7%, 73.9%] | +26.29% |
| **>50** | **38** | **19–19** | **50.00%** | **[34.6%, 65.4%]** | **−4.55%** |
| all | 234 | 151–83 | 64.53% | [58.3%, 70.5%] | +23.19% |

>50 against everything else is 19–19 vs 132–64, **Fisher two-sided p = 0.063**.
Not significant at 0.05. The two-sided test is the honest one here: the model's
own theory predicts this bucket should do *better*, since its mean expected bias
is higher (2.78 vs 2.27). Testing one-sided in the direction the data happened to
fall, against the prior's direction, would be picking the tail after the fact.

This is not "high bias underperforms." `ROI_HITRATE.md`'s >2.50 bias bin hits
63.64%. Spread magnitude carries information the bias bin does not.

## [B] Why — the favorite leg flips sign

The model is a **dog-floor** story: scoring censored at zero lifts the underdog
above its spread/total-implied points, so the total goes over. It asserts nothing
about the favorite; it takes the favorite at its implied number. Splitting
realized-minus-implied points into the two legs (`implied_team_points`, the
model's own split):

| spread | N | favorite error | underdog error | total error |
|---|---:|---:|---:|---:|
| 0–30 | 8 | −1.22 | +6.59 | +5.38 |
| 30–40 | 58 | +3.46 | +2.43 | +5.89 |
| 40–50 | 130 | +3.02 | +1.97 | +4.99 |
| **>50** | **38** | **−2.39** | **+2.70** | **+0.32** |

**The dog leg holds.** +2.70 in the >50 bucket, against +2.30 across everything
at or below 50 — slightly *stronger*, exactly as censoring theory says it should
be. The mechanism the model is built on does not break at extreme spreads.

**The favorite leg flips.** +3.0 below 50, **−2.39 above it.** In a 50-plus-point
mismatch the favorite stops being a fixed number and gets censored from above —
starters pulled, clock burned, second string in by the third quarter. That −2.39
eats the +2.70 dog gain, and the realized total lands **+0.32** against the posted
number instead of the +5.27 the model collects everywhere else. The market prices
these games correctly. There is nothing left to bet.

## [C] What this does *not* support

- **It is not a filter, and no filter was added.** n=38, and the interval
  [34.6%, 65.4%] contains both break-even (52.38%) and the pooled 64.53%. The
  record cannot distinguish "dead bucket" from "normal bucket, thin sample."
  The *leg decomposition* is the stronger evidence, not the win-loss.
- **The cut at 50 was not fitted.** It came from the question as asked, which is
  the one real mitigant against post-hoc subgroup selection here. It is not a
  tuned boundary and should not be read as one — `--cut 45` is there so the next
  reader can see how much the number moves.
- **"Spread >50" is confounded with FBS-vs-FCS.** Alabama State, Arkansas–Pine
  Bluff, The Citadel, Grambling, Bethune-Cookman, Samford, Mercer, Wagner. The
  causal variable might be the mismatch class, the roster-depth gap, or the
  coach's benching convention rather than the spread number itself. The spread is
  a usable *proxy* because it is known pre-game; it is not established as the
  cause.
- **It says nothing about where between 40 and 50 the effect starts.** 40–50 is
  healthy (+3.02 favorite error) and >50 is not; with 38 games above the line
  there is no power to locate a boundary inside that gap.

## [D] Why this matters more than n=38 suggests

The onset study closed with the favorite-shortfall fact confirmed but
unexploitable: *"no independent trigger to bet around... this analysis only
tested win-probability timing, and found that specific candidate collinear with
the outcome rather than causal or predictive of it."*

Spread magnitude is not collinear with the outcome. It is **posted before
kickoff**, on the same line the model already reads. That is the leading
indicator the onset study said it had not found — on a small sample, with a
confound named in [C], but it is a candidate of a different kind than
`onset_frac` was.

Worth a follow-up with real power: FBS-vs-FCS as a flag in its own right, graded
across every game rather than only the 38 that qualified, would separate the
mismatch class from the spread number and would not be limited to bets.

## [E] Live relevance as of this run

The 2026-09-10 board carries 12 picks; **3 sit in this bucket**, including the
top two by expected bias:

| pick | spread | total | bias |
|---|---:|---:|---:|
| Florida A&M @ Miami (FL) | −59.5 | 65.5 | 3.06 |
| Howard @ Indiana | −56.5 | 65.5 | 2.51 |
| Southern U @ Houston | −51.0 | 60.5 | 2.43 |

All three are FBS-vs-FCS. Per [C] this is not grounds to drop them, and the
board was not changed. It is grounds to know that the model's headline 64.5% is
not the number these three are drawing from.

---
Bets: `docs/backtest_bets.csv`, `passes_filter == 1`, bias > 1.75, 2016–2025,
N=234 | prices −110 flat | reproduced by `spread_magnitude.py` | generated
2026-09-10
