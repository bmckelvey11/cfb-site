# Phase 1: System Editor Main Page - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 1-System Editor Main Page
**Areas discussed:** Tabs implementation, Theory field save flow (user selected these two of four presented; Money-graph x-axis and Grade chip placeholder deferred to Claude's discretion per user instruction)

---

## Tabs Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Query-param reload | `?tab=graph` vs `?tab=matches`, full page reload. Matches every other interaction in this app (filters, load system, save all reload via GET/POST). Zero new JS. | ✓ |
| CSS-only, no reload | Radio-input + sibling-selector CSS hack to swap panels client-side. Snappier, but a new pattern not used anywhere else in `index.html` today. | |
| You decide | Let Claude pick based on what's simplest to implement and test. | |

**User's choice:** User dismissed the follow-up AskUserQuestion mid-discussion, then instructed: "unless it is a crucial thing about design then go with your recommendations." Claude proceeded with the recommended option (query-param reload).
**Notes:** Not a crucial/ambiguous design fork — recommended option directly matches the existing GET-form architecture used everywhere else in the app.

---

## Theory Field Save Flow

**User's choice:** Not asked as a separate AskUserQuestion — resolved via the same "go with your recommendations" instruction. Claude chose to bundle the theory textarea into the existing main filter form, saved via the existing `POST /save` endpoint (per `docs/bet-labs-parity-plan.md`'s stated approach), rather than adding a new quick-save endpoint.
**Notes:** Matches the design doc's explicit guidance; no new route needed.

---

## Claude's Discretion

- **Money-graph x-axis** — user did not select this area for discussion. `GameRecord` has no per-game date field (only `season`/`week` ints), so the design doc's "x = date" isn't literally implementable today. Claude will use chronological bet order sorted by `(season, week)` as the x-axis.
- **Grade chip placeholder** — user did not select this area for discussion. Claude will render a neutral placeholder ("—") in the Grade chip slot until Phase 2 computes the real value.

## Deferred Ideas

None raised during this discussion.
