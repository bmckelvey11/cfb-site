# Spread research, margin era (2026-08-28 → 2026-08-29) — archived 2026-09-08

Everything here asked one question: **can a combination of The Prediction Tracker's model
panel out-forecast the closing spread as a prediction of the game margin?** The answer was a
tight null (50.31% ATS on 12,560 bets, best Holm p 0.49), and on 2026-09-02 the work
retargeted at predicting **where the line goes** — the live question in `research/spread/`.

The user's instruction on 2026-09-08: the tree should carry only work aimed at predicting
future lines. These documents and scripts are retained for audit history under the root
archive rule and must not be cited as current guidance.

What still matters from this era is carried in the live tree where it is used:

- `lineca` / `linemidweek` are market lines, not models → `MARKET_LINES` in
  `research/spread/scripts/eval_prediction_tracker_models.py`.
- The coverage filter must be per-season, not whole-history → `regressor_cols` in
  `eval_combination_sweep.py`.
- Ridge is market-proxying on a mid-week panel → the `--decontaminate` flag in
  `eval_line_movement.py` and `line-movement-results.md`.
- Every method's grid, the 1-SE rule and the Frisch–Waugh anchoring → `eval_combination_sweep.py`,
  which the movement scripts import.

`scripts/` here will not run in place: they imported siblings from
`research/spread/scripts/` by relative path. They are frozen at commit `d212537`; check that
commit out to reproduce a margin-era table.
