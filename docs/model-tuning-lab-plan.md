# CFB Model Tuning Lab

## A governed GUI for feature selection, Optuna tuning, opponent adjustment, preseason priors, and time-aware model validation

**Scope:** FBS college-football predictive and betting-market research. The platform supports game-level forecasts, team-game forecasts, totals, spreads, win probabilities, market-residual models, and carefully governed betting-system research.

**Primary stack:** Streamlit GUI + Python modeling engine + local DuckDB source of truth + optional MotherDuck publishing/mirroring + Optuna persistent studies + worker queue + Parquet/object-store artifacts.

**Revision:** 2.0 — expanded with the project research reports, warehouse catalog, prior design conversations, current MLOps guidance, probabilistic forecasting, realistic sportsbook execution, model-risk controls, observability, and implementation-level testing requirements. Release C below is split into parallel tracks.

**Repo copy.** This file is the plan of record. Math delimiters are `$` / `$$`. Equations keep the plan's "Where" lists and are not yet in the where-table form.

**Design position:** The Lab is a governed research control plane over immutable data snapshots and reproducible compute. It is not the warehouse, feature store, sportsbook screen, or production prediction service, although it coordinates all four.

---

## 1. Purpose

The CFB Model Tuning Lab is a research environment—not a one-click model optimizer. It should let a user:

1. Select a versioned, pregame-valid CFB feature table.
2. Choose a target and decision timestamp.
3. Add, remove, inspect, and version variables through a feature catalog.
4. Select an opponent-adjustment and preseason-prior strategy.
5. Configure a model family and a bounded Optuna hyperparameter space.
6. Evaluate configurations using strictly time-ordered, game-group-aware folds.
7. Monitor persistent Optuna trials and inspect trial-level outcomes.
8. Compare finalists against fixed football and market baselines.
9. Run a final untouched confirmation evaluation.
10. Generate a complete model card and preserve all experiment provenance.

The system must prevent accidental future-data leakage, indiscriminate feature fishing, repeated testing against a final holdout, and false confidence from a single historical ROI or a single favorable season.

---

## 2. Supported CFB objectives

The UI must require an explicit task template. A model trained for one target is not automatically valid for another.

| Task template | Unit of observation | Example target | Primary forecasting use | Market benchmark |
|---|---|---|---|---|
| Game total | One row per game | `home_points + away_points` | Project total scoring | Opening/closing total, consensus total |
| Team-game scoring | Two rows per game | Team points or scoring rate | Construct totals and spreads from components | Implied team total where available |
| Margin/spread | One row per game | `home_points - away_points` | Project game margin | Opening/closing spread |
| Win probability | One row per game | Home win indicator | Price moneyline / game winner | Closing moneyline implied probability |
| Market residual | One row per game | Actual target minus timestamped market forecast | Identify incremental information beyond market | The market value embedded in target construction |
| Line movement | One row per game/market timestamp | Close minus opener; later minus earlier | Forecast market movement, not game outcome | Opening or current line |
| Betting-system research | One row per candidate decision | Result, CLV, or price movement | Test disciplined rules, not generic prediction | Timestamped executable price |

### Recommended starting sequence

1. Build fixed-baseline total and margin models.
2. Add team-game component models for scoring and possession structure.
3. Add market-residual versions only after line timestamps, source/provider identity, and decision availability are fully auditable.
4. Treat system/rule optimization as a later project with its own severe anti-overfitting controls.

---

## 3. Non-negotiable timing rules

Every model run must declare a **prediction decision time**. All feature values must have been available no later than that timestamp.

### Example decision-time modes

| Mode | Intended use | Allowed data |
|---|---|---|
| Preseason | Week 1 forecasting | Previous-season data, offseason roster/staff/recruiting information captured before kickoff |
| Weekly early | Early-week number/market research | All completed games through prior week and timestamped early-week market data |
| Pre-kickoff | Final pregame forecast | All valid pre-kickoff information and a timestamped price/line snapshot |
| Postgame research | Descriptive analysis only | Completed game data; never eligible for pregame forecasts |

### Hard rules

- A feature record needs `feature_as_of_ts`; model input must satisfy `feature_as_of_ts <= decision_ts`.
- A game outcome, final box score, end-of-season adjusted statistic, later injury status, or closing line cannot appear in an earlier decision-time model unless it was genuinely available then.
- Season-final opponent-adjusted metrics must never be joined back to earlier weeks as if they were known at the time.
- Preprocessing statistics—imputation, scaling, transformations, feature selection, target encoding, PCA, winsor limits—must be estimated using the training subset within each fold only.
- A feature computed with a rolling window must exclude the current game and any later game.
- Market lines must retain provider, captured timestamp, and market type. Never silently substitute a close for an opener or an unavailable consensus number.

---

## 4. Data architecture

Keep raw CFBD payloads unchanged, transform them through staging, and expose pregame-valid model marts. The CFBD API covers game, team, player, recruiting, ranking, analytics, and related data; CFBD defines PPA as its implementation of EPA-like expected-points-added, so it should not be assumed numerically interchangeable with another provider’s EPA. [web:58][web:59]

### Warehouse layers

```text
raw
  ├── CFBD API payloads exactly as retrieved
  ├── market line snapshots exactly as captured
  ├── weather/injury/roster inputs with source timestamps
  └── ingestion metadata: source, request parameters, fetched_at, checksum

stg
  ├── stg_games
  ├── stg_teams
  ├── stg_team_game_stats
  ├── stg_advanced_game_stats
  ├── stg_play_by_play
  ├── stg_lines
  ├── stg_recruiting
  ├── stg_rankings
  ├── stg_rosters_and_transfers
  └── stg_coaching_history

core
  ├── dim_team
  ├── dim_conference
  ├── dim_season
  ├── dim_coach_stint
  ├── dim_venue
  ├── fct_game
  ├── fct_team_game
  ├── fct_play
  ├── fct_market_snapshot
  └── fct_preseason_team_snapshot

analytics
  ├── mart_cfb_team_week_pregame
  ├── mart_cfb_game_pregame
  ├── mart_cfb_team_game_pregame
  ├── mart_cfb_market_residual_pregame
  ├── feature_catalog
  ├── feature_values_audit
  ├── ml_experiments
  ├── ml_optuna_studies
  ├── ml_optuna_trials
  ├── ml_model_runs
  └── ml_predictions
```

### Essential model-table keys

A game-level model mart should contain at least:

```text
game_id
season
week
season_type
game_date_utc
kickoff_ts_utc
home_team_id
away_team_id
home_conference_id
away_conference_id
neutral_site
venue_id
division_or_subdivision
model_decision_ts
feature_as_of_ts
source_snapshot_id
market_snapshot_id
```

A team-game mart should additionally contain:

```text
team_id
opponent_id
is_home
is_away
is_neutral
team_points
opponent_points
team_possessions
opponent_possessions
```

---

## 5. GUI information architecture

**Status (2026-09-23): built** (`models/tuning/ui/`).

- **Start it:** `.venv-lab-ui\Scripts\python -m streamlit run models/tuning/ui/app.py`, or "Tuning Lab" in `.claude/launch.json`. It listens on 127.0.0.1 only (`.streamlit/config.toml`).
- **Pages:**
  - **New run** covers pages 01–06: template, dataset, features, validation, search, acceptance, then review and launch.
  - **Jobs** is page 07: state, Optuna trials, best-so-far chart, worker log, and a confirmed cancel.
  - **Runs** is pages 08–09: card, trials, comparisons, spec.
  - **Hypotheses** is page 10.
- **Only what `RunSpec` implements is editable.** Page 03 is read-only because the ratings come fixed from the Release B snapshot. The draft object below is one form rather than session-wide state.
- **Every check runs in `validate`** (`models/tuning/ui/api.py`, main `.venv`), so the GUI cannot skip one. Blocking errors:
  - RunSpec rules, such as the confirmation lock.
  - The sealed season, 2026.
  - A feature the catalog refuses.
  - A job still in flight.
- **Amber warning:** the outer seasons were already evaluated. Prior lab trials are counted from `jobs.sqlite3`.
- **Replicates:** the next free replicate is chosen explicitly.
- **Launch** re-validates the exact draft file, then starts a detached worker that outlives the GUI. It writes only `drafts/` and `logs/` under the lab root; nothing in the repo.
- **Separate venv:** the GUI runs in its own venv, `.venv-lab-ui` (`requirements-lab-ui.txt`), so the shadow tick's `.venv` never gains pyarrow.
- **Outside the run fingerprint:** `models/tuning/ui/` is not fingerprinted, so editing the GUI never makes a completed run look like it ran on different code.
- **Scratch lab:** `--lab-root DIR` or `CFB_LAB_ROOT` points the GUI at a scratch lab.

Use a Streamlit multipage app for the first implementation. Streamlit session state supports retaining variables across reruns within a user session, which is appropriate for an in-progress feature and tuning configuration. [web:32][web:33]

```text
CFB Model Tuning Lab
├── 01 Dataset & Task
├── 02 Feature Builder
├── 03 Opponent Adjustments & Priors
├── 04 Validation Design
├── 05 Model & Search Space
├── 06 Launch / Resume Optuna Study
├── 07 Study Monitor
├── 08 Candidate Review
├── 09 Confirmation & Model Card
└── 10 Experiment Registry
```

### Persistent configuration object

A page should edit a single structured draft rather than create disconnected widget values.

```python
st.session_state.experiment_draft = {
    "task": {},
    "data_contract": {},
    "feature_set": {},
    "opponent_adjustment": {},
    "preseason_prior": {},
    "validation": {},
    "model_search": {},
    "uncertainty": {},
    "decision_policy": {},
    "execution_assumptions": {},
    "acceptance_rules": {},
    "resource_policy": {},
    "reproducibility": {},
}
```

The app should run a validation function before saving or launching. It should display explicit blocking errors rather than silently repairing invalid configurations.

---

## 6. Page 1: Dataset and task

### Required controls

- Project: totals, spread/margin, moneyline, market residual, line movement, or system research.
- Dataset source: approved DuckDB/MotherDuck relation only for production experiments.
- Observation grain: game or team-game.
- Target column.
- Game date and kickoff timestamp columns.
- Decision timestamp and feature-as-of timestamp columns.
- Game ID / observation ID.
- Team, opponent, conference, season, and week identifiers.
- Market source, provider, market type, and quote timestamp when market features or benchmarks are used.
- Baseline forecast fields.
- FBS-only, FCS-only, or explicitly mixed population policy.
- Season type policy: regular season, conference championship, bowl/playoff, all.

### Data audit panel

Display before any model is allowed to run:

- Row count and games count.
- Date coverage and records by season/week.
- Missing target count.
- Duplicate game/observation IDs.
- Distinct teams and conferences.
- Home/away/neutral-site composition.
- FBS/FCS composition and cross-division games.
- Target distribution and extreme values.
- Missingness by candidate feature.
- Market coverage by season/provider/timestamp when relevant.
- Percentage of features passing the as-of rule.

### Inclusion-policy controls

The user must choose and record one policy for:

- FBS vs FCS games.
- Games with missing or unreliable market lines.
- Vacated games or later corrections.
- COVID-era or other unusual-season treatment.
- Bowls, playoff games, conference championships, and opt-out-heavy games.
- Neutral-site games and their home-field treatment.
- Overtime handling.

Do not let the app quietly drop rows. Every exclusion must be counted and recorded in the model card.

---

## 7. Page 2: Feature Builder

The feature builder lets a user add and subtract variables, but only from an explicit feature catalog.

### Layout

```text
Left: catalog filters
  ├── feature family
  ├── unit: team, opponent, matchup, market, environment
  ├── availability mode
  ├── data type
  ├── leakage status
  ├── version
  ├── missingness threshold
  └── season coverage

Center: selected feature set
  ├── baseline features
  ├── included features
  ├── optional feature groups
  ├── excluded / blocked features
  ├── save as versioned set
  └── compare with another saved set

Right: feature inspector
  ├── definition and formula
  ├── source lineage / SQL
  ├── grain and keys
  ├── availability / as-of logic
  ├── current missingness
  ├── distribution by season
  ├── correlation / redundancy
  ├── relationship to target
  └── known caveats
```

### Feature-catalog schema

```sql
CREATE TABLE analytics.feature_catalog (
    feature_name VARCHAR PRIMARY KEY,
    feature_version VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    feature_family VARCHAR NOT NULL,
    entity_grain VARCHAR NOT NULL,
    dtype VARCHAR NOT NULL,
    source_relation VARCHAR NOT NULL,
    source_expression VARCHAR,
    availability_rule VARCHAR NOT NULL,
    lookback_rule VARCHAR,
    postgame_derived BOOLEAN NOT NULL,
    leakage_status VARCHAR NOT NULL,
    fbs_fcs_policy VARCHAR,
    missingness_strategy VARCHAR,
    default_transform_json JSON,
    owner VARCHAR,
    created_at TIMESTAMP,
    deprecated_at TIMESTAMP
);
```

### Feature families

| Family | Examples | Primary role | Key risk |
|---|---|---|---|
| Prior-season performance | Prior adjusted offense/defense, prior pace, prior special teams | Early-season starting information | Treating final prior-year quality as fully persistent despite roster/staff changes |
| Roster continuity | Returning production, returning starts, QB continuity, transfer/portal changes | Adjust prior persistence at the team/unit level | Incomplete or late-captured roster information |
| Recruiting/talent | Multi-year recruiting strength, transfer talent proxies | Long-run talent prior | Confounding with coaching/resources; timing/version control |
| Coach/staff | Head coach continuity, coordinator continuity, historical pace/pass rate | Scheme and continuity prior | Misattributing staff effects or using future staff information |
| Current-season raw form | Rolling PPA/EPA-like efficiency, success rate, explosive rate, finishing drives | Current revealed form | Opponent quality, small samples, garbage-time effects |
| Opponent-adjusted performance | Adjusted offense/defense/pace ratings | Separates team quality from schedule difficulty | Leakage if final-season ratings are used retroactively |
| Pace and possessions | Neutral tempo, plays/drive, possessions/game, seconds/play | Total-volume projection | Raw plays are affected by game state and opponent |
| Efficiency components | Pass/rush efficiency, early-down PPA, third-down rate, red-zone/finishing drives | Scoring-rate projection | High variance and collinearity |
| Explosiveness | Explosive-play rate, yards/PPA on explosives, EPA tails | Ceiling/tail scoring behavior | Sparse event noise |
| Havoc/turnovers | Havoc rate, sacks, TFL, turnover rate, fumble recovery residuals | Possession-quality and variance signals | Turnovers and fumble recoveries regress strongly |
| Special teams | Field-goal quality, punting, return efficiency, kicker PAAR where valid | Field position and scoring adjustment | Small samples and changing personnel |
| Matchup interaction | Offense-vs-defense differences, pass-defense matchup, pace interaction | Game-specific projection | Double counting ratings and overfitted interactions |
| Environment | Weather, elevation, venue, travel, rest, kickoff time | Context adjustment | Forecast-versus-observed weather timing |
| Market | Opener, current line, line movement, quote dispersion | Strong benchmark and incremental signal | Timestamp/provider mismatch and closing-line leakage |

### Feature-selection modes

1. **Fixed manual set:** Default. The user selects approved features; all trials use the identical set.
2. **Feature-group comparison:** Optuna selects among a small number of documented, coherent groups.
3. **Controlled optional variables:** A small user-approved list can be toggled; use only for exploratory studies and require confirmation.
4. **Regularization selection:** Ridge/Elastic Net controls redundancy while the raw input set remains fixed.
5. **Advanced transform search:** Later phase only; lags, windows, or interactions must be represented as train-fold-safe pipeline operations.

Do not support free-form Optuna toggles across hundreds of raw columns.

---

## 8. Football feature definitions

### 8.1 Team-game outcome notation

For team $i$ against opponent $j$ in game $g$:

- $Y_{ig}$: team outcome. It may be points scored, points per possession, offensive PPA/play, success rate, or another declared target.
- $H_{ig}$: home/away/neutral-site indicator or a set of venue indicators.
- $S_g$: season or era fixed effect.
- $W_g$: weather/venue/context covariates valid at the decision time.
- $P_{ig}$: preseason prior for team $i$'s relevant unit.
- $A_{i,g-1}$: all valid current-season evidence for team $i$ available before game $g$.

### 8.2 Raw efficiency

A generic raw current-season efficiency feature is:

$$
\bar{e}_{i,g-1}
= \frac{1}{N_{i,g-1}} \sum_{h < g} e_{ih}
$$

Where:

- $e_{ih}$ is a game-level efficiency statistic for team $i$ in prior game $h$, such as offensive PPA/play.
- $N_{i,g-1}$ is the count of eligible prior games or eligible plays.
- The sum includes only games completed before the selected decision time.

Raw averages are descriptive but not enough for forecasting because schedules differ. A team with a high raw offensive PPA against weak defenses cannot be assumed equivalent to the same PPA against strong defenses.

### 8.3 Neutral-situation efficiency

Many per-play measures should be built using a declared neutral-game-state filter. The exact definition must be configurable and versioned, for example based on quarter, score differential, down, time remaining, and kneel-down exclusions.

The GUI should offer a named `neutral_situation_profile` rather than a hidden filter. The model card should state:

- Score-differential thresholds by quarter.
- Whether overtime is excluded.
- Whether kneels/spikes are excluded.
- Whether end-of-half hurry-up or garbage-time possessions are excluded.
- Whether the same definition is used for pace and efficiency.

Never label a statistic “neutral” without documenting its rule.

### 8.4 Success rate

$$
\text{SuccessRate}_{ig}
= \frac{\text{successful eligible plays}_{ig}}
       {\text{eligible offensive plays}_{ig}}
$$

A play-level success definition must be explicit. Common choices use the fraction of yards-to-go gained by down, but the exact thresholds and play exclusions belong in the feature version. Success rate captures consistent play-to-play efficiency, while PPA/EPA-like metrics incorporate field position and scoring-value change. They are related but not interchangeable.

### 8.5 Explosiveness

A generic explosiveness variable might be:

$$
\text{ExplosiveRate}_{ig}
= \frac{\#\{\text{eligible plays with gain above threshold}\}}
       {\text{eligible plays}}
$$

The threshold must be stored in metadata and may differ for rushes and passes. Alternatives include average PPA on successful plays, explosive PPA share, or 20+ yard play rate. Explosiveness is noisy, so favor partial pooling, longer windows, and separate treatment from baseline success rate.

### 8.6 Possessions and pace

For a game total, expected scoring volume depends on expected possessions as well as points per possession:

$$
E[\text{Game Total}_g]
= E[\text{Possessions}_g]
  \times \left(E[\text{PPP}_{home,g}] + E[\text{PPP}_{away,g}]\right)
$$

Where:

- $E[\text{Possessions}_g]$ is expected total possessions, not merely raw plays.
- $E[\text{PPP}_{home,g}]$ and $E[\text{PPP}_{away,g}]$ are expected points per possession for each side.

Model pace/possessions separately from scoring efficiency. Raw plays per game are influenced by opponent pace, game state, incomplete passes, turnovers, and unusual game scripts. Use neutral pace features and opponent-adjusted possession estimates where possible.

### 8.7 Turnover and havoc variables

Separate repeatable pressure/disruption from volatile recovery outcomes.

Useful decomposition:

$$
\text{TurnoverMargin}
= \text{Interception component}
+ \text{Fumble creation component}
+ \text{Fumble recovery residual}
$$

- Interception rate may contain some quarterback and coverage signal.
- Sack/TFL/havoc measures can reflect pressure/disruption.
- Fumble recovery is typically much less persistent and should be heavily shrunk toward expectation.

The GUI should mark high-variance variables and require a choice: raw, shrunk, residualized, or excluded.

### 8.8 Special teams

Model special teams as a distinct component where available and sufficiently stable:

- Kicking accuracy/expected-points residual.
- Field-goal attempt rate conditioned on field position.
- Punt and kickoff return value.
- Net field position.
- Kicker PAAR or a source-equivalent measure, with clear source/version licensing.

Do not infer that a single season’s field-goal percentage is a stable team trait without sample-size and personnel context.

---

## 9. Opponent adjustment module

Opponent adjustment is a required first-class modeling component, not just another optional raw feature. Its goal is to distinguish a team’s observed performance from the difficulty of the opponents it faced.

CFBD documents adjusted team/player metrics as being adjusted for opponent strength; treat external adjusted metrics as documented input features only when their timing and construction are compatible with the model decision time. [web:63]

### 9.1 Module choices

| Method | What it estimates | Strengths | Limitations | Best role |
|---|---|---|---|---|
| Raw rolling metrics | Past observed performance | Simple, transparent | No schedule correction | Naive baseline only |
| Ridge offense/defense adjustment | Team offensive and defensive effects under penalization | Fast, reproducible, scalable, transparent | Penalty depends on scaling; uncertainty less native | Default benchmark |
| Crossed random-effects model | Team offense and opponent defense random effects, with pooling | Natural early-sample shrinkage and uncertainty | More complex; requires careful estimation | Strong long-term architecture |
| Dynamic state-space/Kalman model | Time-varying latent team strength | Captures evolving teams | More modeling choices and diagnostics | Later advanced model |
| External adjusted metric | Provider’s adjusted rating | Convenient benchmark/input | Method/timing may be opaque or retrospective | Secondary benchmark only |

### 9.2 Ridge-adjusted team offense and defense

For team $i$'s offensive output against opponent $j$ in game $g$:

$$
y_{ig}
= \beta_0
+ \beta_H H_{ig}
+ o_i
+ d_j
+ \gamma^\top W_g
+ \epsilon_{ig}
$$

Where:

- $y_{ig}$: declared team-game outcome, such as neutral offensive PPA/play or points per possession.
- $\beta_0$: population baseline.
- $\beta_H$: home/away/neutral-site effect.
- $o_i$: offensive rating for focal team $i$.
- $d_j$: defensive effect of opponent $j$; sign conventions must be documented.
- $W_g$: game context controls such as season effects or valid environment controls.
- $\epsilon_{ig}$: residual.

Ridge estimation solves:

$$
\min_{\beta,o,d}
\sum_{ig}\left(y_{ig}-\hat{y}_{ig}\right)^2
+ \lambda_o\sum_i o_i^2
+ \lambda_d\sum_j d_j^2
$$

The penalties shrink poorly observed teams toward the population mean. The values of $\lambda_o$ and $\lambda_d$ are not portable across target scaling or design matrices; they must be tuned inside time-aware folds rather than copied from another implementation.

### 9.3 Two-way crossed random-effects model

For the same outcome:

$$
y_{ig}
= \beta_0
+ \beta_H H_{ig}
+ u_i^{off}
+ v_j^{def}
+ \gamma^\top W_g
+ \epsilon_{ig}
$$

With:

$$
\begin{bmatrix}
 u_i^{off} \\
 u_i^{def}
\end{bmatrix}
\sim
\mathcal{N}
\left(
\begin{bmatrix}
 \mu_{i}^{off,prior} \\
 \mu_{i}^{def,prior}
\end{bmatrix},
\Sigma_{team}
\right)
$$

Interpretation:

- $u_i^{off}$: latent offensive effect for team $i$.
- $v_j^{def}$: latent defensive effect for opponent $j$.
- $\mu_i^{off,prior}$, $\mu_i^{def,prior}$: team-specific preseason prior means.
- $\Sigma_{team}$: variance/covariance structure that controls how strongly ratings shrink and whether offense/defense strengths are correlated.

This formulation pools small-sample teams automatically toward priors and the overall population. It is often statistically attractive early in the season, but it needs a reliable implementation, convergence checks, posterior/interval diagnostics if Bayesian, and locked walk-forward comparisons against a simpler ridge benchmark.

### 9.4 Separate unit processes

Do not force one overall “team power” variable to do every job. Estimate separate latent processes where data supports it:

1. Offensive efficiency versus opponent defense.
2. Defensive efficiency allowed versus opponent offense.
3. Neutral pace/possession generation.
4. Explosiveness.
5. Special teams/field position.
6. Turnover/havoc components with strong shrinkage.

For totals, model expected possessions separately from points per possession. For spreads, opponent-adjusted offensive and defensive quality can feed expected scoring differential. For moneylines, their uncertainty can feed win-probability simulation.

### 9.5 Weekly as-of update logic

For a prediction in week $w$:

1. Retrieve only games completed before the selected snapshot cutoff.
2. Refit or update opponent-adjustment ratings using only those games.
3. Build the week-$w$ team and game feature table.
4. Store the rating output with `rating_as_of_week = w` and timestamp.
5. Use that frozen output for all week-$w$ experiments.

Never use a rating generated after Week 14 to describe what the model “knew” in Week 3.

### 9.6 Opponent-adjustment GUI controls

- Adjustment status: none, ridge, crossed mixed model, dynamic model, provider metric benchmark.
- Outcome to adjust: PPA/play, success rate, points per possession, pace, explosive rate, etc.
- Unit: offense/defense, offense-only, defense-only, pace.
- Game-state filter profile.
- Season reset policy.
- Prior linkage: none, generic population, team-specific preseason prior.
- Penalty/search range for ridge.
- Random-effect variance strategy for mixed models.
- Minimum games/plays threshold.
- FBS/FCS treatment.
- Home/neutral-site effect inclusion.
- Current-week update cadence.

The UI should show a rating audit: team, games used, opponent quality summary, prior weight, posterior/estimated rating, standard error/uncertainty where available, and last valid as-of timestamp.

---

## 10. Preseason priors and prior-season information

Early-season CFB has extremely limited current-year data. The system should use **team-specific priors**, not a uniform preseason constant and not a final prior-season rating treated as truth.

### 10.1 Prior components

Build separate preseason prior components for:

- Offensive efficiency.
- Defensive efficiency.
- Neutral pace/possession rate.
- Explosiveness.
- Turnover/havoc tendency, with strong shrinkage.
- Special teams.
- Optional quarterback/player unit effects where data quality supports them.

### 10.2 Generic prior equation

For team $i$, unit $k$, before season $s$:

$$
P_{i,s}^{(k)}
= \alpha_0^{(k)}
+ \alpha_1^{(k)} R_{i,s-1}^{(k)}
+ \alpha_2^{(k)} C_{i,s}
+ \alpha_3^{(k)} Q_{i,s}
+ \alpha_4^{(k)} T_{i,s}
+ \alpha_5^{(k)} S_{i,s}
+ \epsilon_{i,s}^{(k)}
$$

Where:

- $P_{i,s}^{(k)}$: preseason prior for team $i$, season $s$, component $k$.
- $R_{i,s-1}^{(k)}$: prior-season opponent-adjusted component rating, not a raw final box-score aggregate.
- $C_{i,s}$: continuity variables: returning production, returning starters, roster retention, and relevant staff continuity.
- $Q_{i,s}$: quarterback continuity/quality proxy, where available and appropriately timestamped.
- $T_{i,s}$: talent/recruiting/transfer variables.
- $S_{i,s}$: scheme/staff variables such as coordinator continuity and historical pace tendencies.
- $\epsilon_{i,s}^{(k)}$: unexplained team-specific deviation.

The coefficients are estimated from historical seasons with season-held-out validation; they are not fixed universal football constants.

### 10.3 Team-specific prior confidence

A returning veteran team should not receive the same prior uncertainty as a team with a new coach, new quarterback, transfer-heavy roster, and limited returning production.

Represent prior uncertainty as:

$$
P_{i,s}^{(k)} \sim \mathcal{N}\left(
\mu_{i,s}^{(k)},\; \sigma_{i,s}^{2(k)}
\right)
$$

Where $\sigma_{i,s}^{2(k)}$ increases with discontinuity and data uncertainty. In practice, the GUI can derive a `prior_confidence_band` from documented continuity inputs and test its value in walk-forward seasons.

### 10.4 In-season prior decay

A practical blended rating is:

$$
R_{i,w}^{(k)}
= \omega_{i,w}^{(k)} P_{i,s}^{(k)}
+ \left(1-\omega_{i,w}^{(k)}\right) A_{i,w}^{(k)}
$$

Where:

- $R_{i,w}^{(k)}$: blended rating entering week $w$.
- $P_{i,s}^{(k)}$: preseason prior.
- $A_{i,w}^{(k)}$: current-season opponent-adjusted evidence available before week $w$.
- $\omega_{i,w}^{(k)}$: prior weight, expected to decline as informative current-season evidence accumulates.

Do not hard-code that priors “stop mattering” in a particular week. The crossover depends on outcome, sample size, team continuity, schedule, and model specification. Evaluate candidate decay functions in historical rolling-origin backtests.

Possible UI-selectable decay structures:

- Fixed week schedule.
- Effective-play-count schedule.
- Effective-possession-count schedule.
- Data-driven hierarchical/mixed-model shrinkage.
- Tunable parametric decay with strict search limits.

A simple parametric option is:

$$
\omega_{i,w}^{(k)}
= \frac{1}{1 + \exp\left(a^{(k)} + b^{(k)} n_{i,w}\right)}
$$

Where $n_{i,w}$ is the amount of valid current-season evidence, such as opponent-adjusted offensive plays. Tune only if the model is validated with fully time-ordered folds and an untouched final season.

### 10.5 Prior-season GUI controls

- Prior type: simple prior-year adjusted rating, roster-aware prior, recruiting/talent prior, staff/scheme prior, blended.
- Component: offense, defense, pace, special teams, etc.
- Prior-year decay window: one year, multi-year exponentially weighted, or learned.
- Continuity inputs enabled.
- QB-continuity feature policy.
- Transfer/portal source and as-of date.
- Coaching change policy.
- Prior confidence class.
- Decay method and permitted parameters.
- Week 1–3 special handling policy.

The UI must show a preseason audit for each team: prior components, source seasons, continuity indicators, staff/QB status, uncertainty/confidence class, and exact as-of date.

---

## 11. Market module

Markets are powerful benchmarks, but line data is particularly prone to timing errors.

### Market feature policy

- Store each quote as an immutable snapshot: game ID, provider, market, side, price/line, captured timestamp, and source record ID.
- Distinguish opener, consensus-at-decision, current, and close explicitly.
- Require a declared decision timestamp for any target or feature involving market information.
- Preserve the selected provider/consensus construction in the experiment configuration.
- Never use closing line as an input to an earlier prediction model.
- When evaluating betting hypotheses, use an executable or realistically available timestamped price, not a retrospective ideal price.

### Market-residual model

For a total target, define:

$$
R_g = T_g^{actual} - T_g^{market}(t)
$$

Then model:

$$
R_g = f(X_g^{pregame}) + \epsilon_g
$$

Where:

- $T_g^{actual}$ is the final game total.
- $T_g^{market}(t)$ is the market total available at decision time $t$.
- $X_g^{pregame}$ includes only information available by $t$.

The final forecast is:

$$
\widehat{T}_g = T_g^{market}(t) + \widehat{R}_g
$$

This architecture asks a more realistic question: whether the feature set explains future total variation beyond the current market benchmark. It is not a guarantee of a tradable edge; evaluate calibration, CLV, pricing, availability, and post-vig returns separately.

### Required market baselines

- Predict market line unchanged.
- Predict historical mean / conference-season baseline.
- Predict a simple opponent-adjusted football-only model.
- Predict market plus a limited, preregistered residual model.

---

## 12. Page 3: Opponent adjustments and priors

This page controls the football-specific upstream rating process.

### UI sections

#### A. Adjustment target

- Offensive PPA/play.
- Defensive PPA/play allowed.
- Success rate.
- Explosive rate.
- Points per possession.
- Neutral pace/possessions.
- Special-team component.

#### B. Method

- None/raw baseline.
- Ridge-adjusted offense-defense.
- Crossed random effects.
- Dynamic/state-space model.
- Provider-adjusted benchmark feature.

#### C. Prior strategy

- Population mean only.
- Prior-year adjusted ratings.
- Team-specific roster-aware priors.
- Prior-year + continuity + talent + staff blend.
- Separate priors by offense/defense/pace.

#### D. Update and data eligibility

- Current-season data cutoff.
- Game-state filter.
- FBS/FCS policy.
- Minimum plays/games.
- Home/neutral effect.
- Season transition and historical window.

#### E. Diagnostics

- Team ratings table by week.
- Shrinkage/prior weight chart.
- Ratings volatility chart.
- Team-specific inputs audit.
- Rating correlation matrix.
- Historical out-of-sample improvement versus raw ratings.

No downstream Optuna model may launch until its upstream opponent-adjustment configuration is frozen and materialized as a versioned feature snapshot.

---

## 13. Page 4: Validation design

### Default: rolling-origin, game-group-aware validation

For forecast made before week $w$:

1. Train only on seasons/games ending before the fold cutoff.
2. Generate all upstream ratings, priors, transformations, and feature summaries using only training-eligible information.
3. Fit the downstream model using the fold’s training window.
4. Predict an entire future validation block without refitting on outcomes inside that block.
5. Advance the cutoff.
6. Aggregate performance across folds.

### Recommended fold profiles

| Profile | Training window | Validation unit | Appropriate use |
|---|---|---|---|
| Season holdout | All prior seasons | Entire next season | Strong high-level generalization check |
| Expanding weekly | All history through prior week | One future week / small week block | In-season forecast realism |
| Expanding event block | All history through cutoff | 2–4 game-week blocks | Faster development feedback |
| Rolling multiseason | Last N seasons only | Future block | Potential regime drift |
| Nested time-aware | Inner folds tune; outer folds evaluate | Future season/block | Final method comparison |

### Fold safeguards

- Keep all rows of a game together.
- For team-game targets, keep both team observations from the same game in the same fold.
- Recompute ratings and rolling features per fold, not from a final full-season table.
- Keep market features aligned to the same decision timestamp.
- Use a gap/embargo if feature availability or market timing suggests possible leakage.
- Preserve a final untouched confirmation season, date range, or rolling live shadow period.

### Metrics by task

| Task | Primary metrics | Secondary diagnostics |
|---|---|---|
| Total/margin | MAE, RMSE | Bias, calibration, residual distribution, error by total/margin band |
| Team-game scoring | MAE/RMSE for points or PPP | Recombined game-total/margin error, correlation of paired residuals |
| Win probability | Log loss, Brier score | Calibration curve, reliability by probability bucket |
| Market residual | MAE/RMSE of residual | Incremental error vs market, calibration, CLV where executable |
| Betting-system research | CLV and post-vig returns on held-out decisions | Sample size, max drawdown, temporal stability, line availability, sensitivity |

For betting-system research, ROI is never enough by itself. Show number of bets, average edge, line movement, season-by-season outcomes, sensitivity to thresholds, and performance excluding the discovery period.

---

## 14. Page 5: Model and search space

### Model families by implementation phase

| Phase | Models | Purpose |
|---|---|---|
| Baseline | Mean, market line, simple rating formulas | Establish minimum credible benchmark |
| V1 | OLS, Ridge, Elastic Net, Huber | Interpretable models; stable first tuning target |
| V2 | Quantile regression, Poisson/negative-binomial where target supports it | Distribution/tail/count modeling |
| V3 | Random Forest, HistGradientBoosting | Controlled nonlinearity and interaction learning |
| V4 | XGBoost/LightGBM/CatBoost; Bayesian hierarchical/state-space models | Advanced models only after robust baselines |

### First Optuna profile: Ridge vs Elastic Net

```yaml
profile_id: cfb_regularized_regression_v1
allowed_models: [ridge, elastic_net]

search_space:
  model_family:
    type: categorical
    choices: [ridge, elastic_net]

  ridge_alpha:
    condition: {model_family: ridge}
    type: float
    low: 0.001
    high: 1000.0
    log: true

  elasticnet_alpha:
    condition: {model_family: elastic_net}
    type: float
    low: 0.0001
    high: 20.0
    log: true

  elasticnet_l1_ratio:
    condition: {model_family: elastic_net}
    type: float
    low: 0.01
    high: 0.99

fixed_pipeline:
  numeric_imputer: median
  numeric_scaler: standard
  categorical_imputer: most_frequent
  handle_unknown_categories: ignore
```

### Football-specific tunable components

Treat these with caution and isolate them in named configurations:

- Ridge penalties for opponent-adjustment ratings.
- Prior-decay parameters.
- Rolling window length: only from a small predeclared set, e.g. 4, 6, 8 games.
- Recency half-life: only from a small predeclared range.
- Neutral-situation profile: typically fixed, not tuned by outcome.
- Feature-group inclusion: only curated bundles.
- Interaction family: only a small approved list such as offense-vs-defense, pace-vs-pace, or market-residual interactions.

Do not let one study simultaneously discover arbitrary variable subsets, target definitions, line timestamps, game-state filters, window lengths, and model hyperparameters. That is research overfitting even if Optuna’s objective improves.

### Search-space validation

Before launch, the UI must check:

- Parameter bounds are feasible.
- Conditional parameters match chosen model families.
- Search spaces do not include unsupported model/pipeline combinations.
- Trial budget is proportionate to search-space size and fold cost.
- Feature count is plausible for training rows.
- Final confirmation data is excluded from all tuning folds.

---

## 15. Optuna study design

Optuna studies support persistent storage, named studies, samplers, pruners, optimization direction, and loading compatible studies. [web:35] Its pruners decide whether to stop a trial based on intermediate objective values reported during the trial. [web:53]

### Study lifecycle

```text
Draft configuration
  → validate data + timing + features
  → freeze configuration hash
  → materialize upstream ratings/features by fold
  → create persistent study
  → run trials in separate worker
  → record each trial and fold result
  → review finalists
  → create final candidate
  → evaluate once on confirmation period
  → generate model card
  → promote / reject / archive
```

### Recommended initial Optuna configuration

```python
study = optuna.create_study(
    study_name=study_name,
    storage=storage_url,
    direction="minimize",
    sampler=TPESampler(
        seed=42,
        multivariate=True,
        group=True,
    ),
    pruner=MedianPruner(
        n_startup_trials=20,
        n_warmup_steps=2,
        interval_steps=1,
    ),
    load_if_exists=True,
)
```

### Objective function pattern

```python
def objective(trial):
    config = build_trial_config(trial, frozen_experiment)
    fold_metrics = []

    for fold_number, fold in enumerate(frozen_folds):
        fold_data = build_fold_safe_data(
            experiment=frozen_experiment,
            fold=fold,
            trial_config=config,
        )

        pipeline = build_pipeline(config)
        pipeline.fit(fold_data.X_train, fold_data.y_train)
        predictions = pipeline.predict(fold_data.X_valid)

        rmse = compute_rmse(fold_data.y_valid, predictions)
        mae = compute_mae(fold_data.y_valid, predictions)
        bias = compute_bias(fold_data.y_valid, predictions)

        fold_metrics.append({
            "fold_id": fold.id,
            "rmse": rmse,
            "mae": mae,
            "bias": bias,
        })

        running_rmse = mean(x["rmse"] for x in fold_metrics)
        trial.report(running_rmse, step=fold_number)

        if trial.should_prune():
            raise optuna.TrialPruned()

    summary = summarize_folds(fold_metrics)
    trial.set_user_attr("fold_metrics", fold_metrics)
    trial.set_user_attr("mean_mae", summary["mae"])
    trial.set_user_attr("mean_bias", summary["bias"])
    trial.set_user_attr("rmse_sd", summary["rmse_sd"])
    trial.set_user_attr("n_features", len(config.feature_columns))
    trial.set_user_attr("feature_set_id", config.feature_set_id)

    return summary["rmse"]
```

### Pruning requirements

- Do not prune before enough completed startup trials exist.
- Do not prune before at least two valid folds are available.
- Prune only on comparable fold-level intermediate metrics.
- Preserve pruned trial parameters and partial results for audit.
- Display that pruning is an efficiency decision, not evidence that a model is invalid.

### Trial failure policy

Record and classify failures:

- Data validation failure.
- Feature missingness/constant column failure.
- Estimator convergence failure.
- Numerical instability.
- Unsupported parameter combination.
- Resource/time limit.
- Unexpected worker/system error.

Do not silently convert failed trials into favorable scores or exclude them from the study audit.

---

## 16. Feature-group tuning for CFB

Feature selection should be structured around football hypotheses.

### Example groups for a total model

```yaml
feature_groups:
  base_rating:
    required: true
    features:
      - home_adj_offense_rating
      - home_adj_defense_rating
      - away_adj_offense_rating
      - away_adj_defense_rating
      - home_field_or_neutral_effect

  pace_possessions:
    features:
      - home_adj_neutral_pace
      - away_adj_neutral_pace
      - expected_total_possessions

  current_form:
    features:
      - home_recent_adj_offense
      - home_recent_adj_defense
      - away_recent_adj_offense
      - away_recent_adj_defense

  explosiveness:
    features:
      - home_adj_explosive_rate
      - away_adj_explosive_rate
      - home_def_explosive_rate_allowed
      - away_def_explosive_rate_allowed

  havoc_turnovers:
    features:
      - home_havoc_rate
      - away_havoc_rate
      - home_interception_rate_shrunk
      - away_interception_rate_shrunk

  continuity_priors:
    features:
      - home_offense_prior_confidence
      - away_offense_prior_confidence
      - home_qb_continuity
      - away_qb_continuity
      - home_staff_continuity
      - away_staff_continuity

  environment:
    features:
      - weather_temperature_forecast
      - weather_wind_forecast
      - precipitation_probability
      - altitude
      - rest_days_difference
      - travel_distance_difference

  market_residual:
    features:
      - market_total_at_decision
      - total_market_movement_to_decision
      - market_quote_dispersion
```

### Group-selection constraints

- `base_rating` is always required.
- `market_residual` is allowed only for market-residual tasks.
- `continuity_priors` are required for Weeks 1–3 in a dedicated early-season experiment or retained as continuous features throughout.
- `pace_possessions` should be required in total models unless explicitly testing an ablation.
- Limit optional groups to a small predeclared number.
- Require group-level rationale and versioned definitions.
- Study one family of feature hypotheses at a time; do not tune every group in every model family on every target.

---

## 17. Acceptance rules and anti-overfitting controls

### Primary optimization metric

Use mean fold-level RMSE or MAE for continuous forecast targets. For market-residual models, also show incremental improvement versus predicting zero residual / the market itself.

### Mandatory post-study gates

A candidate must pass all applicable gates before confirmation:

| Gate | Example requirement |
|---|---|
| Baseline improvement | Improvement exceeds a preregistered practical threshold versus a fixed baseline |
| Temporal stability | No persistent collapse in a meaningful share of folds/seasons |
| Bias | Mean residual is within a declared tolerance |
| Calibration | Prediction buckets have acceptable average error patterns |
| Complexity | Feature count/model complexity stays within declared limits |
| Convergence | No unresolved convergence or numerical warnings |
| Data availability | Every selected feature passes as-of validation |
| Segment stability | No unacceptable failure in key segments: early season, conference, home/away, favorite/underdog, high/low total |
| Market realism | Market features and benchmark use only valid timestamped quotes |
| Confirmation lock | No use of the final holdout in tuning or threshold selection |

### Betting-system-specific gates

If an experiment creates wagering decisions:

- Evaluate CLV alongside, not instead of, realized outcomes.
- Use timestamped available lines/prices.
- Include vig, limits/liquidity assumptions where relevant, and line availability.
- Show season-by-season and fold-by-fold results.
- Run threshold sensitivity analysis around any edge cutoff.
- Require a minimum sample size.
- Compare against a no-bet rule and simple fixed thresholds.
- Separate discovery, selection, and confirmation periods.
- Do not optimize dozens of market filters against the same results history.

---

## 18. Page 6–7: Launch, monitor, and inspect studies

### Launch screen

Before launch, show a frozen summary:

```text
Task: Game total forecast
Target: final_total_points
Decision time: Wednesday 12:00 ET snapshot
Data relation: analytics.mart_cfb_game_pregame_v3
Feature set: cfb_total_core_v4 (23 features)
Opponent adjustment: Ridge O/D/Pace v2; weekly as-of updates
Preseason priors: roster-aware component priors v2
Validation: expanding weekly, group=game_id, 18 folds
Confirmation period: 2025 season, excluded
Models: Ridge + Elastic Net
Objective: minimize fold-mean RMSE
Trials: 250; timeout: 180 minutes
Sampler/pruner: TPE / Median
```

Require a user confirmation action after configuration is frozen.

### Live monitor

Show:

- Status: queued/running/paused/completed/failed/cancelled.
- Trials requested, completed, pruned, failed.
- Current best objective and baseline delta.
- Current trial’s model, parameters, feature groups, current fold.
- Trial runtime distribution and ETA.
- Fold-level current score.
- Worker ID, resource limit, and artifact location reference.
- Failure log with exact error categories.

Long studies must run in a separate worker process or queue. The Streamlit process should submit work, poll status, and render results—not own a fragile multi-hour computation.

---

## 19. Page 8: Candidate review

### Required results views

- Optimization history.
- Objective distribution.
- Top trials table.
- Top trials within practical tolerance of best score.
- Hyperparameter importance and parameter-vs-score plots.
- Fold-level score table and distribution.
- Score by season/week segment.
- Actual-versus-predicted and residual diagnostics.
- Calibration by prediction bucket.
- Feature coefficient stability for linear models.
- Permutation importance on validation/confirmation data for nonlinear models.
- Rating/prior ablation comparisons.
- Market-baseline comparison.

### Candidate selection table

| Candidate | Trial | CV RMSE | CV MAE | RMSE SD | Bias | Features | Runtime | Market/baseline delta | Recommendation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | 154 | 14.82 | 11.63 | 1.94 | 0.08 | 31 | 7 sec | +1.7% | Review |
| B | 201 | 14.89 | 11.61 | 1.42 | 0.02 | 19 | 3 sec | +1.3% | Preferred if stable |
| C | 089 | 15.02 | 11.77 | 1.20 | -0.01 | 11 | 1 sec | +0.5% | Simpler fallback |

The table is illustrative only; all values must be generated from the actual study.

### Selection policy

Do not automatically select the single lowest score. Choose from candidates within a declared tolerance of the best objective, then prefer:

1. Better stability across folds/seasons.
2. Better calibration and lower bias.
3. Lower complexity.
4. Faster and more reliable execution.
5. Stable feature signs/importance where interpretation matters.
6. Clearer football logic and data availability.

---

## 20. Page 9: confirmation and model card

### Confirmation protocol

1. Freeze selected features, rating configuration, prior configuration, model family, hyperparameters, and decision timestamp.
2. Refit all required upstream components using the full development period only.
3. Fit the final model on the development period.
4. Predict the untouched confirmation period exactly once.
5. Generate diagnostics and compare with baselines.
6. Require a manual promotion/rejection decision and notes.

### Model-card sections

```markdown
# Model Card: CFB Total / Spread / Residual Model

## Purpose and intended decision time
## Task and target definition
## Population and inclusion rules
## Data sources and snapshot hashes
## Game-state and preprocessing rules
## Feature catalog and selected feature versions
## Opponent-adjustment method
## Preseason prior construction and decay policy
## Market data policy and timestamp alignment
## Validation design and fold boundaries
## Optuna study provenance
## Selected model and hyperparameters
## Baseline comparisons
## Cross-validation performance
## Untouched confirmation performance
## Calibration, bias, residual and segment analyses
## Betting/CLV analysis, if applicable
## Leakage audit
## Known limitations and failure modes
## Artifact checksums and reproduction command
## Promotion decision
```

### Required Optuna provenance

- Study name and ID.
- Persistent storage reference without secrets.
- Sampler and pruner configuration.
- Requested/completed/pruned/failed trials.
- Search-space version.
- Feature-set and upstream-rating versions.
- Frozen config hash.
- Best-trial and selected-trial distinction.
- Top competing candidates.
- Trial failure summary.

---

## 21. Experiment registry schema

```sql
CREATE TABLE analytics.ml_experiments (
    experiment_id VARCHAR PRIMARY KEY,
    project VARCHAR NOT NULL,
    experiment_name VARCHAR NOT NULL,
    task_template VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    source_relation VARCHAR NOT NULL,
    source_query VARCHAR,
    data_snapshot_hash VARCHAR NOT NULL,
    entity_grain VARCHAR NOT NULL,
    observation_id_column VARCHAR NOT NULL,
    target_name VARCHAR NOT NULL,
    decision_timestamp_column VARCHAR NOT NULL,
    feature_as_of_timestamp_column VARCHAR NOT NULL,
    market_policy_json JSON,
    inclusion_policy_json JSON,
    opponent_adjustment_config_json JSON,
    preseason_prior_config_json JSON,
    validation_config_json JSON NOT NULL,
    feature_set_id VARCHAR NOT NULL,
    primary_metric VARCHAR NOT NULL,
    optimization_direction VARCHAR NOT NULL,
    baseline_run_id VARCHAR,
    config_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    notes VARCHAR
);

CREATE TABLE analytics.ml_feature_sets (
    feature_set_id VARCHAR PRIMARY KEY,
    feature_set_name VARCHAR NOT NULL,
    feature_set_version VARCHAR NOT NULL,
    selection_mode VARCHAR NOT NULL,
    feature_spec_json JSON NOT NULL,
    is_frozen BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR
);

CREATE TABLE analytics.ml_optuna_studies (
    study_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    optuna_study_name VARCHAR NOT NULL,
    storage_reference VARCHAR,
    sampler_name VARCHAR,
    sampler_config_json JSON,
    pruner_name VARCHAR,
    pruner_config_json JSON,
    search_space_version VARCHAR,
    n_trials_requested INTEGER,
    timeout_seconds INTEGER,
    random_seed INTEGER,
    state VARCHAR NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE analytics.ml_optuna_trials (
    study_id VARCHAR NOT NULL,
    trial_number INTEGER NOT NULL,
    trial_state VARCHAR NOT NULL,
    objective_value DOUBLE,
    parameter_json JSON NOT NULL,
    user_attributes_json JSON,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds DOUBLE,
    error_type VARCHAR,
    error_message VARCHAR,
    PRIMARY KEY (study_id, trial_number)
);

CREATE TABLE analytics.ml_trial_fold_metrics (
    study_id VARCHAR NOT NULL,
    trial_number INTEGER NOT NULL,
    fold_id VARCHAR NOT NULL,
    train_start_date DATE,
    train_end_date DATE,
    validation_start_date DATE,
    validation_end_date DATE,
    metric_name VARCHAR NOT NULL,
    metric_value DOUBLE NOT NULL,
    train_rows INTEGER,
    validation_rows INTEGER,
    PRIMARY KEY (study_id, trial_number, fold_id, metric_name)
);

CREATE TABLE analytics.ml_model_runs (
    model_run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    study_id VARCHAR,
    selected_trial_number INTEGER,
    model_family VARCHAR NOT NULL,
    model_params_json JSON NOT NULL,
    artifact_uri VARCHAR,
    artifact_sha256 VARCHAR,
    model_card_uri VARCHAR,
    status VARCHAR NOT NULL,
    promotion_decision VARCHAR,
    promotion_notes VARCHAR,
    created_at TIMESTAMP NOT NULL,
    promoted_at TIMESTAMP
);
```

---

## 22. Artifact layout

```text
artifacts/
  experiments/{experiment_id}/
    frozen_config.json
    data_contract.json
    feature_set.json
    opponent_adjustment_config.json
    preseason_prior_config.json
    validation_folds.parquet
    source_query.sql
    source_snapshot_manifest.json

  studies/{study_id}/
    study_summary.json
    trial_export.parquet
    fold_metrics.parquet
    tuning_log.jsonl
    candidate_comparison.parquet

  runs/{model_run_id}/
    model.joblib
    preprocessing_schema.json
    selected_features.json
    training_manifest.json
    cv_predictions.parquet
    confirmation_predictions.parquet
    coefficients_or_importance.parquet
    diagnostics/
    model_card.md
    checksums.sha256
```

Store queryable metadata and aggregate metrics in DuckDB/MotherDuck; keep serialized models and large predictions as artifacts with checksums and registry references.

---

## 23. Build sequence

### Phase 0: CFB data and timing foundation

- Build immutable raw captures and source metadata.
- Materialize pregame-valid team-week and game-level marts.
- Build feature catalog with availability rules.
- Build weekly source snapshot and as-of audit.
- Establish fixed baseline models and versioned model cards.

**Exit criterion:** Reproduce a historical Week $w$ input table exactly from only data available before that week’s decision timestamp.

### Phase 1: Opponent-adjusted baseline ratings

- Implement raw rolling baselines.
- Implement ridge-adjusted offense, defense, and pace ratings.
- Materialize weekly rating snapshots.
- Compare raw vs adjusted ratings in rolling-origin evaluation.
- Add FBS/FCS and neutral/garbage-time policy controls.

**Exit criterion:** A rating record has explicit as-of metadata, inputs, tuning configuration, and tests proving no future-game leakage.

### Phase 2: Team-specific preseason priors

- Create prior-year adjusted-rating input tables.
- Add roster continuity, QB continuity, talent/recruiting, transfer, and staff variables with source timestamps.
- Construct separate offense, defense, pace, and special-team priors.
- Test decay schedules using season-held-out evaluation.

**Exit criterion:** Early-season forecasts outperform or match a simple prior-year baseline out of sample, with transparent uncertainty and no hand-waved crossover week.

### Phase 3: Feature Builder and manual model runs

- Deliver feature search/add/remove UI.
- Save/load versioned feature sets.
- Add data audit and correlation/redundancy views.
- Support Ridge and Elastic Net with fixed manual controls.
- Generate complete model cards and run registry records.

**Exit criterion:** A user can reproduce a manually configured model solely from its run ID.

### Phase 4: Persistent Optuna tuning

- Add versioned search profiles.
- Add persistent study storage.
- Execute studies using separate workers.
- Add live monitoring, pruning, resume/cancel/clone.
- Export trial/fold telemetry into the registry.

**Exit criterion:** A study can safely resume and every trial has a reproducible config, score, duration, state, and audit trail.

### Phase 5: Controlled feature-group tuning and confirmation

- Add curated feature-group search.
- Add automated ablation and stability reports.
- Add final untouched confirmation workflow.
- Add market-residual model template with timestamp validation.
- Add promotion/rejection status and champion/challenger comparison.

**Exit criterion:** No model can be marked promoted without passing the declared confirmation and leakage gates.

### Phase 6: Advanced models

- Add crossed random effects / hierarchical model implementation.
- Add dynamic ratings if simpler approaches justify it.
- Add boosted models against regularized baselines.
- Add probability/distribution modeling and simulation for totals/spreads if needed.
- Add live shadow monitoring and drift alerts.

**Exit criterion:** Every advanced method beats or meaningfully complements the regularized baseline in locked, time-aware evaluation.

---


## 24. Architecture hardening

### 24.1 Control plane and data plane

Separate the interactive control plane from expensive or stateful work.

```text
Streamlit control plane
  -> validates and freezes ExperimentSpec
  -> submits immutable RunSpec
  -> reads status, metrics, and artifacts

Worker data plane
  -> resolves snapshot and fold manifests
  -> builds fold-safe features
  -> trains/evaluates trials
  -> writes append-only telemetry
  -> atomically publishes completed artifacts
```

The Streamlit process must never be the sole owner of a long-running study. A page refresh, browser disconnect, or app restart must not kill a run. Use a durable queue or a deliberately simple job table with worker claims, leases, heartbeats, retries, and idempotency keys.

### 24.2 Typed configuration contracts

Define versioned Pydantic models or equivalent typed schemas for:

- `DatasetSpec`: relation, snapshot, keys, target, grain, filters, decision time.
- `FeatureSetSpec`: feature versions, transforms, groups, and inclusion rules.
- `RatingSpec`: adjusted outcome, prior, shrinkage, update cadence, and as-of policy.
- `FoldSpec`: chronological boundaries, gap/embargo, grouping, retraining cadence.
- `SearchSpec`: model families, conditional parameter space, sampler, pruner, budget.
- `MetricSpec`: point, probabilistic, calibration, utility, and segment metrics.
- `DecisionPolicySpec`: offered market, edge threshold, uncertainty rule, and abstention.
- `ExecutionSpec`: provider, quote age, price, push rule, line shopping, and stake policy.
- `AcceptanceSpec`: preregistered gates and failure conditions.
- `RunSpec`: immutable references to all specifications plus code/environment identity.

A specification has `schema_version`, `spec_id`, `created_at`, `created_by`, and canonical JSON. Compute `config_hash` from normalized JSON, not from UI widget order. Reject unknown fields by default so old workers cannot silently ignore a new option.

### 24.3 Reproducibility envelope

Every run must capture:

- Git commit SHA and dirty-worktree status.
- Python version, OS, CPU/GPU identity, and package lock hash.
- DuckDB version and relevant extension versions.
- Random seeds for split generation, model fitting, samplers, bootstrap, and simulation.
- SQL text/hash and source-table snapshot manifest.
- Row-level inclusion/exclusion manifest or deterministic query sufficient to recreate it.
- Model serialization format and library version.
- Time zone database version when local kickoff conversion is material.

Where algorithms remain nondeterministic, record that fact and run repeated-seed stability checks rather than claiming bit-for-bit reproducibility.

### 24.4 Storage policy

Use local DuckDB as the canonical analytical source unless an explicit migration decision changes that policy. Treat MotherDuck as a shareable mirror/publishing target, not an assumed source of truth. Keep large immutable matrices, out-of-fold predictions, and simulation draws in partitioned Parquet; keep compact metadata and aggregate metrics in registry tables.

SQLite is acceptable for a single-host Optuna prototype. For concurrent multi-process or multi-host workers, use a supported shared RDB backend and configure worker heartbeats, stale-trial handling, and bounded retries. Never share Optuna `InMemoryStorage` across worker processes.

---

## 25. Warehouse integration

The current warehouse already contains useful raw, staging, core, and metadata assets. The Lab should adapt to that physical model rather than invent parallel copies prematurely.

### 25.1 Existing-source mapping

| Modeling need | Preferred existing inputs | Required transformation or audit |
|---|---|---|
| Game identity and schedule | `core.fact_game`, `core.fact_game_historical`, `core.dim_week`, `core.dim_team`, `core.dim_venue` | Confirm stable game IDs, kickoff revisions, season type, neutral site, and historical team/conference identity |
| Team-game outcomes | `core.fact_game_team`, staged game/team stats | Produce exactly two records per eligible game and reconcile scores to game fact |
| Market lines and odds | `core.fact_game_line`, `core.fact_game_odds`, `core.dim_lines_provider`, raw/staged line feeds | Audit provider, quote timestamp, opener/close semantics, price, duplicate/conflicting records, and stale quotes |
| Play and drive features | staged plays, `core.fact_drive_postgame`, play-type dimensions | Build strictly trailing weekly aggregates; retain play-filter version and parsing-quality flags |
| Weather | `core.fact_game_weather`, venue/weather dimensions | Mark observed versus forecast; do not use postgame observed weather in historical pregame backtests |
| Recruiting and talent | `core.fact_team_recruiting`, `core.fact_team_talent`, recruit dimensions | Snapshot before decision date; account for source/method revisions |
| Returning production | `core.fact_team_returning_production` | Archive publication/as-of date and distinguish unavailable from true zero |
| Coaches | `core.fact_coach_season`, `core.dim_coach` | Convert stints into decision-time-valid staff continuity and change features |
| Provider ratings/projections | `core.fact_team_season_rating_postgame`, `core.game_projections`, staged adjusted metrics | Default-block postgame or retrospective fields; admit only after timing audit |
| Load and lineage metadata | `meta.load_report`, `meta.relationship`, `meta.table_dictionary` | Link source batches to model snapshots and surface freshness/completeness in the UI |

The catalog indicates that local DuckDB is the source of truth, while the MotherDuck copy may lag and omit the complete core layer. The Lab therefore needs an environment banner showing database URI, catalog timestamp, source freshness, and whether the selected relation is canonical or mirrored.

### 25.2 Semantic modeling layer

Add a thin, explicit modeling semantic layer rather than letting notebooks query arbitrary tables:

```text
analytics.mart_cfb_game_universe
analytics.mart_cfb_market_quotes
analytics.mart_cfb_team_week_features
analytics.mart_cfb_team_game_pregame
analytics.mart_cfb_game_pregame
analytics.mart_cfb_targets_postgame
analytics.mart_cfb_prediction_context
```

`mart_cfb_prediction_context` should join only immutable identifiers and references. Target columns should live in a logically separate postgame relation and be joined by the training builder only after it has frozen the eligible pregame rows. This separation makes accidental target leakage harder.

### 25.3 Snapshot manifest

For every dataset snapshot, persist:

```yaml
snapshot_id: snap_...
created_at_utc: ...
source_database_fingerprint: ...
relations:
  - relation: analytics.mart_cfb_game_pregame
    row_count: ...
    min_kickoff: ...
    max_kickoff: ...
    schema_hash: ...
    content_hash_strategy: partitioned
source_batches: [...]
watermarks:
  games_through: ...
  lines_through: ...
  plays_through: ...
quality_suite_id: ...
quality_result_id: ...
```

A hash of SQL alone is insufficient: identical SQL against revised source data can produce a different training set. Record source batch IDs and partition-level content hashes or stable row checksums.

### 25.4 Data contracts and quarantine

Create executable contracts for required columns, uniqueness, referential integrity, legal ranges, two-team game structure, kickoff ordering, quote ordering, and outcome reconciliation. Failed rows go to a quarantine relation with reason codes; they must never disappear through an unlogged `WHERE` clause.

Minimum blocking tests include:

- Unique canonical game ID at game grain.
- Exactly one home and one away team unless a documented exception exists.
- Both team-game records stay paired.
- Final total equals reconciled home plus away scores under the selected overtime policy.
- Market quote time precedes decision time.
- Feature as-of time does not exceed decision time.
- No target/postgame columns appear in the predictor allowlist.
- Week/season sequence is plausible and kickoff time is timezone-normalized.
- Team and conference identifiers resolve historically, not merely to current affiliations.

---

## 26. CFB regime framework

College football is nonstationary. Add named regime features and evaluation slices, but do not automatically let Optuna discover arbitrary era cutoffs.

### 26.1 Required regimes

- NCAA timing and clock-rule eras, including an explicit post-2023 indicator and interaction tests for pace features.
- Overtime-rule eras and an option to evaluate regulation-only targets separately when reliable regulation scores exist.
- COVID-disrupted 2020 season as exclude, include-with-indicator, or dedicated sensitivity analysis.
- Transfer-portal/NIL roster-churn era as a broad regime, with any exact cutoff preregistered.
- Conference realignment and team transition periods, including FBS/FCS reclassification.
- Playoff/bowl structure eras and opt-out-heavy postseason games.
- Major source/schema methodology revisions.

### 26.2 Regime policy

For each regime, choose one of: pool, add indicator, allow limited interactions, reweight, train rolling-window only, or exclude. Compare choices in outer chronological folds. A regime flag is not proof of a stable causal effect; it is a guardrail against forcing one historical relationship across structurally different eras.

### 26.3 Historical identity

Team, conference, coach, venue, and division membership require effective-dated dimensions. Features for a 2014 game must not use the team's 2026 conference, current venue attributes if materially changed, or a later canonical naming resolution that merges distinct entities incorrectly.

---

## 27. Feature engineering expansion

### 27.1 Possession decomposition

For totals, prefer a compositional architecture:

```text
expected possessions
x expected home points per possession
+ expected away points per possession
+ special-teams / defensive-score adjustments
= expected game total
```

Add drive-start field position, drives per game, plays per drive, three-and-out rate, explosive-drive rate, scoring-opportunity rate, finishing-points-per-opportunity, and expected possession loss from turnovers. Keep pace and scoring efficiency separate so the model can explain *why* a total is high.

### 27.2 Situation splits

Candidate splits must be football-grounded and sample-aware:

- Early downs versus late downs.
- Standard downs versus passing downs.
- Run versus pass efficiency.
- Neutral situation versus trailing/leading game states.
- First half versus second half only when the intended mechanism justifies it.
- Red zone and scoring opportunities.
- Field-position bands.
- Explosive-play creation and prevention.
- Sack/havoc generation and allowed.

Each split needs eligible-play counts, empirical-Bayes or ridge shrinkage, and a minimum effective sample. The feature inspector should show numerator, denominator, prior mean, posterior/shrunk value, and uncertainty—not only the final rate.

### 27.3 Matchup transforms

Provide deterministic, versioned transforms:

- Offense minus opponent defense rating.
- Offense and defense weighted mean.
- Harmonic or geometric combination for rates only when mathematically valid.
- Pace interaction and expected-possession formula.
- Pass-rate-over-expected versus defensive pass tendency.
- Explosive offense versus explosive prevention.
- Havoc creation versus protection.
- Finishing-drives offense versus scoring-opportunity defense.
- Style-clash distance between team tendency vectors.

Never add both every home/away raw value and every sum/difference/product automatically. Use a collinearity budget and named transform families.

### 27.4 Recency and sample size

Every rolling statistic should expose:

- Window type: season-to-date, trailing games, trailing plays/possessions, exponential decay.
- Exclusions: current game, overtime, garbage time, FCS, kneels, spikes, penalties/no-plays.
- Effective sample size.
- Prior/shrinkage target.
- Minimum-history fallback.
- Cross-season carryover policy.

Tune only a small preregistered set of windows. Better yet, compare a simple exponential state update or dynamic rating against proliferating 4/6/8-game versions of the same feature.

### 27.5 Availability classes

Add `availability_class` to the feature catalog:

| Class | Meaning | Default policy |
|---|---|---|
| Historical replayable | Exact value reconstructible at the decision time | Eligible for retrospective tuning |
| Snapshot-dependent | Valid only if exact archived publication/quote exists | Eligible only where snapshot coverage passes |
| Prospective-only | Can be collected correctly now but not reconstructed historically | Shadow/live studies only |
| Retrospective descriptive | Known only after kickoff/game/season | Blocked from prediction |
| Provider-opaque | Construction or timing is not fully known | Benchmark-only until audited |

Injuries, depth charts, and many late-breaking roster changes should default to prospective-only. Historical observed weather must not masquerade as a timestamped forecast.

### 27.6 Missingness semantics

Distinguish at least:

- Source not collected.
- Feature structurally not applicable.
- Team had zero eligible events.
- Source record delayed.
- Parsing/quality failure.
- True unknown at decision time.

Create missingness indicators only where their availability itself is legitimate. Never let missingness encode future knowledge such as whether a game was eventually cancelled.

---

## 28. Target and distribution layer

### 28.1 Target registry

Create a versioned target catalog with formula, grain, overtime policy, settlement rules, and availability time. Required targets include final points, regulation points where available, margin, team points, points per possession, market residual, cover/over result including pushes, line movement, and CLV.

A target change creates a new experiment family. Do not compare scores across target versions as if they were the same task.

### 28.2 Joint score coherence

When modeling home points and away points separately, preserve their residual dependence. At minimum:

1. Fit separate conditional means.
2. Estimate out-of-fold residual covariance by relevant regime/segment.
3. Simulate joint scores with a documented dependence structure.
4. Derive total, margin, win, and team-total distributions from the same draw set.

This prevents internally inconsistent outputs such as a total distribution, spread distribution, and win probability that could not arise from one joint score model.

### 28.3 Distributional candidates

After point baselines are stable, add:

- Quantile regression and quantile boosting.
- NGBoost or GAMLSS-style conditional mean/scale models.
- Conformalized quantile regression.
- Bayesian posterior predictive draws from hierarchical models.
- Possession/drive Monte Carlo with empirically estimated dependence.
- Bivariate or copula score models only after an independent-score baseline.

Score probabilistic forecasts with CRPS, log score/NLL where valid, interval score, PIT/rank diagnostics, calibration, sharpness, and empirical coverage. Point RMSE alone cannot tell whether two equal-edge games have materially different uncertainty.

### 28.4 Conformal policy

Conformal intervals are a calibration layer, not a license to assume exchangeability in a drifting sport. Use time-aware calibration windows or methods designed for sequential data, report coverage by season and segment, and monitor interval width. Treat formal coverage guarantees as conditional on method assumptions; the 2023 rule era, roster churn, and source changes can break them.

---

## 29. Validation upgrades

### 29.1 Three-level protocol

Use three separate levels:

1. **Inner tuning:** chronological folds used by Optuna.
2. **Outer selection:** untouched seasons/blocks used to compare methods and feature hypotheses.
3. **Final confirmation:** one locked period or prospective shadow window opened once for a promotion decision.

A final holdout is consumed after inspection. Record `holdout_opened_at`, who opened it, candidate hash, and decision. Subsequent changes require a new confirmation period.

### 29.2 Replay engine

Build a historical replay engine that loops through decision timestamps exactly as production would:

```text
for decision_event in chronological_schedule:
    resolve only data available at event timestamp
    update ratings from completed eligible games
    select market quote under execution rule
    produce and persist prediction
    wait logically until outcome availability
    score prediction and decision
```

The replay engine and live prediction service should call the same feature and model code paths. A backtest-only SQL pipeline and separate live pipeline will drift.

### 29.3 Purging and embargo

Use a calendar/time-based gap when labels, feature revisions, or quote feeds arrive with delay. Do not confuse scikit-learn's sample-count `gap` with a calendar embargo. Define the exclusion by actual timestamp and keep all rows from one game together.

### 29.4 Uncertainty in comparisons

For every baseline delta, report:

- Paired game-level loss difference.
- Season/block-level distribution.
- Block-bootstrap confidence interval using week or game-day blocks.
- Practical effect size, not just a p-value.
- Win/loss/tie count versus baseline across folds.
- Sensitivity to one-season removal.

For many feature groups, models, or betting thresholds, track the entire research family and control selection bias. Use nested evaluation, a limited preregistered hypothesis set, and methods such as false-discovery control or a reality-check/bootstrap where appropriate. Do not present the winning trial's raw CV score as an unbiased estimate.

### 29.5 Required negative controls

Add tests that should fail or show no gain:

- Random-noise feature.
- Permuted target within a safe historical block.
- Deliberately shifted future-only feature in a leakage-test fixture; launch must block it.
- Team-name or row-order identifiers with no legitimate predictive role.
- Market residual model with only an intercept, equivalent to zero-residual baseline.

Negative controls verify that the pipeline is not manufacturing apparent skill.

### 29.6 Stress tests

Every finalist should be re-evaluated under:

- Excluding 2020.
- Pre-2023 versus post-2023 clock eras.
- FBS-only versus declared FCS treatment.
- Regular season only versus postseason.
- Early season versus mature season.
- One sportsbook/provider at a time.
- Quote staleness limits.
- Missing-feature fallback paths.
- Leave-one-season-out and leave-one-conference-out diagnostics.
- Plausible transaction-cost and line-degradation assumptions.

---

## 30. Metric framework

### 30.1 Forecast metrics

Report against each fixed baseline:

- MAE and RMSE.
- Median absolute error and trimmed RMSE as robustness diagnostics.
- Mean error/bias and slope/intercept calibration.
- Error by predicted-total, spread, week, conference, neutral site, and regime.
- Correlation is descriptive only and never a primary success metric.

### 30.2 Probabilistic metrics

- CRPS for continuous predictive distributions.
- NLL/log score only when the density is valid and numerically protected.
- Pinball loss by quantile.
- Interval coverage, average width, and interval score.
- PIT/rank histogram by season and decision-time segment.
- Brier score, log loss, reliability, and resolution for binary market outcomes.

### 30.3 Market metrics

Keep separate ledgers for:

- Forecast accuracy versus realized outcome.
- Edge versus offered line.
- CLV versus a defined later reference quote.
- Realized result and net units after actual price/push rules.
- Availability/fill rate and quote age.

A model can improve RMSE without producing bets, earn CLV without short-run profit, or show realized profit without stable predictive skill. The UI should never collapse these into one score.

### 30.4 Composite objectives

Avoid opaque weighted sums initially. Prefer constrained optimization: minimize RMSE subject to bias, calibration, complexity, runtime, and coverage gates. If multi-objective Optuna is later enabled, show the Pareto front and require a documented rule for selecting one candidate after the search.

---

## 31. Betting execution engine

### 31.1 Quote model

A bet decision must reference a specific immutable quote:

```text
quote_id
game_id
provider_id
market_type
period
side_or_outcome
line_value
american_price
decimal_price
captured_at_utc
source_received_at_utc
is_live
availability_status
```

Do not backtest against a consensus number that was not executable. If a consensus is used as a feature, separately select an executable provider quote for settlement and P&L.

### 31.2 Settlement

Implement tested settlement functions for:

- Over/under wins, losses, and pushes.
- Half points and integer totals.
- American/decimal price conversion.
- Regulation-only versus overtime-included markets.
- Cancelled, postponed, suspended, and no-action games.
- Team totals, first-half markets, and alternate lines if later supported.

Store result logic version on every decision.

### 31.3 Price-aware probabilities

Convert each predictive distribution into win, loss, and push probabilities at the exact offered number. Expected value must use price and push probability:

$$
EV = p_{win} \times b - p_{loss}
$$

where $b$ is net profit per unit stake at the offered odds; a push contributes zero. Preserve the full distribution used for this calculation.

### 31.4 Decision policies

Support explicit policies:

- No-bet baseline.
- Fixed point-edge threshold.
- Minimum expected-value threshold.
- Probability-edge threshold after removing vig under a declared method.
- Uncertainty-aware abstention.
- Selective/meta-label policy trained only on prior out-of-fold primary predictions.

Version thresholds separately from the forecast model. Never retune a betting threshold on the model's confirmation period.

### 31.5 Staking and risk

Default research reports to flat one-unit stakes. Add fractional Kelly only as a scenario analysis with a hard cap, minimum edge, bankroll path, and explicit warning that probability error makes Kelly fragile. Report turnover, maximum drawdown, longest losing streak, risk of ruin proxy, exposure by game/time/conference, and correlation among simultaneous bets.

### 31.6 Execution sensitivity

Recalculate outcomes under:

- Best available, median available, and named-book quotes.
- One-tick or half-point line degradation.
- Price degradation.
- Maximum quote age.
- Missed-fill rate.
- Delayed decision timestamp.
- One bet per game versus multiple related markets.

If profitability vanishes under modest degradation, mark the strategy non-actionable even if the idealized backtest is positive.

---

## 32. Search governance

### 32.1 Research hypothesis card

Before launching a study, require:

```yaml
hypothesis_id: HYP-...
claim: pace-adjusted possession features add information beyond market total
mechanism: ...
feature_groups: [...]
primary_target: ...
primary_metric: ...
baseline: ...
outer_test_periods: [...]
practical_improvement: ...
failure_condition: ...
follow_up_if_null: ...
```

The registry must retain negative and null studies. Deleting failed ideas creates survivorship bias in the research process.

### 32.2 Search budgets

Define budgets at the research-family level, not only per Optuna study:

- Maximum trials per search-space version.
- Maximum model families compared on one outer holdout.
- Maximum threshold variants.
- Maximum times a confirmation set may be inspected.
- Compute and wall-clock ceilings.

Clone/resume must preserve accumulated budget. A user cannot evade governance by renaming an equivalent study.

### 32.3 Candidate selection

Use a one-standard-error or practical-equivalence rule where appropriate: among candidates statistically/practically indistinguishable from the best, prefer the smallest stable model. Record why `selected_trial_number` differs from `best_trial_number`.

### 32.4 Feature evidence ledger

For each feature or group, track:

- Football mechanism.
- Data source and historical availability.
- Direct FBS forecasting evidence.
- Incremental-to-market evidence.
- Leakage risk.
- Cost/maintenance burden.
- Experiments attempted and their results.
- Current status: proposed, approved, rejected, deprecated, prospective-only.

This prevents rediscovering the same failed feature every few weeks.

---

## 33. Explainability and diagnostics

### 33.1 Linear models

Show standardized and native-unit coefficients, fold-by-fold sign stability, coefficient intervals/bootstrap distributions, variance inflation/redundancy diagnostics, and predicted impact over realistic feature ranges. Coefficient magnitude is not standalone feature importance when features are correlated.

### 33.2 Nonlinear models

Use out-of-fold permutation importance, grouped permutation for correlated football families, partial dependence or accumulated local effects, and SHAP only as a descriptive diagnostic. Never compute importance on the training set and call it predictive evidence.

### 33.3 Ablations

Automate these comparisons:

- Raw versus opponent-adjusted.
- Population versus team-specific priors.
- No-prior versus prior with decay.
- Aggregate scoring versus possession decomposition.
- Football-only versus market-only versus market-plus-football residual.
- Mean-only versus distributional uncertainty.
- Full feature set versus each coherent group removed.

Ablations use the same folds and game universe, then report paired loss differences.

### 33.4 Error review

Add a game-level error explorer with the full as-of feature snapshot, market path, model components, uncertainty interval, exclusion warnings, and comparable historical games. Allow analyst notes, but keep notes out of training unless converted into a governed feature later.

---

## 34. Operations and monitoring

### 34.1 Champion/challenger lifecycle

Use immutable model versions plus mutable aliases such as `champion`, `challenger`, `shadow`, and `rollback`. Promotion changes an alias only after automated gates and manual approval; it never overwrites an artifact.

Allowed states:

```text
draft -> validated -> tuning -> candidate -> confirmation
      -> rejected/archive
confirmation -> shadow -> promoted -> retired
```

### 34.2 Prediction ledger

Persist every live or replayed prediction before kickoff:

```sql
CREATE TABLE analytics.ml_predictions (
    prediction_id VARCHAR PRIMARY KEY,
    model_run_id VARCHAR NOT NULL,
    game_id BIGINT NOT NULL,
    decision_ts_utc TIMESTAMP NOT NULL,
    generated_at_utc TIMESTAMP NOT NULL,
    feature_snapshot_id VARCHAR NOT NULL,
    market_quote_id VARCHAR,
    point_prediction DOUBLE,
    distribution_uri VARCHAR,
    lower_interval DOUBLE,
    upper_interval DOUBLE,
    model_status VARCHAR NOT NULL,
    warnings_json JSON,
    UNIQUE(model_run_id, game_id, decision_ts_utc)
);
```

Predictions are append-only. Corrections create a new record linked by `supersedes_prediction_id`.

### 34.3 Drift monitoring

Monitor separately:

- Data freshness and missingness.
- Schema and category drift.
- Feature distribution drift.
- Prediction distribution drift.
- Residual/performance drift after outcomes arrive.
- Calibration and interval-coverage drift.
- Market edge and CLV drift.
- Rating/prior weight drift.

Drift is an investigation trigger, not an automatic retraining command. Small weekly CFB samples make uncontextualized statistical alarms noisy; aggregate by sensible blocks and compare against historical seasonality.

### 34.4 Retraining policy

Choose and version one policy: scheduled weekly, event-triggered, or hybrid. Retraining must rerun quality checks, reconstruct as-of features, evaluate smoke tests, and preserve the prior champion for rollback. Do not silently refit a promoted model after every corrected source row.

### 34.5 Failure modes and fallbacks

Define operational behavior for stale market feeds, missing weather, incomplete games, postponed kickoff, partial play ingestion, unavailable model artifact, and worker failure. A safe fallback is usually market-only/no-bet, not an imputed high-confidence wager.

---

## 35. Worker reliability

### 35.1 Job state machine

```text
queued -> claimed -> running -> completed
                 -> retry_wait -> queued
                 -> failed
queued/running -> cancellation_requested -> cancelled
```

Workers claim jobs with a lease. Heartbeats extend the lease; an expired lease can be retried up to a configured limit. Artifact publication should be atomic: write to a temporary location, verify checksums, then rename/commit and update registry status.

### 35.2 Idempotency

Use `(run_spec_hash, attempt_scope)` as an idempotency key. Re-submitting an identical completed run should return the existing run unless the user explicitly requests a repeated-seed replication. Trial numbers must not be reused after a crash.

### 35.3 Resource controls

- CPU, memory, GPU, timeout, and disk quotas per job.
- Maximum parallel folds/trials to prevent oversubscription.
- Deterministic thread limits for BLAS/OpenMP libraries.
- Cancellation checks between folds and expensive stages.
- Cache quota and eviction policy.
- Separate development and production credentials.

### 35.4 Cache design

Cache only objects keyed by complete immutable dependencies. Good candidates are fold manifests, weekly ratings, encoded fold matrices, and baseline predictions. A cache key must include data snapshot, feature/rating spec, fold ID, code version, and relevant library version. Never key only by feature-set name.

---

## 36. Test strategy

### 36.1 Unit tests

- Target formulas and sportsbook settlement, including pushes.
- Odds conversion and expected-value math.
- Rolling windows exclude the current game.
- Preseason prior decay is monotone under declared settings.
- Opponent rating sign conventions.
- Neutral-site encoding.
- Overtime and cancelled-game rules.
- Config canonicalization and hash stability.

### 36.2 Property tests

- Permuting input row order does not change predictions after deterministic sorting.
- Both team rows from a game always share a fold.
- Adding future rows cannot alter an earlier snapshot.
- All generated decision features satisfy `as_of <= decision_ts`.
- Probabilities are bounded and sum correctly; predictive quantiles are monotone.
- Re-running the same deterministic spec yields identical IDs and metrics within tolerance.

### 36.3 Integration tests

- Build one historical week from raw/staging through final prediction.
- Kill and restart an Optuna worker; verify stale trial recovery and no duplicate completed trial.
- Refresh Streamlit during a study; verify the job continues.
- Promote and roll back aliases without changing model artifacts.
- Recreate a run from its manifest in a clean environment.

### 36.4 Golden fixtures

Maintain a tiny hand-verified set of games, plays, market quotes, and expected features. Include deliberately malformed and leaking rows. Golden tests should detect source-parser changes, game-ID mismatches, and line-provider conflicts before a full backtest runs.

### 36.5 Statistical tests

- Simulation-based recovery tests for rating and prior models.
- Calibration tests on generated data only as software tests, never as evidence of real model skill.
- Repeated-seed sensitivity for stochastic learners.
- Coverage and residual diagnostics on real out-of-fold predictions.

---

## 37. GUI improvements

### 37.1 Global navigation

Add persistent top-level context: environment, database snapshot, experiment draft status, active job count, current champion, latest data watermark, and blocking warnings. Users should always know whether they are in development, replay, shadow, or live mode.

### 37.2 New pages

```text
11 Data Quality & Lineage
12 Historical Replay
13 Forecast Distribution & Scenario Explorer
14 Betting Decision Lab
15 Live/Shadow Monitor
16 Model Registry & Champion/Challenger
17 Research Hypothesis Ledger
18 System Health & Drift
```

**Status (2026-09-23): pages 15, 17 and 18 are built, read-only**, in the lab GUI (§5 status).

- **Shadow** covers pages 15 and 18. It shows alerts for a stale tick, a snapshot deadline, a missed week, or the verdict; then the weeks and the replay.
- **Hypotheses** is page 17, read from `models/tuning/hypotheses.json`.
- Pages 11–14 and 16 are not built.

### 37.3 Comparison workspace

Allow pinning runs and comparing only compatible experiments. Block or clearly warn when target, game universe, folds, line timestamp, provider, or target policy differs. Show paired game-level deltas rather than side-by-side aggregate metrics alone.

### 37.4 Scenario explorer

Permit controlled what-if changes to legitimate pregame inputs such as total line, spread, wind forecast, QB status, or expected possessions. Clearly label scenario outputs as sensitivity analysis, never stored historical predictions. Show prediction change, uncertainty change, and whether the scenario falls outside training support.

### 37.5 Guardrail UX

- Red blocking errors for leakage/timing violations.
- Amber warnings for thin samples, provider opacity, drift, and extrapolation.
- Explicit reason codes for excluded games/features.
- A diff view before freezing a revised spec.
- Confirmation text showing which holdout will be consumed.
- No destructive delete in the UI; archive instead.

---

## 38. Registry additions

Extend the schema with these entities:

```text
ml_dataset_snapshots
ml_snapshot_relations
ml_data_quality_runs
ml_target_definitions
ml_feature_definitions
ml_feature_sets
ml_rating_snapshots
ml_validation_schemes
ml_fold_manifests
ml_hypotheses
ml_experiment_families
ml_experiments
ml_jobs
ml_job_attempts
ml_optuna_studies
ml_optuna_trials
ml_trial_fold_metrics
ml_model_runs
ml_model_aliases
ml_predictions
ml_prediction_outcomes
ml_market_quotes_used
ml_bet_decisions
ml_bet_settlements
ml_calibration_metrics
ml_drift_metrics
ml_audit_events
```

### 38.1 Important constraints

- Immutable IDs for snapshots, specs, runs, predictions, and quotes.
- Unique constraints at declared grains.
- Foreign keys or explicit application-level integrity checks where DuckDB limitations apply.
- `created_at`, `created_by`, `code_sha`, and `config_hash` on governed entities.
- Append-only audit events for status transitions, holdout access, promotion, rollback, and manual overrides.
- No credentials, API keys, or raw provider secrets in JSON config fields.

### 38.2 Bet-decision schema

```sql
CREATE TABLE analytics.ml_bet_decisions (
    decision_id VARCHAR PRIMARY KEY,
    prediction_id VARCHAR NOT NULL,
    policy_id VARCHAR NOT NULL,
    quote_id VARCHAR NOT NULL,
    decision_ts_utc TIMESTAMP NOT NULL,
    side VARCHAR NOT NULL,
    line_value DOUBLE NOT NULL,
    decimal_price DOUBLE NOT NULL,
    p_win DOUBLE NOT NULL,
    p_push DOUBLE NOT NULL,
    p_loss DOUBLE NOT NULL,
    expected_value_per_unit DOUBLE NOT NULL,
    stake_units DOUBLE NOT NULL,
    action VARCHAR NOT NULL,
    abstention_reason VARCHAR,
    execution_status VARCHAR NOT NULL,
    policy_version VARCHAR NOT NULL
);
```

### 38.3 Audit event examples

- Config frozen or unfrozen.
- Holdout opened.
- Study resumed, cancelled, or force-failed.
- Trial manually excluded from comparison, with reason.
- Candidate selected over nominal best trial.
- Model promoted, demoted, or rolled back.
- Source data corrected after prediction.
- Bet decision manually overridden.

---

## 39. Frontier backlog

Frontier work belongs behind stable baselines and explicit falsification criteria.

| Candidate | Question | Required baseline | Promotion/failure test |
|---|---|---|---|
| NGBoost/GAMLSS | Does conditional variance/skew improve decision quality? | Constant-variance residual model | Better held-out CRPS/coverage; fail if variance does not track squared error |
| Dynamic Bayesian ratings | Does latent weekly updating beat rolling/ridge ratings? | Weekly ridge and exponential decay | Better one-step-ahead outer-fold loss and stable uncertainty |
| TabPFN | Does a tabular foundation model help in the small-data regime? | Tuned boosting and regularized linear | Strictly prior context only; fail if no robust outer-fold gain |
| Meta-labeling | Can the system identify when to abstain? | Fixed edge/EV threshold | Nested out-of-fold training; fail if selective utility is unstable |
| Joint/copula scores | Does dependence improve total/margin distributions? | Independent score model | Better proper score and dependence calibration |
| Drive competing-risk model | Do drive outcomes improve score simulation? | Aggregate possession model | Better total distribution without calibration collapse |
| Matrix factorization | Are there repeatable style factors beyond scalar ratings? | Rank-one offense/defense | Higher rank must improve future blocks |
| Change-point/HMM | Can latent regime shifts detect genuine team changes? | Known-event flags and dynamic state | Changes must improve forecasts and align prospectively |
| Multi-book quote fusion | Do cross-book dynamics identify stale prices? | Decision-time consensus | Requires timestamped executable quotes and realistic fills |
| Symbolic regression | Can stable football formulas be discovered? | Hand-built possession formula | Formula must remain simple and stable across seasons |

Defer deep neural sequence models, normalizing flows, GNNs, player embeddings, Hawkes processes, and reinforcement-learning staking unless the data grain and sample size change materially. Complexity is not a roadmap milestone by itself.

---

## 40. Revised delivery roadmap

### Release A: trustworthy replay foundation

- Audit canonical game IDs and historical identity.
- Build dataset/target contracts, snapshot manifests, and quarantine tables.
- Audit line/provider/timestamp semantics against overlapping external quotes where possible.
- Build the historical replay engine and golden leakage fixtures.
- Establish market-only, mean, and simple rating baselines.

**Go/no-go:** Recreate a historical week using only then-available data, with zero as-of violations and reconciled outcomes/quotes.

### Release B: CFB rating core

- Weekly ridge offense, defense, pace, and points-per-possession ratings.
- Team-specific preseason priors with continuity/talent/staff inputs.
- Effective-sample-size shrinkage and documented garbage-time filters.
- Era/FBS-FCS/postseason policies.

**Go/no-go:** Ratings and priors improve or match simpler baselines in multiple outer seasons and remain stable under key stress tests.

### Release C: governed tuning MVP

**Status (2026-09-23):** built; go/no-go met.

- Design: [`superpowers/specs/2026-09-23-tuning-lab-release-c-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-c-design.md).
- Build order: [`superpowers/plans/2026-09-23-tuning-lab-release-c-PLAN.md`](superpowers/plans/2026-09-23-tuning-lab-release-c-PLAN.md).
- Code: `models/tuning/`.
- **Reproducibility:** the committed run `models/tuning/specs/total_ratings_v1.json` was run into two clean roots in separate processes. Both gave `run-de1927346ab0` with byte-identical predictions.
- **Crash safety:** a worker killed mid-trial resumes with its completed trials unchanged (`tests/test_tuning_worker.py`).
- **Deviations from this plan:** the tracks were built one after another, not in parallel, and `fit_fold` takes the trial's `ModelSpec` as a fourth argument.

Same scope as before: typed specs and config hashes, a feature builder with availability classes, Ridge / Elastic Net / Huber on fixed feature sets, nested chronological validation, paired baseline comparisons, persistent Optuna workers, model cards, and job heartbeat / retry / cancel / checksum. The Streamlit pages stay out of this release. The go/no-go is a CLI run.

Work splits into one short serial gate, then four tracks that can run at the same time. Each track owns the files listed on it and does not edit another track's files. They all code against the contract below, so nobody waits on another track's pull request to start.

**Shared contract.** A run is one JSON document, `RunSpec`, with `schema_version`, `spec_id`, and canonical JSON. `config_hash` is a hash of that normalized JSON, not of widget order. Unknown fields are rejected. `RunSpec` references:

- `DatasetSpec` — snapshot, grain, target, decision time
- `FeatureSetSpec` — feature ids, versions, availability class
- `FoldSpec` — chronological bounds, game grouping, embargo
- `SearchSpec` — model family and the conditional space in §14 (`cfb_regularized_regression_v1`: Ridge and Elastic Net only)
- `AcceptanceSpec` — the gates for this run

`DecisionPolicySpec` and `ExecutionSpec` belong to Release D. Leave them out.

Every track calls the same function. C3 implements it. C4 calls it. Until C3 has merged, C4 may use a stub that returns a fixed `FoldResult` with the same fields.

```text
fit_fold(train, test, run_spec) -> FoldResult
```

`FoldResult` carries `run_id`, `config_hash`, fold id, predictions, metric values, and the artifact checksum. Seeds for the split, the model, and the sampler live on `RunSpec`.

**C0 — gate, serial, one person.** Land the types and the hash, plus a test that two equivalent specs hash the same and that an unknown field is rejected. Files: `models/tuning/spec.py`, `tests/test_tuning_spec.py`. Other tracks start once this is merged. It should be a small change, not a model.

**Then in parallel:**

| Track | Owns | Builds | Does not build |
| --- | --- | --- | --- |
| C1 Cards | `models/tuning/cards.py`, `tests/test_tuning_cards.py` | Markdown model card from a fixture `FoldResult` and `RunSpec`. Card includes run id, config hash, feature-set id, fold bounds, and baseline comparison slots. | Training, Optuna, UI |
| C2 Features | `models/tuning/features.py`, `tests/test_tuning_features.py` | Versioned fixed feature-set files and a loader. Each feature has an availability class. The loader drops a feature whose as-of time is after `DatasetSpec.decision_ts`. | New rating math, search over feature groups, UI |
| C3 Folds and estimators | `models/tuning/folds.py`, `models/tuning/estimators.py`, `tests/test_tuning_folds.py` | Game-group chronological folds. Ridge, Elastic Net, and Huber on a fixed matrix. Huber is a fixed estimator, not part of the §14 search profile. Paired comparison against the market number and the past-only mean on the same games. `fit_fold` as specified above. Synthetic frames are enough until C2's loader exists. | Workers, study storage, feature search |
| C4 Worker | `models/tuning/worker.py`, `tests/test_tuning_worker.py` | Optuna study on local disk, job states from §35.1 (`queued`, `claimed`, `running`, `completed`, `retry_wait`, `failed`, `cancellation_requested`, `cancelled`), heartbeat lease, retry, cancel between folds, atomic artifact write plus checksum. Idempotency key is `(config_hash, attempt)`. A crash must not reuse a trial number. | Estimator math, feature catalog, UI |

**Join, serial again.** One command runs a fixed feature set through `fit_fold` inside the worker and writes a card. Re-running that command in a clean environment with the same `RunSpec` returns the same `run_id` and the same predictions. Killing the worker mid-trial and resuming leaves completed trials unchanged.

**Go/no-go:** Any run is reproducible from one run ID in a clean environment, and worker interruption does not corrupt study state.

### Release D: probabilistic decisions

**Status (2026-09-23):** built; go/no-go met.

- Design: [`superpowers/specs/2026-09-23-tuning-lab-release-d-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-d-design.md).
- Result: [`total-distributions-2026-09-23.md`](total-distributions-2026-09-23.md).
- **Calibration:** run `dist-0b0cc0382eca` selected the joint home/away model, which passes the calibration gate on the 2021–25 outer folds, declared before scoring.
- **Reproducibility:** the run is byte-identical from two clean roots.
- **No betting claim:** timestamped, priced totals quotes exist for 2026 only, so the second clause holds trivially. The pricing engine (`models/tuning/market.py`) is verified on fixtures only, and priced evaluation moves to Release E.

- Quantile/distributional models and time-aware calibration.
- Prediction intervals and joint score simulation.
- Immutable quote selection, push-aware EV, flat-stake backtester, CLV ledger, and execution sensitivity.
- Abstention and selective-prediction policies.

**Go/no-go:** Distributional outputs are calibrated on outer folds; any betting claim survives realistic price/line degradation and threshold sensitivity.

### Release E: live shadow system

**Status (2026-09-23):** built and armed. The go/no-go is pending until the shadow period ends, around 2026-10-26.

- Design: [`superpowers/specs/2026-09-23-tuning-lab-release-e-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-e-design.md).
- Shadow `shadow-3be5383c3469` covers 2026 weeks 5–8, with week 4 as a rehearsal. Its champion is `ridge_v1_total`; its challenger is `run-de1927346ab0` plus `dist-0b0cc0382eca`, frozen in `dd9724b5`.
- An append-only, hash-chained ledger records every snapshot, prediction, and score. The daily refresh (`scripts/refresh_cfbd.cmd`, 05:00 ET, while logged on) runs `shadow tick` from the code pinned in the detached worktree `../cfb-shadow-pin` at `f0420699`.
- **Priced replay, declared before week 5:** `python -m models.tuning replay --spec models/tuning/specs/replay_2026_w05_08.json` runs after the verdict. It uses the frozen policy on the recorded tables and archived quotes, and its rules are in `models/tuning/replay.py`.
- **Snapshot windows (ET):**
  - Week 5: Sun 9/27 – Thu 10/1.
  - Week 6: Mon 10/5 – Tue 10/6.
  - Week 7: Sun 10/11 – Tue 10/13.
  - Week 8: Sun 10/18 – Tue 10/20.
  - A window with no run is a missed week, which means NO-GO.
- Status: `$CFB_DATA_ROOT/processed/tuning/shadow/shadow-3be5383c3469/status.md`.
- **The verdict is written to the ledger** once every week 5–8 game is scored or no-action.
- **Parity check:** live features equal the historical path's on three past weeks, to within 1e-9.
- **Prospective-only feeds:** the only one wired in is Action Network history, which is hashed after each cutoff. Injuries are not.

- Scheduled snapshots and prediction ledger.
- Champion/challenger aliases, shadow comparisons, rollback.
- Data/prediction/performance/calibration drift monitoring.
- Operational fallbacks and prospective-only feeds such as injuries or archived forecasts.

**Go/no-go:** Complete at least one defined shadow period with no untracked data revisions, timing violations, or missing prediction artifacts.

### Release F: controlled frontier experiments

Run only one frontier hypothesis family at a time, with a preregistered baseline, budget, outer test, and failure rule. Negative results remain first-class artifacts.

**F1, dynamic Kalman ratings (2026-09-23): null, stopped at the screen gate.**

- Declared: [`superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md`](superpowers/specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md).
- Result: [`dynamic-ratings-2026-09-23.md`](dynamic-ratings-2026-09-23.md).
- A week-to-week random walk on `ridge_v1`'s ratings is 0.08 MAE worse on 2021–25, in every season. Recency decay picks no decay.
- The 2026 weeks 9+ confirmation does not run. The next family needs its own declaration.

---

## 41. Definition of done

The Lab is not complete when it can launch Optuna. It is complete when it can prove, for any published forecast or research result:

1. Which exact data and quotes were available at decision time.
2. Which code, configuration, feature, target, rating, and prior versions were used.
3. How every fold was formed and how every transformation was fitted.
4. Which hypotheses and alternatives had already been tried.
5. How the model compared with identical-game, identical-time baselines.
6. Whether uncertainty and calibration were valid out of sample.
7. How a betting decision was priced, settled, and stress-tested.
8. Whether the model was in research, shadow, challenger, or champion status.
9. How to reproduce or roll back the result.
10. What evidence would cause the model or feature to be retired.

---

## 42. Original MVP checklist

Build this first:

1. `analytics.mart_cfb_game_pregame` with strict decision-time/as-of fields.
2. A versioned feature catalog and fixed feature-set picker.
3. Ridge-adjusted weekly offense, defense, and pace ratings.
4. A simple roster-aware prior-year rating blend for offense, defense, and pace.
5. Expanding-window game-group-aware validation.
6. Ridge and Elastic Net downstream models.
7. Persistent Optuna tuning for fixed feature sets.
8. Market-line baseline and timestamp audit.
9. Trial registry, candidate review, and Markdown model-card export.
10. A final untouched season confirmation workflow.

Do not begin with unrestricted feature selection, complex boosted models, automated betting-rule discovery, or a large collection of unvalidated filters. First establish a reproducible, time-safe baseline that can quantify the incremental value of opponent adjustment, preseason priors, pace modeling, and market information.

---

## 43. Final operating rules

- Prefer simple models that survive future seasons over complex models that win one historical split.
- Opponent adjustment is time-indexed; final-season adjustments are not valid historical pregame inputs.
- Separate offensive/defensive efficiency, pace/possessions, and preseason priors rather than compressing everything into one rating.
- Use team-specific preseason priors and estimate their decay empirically.
- Record the exact availability timing of every feature and market quote.
- Keep model selection separate from final confirmation.
- Tune hyperparameters inside chronological folds, never on the final holdout.
- Track all trials, including pruned and failed ones.
- Require baseline, calibration, stability, leakage, and segment checks before promotion.
- Treat CLV, realized returns, and prediction accuracy as distinct outcomes when studying markets.
- Make every promoted model reconstructible from a run ID, config hash, data snapshot, feature versions, rating version, and artifact checksum.

---

## 44. Research and implementation references

This revision synthesizes the attached plan, the project's two FBS totals research reports, the current warehouse catalog, and prior project conversations. The most important external implementation references are:

- [Optuna RDB storage and heartbeat documentation](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.storages.RDBStorage.html)
- [Optuna distributed optimization documentation](https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/004_distributed.html)
- [scikit-learn `TimeSeriesSplit` documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [MAPIE time-series prediction-interval tutorial](https://mapie.readthedocs.io/en/v1.0.1/examples_regression/1-quickstart/plot_ts-tutorial.html)
- [MLflow model registry workflow: aliases and tags](https://mlflow.org/docs/latest/ml/model-registry/workflow/)
- [Great Expectations data-integrity documentation](https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/integrity/)
- [Evidently data-drift documentation](https://docs.evidentlyai.com/metrics/explainer_drift)
- [Arscott, *Market Efficiency and Censoring Bias in College Football Totals Betting*](https://journals.sagepub.com/doi/10.1177/15270025221148991)
- [Paul and Weinbach, *Bettor Preferences and Market Efficiency in Football Totals Markets*](https://ideas.repec.org/a/spr/jecfin/v29y2005i3p409-415.html)
- [Hollmann et al., *Accurate Predictions on Small Data with a Tabular Foundation Model*](https://www.nature.com/articles/s41586-024-08328-6)

### Evidence caution

The project research found little direct published evidence that individual advanced features or frontier models beat FBS game-total markets out of sample after vig. Therefore, this plan treats most football feature ideas as hypotheses, makes the market a mandatory benchmark, requires chronological falsification, and preserves null results.

