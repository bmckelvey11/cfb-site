# Review — the book composite, and how the predictions combine

2026-09-02. Reviews the fair-value composite in `eval_line_shopping.py` and specifies how the
model numbers (E4, E14, raw consensus) and the book numbers should be combined into one fair
spread and one bet decision. Evidence cited is in `prediction-tracker-findings.md`,
`line-shopping-results.md`, and `review-2026-09-02-composite-spread.md`.

## 1. The book composite as built

`fair = median of closing home spread over real books {49, 68, 69, 71, 75}`, ≥ 2 books required.

**What is right about it.** Median, not mean, so one mis-posted book cannot drag it. Real books
only; the consensus (15) and opener (30) pseudo-books are excluded, which the earlier
line-shopping attempt got wrong twice. Odds window kills alt lines.

**Four defects, in order of consequence.**

1. **No outlier guard.** Book 71 posted 18 against 7.5, 34 against 9.5, 0 against −20.5. With
   three books the median survives, but the *best number* does not: those rows became the
   "best" side and 23 of the 500 gain ≥ 1 sides. Rule for the live version: a book's number is
   ignored when it is more than **2.5 points** from the median of the *other* books and at least
   two other books exist. Pre-register the threshold; do not tune it to the 51 tail games.
2. **Price is ignored.** Spreads are compared at face value inside [−135, +125]. Ten cents of
   juice is ~2.1 win-rate points, roughly a non-key half-point. Measured on the 1,695 sides with
   gain ≥ 0.5: best-number odds are −115 or worse on 26%, the break-even penalty against the
   median book's odds averages +0.10 win-rate points but is ≥ 1 point on 18%, and on **12% of
   shopped sides the juice wipes out the point gain**. Fix: compare sides on a common scale —
   `value = 3.2 × points_gained − 100 × (breakeven(best odds) − breakeven(median odds))`,
   with a key-number multiplier (§3). The 3.2 comes from P2 and should be re-estimated once
   the key-number split is modelled rather than averaged.
3. **The median of three is one book.** 77% of games have exactly three real books, and in 18%
   of those all three differ, so "fair" is whichever book sits in the middle. Acceptable for
   dispersion and value measurement; not a fair value to fit a model against. When the
   consensus (15) is present, a better fair is `median(real books ∪ {15})` — 15 is Action
   Network's aggregate over more books than the five here and was within 0.25 of the three-book
   median only 78.5% of the time, which says the three books under-sample the market.
4. **Snapshot = close is assumed, not verified.** The scoreboard for a completed game is taken as
   the final pre-kickoff market. The 2026 timestamped histories can check it after a few weeks:
   compare each book's last pre-kickoff tick to the scoreboard number for the same event.

None of the four changes the result (+1.26 → +1.15 with the tail out; juice is second-order),
but 1 and 2 are required before this composite drives a live bet.

## 2. How the model predictions combine — the evidence, then the rule

Everything below was measured on 12.8–17.7K games; nothing is speculative.

| question | answer | where |
|---|---|---|
| Weight scheme across models | **equal weights on the top-K by prior skill**, K ≈ 20, `lineca`/`linemidweek` removed | E4 survived; ridge (E6) was significantly *worse* than the line vs close |
| Recency weighting | none; ρ = 1.00 chosen 20/20 seasons | recency screen |
| Cohort / entry-year adjustment | none; it removed the best forecasters | recency screen §6 |
| Averaging everything | never; +9.3 MSE vs doing nothing | model-eval §3 |
| How the consensus enters | as a **tilt on the market**: `fair_model = market + γ · (consensus − market)` | E4 form |
| γ vs the closing line | **0.07–0.10** (live fits this week: 0.073, 0.025, 0.100) | forward log |
| γ vs the opening line | 0.37–0.55 | model-eval §3, sweep §1 |
| γ vs Monday's line | **unknown**; week 1 says Monday ≈ close, so start at the closing γ | review §6 |
| E14 (subset regression) | report beside E4, do not average them; selection-conditional winner, ~half market proxying | findings §4 |
| Does consensus *direction* vs close predict covers | no — 49.7% on 17,166 games, worst in the strongest-disagreement bucket | review §1 |

**The rule that follows.** One fair number per game:

```
market_fair  = median(real book numbers passing the outlier guard  ∪  consensus 15)
model_fair   = market_fair + γ · (screened_consensus − market_fair),   γ = 0.07 until the
               forward test yields a Monday-specific value
```

`model_fair` differs from `market_fair` by a median of 0.3 points and never by a full point on
this week's 44 games. **That is the honest size of the model's contribution.** Its role is
tie-breaking at the margin, not generating bets. The reason to keep it in the formula at all is
the forward test: if a Monday γ comes back near 0.3 or higher, the term matters; if it comes
back near 0.07, drop it and the pipeline is line shopping alone.

Do **not** combine E4 and E14 into a mean, do not add a "raw median" term, and do not fit a new
weight vector — each has a recorded null or a recorded failure.

## 3. The bet decision

For each game and each side, the number to bet is the best posted one that passes the guard.

```
edge_pts      = side_best_number − model_fair          (from that side's perspective, ≥ 0)
key_mult      = 2.5 if the interval [model_fair, side_best_number] straddles or lands on 3 or 7
                else 1.0
value_pts     = 3.2 · edge_pts · key_mult − 100 · (breakeven(best odds) − 0.5238)
p_cover       = 0.50 + value_pts / 100
bet if p_cover > breakeven(best odds); stake = quarter-Kelly at that price
```

Calibration of the three constants (3.2 per point, 2.5 key multiplier, 0.07 γ) is from
2024–25 and the archive; all three are *measured*, none is *validated out of sample*. Track
CLV against the closing consensus and the realised cover rate per value bucket; ~150 bets
per bucket separates a 52% from a 55% cell.

**What this pipeline will and will not do.** On 2024–25 data the shopped side at gain ≥ 1 ran
52.8% [48.7, 56.9]. So the expected state after all three steps is **break-even to slightly
positive**, with the interval including a loss. It converts a losing spread process into a
non-losing one. It does not manufacture the 55%+ the user's totals record shows, and nothing
in this tree suggests any spread pipeline will.

## 4. Order of work

1. Add the outlier guard and price-adjusted value to `eval_line_shopping.py`; re-run once as a
   pre-registered amendment (record the threshold first).
2. Verify snapshot = close on 2026 histories after ~4 weeks.
3. Let the forward log accumulate; fit γ against the Monday line when ~300 graded games exist.
4. Only then wire §3 into anything that produces a slip. Until then the composite is a
   reference number, and the actionable content is: shop, and respect 3 and 7.
