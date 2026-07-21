# Milestones

## v1.0 Bet Labs Parity (Shipped: 2026-07-20)

**Phases completed:** 5 phases, 21 plans, 29 tasks
**Timeline:** 2026-07-16 → 2026-07-20 (4 days, 193 commits)
**Codebase:** ~11k Python LOC; 307 tests passing
**Closeout:** override_closeout — all requirements code-verified; two live-in-season verification checks deferred to season start (see STATE.md Deferred Items)

**Delivered:** The `cfb_system_maker` web UI now reads and behaves like Sports Insights Bet Labs — a stat-chip system editor with a money-won graph and plain-English filters, live filter-popup exploration, and a My Systems dashboard that evaluates saved systems against upcoming games.

**Key accomplishments (by phase):**

- **Phase 1 — System Editor Main Page:** Replaced the plain metrics row with a Bet Labs-style stat-chip header (Record / Margin / Money Won / ROI / Grade), a chronological "Money Won Over Time" SVG chart, Results Graph / Past Matches tabs, plain-English active-filter sentences via a pure `describe()` function, and a persisted free-text `theory` field.
- **Phase 2 — Integrity (Fade & Grade):** A Fade toggle that flips the graded side without changing which games match, and a composite A–F System Grade combining Wilson sample-size significance, ROI z-score, season sign-consistency, permutation p-value, and an overfit penalty.
- **Phase 3 — Data Depth & Breadth:** Confirmed the 2013 CFBD betting-line floor against the live API, and wired new entering-game features (Off/Def Success Rate, Off/Def Explosiveness, prior-season offensive wEPA) into the registry under the existing no-lookahead convention.
- **Phase 4 — Filter Popup Modal:** Every filter opens a live-recalculating popup — dual-handle numeric ranges with a money chart, searchable/sortable categorical value tables, About-Filter text, and Edit-from-sentence — committing through the existing query-string GET flow with a 250ms debounced live path.
- **Phase 5 — Dashboard & Current Matches:** A My Systems dashboard at `/` (editor moved to `/system`) with per-season figures cached from one all-time backtest and sparklines; three bundled read-only example systems on their own tab; a new `upcoming` CLI pipeline; and a Current Matches panel that matches saved systems against upcoming games (matching without grading) with fade-correct play text and reused `describe()` filter details.

**Descoped:** DASH-04 (teaser / alternate-line records) — deferred out of v1.0 on 2026-07-20 during Phase 5 discussion; partial decisions preserved in the Phase 5 context archive.

---
