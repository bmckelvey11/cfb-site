# The warehouse as the model's source — and what line selection is worth

**Question.** The floor-bias model read `data/raw/lines_*.json`. Should it read
`data/cfb.duckdb` instead, and what changes if it does?

**Answer.** Yes, and almost nothing changes in the headline: pooled walk-forward
ROI moves +23.57% → **+23.32%**, well inside its own interval. What the switch
buys is a better *spread* — consensus on 60% of games against the raw path's
38%, which is the field the two sources disagreed about on 20% of games.

It buys **no improvement in tradeability**, and an earlier draft of this doc
claimed otherwise. Both sources draw on projection-site numbers
(`teamrankings`, `numberfire`) for the same 23.2% of games. Raw takes the
projection's spread *and* total; the warehouse keeps a consensus spread and
takes the projection's total. Same games touched, different field.

**The finding that matters more than the switch.** With the same code and the
same walk-forward, changing only the line-selection rule moves ROI from +23.3%
to +28.2%. The edge estimate is sensitive to a choice nobody thinks of as a
model parameter, at roughly a fifth of its own magnitude.

## Method

Three configurations through one `run()` in one process, identical protocol
(train on seasons < *t*, grade *t*, min-train 3, filter bias > 1.75, flat 1u at
−110, pushes dropped), seasons 2013–2026:

| # | source | line selection rule |
|---|---|---|
| 1 | `data/raw/lines_*.json` | `models_v2.pick_line` — one provider must supply **both** spread and total; consensus preferred, else the first book in the JSON array |
| 2 | `core.fact_game` | `selected_spread` / `selected_total`, chosen **per field**; consensus-first each |
| 3 | `core.fact_game_line` | one provider must supply both, consensus first, else `order by provider_key` |

Reproduced by `notebooks/over_zero_from_warehouse.ipynb` and
`v2/warehouse_source.py` (`coherent_pair=True` is configuration 3).

## Result

| configuration | N | record | hit rate | ROI | ROI 95% |
|---|---:|---:|---:|---:|---|
| 1. raw / `pick_line` | 275 | 178–97 | 64.73% | +23.57% | [+12.47, +33.90] |
| 2. warehouse / per-field — **shipped** | 274 | 177–97 | 64.60% | **+23.32%** | [+12.20, +33.68] |
| 3. warehouse / coherent pair — *probe, not reportable* | 210 | 141–69 | 67.14% | +28.18% | [+15.56, +39.63] |

## Why the sources disagreed at all

Reconciling 13,391 shared games:

| field | games differing | share |
|---|---:|---:|
| final score | 0 | 0.00% |
| total | 11 | 0.08% |
| **spread** | **2,667** | **19.92%** |

Plus 6 games only the warehouse has and 11 only the raw JSON has.

Neither source is corrupt. Every one of the 13,402 raw games agrees with its own
`formattedSpread` text, and the warehouse rows agree with their own
`formatted_spread`. The disagreement is entirely **which provider got selected**:

`pick_line` filters to providers carrying *both* a spread and an `overUnder`,
then prefers consensus *within that filtered set*. CFBD frequently publishes a
consensus spread with no consensus total — so consensus is dropped from the
candidate list and the model silently falls back to whatever book the JSON array
listed first, usually `teamrankings`. Game 332410189 (Tulsa at Bowling Green,
2013) has `consensus spread=3, formatted='Tulsa -3'`, and `pick_line` returns
−3.0 from teamrankings: the opposite favourite. Sixteen games are exact sign
flips of this kind; the median disagreement is 2.0 points and the maximum is
44.5.

`core.fact_game` picks each field independently, so it keeps the consensus
spread and takes the total from elsewhere. That is the 22% of warehouse rows
where `selected_spread_provider_key != selected_total_provider_key`, and 2,878
of those 2,943 are exactly this pattern: consensus spread, teamrankings total.

| rule | games | consensus spread | projection-site **spread** | projection-site **either field** |
|---|---:|---:|---:|---:|
| raw / `pick_line` | 13,402 | 5,137 (38.3%) | 3,104 (23.2%) | 3,104 (23.2%) |
| warehouse / per-field | 13,397 | 8,038 (60.0%) | 202 (1.5%) | **3,103 (23.2%)** |
| warehouse / coherent pair | 10,324 | 5,137 (49.8%) | 0 (0.0%) | 0 (0.0%) |

The last column is the one that matters for tradeability, and it is identical
between the two shippable rules. The warehouse's 1.5% projection-site *spread*
figure is real but does not mean what it looks like: `selected_total` is
projection-sourced on 3,103 games (23.2%), so the same games are affected either
way. Configuration 3 reads 0% only because it discards those games rather than
resolving them — a smaller sample, not cleaner data.

For the two shippable rules this is a CFBD coverage limit, not a selection
mistake. On 3,096 of the 3,104 games where `pick_line` lands on a projection
site — **99.7%** — no sportsbook *in the raw JSON feed* published both a spread
and a total. The projection was the only complete option available.

(The refreshed `core.fact_game_line` does carry books for many of those games,
which is why configuration 3's coverage changed at 05:34. That is a reason to
revisit whether `core.fact_game`'s per-field selection should now prefer a book
total over a projection one — a separate question, not settled here.)

## Why configuration 3 was not shipped despite the higher ROI

It scores +28.18%, 4.9 points above the shipped rule, and that number is not
usable — for a reason that is easy to miss.

Requiring one provider to carry both numbers does not merely change *which* line
is read; it changes *which games exist*. Only 10,324 of 13,397 games have any
single provider publishing both a spread and a total, so configuration 3 silently
drops 3,073 games (23%) and scores a subsample — 210 bets against 274. That
subsample is not random: it is exactly the games with the richest book coverage,
which skews toward higher-profile matchups. Comparing its ROI to the shipped
rule's compares two different populations.

**The warehouse moved underneath this measurement, which makes the point
sharply.** `core.fact_game_line` was rebuilt at 05:34 on 2026-09-22, part-way
through this analysis — it gained `circa`, `fanduel` and `betmgm` and dropped
the projection sites. Configuration 3 scored +30.81% on 270 bets before that
refresh and +28.18% on 210 after, with no code change. Configurations 1 and 2
reproduced to the digit across the same refresh, because `core.fact_game` was
untouched. A rule whose result moves 2.6 points when a provider table is
refreshed is not measuring the edge.

A parameter chosen on the outcome is the failure mode
[`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)
treats as invalidating, and this one was authored *after* seeing that it scored
better. The path is kept in `v2/warehouse_source.py` as a sensitivity probe,
labelled not-reportable.

The per-field rule was preferred on grounds fixed before it was scored: it
carries the most consensus spreads, it is the warehouse's own published
selection rather than one invented here, and its ROI sits inside the raw path's
interval rather than above it.

## What shipped

- `monitor/monitor.py` gains `load_games(seasons, source)` and
  `add_source_arg(ap)`. All eight monitor entry points — `roi_report`,
  `roi_hitrate_doc`, `bias_bins`, `run_walkforward`, `run_monitor`,
  `recalibrate`, `score_game`, `review_game` — take `--source` and **default to
  `warehouse`**. `--source raw` restores the old behaviour.
- `roi_report.warehouse_game_meta` supplies per-game identity from the warehouse
  frame. The existing per-season length assertion caught the mismatch the first
  time this ran, which is why it exists.
- The provenance footer now records the source, so a generated doc says which
  ledger produced it.
- `review_game.py`'s hard-coded season range moves 2013–2025 → 2013–2026.
- `docs/ROI_HITRATE.md`, `docs/backtest_bets.csv` (11,037 graded games, was
  11,048) and both figures regenerated from the warehouse.

The shipped numbers were re-derived after the 05:34 `core.fact_game_line`
rebuild and are unchanged: `core.fact_game`, which is what configurations 1 and
2 read, was not touched by it.

Decay is unchanged by the switch: slope trend +0.0101 units/yr, p = 0.292, no
decay.

## What this does not support

- **Not evidence the warehouse is more accurate, and not a tradeability win.**
  Both sources are internally consistent, and both rest on projection-site
  numbers for the same 23.2% of games. The warehouse is preferred because it
  keeps a consensus *spread* where the raw rule falls back to a projection's
  spread — a narrower claim than "more tradeable", which is false here. On
  those 3,103 games neither source could have been bet as priced.
- **Not a decision-time reconstruction.** `selected_spread` / `selected_total`
  carry no timestamp; they are a warehouse-time selection, exactly as the raw
  JSON is a pull-time one. The switch neither fixes nor worsens the evaluation
  standard's "prices reconstructible at decision time" gate. That gate remains
  unmet by both.
- **Not a clean re-baseline.** The 1.75 threshold was chosen on the raw-sourced
  data and is now being scored on a differently-selected one. The planning
  number stays the lower bound (+12.20%), not the point estimate.
- **The sensitivity finding is not quantified beyond two contrasts.** One
  alternative rule moved ROI 4.9 points, and refreshing a provider table moved
  that same rule 2.6 points. Nobody has swept line selection systematically, so
  the true spread of achievable ROI across defensible rules is unknown and could
  be wider. This is the strongest argument in this doc for treating the planning
  lower bound, not the point estimate, as the number.
- **No proper score.** Still hit rate, ROI and Wilson intervals only — no Brier
  or log-loss against the de-vigged market, which the standard asks for at
  Tier 1. Pre-existing gap in the generators.
- **Downstream consumers were not regenerated.** `docs/backtest_bets.csv` is now
  warehouse-sourced. `research/bankroll/docs/seed-bankroll-proposal-2026-09-21.md`,
  `mc-combined-totals-2026-09-17.md` and the two `research/` study dirs still
  cite it as "234 walk-forward bets 2016–2025". They are dated records and are
  not re-scored, but they now name a ledger that differs from theirs in both
  span and source.

## Reproducing

```
cd models/over_zero
python monitor/roi_report.py      --season $(seq 2013 2026)
python monitor/roi_hitrate_doc.py --season $(seq 2013 2026)
python monitor/run_monitor.py     --season $(seq 2013 2026)
```

Add `--source raw` to any of them for the pre-switch numbers. The three-way
comparison is in `notebooks/over_zero_from_warehouse.ipynb`. Run from
`models/over_zero/`, not the repo root — the `--fig` defaults are cwd-relative.
