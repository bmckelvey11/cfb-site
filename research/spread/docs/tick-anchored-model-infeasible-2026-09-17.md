# Can a tick-anchored movement model be built? — 2026-09-17

**Answer: no, and not for want of effort.** The data required does not exist and cannot be
obtained retroactively. Recorded so the idea is not proposed a fourth time.

## The question

`actionable-picks-2026-09-17.md` § 0 showed that `weekly_slate.py`'s `edge` is the market's own
move since the opener, sign-flipped, because E4 is anchored on the opener and barely leaves it.
The fix is a model anchored on the **current** line: predict the close from the price you can
actually get today. That needs a training set of `(line at time T, features at time T) → close`.

## Why it cannot be built

### 1. The PT archive has one line per game, and it is the target

`fit_movement_models` sets the target to `-hist["line"]`. Making `line` the anchor makes the
anchor identical to the target. Measured:

| BENCH | gamma | anchor residual sd on held-out rows |
|---|---|---|
| `lineopen` | +0.133 | 2.12 |
| `line` | **−0.00000** | **0.00000** |

Live that means an `edge` of ~0 on every game and a silently empty slate. `lineopen → line` is
the only two-point structure the archive contains.

### 2. `stg.an_market` is a snapshot, not a tape

88,426 rows over 1,897 events, 2024–2026 — but **no timestamp column**
(`event_id, season, week, book_id, period, market_type, side, team_id, line, odds, market_id,
outcome_id, is_live, line_status, …`). 46.6 rows per event is books × sides of current state,
not a time series. The 2024–2026 range describes which *games* are covered, not a span of
observations.

*This corrects a claim made earlier the same day that `stg.an_market` held "88,426 tick rows
across 2024–2026". It does not.*

### 3. The real tick data is 275 files, all inside the forward-test period

`raw/actionnetwork/history_event_*.json` does carry genuine timestamped paths
(`spread[].history[].updated_at` + `value`, per book). Coverage:

| season | week | games with a path |
|---|---|---|
| 2026 | 1 | 99 of 99 |
| 2026 | 2 | 86 of 86 |
| 2026 | 3 | 74 of 75 |
| 2026 | 4 | 16 of 71 (in progress) |

275 games, **2026 only**. That is the version B forward-test period. Fitting on it would
contaminate the one confirmatory test in the tree.

### 4. It cannot be backfilled — Action Network does not retain settled paths

Probed `AN_HISTORY` directly for four events (one request each, 1 s apart):

| probe | response | history present |
|---|---|---|
| 2024 week 5, event 226737 | 18,834 bytes | **no** |
| 2025 week 5, event 254604 | 18,984 bytes | **no** |
| 2025 week 12, event 255438 | 21,395 bytes | **no** |
| 2026 week 1, event 288897 | 23,068 bytes | **no** |

The endpoint answers, but with current state only — no `updated_at` anywhere in the payload.
Even a 2026 week 1 game, four weeks old, has lost its path. AN replays the full path only while
an event is live, which is exactly why `collect_line_timing.py history` exists and why the
runbook calls a missed window unrecoverable.

## What has already been tested, and is not this

**Amendment A5** ran the one re-anchoring the PT archive *can* support: regress
`AN_close − PT_line` on `pred − PT_line`, 1,440 matched 2024–25 games, 31 season-week clusters.
E4 slope **−0.033 [−0.059, −0.007]**. See `line-movement-results.md` § A5 for the full read and
its caveats. That covers only the sliver of move remaining after PT's last capture (~0.69 points
on average), not the multi-day window a slate-time anchor would need — but it is the only
archive evidence available, and it is null.

## What this does not support

- **Not a claim that a tick-anchored model would fail.** It is untested and untestable today.
  Nothing here says anything about its merit.
- **Not a reason to weaken the collector.** The opposite: forward capture is now the *only*
  route to this dataset, and every missed window is permanent.
- **Not a criticism of `stg.an_market`.** It is a correct current-state table; it was simply
  mistaken for a tape.

## The only path forward

Accumulate tick paths prospectively. The collector already does this and is keeping up —
weeks 1–3 of 2026 are at 98.7–100% capture. A usable training set means multiple seasons of
that, and it must exclude whatever window version B is still grading. This is a multi-season
project, not a sprint.

Until then `weekly_slate.py` stays on the opener anchor, `EDGE_DEF_VERSION` stays at 1, and the
constant's comment in that file carries the short version of this document.

## Reproduction

The probes above are one-off diagnostics against a live endpoint, not a pipeline; the commands
are in this document's git history. The reproducible parts:

```bash
python research/spread/scripts/edge_vs_market_move.py     # the defect this would have fixed
python research/spread/scripts/eval_version_b.py          # what it must not contaminate
```
