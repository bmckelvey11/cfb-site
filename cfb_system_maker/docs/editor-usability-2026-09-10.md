# System Maker editor usability, 2026-09-10

Question: address the five priority findings and supporting accessibility/copy findings from the Impeccable review.

## Delivered

- Open Matchup and groups with active filters by default; collapse the rest. Search reveals matching rows without disabling or removing form values.
- Label unfiltered results as a full-dataset baseline, with explicit Run baseline actions. Preserve baseline analysis as a valid workflow.
- Keep current-system scope, removable filters, count, run, clear and display time visible. Indicate when form edits make displayed results stale.
- Provide a metric guide, team-perspective help, unique accessible button names, chart-value tables, focus treatment, and reduced-motion support.
- Collapse filters below 900px and stack dashboard columns. Filters stay available without JavaScript through the existing native form fallback.
- Expand example theory on demand, improve footer readability, simplify duplicate empty states, remove match-row side stripes and reduce em-dash-heavy copy.
- Keyboard shortcuts: Ctrl/Cmd+Enter runs; Ctrl/Cmd+Shift+F opens filter search; Escape closes narrow filter panel unless a filter dialog is open.

## Evidence and reproduction

Run `python -m pytest` from repository root: 846 passed, 1 skipped, 6 deselected. Existing spread-analysis tests emitted 41 empty-slice warnings. After final refinements and an added scope regression test, `python -m pytest tests/test_web.py tests/test_web_features.py tests/test_filter_modal.py -q`: 196 passed.

Run `python -m cfb_system_maker web --data-dir data --port 5000` and open `/system`. Live data covers 2013-2026, with 13,674 baseline bets in this local snapshot. Search Days of Rest, open Bet-side, enter minimum 14 and save filter: 2,006 matched bets with an active group badge. Clear all returns to the labeled baseline. Expand metric help and example theory. Test viewport widths 320, 390, 768 and desktop; narrow pages showed no document-wide horizontal overflow. No console errors observed.

## Limits

This changes presentation and navigation, not grading, source data, saved systems, or statistical methods. Display time is not an uncached backtest execution time. Cumulative chart table explicitly limits itself to the first 250 points; line-range table lists all ranges. This was not a formal screen-reader certification. The original 26/40 critique score is historical; no new independent score was assigned.
