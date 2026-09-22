# Refreshing ROI_HITRATE with 2026 — and why every historical season moved

**Question.** `ROI_HITRATE.md` was generated 2026-08-28 at commit `2a82c87`. Refresh it so
the deployed filter's walk-forward record includes the 2026 season to date. Then: why did
the 2016–2024 rows change when appending a later season cannot touch an earlier fold?

**Answer.** The historical rows moved because the raw CFBD lines files have been
backfilled since August — not because of any code change, and not because adding 2026
altered the walk-forward. 2026 itself is a legitimate out-of-sample fold: 39 bets,
26–13, +27.27% ROI.

## Method

Both generators default to `--season 2013 ... 2025`, so a bare rerun is a no-op. The
refresh passed `--season 2013 ... 2026` to **both** (`roi_hitrate_doc.py` has its own
default and does not inherit the report's):

```
cd models/over_zero
python monitor/roi_report.py      --season 2013 2014 ... 2026
python monitor/roi_hitrate_doc.py --season 2013 2014 ... 2026
```

Walk-forward protocol unchanged: for season *t*, fit Tobit sigmas + probit on seasons
< *t* only, grade *t*. Pushes dropped. Flat 1u at −110.

### Gates run before trusting the output

1. **2026 games are settled finals, not scheduled placeholders.** `load_raw_seasons`
   (`v2/models_v2.py:85`) already skips games with a null `homeScore`/`awayScore`;
   confirmed empirically — 409 graded games, weeks 1–3, dates 2026-08-27 → 2026-09-20,
   zero 0–0 rows, mean combined score 54.45 against a mean line of 53.11.
2. **Both scripts write and read the same ledger.** At the deployed threshold
   `default_csv_path` returns `docs/backtest_bets.csv` for the report; the doc generator
   recomputes the walk-forward itself rather than reading that CSV, so there is no
   stale-CSV path between them.
3. **Earlier folds must not move.** They did — which is what the rest of this doc is about.

## What moved, and why

Graded games per bet season, committed ledger (Aug 28) against the refresh:

| season | Aug 28 | 2026-09-22 | diff |
|---|---:|---:|---:|
| 2016 | 711 | 752 | +41 |
| 2017 | 736 | 776 | +40 |
| 2018 | 805 | 843 | +38 |
| 2019 | 827 | 867 | +40 |
| 2020 | 533 | 559 | +26 |
| 2021 | 841 | 879 | +38 |
| 2022 | 1390 | 1435 | +45 |
| 2023 | 1327 | 1393 | +66 |
| 2024 | 1492 | 1542 | +50 |
| 2025 | 1593 | 1593 | **0** |
| 2026 | — | 409 | +409 |
| total | 10255 | 11048 | +793 |

Every season but 2025 gained games. Three candidate explanations were tested:

- **Code change.** Ruled out. Between `2a82c87` and `HEAD` only `v2/models_v2.py` and
  `monitor/roi_report.py` changed. `models_v2.py` changed `RAW_DIR` from
  `parents[1]/data/raw` to `cfb_paths.DATA_ROOT/raw` — the same directory. `roi_report.py`
  gained a `threshold` column, `default_csv_path`, and a Kelly `b` denominator fix
  (`payout/risk`, previously `payout/abs(price)`) that touches staking, not game
  selection. `monitor.py`, `run_walkforward.py` and `bias_bins.py` are byte-identical.
- **A second, stale copy of the raw data.** Ruled out — `lines_2016.json` exists at
  exactly one path on disk, `data/raw/`.
- **Backfilled source data.** Confirmed. At `2a82c87` the raw lines files were *tracked in
  git* (997 files under `data/raw/`); they are untracked now, under the repo's
  "data is never committed" rule. Comparing the tracked blob against the live file:

  | season | tracked games / graded | live games / graded |
  |---|---|---|
  | 2016 | 832 / 719 | 873 / 760 |
  | 2023 | 1350 / 1345 | 1416 / 1411 |
  | 2025 | 1597 / 1594 | 1597 / 1594 |

A worktree at `2a82c87` reproduced the committed doc exactly — 10255 graded games, 234
bets, pooled +23.19% ROI. That run read the *tracked* lines files the worktree checked
out, which is precisely the point: same code, old data, old numbers.

Note the file mtimes on `data/raw/lines_2013..2025.json` all read 2026-08-28 13:56–13:57
and are therefore **not** a reliable signal of content age — the live content is newer
than those stamps suggest. Do not use mtime to date this warehouse.

## Numbers

Deployed filter (bias > 1.75), walk-forward, flat 1u at −110, seasons 2016–2026:

| | Aug 28 (10255 games) | 2026-09-22 (11048 games) |
|---|---|---|
| bets | 234 | 275 |
| record | 151–83 | 178–97 |
| hit rate | 64.53% [58.21, 70.38] | 64.73% [58.91, 70.14] |
| ROI | +23.19% [+11.13, +34.36] | +23.57% [+12.47, +33.90] |
| planning number (lower bound) | +11.13% | +12.47% |

By bias bin, all graded games, disjoint bands:

| bias bin | N | record | ROI | ROI 95% | clears |
|---|---:|---:|---:|---|:---:|
| 0.00–0.50 | 9118 | 4403–4715 | −7.81% | [−9.77, −5.85] | no |
| 0.50–1.00 | 1157 | 608–549 | +0.32% | [−5.18, +5.79] | no |
| 1.00–1.75 | 498 | 262–236 | +0.44% | [−7.94, +8.74] | no |
| 1.75–2.50 | 185 | 118–67 | +21.77% | [+8.14, +34.33] | **yes** |
| >2.50 | 90 | 60–30 | +27.27% | [+7.71, +44.23] | **yes** |

The monotone rise across bins — the censoring mechanism's prediction — survives the
backfill and the extra season. The excluded 1.00–1.75 band still shows no edge.

## Generator defects found and fixed

The doc is generated, so these were fixed in the generators, not by editing the output:

1. **A hardcoded false superlative.** The decay-watch bullet asserted
   "`{last} is the largest sample and the flattest result`" of whatever season sorted
   last. That was true of 2025 (n=51, +1.07%) and false of 2026 (n=39, +27.27%) — the doc
   would have published that 2026 was both. The same claim was hardcoded in three places
   — the doc bullet, `roi_report.py`'s console NOTE, and the callout baked into
   `figs/roi_report.png`. All three now check each superlative against the rows
   (`_last_supers`), and the doc's "not evidence of decay" verdict is conditioned on the
   interval actually containing the pooled estimate and break-even.
2. **No partial-season flag.** The auto-derived footer reads "data 2013–2026", implying a
   complete season. A caveat now fires when the final season has graded under 60% of the
   median finished season.
3. **A reproduce command that reproduced something else.** The doc told the reader to run
   both scripts bare, which regenerates the 2013–2025 version. It now emits the explicit
   `--season` range; `monitor/README.md`'s command list was corrected the same way.

## What this does not support

- **It is not evidence the edge grew.** The pooled ROI moved +23.19% → +23.57% on a
  larger sample; that is inside the noise, not an improvement. The 1.75 threshold was
  still chosen partly on this data, so the planning number remains the lower bound
  (+12.47%), not the point estimate.
- **2026's +27.27% is not a season verdict.** 39 bets over three weeks, interval
  [−2.68%, +51.52%], which includes break-even. It is also pooled into every headline
  above, so the pooled row is no longer a record of finished seasons only.
- **It says nothing about decay.** `monitor/run_monitor.py` is the test that measures
  decay directly and was not re-run here.
- **It is not a re-grading of the prior doc.** The Aug 28 numbers were correct for the
  data available then. This is a living generated doc, refreshed in place per the docs
  lifecycle rule; the older figures survive in git history, not as a superseded record.
- **Other consumers of this CSV were not regenerated.** `docs/backtest_bets.csv` went
  from 234 filter-passing bets over 10 seasons to 275 over 11. Still citing the old
  figures: `research/bankroll/docs/seed-bankroll-proposal-2026-09-21.md` and
  `mc-combined-totals-2026-09-17.md` (both quote "234 walk-forward bets 2016–2025"), and
  the study dirs `models/over_zero/research/2026-08-31_win_prob_onset/` and
  `2026-09-10_spread_magnitude/`. Those are dated records and are not re-scored, but the
  bankroll planning inputs in particular now trail the ledger they name.
  `monitor/README.md` is a living doc and *was* updated here.
- **The backfill itself was not audited.** Which games CFBD added, and whether the added
  games differ systematically from the ones already present, is unexamined. If the
  backfill were non-random with respect to bias, it could shift the bins — nothing here
  rules that out.

## Reproducing

```
cd models/over_zero
python monitor/roi_report.py      --season $(seq 2013 2026)
python monitor/roi_hitrate_doc.py --season $(seq 2013 2026)
```

Run from `models/over_zero/`, not the repo root — both default `--fig` paths are
cwd-relative and land in root `docs/figs/` otherwise. Outputs: `docs/backtest_bets.csv`,
`docs/figs/roi_report.png`, `docs/figs/roi_hitrate.png`, `docs/ROI_HITRATE.md`.
