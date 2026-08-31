# cfb-totals-model

A walk-forward backtest harness for a college-football totals model. Predicts
combined points, then bets the side the market disagrees with.

After dropping leaked this-game features (havoc, attendance, post-game
winProb), the **citable** 2022–25 prior-season book hits **49.69%** (week-clustered
95% CI 47.66–51.71, n=2,383) against the opening total — below −110 breakeven,
and indistinguishable from shuffled predictions. A previous 57% figure is
invalid; see [`docs/MODEL.md`](docs/MODEL.md).

## Install

```bash
pip install -r requirements.txt
```

Needs a [cfb-site](../cfb-site) checkout with scraped data. By default it looks
at `../cfb-site/data`; override with `--data-root`.

Required under that directory:

| path | supplies |
|---|---|
| `processed/games.csv` | game index, final scores, closing total |
| `processed/features.json` | registry features (talent, Elo, weather) |
| `raw/games_*.json` | kickoff timestamps, team names |
| `raw/lines_*.json` | per-provider lines incl. `overUnderOpen` |
| `raw/advanced_game_stats_*.json` | per-team-game pace and efficiency |

## Use

```bash
python -m cfb_totals_model backtest --line ou_open --permute
```

```bash
python -m cfb_totals_model importance --line ou_open --top 15
```

```bash
python compare_lines.py
```

`--line ou_open` grades against the opening total (the number you can actually
bet). `--line total` grades against the close — useful as a reference point,
not as a strategy, since nobody gets the closing number.

Default `--seasons` is 2021–25. The **headline** table is 2022–25 prior-season
folds; 2021 week-expanding is printed as an appendix. `|edge| ≥ 0` is the
citable row; other thresholds are diagnostic.

## What it produces

```
loaded 8868 games | 35 features | line=ou_open

headline: prior-season folds only. |edge| >= 0 is the citable row; other thresholds are diagnostic.
 min_edge    n  hit_pct  hit_ci_lo  hit_ci_hi  mde_pp  roi_pct
        0 2383    49.69      47.66      51.71    2.89    -5.15

paired MSPE vs line: Δ=+22.767  (neg = model better)
permutation (headline): shuffled 49.91% vs actual 49.69%
```

The model does not beat the opening line as a point forecast (paired MSPE/MAE
Δ > 0, CI excludes 0). Hit rate is not a proper score; it is reported next to
that paired Δ.

## Tests

```bash
python -m pytest
```

Checks cover no-lookahead rolling stats, leaked-column exclusion, walk-forward
splits, paired MSPE on the same games, and open-vs-close pairing that drops
one-sided pushes. See `tests/`.

## Status

Retrospective only. On the clean feature set there is no evidence of edge vs
the opening total. Opening lines still come mostly from a soft book whose
numbers may not have been takeable at size.

