---
task: coach-playstyle-analysis-note
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-coach-playstyle-analysis-note — Summary

The coach playstyle study is now durable in the repo instead of living only in a published
artifact and a session scratchpad.

## What landed

- **`docs/coach-playstyle-analysis.md`** — the note. Why features are residualized on SP+ (raw
  PC1 was 42% team quality), the five groups with signatures and exemplars, the stability caveat,
  the conference-tier confound, the walk-forward market test, and limits. Links the formatted
  artifact.
- **`scripts/analyze_coach_styles.py`** — one re-runnable study script consolidating the two
  scratchpad scripts. Imports `build_coach_style_clusters.py` via `spec_from_file_location` so the
  feature matrix keeps a single definition. Writes the eight charts to `docs/img/` and prints every
  number quoted in the note. Reads `data/` only; touches no package code.
- **`docs/img/coach-style-*.png`** — eight committed charts (~750 KB) so the note renders on
  GitHub without a re-run.
- **`CLAUDE.md`** — new bullet next to the other feature conventions: `coach_style.py` is
  generated, `coach_style_cluster` is `result_lookahead` and why, plus a pointer to the validity
  study with its three load-bearing caveats.

## Verification

- `python scripts/analyze_coach_styles.py` reproduces every number in the note exactly
  (stability 0.456 vs 0.225 chance, walk-forward agreement 0.729, χ² 135.34 p=2.20e-25, Holm
  minimum adjusted p 0.093, market baseline 54.24 line vs 54.38 points).
- All eight markdown image links resolve to committed files.
- Full suite: 566 passed, 1 skipped, 3 deselected.

## Notes

- Two escape-collapse bugs appeared while mechanically consolidating the scratchpad scripts
  (two-line tick labels and one `print("\n...")` lost their backslashes); both fixed and the file
  now parses and runs clean.
- No `results.json` committed — the prose holds every number and the script regenerates it.
- The suite passing is a guard only; this task changed no package code.
