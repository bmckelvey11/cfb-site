# Spread research instructions

Scope: predicting **where the closing spread goes** from The Prediction Tracker's model panel,
the book fair and line shopping, the forward timing test, and their preregistrations. Shared
data, archive, and no-lookahead rules live in root `CLAUDE.md`.

`docs/README.md` indexes every document, script, and data artifact in this tree. Start there.

- Raw Prediction Tracker source belongs under `$CFB_DATA_ROOT/ingest/prediction_tracker/`.
- Preserve preregistration order: `prereg-line-movement.md` and its amendments are binding;
  an amendment overrides only the rules it names. Results go in `line-movement-results.md`;
  summaries elsewhere point at it and do not restate numbers.
- Current result (decontaminated, amendment A3): the screened consensus anticipates ~15% of the
  open→close move at the opener. The opener is unreachable through PT and the archive's "close"
  is PT's last recorded line, so this is an upper bound. **Version B** (`eval_version_b.py`,
  Monday's line vs the real close) is the only thing that can turn it into a bet.
  `docs/plan-2026-09-08-master.md` is the plan of record and its §3 states the one rule
  fixing when version B may be read.
- The earlier margin-vs-close question is closed and archived in `archive/spread-margin-era/`.
  Do not reopen it; do not cite it as current. Its nulls were about a different target and are
  not a gate on movement methods.
- `lineca` and `linemidweek` are market lines, not models: `MARKET_LINES` in
  `eval_prediction_tracker_models.py`, excluded everywhere.
- Sign convention: PT publishes positive = home favoured; the archive is negated. Live
  snapshots are raw PT and must go through `predict_upcoming.to_archive_convention` before
  touching fitted code. Check a number you know before trusting a table.
- Treat open questions as research, not validated edge.
