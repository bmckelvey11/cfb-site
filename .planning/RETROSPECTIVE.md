# Retrospective — Bet Labs Parity for cfb-site

Living document. One section per milestone, newest first, followed by cross-milestone trends.

## Milestone: v1.0 — Bet Labs Parity

**Shipped:** 2026-07-20
**Phases:** 5 | **Plans:** 21 | **Tasks:** 29 | **Commits:** 193 | **Timeline:** 4 days (2026-07-16 → 2026-07-20)
**Tests:** grew across the milestone to 307 passing at close.

### What Was Built

A backtesting research tool became a weekly-use product. The web UI now reads like Sports Insights Bet Labs: a stat-chip system editor with a money-won graph and plain-English filter sentences (Phase 1), a fade toggle and composite A–F trust grade (Phase 2), deeper entering-game features on confirmed data (Phase 3), a live-recalculating filter popup replacing inline editing (Phase 4), and a My Systems dashboard that evaluates saved systems against upcoming games via a brand-new `upcoming` pipeline (Phase 5).

### What Worked

- **Wave-based parallel execution on disjoint file sets.** Phase 5's Wave 1 ran three executors concurrently (`upcoming.py`/`storage.py`/`cli.py` vs `backtest.py` vs `web.py`/templates) with zero merge conflicts because the file ownership was verified disjoint before dispatch. Wall-clock roughly a third of sequential.
- **Verify by running the real thing, not the fakes.** The single most valuable pattern of the milestone. Every phase-5 executor that ran the actual CLI/page (not just its test doubles) caught a bug the fakes structurally could not: the CFBD `SeasonType` enum stringifying to `SeasonType.POSTSEASON`; the example system that matched zero games in the resolved week; the season-to-date accumulation base coming back empty.
- **Extending the one authoritative path instead of forking it.** `matches_system(require_played=False)` (D-18) let Current Matches match unplayed games without a second matcher and without touching the grading path — preserving the Phase 4 single-grading-path invariant rather than fighting it.
- **Decisions recorded at the moment they were made.** Post-research decisions (D-18..D-21) went into the context doc immediately, so the planner, executors, verifier, and security auditor all saw the same locked set. No decision had to be re-derived.
- **Honest closeout.** Phase 5 verification was `human_needed` (two live-in-season checks that can't run in July), and the milestone closed as `override_closeout` with those checks recorded as deferred rather than rubber-stamped as passed.

### What Was Inefficient

- **Concurrent writers to STATE.md.** Every parallel executor hit `state.advance-plan` parse failures because three agents can't safely increment a shared plan counter. Each correctly declined to hand-edit, but it meant the orchestrator reconciled counters by hand after every wave. A per-plan state file or a lock would remove the manual step.
- **Premature requirement completion in frontmatter.** Executors marked DASH-01/DASH-03 complete in their plan frontmatter, but those requirements were only delivered by later plans. The status flipped to `[x]` twice before the work actually existed, and had to be reverted twice. Requirement completion should come from phase verification, not per-plan frontmatter.
- **One executor died mid-stream to an API stall.** Cost a full restart of plan 05-06. The recovery was clean (confirmed nothing had committed, restarted fresh rather than resuming a corrupted context), but the compute was spent twice.
- **A plan that contradicted itself.** 05-04's prose said "reuse `enrich_games` with the upcoming records," which — followed literally — reproduced the exact null-feature bug the plan existed to prevent. The executor caught it, but a plan-check that traced the load path would have caught it earlier.

### Patterns Established

- **Separate file over schema migration.** Upcoming games got their own `upcoming.csv` rather than a `games.csv` column, keeping the `GameRecord` CSV contract intact and making it structurally impossible to grade an unplayed game (D-01).
- **"A correct filter that renders empty is still a bug."** Seen twice: the SeasonType enum and the neutral-site example. A feature/filter can be correct in principle (right field, no lookahead) and still show nothing in the exact window it ships in. Always check against the *resolved/live* data, not all-history.
- **Fade is the inversion case for any derived display.** Play text, like grading, must run the same side/over-under normalization including fade inversion — deriving from the declared `side` alone produces a factually wrong bet on a page telling the user what to bet (D-08).
- **Descope is a roadmap edit, not a silent drop.** DASH-04 (teasers) was removed from ROADMAP.md, REQUIREMENTS.md, and the coverage counts, with partial decisions preserved — so verification couldn't later fail on a criterion nobody intended to deliver.

### Key Lessons

1. Run the real command/page before declaring a data-touching change done — the fakes agree with the code, not with reality.
2. Verify wave file-sets are disjoint *before* dispatch; it's what makes parallelism free of conflicts.
3. Let phase verification own requirement status; per-plan frontmatter is too early and flips prematurely.
4. When a decision emerges from research, write it into the locked context immediately so every downstream agent shares it.

### Cost Observations

- Model mix: Opus throughout (planner, executors, verifier, security auditor, orchestrator) — no tier mixing this milestone.
- One API stall forced a full re-execution of one plan (05-06).
- Wave parallelism (3 concurrent executors) was the main wall-clock saver; the offsetting cost was manual state-counter reconciliation after each wave.

---

## Cross-Milestone Trends

*(v1.0 is the first milestone; trends populate from v1.1 onward.)*

| Milestone | Phases | Plans | Tests at close | Notable |
|-----------|--------|-------|----------------|---------|
| v1.0 Bet Labs Parity | 5 | 21 | 307 | Wave-parallel execution; run-the-real-thing verification |
