# Predictive distributions of the game total: calibration, and P(over) the open

**Question.** Turn the tuning lab's point forecast of the FBS full-game total into a full
predictive distribution. Is that distribution calibrated on 2021–2025? And does its
probability of the over beat a coin flip against the CFBD open label?

**Answer.**

- **Calibrated: yes.** The selected distribution, a joint home/away model, passes every
  declared coverage and PIT check on 2021–2025. Its 80% intervals cover 80.8% of games,
  and every season falls between 79.7% and 82.8%.
- **P(over) the open: no skill.** A Brier score of 0.257 is worse than the 0.25 of always
  saying 50%. The distributions are honest about their own uncertainty, but they carry no
  information about which side of the open label the total lands on. This matches the
  point forecast's 0.38 MAE gap to the open.
- **Abstaining on predicted-hard games does not help.**

These are descriptive results on a spent holdout, and nothing here is priced.

Reproduce:

```text
python -m models.tuning run --spec models/tuning/specs/total_ratings_v1.json
python -m models.tuning dist --spec models/tuning/specs/dist_total_v1.json
```

- **Code:** [`models/tuning/distributions.py`](../models/tuning/distributions.py),
  [`dist_run.py`](../models/tuning/dist_run.py),
  [`selective.py`](../models/tuning/selective.py).
- **Declared before scoring:**
  [`superpowers/specs/2026-09-23-tuning-lab-release-d-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-d-design.md)
  (`44b9eea`), with the run spec committed in `7c0962c`.
- **Run:** `dist-0b0cc0382eca`, on point-forecast run `run-de1927346ab0`. Two separate
  processes writing to fresh roots gave byte-identical tables, predictions, and scores.

## Method

- **Point forecasts.** Season-ahead forecasts from the tuning lab's selected model: Elastic
  Net, $\alpha$ 0.042, L1 ratio 0.031, on nine `ridge_v1` as-of features. Each season is
  fit on every earlier season, 2020 excluded. For 2021–2025 these equal the base run's
  outer predictions exactly. Separate forecasts of home and away regulation points use
  the same model.
- **Residual window.** Out-of-sample residuals from the three seasons before the test
  season. They are split into early games (a team with fewer than 3 prior games) and the
  rest.
- **Three candidates.** Each produces one probability table per game over integer totals
  0–150, overtime included.

  | Candidate | How its table is built |
  | --- | --- |
  | `normal_const` (baseline) | A normal distribution with the window's residual SD |
  | `empirical_total` | The forecast plus every window residual, rounded |
  | `joint_bootstrap` | Home and away regulation forecasts, each shifted by a residual pair from one historical game. A regulation tie adds an observed overtime total |

- **Selection.** Lowest mean CRPS on 2018–2019. CRPS for an integer outcome $y$ and
  table CDF $F$ is $\sum_k (F(k) - \mathbf{1}\{y \le k\})^2$, in points; lower is better.
- **Gate.** Declared before scoring and applied once to the selected candidate on
  2021–2025. It uses mid-PIT, $F(y-1) + \tfrac12 p(y)$.

  | Check | Tolerance |
  | --- | --- |
  | Pooled coverage at 50/80/90% | ±0.03 |
  | 80% coverage in each season | ±0.06 |
  | Share in each PIT decile | ±0.02 |

- **Open label.** $P(\text{over})$ at Bovada's `overUnderOpen`, conditional on no push. A
  game landing exactly on an integer label is excluded (36 games).
- **Selective prediction.** A fixed Ridge predicts |residual| from the features and the
  week, trained on window seasons only. The risk-coverage curve keeps the
  lowest-predicted-error games.

## Data

- **Games.** 2021–2025 week-2+ FBS-vs-FBS regular-season games: 3,488, in 72 season-week
  clusters. 3,444 have an open label and no push.
- **Selection seasons.** 2018–2019.
- **Sources.** Raw games and drives JSON, the Release B snapshot CSV, and `lines_<s>.json`.
  The run refuses to start if any of them hashes differently from what the base run
  recorded.

## Numbers

**Selection, 2018–2019 mean CRPS:**

| Candidate | Mean CRPS |
| --- | ---: |
| `joint_bootstrap` (selected) | 9.699 |
| `empirical_total` | 9.704 |
| `normal_const` | 9.720 |

**Gate, `joint_bootstrap`, 2021–2025: PASS.**

| Check | Value | Target |
| --- | ---: | --- |
| Coverage 50% | 0.512 | 0.50 ± 0.03 |
| Coverage 80% | 0.808 | 0.80 ± 0.03 |
| Coverage 90% | 0.905 | 0.90 ± 0.03 |
| Coverage 80%, by season 2021–2025 | 0.828 / 0.799 / 0.807 / 0.797 / 0.812 | 0.80 ± 0.06 each |
| Largest PIT-decile deviation | 0.011 | ≤ 0.02 |

**All candidates, 2021–2025.** The CRPS difference is against `normal_const` on the same
games, with a week-cluster bootstrap (10,000 draws).

| Candidate | CRPS | vs normal | 95% interval | 80% width (pts) | P(over) Brier | Log loss |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| `joint_bootstrap` | 9.153 | −0.031 | −0.062 to −0.0002 | 42.8 | 0.2573 | 0.709 |
| `empirical_total` | 9.156 | −0.027 | −0.055 to +0.0001 | 43.1 | 0.2571 | 0.709 |
| `normal_const` | 9.184 | — | | 43.0 | 0.2582 | 0.711 |

- **Reading the Brier column.** A constant 50% scores 0.2500, and the over rate was 48.8%.
  All three candidates do worse than the constant.
- **Other candidates against the gate.** `normal_const` would fail it on PIT deciles
  (0.022); `empirical_total` would pass.
- **Joint model coherence.** The table's mean total is 53.79 against 53.85 observed. It
  simulates overtime in 2.0% of games against 4.8% observed. Rounding continuous residuals
  makes exact regulation ties too rare, but the total's calibration still passes.
- **Selective prediction.** Keeping the lowest-scored half gives CRPS 8.95 against 9.15
  for all games. The area under the curve minus full-coverage risk is −0.055
  (−0.166 to +0.046), so no gain can be shown. Skipping early games keeps 75%, at 9.13.

## What this changes downstream

- **Default distribution.** `joint_bootstrap` is the default table for any later pricing
  (Release E). Its intervals can be taken at face value on 2021–2025.
- **No betting signal against the open.** The model's over/under probability against the
  open label is not a betting signal. Beating a coin flip there is the minimum any
  priced policy would have to show first.

## What this does not support

- **No betting value.** The open label has no capture time and no price. Timestamped,
  priced totals quotes exist for 2026 only. The betting engine
  ([`models/tuning/market.py`](../models/tuning/market.py)) is verified on hand-computed
  fixtures and has not been run on real quotes.
- **Not new holdout evidence.** 2021–2025 was already used by Release B and the priors
  work. 2026 is the untouched season.
- **Not a statement about game-level uncertainty.** The distributions have constant
  spread within a segment, and the selective model found no usable per-game signal for
  when the forecast is worse.
