---
phase: "05"
slug: dashboard-current-matches
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
threats_total: 29
threats_closed: 26
threats_accepted: 3
threats_open: 0
status: verified
audited: 2026-07-20
---

# Phase 5 — Security Audit

**Verdict: SECURED.** 26/29 threats mitigated + 3 accepted (29/29 dispositioned). `threats_open: 0`.

Run mode: State B — no prior SECURITY.md; register reconstructed from the six PLAN.md `<threat_model>` blocks (every plan carried one). All verification was performed against implemented code (grep / read / git), not plan or summary claims. `block_on: high` — only OPEN threats of severity ≥ high count toward the blocking gate.

## High severity (blocking gate) — all CLOSED

| Threat | Category | Disposition | Evidence (verified in code) |
|--------|----------|-------------|------------------------------|
| T-05-01 | Info Disclosure | mitigate | `upcoming.py:59,75` token → `Configuration(access_token=…)` only; `cli.py:85-97` prints meta fields only; meta dict carries no token |
| T-05-05 | Tampering | mitigate | Upcoming writers target `processed/upcoming.csv`, `upcoming_meta.json`, `raw/*.json`; no `processed/games.csv` write in the upcoming path |
| T-05-06 | Tampering | mitigate | `grade_bet`/`_grade_total_bet` still raise `ValueError` on null scores; no `require_played` added to any grading fn |
| T-05-07 | Tampering | mitigate | `matches_system` gains `*, require_played: bool = True` (`backtest.py:246`); guard `if require_played and (...)`; existing call sites unedited |
| T-05-09 | XSS | mitigate | `dashboard.html`: 0 `\|safe`, 0 autoescape-disable, 0 `<script>`; Flask default autoescape on |
| T-05-10 | Tampering | mitigate | `web.py:404` tab ∈ {mine, examples}; `_normalize_timeframe` → `'all'` or int-in-`seasons`; never concatenated into a path |
| T-05-14 | Tampering | mitigate | `save_features_to(path,…)` explicit path; upcoming writes `upcoming_features_path`; `enrich_games` returns a dict, performs no write |
| T-05-15 | Lookahead | mitigate | `running_stats.py` byte-unchanged (git diff empty); `_accumulation_base` excludes target ids; snapshot-before-accumulate reused |
| T-05-16 | Tampering | mitigate | No fallback/default/placeholder logic in `enrich_upcoming`/`_accumulation_base`; null fails closed |
| T-05-18 | Path Traversal | mitigate | `_safe_system_name` regex `^[A-Za-z0-9_-]+$` rejects `.` `/` `\`; applied in **both** `load_example_system` and `save_system` (loader + copy destination) |
| T-05-19 | XSS | mitigate | `dashboard.html`: 0 `\|safe` / 0 autoescape-disable (example name + theory) |
| T-05-23 | Tampering | mitigate | `_play_text` applies same normalization as grading (fade inversion + `_side_spread` away flip) |
| T-05-24 | XSS | mitigate | `dashboard.html`: 0 `\|safe` / 0 autoescape-disable (system name, team name, `describe()` sentences) |
| T-05-25 | DoS | mitigate | Panel reads wrapped in try/except → `{"state":"missing"}`; features read wrapped |
| T-05-27 | Tampering | mitigate | `_current_matches_panel` calls `matches_system(..., require_played=False)` only; no filter logic reimplemented; `grade_bet` absent from panel path |

## Medium severity (non-blocking) — all CLOSED

| Threat | Category | Evidence |
|--------|----------|----------|
| T-05-02 | Tampering | Numeric fields flow through `normalize_games`; no raw writes |
| T-05-03 | DoS | Fallback bounded `_MAX_SEASONS_BACK=2`; no-target branch writes empty meta and returns |
| T-05-08 | Tampering | One `matches_system`, one flag; no second matcher |
| T-05-11 | Info Disclosure | Redirect target fixed `/system`, never user-supplied — cannot become open redirect |
| T-05-12 | DoS | One all-time `run_backtest` per system, cached; per-season derived, not re-run |
| T-05-13 | DoS | `FileNotFoundError` → `missing_data` render |
| T-05-20 | Tampering | Copy reads package dir, writes only `DATA_DIR` via `save_system` |
| T-05-21 | Spoofing | Tab note "…not betting recommendations" |
| T-05-22 | DoS | `_example_rows` skips unparseable files |
| T-05-26 | Info Disclosure | `web.py` imports no fetch/cfbd_client/scrapers/graphql module; panel is file-reads only |
| T-05-28 | Spoofing | Fetch timestamp + fallback label emitted; line-movement caveat in template |

## Low severity — ACCEPTED

| Risk | Threat | Rationale | Accepted By | Date |
|------|--------|-----------|-------------|------|
| R-05-01 | T-05-04 | Single-user local tool; `--data-dir` is operator-controlled, no new exposure beyond existing CLI commands | bmckelvey11 | 2026-07-20 |
| R-05-02 | T-05-17 | Full-season upcoming enrichment is CLI-only, one season, bounded — never in a request path | bmckelvey11 | 2026-07-20 |
| R-05-03 | T-05-SC | No packages added/removed/upgraded; `requirements.txt` byte-unchanged across the phase-05 commit range (git) | bmckelvey11 | 2026-07-20 |

## Unregistered flags

None. All six SUMMARYs report no new threat surface beyond the register.

**threats_open: 0 — phase clear to ship.**
