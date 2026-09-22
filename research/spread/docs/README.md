# Spread research — index

Entry point for the line-movement work: does The Prediction Tracker's model panel forecast
**where the closing spread goes**, and is any of that reachable at a price you can bet? Every
document, script and data artifact in this tree is listed below. Nothing here restates a
result; each row points at the file that carries it.

The earlier question — can the panel out-forecast the closing line as a margin forecast — is
closed and archived: `archive/spread-margin-era/` (never cite as current). What it left behind
that the live tree still uses is listed in that folder's README.

The forecaster this tree serves is the **pred-tracker-model** (E4 and its siblings, via
`weekly_slate.py`) — distinct from **The Prediction Tracker** / **PT**, the upstream vendor
panel it reads. Renamed from "the spread model" on 2026-09-17.

## Current position, in three sentences

Anchored on the opener, the screened consensus (E4) anticipates about 15% of the open→close
move; that survives the walk-forward decontamination screen (amendment A6, the screen that never
sees its own test set, now the citable one), and E4 is also the best method here — the ridge that
briefly appeared to beat it was an artifact of where its grid stopped, withdrawn by amendment A7,
which retired the ridge from the served slate. But the opener is unreachable through PT, the
archive's "close" is PT's last recorded line about 0.7 points short of the consensus close, and
amendment A5 found no information in the panel past PT's last capture — so nothing here shows
the panel leading the market rather than reporting it late. **Version B** — the same forecast
graded at Monday's line against the real close — is what decides whether anything is bettable;
it has returned no verdict, and amendment B3 fixes that it cannot before season end, where
confirmatory inference needs ≥ 8 week clusters. Every number above lives in
`line-movement-results.md`, never here.

## Reading order for someone new

1. `prereg-line-movement.md` — the question, the estimators, the amendments. Binding.
2. `line-movement-results.md` — the result, decontaminated, with the target and version B reads.
3. `combining-predictions.md` — how the model numbers and the book numbers combine into one bet.
4. `review-2026-09-08-tree-audit.md` — the last full review, every finding resolved in-file.
   The plan that follows it: `docs/superpowers/plans/2026-09-08-spread-next-steps.md`.
5. `prediction-tracker.md` — the dataset: 179 columns, 17,755 games, 2001–2025.

## Documents

| Document | Kind | What it holds |
|---|---|---|
| `prereg-line-movement.md` | prereg | Retarget the panel at line movement. Version A, amendments A2 (rest of the library), A3 (decontamination), B1 (the version B read), the amendment ledger, A6 (walk-forward screen), B3 (stopping rule), A5 (post-capture move), A4 (finer ridge grid). |
| `line-movement-results.md` | results | A, A2, A3, A6, A4, A5; what PT's `line` is; when the constituents publish; B2 (capture buckets); version B reads. |
| `prereg-line-shopping.md` | prereg | Book fair = median of books; the outlier book is the bet. |
| `line-shopping-results.md` | results | Dispersion tail across 7 Action Network books, 2024–2025. |
| `combining-predictions.md` | review | How E4 and the book fair combine into one fair spread and one bet decision. |
| `prediction-tracker.md` | dataset | Column dictionary for the joined panel. |
| `review-2026-09-08-tree-audit.md` | review | Full-tree audit; each finding carries its resolution date. |
| `methods-review-2026-09-21.md` | review | Audit of the live serving and version B grading paths on 147 graded games. Leakage and selection clean; the graded "Monday line" is a Tuesday line for 62% of games, B4's regressor spends 71% of its variance on the revert-to-opener component, and `beat_close` counts a line that never moved as a loss. No verdict. |
| **`plan-2026-09-08-master.md`** | **plan of record** | **Start here for the plan.** What is true, what is decided, what must change, and the execution waves. Absorbs the hardened plan, the review log and the audit's open items. |
| `plan-2026-09-08-hardened.md` | absorbed | Contract the master absorbed; audit history of the claudex-loop. |
| `plan-review-log-2026-09-08.md` | absorbed | The three-round adversarial argument (claudex-loop) that produced the hardened plan. |
| `build-brief-2026-09-08.md` | appendix | Parallel execution of the hardened plan: waves, file ownership, per-agent acceptance checks. |
| `actionable-picks-2026-09-17.md` | review | Can the slate be bet today? No — the anchor holds ~0.7 pt of move total, and beat-close inverts with edge. Points at the results doc. |
| **`pt-findings-summary-2026-09-17.md`** | **index** | **Start here for the 2026-09-17 PT studies.** Connects all six, the mechanism they share, and what is still open. Restates no numbers. |
| `tick-anchored-model-infeasible-2026-09-17.md` | review | Why the current-line anchor cannot be built: the archive's only line IS the target, an_market has no timestamp, the 275 tick paths are all inside the forward-test period, and AN does not retain settled paths. |
| `phcover-accuracy-2026-09-17.md` | review | EXPLORATORY: PT's published P(home covers). AUC 0.489, Brier skill negative, and 99.45% a transform of `lineavg - line`. No signal. |
| `linestd-confidence-2026-09-17.md` | review | EXPLORATORY: PT's panel dispersion. No volatility content; no quintile rescues the panel signal, which goes 0.4943 ATS over 2003-2025. |
| `phwin-accuracy-2026-09-17.md` | review | EXPLORATORY: PT's P(home wins). A real forecast (AUC 0.80) but beaten by the line on AUC and Brier, and encompassed by it. |
| `model-columns-ats-2026-09-17.md` | review | EXPLORATORY: all 109 screened PT model columns bet ATS against the close. Walk-forward selection lands at 0.5001; no model's CI clears the vig. |
| `phwin-moneyline-2026-09-17.md` | review | EXPLORATORY: phwin priced against real moneylines, 2021-25. Loses; the spread control arm is unresolved, not an edge. |
| `panel-vs-line-2026-09-17.md` | review | EXPLORATORY: what the ~140 `line*` columns are. None of 141 beats the closing line, and deviation from it correlates +0.97 with error. |
| `panel-ats-2026-09-17.md` | review | EXPLORATORY: the bettability test the RMSE study could not do. 2 of 330 testable cells clear break-even; `linecrunch` clears it while losing on RMSE. |
| `line-movement-distribution-2026-09-18.md` | results | DESCRIPTIVE: how far the spread actually travels open→close (Bovada, 2021-25, n=3,932). 14.24% never move; the market moves onto 3 and 7 (+1.22 pp each) but only 7 is sticky; no stable drift. Forecasts nothing — that is `line-movement-results.md`. |
| `review-2026-09-02-composite-spread.md` | dated record | The pivot from margin to movement; §5–6 set the direction. Cites archived files. |
| `session-guide-2026-09-02.md` | dated record | Narrative of the 2026-09-02 session. Paths and numbers are as of that day; see its banner. |

## Scripts → what they implement → what they write

All paths under `{CFB_DATA_ROOT}`. Run from repository root.

| Script | Implements | Writes |
|---|---|---|
| `build_prediction_tracker.py` | `prediction-tracker.md` | `ingest/prediction_tracker_lines.csv` |
| `eval_line_movement.py` [`--amend`] [`--decontaminate`] [`--decontaminate-wf`] [`--fine-ridge`] | `prereg-line-movement.md` A / A2 / A3 / A6 / A4 | `processed/pt_movement_preds{,_a2}{,_decon,_decon_wf}.csv`, `pt_movement{…}.json`, `pt_movement_decon_wf_a4.json` |
| `eval_version_b.py` | `prereg-line-movement.md` B4–B5, amendments B1, B2, B3 | `processed/version_b.json` |
| `version_b_by_week.py` | The version B read cut by season-week cluster (same joins as `eval_version_b.py`; per-week SEs are HC1, informational only) | stdout |
| `audit_version_b_methods.py` | `methods-review-2026-09-21.md` — anchor realization, regressor composition, tie handling, selection, B2 coverage, archive leakage, and the exploratory R/C decomposition. Grades nothing | stdout |
| `eval_line_shopping.py` | `prereg-line-shopping.md` | `processed/line_shopping_sides.csv`, `line_shopping.json` |
| `check_pt_line_is_close.py` | `line-movement-results.md` § target, amendment A5 | `processed/pt_line_vs_an_close.json` |
| `model_publish_times.py` | `line-movement-results.md` § when the constituents publish | `processed/model_publish_times.csv` |
| `eval_phcover_calibration.py` | `phcover-accuracy-2026-09-17.md` | `processed/phcover_calibration.json` |
| `eval_linestd_confidence.py` | `linestd-confidence-2026-09-17.md` | `processed/linestd_confidence.json` |
| `eval_phwin_accuracy.py` | `phwin-accuracy-2026-09-17.md` | `processed/phwin_accuracy.json` |
| `eval_phwin_moneyline.py` [`--from-season`] [`--to-season`] [`--cluster`] | `phwin-moneyline-2026-09-17.md` | `processed/phwin_moneyline.json` |
| `eval_panel_vs_line.py` [`--min-n`] | `panel-vs-line-2026-09-17.md` | `processed/panel_vs_line.json` |
| `eval_panel_ats.py` [`--min-bets`] | `panel-ats-2026-09-17.md` | `processed/panel_ats.json` |
| `eval_model_columns_ats.py` | `model-columns-ats-2026-09-17.md` | `processed/model_columns_ats.json` |
| `edge_vs_market_move.py` | `actionable-picks-2026-09-17.md` § 0: regresses the served `edge` on the move since the opener | stdout |
| `version_b_ceiling.py` | `line-movement-results.md` § version B read of 2026-09-17: E\|close − anchor\| (the CLV ceiling) and each week's anchor ET weekday | stdout |
| `analyze_line_movement_distribution.py` [`--start`] [`--end`] [`--book`] | `line-movement-distribution-2026-09-18.md` | `research/spread/docs/img/line-movement-distribution.png`, `research/spread/docs/data/line-movement-frequency.csv` |

Estimator core, imported by all of the above and not run on its own for live work:
`eval_prediction_tracker_models.py` (loader, `MARKET_LINES`, prior skill, wild cluster
bootstrap) and `eval_combination_sweep.py` (Frisch–Waugh `Anchor`, `gamma_fit`, the E6–E14
fitters, grids, 1-SE rule). Their `main()`s produce the archived margin-era tables.
`tests/test_spread_estimators.py` covers the core on synthetic data.

### Forward operation — runs on every new PT snapshot

| Script | Job |
|---|---|
| `collect_line_timing.py snapshot` | Fetch PT's rolling CSV to `ingest/pt_snapshots/`, then invoke the two below on the new file. |
| `predict_upcoming.py` | E4 / E14 against the line at capture → `processed/pt_upcoming_predictions.csv` |
| `weekly_slate.py` | Every movement model + live book fair over 10 books (Action Network + the-odds-api, deduped — amendment S2) + the side to take → `processed/weekly_slate_<stamp>.csv` and `weekly_slate_latest.csv`; appends `movement_forward_log.csv` (version B's dataset) unless the slate is stale |
| `pt_rollover.py` | Exit 0 once PT's slate flips to a new week. Gates a wait loop; writes nothing. |
| `migrate_book_set_version.py` | One-time, idempotent: stamps `book_set_version=1` on forward-log rows written before amendment S2 promoted the-odds-api books into `book_fair` |
| `collect_line_timing.py history` | Mondays: Action Network tick histories → `raw/actionnetwork/history_event_<id>.json` (version B's closes) |
| `collect_line_timing.cmd` | Scheduled-task wrapper; exits 3 if `CFB_DATA_ROOT` is unset. Runbook: `docs/line-timing-collector.md`. |
| `scrape_dratings.py` | DRatings FBS power ratings (overall, SOS, standard, inference, Vegas + ranks) → `ingest/dratings/fbs_ratings_<updated>.csv`. Page is overwritten weekly with no history; runs Mondays from `collect_line_timing.py history`. Not wired into any model. |

## Data

Never committed. `CFB_DATA_ROOT` is `C:\Users\mckel\dev\cfb\data`.

| Path | What |
|---|---|
| `ingest/prediction_tracker/ncaa20*.csv` | Upstream source, one CSV per season, 2001–2025. |
| `ingest/prediction_tracker_lines.csv` | The joined panel. Regenerate, don't archive. |
| `ingest/pt_snapshots/` | Forward collector: live slate + `.meta.json`, one pair per fetch. Irreplaceable. |
| `raw/actionnetwork/history_event_*.json` | Per-book price paths; the close for version B. Backfillable. |
| `processed/pt_movement*`, `version_b.json`, `movement_forward_log.csv`, `weekly_slate_*.csv`, `line_shopping*`, `pt_line_vs_an_close.json`, `model_publish_times.csv` | Every analysis output above. |

`processed/pt_*` files not listed (leaderboards, sweeps, recency, neff, ats tail, season
stability) are margin-era outputs; their scripts are archived and they are not regenerated.

**Action Network book ids**, from AN's own `/web/v1/books` (checked 2026-09-08): 15 consensus,
30 opener, **49 Caesars, 68 DraftKings, 69 FanDuel, 71 BetRivers, 75 BetMGM**. Every document
dated before 2026-09-08 that names these books (Pinnacle, Bet365, "Caesars mis-posts") used a
wrong label; the ids and every number were right. Book 71, the one that mis-posts, is BetRivers.

`ingest/snapshots/` (Action Network book lines) and `ingest/vendor/` (PFF) are **not** PT.
There is no Prediction Tracker table in `cfb.duckdb`; this work is file-based end to end. The
warehouse contributes `stg_gql.game` (the `game_id` join and version B's scores) and
`stg.an_scoreboard` / `stg.an_market` (line shopping and the PT-line check).
