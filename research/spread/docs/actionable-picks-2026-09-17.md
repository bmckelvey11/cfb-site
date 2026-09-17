# Can the pred-tracker-model give actionable picks? — 2026-09-17

**Question.** The pred-tracker-model (E4 and siblings, served by `weekly_slate.py`) has been
running forward since 2026-08-31. Can its weekly slate be bet today?

**Answer: no, and the blocker is structural, not statistical.** Two separate reasons, in order
of how much they matter.

## 0. The edge is the market's own move, sign-flipped

This is the mechanism under §1 and §2; they are consequences of it, not separate objections.

E4 predicts the close **anchored on the opener**. `weekly_slate.py` compares that prediction to
the **current** book fair and calls the difference `edge`. But E4 barely leaves the opener — on
the 2026-09-16 slate, mean |E4 − open_pt| = 0.51 against mean |E4 − book_fair| = 1.11. So the
subtraction mostly reproduces the move the market already made, with the sign flipped:

```
57 games, predictor E4
corr(edge, move since opener) = -0.908
edge = +0.28 - 0.97 x (move since opener)
```

Each point the market has moved off the opener manufactures 0.97 points of "edge". The largest
edges on the served slate are all the same trade:

| matchup | opened | book fair | moved | E4 | edge |
|---|---|---|---|---|---|
| Ohio @ South Alabama | 3.5 | 7.0 | +3.5 | 3.3 | −3.7 |
| BYU @ Colorado St. | −20.5 | −17.5 | +3.0 | −20.8 | −3.3 |
| Georgia St. @ Central Florida | 20.5 | 17.5 | −2.0 | 20.6 | +3.1 |
| Akron @ Minnesota | 26.5 | 23.5 | −3.0 | 26.5 | +3.0 |

"Take Ohio +7" is not a read on Ohio. It is the claim that the market was wrong to move 3.5
points and will retrace to its opener.

**That inverts the registered finding.** Amendment A6's gamma (~0.25) says the move *from the
opener* is partly predictable **measured at the opener**, before it happens — a momentum result.
Applying the same fitted predictor to a line that has *already* moved converts it into a
mean-reversion bet on that move. The archive never tested that trade and does not support it.

It also explains §2's bet record without appealing to variance: fading real market moves is how
a predictor gets ATS 0.442, beat-close 37.2%, and beat-close *falling* as edge rises — a larger
edge is by construction a larger realized move to fade.

Reproduce: `python research/spread/scripts/edge_vs_market_move.py`.

**What this does not support:** a claim that E4 is broken, or that A6 is wrong. E4 fit at the
opener is the registered, validated object. The defect is in reading its output against a later
price, which is what the served `edge` column does.

## 1. There is not enough move left at the anchor to pay for the vig

Version B grades E4's side at the week's anchor price against the real close. The total move
available from that anchor is ~0.7 points. An oracle that knew the close exactly would earn
0.76 points of CLV at |edge| ≥ 1; the model captures a fraction of that, so its ceiling is a
fraction of 0.76. Plugging in the archive's opener gamma (~0.25–0.30) gives 0.19–0.23 points.

How little that buys, using this tree's own measured CLV↔ATS pairs (not an imported
points-to-win-rate constant — `line-movement-results.md` warns against converting with the
line-shopping figure, and `eval_ats_vs_breakeven.py` exists because this file's ancestor
over-converted): at the opener, **+1.32 points of CLV bought 52.5% ATS [49.6, 55.2]**, an
interval straddling the 52.381% break-even at −110; 57.8% took +2.33 points. The anchor's
*oracle* ceiling of 0.76 points sits below the CLV that already failed to clear break-even.
Caveat: those pairs are opener bets over a different spread distribution, so this transfers in
order of magnitude, not exactly.

This ceiling bounds **CLV, not ATS** — a bet can win against the spread without the line moving.
The ATS case is killed by §2, not by this number.

The archive's headline 2–4 points of CLV were measured **at the opener**. They do not shrink
as you move to the anchor; they are simply not in that window. No improvement to the model
recovers them. Reaching them requires pricing earlier than the forward collector can see,
which is the same wall `prereg-line-movement.md` already names (the opener is unreachable
through PT).

## 2. The measured slope is zero, and the bet record inverts with edge

| | E4 slope | 95% CI |
|---|---|---|
| pooled, 91 games, 2 week clusters | +0.026 | [−0.090, +0.142] |

| threshold | bets | CLV | beat close | ATS |
|---|---|---|---|---|
| \|edge\| ≥ 1 | 43 | +0.20 | 37.2% | 0.442 |
| \|edge\| ≥ 2 | 18 | −0.06 | 27.8% | 0.556 |

**Beat-close falls as edge rises** (37% → 28%) and CLV goes negative in the higher bucket. A
real edge does not invert — that is the signature of a predictor with no information, where a
bigger disagreement with the market just means the model is more wrong.

**The 55.6% ATS at |edge| ≥ 2 is not a bright spot.** n = 18, CI [0.30, 0.81], and the same 18
bets lost CLV. An ATS number that disagrees with the CLV on the identical bets is sampling
noise in the margin, not evidence. It will be the most tempting number in this table; it should
not be acted on.

Week over week the picture flips sign entirely — week 1 slope +0.202 / CLV +0.47 / beat close
55%, week 2 slope −0.067 / CLV −0.04 / beat close 22%. Two draws from noise.

## 3. The anchor being graded is not the anchor that was registered

Both graded weeks anchored on **Tuesday**, not Monday, so version B has never measured the
quantity B1 registered, and the ceiling in §1 is a lower bound on the Monday ceiling.

This is history, not a design flaw: the collector has run four snapshots a day including Mondays
since 2026-08-29. Week 1's Monday snapshot was captured (Mon 08-31 15:05 ET) but predates
`weekly_slate.py` logging to the forward log — it is still on disk and replayable. Week 2's
Monday fell inside a 3.8-day collector outage (Fri 09-04 06:30 → Tue 09-08 02:31 ET) and is
gone for good, since PT overwrites in place. **Week 3 already has a logged Monday anchor**
(Mon 09-14 18:30 ET), ungraded until its games kick 09-19.

So the anchor problem self-corrects from week 3. Replaying week 1's snapshot would recover one
more Monday cluster. Neither touches §2.

## What this does not support

- **Not a verdict.** Amendment B3 is binding: no verdict before season end, and ≥ 8 week
  clusters for confirmatory inference. There are 2. Everything above is descriptive.
- **Not a claim that the opener edge is fake.** The archive's A6 result stands; this says only
  that the served anchor cannot reach it.
- **Not a reason to stop collecting.** Six more weeks of forward log is what B3 asks for, and
  the collector is the only source of it.

## Method and reproduction

Data: `data/processed/movement_forward_log.csv` as of 2026-09-16 (16 snapshots, 147 anchored
games, 91 graded, weeks of 2026-08-31 and 2026-09-07), Action Network tick histories for the
close, `stg_gql.game` for scores.

```bash
python research/spread/scripts/eval_version_b.py       # slope, bet record, B2 buckets
python research/spread/scripts/version_b_by_week.py    # per-week cut
python research/spread/scripts/version_b_ceiling.py    # ceiling + anchor weekday (new)
```

Every number above is carried by `line-movement-results.md` § "Version B — reads", read of
2026-09-17. This document does not restate anything it does not own.

## Next

1. Replay the Mon 2026-08-31 15:05 ET snapshot through `weekly_slate.py --snapshot` to recover
   week 1's Monday anchor. It is the only lost Monday that is still on disk.
2. Watch collector uptime — `collector_health.py` exits 1 past a 12 h gap, and the 3.8-day
   outage that cost week 2's Monday is the failure mode that actually matters. PT overwrites in
   place, so a missed window is unrecoverable.
3. Keep grading weekly to B3's stopping rule. Reassess at season end with ≥ 8 clusters.
4. Do not stake the slate meanwhile — `research/bankroll/` already excludes it.
