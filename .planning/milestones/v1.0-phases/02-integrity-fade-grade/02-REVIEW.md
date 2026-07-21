---
phase: 02-integrity-fade-grade
reviewed: 2026-07-17T11:01:20Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - cfb_system_maker/backtest.py
  - cfb_system_maker/cli.py
  - cfb_system_maker/models.py
  - cfb_system_maker/storage.py
  - cfb_system_maker/templates/index.html
  - cfb_system_maker/web.py
  - tests/test_backtest.py
  - tests/test_cli.py
  - tests/test_storage_systems.py
  - tests/test_web.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-17T11:01:20Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the fade toggle (`SystemFilter.fade`) and composite Grade (`compute_grade`) features plus the files that carry them (models, backtest, cli, storage, web, templates, and their tests). The two headline correctness invariants called out in scope both hold up under direct testing:

- `matches_system` never references `.fade` — confirmed by reading the function body and by `test_fade_does_not_change_matched_bet_count`. Fade only flips the graded side inside `grade_bet`/`_grade_total_bet`.
- Zero-bet edge cases in `compute_grade` are handled without division-by-zero: `result.bets == 0` returns `None` immediately, and the degenerate "matched bets but zero decided" (all-push) case was hand-verified to produce a stable `"F"` grade with no exception (`_wilson_interval`/`_hit_rate_z_test`/`_permutation_p_value` all short-circuit on `n == 0`).
- The Grade chip in `templates/index.html` renders `result.grade` through plain Jinja substitution with no `|safe` anywhere near it (auto-escaping intact), matching the existing Margin chip's em-dash convention.
- `count_overfit_filters` never counts `system.fade`, matching D-06 and its dedicated test.

However, the review surfaced one critical, exploit-confirmed security defect in `storage.py`/`web.py` (present in code this phase touches — `load_saved_system` is new, `save_system`/`load_system` are pre-existing but now reachable via the phase's new theory/fade round-trip paths), plus two lower-severity issues: a statistically weak spot in the Grade rubric's equal-weighted average, and pre-existing unhandled-exception paths for malformed numeric query params.

## Critical Issues

### CR-01: Path traversal in system save/load allows arbitrary file read and write

**File:** `cfb_system_maker/storage.py:79-107` (also exercised via `cfb_system_maker/web.py:110-117` `/save` route and `cfb_system_maker/web.py:64-72` `/` `load_system` query param, and `/compare?system=`)

**Issue:** `save_system`, `load_system`, and the new `load_saved_system` all build a filesystem path directly from a caller-supplied `name` with no validation:

```python
path = Path(data_dir) / "systems" / f"{name}.json"
```

`name` comes straight from user input — the `save_name` POST field (`web.py:113`, `_form_values_from_post`) and the `load_system` GET query parameter (`web.py:64`, also `/compare`'s `?system=` list). Because `Path.__truediv__` happily accepts `..` segments, a crafted name escapes both the `systems/` directory and `data_dir` itself.

Confirmed with a live `Flask` test client against `create_app`:

```python
client.post("/save", data={"save_name": "../../outside_secret", "bet_type": "spread", "side": "home", "total_side": "over"})
# -> overwrites <data_dir>/../../outside_secret.json with attacker-controlled JSON content
```

This produced a real file write outside the sandboxed `data_dir` in a local repro. The read side is equally exploitable:

```python
client.get("/?load_system=../../secret_system")
# -> loads and renders the "theory" field of an arbitrary JSON file elsewhere on disk
```

Both were reproduced end-to-end (arbitrary overwrite of a sibling-directory file via `/save`; arbitrary read-and-render of a sibling-directory file's `theory` field via `/?load_system=`). This is a classic CWE-22 (path traversal) that becomes CWE-73 (arbitrary file write) on the save path. Anyone who can reach the Flask app (including `--host 0.0.0.0` deployments, which the CLI supports via `--host`) can overwrite arbitrary `.json`-suffixed files reachable by the process, or exfiltrate the contents of any file it can coerce this loader to parse as JSON.

**Fix:** Reject `name` values that aren't a bare filename before building the path — e.g.:

```python
import re

_SYSTEM_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

def _safe_system_name(name: str) -> str:
    if not _SYSTEM_NAME_RE.match(name):
        raise ValueError(f"invalid system name: {name!r}")
    return name
```

and call it at the top of `save_system`, `load_system`, and `load_saved_system` before constructing `path`. In `web.py`, catch the resulting `ValueError` the same way `FileNotFoundError` is already caught (treat it as "system not found" / silently drop the save) so malformed input degrades gracefully instead of 500ing or succeeding maliciously.

## Warnings

### WR-01: Equal-weighted Grade average lets sub-30-decided-bet systems earn a "B"

**File:** `cfb_system_maker/backtest.py:186-203` (`compute_grade`)

**Issue:** `_sample_size_score` is explicitly designed to zero out when `decided < 30` ("the Wilson interval itself is unreliable, so no margin can rescue the score" — per the phase plan). But `compute_grade` only ever uses that 0.0 as 1 of 5 equally-weighted inputs to a plain average, so a small, statistically fragile sample can still be graded "B" if the other four sub-scores (ROI z-score, season sign-consistency, permutation p-value, overfit penalty) happen to look good — which is common with small samples because they're all derived from the same handful of bets and are prone to exactly the kind of small-sample luck the 30-bet floor exists to guard against.

Reproduced directly: a system with 10 decided bets (9-1, a `low_sample=True` sample by the codebase's own definition) scores `sample=0.0, roi=1.0, consistency=1.0, permutation=1.0, overfit=1.0` → average `0.8` → **grade "B"**, while the same UI simultaneously flags "Low sample warning (<30 decided bets)" a few lines below the Grade chip. A user skimming the Grade chip alone has no signal that the letter grade papers over an unreliable sample.

```python
stats = compute_system_stats(details, hit_rate=0.9, roi=0.7182, american_odds=-110, stake=1.0)
# stats.wilson_low=0.5958 (decided=10 -> _sample_size_score forces 0.0 regardless)
compute_grade(result, SystemFilter(side="home"))  # -> "B"
```

Note: the phase plan (`02-02-PLAN.md`) documents the equal-weighted-average-not-worst-of choice as an explicit, discretionary decision (D-05), so this is not a deviation from spec — but it is a real, demonstrable behavior that undercuts the stated purpose of the sample-size sub-score ("below this floor... no margin can rescue the score"), and is worth a second look before this ships as a trust signal to end users.

**Fix:** If the intent really is "small samples can never earn a strong grade," floor the composite instead of averaging it in — e.g. `min(scores)` when `decided < 30`, or cap the letter band at "C" whenever `stats.low_sample` is true, regardless of the other four sub-scores. If the current equal-weighted behavior is intentional (composite confidence score rather than a hard sample-size gate), consider surfacing that nuance in the UI (e.g., a low-sample qualifier on the Grade chip itself) rather than only in the separate stats panel.

### WR-02: Malformed numeric query/form params crash the index page with a 500

**File:** `cfb_system_maker/web.py:448-458` (`_parse_filter_value`), `cfb_system_maker/web.py:494-503` (`_int_set`, `_optional_float`)

**Issue:** Unlike `_valid_choice` (added this phase for `side`/`bet_type`/`total_side`, which falls back to a default on bad input), the numeric parsing helpers raise unhandled `ValueError`s that propagate straight to a Flask 500:

```python
client.get("/?min_spread=abc")            # -> 500, ValueError: could not convert string to float: 'abc'
client.get("/?filter_seasons=abc")        # -> 500, ValueError: invalid literal for int() with base 10: 'abc'
client.get("/?ff_op=gte&ff_value=notanumber&...")  # -> 500
```

All three were reproduced against a live `create_app` test client. This is pre-existing code untouched by this phase's diff, but it sits directly alongside the newly-hardened `_valid_choice` pattern in the same file, so the inconsistency is now more visible: some malformed inputs degrade gracefully (enum fields) while others take the whole page down.

**Fix:** Wrap the `float(...)`/`int(...)` conversions the same way `_valid_choice` guards enum fields — return `None`/skip the value on a `ValueError` instead of letting it propagate:

```python
def _optional_float(value: str) -> float | None:
    if not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None
```

## Info

### IN-01: `_roi_significance_score` credits an undefined z-score in the all-push (zero-decided-bets) case

**File:** `cfb_system_maker/backtest.py:124-133` (`_roi_significance_score`), `cfb_system_maker/backtest.py:430-438` (`_hit_rate_z_test`)

**Issue:** When `decided == 0` (e.g., a system whose only matched bets are pushes), `_hit_rate_z_test` returns a sentinel `z_score = 0.0` because there's no real statistic to compute. `compute_grade` feeds that sentinel straight into `_roi_significance_score`, which treats `z_score = 0.0` as a genuine (weak but real) result and awards `0.2` rather than treating "no decided bets" as undefined/zero. In practice this never changes the final letter (the `_sample_size_score` term is already `0.0` for `decided < 30`, which includes `decided == 0`), so this is cosmetic today, but it's a latent trap if the grading rubric or thresholds are ever revisited independently of the sample-size gate.

**Fix:** Have `compute_grade` special-case `decided == 0` (distinct from `bets == 0`, which already returns `None`) and skip/zero the ROI-significance and permutation sub-scores explicitly, rather than relying on downstream sentinel values from `_hit_rate_z_test`/`_permutation_p_value` to "happen" to be inert.

---

_Reviewed: 2026-07-17T11:01:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
