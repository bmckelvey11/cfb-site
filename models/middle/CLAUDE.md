# Totals model instructions

Scope: totals-model harness only. Shared data, archive, and no-lookahead rules live in
root `CLAUDE.md`; this file does not own system-maker or spread-research behavior.

- Main command: `python -m models.middle backtest --line ou_open --permute`.
- Other `cli.py` subcommands: `importance` (feature importance), `snapshot` (log takeable
  current totals for CLV), `clv` (refresh closes and report mean CLV).
- `python -m models.middle.build_middle_table` rebuilds the table embedded in
  `middle_calculator.html` (a static page; no network requests).
- Cite opening totals from `ou_open`, 2022-2025 prior-season folds, and `|edge| >= 0`.
- Default `--min-prior-games 3` makes week 1 and teams with fewer than three prior games
  no-bets.
- Never cite leaked-era 57% / +8.82% ROI.
- Tests: `tests/test_totals_clv.py`, `tests/test_totals_inference.py`,
  `tests/test_totals_model.py`, and `tests/test_middle_ev.py` (EV math in
  `middle_calculator.html`; skipped without `node`).
