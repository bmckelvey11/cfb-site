# Phase 2: Integrity — Fade & Grade - Research

**Researched:** 2026-07-17
**Domain:** Pure-function statistical scoring + boolean toggle over an existing Python backtest engine (Flask/Jinja SSR, vanilla JS/CSS, no frontend framework)
**Confidence:** HIGH

## Summary

This phase adds no new libraries, services, or data sources. It is entirely an extension of code that already exists and was read directly from the repository: `cfb_system_maker/backtest.py`, `models.py`, `storage.py`, `web.py`, `cli.py`, and `templates/index.html`. The two capabilities — a Fade toggle and a composite System Grade — both reduce to pure functions over types the codebase already computes (`BacktestResult`, `SystemStats`, `SeasonRecord`, `SystemFilter`).

The load-bearing design decision, forced by CONTEXT.md D-03 ("grading the opposite side's outcome for the *same matched games*"), is that **fade must never touch `matches_system`** — it only flips which side `grade_bet`/`_grade_total_bet` scores. This means `run_backtest`'s aggregation (Record, Money Won, ROI) is fade-aware for free once grading flips; no separate branch is needed anywhere except inside the two grading functions. The margin sign flips exactly (`away_pts + away_spread - home_pts == -(home_pts + home_spread - away_pts)`), which gives "pushes stay pushes" as a mathematical consequence, not a special case.

The Grade is a new pure function, `compute_grade(result, system) -> str | None`, combining five 0.0–1.0 sub-scores (sample size, ROI significance, season sign-consistency, permutation p-value, overfitting penalty) via equal-weighted average into a single letter A–F, or `None` (rendered as `&mdash;`) when zero bets are matched. Every threshold in this document is an explicit, testable constant — not a hand-wave — per D-05's requirement that the rule be "fixed" and "not vibes."

**Primary recommendation:** Implement fade entirely inside `grade_bet`/`_grade_total_bet` (never in `matches_system`); implement grade as a new pure function in `backtest.py` built from five documented sub-score helpers, each independently unit-testable via constructed `BacktestResult`/`SystemFilter` fixtures in the existing test style.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTG-01 | User can toggle "Fade System" on a system to grade the opposite side of every matched bet | Fade Architecture pattern (below): flip in `grade_bet`/`_grade_total_bet` only; `SystemFilter.fade: bool` field; storage/web/CLI round-trip touchpoints enumerated in Code Examples and Common Pitfalls |
| INTG-02 | User sees a composite System Grade letter combining sample size vs significance, ROI z-score, season sign-consistency, permutation p-value, and filter/value-count overfitting penalties | Grade Architecture pattern (below): `compute_grade` + 5 documented sub-score functions with explicit thresholds |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Fade is a toggle on the system editor page (near the stat chips), applies to both `bet_type="spread"` and `bet_type="total"` systems — flips `side` (home↔away) for spread, `total_side` (over↔under) for total.
- **D-02:** `fade: bool` persists on `SystemFilter`/`SavedSystem` — survives save/reload (per roadmap success criteria #3).
- **D-03:** Flipping in `grade_bet`/`_grade_total_bet` means grading the opposite side's outcome for the same matched games — pushes stay pushes.
- **D-04:** Grade is a composite pure function over `SystemStats`/`BacktestResult` fields that already exist: `z_score`, `p_value` (permutation), `wilson_low`/`wilson_high` (sample size vs significance), `season_breakdown`/`sign_consistency`, plus a new overfitting-penalty input (D-06).
- **D-05 (Claude's discretion):** User is not attached to a literal letter grade — output format (letter, score, or short label) and the exact combination rule (e.g. worst-of vs weighted average across the 5 inputs) are Claude's call. Document the chosen rule explicitly in the plan/implementation so it's a fixed, testable function — not vibes. Whatever is chosen must be derivable purely from `BacktestResult` + `SystemFilter`.
- **D-06:** Overfitting penalty counts: every populated `SystemFilter` field (e.g. `favorite`, `min_spread` set, `providers` non-empty) counts as 1 active filter; each element inside a set-valued field (`teams`, `conferences`, `seasons`, `weeks`, and each `FeatureFilter` with `op="in"` — count each in-list value individually) counts individually toward the "too many values selected" penalty. Mirrors Bet Labs' "27 pitchers hand-picked" example.
- **D-07:** This phase renders the composite Grade value into the existing Grade chip slot only (replacing Phase 1's em-dash placeholder). No hover/click sub-score breakdown panel this phase.

### Claude's Discretion
- Exact grade formula/thresholds and output format (D-05) — resolved below in Architecture Patterns; treat as a settled, documented design, not an open question.
- Exact wording/styling of the Fade toggle control, consistent with existing vanilla JS/CSS stat-chip header from Phase 1.

### Deferred Ideas (OUT OF SCOPE)
- Grade breakdown/sub-score panel (each of the 5 sub-scores with its own letter) — future work, likely alongside the filter popup modal phase.
- Alternate-line ("teaser") records — later phase per roadmap.
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fade flip logic (`grade_bet` / `_grade_total_bet`) | API/Backend | — | Pure Python business logic over `GameRecord`/`SystemFilter`; no UI concern, no persistence concern |
| Fade toggle persistence (`SystemFilter.fade`, `SavedSystem` JSON) | Database/Storage | API/Backend | `data/systems/<name>.json` is the persistence tier; `SystemFilter` is the transfer object that crosses into it |
| Fade toggle control (checkbox) | Frontend Server (SSR) | Browser/Client | Server-rendered Jinja template; browser only re-submits the existing GET form on "Run System" — no new client-side JS |
| System Grade computation (5 sub-scores + composite) | API/Backend | — | Pure function alongside `compute_system_stats`/`sign_consistency` in `backtest.py`, same tier, same call site (`run_backtest`/`web.py`) |
| Grade chip rendering | Frontend Server (SSR) | — | Existing template slot from Phase 1 (`templates/index.html:232`), Jinja auto-escaped substitution, no new markup structure |

## Standard Stack

**No new dependencies this phase.** Everything is built from the existing stack already in `requirements.txt` / vendored code:

### Core (already in use — no install needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.x (project runtime) | `SystemFilter.fade` field, `dataclasses.replace` for immutable updates | Every domain type in `models.py` is a frozen dataclass; this is the established convention, not a new choice |
| Flask / Jinja2 | already vendored via `requirements.txt` | Fade checkbox rendering, Grade chip substitution | Existing SSR stack; auto-escaping already relied on (STATE.md: "no `\|safe`" rule) |
| pytest | already vendored via `requirements.txt` | Unit tests for fade flip and grade sub-scores | Existing test runner (`pytest.ini`, `testpaths=tests`) |

### Supporting
None — this phase touches only existing modules (`backtest.py`, `models.py`, `storage.py`, `web.py`, `cli.py`, `templates/index.html`).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Equal-weighted average of 5 sub-scores | "Worst-of" (grade = min sub-score) | Worst-of makes overfitting or low sample size alone floor the grade to F even with a strong, well-sampled edge — harsher and arguably closer to Bet Labs' framing ("27 pitchers" example implies one bad sub-score should tank it). Documented as the discretionary alternative below; average was chosen for smoother, less punitive grading of otherwise-solid systems with one weak dimension. Either is a one-line change in `compute_grade` (`sum(scores)/5` → `min(scores)`) if the user later prefers worst-of. |
| Single letter grade (A–F) | Letter + modifier (A+/B-) | Simpler band logic, fewer boundary-condition tests; user explicitly said "not attached to a literal letter grade" so simplicity wins per D-05 |

**Installation:** None required.

## Package Legitimacy Audit

**Not applicable.** This phase installs zero new packages (no `npm install` / `pip install` targets). All work is in existing, already-installed modules. Skip the Package Legitimacy Gate.

## Architecture Patterns

### System Architecture Diagram

**Fade flow (request → grading → chips):**

```
Browser: checkbox "Fade System" submitted with the existing GET filters form
        │  (name="fade", value="on"; form="filters-form" HTML attribute —
        │   see Code Examples — lets it live near the stat chips in the DOM
        │   while still submitting with the sidebar <form>)
        ▼
web.py:_form_values() / _form_values_from_post()
        │  fade = request.args.get("fade") == "on"   (same pattern as favorite/underdog)
        ▼
web.py:_system_from_form()  →  SystemFilter(fade=True, ...)
        ▼
backtest.py:run_backtest(games, system, feature_map)
        │
        ├──▶ matches_system(game, system, feature_map)
        │        fade is NEVER read here — the matched game set is
        │        identical whether fade is True or False (D-03 contract)
        │        │
        │        ▼ matched games
        │
        └──▶ grade_bet(game, system, ...)  /  _grade_total_bet(game, system, ...)
                 │  reads system.fade — flips the graded side BEFORE
                 │  computing team/opponent/points/margin/result/profit
                 ▼
             BetDetail  (result, profit, side, margin already reflect fade)
        │
        ▼
BacktestResult  (wins/losses/pushes/profit/roi already fade-correct —
        │        no separate "faded" code path anywhere in run_backtest)
        │
        ├──▶ compute_grade(result, system)  →  letter "A".."F" | None
        │
        ▼
web.py:index()  passes result + grade to template
        ▼
templates/index.html stat-chips section
        Record / Margin / Money Won / ROI  — UNCHANGED template code,
        values are correct because BetDetail was already flipped upstream
        Grade  — NEW: renders compute_grade() output or &mdash;
        ▼
Browser renders updated chips
```

**Persistence flow (save → reload):**

```
POST /save (form includes fade=on or is absent)
   ▼
web.py:_form_values_from_post() → _system_from_form() → SystemFilter(fade=...)
   ▼
storage.py:save_system() → _system_to_dict()  adds "fade": system.fade
   ▼
data/systems/<name>.json   {"system": {..., "fade": true, ...}}
   ▼  (on later GET /?load_system=<name>)
storage.py:load_saved_system() → _system_from_dict()
   fade = bool(system.get("fade", False))   ← backward-compat default
   ▼
web.py:_form_from_system()  must also carry fade into the form dict
   ▼
templates/index.html  checkbox pre-checked from form.fade
```

### Recommended Project Structure

No new files. Modify existing modules only:
```
cfb_system_maker/
├── models.py            # + SystemFilter.fade: bool = False
├── backtest.py           # + fade flip in grade_bet/_grade_total_bet
│                          # + compute_grade() + 5 sub-score helpers
│                          # + count_overfit_filters()
├── storage.py             # + fade in _system_to_dict / _system_from_dict
├── web.py                  # + fade in form dicts, _system_from_form,
│                            #   _query_args_from_form; pass grade to template
├── cli.py                    # + optional --fade flag on `backtest` subcommand
│                              #   (parity, not required by roadmap UI criteria)
└── templates/index.html        # + Fade checkbox control; Grade chip renders value
```

### Pattern 1: Fade Inverts Grading, Never Matching

**What:** `system.fade` is read only inside the two grading functions. `matches_system` has zero knowledge of it.

**When to use:** Any time you need "test the opposite bet on the same evidence" — the matched-game population is a property of the *filters* (season, team, favorite/underdog, spread/total ranges, feature filters), not of which side gets graded.

**Example:**
```python
# Source: cfb_system_maker/backtest.py (existing code, read directly) + this phase's addition

def _fade_side(side: str) -> str:
    return "away" if side == "home" else "home"

def _fade_total_side(total_side: str) -> str:
    return "under" if total_side == "over" else "over"


def grade_bet(game, system, *, stake=1.0, american_odds=-110):
    ...
    normalized_side = system.side.lower()
    if system.fade:
        normalized_side = _fade_side(normalized_side)
    if game.home_points is None or game.away_points is None:
        raise ValueError("game must have spread and final score")
    if system.bet_type == "total":
        return _grade_total_bet(game, system, stake=stake, american_odds=american_odds)
    # ... rest unchanged, now operates on the (possibly flipped) normalized_side


def _grade_total_bet(game, system, *, stake, american_odds):
    ...
    effective_total_side = system.total_side
    if system.fade:
        effective_total_side = _fade_total_side(effective_total_side)
    # ... winner/result/profit logic now compares against effective_total_side
    # instead of system.total_side directly; team/side fields in the returned
    # BetDetail use effective_total_side too, so the UI shows the faded side.
```

**Correctness proof (why pushes survive unchanged, without a special case):**
Home margin = `home_pts + home_spread - away_pts`. Away margin = `away_pts + away_spread - home_pts` = `away_pts - home_spread - home_pts` = `-(home_pts + home_spread - away_pts)`. The faded margin is the exact negation of the original. `margin > 0` (win) becomes `margin < 0` (loss) and vice versa; `margin == 0` (push) stays `0` under negation. This is the load-bearing test case for INTG-01 (see Validation Architecture).

### Pattern 2: Composite Grade as a Fixed, Testable Pure Function

**What:** `compute_grade(result: BacktestResult, system: SystemFilter) -> str | None` combines five independently-defined 0.0–1.0 sub-scores by equal-weighted average, then buckets the average into a letter. Returns `None` when `result.bets == 0` (nothing to grade — mirrors the existing `Margin` chip's `&mdash;` convention for the "no data" case, distinct from "graded and found weak", which is `F`).

**When to use:** This exact shape — every time the Grade chip needs a value; called once per request in `web.py:index()` immediately after `run_backtest`.

**Example:**
```python
# Source: this phase's design, following the existing compute_system_stats /
# sign_consistency pattern already in cfb_system_maker/backtest.py

_GRADE_BANDS = (  # (min composite score inclusive, letter)
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.35, "D"),
    (0.00, "F"),
)


def _sample_size_score(decided: int) -> float:
    if decided < 30:
        return 0.0
    if decided < 100:
        return 0.3
    if decided < 300:
        return 0.6
    if decided < 1000:
        return 0.8
    return 1.0


def _roi_significance_score(z_score: float) -> float:
    # Uses SystemStats.z_score (hit-rate z-test vs. break-even), NOT
    # roi_t_stat. At fixed stake/odds, ROI is a linear function of hit
    # rate, so z_score is monotonic with ROI significance and is already
    # computed against the correct break-even baseline (roi_t_stat is a
    # t-stat of per-bet returns against zero, a different null hypothesis).
    if z_score < 0:
        return 0.0
    if z_score < 1.0:
        return 0.2
    if z_score < 1.645:   # 90% one-tailed critical value
        return 0.5
    if z_score < 1.96:    # 95% two-tailed / 97.5% one-tailed critical value
        return 0.75
    return 1.0


def _consistency_score(profitable: int, total_seasons: int) -> float:
    if total_seasons == 0:
        return 0.0
    return profitable / total_seasons


def _permutation_score(p_value: float) -> float:
    if p_value < 0.01:
        return 1.0
    if p_value < 0.05:
        return 0.8
    if p_value < 0.10:
        return 0.5
    if p_value < 0.20:
        return 0.25
    return 0.0


def _overfit_score(active_filter_value_count: int) -> float:
    if active_filter_value_count <= 3:
        return 1.0
    if active_filter_value_count <= 7:
        return 0.75
    if active_filter_value_count <= 14:
        return 0.5
    if active_filter_value_count <= 24:
        return 0.25
    return 0.0   # e.g. Bet Labs' "27 pitchers hand-picked" example lands here


def count_overfit_filters(system: SystemFilter) -> int:
    """D-06 counting rule. Per-field booleans/optionals count as 1 each;
    teams/conferences/seasons/weeks and each op="in" FeatureFilter count
    every individual selected value; providers (also set-valued) counts
    as 1 if non-empty, per D-06's explicit example."""
    count = 0
    for flag in (system.favorite, system.underdog, system.home, system.away):
        if flag:
            count += 1
    for value in (system.min_spread, system.max_spread, system.min_total, system.max_total):
        if value is not None:
            count += 1
    if system.providers:
        count += 1
    for values in (system.teams, system.conferences, system.seasons, system.weeks):
        count += len(values)
    for filt in system.feature_filters:
        if filt.op == "in" and isinstance(filt.value, (list, tuple, set)):
            count += len(filt.value)
        else:
            count += 1
    return count


def compute_grade(result: BacktestResult, system: SystemFilter) -> str | None:
    if result.bets == 0:
        return None
    decided = result.wins + result.losses
    stats = result.stats  # always populated by run_backtest
    profitable, total_seasons = sign_consistency(result.season_breakdown)
    scores = [
        _sample_size_score(decided),
        _roi_significance_score(stats.z_score),
        _consistency_score(profitable, total_seasons),
        _permutation_score(stats.permutation_p_value),
        _overfit_score(count_overfit_filters(system)),
    ]
    composite = sum(scores) / len(scores)
    for threshold, letter in _GRADE_BANDS:
        if composite >= threshold:
            return letter
    return "F"  # unreachable given the 0.00 floor band, kept for exhaustiveness
```

```html
<!-- Source: templates/index.html, existing chip pattern (Phase 1) -->
<article><span>Grade</span><strong>{{ grade if grade else "&mdash;"|safe }}</strong></article>
<!-- NOTE: do not literally pipe grade through |safe. Grade is always one of
     A/B/C/D/F/None from compute_grade — render it through normal Jinja
     auto-escaping like every other chip value (STATE.md Phase 1 rule).
     The em-dash fallback can stay a literal &mdash; entity as it already is. -->
```

**Fade toggle control — DOM placement without a second `<form>`:**
```html
<!-- Source: this phase's design, HTML5 form= attribute, no new JS needed -->
<!-- sidebar form gets an id -->
<form method="get" class="filters" id="filters-form" autocomplete="off"> ... </form>

<!-- inside the workspace stat-chips section, physically near the Grade chip -->
<label class="fade-toggle">
  <input type="checkbox" name="fade" form="filters-form" {% if form.fade %}checked{% endif %}>
  Fade System
</label>
```
This keeps the toggle in the DOM location D-01 asks for ("near the stat chips") while it still submits with the single existing GET form — no client-side JS, consistent with "vanilla JS/CSS, no frontend framework" and the app's existing full-reload-on-submit pattern (no control auto-submits today; Fade following that convention is the minimal, consistent choice).

### Anti-Patterns to Avoid
- **Flipping `system.side`/`system.total_side` before calling `matches_system`:** breaks D-03's "same matched games" contract — `favorite`/`underdog`/`home`/`away` filters are side-dependent, so flipping before matching silently changes which games are included, not just which side is graded.
- **Mutating a frozen `SystemFilter` in place:** every domain type is `@dataclass(frozen=True)`; use `dataclasses.replace(system, fade=True)` if a copy-with-change is ever needed (it isn't, for this phase — `fade` is just read, never written mid-pipeline).
- **`payload["fade"]` instead of `payload.get("fade", False)` in `_system_from_dict`:** any system saved before this phase ships has no `"fade"` key; a direct index raises `KeyError` on load.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Statistical significance of the edge | A new hypothesis test | `SystemStats.z_score` / `.permutation_p_value` / `.wilson_low`/`.wilson_high` (already computed in `compute_system_stats`) | These are already validated, tested (`tests/test_backtest.py`), and used elsewhere (CLI output, web stats panel) — Grade should consume them, not recompute |
| Season-by-season consistency | A new season-grouping loop | `sign_consistency(result.season_breakdown)` (already exists, already imported in `web.py`) | Single source of truth for "profitable N of M seasons" |
| Boolean form-field parsing | A new truthiness convention | `request.form.get("fade") == "on"` (exact pattern already used for `favorite`/`underdog`/`home`/`away`) | `bool(request.form.get("x"))` is a well-known Flask footgun — an empty string from an unchecked-but-present field is still truthy; the codebase's own `== "on"` pattern avoids this and must be matched exactly for consistency |
| JSON backward compatibility | A schema-versioning mechanism | `.get(key, default)` at load time (already the pattern used for `theory` in `storage.py:_system_from_dict`/`load_saved_system`) | The project has one established migration idiom for new optional fields; reuse it rather than introducing a new one |

**Key insight:** every piece of this phase's "hard part" (statistics, season grouping, backward-compat defaults, boolean parsing) already has an established, tested implementation elsewhere in this same codebase. The work is composition, not invention.

## Common Pitfalls

### Pitfall 1: An existing test breaks the moment Grade renders a real value
**What goes wrong:** `tests/test_web.py:134` currently asserts `'<article><span>Grade</span><strong>&mdash;</strong></article>' in metrics_html`. Once `compute_grade` returns a letter for the default sample-data system, this assertion fails.
**Why it happens:** Phase 1 shipped the em-dash placeholder and pinned it in a test; this phase's whole purpose is to replace that placeholder.
**How to avoid:** Treat updating this assertion as a required task, not an incidental side effect. Line 131's chip-label list assertion (`["Record", "Margin", "Money Won", "ROI", "Grade"]`) is unaffected and should stay as-is.
**Warning signs:** `pytest tests/test_web.py -k test_web_index_loads_filters_and_default_results` failing after the Grade chip change is expected and must be fixed in the same plan wave, not left red.

### Pitfall 2: Fade leaking into `matches_system`
**What goes wrong:** If a developer's first instinct is "fade = flip `system.side`", and that flipped `SystemFilter` gets passed into `matches_system` (e.g. by building a temporary faded copy of the system before the whole pipeline runs), the matched-game count changes whenever `favorite`/`underdog`/`home`/`away`/team-conference filters are active — silently violating "same matched games."
**Why it happens:** It looks like the simpler implementation (one flipped `SystemFilter` object, reuse the whole pipeline unchanged) — but the pipeline's matching step is side-aware in ways that only became apparent from reading `matches_system` directly (lines 119–120, 129–136 of `backtest.py`).
**How to avoid:** Fade is read exclusively inside `grade_bet`/`_grade_total_bet`, never passed as a "flip the system" transform upstream of `matches_system`.
**Warning signs:** A test that asserts `run_backtest(games, system).bets == run_backtest(games, replace(system, fade=True)).bets` failing.

### Pitfall 3: `fade` dropped from query-string round-trips
**What goes wrong:** `web.py:_query_args_from_form` builds the base query string used for tab-switch links and remove-filter links (`_query_href_removing`). If `fade` isn't added there, switching tabs or removing any other filter on a faded, loaded system silently un-fades it (the URL loses `fade=on`).
**Why it happens:** This function enumerates form fields explicitly (`favorite`, `underdog`, `home`, `away`, ranges, etc.) — a new boolean field must be added to that same list, it isn't picked up automatically. `theory` had the identical gap and was fixed the same way (visible in the existing `theory` handling in the same function).
**How to avoid:** Add `fade` to `_query_args_from_form`'s boolean-flags loop (`for key in ("favorite", "underdog", "home", "away", "fade")`) in the same change that adds it to `_form_values`/`_form_values_from_post`/`_form_from_system`/`_system_from_form`.
**Warning signs:** A test that saves a faded system, loads it, clicks any remove-filter link or tab-switch link, and asserts `fade` is still `on` in the resulting page — analogous to the existing `test_web_tab_switch_preserves_load_system_and_round_trips` and `test_web_loaded_system_remove_link_materializes_and_drops_load_system` tests for `theory`.

### Pitfall 4: Grade sub-score boundary inconsistency
**What goes wrong:** Mixing `<` and `<=` inconsistently across the five threshold ladders produces off-by-one grade flips at exact boundary values (e.g. `z_score == 1.645` landing in the wrong band).
**Why it happens:** Five separate tiered functions, each with its own boundary list, invite copy-paste drift.
**How to avoid:** Every threshold function in this document uses strict `<` for "below this tier" checks in ascending order, falling through to the highest tier — write one boundary test per function (test the exact threshold value and one value on each side).
**Warning signs:** A test asserting `_roi_significance_score(1.645) == 0.75` (not `0.5`) failing.

## Code Examples

Already inlined above under Architecture Patterns (Pattern 1 and Pattern 2) — this phase has no external API to demonstrate; all "verified" code is either read directly from the existing codebase or is this phase's own new pure-function design, documented once rather than duplicated here.

## State of the Art

Not applicable — no external library or API version drift to track. This phase's only "state of the art" concern is internal: the grade formula is a new, explicitly-versioned design (this document *is* the spec for it), not an adoption of an external changing standard.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `SystemStats.z_score` (hit-rate z-test) is the right field for the roadmap's "ROI z-score" input, not `SystemStats.roi_t_stat` | Architecture Patterns → Pattern 2, `_roi_significance_score` | Low-medium: if the user actually meant the ROI t-stat (a different null hypothesis, per-bet-return based), the grade's second sub-score would be measuring something else. Both fields exist and are documented in the code with the rationale given here, so switching is a one-line change if flagged during planning/discuss. |
| A2 | Zero matched bets (`result.bets == 0`) should render Grade as `&mdash;` (no data), not `F` (graded and failing) | Architecture Patterns → Pattern 2 | Low: cosmetic only, mirrors the existing `Margin`/`Money Won` empty-state convention already in the template; easy to flip to `F` if the user disagrees. |
| A3 | Equal-weighted average (not "worst-of") is the composite combination rule | Standard Stack → Alternatives Considered, Pattern 2 | Medium: worst-of is a materially harsher rule for the overfitting sub-score specifically (a badly overfit but otherwise strong system would go straight to F). D-05 explicitly delegates this choice to Claude, so this is a documented design decision rather than an unconfirmed fact — flagged here so it's visible during plan review, not because it needs a new user decision. |
| A4 | Overfit-count tier boundaries (3/7/14/24) and all five sub-score tier boundaries are original to this phase, not derived from Bet Labs' actual (proprietary, unobserved) algorithm | Architecture Patterns → Pattern 2 | Low: D-06 only specifies the *counting* rule precisely (which is followed exactly); the *scoring bands* built on top of that count are necessarily invented, since Bet Labs' internal grading algorithm isn't published. Documented explicitly so it reads as a deliberate, adjustable constant table, not a researched fact. |
| A5 | The Fade checkbox uses the HTML5 `form="filters-form"` attribute (no client JS) to place it near the stat chips while submitting with the existing sidebar form | Architecture Patterns → Fade toggle control | Low: purely a UI wiring choice within D-01's "Claude's discretion" grant for styling/wording; if it doesn't fit visually, an alternative is a second tiny `<form>` posting only `fade` via query-string merge, at the cost of one more moving part. |

## Open Questions

1. **Should `cli.py`'s `backtest` subcommand get a `--fade` flag?**
   - What we know: CONTEXT.md's Integration Points note flags this as "not required by roadmap success criteria, which are UI-only" but worth checking CLI test backward compatibility.
   - What's unclear: whether the user wants CLI/UI parity in this phase or a later one.
   - Recommendation: add it — it's a ~4-line addition (one `argparse` flag + one `SystemFilter(fade=args.fade, ...)` kwarg in `_backtest()`) with no interaction risk, and leaving `SystemFilter.fade` unreachable from the CLI would create an inconsistent surface. Low-cost, low-risk; include as a plan task but not a blocking one.

## Environment Availability

Not applicable — no external tools, services, runtimes, or CLIs beyond what Phase 1 already required (Python, Flask, pytest — all already verified present by Phase 1's own execution). No new dependency to probe.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already vendored; `pytest.ini` sets `testpaths=tests`) |
| Config file | `pytest.ini` (repo root) |
| Quick run command | `python -m pytest tests/test_backtest.py tests/test_storage.py tests/test_web.py -q` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTG-01 | Fade flips graded side; matched-game count is unchanged; pushes stay pushes | unit | `python -m pytest tests/test_backtest.py -k fade -x` | ❌ Wave 0 (new test function in existing `tests/test_backtest.py`) |
| INTG-01 | `fade` persists through `save_system`/`load_saved_system` JSON round-trip, defaults `False` for pre-phase saved-system JSON missing the key | unit | `python -m pytest tests/test_storage.py -k fade -x` | ❌ Wave 0 (new test function in existing `tests/test_storage.py`) |
| INTG-01 | Fade checkbox state round-trips through GET form, POST /save, tab-switch links, and remove-filter links (mirrors the existing `theory` round-trip tests) | integration | `python -m pytest tests/test_web.py -k fade -x` | ❌ Wave 0 (new test functions in existing `tests/test_web.py`) |
| INTG-02 | Each of the 5 sub-score helper functions returns the documented value at and around its threshold boundaries | unit | `python -m pytest tests/test_backtest.py -k grade -x` | ❌ Wave 0 (new test functions in existing `tests/test_backtest.py`) |
| INTG-02 | `compute_grade` returns the correct letter for representative composite scores, and `None` for zero matched bets | unit | `python -m pytest tests/test_backtest.py -k compute_grade -x` | ❌ Wave 0 |
| INTG-02 | `count_overfit_filters` follows D-06's counting rule exactly (per-field=1, teams/conferences/seasons/weeks/`in`-list values counted individually, `providers` counts as 1 non-empty) | unit | `python -m pytest tests/test_backtest.py -k overfit -x` | ❌ Wave 0 |
| INTG-02 | Grade chip renders the computed letter (or em-dash) in `templates/index.html`; existing `test_web.py:134` assertion updated to match | integration | `python -m pytest tests/test_web.py -k grade -x` | ❌ Wave 0 (modifies existing test) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_backtest.py tests/test_storage.py tests/test_web.py -q`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_backtest.py` — add fade-flip tests (spread + total), add 5 sub-score boundary tests, add `compute_grade` composite tests, add `count_overfit_filters` D-06 rule tests
- [ ] `tests/test_storage.py` — add fade JSON round-trip test, add backward-compat "missing fade key defaults False" test
- [ ] `tests/test_web.py` — add fade checkbox round-trip tests (save/load, tab-switch, remove-filter-link preservation, mirroring the existing `theory` tests), update the existing Grade em-dash assertion at line 134
- [ ] Framework install: none — pytest already present, no config changes needed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | Single-user local tool, no auth surface (established in Phase 1) |
| V3 Session Management | no | No sessions in this app |
| V4 Access Control | no | No access boundaries within a single-user local tool |
| V5 Input Validation | yes | `fade` boolean parsed via the existing `request.form.get("fade") == "on"` string-comparison pattern (identical to `favorite`/`underdog`/`home`/`away`) — no free-text, no injection surface, bounded to `True`/`False` |
| V6 Cryptography | no | No crypto surface introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Reflected/stored XSS via server-rendered free text | Tampering | Not newly relevant here — `Grade` is always one of a fixed 6-value set (`A`/`B`/`C`/`D`/`F`/`None`→em-dash) produced entirely server-side by `compute_grade`, never user-supplied text; render it through normal Jinja auto-escaping (no `\|safe`), consistent with the Phase 1 STATE.md decision that `theory` and all href construction avoid `\|safe` |
| Boolean-field truthiness bug (empty-string-is-truthy) | — (correctness, not a STRIDE threat, but flagged since it's a real footgun in this exact codebase) | Match the established `value == "on"` pattern exactly for `fade`, not `bool(request.form.get(...))` |

## Sources

### Primary (HIGH confidence — direct codebase reads this session)
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\backtest.py` — `run_backtest`, `matches_system`, `grade_bet`, `_grade_total_bet`, `compute_system_stats`, `sign_consistency`, `compute_season_breakdown`, `_side_spread`, `_wilson_interval`, `_hit_rate_z_test`, `_permutation_p_value`
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\models.py` — all frozen dataclasses (`SystemFilter`, `SystemStats`, `BetDetail`, `SeasonRecord`, `BacktestResult`, `SavedSystem`)
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\storage.py` — `save_system`, `load_saved_system`, `_system_to_dict`, `_system_from_dict` (backward-compat `.get()` pattern for `theory`)
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\web.py` — `_form_values`, `_form_values_from_post`, `_form_from_system`, `_system_from_form`, `_query_args_from_form`, `index()` route
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\cli.py` — `_backtest`, `_build_parser` (`backtest` subcommand args)
- `C:\Users\mckel\dev\cfb-site\cfb_system_maker\templates\index.html` — stat-chips section (line 227–233), sidebar filters form
- `C:\Users\mckel\dev\cfb-site\tests\test_backtest.py`, `test_storage.py`, `test_web.py`, `test_cli.py` — existing test conventions and the specific breaking assertion at `test_web.py:134`
- `.planning/phases/02-integrity-fade-grade/02-CONTEXT.md` — locked decisions D-01 through D-07
- `.planning/REQUIREMENTS.md` — INTG-01, INTG-02 text
- `.planning/STATE.md` — Phase 1 carried-forward decisions (no `\|safe`, T-01-03 accepted risk)
- `docs/bet-labs-parity-plan.md` — items 9–10 (Fade System toggle, System Grade design intent), "27 pitchers hand-picked" overfitting example, "fade of a 60% system grades ~40%... pushes unchanged" test expectation

### Secondary (MEDIUM confidence)
- [Z Critical Value Calculator](https://zscorecalculator.net/zcritical) — confirms 1.645 (90% one-tailed) and 1.96 (95% two-tailed) as the standard critical values used in `_roi_significance_score`'s tier boundaries
- [Confidence Interval Critical Values table (Crafton Hills College)](https://www.craftonhills.edu/current-students/tutoring-center/mathematics-tutoring/distribution_tables_normal_studentt_chisquared.pdf) — standard normal distribution reference table

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all reused code read directly from the repository this session
- Architecture: HIGH — fade design is forced by D-03's explicit wording and verified against the actual `matches_system`/`grade_bet` source; grade design is original but every threshold is stated explicitly and testable
- Pitfalls: HIGH — all four pitfalls are grounded in specific line-level codebase reads (existing test assertion, existing `_query_args_from_form` field-enumeration pattern, existing frozen-dataclass convention)

**Research date:** 2026-07-17
**Valid until:** No external expiry — this research is tied to the current state of the local codebase, not to any external library version. Re-verify only if `backtest.py`/`models.py`/`web.py` change materially before this phase is planned.
