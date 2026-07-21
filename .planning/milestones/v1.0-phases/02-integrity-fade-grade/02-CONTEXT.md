# Phase 2: Integrity — Fade & Grade - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can invert a system to test the fade and see an at-a-glance composite grade of how trustworthy a system's edge is, both surfaced in the stat-chip header built in Phase 1. Two capabilities: (1) a Fade toggle that flips the graded side of every matched bet, and (2) a composite System Grade rendered into the Grade chip slot that Phase 1 already reserved (placeholder em-dash).

Out of this phase's scope: Grade breakdown/hover panel (deferred), Current Matches tab, filter popup modal, dashboard — all separate roadmap phases.

</domain>

<decisions>
## Implementation Decisions

### Fade Toggle
- **D-01:** Fade is a toggle on the system editor page (near the stat chips), applies to both `bet_type="spread"` and `bet_type="total"` systems — flips `side` (home↔away) for spread, `total_side` (over↔under) for total.
- **D-02:** `fade: bool` persists on `SystemFilter`/`SavedSystem` — survives save/reload (per roadmap success criteria #3).
- **D-03:** Flipping in `grade_bet`/`_grade_total_bet` means grading the opposite side's outcome for the same matched games — pushes stay pushes.

### System Grade Computation
- **D-04:** Grade is a composite pure function over `SystemStats`/`BacktestResult` fields that already exist: `z_score`, `p_value` (permutation), `wilson_low`/`wilson_high` (sample size vs significance), `season_breakdown`/`sign_consistency`, plus a new overfitting-penalty input (D-06).
- **D-05 (Claude's discretion):** User is not attached to a literal letter grade — output format (letter, score, or short label) and the exact combination rule (e.g. worst-of vs weighted average across the 5 inputs) are Claude's call. Document the chosen rule explicitly in the plan/implementation so it's a fixed, testable function — not vibes. Whatever is chosen must be derivable purely from `BacktestResult` + `SystemFilter` (per roadmap: "Pure function... very testable").
- **D-06:** Overfitting penalty counts: every populated `SystemFilter` field (e.g. `favorite`, `min_spread` set, `providers` non-empty) counts as 1 active filter; each element inside a set-valued field (`teams`, `conferences`, `seasons`, `weeks`, and each `FeatureFilter` with `op="in"` — count each in-list value individually) counts individually toward the "too many values selected" penalty. Mirrors Bet Labs' "27 pitchers hand-picked" example.

### Grade Chip UI
- **D-07:** This phase renders the composite Grade value into the existing Grade chip slot only (replacing Phase 1's em-dash placeholder). No hover/click sub-score breakdown panel this phase — that's deferred (see Deferred Ideas).

### Claude's Discretion
- Exact grade formula/thresholds and output format (D-05).
- Exact wording/styling of the Fade toggle control, consistent with existing vanilla JS/CSS stat-chip header from Phase 1.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Constraints
- `.claude/CLAUDE.md` — tech stack (Python + Flask + vanilla JS/CSS, no frontend framework), no-lookahead rule, storage backward-compatibility rule (`SavedSystem` JSON must default gracefully for systems saved before `fade` existed), CSV schema stability rule.
- `.planning/PROJECT.md` — Core Value, Active requirements list (Fade toggle, System Grade letter already listed there).

### Phase Source Material
- `docs/bet-labs-parity-plan.md` items 9–10 (lines ~121-122) — Fade System toggle and System Grade design intent, including the "fade of a 60% system grades ~40% on same matches, pushes unchanged" test expectation, and the grade's 5 sub-score inputs.
- `.planning/ROADMAP.md` Phase 2 section — goal, success criteria, requirements INTG-01/INTG-02.
- `.planning/REQUIREMENTS.md` INTG-01/INTG-02 — requirement text and phase mapping.

### Prior Phase Decisions
- `.planning/phases/01-system-editor-main-page/01-CONTEXT.md` — confirms the Grade chip UI slot shipped in Phase 1 as a placeholder ("—"), and that Phase 2 wires the real computed value into that same slot (no header layout change needed).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cfb_system_maker/backtest.py::compute_system_stats` — already computes `z_score`, `p_value`, `wilson_low`/`wilson_high`, `permutation_p_value`, `roi_t_stat` via `_permutation_p_value`, `_hit_rate_z_test`, `_wilson_interval`. Grade function should consume `SystemStats`/`BacktestResult`, not recompute stats.
- `cfb_system_maker/backtest.py::compute_season_breakdown` and `sign_consistency` — season-by-season win/loss already computed; feeds directly into the sign-consistency grade input.
- `cfb_system_maker/models.py::SystemFilter` — frozen dataclass; `fade: bool` is a new field to add here (frozen dataclasses use `dataclasses.replace` for mutation, as seen in `backtest.py::split_holdout`).
- `cfb_system_maker/backtest.py::grade_bet` / `_grade_total_bet` — grading entry points; fade flips `normalized_side` (spread) or the over/under branch (total) before existing grading logic runs.

### Established Patterns
- All domain types are frozen dataclasses (`models.py`) — new `fade` field follows this convention, not a mutable class.
- Storage backward compatibility: `storage.py` / `SavedSystem` JSON load must default `fade=False` for systems saved before this phase (per `.claude/.claude/CLAUDE.md` constraint).
- Web UI is server-rendered Flask + vanilla JS (`templates/index.html`) — Fade toggle is a form control/checkbox posted like other filter fields, consistent with existing pattern (no client-side framework).

### Integration Points
- `templates/index.html` Grade chip (`<article><span>Grade</span><strong>&mdash;</strong></article>`, line 232) — replace placeholder with computed grade value.
- `web.py` — wherever `run_backtest`/`compute_system_stats` results are passed to the template, the new grade function slots in alongside existing stat computations.
- CLI (`cli.py`) — if fade needs a CLI flag for parity with other `SystemFilter` fields, add there following existing flag patterns (not required by roadmap success criteria, which are UI-only, but check backward compatibility with existing CLI tests).

</code_context>

<specifics>
## Specific Ideas

No specific UI mockup or exact letter-grade example given — user explicitly deferred the letter-grade format decision to Claude. The "27 pitchers hand-picked" cherry-picking example from `docs/bet-labs-parity-plan.md` is the concrete reference for how the overfitting penalty should feel (many hand-picked in-list values = bad grade).

</specifics>

<deferred>
## Deferred Ideas

- **Grade breakdown/sub-score panel** — Bet Labs shows each of the 5 sub-scores with its own letter, rolling up to the header letter (see `bet-labs-parity-plan.md` line 50, "overfit_2 screenshot"). This phase ships only the single composite value in the header chip; the interactive breakdown panel is future work, likely alongside the filter popup modal phase.
- **Alternate-line ("teaser") records** — mentioned in `bet-labs-parity-plan.md` item 14, explicitly out of this phase (belongs to a later phase per the roadmap).

None — discussion stayed within phase scope otherwise.

</deferred>

---

*Phase: 2-Integrity — Fade & Grade*
*Context gathered: 2026-07-17*
