# Feature Research

**Domain:** Betting system-builder web UI (Bet Labs parity), v1.1 Season Readiness closeout
**Researched:** 2026-08-26
**Confidence:** MEDIUM — repo/code evidence is HIGH confidence; Bet Labs UX claims come from the already-vendored `docs/bet-labs-parity-plan.md` (screenshot-derived, no live product access), tagged LOW where noted; no external web research was needed or performed (product is closed, docs already ingested).

## Critical Finding: Item 3's premise does not hold in this codebase

The milestone context describes Hide Duplicates as needed because "a total system with no team/side-fixing filter matches both a home-team-based row and an away-team-based row for one game." **This is not what happens.** Verified two ways:

1. **Data:** `data/processed/games.csv` has 12,964 rows for 12,964 distinct `game_id`s; `data/processed/upcoming.csv` has 50 rows for 50 distinct `game_id`s. One row per game, always — `normalize._select_line` guarantees this at build time.
2. **Code:** `matches_system()` (`backtest.py:336`) takes one `GameRecord` and returns one `bool`. `run_backtest()` (`backtest.py:47`) is a single list comprehension over `games`. There is no code path that emits two candidate bets for one `game_id`. This structurally cannot double-count a game in the top-line Record/Money/ROI chips, with or without a checkbox.

What **d9c93e4** ("team/conference filters on total systems match either side") actually introduced is narrower: `resolve_candidate_value()` (`web.py:213-220`) returns a `(home_team, away_team)` tuple for `core:team`/`core:conference` on total systems, and `aggregate_filter_value_rows()` (`web.py:242`) — the **filter-detail modal's per-value breakdown table**, not the backtest engine — buckets one game's single `BetDetail` under *each* distinct team/conference value. A Georgia-vs-Auburn total game appears as one row's worth of Record/Money under "Georgia" and again under "Auburn" in that table. Each row is individually correct (it's that team's game); the issue is the table's rows don't partition the games the way Bet Labs' team-identifying model would lead a user to expect — sum-across-rows exceeds the system's total. The top-line stat chips are unaffected.

**Implication for scoping:** Bet Labs' Hide Duplicates (parity-plan §1.4, LOW confidence — screenshot-derived) drops a game from the *top-line Record* when both teams in a matchup independently satisfy the same team-scoped filter (its record example: 154-133-4 → 136-115-4, a real record change). cfb-site's `bet_type` model has no analogous mechanism: a "system" is a global side/perspective + filters, not a team identity the engine chases across both participants. Building a literal Hide Duplicates toggle today would ship a checkbox that changes nothing observable in the Record/Money/ROI chips it's supposed to affect — the roadmapper should treat this as **descope, not build**, unless the true target is instead the filter-detail modal's per-value table (a different, smaller fix: label those rows so their sum isn't mistaken for a partition, e.g. a footnote "totals count a game once per team/conference shown").

Also checked while here: `upcoming.csv` has the same one-row-per-game guarantee, so Current Matches (item 2) is not exposed to this duplication either.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or gives wrong data.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Merge `fix/web-app-review-2026-08-26` to master (item 1) | 26 commits of shipped fixes (security, a11y, correctness, perf) currently only on a branch; master is stale relative to what's been verified | LOW | Integration/merge only, not feature design. Branch head is `6dd627f`; working tree already shows uncommitted `filter_modal.js`/`test_filter_modal.py` changes layered on top — confirm those are intentional pre-merge work, not merge conflicts, before merging. |
| Current Matches shows real 2026 games once lines post (item 2) | Core promise of the My Systems dashboard ("turns backtester into a tool you check weekly," parity-plan §4); currently unverifiable pre-season | LOW (verification, not code) | `upcoming` CLI path + Current Matches panel already shipped in v1.0 Phase 5 (`require_played=False` in `matches_system`, D-18). Nothing to build — this is a live check against the 2026-08-29 slate: run `upcoming`, confirm dashboard rows render, confirm feature-filtered systems still match (season-to-date stats computable pre-game). If it fails, that's a bug-fix task, not new scope. |
| Every active filter renders a visible sentence (item 4) | A filter with no visible sentence looks like it silently vanished — user can't tell what's constraining their backtest, and (per PROJECT.md T-01-03) there's no ✕ to remove it either. This is a correctness/integrity gap, not a nice-to-have. | LOW | Root cause identified: `_feature_group_sentence()` (`describe.py:58`) returns `None` in two cases — (a) numeric feature with neither `gte` nor `lte` filter present in the group (shouldn't normally happen but is reachable via malformed query params, which the fix branch already hardens elsewhere), (b) bool/categorical feature whose `filt.op`/`feature.control` combo isn't one of the three hardcoded branches (line 76-85 falls through the loop, `text` stays `None`). `describe()` (line 89) then just omits the row — silent drop, not a placeholder. |
| Bundled neutral-site/dome unders example (item 5) | Matches the existing 3-example pattern (My Systems dashboard "Example Systems" tab, parity-plan §1.1/§4); a shipped statistical lead with a real p-value is exactly the kind of theory-driven example the product already showcases | LOW | All three registry features (`neutralSite`, `gameIndoors`, `venue_dome`) already exist in `features.py` (lines 59, 161, 294) as `bool` controls — no registry work needed, purely a new JSON file plus loader registration. |

### Differentiators (Not Required, But Worth Doing Right)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Fallback sentence looks native, not debug-y | A visible-but-ugly fallback (e.g. raw key dump) undermines the "reads like Bet Labs" core value as much as a missing sentence does | LOW | Repo already sets the native-looking precedent at `describe.py:63`: `{"text": f'Unknown filter "{key}" is unavailable', "key": f"ff:{key}"}` for a genuinely unknown key. Extend that same shape for the *known-key-but-unrenderable-combo* case — e.g. `f'{label} is set (unsupported display)'` with `key=f"ff:{key}"` — so the remove-link still works (see Anti-Features below) and the row visually matches the other filter rows (same class, same ✕ affordance) rather than reading as an error banner. LOW confidence this exact wording matches Bet Labs (they have no analogous gap surfaced in the screenshots) — this is a cfb-site-native design decision, not a parity import. |
| Per-value modal table labeled to prevent sum-inflation misreading (real referent for item 3) | Directly closes the actual duplication users can observe today (per-value Record/Money rows for total-system team/conference filters don't partition the games) | LOW-MEDIUM | Smallest fix: a caption/footnote near the `core:team`/`core:conference` table when `bet_type == "total"` — something like "Totals count each game once per team shown; rows don't sum to the system total." No engine change. Only pursue if the roadmapper decides the "Hide Duplicates" deferred item should resolve to *something* rather than close as N/A — see Anti-Features. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Literal "Hide Duplicates" checkbox on the system editor, wired to drop a `game_id` from `run_backtest` | PROJECT.md/parity-plan carry it as a known Bet Labs feature and a previously-deferred item now marked "reachable" | Nothing to hide — `run_backtest`/`matches_system` never produce two bets for one `game_id` (verified above). A checkbox with no observable effect on Record/Money/ROI is worse than no checkbox: it implies a data-integrity feature exists where none is needed, and a user who toggles it and sees zero change will (correctly) distrust the tool. Building it as literal parity would require restructuring `bet_type` around team-identity matching (a materially larger, out-of-scope change) just to give the checkbox something to do. | Descope explicitly in this milestone with a documented reason (update PROJECT.md's Out of Scope entry from "deferred, reachable" to "N/A — architecture doesn't produce per-game duplicates"), and if the underlying user complaint (per-value modal table double-listing totals games) is worth 30 minutes, ship the labeling fix instead under its own name, not the Bet Labs name. |
| A fallback sentence that echoes raw internal state (op code, control type, param dump) for debuggability | Feels helpful for future maintainers hitting the same gap | Directly contradicts the "reads like Bet Labs" core value — a debug-y row is more jarring to an end user than a missing row, especially since this ships to the *user-facing* active-filter list, not a log | Keep the fallback human-readable using the feature's existing `label` (already resolved via `FEATURE_BY_KEY`); log the unhandled op/control combo server-side (or as a code comment/TODO) for maintainers instead of surfacing it in the UI text |
| A new/parallel example-system file format or loader path for the 5th example | Tempting to "improve" the schema while adding a new instance | The 3 existing examples (`spread-home-favorites.json`, `total-unders-high-lines.json`, `nonconference-away-dogs.json`) are plain `SavedSystem` JSON with a `theory` string, loaded via the existing `list_examples`/`load_example_system(name, EXAMPLES_DIR)` (`web.py:40-43`, `1677-1679`) — no example-specific schema exists to begin with. Any deviation breaks that uniform loader. | Write the 4th file in the identical shape: `name`, `saved_at`, `system` (full `SystemFilter` dict incl. `feature_filters` for the three bool features), `theory`. Drop it in `cfb_system_maker/examples/`. |

## Feature Dependencies

```
Item 1 (merge fix branch)
    └──independent of──> Items 2-5 (no code dependency, but should land first —
                          items 4/5 will conflict-diff against files the branch
                          already touches: web.py, filter_modal.js)

Item 4 (fallback sentence)
    └──touches describe.py::_feature_group_sentence / describe()
    └──consumed by──> Item 2's Current Matches panel (PROJECT.md: "reused describe()
                       filter details") — a fallback fix changes BOTH the system-editor
                       active-filter list AND the dashboard's Details column; verify
                       both render sets after the fix, not just the editor page.
    └──must preserve──> remove-link affordance (every sentence's "key" must map to a
                         real query-string removal target; the fallback's key should
                         reuse the existing "ff:{key}" scheme already used for the
                         unknown-filter branch, not invent a new one the template's
                         remove-link builder doesn't recognize)

Item 3 (Hide Duplicates) ──conflicts with── the milestone's stated premise
    Recommend: resolve via PROJECT.md update (close as N/A / architectural mismatch),
    optionally paired with the smaller per-value-table labeling fix (Differentiators).
    No dependency on Items 1/2/4/5.

Item 5 (bundled example)
    └──requires──> neutralSite, gameIndoors, venue_dome features already in registry (✓ present, no gap)
    └──requires──> existing examples/ loader (✓ present, no gap)
    └──should carry──> an honest theory-field disclosure of sample size (109 games,
                        p=0.014) — see MVP Definition note below; this is a product-
                        honesty dependency, not a code dependency: the system's own
                        System Grade (compute_grade / _sample_size_score, backtest.py:150)
                        will likely NOT grade this system highly (small n, 3-filter
                        combo trips the overfitting-count penalty), and a bundled
                        "example" that the product's own grade chip visibly distrusts
                        undermines both the example and the grade feature's credibility
                        unless the theory text sets that expectation up front.
```

### Dependency Notes

- **Item 4 requires touching a shared code path.** `describe()` is not editor-only; PROJECT.md documents Current Matches (Phase 5) as reusing it for the dashboard's per-match Details column. A fix here has two render surfaces to verify, not one.
- **Item 4's fix must not break the existing remove-link contract.** Every sentence dict is `{"text": str, "key": str}` and the template builds a query-string-minus-this-filter link from `key`. The existing `Unknown filter "{key}"` branch (line 63) already proves the right shape (`key=f"ff:{key}"`) for a row that still needs a working ✕ — extend that pattern rather than inventing a new key scheme.
- **Item 3 has no dependency on any other item** — it is a scoping/documentation resolution (update the Out of Scope rationale in PROJECT.md), not implementation work, unless the roadmapper elects to pursue the smaller per-value-table labeling fix instead.
- **Item 5's dependency chain is fully satisfied already** — no registry, loader, or schema gaps. The only open question is whether the `theory` text (or a grade-adjacent disclosure) should preempt the low-n concern before shipping it as a bundled example a new user will trust by default.

## MVP Definition

### Launch With (v1.1, before 2026-08-29)

- [ ] Item 1: Merge `fix/web-app-review-2026-08-26` — 26 verified fixes currently stranded on a branch; season starts in 3 days, this needs to land regardless of the other 4 items
- [ ] Item 2: Live-verify Current Matches once 2026 lines post — this is a verification task with a hard external deadline (season start), not something that can slip
- [ ] Item 4: Fix `_feature_group_sentence` fallback — small, well-scoped, closes an accepted risk (T-01-03) that's flagged in PROJECT.md as revisit-worthy; low complexity, high integrity payoff (no more silently-applied-but-invisible filters)
- [ ] Item 5: Ship the neutral-site/indoor unders example — all dependencies satisfied, matches an existing pattern exactly; gate on writing an honest `theory` string (disclose n=109, p=0.014, three-filter combo) so it doesn't read as an overconfident claim the product's own Grade chip will contradict

### Add After Validation / Reframe (v1.1 scope decision needed)

- [ ] Item 3: **Not buildable as literally specified** — recommend closing PROJECT.md's Hide Duplicates deferral as "N/A, architecture doesn't produce per-game duplicates" rather than building a no-op checkbox. If the roadmapper still wants to address the real (smaller) issue — per-value modal table rows summing past the system total for total-system team/conference filters — scope that as its own small labeling task, explicitly not named "Hide Duplicates" to avoid re-promising Bet Labs parity that doesn't apply here.

### Future Consideration (out of this milestone)

- Restructuring `bet_type`/`SystemFilter` around team-identity matching (the only path to a *literal* Hide Duplicates) — explicitly out of scope; large architectural change with no current user-facing motivation beyond re-creating a Bet Labs mechanic that doesn't map onto cfb-site's side/perspective model.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Merge fix branch (item 1) | HIGH (correctness/security fixes currently unshipped) | LOW | P1 |
| Current Matches live verification (item 2) | HIGH (core weekly-use promise, hard deadline) | LOW | P1 |
| Fallback filter sentence (item 4) | MEDIUM-HIGH (closes a real, if narrow, integrity gap) | LOW | P1 |
| Neutral-site/dome unders example (item 5) | MEDIUM (content addition, not mechanism) | LOW | P1 (gate on honest theory text) |
| Hide Duplicates as literally specified (item 3) | NONE observable (no-op given current architecture) | LOW to build the checkbox / MEDIUM-HIGH to make it do anything real | P3 — recommend closing as N/A instead |
| Per-value modal table duplication labeling (item 3's real referent) | LOW-MEDIUM (fixes a real but narrow display-sum confusion) | LOW | P2, optional |

**Priority key:**
- P1: Must have for this milestone / has a hard external deadline
- P2: Should have if time allows, doesn't block season start
- P3: Reconsider scope — likely should not be built as specified

## Competitor Feature Analysis

| Feature | Bet Labs (Sports Insights) — via `bet-labs-parity-plan.md` §1.4, LOW confidence (screenshot-derived, no live access) | cfb-site today | Recommended approach |
|---------|-------------------------------------------------------------------------------------------------------------------|-----------------|-----------------------|
| Hide Duplicates | Checkbox next to Fade System, top-right of system editor; drops a game where *both* teams in the matchup independently satisfy the filters (their example: 154-133-4 → 136-115-4); doc explicitly notes it's "unneeded when a filter already forces one side" | No mechanism produces duplicate top-line bets for one `game_id`; only a per-value modal *table* can list a total-system game under two team buckets | Close as N/A for the top-line record; optionally label the modal table instead |
| Every filter has a display sentence | Filter list shows "pencil Edit \| filter name \| plain-English sentence \| red ✕ delete" for every active row — no screenshot shows a blank/missing row | `describe()` silently omits rows for unhandled (op, control) combos | Extend the existing "Unknown filter" fallback pattern (`describe.py:63`) to the unhandled-combo case, keeping the same `key=f"ff:{key}"` shape so remove-links stay live |
| Example Systems tab | Ships with the product "so a new user has something to open" (§1.1); no stated cap on count | 3 examples today (spread-home-favorites, total-unders-high-lines, nonconference-away-dogs), all `SavedSystem` JSON + `theory` text, loaded via `list_examples`/`load_example_system` | Add a 4th file in the identical schema; no pattern change needed — this is already "the standard pattern," just add content |

## Sources

- `C:\Users\mckel\dev\cfb-site\docs\bet-labs-parity-plan.md` §1.2, §1.4, §3 (Phase 3 item 11) — Bet Labs GUI inventory, screenshot-derived, LOW confidence per the doc's own framing (no live product access, secondary description of screenshots)
- `C:\Users\mckel\dev\cfb-site\.planning\PROJECT.md` — Key Decisions table (Hide Duplicates deferral rationale), Deferred/Out of Scope sections, Context section
- Repo code read directly (HIGH confidence, primary source): `cfb_system_maker/backtest.py` (`matches_system`, `run_backtest`), `cfb_system_maker/describe.py` (`describe`, `_feature_group_sentence`), `cfb_system_maker/web.py` (`resolve_candidate_value`, `aggregate_filter_value_rows`, examples loader wiring), `cfb_system_maker/examples/*.json` (all 3 existing bundled examples), `cfb_system_maker/features.py` (registry entries for `neutralSite`, `gameIndoors`, `venue_dome`)
- Empirical data check: `data/processed/games.csv` (12,964 rows / 12,964 distinct `game_id`), `data/processed/upcoming.csv` (50 rows / 50 distinct `game_id`) — run 2026-08-26
- Git history: `git log fix/web-app-review-2026-08-26` (26 commits), `git show d9c93e4` / `git show 5040b31` (the two commits that make total systems match either side — the actual mechanism behind the milestone's item 3 framing)

---
*Feature research for: betting system-builder web UI closeout milestone*
*Researched: 2026-08-26*
