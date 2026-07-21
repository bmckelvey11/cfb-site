---
phase: 04
slug: filter-popup-modal
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-20
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Run mode: **State B** (no prior SECURITY.md; register reconstructed from the four
PLAN.md `<threat_model>` blocks and their SUMMARY threat flags).
`register_authored_at_plan_time: true` — all four plans carried a threat model, so
this audit **verifies mitigations exist** rather than scanning for new threats.

Per the workflow short-circuit rule (`threats_open: 0` AND
`register_authored_at_plan_time: true` AND `asvs_level == 1`), L1 grep-depth
verification is sufficient and no `gsd-security-auditor` subagent was spawned.

> **Note on severity:** the phase-04 plan tables use the columns
> `Threat ID | Category | Component | Disposition | Mitigation Plan` — they carry no
> severity column. Severities below are assigned at audit time from category and
> blast radius. Because every threat resolved to closed or accepted, `threats_open`
> is 0 under any severity assignment.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser → GET `/api/backtest` | Untrusted query args from the live modal | keys, ops, values, perspectives |
| Browser → GET `/filter-detail` | Untrusted candidate/perspective + form filters | candidate_id, perspective, filter form |
| Browser numeric draft → API | Draft bounds submitted for live recompute | min/max floats, feature keys |
| Server → Browser JSON/HTML | Definitions and labels are untrusted text at render time | descriptions, labels |
| Server row labels → DOM | Categorical values/descriptions rendered by JS | strings |
| Chart points → SVG | Plotted series | server-provided numbers only |
| Async fetch responses → UI state | Out-of-order responses must not commit | response generation identity |
| Edit metadata → modal open | Reopened filter identity | server-authored allowlisted candidate_id |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering | `/api/backtest` args | high | mitigate | Strict allowlist parse; unknown keys/ops/perspectives rejected with 400 before compute (D-18). Verified: 5 rejection sites in `web.py` | closed |
| T-04-02 | Tampering | Client metrics | medium | mitigate | Browser never computes Record/ROI/Money, only renders server JSON (D-15). Verified: 0 metric arithmetic in `filter_modal.js` (format-only) | closed |
| T-04-03 | Information Disclosure / XSS | About Filter / chip labels | high | mitigate | Plain-text definitions; Jinja auto-escape; DOM `textContent` (D-19). Verified: 52 `textContent` uses | closed |
| T-04-04 | Denial of Service | `/api/backtest` | medium | mitigate | `run_backtest_summary` skips permutation/stats; no N×full backtests. Verified present | closed |
| T-04-05 | Tampering | GET handlers | low | **accept** | Endpoints read-only; no storage writes (phase boundary) | accepted |
| T-04-06 | Tampering | candidate_id / perspective | high | mitigate | Resolved only via `CORE_FILTER_META` / `FEATURE_BY_KEY`, else 400 (D-18). Verified: 13 resolution sites | closed |
| T-04-07 | XSS | Table Description cells | high | mitigate | Rows built with DOM APIs + `textContent`; untrusted HTML never assigned to `innerHTML` (D-19). Verified: **0** non-empty `innerHTML` assignments | closed |
| T-04-08 | Denial of Service | `/filter-detail` | medium | mitigate | One-pass aggregation; no per-value `run_backtest` loops. Verified: all 4 `run_backtest` call sites are main/holdout paths, none in a loop | closed |
| T-04-09 | Tampering | Distribution conditioning | medium | mitigate | `remove_candidate_filters` clears the full candidate representation before matching (D-08). Verified present | closed |
| T-04-10 | Tampering | Numeric bounds | medium | mitigate | Server rejects non-finite / reversed bounds on Save and API parse (D-06, D-18). Verified present | closed |
| T-04-11 | Denial of Service | High-cardinality numeric domains | medium | mitigate | One-pass aggregation; `chart_points` capped at 60; metrics stay server-authoritative (D-09). Verified present | closed |
| T-04-12 | Tampering | Spread sign | medium | mitigate | Reuses `_side_spread` only; never plots raw home spread for side-aware systems. Verified present | closed |
| T-04-13 | Tampering | Stale fetch race | medium | mitigate | `AbortController` + generation identity checked before render / enabling Save (D-16/D-17). Verified present | closed |
| T-04-14 | Tampering | Failed live request | medium | mitigate | Error+Retry path never mutates `filters-form`; Save gated on successful validation (D-17). Verified statically (all `filtersForm` uses are reads; no `.submit()`) **and empirically** in UAT Test 4 — form and URL byte-identical through a forced outage, Save disabled while errored | closed |
| T-04-15 | Elevation / XSS | Edit aria-labels / sentence text | high | mitigate | Jinja auto-escape on aria-label and sentence text; no `\|safe`. Verified: **0** `\|safe` filters in `index.html` | closed |
| T-04-16 | Spoofing | Edit `candidate_id` attributes | high | mitigate | Open path still resolves ids through server allowlists on `/filter-detail` and `/api/backtest`. Covered by the T-04-06 resolution sites | closed |
| T-04-SC | Tampering (supply chain) | pip installs | low | **accept** | No new packages this phase. Verified: `requirements.txt` last modified by baseline `7ae6224`; phase-04 commits touched only source + planning docs | accepted |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-04-01 | T-04-05 | Phase-04 endpoints (`/api/backtest`, `/filter-detail`) are read-only GET handlers performing no storage writes. Tampering with query args can only affect the caller's own computed view, never persisted state. Revisit if a write endpoint is added to this surface. | bmckelvey11 | 2026-07-20 |
| R-04-02 | T-04-SC | No dependencies were added, removed, or upgraded during phase 04, so no supply-chain review was warranted. Verified against git history rather than asserted. | bmckelvey11 | 2026-07-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-20 | 17 | 15 | 0 (2 accepted) | /gsd-secure-phase (L1 short-circuit, no auditor subagent) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-20
