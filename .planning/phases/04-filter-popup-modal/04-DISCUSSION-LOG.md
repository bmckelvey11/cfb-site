# Phase 4: Filter Popup Modal - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 4-filter-popup-modal
**Areas discussed:** Modal launch and commit lifecycle, Numeric range exploration, Categorical and boolean selection, Live feedback and accessibility

---

## Modal launch and commit lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| All filtering constraints | Registry features and core filtering constraints use the modal; global system controls remain inline | ✓ |
| Registry features only | Replace only current feature `<details>` controls | |
| Numeric filters only | Keep categorical/core controls unchanged | |

**User's choice:** Delegated to Claude unless a dire issue required intervention.
**Notes:** Selected the complete filtering workflow because the roadmap says configuring any filter opens the popup. Kept bet type, side, position, Fade, theory, run, load, and save as global editor controls.

| Option | Description | Selected |
|--------|-------------|----------|
| Draft then explicit Save | Cancel discards; Save writes canonical form controls and submits | ✓ |
| Immediate application | Every modal movement mutates the current system | |
| Save without rerunning | Close modal but leave main results stale | |

**User's choice:** Delegated to Claude.
**Notes:** Explicit draft state best matches MODAL-06 and prevents exploratory changes from leaking into the committed system.

---

## Numeric range exploration

| Option | Description | Selected |
|--------|-------------|----------|
| Dual-handle range plus chart/table | Synchronized BETWEEN controls, per-value chart, optional list view | ✓ |
| Number inputs only | No direct-manipulation slider or distribution view | |
| Single threshold | Preserve only current ≥/≤ interaction | |

**User's choice:** Delegated to Claude.
**Notes:** Chosen to match the canonical Bet Labs modal and MODAL-03. Exact values remain authoritative even when display points are downsampled.

---

## Categorical and boolean selection

| Option | Description | Selected |
|--------|-------------|----------|
| Searchable sortable checkbox table | Multi-select values with Description/Record/ROI/Money | ✓ |
| Plain select | Compact but hides per-value evidence and multi-select exploration | |
| Free-text comma list | Current implementation; error-prone and not discoverable | |

**User's choice:** Delegated to Claude.
**Notes:** Categorical values use existing `in` semantics. Boolean values share the table language but permit one Yes/No selection.

---

## Live feedback, failure states, and accessibility

| Option | Description | Selected |
|--------|-------------|----------|
| Debounced cancellable fetch | Preserve prior successful data, ignore stale responses, inline retry | ✓ |
| Fetch every input event | Simpler but creates avoidable work and response-order races | |
| Recalculate on Save only | Fails the live-before-commit requirement | |

**User's choice:** Delegated to Claude.
**Notes:** The main backtest/grading path remains authoritative; the client displays server results and never computes betting performance independently.

| Option | Description | Selected |
|--------|-------------|----------|
| Accessible dialog with progressive enhancement | Focus management, keyboard operation, responsive stacking, no-JS fallback | ✓ |
| Custom div overlay | More manual focus and keyboard work | |
| Desktop-only modal | Does not preserve the existing responsive baseline | |

**User's choice:** Delegated to Claude.
**Notes:** No frontend framework or chart library is introduced.

---

## Claude's Discretion

- The user explicitly requested judgment without follow-up questions unless a dire issue appeared.
- Exact dimensions, spacing, animation, loading indicator, JSON field names, helper boundaries, and chart point density remain implementation discretion.

## Deferred Ideas

- Grade sub-score breakdown.
- Dashboard, Current Matches, bundled examples, and teaser records.
- Moneyline wager support, public betting percentages, Think Tank, and duplicate-side handling.
