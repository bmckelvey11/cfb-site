# Prediction Tracker work — index

Entry point for everything built on The Prediction Tracker's model panel. Every document,
script, and data artifact in this line of work is listed below, tagged to the era it belongs
to. Nothing here restates a result; each row points at the file that carries it.

## Current position, in two sentences

The panel does **not** beat the closing line as a margin forecast — a tight, well-powered null
across 154 models and ten combination rules (margin era, closed 2026-08-29). The panel **does**
predict where the line goes: fit against the close with the opener as anchor, every estimator is
significant, direction is right 71–77% of the time, and betting the panel's side at the opener
earns 1.3–3.9 points of closing line value (movement era, live).

**The margin null is not a gate on the movement target.** A method with a recorded null as a
margin forecast is still a candidate against line movement — that is `prereg-line-movement.md`
§ and `review-2026-09-02-composite-spread.md` §5 item 4. Read `line-movement-results.md`, not
`prediction-tracker-findings.md`, for what the work is currently chasing.

## Reading order for someone new

1. `session-guide-2026-09-02.md` — complete narrative account of the movement-era session.
2. `prediction-tracker.md` — the dataset: 179 columns, 17,755 games, 2001–2025.
3. `line-movement-results.md` — the live result.
4. `prediction-tracker-findings.md` — the margin era, consolidated. Read for what was ruled out.
5. `combining-predictions.md` — how the model numbers and the book numbers combine into one bet.

## Documents

### Movement era — predict the close from an early line (2026-09-02 →, live)

| Document | Kind | What it holds |
|---|---|---|
| `prereg-line-movement.md` | prereg | Retarget the panel at line movement. Version A + amendment A2. |
| `line-movement-results.md` | results | γ=0.30, R² to 0.25, 71–77% directional, 1.3–3.9 pts CLV. Version A + A2. |
| `prereg-line-shopping.md` | prereg | Book fair = median of books; the outlier book is the bet. |
| `line-shopping-results.md` | results | Dispersion tail across 7 Action Network books, 2024–2026. |
| `combining-predictions.md` | review | How E4 / E14 / raw consensus and the book fair combine into one fair spread. |
| `review-2026-09-02-composite-spread.md` | review | Reviewer pass on the goal; §5 sets the direction. Status marked in-file. |
| `session-guide-2026-09-02.md` | guide | Full account of the session: what was built, what the numbers say, where it lives. |

### Margin era — beat the close as a margin forecast (2026-08-29, closed null)

| Document | Kind | What it holds |
|---|---|---|
| `prediction-tracker.md` | dataset | Column dictionary for the joined panel. Not era-scoped — still current. |
| `prediction-tracker-model-eval-plan.md` | prereg | Parent plan. Binding on everything downstream. |
| `prediction-tracker-model-eval.md` | results | Per-model leaderboard, pre-registered ensemble, §10 correction. |
| `prediction-tracker-model-eval-plan-addendum.md` | prereg | Nine-method sweep (§1–10) and recency weighting (§11). |
| `prediction-tracker-combination-sweep.md` | results | The nine-method sweep. |
| `prediction-tracker-recency-screen.md` | results | Recency weighting, rolling windows, cohort pooling. |
| `prereg-ats-tail-test.md` | prereg | Is there an actionable ATS edge in the disagreement tail? |
| `prediction-tracker-findings.md` | summary | Consolidated margin-era findings, corrections, defect ledger. |

### Not yet run

| Document | Kind | What it holds |
|---|---|---|
| `prereg-spread-model.md` | prereg | GBM on the repo's own feature stack. Committed; not fitted. |

### Research prompts — questions sent out, not findings

| Document | Status |
|---|---|
| `research-prompt-forecast-combination.md` | Answered; methods implemented and run in the sweep. |
| `research-prompt-open-questions.md` | Open questions raised *by* the results. |
| `prediction-tracker-research-bundle.json` | Generated evidence bundle for those prompts. Rebuild with `build_research_bundle.py`. |

### Lives outside this tree — cited at its real path

| Document | Path |
|---|---|
| Forward collector runbook | `docs/line-timing-collector.md` |
| Where value lives besides the close | `docs/value-sources-beyond-the-close.md` |
| Panel coverage by season | `docs/data-coverage.md` |
| `game_id` join plan and summary | `.planning/quick/260828-p4c-prediction-tracker-game-id-join/` |

## Scripts → what they implement → what they write

All paths under `{CFB_DATA_ROOT}`. Run from repository root.

| Script | Implements | Writes |
|---|---|---|
| `build_prediction_tracker.py` | `prediction-tracker.md` | `ingest/prediction_tracker_lines.csv` |
| `eval_prediction_tracker_models.py` | `…model-eval-plan.md` | `processed/pt_model_eval.json`, `pt_leaderboard_*.csv`, `pt_e4_weights_*.csv`, `pt_ensemble_spread_*.csv` |
| `eval_combination_sweep.py` | `…plan-addendum.md` §1–10 | `processed/pt_combination_sweep.json`, `pt_sweep_*.csv`, `pt_sweep_params_*.csv` |
| `eval_recency_screen.py` | `…plan-addendum.md` §11 | `processed/pt_recency_screen.json`, `pt_recency_*.csv` |
| `eval_ats_tail.py` | `prereg-ats-tail-test.md` | `processed/pt_ats_tail_closing.csv` |
| `eval_line_movement.py` | `prereg-line-movement.md` A + A2 | `processed/pt_movement_preds{,_a2}.csv`, `pt_movement{,_a2}.json` |
| `eval_line_shopping.py` | `prereg-line-shopping.md` | `processed/line_shopping_sides.csv`, `line_shopping.json` |
| `diag_weight_concentration.py` | `…model-eval.md` §weights | `processed/pt_neff_*.csv`, `pt_neff_ridge_lambda_*.csv`, `pt_sweep_params_*.csv` |
| `build_research_bundle.py` | the two research prompts | `research/spread/docs/prediction-tracker-research-bundle.json` |

### Forward operation — runs every week, in this order

| Script | Job |
|---|---|
| `collect_line_timing.py snapshot` | Fetch PT's rolling CSV to `ingest/pt_snapshots/`, then invoke the two below on the new file. |
| `predict_upcoming.py` | Model predictions for the live slate → `processed/pt_upcoming_predictions.csv` |
| `weekly_slate.py` | Every movement model + live book fair → `processed/weekly_slate_<stamp>.csv`, appends `movement_forward_log.csv` |
| `pt_rollover.py` | Exit 0 once PT's slate flips to a new week. Gates a wait loop; writes nothing. |
| `collect_line_timing.cmd` | Scheduled-task wrapper. Runbook is `docs/line-timing-collector.md`. |

### Diagnostics — one question each

`diag_market_proxy.py` (which models are the line under another name) · `diag_screen_decontam.py`
(does screening launder the consensus) · `diag_eligibility_tenure.py` (the tenure-test defect, `prediction-tracker-findings.md` §4) ·
`akm_winner_bound.py` (winner's-curse bound on the leaderboard top) · `compare_lines.py`
(PT's line columns against the book feed).

## Data

Never committed. `CFB_DATA_ROOT` is `C:\Users\mckel\dev\cfb\data`.

| Path | What |
|---|---|
| `ingest/prediction_tracker/ncaa20*.csv` | Upstream source, one CSV per season, 2001–2025. |
| `ingest/prediction_tracker_lines.csv` | The joined panel. Regenerate, don't archive. |
| `ingest/pt_snapshots/` | Forward collector: live slate + `.meta.json`, one pair per fetch. |
| `processed/pt_*` | Every analysis output above. |

`processed/pt_model_season_stability.csv` is an orphan: `prediction-tracker-model-eval.md` cites it,
but no script in the tree writes it. Treat the file as unreproducible until a script claims it.

`ingest/snapshots/` (Action Network book lines) and `ingest/vendor/` (PFF) are **not** PT.
There is no Prediction Tracker table in `cfb.duckdb` — this work is file-based end to end;
the warehouse contributes only `stg_gql.game` for the `game_id` join.
