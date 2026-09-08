# Spread research — index

Entry point for the line-movement work: does The Prediction Tracker's model panel forecast
**where the closing spread goes**, and is any of that reachable at a price you can bet? Every
document, script and data artifact in this tree is listed below. Nothing here restates a
result; each row points at the file that carries it.

The earlier question — can the panel out-forecast the closing line as a margin forecast — is
closed and archived: `archive/spread-margin-era/` (never cite as current). What it left behind
that the live tree still uses is listed in that folder's README.

## Current position, in three sentences

Anchored on the opener, the screened consensus (E4) anticipates about 15% of the open→close
move, and that survives removing the most market-anchored columns (γ ≈ 0.29, R² 0.15, direction
right ~69%, +1.2 to +3.8 points of CLV at the opener). The opener is unreachable through PT,
and the archive's "close" is PT's last recorded line, 0.7 points short of the consensus close.
**Version B** — the same forecast graded at Monday's line against the real close — decides
whether anything is bettable; its first read (42 games) is a slope of 0.20 with an interval that
includes zero, and no verdict is due before the MDE reaches 0.2.

## Reading order for someone new

1. `prereg-line-movement.md` — the question, the estimators, the amendments. Binding.
2. `line-movement-results.md` — the result, decontaminated, with the target and version B reads.
3. `combining-predictions.md` — how the model numbers and the book numbers combine into one bet.
4. `review-2026-09-08-tree-audit.md` — the last full review; §5 is the order of work.
5. `prediction-tracker.md` — the dataset: 179 columns, 17,755 games, 2001–2025.

## Documents

| Document | Kind | What it holds |
|---|---|---|
| `prereg-line-movement.md` | prereg | Retarget the panel at line movement. Version A, amendments A2 (rest of the library), A3 (decontamination), B1 (the version B read). |
| `line-movement-results.md` | results | A, A2, A3; what PT's `line` is; version B first read. |
| `prereg-line-shopping.md` | prereg | Book fair = median of books; the outlier book is the bet. |
| `line-shopping-results.md` | results | Dispersion tail across 7 Action Network books, 2024–2025. |
| `combining-predictions.md` | review | How E4 and the book fair combine into one fair spread and one bet decision. |
| `prediction-tracker.md` | dataset | Column dictionary for the joined panel. |
| `review-2026-09-08-tree-audit.md` | review | Full-tree audit; each finding carries its resolution date. |
| `review-2026-09-02-composite-spread.md` | dated record | The pivot from margin to movement; §5–6 set the direction. Cites archived files. |
| `session-guide-2026-09-02.md` | dated record | Narrative of the 2026-09-02 session. Paths and numbers are as of that day; see its banner. |

## Scripts → what they implement → what they write

All paths under `{CFB_DATA_ROOT}`. Run from repository root.

| Script | Implements | Writes |
|---|---|---|
| `build_prediction_tracker.py` | `prediction-tracker.md` | `ingest/prediction_tracker_lines.csv` |
| `eval_line_movement.py` [`--amend`] [`--decontaminate`] | `prereg-line-movement.md` A / A2 / A3 | `processed/pt_movement_preds{,_a2}{,_decon}.csv`, `pt_movement{…}.json` |
| `eval_version_b.py` | `prereg-line-movement.md` B4–B5, amendment B1 | `processed/version_b.json` |
| `eval_line_shopping.py` | `prereg-line-shopping.md` | `processed/line_shopping_sides.csv`, `line_shopping.json` |
| `check_pt_line_is_close.py` | `line-movement-results.md` § target | `processed/pt_line_vs_an_close.json` |

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
| `weekly_slate.py` | Every movement model + live book fair → `processed/weekly_slate_<stamp>.csv`; appends `movement_forward_log.csv` (version B's dataset) unless the slate is stale |
| `pt_rollover.py` | Exit 0 once PT's slate flips to a new week. Gates a wait loop; writes nothing. |
| `collect_line_timing.py history` | Mondays: Action Network tick histories → `raw/actionnetwork/history_event_<id>.json` (version B's closes) |
| `collect_line_timing.cmd` | Scheduled-task wrapper; exits 3 if `CFB_DATA_ROOT` is unset. Runbook: `docs/line-timing-collector.md`. |

## Data

Never committed. `CFB_DATA_ROOT` is `C:\Users\mckel\dev\cfb\data`.

| Path | What |
|---|---|
| `ingest/prediction_tracker/ncaa20*.csv` | Upstream source, one CSV per season, 2001–2025. |
| `ingest/prediction_tracker_lines.csv` | The joined panel. Regenerate, don't archive. |
| `ingest/pt_snapshots/` | Forward collector: live slate + `.meta.json`, one pair per fetch. Irreplaceable. |
| `raw/actionnetwork/history_event_*.json` | Per-book price paths; the close for version B. Backfillable. |
| `processed/pt_movement*`, `version_b.json`, `movement_forward_log.csv`, `weekly_slate_*.csv`, `line_shopping*`, `pt_line_vs_an_close.json` | Every analysis output above. |

`processed/pt_*` files not listed (leaderboards, sweeps, recency, neff, ats tail, season
stability) are margin-era outputs; their scripts are archived and they are not regenerated.

`ingest/snapshots/` (Action Network book lines) and `ingest/vendor/` (PFF) are **not** PT.
There is no Prediction Tracker table in `cfb.duckdb`; this work is file-based end to end. The
warehouse contributes `stg_gql.game` (the `game_id` join and version B's scores) and
`stg.an_scoreboard` / `stg.an_market` (line shopping and the PT-line check).
