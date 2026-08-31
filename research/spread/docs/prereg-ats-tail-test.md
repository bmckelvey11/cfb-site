# Pre-registration — is there an actionable ATS edge in the disagreement tail?

**Written and committed before running the test.** Everything in this repo's defect ledger
argues for doing this; defect 8 was a post-hoc narrowing caught only by an outside reviewer.

## The question

The combination work measured **squared error**. Betting is decided by **sign against a
threshold**. Those are different objectives, and a method can be near-null on MSE while still
being profitable — or, more likely, the reverse. This tests the betting objective directly.

The specific actionable hypothesis: the screened consensus (E4) has no edge on average against
the closing line, but its edge may **concentrate in games where it disagrees most with the
market**. If it does, the actionable rule is "bet only when |edge| exceeds some threshold."

## Data

`pt_ensemble_spread_closing.csv` — 12,803 walk-forward out-of-sample predictions, 2006–2025.
Already generated; this test adds no new fitting. Closing line only. The opening line is
excluded on purpose: the timing problem makes it unactionable regardless of the result, and
`scripts/predict_upcoming.py` week 1 shows `corr(line move, edge_vs_open) = +0.988`.

## Bet rule

`edge_vs_market = market_spread - ensemble_spread`. Positive means the consensus likes the home
team more than the market does.

- `edge > 0` → bet **home** against `market_spread`. Wins if `actual_margin + market_spread > 0`.
- `edge < 0` → bet **away**. Wins if `actual_margin + market_spread < 0`.
- Exactly zero → push, excluded from the win rate and from the count.

## Buckets — fixed absolute thresholds, chosen before seeing results

`|edge|` in points: **[0,1), [1,2), [2,3), [3,5), [5,inf)**.

Absolute, not quantile: quantile buckets move with the data and invite re-cutting. Five buckets,
fixed here, no re-cutting for any reason.

## Primary outcome

ATS win rate per bucket against the **-110 breakeven of 52.38%**. A bucket is actionable only if
it clears breakeven with the multiplicity-corrected interval excluding it.

## Inference

Wild cluster bootstrap by season, matching every other test in this analysis (B=2000, so the
p-value floor is 1/2000). **Holm across the five buckets.** One-sided is tempting since only
"above breakeven" is actionable; use **two-sided** anyway, because a bucket significantly
*below* breakeven is also a finding (it would mean fading the consensus).

## What I expect, recorded before running

**No bucket clears 52.38% significantly.** The MSE gap against the raw market on closing is
-0.093 and against the recalibrated line -0.128 (p=0.153); an edge that small should not produce
a tradeable sign advantage. I expect all five buckets near 50% and the top bucket to be the
noisiest, not the best.

**If I am wrong** — if the top bucket clears — the correct reading is NOT "found a system". It
is a single post-hoc-flavoured slice with no confirmation window, on a panel where I have
already recorded eight defects, and the honest next step is forward testing via
`pt_upcoming_predictions.csv`, not action.

## Stopping rule

One run. No re-bucketing, no switching to opening lines, no dropping seasons, no adding a
"minimum line movement" filter after the fact. If the result is null, it is null and gets
written up as null.

## Secondary, reported but not decisive

- Win rate by bucket for the **subset regression (E14)** predictions, same rule. Reported for
  comparison only; E14 is the selection-conditional winner and is not the served method.
- Mean ROI per bucket at -110, for magnitude. Not a separate hypothesis.
