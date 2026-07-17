---
status: testing
phase: 04-filter-popup-modal
source: [04-VERIFICATION.md]
started: 2026-07-17T19:25:00Z
updated: 2026-07-17T19:25:00Z
---

## Current Test

number: 1
name: Sidebar open + live chips
expected: |
  Dialog opens, focus moves inside, live chips update after a short pause;
  About Filter shows escaped definition text.
awaiting: user response

## Tests

### 1. Sidebar open + live chips
expected: Start web UI with processed data; open a categorical filter from the sidebar. Dialog opens, focus inside, chips update after short pause; About shows definition.
result: [pending]

### 2. Numeric explore + Save/Cancel
expected: Drag/edit numeric filter; Chart/List; Save then Cancel on a second edit. Dual handles sync with BETWEEN; Save commits URL via filters-form GET; Cancel leaves URL unchanged.
result: [pending]

### 3. Edit / Escape / backdrop
expected: Click Edit on an active-filter sentence; press Escape; click backdrop. Prefill; Escape discards + focus restore; backdrop neither commits nor discards.
result: [pending]

### 4. Live failure + Retry
expected: Block `/api/backtest` (DevTools offline); change draft; Retry. Inline error + Retry; last chips remain; Save gated; form untouched; Retry recovers.
result: [pending]

### 5. Narrow layout
expected: Resize viewport ≤900px with a wide categorical table open. About stacks below; table scrolls horizontally inside modal; Cancel/Save remain reachable; page does not grow sideways.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

<!-- Filled if human tests fail — consumed by /gsd-plan-phase --gaps -->
