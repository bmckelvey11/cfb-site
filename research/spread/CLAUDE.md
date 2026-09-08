# Spread research instructions

Scope: Prediction Tracker forecast evaluation, combination studies, preregistrations, and
supporting scripts. Shared data, archive, and no-lookahead rules live in root `CLAUDE.md`.

`docs/README.md` indexes every document, script, and data artifact in this tree, tagged to
the margin era (closed) or the line-movement era (live). Start there.

- Raw Prediction Tracker source belongs under `$CFB_DATA_ROOT/ingest/prediction_tracker/`.
- Preserve preregistration order. Parent model-evaluation plan remains binding; addendum
  overrides only rules it names.
- Current result: on the **line-movement** target -- predict the close from an early line,
  which is the actual goal: closing line value -- the panel works. Opener-anchored, gamma 0.30,
  R^2 to 0.25, direction right 71-77% of the time, 1.3-3.9 points of CLV at the opener. See
  `research/spread/docs/README.md`, then `prereg-line-movement.md` and `line-movement-results.md`.
- Closed null, do not reopen as stated: **as a margin forecast** against the close, the panel
  reached 50.31% ATS versus 52.38% break-even. That null is specific to that target and is not
  a gate against trying the same methods on line movement, where they succeed.
  Treat open questions as research, not validated edge.
- Keep generated research bundles clearly labeled and reproducible from named scripts.
