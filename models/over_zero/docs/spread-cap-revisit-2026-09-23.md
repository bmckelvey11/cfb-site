# The 50-point spread cap on the warehouse ledger, and its first forward test

**Question.** [`RESULTS-2D.md`](../research/2026-09-10_spread_magnitude/RESULTS-2D.md)
(2026-09-10/11) recommended adding `|spread| <= 50` to the bet rule. The board has run
`--max-spread 50` since 2026-09-16. The ledger that recommendation was fit on has since
been replaced twice: first the CFBD backfill, then the move to warehouse book lines
([`roi-refresh-backfill-2026-09-22.md`](roi-refresh-backfill-2026-09-22.md),
[`warehouse-as-model-source-2026-09-22.md`](warehouse-as-model-source-2026-09-22.md)).
Does the cap's case hold on the current ledger? And what does 2026 show? 2026 is the
forward test RESULTS-2D §6 said to wait for.

**Answer.** The cap stands on the seasons that chose it, and the only out-of-sample
data points the other way. That data is 10 bets over three weeks.

- **Projection-site lines did not cause the old >50 record.** 28 of the 38 old >50 bets
  are still bets on the warehouse ledger, with the line unchanged on 23 of them.
- **On 2020–2025 the pattern holds.** On the warehouse ledger, bets above 50 went 12–14
  for −3.09u, with favorite-leg error −2.99. Games at or below 50 went 107–49 for
  +48.27u. This re-grades the seasons that chose the cap. It confirms the result
  survives the source change. It does not confirm the cap.
- **2026 is the first out-of-sample test, and it points the other way.** Bets above 50
  went **8–2, +5.27u**, with favorite-leg error **+6.90**. That is the opposite sign to
  the cap's mechanism. The hit-rate 95% interval is [49.7%, 95.6%], which contains
  break-even, the 50% the cap assumed, and the kept bucket's rate.
- **The overturn trigger has fired once.** RESULTS-2D §6 lifts the cap if the favorite
  leg above 50 "turns positive and holds over a few seasons". It turned positive in one
  partial season. That does not meet "holds", so the verdict is unchanged for now and
  the re-check point is the end of the 2026 regular season.

## Trial count

This is at least the **fourth look** at the cap on overlapping seasons:
[`RESULTS.md`](../research/2026-09-10_spread_magnitude/RESULTS.md) (the >50 record),
RESULTS-2D §1–7 (surface and gate), RESULTS-2D §8 (optimal cap), and this revisit.
Every number below from 2020–2025 was also used to choose the cap. Only 2026 is
untouched.

## Method

- **Ledgers.** The *old* ledger is `docs/backtest_bets.csv` at `96799f3f` (Aug 28):
  raw CFBD JSON, bet seasons 2016–2025, 234 bets on 10,255 graded games. The *current*
  ledger is the working-tree CSV from `dd098a41`: `core.fact_game_line`, bet seasons
  2020–2026, 210 bets on 7,838 graded games.
- **Rule and scoring.** Deployed rule, bias > 1.75, walk-forward (train < *t*,
  grade *t*). Pushes dropped, flat 1u at −110. Hit-rate intervals are Jeffreys.
- **Leg errors.** Realized points minus the model's own implied split
  (`implied_team_points`), exactly as in RESULTS-2D §3.
- **Scripts.** `edge_surface.py` gained `--until`. Its window labels were hardcoded
  ("2018–2025", "2021–2025"); on the current ledger those windows silently included
  2026. They are now derived from the seasons present.

## 1. Did the old >50 record come from projection-site lines?

No. `ledger_compare.py` follows every old >50 bet into the current ledger:

| fate on the warehouse ledger | n | old record | line moved |
|---|---:|---:|---:|
| still a bet | 28 | 12–16, −5.09u | 5 |
| graded, no longer a bet | 1 | 0–1, −1.00u | 1 |
| season not bet (2018–2019) | 9 | 7–2, +4.36u | — |

The hypothesis to rule out was that FCS games often have no book total, so the raw
path priced them off teamrankings. That did not happen here. The old >50 losers are
book-priced games that are still in the ledger. Dropping 2018–2019 removed seven
*winners* from the >50 bucket. That made the bucket look worse, not better.

## 2. By season

Bets with spread > 50, current ledger (`spread_magnitude.py --by-season`):

| season | n | record | units | fav_err | dog_err | total_err |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 1 | 0–1 | −1.00 | −4.75 | −3.25 | −8.00 |
| 2021 | 6 | 4–2 | +1.64 | +0.21 | +2.12 | +2.33 |
| 2022 | 5 | 2–3 | −1.18 | −6.90 | +1.80 | −5.10 |
| 2023 | 4 | 2–2 | −0.18 | +2.50 | +7.25 | +9.75 |
| 2024 | 3 | 2–1 | +0.82 | −7.58 | +4.25 | −3.33 |
| 2025 | 7 | 2–5 | −3.18 | −3.86 | −2.07 | −5.93 |
| **2026** | **10** | **8–2** | **+5.27** | **+6.90** | +0.85 | +7.75 |

On all graded games above 50, the population the trigger was stated on, the favorite
leg is −3.66 over 2020–2025 (n=29) and **+4.83** in 2026 (n=12).

Summary against the kept bucket:

| slice | n | record | hit | 95% | ROI | units |
|---|---:|---:|---:|---|---:|---:|
| 2020–25, >50 | 26 | 12–14 | 46.2% | [28.2, 64.9] | −11.9% | −3.09 |
| 2020–25, ≤50 | 156 | 107–49 | 68.6% | [61.0, 75.5] | +30.9% | +48.27 |
| **2026, >50** | **10** | **8–2** | 80.0% | [49.7, 95.6] | +52.7% | +5.27 |
| 2020–26, >50 | 36 | 20–16 | 55.6% | [39.4, 70.8] | +6.1% | +2.18 |

Under a true 50% hit rate, 8 or more wins in 10 has probability 0.055. At break-even
(52.4%) the probability is 0.074. That is suggestive, and it is not a rejection.

**Live consequence.** Two of the 2026 wins above 50 were on the week-3 board: Kent State
@ Ohio State (−52.5) and Portland State @ Oregon (−58.5). They cleared the bias gate and
were removed from it by the cap on 2026-09-16. Both went over.

## 3. What the pooled numbers say, and why they do not lead

Pooled 2020–2026 on the current ledger (`edge_surface.py`):

- The fixed cap at 50 makes **+57.00u** against **+59.18u** uncapped, so it now costs
  2.18u. On the old ledger it gained 1.73u.
- The in-sample units argmax is **no cap** (60), where the old ledger's was 50. Under
  season resampling the argmax interval is [49, 60]. The modes are 50, 52, 54 and
  no cap, each drawing 18–23% of resamples. The old floor of "never below 50" slips
  to 49.
- The fine-band favorite leg at 50–55 is −2.42 [−10.6, +5.8]. RESULTS-2D §8d's
  interval, [−7.7, −0.7], excluded zero. This one does not.
- Kept vs dropped at 50 gives Fisher p = 0.12, against 0.063 on the old ledger.

Each of these moves comes from the same 10 bets in 2026. Without 2026
(`--until 2025`: 7,429 graded games, 182 bets), every one reverts to the old verdict:

| measure | 2020–2025 | 2020–2026 |
|---|---|---|
| units, cap 50 vs no cap | **+48.27 vs +45.18** (cap +3.09) | +57.00 vs +59.18 (cap −2.18) |
| in-sample units argmax | **50** | no cap |
| resampled argmax 95% | [49, 57]; 50 in 52% of draws | [49, 60]; no cap in 18% |
| fixed 50 vs fitted-forward caps | beats units-fitted (43.82), ties ROI-fitted (48.91) | trails no cap |
| 50–55 favorite leg | **−4.82 [−9.6, −0.1]** | −2.42 [−10.6, +5.8] |
| kept vs dropped, Fisher p | 0.043 (gap 22.4pp, MDE 27.4pp) | 0.12 |

The cap's case on the warehouse ledger through 2025 is as strong as it was on the old
ledger. The 50–55 favorite leg excludes zero again, which RESULTS-2D §8d called its
strongest single number. Everything that changed, changed with 2026.

## 4. Verdict

**Keep the cap for now. It is on watch, not confirmed.**

- On the seasons that chose it, the cap's mechanism still shows up on clean book
  lines.
- The one forward test contradicts it on n=10.
- RESULTS-2D's overturn rule asks for the favorite leg to stay positive across a few
  seasons. One partial season of early-September paycheck games does not meet that.

Whether to keep the cap is a rule change and the user's call. Ranked options:

1. **Keep the cap and re-check at the end of the 2026 regular season** (recommended).
   Re-run `spread_magnitude.py --by-season`. If the 2026 favorite leg above 50 is still
   positive, with the bucket at or above the kept rate, 2026 counts as one full season
   on the overturn side.
2. **Half-stake above 50.** This keeps the bets on the board while exposure stays small.
   It hedges the asymmetry: if the bucket is dead, half the variance is paid for
   nothing; if it is live, half the edge is forgone.
3. **Remove the cap.** This is defensible only if the pooled 2020–2026 numbers are read
   as the answer, and they rest on the 10 bets above.

Lifting or changing the cap touches more than `--max-spread 50` in
`scripts/over_zero_slate.cmd`. It also touches the site's per-view display guard, the
±50 calculator limit, and the disclosed rule text
([`site-refresh-cap50-2026-09-16.md`](site-refresh-cap50-2026-09-16.md)).

## What this does not support

- **Not evidence the cap is wrong.** The 2026 bucket's interval contains 50%, and the
  3-week sample is early-season FCS-heavy. [`week3-grade-2026-09-21.md`](week3-grade-2026-09-21.md)
  warns against extrapolating those boards to conference weeks.
- **Not evidence the cap is right.** The 2020–2025 support re-uses the seasons that
  chose it. The source change leaves it standing but does not test it.
- **Not a statement about the live board's record.** The ledger's 2026 bets come from a
  walk-forward fit on warehouse 2017–2025. The live slate fits on raw 2013–2025
  (12,985 games), so the two can disagree on individual picks near the gate.
- **Tier 1 gaps, unchanged.** There is no proper score against the de-vigged market, no
  CLV, and no decision-time price reconstruction. These are pre-existing gaps in the
  generators, as `warehouse-as-model-source` records.

## Reproducing

From the repository root:

```
python models/over_zero/research/2026-09-10_spread_magnitude/ledger_compare.py
python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py --by-season
python models/over_zero/research/2026-09-10_spread_magnitude/spread_magnitude.py
python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py
python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py --until 2025
```

`edge_surface.py` takes about 7 minutes (9,999 wild-bootstrap reps per term). The
ledger is `models/over_zero/docs/backtest_bets.csv` at `dd098a41`. Regenerating it
changes these numbers.
