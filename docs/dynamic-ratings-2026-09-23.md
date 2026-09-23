# Dynamic (Kalman) team ratings vs weekly ridge: a null at the screen gate

**Question.** Release F's first frontier experiment. Do team offense, defense, and pace
ratings that drift week to week forecast the FBS full-game total better than `ridge_v1`?
`ridge_v1` weights every game of the season to date equally.

**Answer: no. The dynamic ratings are worse, and F1 stops at its declared screen gate.**

- **Worse than ridge.** On 2021–2025, primary games, `kalman_v1` misses the total by 0.08
  points more than `ridge_v1` (+0.04 to +0.12). It is worse in all five seasons, and at half
  and at double the drift.
- **The tuned drift does not replicate.** The drift was picked on 2014–2019. On 2021–2025
  the same component loss is worse at that drift than at zero drift.
- **Recency weighting loses too.** An exponentially weighted ridge picked no decay on
  2014–2019, so `decay_v1` is `ridge_v1`.
- **No 2026 confirmation runs.** Stop rule 2 fired.
- **The screen is descriptive.** 2021–2025 is a spent holdout, and nothing was re-tuned
  after the screen.

Reproduce:

```text
python -m scripts.weekly_dynamic tune      # the tuning; the freeze is committed
python -m scripts.weekly_dynamic screen    # the screen; the gate is committed
```

- **Code:** [`scripts/weekly_dynamic.py`](../scripts/weekly_dynamic.py),
  tests in [`tests/test_weekly_dynamic.py`](../tests/test_weekly_dynamic.py).
- **Declared before tuning:**
  [`superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md)
  (`096a3e24`).
- **Freeze:** [`scripts/weekly_dynamic_v1.json`](../scripts/weekly_dynamic_v1.json) (`89eef2f8`), committed before the screen.
- **Gate:** [`scripts/weekly_dynamic_v1_screen.json`](../scripts/weekly_dynamic_v1_screen.json).

## Method

- **Model.** Release B's two components with drifting team effects.
  - Points per possession: league mean + offense + opponent defense + home edge.
  - Possessions: league mean + both teams' pace.
  - Each team effect follows a random walk between weeks, with drift variance $q$ as a
    share of the noise variance.
  - Each season starts at league average with prior variance $1/\lambda$, at Release B's
    λ 40 / 8. There is no carryover between seasons.
  - A forward Kalman filter gives the ratings at each week's cutoff. It is rebuilt from
    `ridge_v1`'s exact fit set: games that kicked off before the cutoff, drive-gated games
    excluded.
- **Nesting.** With $q = 0$ the filter is `ridge_v1`. The tests check this to $10^{-6}$ on
  synthetic data and on a real 2021 week 8 cutoff.
- **Tuning** (2014–2019, 85 cutoffs). Release B's one-step-ahead component loss.
  - Possession-weighted squared error of points per possession picks $q_{\text{PPP}}$.
  - Squared error of possessions picks $q_{\text{pace}}$.
  - The decay baseline weights each game by $\delta$ per week of age, and gets the same
    grid budget.
  - 24 grid points in all.
- **Screen.** Release B's populations, all with the Bovada open present.
  - **Primary:** both teams have at least 3 prior games.
  - **Early:** some team has fewer.
  - Paired MAE with the season-week cluster bootstrap (10,000 draws, seed 20260922).
  - Release B's verdict rule.
- **Gate, declared.** The 2026 confirmation runs only if `kalman_v1` − `ridge_v1` is
  *improves* on primary, and `kalman_v1` − `ridge_x0.5` is below zero.

## Data

- **Games.** FBS vs FBS regular season, weeks 2+.
  - Tuning seasons: 2014–2019.
  - Screen seasons: 2021–2025: 2,618 primary games in 61 season-week clusters, plus 862
    early games.
  - 2020 is excluded.
- **Sources.** Raw CFBD `games_<s>.json`, `drives_<s>.json`, and `lines_<s>.json`, as
  in Release B. The warehouse is not read.

## Numbers

**Tuning, 2014–2019** (component loss; lower is better):

| Grid | Zero | Picked | Loss at zero → at pick |
| --- | --- | --- | --- |
| $q_{\text{PPP}}$ | 0 | 0.001 | 97,157 → 97,003 (−0.16%) |
| $q_{\text{pace}}$ | 0 | 0.005 | 13,188 → 13,173 (−0.11%) |
| $\delta$, points per possession | 1 | 1 (no decay) | 0.98 already worse: 97,205 |
| $\delta$, pace | 1 | 1 (no decay) | 0.98 already worse: 13,202 |

**Screen, 2021–2025, primary** (MAE in points):

| Forecast | MAE |
| --- | ---: |
| Bovada open | 12.602 |
| `ridge_v1` (and `decay_v1`) | 12.937 |
| `kalman_v1` | 13.017 |
| `ridge_x0.5` (λ 20 / 4) | 13.185 |

| Comparison | Difference | 95% interval | Per season 2021 / 22 / 23 / 24 / 25 | Verdict |
| --- | ---: | --- | --- | --- |
| `kalman_v1` − `ridge_v1` | +0.080 | +0.040 to +0.123 | +0.11 / +0.08 / +0.03 / +0.09 / +0.08 | worse, at ×0.5 and ×2 drift too |
| `kalman_v1` − `ridge_x0.5` | −0.168 | −0.234 to −0.101 | all negative | (reported) |
| `kalman_v1` − open | +0.415 | +0.260 to +0.563 | | (reported) |
| Early: `kalman_v1` − `ridge_v1` | +0.013 | +0.001 to +0.027 | | (reported) |

**Why the tuned drift failed** (descriptive; the same component loss on 2021–2025):

| $q_{\text{PPP}}$ | 0 | 0.0001 | 0.0003 | 0.001 (frozen) | 0.003 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Loss | 83,156 | 83,133 | 83,112 | 83,224 | 84,279 |

At the frozen drift, the points-per-possession loss is worse than at zero drift. The best
drift on these seasons is a third as large and gains 0.05%. Pace's frozen drift still helps
there (9,717 → 9,713), but by far too little to offset it.

**Confirmation power, had the gate passed.** 2025 weeks 9+ held 351 primary games in 8
week clusters. The projected MDE (80% power) there is 0.16 points, twice the 0.08 difference the
screen measured.

## What this changes downstream

- **`ridge_v1`'s equal weighting stands** for within-season ratings. Neither a random walk
  nor recency decay improves it.
- **The frontier backlog entry is closed** for this data grain. The family is retired until
  the grain changes, for example to play-by-play state or player availability.
- **No 2026 look.** Weeks 9+ of 2026 stay untouched by this question.

## What this does not support

- **Not a statement about all dynamic models.** It covers a Gaussian random walk on
  season-to-date game results, with Release B's components and λ.
  - A model with jumps (change-points at quarterback or coaching changes) is a different
    family.
  - So is one that carries state across seasons, which belongs to `prior_v3`.
- **Not tuned on the total.** The declared loss was Release B's component loss. Tuning on
  total MAE would be a new trial on a spent holdout, and was not run.
- **No betting value.** The open has no capture time and no price.
