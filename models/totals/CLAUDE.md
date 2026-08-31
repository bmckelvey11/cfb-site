# Totals model instructions

Scope: totals-model harness only. Shared data, archive, and no-lookahead rules live in
root `CLAUDE.md`; this file does not own system-maker or spread-research behavior.

- Main command: `python -m models.totals backtest --line ou_open --permute`.
- Cite opening totals from `ou_open`, 2022-2025 prior-season folds, and `|edge| >= 0`.
- Default `--min-prior-games 3` makes week 1 and teams with fewer than three prior games
  no-bets.
- Never cite leaked-era 57% / +8.82% ROI.
- `cfb_paths.DATA_ROOT` supplies warehouse/data location; no repository-relative fallback.
- Tests: `tests/test_totals_clv.py`, `tests/test_totals_inference.py`, and
  `tests/test_totals_model.py`.
