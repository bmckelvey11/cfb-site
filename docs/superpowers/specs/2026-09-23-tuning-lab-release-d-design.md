# Tuning lab Release D: probabilistic decisions — design

**Status:** declared 2026-09-23, before any distribution was scored. The user asked for
Release D to be built end to end ("start on D and finish unless I'm needed"). Every
choice below is Claude's default; the one the user may want to override is in
*Priced evaluation is deferred*.
**Builds on:** [`docs/model-tuning-lab-plan.md`](../../model-tuning-lab-plan.md) §40
Release D, §28 (targets, joint coherence, distributions, conformal policy), §30 (metrics),
§31 (betting execution engine); Release C
([`2026-09-23-tuning-lab-release-c-design.md`](2026-09-23-tuning-lab-release-c-design.md))
and its published run `run-de1927346ab0`.
**Review:** none cross-model (Codex sandbox error 206). An advisor pass set the hash pin,
the link to Release C by run id, declare-before-score, and the engine's refusal of
unpriced numbers.

## Goal and go/no-go

Turn Release C's point forecasts into predictive distributions of the full-game total,
check that they are calibrated, and build the machinery that turns a distribution and a
real quote into a priced decision.

- **Go/no-go (plan §40):** distributional outputs are calibrated on outer folds, and any
  betting claim survives realistic price and line degradation and threshold sensitivity.
- **This release makes no betting claim** (see *Priced evaluation is deferred*), so the
  second clause holds trivially. The first is tested once, on 2021–2025, against the gate
  below.

## Priced evaluation is deferred to Release E

Timestamped, priced totals quotes exist for 2026 only:

- Action Network ticks from 2026-04-02, keyed by AN `event_id`, not CFBD `game_id`.
- the-odds-api from 2026-09-09.

No earlier season has both a capture time and a price
(`docs/pregame-replay-2026-09-22.md`; the source audit behind this spec). A priced
backtest in Release D would have four problems:

1. It would need 2026 rating snapshots, which the Release B CSV does not hold.
2. It would need an AN-to-CFBD event crosswalk, which lives in a warehouse table that is
   being rebuilt now.
3. It would cover about four weeks.
4. It would spend the only priced season on an unfrozen policy.

So Release D builds the engine and proves it on hand-computed fixtures and synthetic rows
that use the real AN column names. A read-only pass over the real tick CSV reports counts
and quote ages only: no outcomes and no units. The first priced run belongs to Release E's
shadow period, on 2026 ticks with a policy frozen beforehand.

## Decisions

| Decision | Choice |
| --- | --- |
| Link to Release C | Read the selected `ModelSpec` from `run-de1927346ab0`'s verified `outer/*.json`. Refuse if C's source sha256s differ from today's files. Record C's `run_id` and `code_sha256` |
| Contract | New types in `models/tuning/dist_spec.py` with their own hash (`dist-<hash12>`). `RunSpec` is untouched; a test pins `total_ratings_v1` to `run-de1927346ab0` |
| Representation | One probability table per game over integer totals 0–150, overtime included. Every score and every price derives from it. Stored as `.npy` (deterministic bytes) with a game-id CSV |
| Point forecasts | Season-ahead: each season is fit on every earlier usable season with C's selected model. For 2021–2025 this must reproduce C's outer predictions exactly (asserted) |
| Residual window | Time-aware: out-of-fold residuals from the K = 3 most recent usable seasons before the test season. Split into early (a team with fewer than 3 prior games) and primary pools, per §28.2 |
| Candidates | See the next section |
| Selection | Lowest mean CRPS on inner test seasons 2018–2019. The 2018 window, 2015–2017, is the first complete one |

**Candidates.**

1. `normal_const` (baseline): $\mathcal N(\hat\mu, \sigma^2)$, with $\sigma$ the standard
   deviation of the window's total residuals, discretized to integer bins.
2. `empirical_total`: $\hat\mu$ plus every residual in the game's segment pool, rounded to
   integers.
3. `joint_bootstrap`:
   - home and away regulation points each get a C-model mean;
   - both are shifted by residual pairs taken from the same historical game in the
     segment pool, then rounded and floored at 0;
   - a regulation tie adds an overtime total drawn from the window's overtime games.

   Total and home-win probability come from the same draws (a regulation tie counts
   as half a home win).

## Calibration gate (declared; applied once to the selected candidate on 2021–2025)

- **PIT:** mid-distribution PIT, $F(y-1)+\tfrac12 p(y)$. It is deterministic, and it is
  unbiased for integer outcomes.
- **Coverage, pooled:** the share of games whose PIT lies in the central $1-\alpha$ band.
  It must be within ±0.03 of nominal at 50%, 80%, and 90%.
- **Coverage, per season:** 80% coverage within ±0.06 in every outer season.
- **PIT deciles, pooled:** every decile's share within ±0.02 of 0.10.
- **Result:** pass means go on clause 1. Failure is reported as a no-go. Nothing is
  re-tuned on 2021–2025.

**Expected weak spot.** The residual pools for 2021–2022 come from seasons whose
hyperparameters were tuned on those games (inner folds 2015–2019), so they may run narrow
and under-cover. If 2021 misses, the card names this cause.

## Also reported (not gated)

- **CRPS:** mean per candidate and per season. Paired CRPS difference against
  `normal_const`, with the Release B week-cluster bootstrap (10,000 draws, seed 20260922).
- **Other scores:** pinball loss at 0.05/0.10/0.25/0.50/0.75/0.90/0.95; interval widths.
- **Over/under the CFBD open label,** as a forecast of the event only:
  - Brier score and log loss of $P(\text{over})$, conditional on no push. A game whose
    total equals an integer label is excluded.
  - Reliability by decile.
  - This is not a price.
- **`joint_bootstrap` coherence and secondary scores:**
  - simulated overtime rate vs observed;
  - each game's table sums to 1;
  - the pooled mean matches the observed mean;
  - support covers the observed maximum;
  - home-win Brier (secondary).

## D2 — betting engine (`models/tuning/market.py`)

- **`Quote`** (frozen) follows §31.1.
  - `american_price` and `captured_at_utc` are required.
  - `decimal_price` must agree with the American price.
  - Only `market_type="total"` and `period="full_game"` are accepted.
  - An unpriced or untimed number, such as the CFBD open, cannot become a `Quote`.
- **Settlement.**
  - `settle(side, line, final_total, american, status)` returns win, loss, push, or
    no_action, and the units won.
  - Totals include overtime.
  - Cancelled, postponed, and suspended games are no_action.
  - `RESULT_LOGIC_VERSION = "totals_full_game_v1"` is stamped on every decision.
- **Pricing.**
  - `outcome_probs(pmf, side, line)` returns win, push, and loss probabilities at the
    exact number.
  - $EV = p_{win}\,b - p_{loss}$, where $b$ is the net profit per unit.
  - Multiplicative de-vig of a two-way pair.
- **Quote selection.**
  - Take the last non-live, available tick per book at or before `decision_ts`.
  - Refuse quotes older than `max_quote_age`.
  - Then pick by rule: best, median, or named book.
- **Policies.** `DecisionPolicySpec`, versioned separately from the model:
  - `no_bet`
  - `point_edge`, a threshold in points
  - `min_ev`
  - `prob_edge`, against the de-vigged market
  - abstention on `min_prior_games` and on the selective score (D3)
- **Backtest.** Flat one unit, with a ledger kept per §30.3:
  - forecast
  - edge versus the offered line
  - CLV against the last pre-kickoff tick of the same book and side, in points and in
    de-vigged probability
  - realized units
  - availability and quote age
- **Execution sensitivity:**
  - best, median, and named book
  - half-point line degradation
  - price degradation in cents
  - maximum quote age
  - missed-fill rate (seeded)
  - delayed decision
  - a threshold grid

  A scenario table flags a strategy as non-actionable when its units turn non-positive
  under modest degradation.
- **AN mapper.** `quotes_from_an_ticks(frame, event_to_game)` keeps full-game total ticks
  and drops live, unavailable, and alternate ones. `quote_id` = `an:<event>:<book>:<side>:<updated_at>`.
  The mapper works whether or not a crosswalk is supplied.

## D3 — selective prediction (`models/tuning/selective.py`)

- **Meta-model.** A Ridge meta-model predicts |residual| from the nine features plus
  `week`. It is trained only on out-of-fold residuals of seasons before the test season,
  per §31.4.
- **Risk-coverage curve.** Keep the fraction $c$ of games with the lowest predicted
  error, for $c \in \{1.0, 0.9, \dots, 0.5\}$, and report mean CRPS and MAE on the kept
  games.
- **Baselines:**
  - keep in random order (expected risk equals full-sample risk);
  - abstain when `min_prior_games < 3`.
- **Area under the curve (AURC)**, with the week-cluster bootstrap. Descriptive.

## D4 — join

- **CLI:** `python -m models.tuning dist --spec models/tuning/specs/dist_total_v1.json [--root DIR]`.
  - It reads C's run directory.
  - It writes `runs/dist-<hash12>/`, atomically and checksummed, as in C:
    - `dist_spec.json` and `manifest.json` (C `run_id` and code sha, source sha256s,
      git sha, packages)
    - `pmf_outer.npy` and `pmf_games.csv`
    - `predictions.csv` (quantiles, PIT, $P(\text{over})$ at the open label)
    - `scores.json` and `selective.json`
    - `card.md`
- **Reproducibility.** Two runs into two fresh roots give byte-identical `pmf_outer.npy`
  and `predictions.csv`.

## Files

| File | Role |
| --- | --- |
| `models/tuning/dist_spec.py` | `DistributionSpec`, `CalibrationGate`, `DistRunSpec`, `DecisionPolicySpec`, `ExecutionSpec` |
| `models/tuning/distributions.py` | Season-ahead forecasts, residual pools, the three candidates, scoring |
| `models/tuning/market.py` | `Quote`, conversions, settlement, pricing, selection, policies, backtest, sensitivity, AN mapper |
| `models/tuning/selective.py` | Meta-model and risk-coverage curves |
| `models/tuning/dist_run.py` | The join: link to C, run, gate, publish, card |
| `models/tuning/features.py` | Adds `home_reg`, `away_reg`, `ot_points` to the frame (targets, not features) |
| `tests/test_tuning_{dist_spec,distributions,market,selective,dist_join}.py` | One test file per track |

## What this cannot claim

- **No betting value, and no priced result.** No priced run happens in this release.
- **Weak evidence on 2021–2025.** Those seasons are a spent holdout. The calibration gate
  is a software go/no-go on a season range already used by earlier work, not new
  evidence about 2026.
- **Limits of the betting engine's proof.** It is shown correct on hand-computed cases,
  not on historical profits.
