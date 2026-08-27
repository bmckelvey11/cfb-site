# Requirements: v1.1 Season Readiness

Source: `docs/roadmap-v2-2026-08.md` §2, refined via research (`.planning/research/SUMMARY.md`)
and scoping conversation on 2026-08-26.

## v1.1 Requirements

### Merge & Integration

- [x] **MERGE-01**: `fix/web-app-review-2026-08-26` (26 commits) is merged to `master` with all 435 tests passing. — done 2026-08-26 (commit `2e86ba5`, 441 tests passing)
- [x] **MERGE-02**: Any `SearchRun`/`SearchRunFinalist` JSON persisted in `data/search_runs/` under pre-merge matching semantics is audited and, if stale, regenerated or flagged — so a beam-search result never silently disagrees with the post-merge matching behavior. — done 2026-08-26 (audited: directory empty, no-op)

### Integrity Fixes

- [x] **FIX-01**: `describe()` renders a fallback sentence for any active filter whose `(op, control)` combination isn't covered by an existing branch, so no active filter is ever silently missing from the displayed filter list (closes T-01-03). Fallback preserves a working remove-link and is verified on both the system editor and the Current Matches dashboard panel (both surfaces reuse `describe()`).
- [ ] **FIX-02**: `aggregate_filter_value_rows` (backs `GET /filter-detail`) no longer double-counts a bet across multiple value buckets for total-system team/conference filters — per-value Record/ROI/Money in the modal table reconciles with the top-line backtest result.
- [x] **FIX-03**: The original "Hide Duplicates" deferral is closed in `PROJECT.md` as architecturally not applicable — `run_backtest` is verified 1:1 on `game_id` (no top-line double-counting exists to toggle away); the real bug addressed instead is FIX-02.

### Data & Verification

- [ ] **DATA-01**: A 4th bundled example system ("Neutral-Site & Indoor Unders") ships on the Example Systems tab, using existing registry features (`neutralSite`, `gameIndoors`, `venue_dome`). Its `theory` field discloses the sample size and significance (n=109, p=0.014) so the example doesn't read as a stronger claim than the underlying analysis supports.
- [ ] **DATA-02**: Current Matches is confirmed against the live 2026 season to show real unplayed games with posted lines, and feature-filtered systems are confirmed to match those games via season-to-date stats. A pre-season dry run checks whether the live CFBD calendar API returns `startDate`/`endDate` as `str` (untested path — historical fixtures only exercised `datetime` objects). Scheduled for week 3+ of the season, not week 1 (season-to-date accumulators are `games_played=0` and fail closed in week 1 by design — a week-1 empty result is not a bug).

## Future Requirements (deferred out of v1.1)

- Alternate-line ("teaser") record popover off the Record chip (DASH-04) — remains descoped from v1.0, unscheduled.
- CLV tracking & bet-log ingestion, finance-grade result metrics, weekly-loop alerts/line-shopping, and differentiators (system-as-text, NL theory input, moneyline) — see `docs/roadmap-v2-2026-08.md` §§3-6 (v1.2-v1.5).

## Out of Scope

- **Hide Duplicates as originally specified** (a toggle inside `run_backtest`/`SystemFilter` to drop games producing two candidate bets) — architecture research (3 independent findings) confirmed `run_backtest` is structurally 1:1 on `game_id`; there is no top-line duplication to toggle away. Superseded by FIX-02/FIX-03.
- **Scheduled/recurring live verification** (cron, APScheduler, Celery) for DATA-02 — a one-time manual `upcoming` CLI run at season start is sufficient; no recurring job is warranted this milestone.
- **New CFBD dependency or data pull** for DATA-01 — all three required features (`neutralSite`, `gameIndoors`, `venue_dome`) already exist in `FEATURE_REGISTRY`.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MERGE-01 | Phase 6 | Complete |
| MERGE-02 | Phase 6 | Complete |
| FIX-01 | Phase 7 | Complete |
| FIX-02 | Phase 7 | Pending |
| FIX-03 | Phase 7 | Complete |
| DATA-01 | Phase 8 | Pending |
| DATA-02 | Phase 9 | Pending |
