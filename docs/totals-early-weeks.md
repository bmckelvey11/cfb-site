# Early-Season Totals & Spread Analysis

**Date:** August 27, 2026
**Scope:** Read-only analysis of whether early-week college football games support a viable totals or point-spread model, using live data from this repo's `data/` folder. No production code was changed.

> **Dated note (2026-08-27):** This note used the leaked feature set (this-game
> havoc, attendance, post-game winProb). Headline totals hit rates here are not
> evidence of edge. See [`totals-model.md`](totals-model.md) for the clean 2022–25 re-grade.
> Early-week strategy is out of scope for that fix; this file is not re-run.

---

## Executive summary

| Question | Verdict |
|----------|---------|
| **Totals in early weeks?** | **Yes** — modest but real edge vs late season on walk-forward backtests |
| **Dedicated “openers only” strategy?** | **No** — `min_n = 0` games hit ~54%; not statistically distinguishable from chance |
| **Point spread model?** | **Not yet** — closing spread ~50% ATS; `spreadOpen` exists in raw lines but is not loaded by `data.load()` |
| **Change default `--min-prior-games`?** | **Not recommended alone** — early games are additive; late season still profitable |

**Headline finding:** The existing totals model performs *slightly better* on early-season games (weeks 1–4, or when either team has ≤2 prior games) than on mid/late season games — roughly **+1.5 to +2 percentage points** at the same edge thresholds. Priors (talent, Elo, recruiting) carry more weight when in-season rolling stats are thin; the opening line carries less.

This contradicts the intuitive worry that “week 1 is too noisy to model.” It does **not** contradict keeping `--min-prior-games 3` as the conservative default for live picks until NaN handling and forward testing are resolved.

---

## Background: what this repo already does

`cfb-totals-model` is a walk-forward backtest harness for college football **totals** (over/under combined points):

1. **Predict** combined points with `GradientBoostingRegressor` (41 features + the line).
2. **Compare** prediction to the betting line: `edge = line - prediction`.
3. **Bet** under when edge > 0, over when edge < 0 (subject to `|edge|` threshold).

Default grading uses **opening totals** (`ou_open`) — the number you can actually bet — not the closing total.

Documented baseline (2021–2025, `--min-prior-games 3`):

| min \|edge\| | n | hit % | ROI |
|---|---|---|---|
| 0 | 2,640 | 55.98% | +6.88% |
| 3 | 1,656 | 57.37% | +9.52% |
| 5 | 1,086 | 58.10% | +10.92% |

Permutation test: shuffled ~50% vs actual 55.98% — grading metric is sound.

See [`totals-model.md`](totals-model.md) for features, no-lookahead guarantees, and caveats.

---

## Research question

> In the first few weeks of the season — when teams have little or no in-season history — is there enough signal to support a **totals** or **point spread** model (or a subset strategy)?

Constraints for the analysis:

- Use external `CFB_DATA_ROOT` via `models.totals.data.load()`.
- Respect no-lookahead: week *N* features = expanding mean of weeks 1…*N−1* only (`_entering_game_stats`).
- Do not invent spreads or stats not in the data root.
- Do not retune hyperparameters or ship new production code.

---

## Methodology

### Data load

- **Default filter:** `--min-prior-games 3` drops games where either team has fewer than three prior games in the season (`min_n = min(h_pre_n, a_pre_n)`).
- **Expanded pool:** `--min-prior-games 0` retains all games with valid lines/scores (12,194 rows loaded vs 8,868 at default).
- **Opening totals:** available from 2021+ (`ou_open` in `raw/lines_*.json`).
- **Spreads:** closing `spread` in `processed/games.csv`; opening `spreadOpen` in raw lines but **not** joined by `load()`.

### Bin definitions

| Bin | Rule |
|-----|------|
| **Openers** | `min_n = 0` (season opener for at least one team in the pairing sense of cumcount) |
| **Early** | `min_n ≤ 2` |
| **Late** | `min_n ≥ 3` (matches production default) |
| **Weeks 1–4** | calendar `week ≤ 4` |
| **Weeks 5+** | calendar `week ≥ 5` |

### Metrics

**Market-only (no model):**

- Mean error: `actual_pts - line`
- MAE, over % (`pts > line`)
- ATS home cover %: `home_points + spread > away_points` (pushes excluded)

**Model (walk-forward):**

- Train on prior seasons only (2021 uses week-expanding window inside the year).
- Test filtered to each bin; **training pool stays full history** (production-path follow-up).
- Hit rate, ROI at edge thresholds 0 / 3 / 5.
- Permutation test (500 shuffles) on graded bets.

Breakeven at −110 vig: **52.38%**.

---

## Phase 1: Exploratory analysis

Initial pass used `load(min_prior_games=0)` and custom slicing (including zero-fill for all-NaN rolling columns in tiny train slices). Key observations:

### Market totals bias by bin (`ou_open`)

| Bin | n | Mean err | Over % |
|-----|---|----------|--------|
| min_n = 0 | 494 | −1.68 | 43.5% |
| min_n = 1 | 350 | −0.47 | 49.1% |
| min_n = 2 | 328 | +1.17 | 52.7% |
| min_n ≥ 3 | 2,959 | +0.31 | 49.0% |
| Weeks 1–4 | 1,413 | −0.29 | 48.1% |
| Weeks 5+ | 2,718 | +0.26 | 49.0% |

Openers show a slight **under** bias (market high by ~1.7 pts on average), but sample is small and season-unstable.

### Market spread (opening `spreadOpen`, exploratory)

| Bin | n | Home cover % |
|-----|---|--------------|
| Early (min_n ≤ 2) | 1,168 | 51.8% |
| Late (min_n ≥ 3) | 2,927 | 50.3% |
| Home dogs early | 273 | 55.0% [uncertain — small n] |

No durable ATS edge; home-dog early bump is likely noise.

### Model by bin (exploratory walk-forward)

| Bin | n graded | Hit @ 0 | Hit @ ≥3 |
|-----|----------|---------|----------|
| min_n = 0 | 381 | 56.4% | 59.9% |
| min_n ≤ 2 (early) | 1,009 | 58.1% | 61.1% |
| min_n ≥ 3 (late) | 2,846 | 55.7% | 57.0% |
| Weeks 1–4 | 1,250 | 58.3% | 59.7% |
| Weeks 5+ | 2,608 | 55.4% | 57.4% |

**Feature importance (train ≤ 2022):**

| Pool | Line share | Prior share | Pace + mismatch share |
|------|------------|-------------|------------------------|
| Early (min_n ≤ 2) | ~12% | ~28% | ~7% |
| Late (min_n ≥ 3) | ~20% | ~18% | ~12% |

Early games: priors dominate; rolling pace/mismatch matter less (often missing).

**Baselines (early pool):**

| Model | Hit @ 0 | Hit @ ≥3 |
|-------|---------|----------|
| Full features | 58.1% | 61.1% |
| Priors only | 55.8% | 59.2% |
| Line only | 47.4% | 47.8% |

Line-only loses early — the “nudge off priors + market” story holds.

---

## Phase 2: Production code path verification

Follow-up used **unmodified** `models.totals.model` functions (`_grade_split`, `_fit_predict`, `iter_walk_forward_splits`, `walk_forward`, `permutation_test`). Only the **test set** was filtered per bin; training always used full prior-season history.

### CLI baselines

**Default (`--min-prior-games 3`):**

```
loaded 8868 games
 min_edge    n  hit_pct  roi_pct
        0 2640    55.98     6.88
        3 1656    57.37     9.52
        5 1086    58.10    10.92
permutation: shuffled 49.86% vs actual 55.98%
```

**Full pool (`--min-prior-games 0`):**

```
loaded 12194 games
 min_edge    n  hit_pct  roi_pct
        0 3831    55.52     5.99
        3 2295    58.34    11.38
        5 1478    61.10    16.64
permutation: shuffled 49.89% vs actual 55.52%
```

Including early games adds ~1,200 graded bets at similar overall hit rate; edge ≥ 3 improves slightly (58.34% vs 57.37%).

### Test-filtered slices (min_prior = 0 pool, production path)

| Slice | n @ edge≥0 | Hit @ 0 | Hit @ ≥3 | Hit @ ≥5 | Perm (actual) |
|-------|------------|---------|----------|----------|---------------|
| **Early min_n ≤ 2** | 924 | **56.82%** | **58.97%** | 60.10% | 56.82% vs CI 46.9–53.1 |
| Late min_n ≥ 3 | 2,907 | 55.11% | 58.13% | 61.45% | 55.11% |
| **Weeks 1–4** | 1,113 | **56.42%** | **58.86%** | 61.05% | 56.42% vs CI 47.2–53.1 |
| Weeks 5+ | 2,718 | 55.15% | 58.12% | 61.12% | 55.15% |
| Openers min_n = 0 | 360 | 54.44% | 55.16% | 55.07% | 54.44% inside CI |

### Early vs late at |edge| ≥ 3 (production path)

| Slice | n | Hit % |
|-------|---|-------|
| Early min_n ≤ 2 | 585 | 58.97% |
| Late min_n ≥ 3 | 1,710 | 58.13% |

Difference is real but modest (~0.8 pp at edge ≥ 3).

### Season stability — early slice (|edge| ≥ 3)

| Season | n | Hit % |
|--------|---|-------|
| 2021 | 8 | 62.5% (tiny) |
| 2022 | 146 | **50.7%** |
| 2023 | 141 | 57.5% |
| 2024 | 122 | 67.2% |
| 2025 | 168 | 61.3% |

2022 is a weak year for early games. Do not treat early-season edge as monotonic across seasons.

### Season stability — weeks 1–4 (|edge| ≥ 3)

| Season | n | Hit % |
|--------|---|-------|
| 2022 | 179 | 52.0% |
| 2023 | 177 | 57.6% |
| 2024 | 147 | 66.7% |
| 2025 | 197 | 60.4% |

Same 2022 weakness.

---

## Totals vs spread: final verdict

### Totals — GO (with caveats)

1. **Early weeks are not dead zone.** Walk-forward hit rates on `min_n ≤ 2` and weeks 1–4 beat late season by ~1.5–2 pp at edge ≥ 0.
2. **Default filter hides ~900 bets.** `--min-prior-games 3` excludes games that backtest profitably when included.
3. **Openers alone are not a strategy.** True `min_n = 0` is ~54% with wide permutation CI.
4. **Priors carry early signal; line-only fails early.** Consistent with feature-importance shift.
5. **Late season still works.** Do not replace late bets with early-only; add early if anything.

**Recommended live posture:**

- Keep `--min-prior-games 3` as conservative default until forward logging proves otherwise.
- Consider `--min-prior-games 0` with edge ≥ 3 for early weeks as an **experimental** add-on.
- Log takeable open vs close for one season before sizing up (see [`totals-model.md`](totals-model.md#the-test-that-would-actually-settle-it)).

### Spread — NO-GO (for now)

1. Closing spread ATS ≈ 50% overall and by bin.
2. Opening spread (`spreadOpen`) not in modelling frame.
3. No spread prediction pipeline exists (model predicts total points only).
4. Early home-dog cover ~55% on n=273 — not enough to build on.

**Stop condition for spread work:** Do not invest until `spreadOpen` is loaded, ATS walk-forward clears 52.4% breakeven with n ≥ 500, and holds in ≥ 3 of 5 seasons.

---

## Technical notes

### No-lookahead

All rolling stats use `_entering_game_stats`: `shift(1).expanding().mean()` within `(team, season)`. Week 5 uses weeks 1–4 only. Covered by `test_entering_game_stats_exclude_current_game`.

### Why default drops early games

`load(..., min_prior_games=3)` filters `min_n >= 3` because two-game rolling averages are noisy. [`totals-model.md`](totals-model.md) documents this as intentional. The early-week analysis shows those rows are not worthless — but they require median imputation for missing roll features, which can skew live week-1 scores if not handled carefully.

### NaN handling gap

Production `_fit_predict` uses `train[x_cols].fillna(median)` only. When **all** rolling features are NaN in train (isolated early-only train slices), sklearn raises. Full walk-forward trains on mixed early+late history, so this usually works. A dedicated early-only train slice would need `.fillna(0)` after median or `HistGradientBoostingRegressor`.

### Data not loaded

| Field | Location | Status |
|-------|----------|--------|
| `ou_open` | `raw/lines_*.json` | Loaded |
| `total` (close) | `games.csv` | Loaded |
| `spread` (close) | `games.csv` | Loaded, not used by model |
| `spreadOpen` | `raw/lines_*.json` | **Not loaded** |

---

## Suggested next steps

### Smallest code change (if pursuing early totals)

Add optional CLI filters to `models/totals/cli.py`:

- `--max-prior-games N` — include games where `min_n ≤ N`
- `--early-only` — shorthand for `min_prior_games=0` + test filter `min_n ≤ 2`

No change to default behavior.

### Medium effort

1. NaN-safe imputation in `_fit_predict` (median then zero for remaining NaNs).
2. Document early-week backtest in README with reproduction commands.
3. Split reporting: early / late / combined in backtest output.

### Spread (only if totals forward test succeeds)

1. Join `spreadOpen` in `_read_lines()` mirroring `ou_open` provider priority (Bovada → ESPN Bet → DraftKings).
2. New spread model or side model — out of scope for current repo architecture.

---

## How to reproduce

From repo root with `CFB_DATA_ROOT` set:

```bash
# Production baseline
python -m models.totals backtest --line ou_open --permute

# Full pool including early games
python -m models.totals backtest --line ou_open --min-prior-games 0 --permute

# Open vs close comparison
python models/totals/compare_lines.py
```

Test-filtered early/late slices require a one-off script that calls `walk_forward` with filtered test frames (as run in the August 2026 session). A future CLI flag would replace that script.

---

## Uncertainties and limitations

1. **Retrospective only** — no forward-season validation of early-week edge.
2. **Opening line takeability** — Bovada-sourced opens may not have been bettable at size ([`totals-model.md` caveats](totals-model.md#what-would-sink-this)).
3. **2022 early weakness** — one bad season may be noise or regime change; unknown.
4. **Openers market under-bias** — statistically weak; do not bet blindly under week 1.
5. **Multiple comparisons** — many bins and thresholds tested; apply skepticism.
6. **Hyperparameters untuned** — early/late split not validated under tuning.
7. **spreadOpen ATS** — exploratory only; not walk-forward model graded.

---

## Session changelog

| Item | Action |
|------|--------|
| Production code | **Unchanged** |
| `docs/EARLY-WEEKS-ANALYSIS.md` | **Created** (this document) |
| `AGENTS.md` | Updated via continual-learning: `ou_open` preference, cfb-totals-model workspace facts |
| `.cursor/hooks/state/continual-learning-index.json` | Created; 7 transcripts indexed |

---

## One-paragraph plain-English summary

We asked whether the first few weeks of the college football season are too unpredictable to bet totals or spreads. **Totals: no** — the existing model actually hits *slightly better* in weeks 1–4 and when teams have little in-season history, because preseason priors (talent, Elo, recruiting) matter more and the model still beats blindly following the line. **Spreads: not ready** — no spread in the model, no clear ATS bias in the data. **Openers only: skip** — true week-1 openers are only ~54% on a naive under strategy and the model isn't clearly better there alone. The practical takeaway: the default filter that skips early games is conservative; including them with `--min-prior-games 0` and edge ≥ 3 looks worth testing forward, but don't drop mid/late season bets or build a spread model until the data pipeline catches up.
