# B6 — ">66 totals line → bet the under" lead: NULL

Tests the under-side lead surfaced during the floor-bias work
(`docs/floor_bias_1h_chat_history.md:980-987`: >66 line → 54.15% under, N=977).

Run: `python research/b6_high_total_under/test_high_total_under.py`
Data: `data/raw/lines_{2013..2025}.json`, 12,493 usable games / 12,372 after pushes.

**Verdict: not a bettable edge.** The 54.15% replicates exactly, but it does not
clear break-even at realistic juice and does not survive inference. There is a
weak, genuine totals-level gradient underneath it — too small to bet.

## [A] The bin replicates and still loses

| totals line | N | under% | 95% CI | vs −110 (52.38%) | vs −120 (54.55%) |
|---|---|---|---|---|---|
| 0–45 | 1281 | 50.59% | [47.8, 53.3] | −1.79pp | −3.96pp |
| 45–59 | 7868 | 50.18% | [49.1, 51.3] | −2.20pp | −4.37pp |
| 59–66 | 2246 | 52.49% | [50.4, 54.6] | +0.11pp | −2.06pp |
| **>66** | **977** | **54.15%** | [51.0, 57.2] | **+1.77pp** | **−0.40pp** |

- vs −110: z=1.10, one-sided **p=0.135**. Not significant.
- The bin was picked by eye from a 4-bin totals scan on the same data that
  produced the floor-bias result, on top of a 5-bin spread scan — 9 prior
  comparisons. Bonferroni **p_adj = 1.000**.
- Season block-bootstrap 95% CI **[51.58%, 56.52%]** — straddles both break-evens.
- **MDE at N=977 is 56.35%.** The observed point estimate is below what this
  sample could confirm even if the effect were real.
- **At −120 the point estimate is already a loser** (break-even 54.55% > 54.15%).
  The pptx v2 juice scenario kills it before any inference question.

## [B] Continuous probit — a weak gradient, far too small to bet

`P(under) = Φ(const + slope·totalsEst)`, slope **+0.003279 per point**
(unclustered SE 0.001435, z=+2.28, p=0.0224). Season block-bootstrap 95% CI
**[+0.000130, +0.006115]** per point — excludes zero, but the lower bound sits
essentially at it. So the totals level carries some signal and this isn't purely
a bin artifact, but the evidence is weak once season clustering is respected.

Effect size is the real problem: implied P(under) moves 49.93% → 51.98% across
±1σ of the totals line (47 → 63). That never reaches 52.38%. A gradient too
small to cross the hurdle is not a strategy.

Two caveats against reading more into this slope. The bins are not monotone at
the low end (0–45 at 50.59% sits *above* 45–59 at 50.18%), so a linear-in-level
probit is fitting a non-monotone pattern. And the reported `const=+0.0239` is on
the standardized scale while the slope is in raw points — the implied
probabilities above are computed correctly in-script, but don't combine that
printed pair by hand.

## [C] It is largely the floor-bias edge read backwards

High totals lines are nearly the complement of the floor-bias sweet spot: mean
censoring bias is **0.073** for totals>66 vs **0.300** for totals≤66.

| stratum | N | under% |
|---|---|---|
| totals>66 & bias<0.25 | 902 | 54.88% |
| totals>66 & bias≥0.25 | 75 | 45.33% |
| totals≤66 & bias<0.25 | 7549 | 52.15% |
| totals≤66 & bias≥0.25 | 3846 | 47.79% |

The dominant split is bias, not totals level: within low-bias games the >66
premium over the rest is only 54.88% vs 52.15% (+2.7pp), and restricting the
probit to bias<0.25 drops the slope to z=+1.62, **p=0.106** — no longer
significant. Most of what looked like a "high totals under edge" is the absence
of the over edge, which the v1 model already prices via `biasTotals`.

## Conclusion

Consistent with the paper's asymmetry claim. Censoring is one-directional, so
the under gets nothing from that mechanism; the totals-level gradient is a
separate, weakly-evidenced, sub-hurdle effect that mostly dissolves once
censoring bias is controlled. No model change. Filed alongside
`saturation_bias/` as a clean negative result.

**What this null does and does not say.** It says no edge is *demonstrable* at
N=977 — not that the true edge is zero. It also assumes symmetric −110/−120
juice; if books tilt price toward the over on high totals, the under's real
hurdle in that exact bin is lower than assumed here. Neither rescues the lead:
the MDE gap and the [C] dissolution are both juice-independent. Reopening this
would need materially more high-total games or per-book prices, not a different
cut of the same data.
