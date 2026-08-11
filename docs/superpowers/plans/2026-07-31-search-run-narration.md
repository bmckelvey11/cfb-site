# Search Run Narration (P2-001) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a `search` CLI run's full top-K finalist list (candidates, holdout stats, raw/corrected p-values) to disk, add a web view to see it, and add an opt-in "Narrate results" button that sends only that already-computed data to the Anthropic API for a one-shot plain-English summary.

**Architecture:** `search.py`'s `grade_finalists` output (`FinalistGradingResult`) is currently transient — `cli.py`'s `_search` prints it and only saves the single winning `SystemFilter` via `save_system`. This plan adds a `SearchRun` persistence layer (`storage.py`) that serializes the full `FinalistGradingResult` (plus effective params) to `data/search_runs/<run_id>.json`, a new `search --save-run <name>` CLI flag to write it, a `GET /search-runs/<name>` Flask route + template to view it (stat table per finalist, theory-panel-style layout), and a `POST /search-runs/<name>/narrate` route that builds a text summary of the already-persisted run and makes exactly one Anthropic API call, returned as JSON for a small fetch-driven collapsible `<details>` block. No LLM involvement anywhere in beam_search/grade_finalists — narration reads persisted output only, after the fact.

**Tech Stack:** Python 3, Flask, vanilla JS/fetch (no framework), `anthropic` Python SDK (already present in this environment; pinned in requirements.txt for the record), pytest.

## Global Constraints

- Narration triggers only on an explicit user action — never automatic on page load (P2-001 AC).
- Exactly one LLM call per explicit "Narrate results" click — no chained/looping calls (P2-001 AC).
- The LLM call receives only already-computed stats (candidate list, holdout results, raw/corrected p-values, grades) as input text — no LLM call anywhere in beam_search/grade_finalists/candidate selection (P2-001 AC).
- Rendered as a `theory-panel`-style collapsible block appended to the run view, reusing existing `.theory-panel` CSS classes for visual consistency (P2-001 Design note).
- LLM call failure/timeout degrades gracefully: the results view remains fully usable without narration; no server 500, no unhandled page error (P2-001 AC).
- API key resolution mirrors the existing `cfbd_client.find_cfbd_token` convention: env var first (`ANTHROPIC_API_KEY`), then `env.env` file, same file already gitignored — never commit or echo the key.
- System/run names go through the existing `_safe_system_name` gate (`^[A-Za-z0-9_-]+$`) — no path traversal.
- `data/` is gitignored; `data/search_runs/` needs no new gitignore entry.

---

## File Structure

- **`cfb_system_maker/storage.py`** (modify): add `save_search_run`, `load_search_run`, `list_search_runs` — same JSON-per-record pattern as `save_system`/`load_saved_system`, under `data/search_runs/<name>.json`. Reuses `_safe_system_name`.
- **`cfb_system_maker/models.py`** (modify): add two frozen dataclasses, `SearchRunFinalist` and `SearchRun`, as the persisted/serializable shape (distinct from `search.py`'s in-memory `GradedFinalist`/`FinalistGradingResult`, which stay runtime-only and unchanged).
- **`cfb_system_maker/cli.py`** (modify): add `--save-run NAME` option to the `search` subcommand; on success, call `save_search_run`.
- **`cfb_system_maker/narration.py`** (new): the single Anthropic API call — builds a plain-text prompt from a `SearchRun`, calls the API with a short timeout, returns narration text or raises a caught exception type. No Flask/CLI imports; unit-testable with an injectable client.
- **`cfb_system_maker/web.py`** (modify): add `GET /search-runs/<name>` (render run view) and `POST /search-runs/<name>/narrate` (call narration, return JSON).
- **`cfb_system_maker/templates/search_run.html`** (new): run view — stat table of finalists, theory-panel-style collapsible narration block, "Narrate results" trigger button.
- **`cfb_system_maker/static/narrate.js`** (new): fetch-driven trigger for the narrate button, mirrors `filter_modal.js`'s fetch+AbortController+status-text pattern.
- **`cfb_system_maker/static/styles.css`** (modify): small additions for the narration trigger/collapsible, reusing `.theory-panel`.
- **`requirements.txt`** (modify): add `anthropic`.
- **Tests:** `tests/test_storage.py` (search-run round-trip), `tests/test_cli.py` (`--save-run` flag), `tests/test_narration.py` (new — prompt building + graceful failure, injectable fake client), `tests/test_web.py` (run view route + narrate route, injectable fake narration function).

---

### Task 1: `SearchRun`/`SearchRunFinalist` models + storage round-trip

**Files:**
- Modify: `cfb_system_maker/models.py`
- Modify: `cfb_system_maker/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `cfb_system_maker.models.SystemFilter` (existing), `cfb_system_maker.storage._safe_system_name` (existing), `cfb_system_maker.storage._system_to_dict`/`_system_from_dict` internals are NOT reused directly — `SystemFilter` serialization for a finalist reuses the same field list as `_system_to_dict`'s `"system"` sub-object, written inline (see Step 3).
- Produces: `models.SearchRunFinalist(system: SystemFilter, wins: int, losses: int, pushes: int, roi: float, raw_p: float, corrected_p: float, bh_significant: bool)`; `models.SearchRun(name: str, saved_at: str, candidates_tested: int, finalists_graded: int, effective_params: dict[str, int | float], finalists: tuple[SearchRunFinalist, ...])`; `storage.save_search_run(name: str, run: SearchRun, data_dir: str | Path) -> Path`; `storage.load_search_run(name: str, data_dir: str | Path) -> SearchRun`; `storage.list_search_runs(data_dir: str | Path) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py (append)

def test_save_and_load_search_run_round_trips(tmp_path):
    from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
    from cfb_system_maker.storage import save_search_run, load_search_run, list_search_runs

    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12,
        losses=8,
        pushes=1,
        roi=0.0524,
        raw_p=0.031,
        corrected_p=0.062,
        bh_significant=False,
    )
    run = SearchRun(
        name="my-run",
        saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482,
        finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )

    save_search_run("my-run", run, tmp_path)
    loaded = load_search_run("my-run", tmp_path)

    assert loaded.name == "my-run"
    assert loaded.candidates_tested == 482
    assert loaded.finalists_graded == 1
    assert loaded.effective_params["beam_width"] == 100
    assert len(loaded.finalists) == 1
    assert loaded.finalists[0].wins == 12
    assert loaded.finalists[0].corrected_p == 0.062
    assert loaded.finalists[0].system.bet_type == "spread"
    assert loaded.finalists[0].system.favorite is True
    assert list_search_runs(tmp_path) == ["my-run"]


def test_load_search_run_missing_file_raises(tmp_path):
    from cfb_system_maker.storage import load_search_run

    with pytest.raises(FileNotFoundError):
        load_search_run("nope", tmp_path)


def test_save_search_run_rejects_unsafe_name(tmp_path):
    from cfb_system_maker.models import SearchRun
    from cfb_system_maker.storage import save_search_run

    run = SearchRun(
        name="x", saved_at="2026-07-31T00:00:00+00:00", candidates_tested=1,
        finalists_graded=0, effective_params={}, finalists=(),
    )
    with pytest.raises(ValueError):
        save_search_run("../escape", run, tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -k search_run -v`
Expected: FAIL with `ImportError`/`AttributeError` — `SearchRun`, `SearchRunFinalist`, `save_search_run`, `load_search_run`, `list_search_runs` don't exist yet.

- [ ] **Step 3: Add the models**

In `cfb_system_maker/models.py`, after the `SavedSystem` dataclass, add:

```python
@dataclass(frozen=True)
class SearchRunFinalist:
    system: SystemFilter
    wins: int
    losses: int
    pushes: int
    roi: float
    raw_p: float
    corrected_p: float
    bh_significant: bool


@dataclass(frozen=True)
class SearchRun:
    name: str
    saved_at: str
    candidates_tested: int
    finalists_graded: int
    effective_params: dict
    finalists: tuple[SearchRunFinalist, ...] = ()
```

- [ ] **Step 4: Add storage functions**

In `cfb_system_maker/storage.py`, add `SearchRun`/`SearchRunFinalist` to the existing import line from `cfb_system_maker.models`, then append:

```python
def _finalist_system_to_dict(system: SystemFilter) -> dict[str, Any]:
    return {
        "bet_type": system.bet_type,
        "side": system.side,
        "total_side": system.total_side,
        "seasons": sorted(system.seasons),
        "weeks": sorted(system.weeks),
        "teams": sorted(system.teams),
        "conferences": sorted(system.conferences),
        "favorite": system.favorite,
        "underdog": system.underdog,
        "home": system.home,
        "away": system.away,
        "fade": system.fade,
        "providers": sorted(system.providers),
        "min_spread": system.min_spread,
        "max_spread": system.max_spread,
        "min_total": system.min_total,
        "max_total": system.max_total,
        "feature_filters": [
            {"key": f.key, "op": f.op, "value": f.value, "perspective": f.perspective}
            for f in system.feature_filters
        ],
    }


def _finalist_system_from_dict(payload: dict[str, Any]) -> SystemFilter:
    return SystemFilter(
        bet_type=payload.get("bet_type", "spread"),
        side=payload.get("side", "home"),
        total_side=payload.get("total_side", "over"),
        seasons=set(payload.get("seasons", [])),
        weeks=set(payload.get("weeks", [])),
        teams=set(payload.get("teams", [])),
        conferences=set(payload.get("conferences", [])),
        favorite=payload.get("favorite", False),
        underdog=payload.get("underdog", False),
        home=payload.get("home", False),
        away=payload.get("away", False),
        fade=payload.get("fade", False),
        providers=set(payload.get("providers", [])),
        min_spread=payload.get("min_spread"),
        max_spread=payload.get("max_spread"),
        min_total=payload.get("min_total"),
        max_total=payload.get("max_total"),
        feature_filters=tuple(
            FeatureFilter(key=f["key"], op=f["op"], value=f["value"], perspective=f.get("perspective", "single"))
            for f in payload.get("feature_filters", [])
        ),
    )


def save_search_run(name: str, run: SearchRun, data_dir: str | Path) -> Path:
    name = _safe_system_name(name)
    payload = {
        "name": run.name,
        "saved_at": run.saved_at,
        "candidates_tested": run.candidates_tested,
        "finalists_graded": run.finalists_graded,
        "effective_params": run.effective_params,
        "finalists": [
            {
                "system": _finalist_system_to_dict(f.system),
                "wins": f.wins,
                "losses": f.losses,
                "pushes": f.pushes,
                "roi": f.roi,
                "raw_p": f.raw_p,
                "corrected_p": f.corrected_p,
                "bh_significant": f.bh_significant,
            }
            for f in run.finalists
        ],
    }
    path = Path(data_dir) / "search_runs" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_search_run(name: str, data_dir: str | Path) -> SearchRun:
    name = _safe_system_name(name)
    path = Path(data_dir) / "search_runs" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SearchRun(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        candidates_tested=int(payload.get("candidates_tested", 0)),
        finalists_graded=int(payload.get("finalists_graded", 0)),
        effective_params=payload.get("effective_params", {}),
        finalists=tuple(
            SearchRunFinalist(
                system=_finalist_system_from_dict(f["system"]),
                wins=f["wins"],
                losses=f["losses"],
                pushes=f["pushes"],
                roi=f["roi"],
                raw_p=f["raw_p"],
                corrected_p=f["corrected_p"],
                bh_significant=f["bh_significant"],
            )
            for f in payload.get("finalists", [])
        ),
    )


def list_search_runs(data_dir: str | Path) -> list[str]:
    runs_dir = Path(data_dir) / "search_runs"
    if not runs_dir.exists():
        return []
    return sorted(path.stem for path in runs_dir.glob("*.json"))
```

Note: `load_search_run` on a missing file raises `FileNotFoundError` naturally from `path.read_text()` — no explicit check needed, matching `load_system`'s existing behavior.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_storage.py -k search_run -v`
Expected: 3 passed

- [ ] **Step 6: Run full storage test file to check no regressions**

Run: `python -m pytest tests/test_storage.py -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/models.py cfb_system_maker/storage.py tests/test_storage.py
git commit -m "feat(P2-001): add SearchRun persistence for full top-K finalist lists"
```

---

### Task 2: `search --save-run` CLI flag

**Files:**
- Modify: `cfb_system_maker/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `storage.save_search_run` (Task 1), `models.SearchRun`/`SearchRunFinalist` (Task 1), existing `grading: FinalistGradingResult` and `beam_result: BeamSearchResult` locals already computed in `_search`.
- Produces: `search --save-run NAME` CLI flag; on success, a `data/search_runs/NAME.json` file readable via `storage.load_search_run`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py (append)

def test_search_command_save_run_flag_persists_full_finalist_list(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "30",
            "--save-run", "my-run",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Saved run as my-run" in captured

    from cfb_system_maker.storage import load_search_run

    run = load_search_run("my-run", tmp_path)
    assert run.candidates_tested > 0
    assert run.finalists_graded == len(run.finalists)
    assert run.effective_params["beam_width"] == 100
    if run.finalists:
        assert run.finalists[0].corrected_p >= 0.0


def test_search_command_save_run_flag_persists_even_with_zero_finalists(tmp_path, capsys, monkeypatch):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    import cfb_system_maker.cli as cli_module

    def _empty_grade_finalists(beam_result, holdout_games, holdout_feature_map, *, alpha=0.05, american_odds=-110):
        from cfb_system_maker.search import FinalistGradingResult
        return FinalistGradingResult(finalists=(), candidates_tested=beam_result.candidates_tested, finalists_graded=0)

    monkeypatch.setattr(cli_module, "grade_finalists", _empty_grade_finalists)

    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "30",
            "--save-run", "empty-run",
        ]
    )
    assert exit_code == 0

    from cfb_system_maker.storage import load_search_run

    run = load_search_run("empty-run", tmp_path)
    assert run.finalists_graded == 0
    assert run.finalists == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -k save_run -v`
Expected: FAIL — `--save-run` unrecognized argument (argparse error / exit code 2).

- [ ] **Step 3: Add the CLI flag and persistence call**

In `cfb_system_maker/cli.py`, find the `search` subparser definition (near the other `search.add_argument` calls, alongside `--save`) and add:

```python
    search.add_argument("--save-run", dest="save_run", default=None)
```

Then in `_search`, after the existing `if args.save:` block (which ends around line 352 per current numbering) and before `return 0`, add:

```python
    if args.save_run:
        from datetime import datetime, timezone

        from cfb_system_maker.models import SearchRun, SearchRunFinalist
        from cfb_system_maker.storage import save_search_run

        run = SearchRun(
            name=args.save_run,
            saved_at=datetime.now(timezone.utc).isoformat(),
            candidates_tested=beam_result.candidates_tested,
            finalists_graded=grading.finalists_graded,
            effective_params=dict(beam_result.effective_params),
            finalists=tuple(
                SearchRunFinalist(
                    system=finalist.system,
                    wins=finalist.holdout_result.wins,
                    losses=finalist.holdout_result.losses,
                    pushes=finalist.holdout_result.pushes,
                    roi=finalist.holdout_result.roi,
                    raw_p=finalist.raw_p,
                    corrected_p=finalist.corrected_p,
                    bh_significant=finalist.bh_significant,
                )
                for finalist in grading.finalists
            ),
        )
        save_search_run(args.save_run, run, args.data_dir)
        print(f"Saved run as {args.save_run} ({grading.finalists_graded} finalists)")
```

Unlike `--save` (which errors with `error=nothing_to_save` when `grading.finalists` is empty), `--save-run` persists an empty-finalists run without erroring — a zero-finalist run is still a real, inspectable result of the search, not a failure.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k save_run -v`
Expected: 2 passed

- [ ] **Step 5: Run full CLI test suite to check no regressions**

Run: `python -m pytest tests/test_cli.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/cli.py tests/test_cli.py
git commit -m "feat(P2-001): add search --save-run to persist full finalist list"
```

---

### Task 3: `narration.py` — single Anthropic API call over persisted stats

**Files:**
- Create: `cfb_system_maker/narration.py`
- Modify: `requirements.txt`
- Test: `tests/test_narration.py`

**Interfaces:**
- Consumes: `models.SearchRun`/`SearchRunFinalist` (Task 1), `describe.describe(system) -> list[dict]` (existing, for plain-English filter text per finalist).
- Produces: `narration.find_anthropic_key(env_path: str | Path = "env.env") -> str` (raises `RuntimeError` if not found); `narration.build_prompt(run: SearchRun) -> str`; `narration.NarrationError(Exception)`; `narration.narrate_run(run: SearchRun, *, client=None, api_key: str | None = None, model: str = "claude-haiku-4-5-20251001", timeout: float = 20.0) -> str` — raises `NarrationError` on any failure (missing key, API error, timeout), never lets a raw SDK exception escape.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_narration.py (new file)
from __future__ import annotations

import pytest

from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
from cfb_system_maker.narration import (
    NarrationError,
    build_prompt,
    find_anthropic_key,
    narrate_run,
)


def _sample_run():
    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12, losses=8, pushes=1, roi=0.0524,
        raw_p=0.031, corrected_p=0.062, bh_significant=False,
    )
    return SearchRun(
        name="my-run", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482, finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )


def test_build_prompt_includes_candidate_count_and_finalist_stats():
    prompt = build_prompt(_sample_run())
    assert "482" in prompt
    assert "12" in prompt and "8" in prompt
    assert "0.031" in prompt or "0.0310" in prompt
    assert "0.062" in prompt or "0.0620" in prompt


def test_build_prompt_handles_zero_finalists():
    run = SearchRun(
        name="empty", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=100, finalists_graded=0,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(),
    )
    prompt = build_prompt(run)
    assert "100" in prompt
    assert "no finalist" in prompt.lower() or "0 finalist" in prompt.lower()


def test_find_anthropic_key_from_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    assert find_anthropic_key(tmp_path / "env.env") == "test-key-123"


def test_find_anthropic_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        find_anthropic_key(tmp_path / "env.env")


class _FakeMessages:
    def __init__(self, text="Narration text.", raise_exc=None):
        self._text = text
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc:
            raise self._raise_exc
        block = type("Block", (), {"text": self._text})()
        return type("Message", (), {"content": [block]})()


class _FakeClient:
    def __init__(self, text="Narration text.", raise_exc=None):
        self.messages = _FakeMessages(text=text, raise_exc=raise_exc)


def test_narrate_run_returns_text_from_client():
    result = narrate_run(_sample_run(), client=_FakeClient(text="Some plain-English summary."))
    assert result == "Some plain-English summary."


def test_narrate_run_raises_narration_error_on_client_failure():
    with pytest.raises(NarrationError):
        narrate_run(_sample_run(), client=_FakeClient(raise_exc=RuntimeError("boom")))


def test_narrate_run_raises_narration_error_when_no_key_and_no_client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NarrationError):
        narrate_run(_sample_run())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_narration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cfb_system_maker.narration'`

- [ ] **Step 3: Add `anthropic` to requirements.txt**

```
-r cfbd-python/requirements.txt
pytest
Flask
anthropic
```

- [ ] **Step 4: Write `cfb_system_maker/narration.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

from cfb_system_maker.describe import describe
from cfb_system_maker.models import SearchRun

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_TIMEOUT = 20.0


class NarrationError(Exception):
    """Raised whenever narration cannot be produced -- missing key, API error, timeout."""


def find_anthropic_key(env_path: str | Path = "env.env") -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]

    path = Path(env_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "ANTHROPIC_API_KEY":
                return value.strip()

    raise RuntimeError("ANTHROPIC_API_KEY not found in env or env.env")


def build_prompt(run: SearchRun) -> str:
    lines = [
        "Summarize this college football betting system search run in plain English, "
        "2-4 short sentences. Be neutral and factual -- do not recommend betting real "
        "money or imply guaranteed future performance.",
        "",
        f"Candidates tested: {run.candidates_tested}",
        f"Finalists graded on holdout data: {run.finalists_graded}",
        f"Search params: {run.effective_params}",
        "",
    ]
    if not run.finalists:
        lines.append("No finalist survived holdout grading.")
        return "\n".join(lines)

    lines.append("Finalists (ranked, holdout results):")
    for i, finalist in enumerate(run.finalists, start=1):
        decided = finalist.wins + finalist.losses
        sentences = [row["text"] for row in describe(finalist.system)]
        filters_text = "; ".join(sentences) if sentences else "no filters (all games)"
        lines.append(
            f"{i}. {filters_text} -- holdout record {finalist.wins}-{finalist.losses}-{finalist.pushes} "
            f"({decided} decided), roi={finalist.roi:.4f}, raw_p={finalist.raw_p:.4f}, "
            f"corrected_p={finalist.corrected_p:.4f}, bh_significant={finalist.bh_significant}"
        )
    return "\n".join(lines)


def narrate_run(
    run: SearchRun,
    *,
    client=None,
    api_key: str | None = None,
    model: str = _DEFAULT_MODEL,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """Exactly one API call. Any failure -- missing key, network, API error -- raises NarrationError."""
    prompt = build_prompt(run)

    if client is None:
        try:
            import anthropic  # noqa: PLC0415

            key = api_key or find_anthropic_key()
            client = anthropic.Anthropic(api_key=key, timeout=timeout)
        except Exception as exc:
            raise NarrationError(f"could not create Anthropic client: {exc}") from exc

    try:
        message = client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if hasattr(block, "text"))
    except Exception as exc:
        raise NarrationError(f"narration call failed: {exc}") from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_narration.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/narration.py requirements.txt tests/test_narration.py
git commit -m "feat(P2-001): add single-call Anthropic narration over persisted search runs"
```

---

### Task 4: `GET /search-runs/<name>` view route + template

**Files:**
- Modify: `cfb_system_maker/web.py`
- Create: `cfb_system_maker/templates/search_run.html`
- Modify: `cfb_system_maker/static/styles.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `storage.load_search_run` (Task 1), `describe.describe` (existing).
- Produces: Flask route `GET /search-runs/<name>` rendering `search_run.html` with context `{run: SearchRun, finalist_rows: list[dict], error: str | None}`; each `finalist_rows` entry is `{"index": int, "filters_text": str, "wins": int, "losses": int, "pushes": int, "roi": float, "raw_p": float, "corrected_p": float, "bh_significant": bool}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web.py (append)

def test_search_run_view_renders_finalist_stats(tmp_path):
    from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
    from cfb_system_maker.storage import save_search_run
    from cfb_system_maker.web import create_app

    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12, losses=8, pushes=1, roi=0.0524,
        raw_p=0.031, corrected_p=0.062, bh_significant=False,
    )
    run = SearchRun(
        name="my-run", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482, finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )
    save_search_run("my-run", run, tmp_path)

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/my-run")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "482" in body
    assert "12-8-1" in body or ("12" in body and "8" in body)
    assert "Narrate results" in body


def test_search_run_view_missing_run_returns_404(tmp_path):
    from cfb_system_maker.web import create_app

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/does-not-exist")

    assert response.status_code == 404


def test_search_run_view_rejects_unsafe_name(tmp_path):
    from cfb_system_maker.web import create_app

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/..%2F..%2Fescape")

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web.py -k search_run_view -v`
Expected: FAIL — 404 for all (route doesn't exist), first two tests fail on missing "482"/"Narrate results" or wrong status.

- [ ] **Step 3: Add imports to web.py**

Near the top of `cfb_system_maker/web.py`, alongside the existing `from cfb_system_maker.storage import ...` line, add `load_search_run` to the import list. Also add `from cfb_system_maker.describe import describe` if not already imported (check first — `index()` already calls `describe(system)`, so this import likely already exists).

- [ ] **Step 4: Add the route**

In `cfb_system_maker/web.py`, after the `/compare` route block (or any convenient spot before `/api/backtest`), add:

```python
    @app.get("/search-runs/<name>")
    def search_run_view(name: str):
        try:
            run = load_search_run(name, app.config["DATA_DIR"])
        except (ValueError, FileNotFoundError):
            abort(404)

        finalist_rows = []
        for i, finalist in enumerate(run.finalists, start=1):
            sentences = describe(finalist.system)
            filters_text = "; ".join(row["text"] for row in sentences) if sentences else "no filters (all games)"
            finalist_rows.append(
                {
                    "index": i,
                    "filters_text": filters_text,
                    "wins": finalist.wins,
                    "losses": finalist.losses,
                    "pushes": finalist.pushes,
                    "roi": finalist.roi,
                    "raw_p": finalist.raw_p,
                    "corrected_p": finalist.corrected_p,
                    "bh_significant": finalist.bh_significant,
                }
            )

        return render_template(
            "search_run.html",
            run=run,
            finalist_rows=finalist_rows,
        )
```

Check whether `abort` is already imported from `flask` at the top of `web.py` (it's a common Flask import); if not, add it to the existing `from flask import ...` line.

- [ ] **Step 5: Write `cfb_system_maker/templates/search_run.html`**

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <header class="workspace-header">
    <div>
      <h2>Search Run: {{ run.name }}</h2>
      <p>{{ run.candidates_tested }} candidates tested, {{ run.finalists_graded }} finalist(s) graded on holdout.</p>
    </div>
  </header>

  <table class="finalist-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Filters</th>
        <th>Holdout Record</th>
        <th>ROI</th>
        <th>Raw p</th>
        <th>Corrected p</th>
        <th>BH Significant</th>
      </tr>
    </thead>
    <tbody>
      {% for row in finalist_rows %}
      <tr>
        <td>{{ row.index }}</td>
        <td>{{ row.filters_text }}</td>
        <td>{{ row.wins }}-{{ row.losses }}-{{ row.pushes }}</td>
        <td>{{ "%.2f%%"|format(row.roi * 100) }}</td>
        <td>{{ "%.4f"|format(row.raw_p) }}</td>
        <td>{{ "%.4f"|format(row.corrected_p) }}</td>
        <td>{{ "Yes" if row.bh_significant else "No" }}</td>
      </tr>
      {% else %}
      <tr><td colspan="7">No finalist survived holdout grading.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <section class="theory-panel narration-panel" id="narration-panel" data-run-name="{{ run.name }}">
    <details>
      <summary><button type="button" id="narrate-trigger">Narrate results</button></summary>
      <div id="narration-body">
        <p id="narration-status"></p>
        <p id="narration-text"></p>
      </div>
    </details>
  </section>
</section>
<script src="{{ url_for('static', filename='narrate.js') }}"></script>
{% endblock %}
```

Before writing this, check `cfb_system_maker/templates/index.html`'s top few lines and `dashboard.html`'s top few lines to confirm whether templates use `{% extends "base.html" %}` or are standalone full-HTML files — match whichever convention the codebase actually uses (adjust the template accordingly; if there's no `base.html`, write `search_run.html` as a standalone file copying the `<head>`/nav structure from `dashboard.html`).

- [ ] **Step 6: Add minimal CSS for the narration trigger**

In `cfb_system_maker/static/styles.css`, after the existing `.theory-panel` rules (around line 310-320), add:

```css
.narration-panel summary {
  cursor: pointer;
  list-style: none;
}

.narration-panel #narrate-trigger {
  font: inherit;
}

#narration-status.error {
  color: var(--negative, #b00020);
}
```

Check the existing `styles.css` for a `--negative`-equivalent CSS variable name (search for how `.negative` class is styled elsewhere, e.g. around the `result.profit`/`result.roi` conditional classes in `index.html`) and reuse that variable/color instead of inventing a new one.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_web.py -k search_run_view -v`
Expected: 3 passed

- [ ] **Step 8: Run full web test suite to check no regressions**

Run: `python -m pytest tests/test_web.py -v`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/search_run.html cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "feat(P2-001): add /search-runs/<name> view for persisted search runs"
```

---

### Task 5: `POST /search-runs/<name>/narrate` route

**Files:**
- Modify: `cfb_system_maker/web.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `narration.narrate_run`, `narration.NarrationError` (Task 3), `storage.load_search_run` (Task 1).
- Produces: Flask route `POST /search-runs/<name>/narrate` returning JSON `{"text": str}` on success (200) or `{"error": str}` on failure (502) — never a 500, never an unhandled exception.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web.py (append)

def test_narrate_route_returns_text_on_success(tmp_path, monkeypatch):
    from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
    from cfb_system_maker.storage import save_search_run
    import cfb_system_maker.web as web_module

    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread"), wins=5, losses=3, pushes=0,
        roi=0.02, raw_p=0.04, corrected_p=0.08, bh_significant=False,
    )
    run = SearchRun(
        name="r1", saved_at="2026-07-31T00:00:00+00:00", candidates_tested=10,
        finalists_graded=1, effective_params={"beam_width": 100}, finalists=(finalist,),
    )
    save_search_run("r1", run, tmp_path)

    monkeypatch.setattr(web_module, "narrate_run", lambda run, **kwargs: "A short summary.")

    app = web_module.create_app(str(tmp_path))
    client = app.test_client()
    response = client.post("/search-runs/r1/narrate")

    assert response.status_code == 200
    assert response.get_json() == {"text": "A short summary."}


def test_narrate_route_returns_502_on_narration_error(tmp_path, monkeypatch):
    from cfb_system_maker.models import SearchRun
    from cfb_system_maker.storage import save_search_run
    from cfb_system_maker.narration import NarrationError
    import cfb_system_maker.web as web_module

    run = SearchRun(
        name="r2", saved_at="2026-07-31T00:00:00+00:00", candidates_tested=10,
        finalists_graded=0, effective_params={}, finalists=(),
    )
    save_search_run("r2", run, tmp_path)

    def _raise(run, **kwargs):
        raise NarrationError("boom")

    monkeypatch.setattr(web_module, "narrate_run", _raise)

    app = web_module.create_app(str(tmp_path))
    client = app.test_client()
    response = client.post("/search-runs/r2/narrate")

    assert response.status_code == 502
    assert "error" in response.get_json()


def test_narrate_route_missing_run_returns_404(tmp_path):
    from cfb_system_maker.web import create_app

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.post("/search-runs/does-not-exist/narrate")

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web.py -k narrate_route -v`
Expected: FAIL — route doesn't exist (404 for all, first two assert wrong status/body).

- [ ] **Step 3: Add the import and route**

In `cfb_system_maker/web.py`, add to imports:

```python
from cfb_system_maker.narration import NarrationError, narrate_run
```

Then add the route, right after `search_run_view`:

```python
    @app.post("/search-runs/<name>/narrate")
    def narrate_search_run(name: str):
        try:
            run = load_search_run(name, app.config["DATA_DIR"])
        except (ValueError, FileNotFoundError):
            abort(404)

        try:
            text = narrate_run(run)
        except NarrationError as exc:
            return jsonify({"error": str(exc)}), 502

        return jsonify({"text": text})
```

Check whether `jsonify` is already imported from `flask` at the top of `web.py` (it likely is, given `/api/backtest` and `/filter-detail` already return JSON); if not, add it to the existing import line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_web.py -k narrate_route -v`
Expected: 3 passed

- [ ] **Step 5: Run full web test suite to check no regressions**

Run: `python -m pytest tests/test_web.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "feat(P2-001): add POST /search-runs/<name>/narrate endpoint"
```

---

### Task 6: `narrate.js` — fetch-triggered client, graceful degradation

**Files:**
- Create: `cfb_system_maker/static/narrate.js`

**Interfaces:**
- Consumes: DOM ids from `search_run.html` (Task 4): `#narration-panel[data-run-name]`, `#narrate-trigger`, `#narration-status`, `#narration-text`.
- Produces: click handler wired on page load; no exported functions (IIFE, matches `filter_modal.js` convention).

- [ ] **Step 1: Write `cfb_system_maker/static/narrate.js`**

No automated test for this file — it's a thin DOM/fetch wrapper with no logic to unit test in isolation (matches the codebase's existing convention: `filter_modal.js` has no dedicated JS test file either; browser verification covers it in Step 2 below).

```javascript
(function () {
  "use strict";

  const panel = document.getElementById("narration-panel");
  const trigger = document.getElementById("narrate-trigger");
  const statusEl = document.getElementById("narration-status");
  const textEl = document.getElementById("narration-text");
  if (!panel || !trigger || !statusEl || !textEl) {
    return;
  }

  const runName = panel.getAttribute("data-run-name");
  let requested = false;

  trigger.addEventListener("click", function () {
    if (requested) {
      return;
    }
    requested = true;
    trigger.disabled = true;
    statusEl.classList.remove("error");
    statusEl.textContent = "Narrating...";

    fetch("/search-runs/" + encodeURIComponent(runName) + "/narrate", {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error(data.error || "narration_failed");
          }
          return data;
        });
      })
      .then(function (data) {
        statusEl.textContent = "";
        textEl.textContent = data.text;
      })
      .catch(function () {
        statusEl.classList.add("error");
        statusEl.textContent = "Narration unavailable right now.";
        trigger.disabled = false;
        requested = false;
      });
  });
})();
```

- [ ] **Step 2: Manual browser verification**

Start the dev server against a data dir containing at least one persisted search run (run `search --save-run demo-run --data-dir data ...` first, or use a test fixture data dir), open `/search-runs/demo-run`, click "Narrate results", confirm:
- Button disables immediately, status shows "Narrating..."
- On success, narration text appears, status clears
- Page never auto-triggers narration on load
- Clicking again after success does nothing (already requested) — matches "exactly one call per explicit request"

If `ANTHROPIC_API_KEY` isn't set in this environment, confirm the failure path instead: status shows "Narration unavailable right now.", button re-enables, rest of the page (finalist table) still fully visible/usable.

- [ ] **Step 3: Commit**

```bash
git add cfb_system_maker/static/narrate.js
git commit -m "feat(P2-001): add narrate.js fetch trigger with graceful failure handling"
```

---

### Task 7: Wire a "View run" link from the CLI save-run output (discoverability)

**Files:**
- Modify: `cfb_system_maker/cli.py`

**Interfaces:**
- Consumes: nothing new — pure print-statement addition to the Task 2 code.

- [ ] **Step 1: Update the save-run print statement**

In `cfb_system_maker/cli.py`, in the `--save-run` block added in Task 2, change the final `print` line to also mention the web path:

```python
        save_search_run(args.save_run, run, args.data_dir)
        print(f"Saved run as {args.save_run} ({grading.finalists_graded} finalists)")
        print(f"View at /search-runs/{args.save_run} (run `web` first)")
```

- [ ] **Step 2: Run CLI tests to confirm no regression**

Run: `python -m pytest tests/test_cli.py -k save_run -v`
Expected: still 2 passed (the new print line doesn't break existing assertions, which only check substring `"Saved run as my-run"`).

- [ ] **Step 3: Commit**

```bash
git add cfb_system_maker/cli.py
git commit -m "feat(P2-001): print view-run hint after search --save-run"
```

---

## Self-Review Notes

**Spec coverage against P2-001 acceptance criteria:**
- "Narration triggers only on explicit action" -> Task 6 `narrate.js`, no auto-call on load. Covered.
- "Exactly one LLM call per request" -> Task 3 `narrate_run` makes one `client.messages.create` call; Task 6 JS guards against double-click via `requested` flag. Covered.
- "LLM call uses only already-computed stats" -> Task 3 `build_prompt` reads only `SearchRun` fields (persisted from `grade_finalists` output in Task 2); no LLM call anywhere in `search.py`/`beam_search`/`grade_finalists`, unchanged in this plan. Covered.
- "theory-panel-style collapsible block appended to results display" -> Task 4 template reuses `.theory-panel` class, wraps in native `<details>` (new interaction, per ticket's design note that this collapsible trigger is new, not a copy of an existing JS pattern). Covered.
- "Graceful degradation on failure/timeout" -> Task 3 catches all exceptions into `NarrationError`; Task 5 route catches `NarrationError` into a 502 JSON response instead of a 500; Task 6 JS catches fetch/response failures and leaves the rest of the page (finalist table) intact. Covered.
- Ticket's own gap note ("no live view for search results") -> resolved by Task 4's new `/search-runs/<name>` route, per user decision to persist a run artifact rather than re-scope to a single saved system.
- Technical Notes' "new small route... consistent with plain JS/fetch modal convention" -> Task 5 route + Task 6 JS follow `filter_modal.js`'s fetch/status-text pattern (simplified — no AbortController needed since there's no debounced re-fire, only a single one-shot click).

**Placeholder scan:** no TBD/TODO left in any step; all code blocks are complete, runnable as written pending the Step 3/Task 4 template-convention check (explicitly called out as a check-before-writing step, not a placeholder in the delivered code).

**Type consistency check:** `SearchRunFinalist`/`SearchRun` field names are identical across Task 1 (definition), Task 2 (CLI construction), Task 3 (`build_prompt` reads `run.finalists`, `run.candidates_tested`, etc.), Task 4 (`finalist.wins`/`losses`/`pushes`/`roi`/`raw_p`/`corrected_p`/`bh_significant`), and Task 5 (passes the same `run` object into `narrate_run`). `narrate_run`'s signature (`client=None, api_key=None, model=..., timeout=...`) matches its Task 3 definition and Task 5's no-kwarg call site (uses defaults) and Task 5's test's `monkeypatch` stub (`lambda run, **kwargs: ...`, tolerant of any call shape).

**One unresolved item requiring human judgment during execution:** Task 4 Step 5 flags that the plan's own author didn't confirm whether templates use `{% extends %}` or are standalone — this must be checked against the real `index.html`/`dashboard.html` files before writing `search_run.html`, not guessed.
