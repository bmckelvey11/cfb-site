---
task: coach-style-cluster-feature
date: 2026-08-27
mode: quick
status: complete
---

# Quick Task 260827-coach-style-cluster-feature — Summary

`coach_style_cluster` shipped as a team-scoped categorical registry feature.

## What landed

- **`scripts/build_coach_style_clusters.py`** — deterministic offline generator
  (pandas/numpy/sklearn, not runtime deps). 13 style features per team-season
  (2016-2024; havoc splits are broken pre-2016 and absent 2025), z-scored within season,
  residualized on SP+ overall, games-weighted per coach with >= 3 seasons, k-means k=5
  (`random_state=0`). Cluster names come from profile signatures (min pass rate ->
  option_ground, etc.), not cluster indices, so regeneration is label-stable.
- **`cfb_system_maker/coach_style.py`** — generated 189-coach dict
  (`COACH_STYLE_CLUSTERS`). Split: balanced_spread 56, pass_first_efficient 42,
  bend_dont_break 39, attack_defense 35, option_ground 17.
- **`features.py`** — `coach_style_cluster` FeatureDef, group `result_lookahead`
  (career-level label: a 2017 game reads a label informed by 2018-2024 stats, so it
  fails the entering-game rule; candidate search already excludes the group).
- **`enrich.py`** — `_lookup_team_scoped` raw_coaches branch resolves the coach's full
  name into the embedded dict; unknown coach -> None (fails closed).
- **Test** — `test_coach_style_cluster_from_embedded_mapping` (known coach -> label,
  unknown -> None).

## Verification

Full suite: 551 passed, 1 skipped, 3 deselected (`.venv/Scripts/python.exe -m pytest`).

## Notes

- Registry version hash changed — existing `features.json` sidecars will show the
  stale-registry warning in the web UI until `enrich` is re-run.
- Analysis provenance: in-session clustering (silhouette scan k=2-9, ~0.13-0.17;
  bootstrap ARI ~0.5; quadrant schemes tested and rejected — silhouette 0.006-0.039).
  Styles are a continuum except option_ground, which is genuinely discrete.
