# Floor Bias model — Arscott (2022) censoring bias in CFB totals betting

**Floor Bias model** (the baseline; `v1`). Named for the mechanism: team scores
are censored at the **floor** of 0, biasing totals up → bet the over. It is the
mirror of the [Saturation Bias model](../saturation_bias/) (ceiling → under),
which fails. Floor Bias is the one that works.

Recreation of every model in **"Market efficiency and censoring bias in college
football gambling"** (Robert Arscott, Syracuse, SSRN 4197428).

## Paper summary

The point spread and team-totals lines *jointly* imply each team's expected
points. Actual points can't go below zero, so team scores are **left-censored at
0**. The betting lines are unbiased about the *latent* (uncensored) score, but
they don't account for censoring. Censoring inflates realized totals (you can
lose points off your prediction far more than you can on a blowout-low score
that's pinned at 0), so:

- **Totals line** = sum of both teams' censoring bias → always ≥ 0 → totals
  forecast errors skew right → the **over** is systematically underpriced.
- **Spread line** = favorite bias − underdog bias → mostly cancels (underdog,
  with the lower expected score, censors more) → spread stays unbiased.

Measure each team's expected censoring bias from a **Tobit** fit, then a
**probit** shows win probability on the over rises with that bias. Betting the
over only when expected bias > ~1.0 point won **55.72%** over two decades — above
the 52.38% break-even for standard −110 juice. Conclusion: the totals market is
semi-strong **inefficient**.

## Files

| File | What |
|------|------|
| `censoring_bias.py`     | All 10 models as pure functions over numpy arrays. |
| `demo_reproduce.py`     | Synthetic data calibrated to paper params; validates the chain. |
| `run_on_project_data.py`| Runs the same models on this repo's `data/processed/games.csv`. |

## Models recreated (paper equation → function)

| # | Model | Eq | Function |
|---|-------|----|----------|
| 1 | Implied team points | 6,7 | `implied_team_points` |
| 2 | OLS line-bias test (joint α=0, β=1 F-test) | 3,4 | `ols_line_test` |
| 3 | OLS team-points | 8,9 | `ols_line_test` |
| 4 | **Tobit Type-1 left-censored MLE** | 10,11 | `tobit_left_censored` |
| 5 | **Censoring bias (spread & totals)** | 12,13 | `censoring_bias` |
| 6 | Probit win model | 14 | `probit_win` → `ProbitFit.win_prob` |
| 7 | Even–Noble log-likelihood ratio test | 5 | `log_likelihood_ratio` |
| 8 | Game win prob = Φ(spread/σ) | §5 | `game_win_prob` |
| 9 | Strategy returns (unit, Kelly turnover, fractional-Kelly bankroll) | Tbl 5 | `strategy_returns`, `kelly_bankroll_roi` |
| 10 | 5-fold cross-validation | Tbl 6 | `kfold_cross_validate` |

`fit_pipeline` chains implied points → Tobit σ → censoring bias → probit.

## The math (model 5, the core)

For one team with latent points `x* ~ N(μ, σ²)` censored at 0, the bias of the
censored mean vs. the latent mean (paper footnote 4):

```
E[x | x*] − μ = σ·φ(μ/σ) − μ·Φ(−μ/σ)     ≥ 0
```

Summed/differenced across favorite and underdog (Eqs. 12, 13):

```
biasTotals = bias_fav + bias_dog     (≥ 0  → over edge)
biasSpread = bias_fav − bias_dog     (≈ 0  → spread stays fair)
```

Break-even threshold: with probit `P = Φ(const + slope·biasTotals)`, the bias
that clears 52.38% is `(Φ⁻¹(0.5238) − const)/slope`.

## Running it

```bash
# Recommended: load straight from raw lines (picks a book with BOTH spread and
# total, recovers ~2,800 games the consensus-only build drops). Needs --season.
python v1/run_on_project_data.py --raw --season 2013 2014 2015 2016 \
    2017 2018 2019 2020 2021 2022 2023 2024 2025

# Or from the processed build (../cfb-site/data/processed/games.csv):
python v1/run_on_project_data.py [--season 2024 2025]

# Synthetic self-test: Tobit recovers planted sigmas to 2 decimals.
python v1/demo_reproduce.py
```

Two data paths: `--raw` reads `data/raw/lines_{season}.json` (has scores +
every book's lines); default reads the consensus `games.csv`, which omits
seasons whose first usable book was spread-only (2013/2015/2016).

## Results — full backtest, 13 seasons of real CFBD data (2013–2025)

`--raw` pooled, **12,443 usable games** (paper sample: 13,276):

| Result | Paper | 2013–2025 |
|--------|-------|-----------|
| Spread line bias (F-test) | unbiased, p=0.27 | unbiased, p=0.63 |
| Totals line bias (F-test) | biased, p<0.01 | biased, p<0.001 |
| Tobit σ (dog / fav) | 11.28 / 11.94 | 11.03 / 11.77 |
| Probit slope on biasTotals | +0.117 | +0.176 |
| Over win% when bias > 1.0 | **55.72%** | **56.62%** |
| Unit return (flat −110) | +6.37% | +8.09% |
| K-fold out-of-sample | robust | 4/5 folds positive |

### Per-season, bet the over when expected censoring bias > 1.0

Stake column is **quarter-Kelly** compounded bankroll ROI (¼ × full-Kelly each
bet, sequential).

| Season | N | Win% | Unit% | ¼-Kelly bankroll ROI |
|--------|---|------|-------|----------------------|
| 2013 | 26 | 53.85% | +2.8% | −2.3% |
| 2014 | 25 | 64.00% | +22.2% | +41.8% |
| 2015 | 14 | 50.00% | −4.6% | 0.0% (model stakes ~0) |
| 2016 | 31 | 51.61% | −1.5% | −2.1% |
| 2017 | 17 | 52.94% | +1.1% | +3.9% |
| 2018 | 41 | 58.54% | +11.8% | +87.5% |
| 2019 | 54 | 62.96% | +20.2% | +67.2% |
| 2020 | 21 | 57.14% | +9.1% | +15.9% |
| 2021 | 78 | 57.69% | +10.1% | +119.4% |
| 2022 | 96 | 55.21% | +5.4% | +16.5% |
| 2023 | 76 | 55.26% | +5.5% | +61.3% |
| 2024 | 93 | 58.06% | +10.9% | +66.8% |
| 2025 | 79 | 55.70% | +6.3% | −3.9% |
| **Pooled** | **680** | **56.62%** | **+8.1%** | († see note) |

† Pooled compounded ¼-Kelly was +1288% (13.9× over 13 yr) but assumes
bet-by-bet sequential compounding; bets cluster on same-day slates where
resizing on settled outcomes is impossible, so treat win%/unit% as the
headline and the compounded figure as an in-sample upper bound.

11/13 seasons profitable on win rate; aggregate 56.62% over 680 bets beats the
paper's 55.72%. Losing seasons (2015, 2016) are tiny-N and 2015's probit slope
flipped negative — looks like variance, not regime change.

**Kelly sizing notes.** Three return figures, don't conflate them:
- *Unit return* — flat stake, profit / total staked. Order-independent.
- *Kelly turnover return* — profit / total staked at full Kelly; invariant to a
  flat fraction, so reported at full Kelly.
- *Fractional-Kelly bankroll ROI* — sequential compounding at `kelly_fraction`
  (¼ here). This is where fractional Kelly matters: full Kelly on this edge
  stakes ~5%/bet and compounds to absurd, high-variance numbers; quarter-Kelly
  (~1.4%/bet) is the practical choice — far smaller drawdowns for ~⅓ the growth.
  Compounded figures depend on bet order and are in-sample.

## Caveats

- **Data depth.** CFBD betting lines only populate from 2013 (2012 lines are
  empty; pre-2013 unavailable). Scores go back to 1992 but are unusable without
  lines. Paper's 1992–2017 came from Goldsheet, a different source.
- **In-sample.** Per-season and pooled win rates are in-sample (k-fold is the
  out-of-sample check). Compounded bankroll ROIs depend on bet order. The
  stricter walk-forward protocol (train on seasons ≤ t−1 only — see
  [monitor/](../monitor/)) pools 56.83% over 681 bets with the Wilson 95%
  lower bound above breakeven, so the edge survives honest time ordering.
- **Book selection.** The `--raw` loader takes consensus if present, else the
  first book carrying both lines — an arbitrary book could in principle be a
  soft line flattering the edge. Consensus-only sensitivity (2013–2025):
  4,927 games, 282 bets at bias > 1.0, **58.16%** win (Wilson 95%
  [52.3, 63.8], unit +11.0%) — the edge is not an artifact of soft books.
- Tobit/probit standard errors use the BFGS inverse-Hessian approximation, not
  the analytic information matrix — fine for inference here, tighten if needed.
- Models assume favorite/underdog score errors are independent (paper's
  assumption: cov(δ₁, δ₂) = 0).
- No live-odds or vig modeling: assumes standard −110 (52.38% breakeven). A book
  that tilts juice on the over when bias is high would erode the edge.
```
