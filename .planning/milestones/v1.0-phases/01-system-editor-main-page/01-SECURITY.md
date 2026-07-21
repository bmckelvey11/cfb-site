---
phase: 01
slug: system-editor-main-page
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-17
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Free-text theory input -> stored JSON -> re-rendered HTML | User-supplied `theory` text persists to disk (saved system JSON) and is re-rendered on every subsequent page load for that saved system — the canonical stored-XSS surface introduced in this phase. | Free text, unbounded length, re-rendered in HTML |
| Query string -> href construction | `_query_href()` (01-02) and `_query_href_removing()` (01-04) build every tab/remove-filter href from `request.args` / a `MultiDict` copy. Crafted query params (e.g. `?tab=<script>`) must never be reflected unescaped into an href attribute. | Query-string values, arbitrary |
| describe() sentence-text vs. matches_system()/feature_ok() actual filter semantics | The plain-English active-filter list (01-03/01-04) is a *display* derived from `SystemFilter`, not the source of truth used for grading — a mismatch between what's shown and what's applied is an integrity/information-disclosure risk, not a rendering risk. | In-process `SystemFilter`/`FeatureFilter` data, no external I/O |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-01-01 | Tampering / Information Disclosure | Theory textarea (sidebar) + `.theory-panel` (workspace) in `templates/index.html` | high | mitigate | Both render locations use bare Jinja `{{ form.theory }}`, relying on Flask/Jinja2's default auto-escaping. Verified: no `\|safe` anywhere in `templates/index.html`, no `{% autoescape false %}`. | closed |
| T-01-02 | Tampering | `_query_href()` / `_query_href_removing()` in `web.py`; tab nav + remove-filter links in `templates/index.html` | high | mitigate | Both helpers build hrefs exclusively via `urllib.parse.urlencode(list(copy.items(multi=True)))` over a `MultiDict` copy — values are always percent-encoded, never string-interpolated raw. Verified by direct code read of both functions (`web.py:212`, `web.py:267`). | closed |
| T-01-03 | Tampering / Information Disclosure | `describe()` in `cfb_system_maker/describe.py` vs. `feature_ok()`/`_value_matches()` in `cfb_system_maker/features.py` | high | accept | Confirmed gap: a `feature_filters` entry with a known `key` but an `(op, control)` combination outside describe()'s four hardcoded branches (`eq`+bool, `eq`+categorical, `in`+categorical, `gte`/`lte`+numeric) falls through with `text = None` and is silently omitted from the sentence list — unremovable via the UI — while `_value_matches()` still applies it during grading since it branches on `op` alone, not `feature.control`. Reachable via crafted query string (`_feature_filters_from_request()` parses arbitrary op/value pairs), not through normal form UI which only emits valid op/control pairings. Same code-smell as the T-01 code-review finding for unknown *keys* (already mitigated), but for unknown *(op,control) combos on known keys* — not previously distinguished in 01-03's threat model. Accepted as documented risk rather than fixed now: low practical exploitability (requires hand-crafting query params; no data exfiltration or execution, only a display/removal-affordance gap) against effort of extending describe()'s branch coverage. | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on (high) count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01-01 | T-01-03 | describe() can silently drop and make unremovable a known-key feature filter whose (op, control) combo isn't one of its four rendered cases (still applied during grading). Requires crafted query params to trigger; display/removal-affordance gap only, no data exposure or execution. Also flagged in 01-REVIEW.md (Warning). Fix deferred — extend describe()'s branch coverage or add a generic fallback sentence in a future pass. | user (bmckelvey11) | 2026-07-17 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-17 | 3 | 3 | 0 | claude (orchestrator, L1 grep-depth, no auditor subagent spawned — user accepted the one open finding directly) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-17
