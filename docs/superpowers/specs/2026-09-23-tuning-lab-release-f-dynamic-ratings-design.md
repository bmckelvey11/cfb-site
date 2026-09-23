# Release F, experiment F1: dynamic ratings vs weekly ridge — design

**Status:** declared 2026-09-23 (`096a3e24`), before any tuning, screening, or confirmation
code ran. Tuned and frozen (`89eef2f8`). **Stopped at stop rule 2**: on the screen,
`kalman_v1` − `ridge_v1` is *worse* (+0.08 MAE). No 2026 look. Result:
[`../../dynamic-ratings-2026-09-23.md`](../../dynamic-ratings-2026-09-23.md).
**Plan of record:** [`../../model-tuning-lab-plan.md`](../../model-tuning-lab-plan.md) §40
Release F and §39 ("Dynamic Bayesian ratings"). One frontier family at a time.
**Builds on:** Release B's `ridge_v1` ([`../../weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md)):
0.33 points of MAE behind the Bovada open on 2021–2025.
**Chosen by the user:** this family first; confirmation on 2026 weeks 9+.

## Hypothesis card (§32.1)

| Field | Value |
| --- | --- |
| `hypothesis_id` | `HYP-F1-dynamic-ratings` |
| Claim | Team ratings that drift week to week forecast the full-game total better than `ridge_v1`, which weights every game of the season to date equally. |
| Mechanism | Teams change within a season: injuries, quarterback changes, scheme changes. A random-walk state discounts older games by exactly as much as the data say teams move. |
| Primary target | Full-game total, FBS vs FBS regular season. |
| Primary metric | Paired MAE difference, `kalman_v1` − `ridge_v1`, same games and same cutoffs. |
| Baseline | `ridge_v1` (λ 40 / 8, season to date). Also `ridge_x0.5` (λ 20 / 4) and `decay_v1`, an exponentially weighted ridge (§39's required baselines). |
| Outer tests | Screen on 2021–2025 (spent for other questions; descriptive). One confirmatory look on 2026 weeks 9+. |
| Practical improvement | Any gain that survives the screen gate. |
| Failure condition | Below, "Stop rules". |
| Follow-up if null | Record the null here and in a dated doc. Retire the family until the data grain changes (for example, play-by-play state). |

## Model

Release B's two components keep their form, but the team effects now move each week:

$$
\begin{gathered}
y_{g,s} = \mu + O_{s,t} + D_{o,t} + h\,H_{g,s} + \varepsilon_{g,s},\qquad
\varepsilon_{g,s}\sim\mathcal N\!\left(0,\ \sigma^2 / w_{g,s}\right) \\
O_{s,t} = O_{s,t-1} + \eta_{s,t},\qquad \eta_{s,t}\sim\mathcal N\!\left(0,\ q_{\text{PPP}}\,\sigma^2\right),\qquad
O_{s,t_0}\sim\mathcal N\!\left(0,\ \sigma^2/\lambda_{\text{PPP}}\right) \\[1em]
\begin{array}{rl}
\text{where}\quad y_{g,s}: & \text{side } s\text{'s regulation points per possession in game } g \\
w_{g,s}: & \text{side } s\text{'s regulation possessions (the observation weight)} \\
\mu,\ h: & \text{league mean and home edge, points per possession; near-flat prior, no drift} \\
O_{s,t},\ D_{o,t}: & \text{offense of } s \text{ and defense of opponent } o \text{ in week } t\text{; + = more points} \\
H_{g,s}: & +1 \text{ home},\ -1 \text{ away},\ 0 \text{ neutral} \\
\sigma^2: & \text{per-possession noise variance; it cancels, so only ratios matter} \\
\lambda_{\text{PPP}}: & \text{Release B's ridge penalty, 40 possessions, held fixed} \\
q_{\text{PPP}}: & \text{weekly drift variance as a share of } \sigma^2\text{; the one new parameter} \\
t_0: & \text{the season's first week}
\end{array}
\end{gathered}
$$

$D$ follows the same random walk as $O$ with the same $q_{\text{PPP}}$. Pace is the same
construction on game possessions: $N_g = \nu + P_{\text{home},t} + P_{\text{away},t} + \varepsilon$
with weight 1, prior variance $\sigma^2/\lambda_{\text{pace}}$ ($\lambda_{\text{pace}} = 8$
games) and drift $q_{\text{pace}}$.

A Kalman filter, run forward over the season's weeks, gives the ratings at each cutoff. It
adds the drift variance once per week step, then folds in that week's games. The total is
Release B's `forecast_total`: possessions times the two points-per-possession rates, plus
mean overtime points.

**Why this is a clean test.** With $q = 0$ the random walk never moves, so the filter's
answer is exactly the ridge solution: prior precision $\lambda$ is ridge's penalty, and the
possession weights are the same. `kalman_v1` at $q = 0$ *is* `ridge_v1`, and the tuning
decides whether any drift helps. A worked reading: $q_{\text{PPP}} = 10^{-3}$ against a prior
variance of $1/40 = 0.025$ lets a team's offense move by about $\sqrt{0.001/0.025} = 20\%$ of
its preseason spread each week.

## Declared rules

- **Season start: no carryover.**
  - Every season starts at league average: $O, D, P = 0$ with variance $1/\lambda$.
  - Only $\mu$, $h$, and $\nu$ get a near-flat prior (precision $10^{-6}$), and they do not drift.
  - The state holds every team in the fit set from the season's first week.
  - Carrying last season in would make this a prior experiment, which belongs to `prior_v3`.
- **Evidence.** The filter is rebuilt at each cutoff from `fit_set(season games, cutoff)`:
  the same games, gates, and cutoffs as `ridge_v1`. Week 1 is not forecast.
- **Tuning** (2014–2019, 2020 excluded): Release B's one-step-ahead component loss.
  - Possession-weighted squared error of points per possession picks $q_{\text{PPP}}$.
  - Squared error of possessions picks $q_{\text{pace}}$.
  - λ stays at 40 / 8.
  - **Grids:**
    - $q_{\text{PPP}} \in \{0, 10^{-4}, 3\cdot10^{-4}, 10^{-3}, 3\cdot10^{-3}, 10^{-2}\}$.
    - $q_{\text{pace}} \in \{0, 5\cdot10^{-4}, 1.5\cdot10^{-3}, 5\cdot10^{-3}, 1.5\cdot10^{-2}, 5\cdot10^{-2}\}$.
  - **`decay_v1`:** the same ridge with each game weighted by $\delta^{(t^{*}-1)-t}$, where
    $t^{*}$ is the forecast week, so the latest week has weight 1. The grid is
    $\delta \in \{1, 0.98, 0.95, 0.9, 0.85, 0.8\}$ for each component, at the same λ, with the
    same loss.
  - **Budget:** 24 grid points.
  - **Freeze:** the picks go to `scripts/weekly_dynamic_v1.json`, written once and committed
    before the screen.
- **Screen** (2021–2025, one run): Release B's populations, all with the Bovada open present.
  - **Primary:** both teams have at least 3 prior games.
  - **Early:** week 2 or later, but some team has fewer than 3 prior games.
  - **Primary comparison:** `kalman_v1` − `ridge_v1`, `classify_verdict` with the season-week
    cluster bootstrap (10,000 draws, seed 20260922).
  - **Also reported:**
    - `kalman_v1` − `ridge_x0.5`, `kalman_v1` − `decay_v1`, and `kalman_v1` − open.
    - $q$ stress at ×0.5 and ×2, with a stable-under-stress flag.
    - The MDE projected to the expected weeks 9+ game count.
- **Confirmation** (2026 weeks 9+, one look): the frozen `kalman_v1` against `ridge_v1` at
  40 / 8.
  - **Games:** FBS vs FBS, completed, Bovada open present, primary population.
  - **When:** the look runs only once no 2026 regular-season FBS game is still scheduled,
    using `prior_v3`'s `season_look`. Before that, `confirm` refuses. There is no interim run.

## Stop rules (the failure condition)

1. **No candidate:** if $q = 0$ wins both components, F1 stops.
2. **Screen gate:** the confirmation runs only if *both* hold on the 2021–2025 primary
   population.
   - `kalman_v1` − `ridge_v1` is *improves*.
   - `kalman_v1` − `ridge_x0.5` has a point estimate below 0. If it is not below 0, any gain
     over `ridge_v1` is less shrinkage, not dynamics, and F1 stops.

   The screen writes its gate once to `scripts/weekly_dynamic_v1_screen.json`, which is
   committed. `confirm` refuses without a passing gate.
3. **Confirmation verdict:**
   - *Improves* confirms.
   - *Matches* is unconfirmed, not failed.
   - *Worse* fails.

A stop at any rule writes a dated null-result doc. Nothing is re-tuned after the screen.

## Power, stated up front

- **Games:** weeks 9–13 of 2026 hold about 317 FBS-vs-FBS games, or about 290 once the
  open is required.
- **Clusters:** 5 week clusters, plus a championship game.
- **Bootstrap:** a percentile bootstrap over 5 clusters is coarse, and its interval is too
  narrow at that size. The screen reports the MDE for this count.
- **Expected outcome:** a gain as small as Release B's ridge-vs-raw steps (tenths of a
  point) will likely read *matches*. That is recorded as unconfirmed.
- **Overlap:** the same 2026 games also carry `prior_v3`'s sealed confirmation, with the
  same comparator. The two are separate hypotheses on shared games, and neither result is
  adjusted for the other.

## Files

- `scripts/weekly_dynamic.py`:
  - `tune --freeze`, `screen`, `confirm --season 2026`.
  - It imports Release B's `_team_rows`, `_solve`, `fit_set`, `forecast_total`, `run_season`,
    and `paired_mae_diff`.
  - `weekly_ratings.py` and `weekly_ratings_eval.py` are not edited: the shadow champion and
    `prior_v3` depend on them.
- `scripts/weekly_dynamic_v1.json` (freeze) and `scripts/weekly_dynamic_v1_screen.json`
  (gate): each written once.
- `tests/test_weekly_dynamic.py`:
  - $q = 0$ equals `ridge_v1` to $10^{-6}$ (synthetic), plus a slow test on a real 2021 cutoff.
  - Week $w$'s forecast is unchanged when results from week $w$ on change.
  - The freeze never overwrites.
  - `confirm` refuses without the freeze, without a passing gate, and before the season is
    final.
- A dated finding doc for the screen, and one for the confirmation.

## What this cannot claim

- **The screen is not holdout evidence.** 2021–2025 has served Releases B, C, and D and
  the priors work.
- **No betting value.** The open has no capture time and no price.
- **No claim about why teams move.** The filter says only how much they move.
