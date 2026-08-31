# Analysis plan — Prediction Tracker model evaluation and ensemble

Written 2026-08-29, **before** fitting any ensemble. Build implements this; Audit grades
against it. Results land in `prediction-tracker-model-eval.md`.

Data: `{CFB_DATA_ROOT}/raw/prediction_tracker_lines.csv` (see `prediction-tracker.md`).
17,731 rows with `match_status=matched` and a real score; 154 model columns; 25 seasons.

## 1. Estimand

**Primary.** The out-of-sample reduction in mean squared error of the predicted home
margin, relative to the market spread, achieved by a weighted combination of the computer
models available at prediction time. Population: Prediction-Tracker-covered FBS games,
seasons 2006–2025 (2001–2005 are weight-fitting burn-in). Conditioning set: games where
the benchmark line exists (99.9% of rows).

**Secondary, per model.** (a) *Accuracy* — paired ΔMSE against the benchmark on that
model's own games. (b) *Volatility* — see §4.

All predictions are stated as **predicted home margin** = −(spread), oriented to Prediction
Tracker's `home`/`road` (i.e. the margin is negated on `orientation_flipped=1` rows so it
matches the sign of the line columns). Error = `margin + spread`.

Identification status: **purely predictive**. No causal claim is made or implied anywhere
in this analysis.

## 2. Model specification

Two benchmarks, both reported in every table — they answer different questions and
collapsing them would confound model quality with forecast staleness:

| Benchmark | Column | Question it answers |
|---|---|---|
| **Skill** | `lineopen` (opening) | Did the modeler add information available *at publication time*? PT models are published mid-week, so scoring them only against closing punishes them for staleness rather than error. |
| **Deployability** | `line` (closing) | Can this beat the number you could actually bet? |

Candidate combinations. All are fit **walk-forward**: weights for season *t* use only
seasons < *t*. `E4` is the **pre-registered primary**; the rest are secondary.

| ID | Specification |
|---|---|
| E1 | Equal-weight mean of all available models. Naive; the pilot already shows it loses to the market by 10.6 MSE, driven by a tail of models at RMSE 27. |
| E2 | Median of available models (robust to that tail). |
| E3 | Skill-screened mean — keep models whose prior-season ΔMSE vs benchmark ranks in the top K; equal-weight the survivors. K fixed at 20 in advance. |
| **E4** | **`margin ~ β₀ + β₁·mkt + β₂·(screened_consensus − mkt)`, two free slopes, refit walk-forward.** Low-dimensional, handles a varying model set without imputation, and nests the benchmark (β₀=0, β₁=1, β₂=0). |
| E5 | Ridge on the model set *active in that season* plus the benchmark, complete data for that set, refit walk-forward. |

**Deliberately excluded:** any imputation of a missing model's prediction from the other
models present in the same row. That makes the imputed column a function of its
co-regressors, launders the consensus into every coefficient, and destroys the
interpretation of which models carry weight. Because missingness is season-level (§
diagnostics), fitting per-season on the active set removes the need for it entirely.

**Functional-form diagnostics for Build:** residual-vs-fitted on E4 (is the margin↔line
relation linear across the spread range?), and whether β₁ drifts across seasons.

## 3. Dependence structure

Games are grouped within **season** (model rosters, rule changes, market efficiency all
move by season). Measured season-level ICC on the paired loss differential is 0.00023,
DEFF 1.16 — small, but 25 clusters is below the ~40 threshold where analytic
cluster-robust SEs are trustworthy, so:

- Primary inference: **wild cluster bootstrap** at season level (`scripts/wild_cluster_boot.py`).
- Secondary: cluster-robust SE at season-week (~500 clusters) as a sensitivity check.
- Never: plain OLS SEs on the raw row count.

## 4. Primary metric, volatility definition, benchmark

**Primary metric:** mean squared error of the predicted margin. Squared error is the
consistent scoring function for a point forecast of a conditional mean, which is what a
spread is. Paired per game, then inference on the differential (Diebold-Mariano logic).

E4 **nests** its benchmark, so the primary test is **Clark-West**, not plain DM — plain DM
is biased toward the larger model and would over-reject.

**Volatility — pre-committed to one number:** the SD of the model's prediction error after
removing that model's own mean bias, `√(MSE − bias²)`. Chosen in advance precisely because
with 154 models some will win on IQR and lose on SD, and choosing after seeing that is the
multiplicity this plan exists to control. Companion descriptive: season-to-season Spearman
correlation of skill rank (stability), reported but never decisive.

**Secondary/descriptive only, never the decision:** MAE, RMSE, ATS hit rate.

**Decision value:** report the against-the-spread record and ROI of E4's disagreements with
the closing line at −110. A squared-error gain that never flips a bet at available prices
is not deployable, and the plan says so before seeing the number.

## 5. Multiplicity budget

| Family | Count | Control |
|---|---|---|
| Primary ensemble claim (E4 vs benchmark) | 1 | None needed — pre-registered here, before fitting. |
| Secondary ensembles (E1, E2, E3, E5) | 4 | Holm. |
| Per-model leaderboard | ≤154 | Benjamini-Hochberg across models; report q-values, not raw p. |

The winner of the per-model leaderboard is subject to winner's-curse inflation. Its quoted
skill is the *selection* estimate and will be labelled as such — no separate confirmation
estimate is available for it without spending the evaluation window.

## 6. Pre-run power / MDE

Computed on the pilot (equal-weight ensemble vs closing line), season-clustered:

| Window | n | Clusters | SE(ΔMSE) | MDE (MSE) | MDE (RMSE) |
|---|---|---|---|---|---|
| Full walk-forward 2006–2025 | 17,709 | 25 | 0.864 | 2.42 | **0.078** |
| 2006–2020 | 10,409 | 15 | 1.017 | 2.85 | 0.092 |
| 2019–2025 | 5,249 | 7 | 1.623 | 4.54 | 0.146 |
| 2021–2025 | 3,944 | 5 | 1.791 | 5.01 | 0.161 |

The full window detects a **0.078 RMSE** improvement at 80% power — informative for an
effect of the size worth deploying.

**Why there is no held-out confirmation window.** A 2021–25 confirmation has MDE 0.161
RMSE, roughly double the effect the selection window can resolve: it could not confirm the
result it exists to check, and a failed confirmation would be uninterpretable. Rather than
run a test that cannot answer, this plan **pre-registers E4** so the primary claim carries
no selection multiplicity and can use the full window at full power. A 2019–25 split is
reported as a *directional* robustness check, explicitly labelled underpowered.

## 7. Stop rule / evaluation window

Fixed now: walk-forward from **2006** (five-season burn-in) through **2025**, one pass, one
look. No re-specification after seeing results; anything discovered post hoc is reported as
exploratory and excluded from the gate.

## 8. Known threats, and what is done about each

| Threat | Evidence | Handling |
|---|---|---|
| **Coverage-difficulty confound** — models cover different game sets, so raw RMSE is not comparable. | `linegrinder` has the best raw RMSE (15.22 vs market 15.62) yet loses to the market by 5.08 MSE *on its own games*. | Never rank on raw RMSE. All ranking is paired ΔMSE vs benchmark on common support. |
| **Game-selective missingness (MNAR)** — a model that skips games it is unsure about looks artificially skilled. | 111 model-seasons cover 30–75% of games while appearing across >60% of weeks: they skip games rather than joining late. 90 more are benign partial-season entrants. | Primary leaderboard restricted to the 997 model-seasons with ≥95% within-season coverage. Full-sample version reported separately and flagged. |
| **Survivorship** — models that stopped publishing may have been dropped for being bad. | 154 models, spans 1–25 seasons. | Skill is estimated per model-season, so a model that quit contributes only the seasons it was active; no forward-filling. Stated as a limitation on the *population*, not fixable in-sample. |
| **Forecast staleness** vs model quality. | Closing line RMSE 15.617 beats opening 15.770. | Dual benchmark (§2). |
| **Forecast-combination puzzle** — estimated weights often lose to simple averages. | — | Simple aggregation (E1, E2) is a serious contender, not a strawman; E4 is deliberately 2-parameter. |
