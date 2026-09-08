# Spread research instructions

Scope: Prediction Tracker forecast evaluation, combination studies, preregistrations, and
supporting scripts. Shared data, archive, and no-lookahead rules live in root `CLAUDE.md`.

`docs/README.md` indexes every document, script, and data artifact in this tree, tagged to
the margin era (closed) or the line-movement era (live). Start there.

- Raw Prediction Tracker source belongs under `$CFB_DATA_ROOT/ingest/prediction_tracker/`.
- Preserve preregistration order. Parent model-evaluation plan remains binding; addendum
  overrides only rules it names.
- Current result: panel reached 50.31% ATS versus 52.38% break-even and did not beat close
  **as a margin forecast**. That null is specific to that target and is not a gate against
  trying methods on the line-movement target (predict the close from an early line), which is
  the actual goal: closing line value. See `research/spread/docs/prereg-line-movement.md` and
  `research/spread/docs/line-movement-results.md`. Treat open questions as research, not validated edge.
- Keep generated research bundles clearly labeled and reproducible from named scripts.
