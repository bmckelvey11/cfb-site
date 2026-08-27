---
task: feature-filter-sidebar-search-collapsible-groups
date: 2026-08-27
mode: quick
status: complete
landed: 1
superseded: 2
---

# Quick Task 260827-8or — Summary

**One of the three planned fixes landed. The other two were solved on `master` by a
concurrent session while this task was executing, and were dropped rather than re-applied.**

## Landed

**`5231273` feat(web): add search and collapsible groups to the Feature Filters sidebar**
(Plan Fix 1.) New `static/feature_sidebar.js` (progressive enhancement, own
`feature-sidebar-js` flag so it does not depend on `filter_modal.js`), a search input in
`index.html`, CSS in `styles.css`, 4 contract tests in `tests/test_filter_modal.py`.

Reworked from the original worktree implementation in two places, because `master`'s new
`.stat-row` markup landed underneath it:

- `rowText()` now matches `.stat-row__label, .filter-launcher`. Team-scoped stats keep
  their name in a `<span class="stat-row__label">` and their buttons read only
  "Bet-side"/"Opponent", so matching button text alone would have missed every stat name
  and matched every team-scoped row on the term "opponent".
- The group badge counts `[data-has-filter="1"]` instead of `input[name="ff_enable"]:checked`.
  Those are the same chips the row already renders as solid pills, so badge and pills can
  never disagree. A stat with both sides configured counts 2, matching what the eye sees.

Verified in the running app against the full dataset (not just tests):

| Check | Result |
|---|---|
| Search "explosiveness" (name only in `.stat-row__label`) | 2 rows, 1 group |
| Search "wind speed" | 1 row, 1 group |
| No-match term | 0 rows, 0 groups (empty legends hidden too) |
| Collapse group | 0 rows, `aria-expanded="false"` |
| Collapsed **then** search | 2 rows revealed — search overrides collapse |
| Hidden rows still serialize | 136 `ff_value` entries survive a no-match search |
| Search input serialized into form | no (`name` attribute absent by design) |
| Badges with 2 filters active | Weather `1`, Season To Date `2` — matches pills and sentences |

## Superseded on master — not applied

**Fix 2 (one launcher per team-scoped feature).** `7c2e694` "style(web): one row per stat in
the filter sidebar" reached the same goal (halve the sidebar) by a better route: one row
holding the stat name once plus two compact side pills, with `data-has-filter="1"` marking
configured sides. That *preserves the active-side visibility the plan had listed as an
accepted loss*. `969c7ca` then deleted `renderPerspectiveControl`, the in-modal switcher
Fix 2 depended on — citing the same silent-retarget bug this task's executor independently
found, and resolving it the opposite way (keep one chip per perspective, drop the switcher).
Re-applying Fix 2 would have reverted both commits. Dropped.

**Fix 3 (cumulative chart circles).** `index.html:551` now gates markers behind
`{% if cumulative_chart.points|length <= 60 %}`, so an unfiltered backtest renders zero
circles instead of 13,003. The DOM explosion is fixed. The worktree branch holds a
refinement — thin server-side to 60 markers so *some* hover titles survive on large samples,
instead of none — which was not applied over a working fix.

## Notes for later

- Branch `worktree-agent-af40be9cf478151a6` is kept (worktree removed). It holds the
  unlanded Fix 2 and Fix 3 commits. Delete it if neither is wanted.
- `reloadFeatureDetail()` (`filter_modal.js:806`) is now dead code — `969c7ca` removed both
  call sites with `renderPerspectiveControl`. Left in place per CLAUDE.md §3 (mention, do
  not delete pre-existing dead code).
- `260827-8or-PLAN.md` (committed as `d7a3f1c`) describes Fix 2's now-obsolete approach.
  Left as the historical record rather than rewritten.
- Six orphaned `worktree-agent-*` worktrees from earlier sessions remain in
  `.claude/worktrees/`, plus two `clv-betlog-ingestion` ones. Not touched.

## Verification

`.venv/Scripts/python.exe -m pytest` — 515 passed, 1 skipped, 3 deselected.
Baseline on `master` before this change was 511 passed; +4 from the new contract tests.
(Note: `python -m pytest` on system Python 3.14 cannot import the vendored cfbd client;
use the venv interpreter.)
