# Sourcing the model from the warehouse — and dropping the lines nobody could bet

**Question.** The floor-bias model read `data/raw/lines_*.json`. Should it read
`data/cfb.duckdb` instead, and what changes if it does?

**Answer.** It now reads `core.fact_game_line`. The headline moves +23.57% →
**+28.18%**, and holding the seasons fixed shows why: on 2017+ alone the raw
path scores +21.24% and the warehouse +28.18% on an almost identical bet count
(211 vs 210). The gain is not a shorter history or a smaller sample — it is that
the warehouse prices only off lines a book actually quoted.

The warehouse's core build excludes projection sites, and CFBD published no
consensus total before 2017, so every pre-2017 total was a model's number rather
than a book's. Those seasons no longer produce bets at all.

The record is now **N=210, 141–69, +28.18% ROI [+15.56, +39.63]**, bet seasons
**2020–2026**, on 7,838 graded games — down from 275 bets over 2016–2026 on
11,048 games. Fewer bets, all of them priceable.

## Why the history shrank

`cfb_system_maker/duckdb_core.py` defines:

```python
PROJECTION_PROVIDERS = ("teamrankings", "numberfire")
```

and filters those out before line selection (commits `10b6943`, `4a14d02`). The
builder documents the exact consequence at `duckdb_core.py:300`:

> projection sites are filtered out before selection … core and `games.csv`
> disagree on 197 projection-only games and on the 2,901 2013-2016 totals the
> CSV still carries

and the reason at `duckdb_core.py:410`:

> CFBD's own payloads carry `overUnder: null` on every `consensus` row until
> 2017 … the ActionNetwork tape starts in 2024 — so the 2,901 are exactly
> 2013-2016 … Nulling them is the honest answer for a game nobody took a price
> on.

`tests/test_core_agreement.py` asserts that divergence positively. So 2013–2016
carrying no usable total is a **design decision, not a defect**, and rebuilding
`core.fact_game` reproduces it exactly.

This was measured independently from the raw side before the builder was read:
`models_v2.pick_line` selects a projection site on **3,104 of 13,402 games
(23.2%)** — teamrankings 3,066, numberfire 38 — and on **3,096 of those (99.7%)**
no sportsbook in the feed published both a spread and a total. The raw path was
pricing roughly a quarter of its sample off numbers no book ever hung. Two
independent routes reached the same conclusion.

## Result

Walk-forward, train on seasons < *t*, grade *t*, min-train 3, filter bias > 1.75,
flat 1u at −110, pushes dropped.

Two things changed at once — the source *and* the span — so they are separated
below. `raw 2017+` is the raw path restricted to the warehouse's usable seasons,
which isolates each effect.

| # | configuration | bet seasons | N | record | ROI | ROI 95% |
|---|---|---|---:|---:|---:|---|
| 1 | raw JSON / `pick_line`, 2013+ — *previous record* | 2016–2026 | 275 | 178–97 | +23.57% | [+12.47, +33.90] |
| 2 | raw JSON / `pick_line`, 2017+ — *span change only* | 2020–2026 | 211 | 134–77 | +21.24% | [+8.48, +33.08] |
| 3 | `core.fact_game_line`, 2017+ — **shipped** | 2020–2026 | **210** | 141–69 | **+28.18%** | [+15.56, +39.63] |

**The decomposition is the finding.** Dropping the four pre-2017 seasons *lowers*
ROI slightly (1 → 2: +23.57% → +21.24%). Swapping the source on the same seasons
*raises* it by nearly 7 points (2 → 3: +21.24% → +28.18%) on an almost identical
bet count, 211 against 210.

So the gain is not the shorter history and not a smaller sample — it is that
configuration 2 is still pricing games off projection-site numbers while
configuration 3 uses only lines a book quoted. Measured on the same seasons,
removing untradeable prices raises the estimated edge by ~7 ROI points.

Read that as a warning as much as a result: it means the old +23.57% was partly
an artefact of grading against numbers nobody could bet. It does **not** mean
the strategy now earns 28% — see the caveats below, especially the threshold
reuse.

Flat +59.18u on 210u risked, max drawdown 4.27u; ¼-Kelly +423.98u on 1,509u
staked (7.19× the turnover), max drawdown 38.0u, largest single stake 13.5% of
bankroll. Flat 1u remains the deployable rule. 7/7 bet seasons profitable on the
point estimate, 4 of 7 clearing break-even on their own interval.

Decay, re-measured on this configuration rather than inherited from the raw run:
slope trend **+0.0022 units/yr, p = 0.839**, R² 0.01 — flat, no decay.

### By bias bin

| bias bin | N | record | hit rate | ROI | ROI 95% | clears |
|---|---:|---:|---:|---:|---|:---:|
| 0.00–0.50 | 6452 | 3132–3320 | 48.54% | −7.33% | [−9.65, −5.00] | no |
| 0.50–1.00 | 822 | 435–387 | 52.92% | +1.03% | [−5.50, +7.50] | no |
| 1.00–1.75 | 354 | 184–170 | 51.98% | −0.77% | [−10.69, +9.07] | no |
| 1.75–2.50 | 157 | 104–53 | 66.24% | +26.46% | [+11.75, +39.69] | **yes** |
| >2.50 | 53 | 37–16 | 69.81% | +33.28% | [+7.79, +53.65] | **yes** |

The monotone rise across the bins survives, and the excluded 1.00–1.75 band
still shows no edge — the mechanism check the threshold rests on.

## What shipped

- `v2/warehouse_source.py` — `load_warehouse_seasons(seasons, lines=...)` returns
  the same contract as `models_v2.load_raw_seasons`, so every existing estimator
  runs unchanged. `lines` selects `fact_game_line` (default), `fact_game`
  (per-field selection) or `game_lines` (staging, projections included).
- A guard that **fails loudly when a season has played games but no usable
  lines**. A season returning zero rows does not error on its own; it silently
  disappears and the walk-forward starts `min_train` seasons later, reporting a
  plausible smaller record. This guard is what surfaced the 2013–2016 change
  rather than letting it through.
- `monitor/monitor.py` gains `load_games(seasons, source)` and
  `add_source_arg(ap)`. All eight monitor entry points take `--source`,
  defaulting to `warehouse`; `--source raw` restores the old behaviour.
- `roi_report.warehouse_game_meta` supplies per-game identity from the warehouse
  frame; the existing per-season length assertion caught the source mismatch the
  first time it ran.
- The provenance footer names the source and selection rule, so a generated doc
  states which ledger and which rule produced it.
- `docs/ROI_HITRATE.md`, `docs/backtest_bets.csv` and both figures regenerated.

## What this does not support

- **Not evidence the strategy now earns 28%.** The 2→3 contrast does support
  the specific claim that untradeable prices were depressing the estimate, since
  the seasons and bet count are held nearly fixed. It does not establish the
  level. The intervals overlap heavily ([+8.48, +33.08] against
  [+15.56, +39.63]), so ~7 points is not separable from noise at N≈210, and the
  1.75 threshold was fitted on the old data. Treat +28.18% as the same edge
  measured against cleaner prices, not a larger one.
- **The threshold is now unvalidated on this population.** 1.75 was chosen on
  the raw, full-history data. Applying it to a 2020–2026 book-only sample reuses
  a parameter fitted elsewhere. Nothing here re-derives it, and re-deriving it on
  this sample would make the result selection-inflated in the way
  [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)
  calls invalidating.
- **Thin seasons.** 2020 carries 4 bets, 2026 carries 28 and is three weeks old.
  7/7 profitable seasons is a weaker claim than it sounds at this count.
- **Line selection is worth several ROI points on its own.** Measured during this
  work: swapping only the tiebreak among equally defensible rules moved ROI by
  ~5 points, and refreshing a provider table moved one rule by 2.6 points with no
  code change. That sensitivity is the strongest argument in this doc for
  planning on the lower bound (+15.56%), not the point estimate.
- **Still no proper score.** Hit rate, ROI and Wilson intervals only — no Brier
  or log-loss against the de-vigged market, which the standard asks for at
  Tier 1. Pre-existing gap in the generators.
- **Not a decision-time reconstruction.** `fact_game_line` carries `spread_close`
  / `total_close` with no timestamp, exactly as the raw JSON is a pull-time
  snapshot. The "prices reconstructible at decision time" gate remains unmet.
- **Downstream consumers were not regenerated.** `docs/backtest_bets.csv` is now
  7,838 rows from the warehouse. `research/bankroll/docs/seed-bankroll-proposal-2026-09-21.md`,
  `mc-combined-totals-2026-09-17.md` and the two `research/` study dirs still
  cite it as "234 walk-forward bets 2016–2025". They are dated records and are
  not re-scored, but they now name a ledger that differs in span, size and
  source. The bankroll planning inputs in particular should be revisited before
  they are relied on.

## A note on reading this warehouse

`data/raw/lines_*.json` mtimes do not track their content — all read
2026-08-28 while the content is newer (see
[`roi-refresh-backfill-2026-09-22.md`](roi-refresh-backfill-2026-09-22.md)). The
warehouse has no `meta.warehouse_version` table at the time of writing, so there
is no version stamp to assert against either. When warehouse contents appear to
shift, check `git log` on `cfb_system_maker/duckdb_core.py` before concluding the
data broke: during this work two builder commits changed line selection
mid-session, which looked exactly like corruption from the row counts alone.

## Reproducing

```
cd models/over_zero
python monitor/roi_report.py      --season $(seq 2017 2026)
python monitor/roi_hitrate_doc.py --season $(seq 2017 2026)
python monitor/run_monitor.py     --season $(seq 2017 2026)
```

`--source raw --season $(seq 2013 2026)` reproduces the previous record. The
source comparison is in `notebooks/over_zero_from_warehouse.ipynb`. Run from
`models/over_zero/`, not the repo root — the `--fig` defaults are cwd-relative.
