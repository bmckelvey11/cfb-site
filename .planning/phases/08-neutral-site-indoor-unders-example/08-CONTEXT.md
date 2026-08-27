# Phase 8: Neutral-Site & Indoor Unders Example - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A user browsing the Example Systems tab can copy a 4th bundled system built on the neutral-site/indoor-unders finding, with its statistical strength disclosed honestly rather than overstated. Requirement: DATA-01.

The 3 required registry features (`neutralSite`, `gameIndoors`, `venue_dome`) all already exist as `bool`, `game_id`-perspective features in `FEATURE_REGISTRY` — no new data pull, no code changes to the registry or scraper.

</domain>

<decisions>
## Implementation Decisions

### Theory Field Wording
- Prose hypothesis style matching the existing 3 examples, with the sample size/significance woven into the prose (not a separate stats block, not stats-first/terse).
- Must state the real numbers from the source analysis (`docs/under-team-stats-analysis.md`): 69-40 record, 63.30% ATS, +20.85% ROI, n=109, p=0.014.
- Should reflect the analysis doc's own honesty caveats: consistent across the season (wk1 63.3%, wk2-13 63.6%, wk14+ 63.0%) and across eras (2013-2019 58.5%, 2020-2025 67.9%) — not a bowl-game artifact — but p=0.014 does not survive Bonferroni correction across the ~25 tests run in the broader analysis project, and 109 games is a small sample. The doc's own framing: "best available lead, not a proven edge."
- Do not overstate: this is the strongest lead found in a multi-angle statistical scan, not a validated system.

### Zero-Match Live Weeks
- Out of scope for this phase. Neutral-site indoor games are seasonally rare/clustered (Week 0/1 kickoff classics, conference championships, bowl season) and `gameIndoors` sources from the sometimes-gated `weather` endpoint — a normal mid-season week showing 0 Current Matches for this example is expected, correct behavior, not a bug requiring special UI treatment.
- The existing Current Matches empty state (used by all saved systems with 0 matches in a given week) is sufficient. No new empty-state design, no code changes beyond the bundled JSON example itself.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cfb_system_maker/examples/*.json` — 3 existing bundled example systems (`nonconference-away-dogs.json`, `spread-home-favorites.json`, `total-unders-high-lines.json`). Adding a 4th is a pure data addition — read via the same generic directory-scan loader (`storage.list_examples()`/`load_example_system()`) that already handles the 3 existing files. No code changes needed for loading/rendering/Copy-to-My-Systems.
- `cfb_system_maker/examples/nonconference-away-dogs.json` — exact template for a boolean `feature_filters` entry: `{"key": "conferenceGame", "op": "eq", "perspective": "single", "value": false}`. The new example needs 3 such entries (`neutralSite`, `gameIndoors`, `venue_dome`, all `op: "eq"`, `perspective: "single"`, `value: true`).
- `docs/under-team-stats-analysis.md:78-101` — source of the exact numbers and honesty caveats to draw the theory text from.

### Established Patterns
- Example JSON shape: `name`, `saved_at` (ISO timestamp), `system` (full `SavedSystem`-shaped dict with all fields, most null/empty/false except the ones the example actually filters on), `theory` (free-text prose).
- `total_side: "under"`, `bet_type: "total"` for a totals system (matches the target bet type here — this is an unders system).

### Integration Points
- `cfb_system_maker/examples/` — new file goes here, e.g. `neutral-site-indoor-unders.json`.
- Example Systems tab (dashboard) — auto-discovers files in this directory, no template/route changes needed per Phase 5's existing generic loader.

</code_context>

<specifics>
## Specific Ideas

Exact theory wording is left to the planner/executor, within the constraints above (prose style, real numbers, honesty caveats). No other UI wording was specified.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
