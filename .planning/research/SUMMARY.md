# Project Research Summary

**Project:** cfb_system_maker v1.1 "Season Readiness"
**Domain:** Brownfield Python/Flask betting-system backtester -- closeout of 5 deferred v1.0 items ahead of 2026-08-29 season start
**Researched:** 2026-08-26
**Confidence:** HIGH

## Executive Summary

This is a milestone-closeout research pass, not a greenfield build: all 4 researchers independently confirm no new dependencies, frameworks, or architectural layers are needed. Four of the five milestone items (merge the review branch, live-verify Current Matches, fix the describe() fallback gap, add a 4th bundled example) are low-risk, well-scoped, and buildable with existing patterns already in the codebase (storage.py's backward-compatible JSON parser, the ff:{key} sentence/remove-link convention, the generic examples-directory loader). The main engineering risk is sequencing -- the review branch (fix/web-app-review-2026-08-26) touches the same files (backtest.py, features.py, storage.py, web.py) that items 3-5 need to edit, so it must merge first or items 3-5 must be built on top of it and merged together.

The fifth item, "Hide Duplicates," is where research earns its keep: the milestone's own premise -- that a total system can now produce two candidate bets for one game_id -- is EMPIRICALLY FALSE against this codebase. run_backtest iterates games once and calls matches_system once per game; games.csv has exactly one row per distinct game_id (12,964/12,964), same for upcoming.csv (50/50). There is no code path that emits two bets for one game. All three researchers (Features, Architecture, Pitfalls) converged independently on the same real bug: aggregate_filter_value_rows in web.py, which backs the /filter-detail modal, fans a total system's either-perspective team/conference tuple return into multiple value buckets, each holding the same BetDetail -- inflating the modal's per-value Record/ROI/Money table to roughly double the true matched count. This is a real, narrow display bug, but it is not what the milestone item as named ("Hide Duplicates toggle for run_backtest") describes, and building a toggle wired to run_backtest/matches_system would be a no-op checkbox with zero observable effect on the Record/Money/ROI stat chips.

Recommended approach: treat items 1, 2, 4, 5 as directly buildable per their existing scoping, sequenced with the merge first, describe() fallback second (smallest surface, de-risks item 5's feature rendering), the new example third, and live verification running in parallel/after (gated on the real 2026-08-29 calendar). Item 3 needs a roadmap-level scope correction before any phase plan is written -- see Implications for Roadmap below. Key non-obvious risk found only by Pitfalls research: SearchRun/SearchRunFinalist JSON persisted under old total-system matching semantics will NOT self-correct on merge (no fingerprint on matching-logic version) and needs an explicit re-backtest/diff pass.

## Key Findings

### Recommended Stack

No new dependencies for any of the 5 items -- Python 3.14.6, Flask 3.1.3, and stdlib (dataclasses, set, dict, json) cover everything, using patterns already established elsewhere in the codebase (search.py's candidate_identity-based dedup as precedent for any list-level filtering; _system_from_dict's backward-compatible parsing as precedent for schema additions). pandas and any scheduler (APScheduler/Celery/cron) were explicitly considered and rejected as unrequested complexity for a single set-keyed filter and a one-time manual verification pass, respectively. The project's existing injectable-fake pattern (post_fn, cfbd_module) should be reused for any new network-adjacent test rather than introducing responses/vcrpy.

**Core technologies (unchanged):**
- Python 3.14.6 -- existing runtime, nothing in this milestone needs a newer capability
- Flask 3.1.3 -- existing routes/query-param/JSON patterns cover all 5 items
- stdlib dataclasses/set/dict/json -- direct precedent already exists in models.py, search.py, storage.py for every data-shape change this milestone needs

### Expected Features

**Must have (table stakes, all P1, all LOW complexity):**
- Merge fix/web-app-review-2026-08-26 to master -- 26 verified fixes (security, a11y, correctness, perf) currently stranded on a branch
- Live-verify Current Matches once real 2026-08-29 lines post -- a one-time manual check against the already-shipped upcoming pipeline, not new code
- Fix _feature_group_sentence's silent-None fallback (T-01-03) -- an active filter with no visible sentence is a correctness/integrity gap (filter still applies via feature_ok(), just invisible with no remove-link)
- Bundle the neutral-site/indoor unders example system -- all three registry features (neutralSite, gameIndoors, venue_dome) already exist; purely additive JSON file, no code change

**Should have (differentiator, optional, P2):**
- Label the /filter-detail modal's per-value table when bet_type == "total" so its team/conference row sums don't appear to silently disagree with the top-line total (the real referent behind "Hide Duplicates")

**Anti-features (do not build):**
- A literal "Hide Duplicates" checkbox wired into run_backtest/matches_system -- no duplicate rows exist there to hide; the checkbox would have zero observable effect on Record/Money/ROI and would misleadingly imply a data-integrity fix where none applies
- A fallback sentence that echoes raw internal state (op code, control dump) for "debuggability" -- contradicts the product's "reads like Bet Labs" plain-English requirement; keep it human-readable using the feature's existing label
- A new/parallel example-system file schema -- the 3 existing examples already use a uniform, generic loader; any deviation breaks it

### Architecture Approach

The system is a clean four-layer pipeline (web.py routes -> backtest.py matching/grading -> describe.py sentence rendering -> storage.py persistence), and each of the 5 items maps to exactly one or two of these layers with no cross-cutting new component needed. The one architectural nuance: not every new SystemFilter toggle should follow the existing fade pattern (D-03: read only inside grade_bet, never changes matched-count). fade is a value-flip; anything that changes counts (a genuine future dedup toggle) must instead be a list-level post-filter inside run_backtest/run_backtest_summary, operating on the full matched/details list -- grade_bet has no visibility into sibling matched games and structurally cannot detect duplicates alone.

**Major components:**
1. backtest.py (matches_system, grade_bet/_grade_total_bet, run_backtest) -- the single candidate-matching and grading path; confirmed 1:1 on game_id, no duplication possible here
2. describe.py (_feature_group_sentence, describe) -- plain-English sentence rendering; owns the T-01-03 fallback gap, independent of web.py/features.py
3. storage.py (_system_to_dict/_from_dict, list_examples/load_example_system) -- backward-compatible JSON persistence for both saved and bundled-example systems
4. web.py (aggregate_filter_value_rows, resolve_candidate_value, _current_matches_panel) -- where the two genuine duplicate-game_id surfaces actually live (filter-detail modal tuple fan-out; cross-system repeats in Current Matches)

### Critical Pitfalls

1. Milestone premise mismatch -- "Hide Duplicates" as scoped targets a bug that doesn't exist in run_backtest; the roadmapper must explicitly redirect the item before phase planning, not assume the original framing is buildable as-is.
2. Stale SearchRun JSON survives the merge -- persisted search-run stats (data/search_runs/*.json) for old total-bet-type systems with team/conference/perspective filters were computed under pre-fix matching semantics and won't self-correct; needs a one-time re-backtest-and-diff script during the merge phase.
3. /filter-detail double-counts either-perspective total bets -- the actual duplicate-producing bug (aggregate_filter_value_rows tuple fan-out); needs an explicit design decision (is one game meant to count once per matching team/conference value, or should that be suppressed?) before any fix, plus a test asserting per-value row sums equal the true matched count.
4. First live upcoming run has two narrow, non-obvious failure modes -- a possible str vs datetime type mismatch in the live-calendar branch (never exercised against real CFBD data, only fixtures), and week-1 season-to-date filters correctly matching zero games by design (fails closed on null games_played=0) -- both can look like "the pipeline is broken" when they're expected; schedule season-to-date verification for week 3+, dry-run the calendar branch against a live-but-past date before season start.
5. New example system can show "0 games matched" for two independent, non-bug reasons -- gameIndoors sources from the Patreon-gated/sometimes-thin weather endpoint (may be null for the live current week even though populated historically), and neutral-site indoor games are genuinely rare/clustered outside Week 0 and bowl season; the UI needs a calm, deliberate empty state and a live-sidecar null-rate check to distinguish "no signal this week" from "data didn't populate."

## Implications for Roadmap

### Scope correction for Item 3 (read before planning any phase)

Do NOT plan "Hide Duplicates toggle for run_backtest" as scoped in PROJECT.md/the milestone brief. Three independent researchers (Features, Architecture, Pitfalls), using two independent verification methods (direct code reading of matches_system/run_backtest, and empirical row-count checks against games.csv/upcoming.csv), converged on the same finding: run_backtest is structurally 1:1 on game_id and has never produced two candidate bets for one game, with or without the total-filter-either-side fix (d9c93e4). There is nothing for a "Hide Duplicates" checkbox wired to run_backtest to hide -- it would be a no-op that changes nothing in the Record/Money/ROI stat chips it's supposed to affect, and would misrepresent a data-integrity feature as present when it isn't.

The real bug the researchers found lives one layer up, in aggregate_filter_value_rows (web.py, backing the /filter-detail modal's per-value breakdown table) -- for total systems with either-perspective team/conference filters, one game's single BetDetail gets fanned into multiple value buckets (once per team/conference value), so the modal's per-value Record/ROI/Money rows sum to roughly double the system's true matched-game count. The top-line stat chips are unaffected; only the modal's per-value table is wrong.

Present these options to the roadmapper/user rather than silently building either:

- (a) Close item 3 as architecturally N/A. Update PROJECT.md's Out of Scope section: change the Hide Duplicates deferral rationale from "deferred, reachable" to "N/A -- run_backtest is 1:1 on game_id; no per-game duplicate bets exist to hide." This alone requires no code, only a documentation update, and can ship immediately.
- (b) Optionally, separately scope the real fix. A small, independently-named task (not called "Hide Duplicates," to avoid re-promising Bet Labs parity that doesn't map onto this codebase's bet_type model) that either labels the /filter-detail modal's per-value table with a caption/footnote when bet_type == "total" (cheapest: "Totals count each game once per team/conference shown; rows don't sum to the system total"), or fixes the tuple fan-out in aggregate_filter_value_rows itself so per-value sums equal the true matched count. This is a design decision (is fanning into multiple buckets intentional/legitimate, or should it be suppressed?) that needs to be made explicitly, not inferred from the bug.

(a) should happen regardless of whether (b) is pursued. Both are small (LOW-MEDIUM complexity) and independent of items 1/2/4/5.

### Phase 1: Merge review branch + stale-stats audit
Rationale: Hard prerequisite -- items 4/5 (and any pursuit of 3b) edit backtest.py/web.py/storage.py/describe.py-adjacent code the fix branch already modified; building against a pre-merge master would produce a conflicting divergent diff.
Delivers: Master updated with 26 verified fixes; a one-time script that re-backtests every saved system + search run and flags any total-bet-type system with team/conference/perspective filters whose bet count changed under the new matching semantics.
Addresses: Milestone item 1.
Avoids: Pitfall 1 (stale SearchRun JSON silently surviving the merge).

### Phase 2: describe() fallback fix
Rationale: Smallest surface area (one function, describe.py, zero schema/route changes), lowest risk, and de-risks item 5's feature-filter rendering (build before the new example so any unusual (op, control) combo in the new JSON still renders instead of silently vanishing).
Delivers: _feature_group_sentence gains a final fallback branch (after the 4 existing hardcoded combos) that renders a generic, human-readable sentence with a working ff:{key} remove-link, instead of returning None.
Addresses: Milestone item 4 (T-01-03).
Avoids: Pitfall 4 (fallback masking real registry gaps / breaking the remove-link contract) -- verify with a test matrix over every (op, control) pair the registry currently defines, and confirm the fallback's key round-trips through _query_href_removing.

### Phase 3: Bundle neutral-site/indoor unders example
Rationale: Pure data addition (new JSON file in cfb_system_maker/examples/), no code dependency on item 3, soft dependency on Phase 2's fallback as a rendering safety net.
Delivers: 4th bundled example system (neutralSite + gameIndoors + venue_dome, 109 games historically, 63.3%, p=0.014), with an honest theory string disclosing sample size, and a deliberate "no games match this week" empty state for the live Current Matches panel.
Addresses: Milestone item 5.
Avoids: Pitfall 6 (zero-match live week misread as broken, due to thin gameIndoors/weather coverage or genuine seasonal rarity) -- verify with a sidecar null-rate check after the first live upcoming run.

### Phase 4: Live in-season verification
Rationale: No code dependency on Phases 1-3 beyond needing the merge landed; gated on the real calendar (season starts ~2026-08-29), so it can run in parallel with or after the above, but its dry-run component should happen before season start.
Delivers: Pre-season dry run against a live-but-past calendar date (catches a possible str/datetime type mismatch in _resolve's live-calendar branch before it's exercised for real); then a live check once 2026 games post, with season-to-date-stat verification explicitly scheduled for week 3+ (not week 1, where games_played=0 correctly fails closed).
Addresses: Milestone item 2.
Avoids: Pitfall 5 (calendar type mismatch, week-1 nulls misread as pipeline failure).

### Phase 5 (or folded into Phase 0/documentation): Hide Duplicates scope resolution
Rationale: Independent of Phases 1-4; primarily a documentation/decision task, optionally a small code task if (b) above is pursued.
Delivers: PROJECT.md Out of Scope entry updated to close item 3 as N/A with the architectural reason recorded; optionally, a small labeling or tuple-fan-out fix in aggregate_filter_value_rows/the filter-detail modal template, scoped and named independently of "Hide Duplicates."
Addresses: Milestone item 3 (as corrected).
Avoids: Shipping a no-op checkbox that misrepresents the system's data integrity; avoids Pitfall 2/3 (double-counting in the modal; dedup-vs-clustering double-correction, which only becomes relevant if a real matched-list-level dedup is ever built in the future -- not required by the corrected scope of item 3).

### Phase Ordering Rationale

- The merge must come first -- it's a hard file-overlap prerequisite for every other code-touching item (Architecture research: backtest.py, features.py, storage.py, web.py are shared touch points).
- describe() fallback before the new example -- smallest, most isolated change, and provides a rendering safety net for whatever (op, control) combo the new example's venue_dome categorical filter happens to need.
- Live verification's dry-run component should happen before season start regardless of where it falls in the phase sequence, since it's gated by a real external date, not by other phases' completion.
- Hide Duplicates scope resolution has no code dependency on anything else and could be done first as a cheap documentation fix, but is sequenced last here only because it's non-blocking -- move it earlier if the roadmapper wants to close the confusion out immediately.

### Research Flags

Phases likely needing deeper research during planning:
- Hide Duplicates scope resolution (Phase 5): if option (b) is pursued, the tie-break/bucketing decision ("does one game legitimately count once per matching team/conference value, or should that be suppressed?") is an open product decision, not resolved by this research -- flag for /gsd-plan-phase --research-phase or at minimum an explicit phase-discussion question.

Phases with standard patterns (skip research-phase):
- Phase 1 (merge): standard git merge + a re-backtest verification script following existing test patterns.
- Phase 2 (describe fallback): single-function, single-file change with a clear minimal-diff shape already identified by Architecture research.
- Phase 3 (bundled example): pure JSON addition matching an existing, fully generic loader -- no schema or code gap.
- Phase 4 (live verification): manual verification against an already-shipped pipeline; the only "research" needed is the pre-season dry run itself, which is the verification step, not a knowledge gap.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct codebase inspection; no external sources needed; confirms zero new dependencies |
| Features | MEDIUM | Repo/code evidence is HIGH; Bet Labs UX comparison claims are LOW (screenshot-derived from docs/bet-labs-parity-plan.md, no live product access) -- does not affect the item 3 correction, which is code/data-verified |
| Architecture | HIGH | All findings read directly from current repo code on the review branch; no external sources needed |
| Pitfalls | HIGH | All findings grounded in direct code inspection plus the branch's own commit log/SUMMARY.md |

Overall confidence: HIGH -- the one MEDIUM area (Bet Labs UX parity claims) is explicitly quarantined by its own researcher and does not touch the load-bearing finding (the item 3 scope correction), which all four files independently corroborate via primary-source code/data evidence.

### Gaps to Address

- Hide Duplicates tie-break semantics (if option (b) pursued): whether the filter-detail modal's per-value fan-out is legitimate-by-design or should be suppressed is an open product decision -- resolve during phase discussion, not assumed by research.
- Live calendar row shape: whether GamesApi.get_calendar() returns str or datetime for startDate/endDate in production is unverified until the pre-season dry run is actually executed -- this is a known unknown with a concrete verification step already identified, not an open question needing more research.
- SearchRun audit scope: exact count/list of affected saved systems in data/search_runs/*.json is unknown until the re-backtest-and-diff script is run during Phase 1 -- the mechanism is understood, the blast radius isn't yet measured.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: cfb_system_maker/models.py, backtest.py, describe.py, storage.py, web.py, features.py, upcoming.py, search.py, cfb_system_maker/examples/*.json, requirements.txt
- Empirical data checks: data/processed/games.csv (12,964 rows / 12,964 distinct game_id), data/processed/upcoming.csv (50/50)
- Git history: git log fix/web-app-review-2026-08-26 (26 commits), git show d9c93e4, git show 5040b31, git diff master...fix/web-app-review-2026-08-26 --stat
- .planning/PROJECT.md, .planning/STATE.md, project CLAUDE.md (root and .claude/)
- .planning/quick/20260826-total-filter-semantics-fixes/SUMMARY.md

### Secondary (MEDIUM confidence)
- None -- all secondary claims were explicitly tagged LOW rather than MEDIUM by the source researcher.

### Tertiary (LOW confidence)
- docs/bet-labs-parity-plan.md sections 1.2, 1.4, 3 -- Bet Labs competitor feature descriptions, screenshot-derived with no live product access; used only for competitive framing, not for the item 3 scope correction (which rests entirely on primary-source evidence)

---
*Research completed: 2026-08-26*
*Ready for roadmap: yes*
