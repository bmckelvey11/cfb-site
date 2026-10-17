# Team rating models: roadmap

This is the plan side of the design review Blake shared on 2026-10-17: what to build, in what
order, and what each step must pass before the next one starts. The reasoning behind each item
is in [`rating-model-theory.md`](rating-model-theory.md). Nothing here is built unless its
**Status** says so. The plan is living: when an item lands or is dropped, its row changes in
the same commit.

Scoring rules for every step below are set by
[`docs/model-evaluation-standard.md`](../../docs/model-evaluation-standard.md). Where this
page and the standard disagree, the standard wins.

## 1. Three products, kept separate

| Product | Purpose | Primary target | Status |
| --- | --- | --- | --- |
| Strength model | Explain and forecast team performance | Points per possession, possessions, margin | Glicko P1.1 (margin) and `ridge_v1` (O/D/pace) are live |
| Market overlay | Find information the line lacks | Outcome minus the market number available at decision time | Only as a test: Glicko's encompassing slope, sealed 2026 confirmation pending |
| Decision engine | Turn calibrated probabilities and prices into bets | Net expected value after vig | Exists for other units (system maker, over-zero); not wired to ratings |

The strength model feeds the overlay. It is never assumed to be the betting model.

## 2. Promotion gates

Each gate is declared before its test runs and read once. A step that fails stays where it
is, and nothing built on top of it is promoted.

**Forecast gate.**
- Better out-of-sample log loss and Brier score than de-vigged market probabilities.
- Better CRPS and interval coverage than a market-implied score distribution.
- Stable across several held-out seasons.
- Holds after dropping outlier seasons and changing the garbage-time definition.

**Market-information gate.**
- Model edge predicts later closing-line movement, and the final residual against the market,
  not just the final score.
- Results by predeclared edge bucket rise with the edge.
- No dependence on one season, one conference or one extreme-total band.

**Betting gate.**
- Positive expected value after realistic vig, using only lines and prices available at the
  stated decision time.
- Enough volume for a meaningful interval.
- Conservative staking with exposure limits.
- Out-of-sample results not materially worse than development results.

The order is fixed: forecast accuracy, then calibration, then market information, then
betting. Skipping a link produces false confidence.

**Status:** the evaluation standard already requires intervals, proper scores against the
de-vigged market, trial counts and walk-forward folds. The Glicko work uses declared
holdouts and forecast fingerprints. What is new here is gating **complexity**. Per the review,
Glicko-2 volatility, rich roster priors and full Bayesian inference stay out until a simpler
model passes the market-information gate. Glicko has not yet passed it cleanly.

## 3. Nested chronological validation

For each evaluation season:

1. Use only earlier seasons to choose features, priors, garbage-time rules, process and
   observation noise, and regularisation.
2. Freeze the whole specification.
3. Start the season from preseason-available data only.
4. Replay games in kickoff order.
5. Save every pregame prediction before reading that game's result.
6. Score forecasts, calibration, market residuals, CLV and return.
7. Move to the next season without changing any earlier output.

**Status:** the Glicko freezes follow steps 2–5 for one fixed split (tune 2014–19, score
later). Re-tuning inside every fold (step 1 per season) is not done anywhere for ratings yet.
The review asks for it as a hard pipeline rule, not an analyst habit.

## 4. Baselines every new model must beat

| Target | Baseline | Status |
| --- | --- | --- |
| Win probability | De-vigged market moneyline | Partly: v1 used Bovada moneylines |
| Spread | Market spread at decision time; the close as a diagnostic | Bovada open used throughout |
| Game total | Market total at decision time | Bovada open, totals harness |
| Team total | Market team total at decision time | Over-zero unit |
| Margin or score | Home-edge mean, Elo, ridge O/D, market-implied score | All built. Implied score (2021–25 opens only): 2023–25 CRPS 6.21 per side, ahead of `ridge_v1` by 0.46 ([record](market-implied-score-baseline-2026-10-17.md)) |
| Pace | Season mean, team trailing average, opponent-adjusted ridge | `ridge_v1` pace |
| Early season | Prior-year carryover plus market | Glicko's offseason step is the carryover |
| Betting return | No bet, and market-only prediction | Per the evaluation standard |

The market-implied home and away scores are $(T \pm M)/2$ (theory §11). They should be the
first score baseline built, since they encode the market's joint view of strength and
scoring.
Built 2026-10-17
([`market-implied-score-baseline-2026-10-17.md`](market-implied-score-baseline-2026-10-17.md)).
Any score or O/D model now has to beat a pooled CRPS of 6.213 on 2023–2025 (SD 11.0 fixed
from 2021–2022) on the same games. CFBD has no open before 2021, so the baseline cannot be
scored earlier.

## 5. Market data as first-class data

Before any market-aware test, audit the odds at record level:

- Book.
- Market type, and spread, total or team-total designation.
- Price.
- Open or close label.
- Observed timestamp and ingested timestamp.
- Missing data by season, book, conference and week.
- Duplicates and stale records.
- Whether the line existed before the decision time.

Then bind every simulated decision to exactly one snapshot row. Proposed table:

```sql
model.market_snapshot
- market_snapshot_id
- game_id
- sportsbook_id
- market_type            -- spread | total | team_total | moneyline
- side
- line
- price_american
- observed_at            -- when the book showed it
- ingested_at            -- when we stored it
- is_opening_candidate
- is_closing_candidate
- source_name
- source_record_id
- data_quality_flag
```

**Status:** not built. Bovada's `spreadOpen` from CFBD has no observed-at timestamp, so
"available before decision time" is assumed, not checked. The totals research flags the
same gap.

## 6. Build sequence

### Phase 1: trustworthy benchmarks

| Step | Status |
| --- | --- |
| Market-data provenance audit (§5) | Not started |
| Freeze the game, possession, venue and market schemas | Games: raw CFBD files. Possessions, venues, market: not frozen |
| Fixed baselines: market-only, Elo, carry-forward, ridge O/D, simple pace | Elo, ridge O/D and pace built; market-only and implied-score not built |
| One walk-forward scoring harness for every model | Separate per family (Glicko, totals harness) |
| Season reports: forecast, calibration, CLV and vig-adjusted return | Forecast and calibration for Glicko; CLV and return not for ratings |

### Phase 2: strength model

| Step | Status |
| --- | --- |
| Dynamic offense, defense and pace states | `kalman_v1` built: **null** vs `ridge_v1`. Retry only with a stated reason it will differ |
| Student-t or possession-weighted PPP observations (theory §4) | Not built; the Glicko robust clip did nothing measurable |
| Hierarchical FBS / FCS and conference priors | Glicko P1 has conference-mean targets and the FCS pool. Bundle D tests the FBS-vs-FCS gap |
| Unit-specific offseason priors and uncertainty (theory §8) | Not built; P2 overall prior rejected; bundle B candidate |
| Score simulation with overtime handled separately | Not built; bundle C tests overtime as a regulation tie |

### Phase 3: market overlay

| Step | Status |
| --- | --- |
| Predict margin − spread, total − market total, and team score − team total | Not built |
| Start with ridge or elastic net plus a few preregistered nonlinear terms | Not built |
| Test whether model uncertainty predicts how reliable an edge is | Not built |
| Calibration and decision thresholds | Not built for ratings |

### Phase 4: research

| Step | Status |
| --- | --- |
| Possession-level likelihood | Not built |
| Low-rank covariance state space | Glicko bundle A carries full cross-team covariance for one rating |
| Forecast-consistent weather | Not built |
| Prospective QB and injury status collection | Not built; nothing historical is usable without timestamped archives |
| Team-total censoring replication | See [`models/over_zero/`](../../models/over_zero/) |
| Ensembles and Bayesian stacking | Only if earlier models add complementary out-of-sample information |

## 7. Feature blocks

Each block is added only after it clears an ablation test against the model without it.

- **Structural:**
  - competitive possessions and seconds per play, plus opponent-adjusted tempo
  - EPA per play or possession, success rate, explosiveness
  - field position
  - sack, havoc and pressure proxies
  - turnover rate (heavily shrunk)
  - red-zone finishing, fourth-down behaviour, special-teams EPA
  - regulation-only and overtime features
  - a 2023 clock-rule regime term
- **Market:**
  - open, current and decision-time lines, with price and de-vigged probability
  - line movement, and dispersion across books where it really exists
  - model–market disagreement
  - spread × total interaction, and nonlinear total bands
  - timestamp and source-quality flags
- **External** (only with as-of archives):
  - forecast weather, dome, altitude, travel and time zones, rest days
  - bowl status
  - coaching and QB continuity
  - returning production split by offense and defense
  - transfers, recruiting and talent

## 8. Not yet

Hold these until a simpler model passes the market-information gate:

- Full Glicko-2 team-specific volatility.
- Team-specific home edges.
- Large neural networks.
- Dozens of interaction terms picked after backtests.
- Injury features rebuilt from history without timestamped proof.
- Closing-line features in a model meant to decide earlier.
- Simulation-based staking before probabilities are calibrated.

The review also lists "dense covariance among every team" here. **Bundle A has already
frozen one.** It stays a candidate under its declared holdout. It is not promoted early, and
it is not withdrawn on the review's say-so.

## 9. Next decision

The review's single recommended build is a dynamic hierarchical offense / defense / pace
Kalman model on competitive PPP, with a market-residual layer on top. Its simplest form has
already failed here (`kalman_v1`). Two cheaper steps would de-risk a second attempt:

1. **The market-implied score baseline** (§4), which every score model must beat.
2. **The odds provenance audit** (§5), without which no market-overlay result can count.

Both are prerequisites in the review's own Phase 1.

**Status, 2026-10-17:** step 1 is built
([`market-implied-score-baseline-2026-10-17.md`](market-implied-score-baseline-2026-10-17.md)).
It beats `ridge_v1` by 0.46 CRPS per side on 2023–2025, so a second Kalman attempt has a
concrete bar. Its home and away errors are nearly uncorrelated (0.04), which lowers the
expected gain from modelling the two scores jointly. Its numbers stay provisional until step 2,
the odds provenance audit, says the open was known before kickoff.
