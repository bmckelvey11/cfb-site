# Phase 2: Integrity — Fade & Grade - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 2-Integrity — Fade & Grade
**Areas discussed:** Grade formula weighting, Fade toggle scope/UX, Overfitting penalty inputs, Grade chip interaction

---

## Grade formula weighting

**User's choice:** "You figure out a way. I am not too pressed about having a letter grade."
**Notes:** Delegated the exact combination rule and output format (letter grade vs score vs label) to Claude's discretion. Must remain a documented, testable pure function over existing `SystemStats`/`BacktestResult` fields (z-score, permutation p-value, Wilson interval, sign-consistency, overfitting penalty).

---

## Fade toggle scope/UX

| Option | Description | Selected |
|--------|-------------|----------|
| Editor page toggle, persists to saved system | Checkbox/toggle on system editor page near stat chips. Flips graded side (home↔away for spread, over↔under for total). Saves to SavedSystem JSON, survives reload. | ✓ |
| Spread systems only for now | Same but only wire fade for bet_type=spread; total fade deferred. | |

**User's choice:** Editor page toggle, persists to saved system (applies to both spread and total).

---

## Overfitting penalty inputs

| Option | Description | Selected |
|--------|-------------|----------|
| Simple count: populated fields + set sizes | Each populated SystemFilter field = 1 filter; each element inside a set (teams, conferences, seasons, in-list feature_filters) counts individually. | ✓ |
| Just count active filter categories | Only count distinct filter types active, ignore in-list value counts. | |

**User's choice:** Simple count: populated fields + set sizes.

---

## Grade chip interaction

| Option | Description | Selected |
|--------|-------------|----------|
| Header letter/score only, breakdown deferred | Phase 2 computes + shows the single composite value in the Grade chip. No hover/click breakdown panel yet. | ✓ |
| Add hover/click breakdown of sub-scores now | Build the Bet Labs-style panel showing each of the 5 sub-scores with their own letter. | |

**User's choice:** Header letter/score only, breakdown deferred.

---

## Claude's Discretion

- Exact grade formula/thresholds and output format (letter vs score vs label), and the combination rule across the 5 sub-score inputs.
- Exact wording/styling of the Fade toggle control, consistent with existing vanilla JS/CSS stat-chip header from Phase 1.

## Deferred Ideas

- Grade breakdown/sub-score panel (Bet Labs-style, each sub-score its own letter rolling up to header) — future phase, likely alongside filter popup modal work.
- Alternate-line ("teaser") records — explicitly out of this phase.
