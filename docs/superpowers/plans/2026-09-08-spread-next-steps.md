# Spread line-movement — fixes and next steps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the decontaminated archive result (the screened consensus anticipates ~15% of the open→close move at the opener) into a yes/no on whether any of it is bettable at a price PT's timing allows, and remove the remaining defects that would make that answer unreliable.

**Architecture:** Everything runs off three files the collector already writes — PT snapshots (`ingest/pt_snapshots/`), Action Network tick histories (`raw/actionnetwork/history_event_*.json`) and the forward log (`processed/movement_forward_log.csv`) — plus scores from `core.fact_game`. Each analysis is a script under `research/spread/scripts/` with a pre-registered expectation in `research/spread/docs/prereg-line-movement.md` written before the run, and a results section in `line-movement-results.md` after. No new data sources; no new models until the timing question is answered.

**Tech Stack:** Python 3.14, pandas, numpy, scipy.stats, duckdb (read-only on `cfb.duckdb`), pytest. Windows Task Scheduler for the collector.

**Spec:** `research/spread/docs/review-2026-09-08-tree-audit.md` (findings and their resolutions) and `research/spread/docs/prereg-line-movement.md` (amendments A3, B1). This plan carries the audit's open items and the decision tree in `line-movement-results.md` "What follows".

## Global Constraints

- `CFB_DATA_ROOT` is required (root `CLAUDE.md`); every script resolves paths through `cfb_paths`. Data is never committed.
- No lookahead: a version B predictor may use only the snapshot it is anchored on and the archive fit; the close and the score enter only as targets.
- Preregistration order: expectation text is committed **before** the run that tests it, as a numbered amendment in `prereg-line-movement.md`. One run per amendment. Reads of version B are reported every week but decide nothing before the amendment B1 gate (MDE ≤ 0.2 or season end).
- Sign convention: PT sign (positive = home favoured) in every live table; archive sign (negated) only inside fitted code. Check a known game before trusting a table.
- Every result lands in `line-movement-results.md`; `README.md` and `CLAUDE.md` point, never restate.
- Root standing rule: when a task here lands, mark it done in this file with the date.
- Run all commands from the repository root.

## Current state (2026-09-08, for the executor)

| thing | state |
|---|---|
| PT snapshots | 10 files, 08-29 → 09-08; collector task fixed 09-08 (battery, StartWhenAvailable), last forced run returned 0 |
| AN histories | 106 files, all 2026 week 1 (AN numbering); weeks 2+ never pulled because `CFB-AN-History` was refused 09-04 → 09-08 |
| Forward log | 7 snapshots × 43 games (PT week 2); `eval_version_b.py` grades 42 against a close, **0 with a score** because it reads `stg_gql.game` (49 scored) instead of `core.fact_game` (454 scored) |
| Version B first read | E4 slope +0.20 [0.00, +0.40], n = 42, one week, HC1 SE; MDE 0.28; no verdict |
| Decontaminated archive | E4 R² 0.153, γ 0.29; E6 0.163 at λ = 10⁴ (grid edge); E14 0.107 |
| PT `line` vs AN close | mean 0.69 apart, exact on 31% |

---

## Phase 1 — this week: data integrity and the cheap questions

### Task 1: Backfill Action Network histories and prove the collector is alive

**Files:**
- Modify: `docs/line-timing-collector.md` (add the health command from Task 3 once it exists)
- No code.

- [ ] **Step 1: Pull histories for every 2026 week posted so far**

```bash
research\spread\scripts\collect_line_timing.cmd history --season 2026 --weeks 1-4
```

Expected: log shows `history: N written, 106 already on disk, M not yet posted`, N ≥ 40 (AN week 2 had 86 games; those with posted histories get files).

- [ ] **Step 2: Verify week-2 events now have files**

```bash
python - <<'EOF'
import pandas as pd, sys
sys.path.insert(0, "research/spread/scripts")
import collect_line_timing as clt
log = pd.read_csv(r"data\processed\movement_forward_log.csv")
ids = log.event_id.dropna().astype(int).unique()
have = sum((clt.AN_DIR / f"history_event_{i}.json").exists() for i in ids)
print(f"{have} of {len(ids)} forward-log events have a history file")
EOF
```

Expected: `42 of 43` or better. If under 35, AN has not posted them yet; rerun Step 1 tomorrow.

- [ ] **Step 3: Confirm the PT task fires on schedule without a hand run**

Wait for the next 6-hour slot (00:30, 06:30, 12:30, 18:30 local), then:

```powershell
(Get-ScheduledTask CFB-PT-Snapshot | Get-ScheduledTaskInfo) | Select LastRunTime, LastTaskResult
Get-Content data\logs\line_timing.log -Tail 3
```

Expected: `LastTaskResult 0` at the slot time, and a `==== ... :: snapshot ====` line in the log at that time.

- [ ] **Step 4: Record in the runbook**

Append under "Checking it is alive" in `docs/line-timing-collector.md`:

```markdown
Backfilled 2026 weeks 1–4 on <date> after the 09-04 → 09-08 outage; the PT snapshots for
Thu 09-04 12:30 through Sun 09-07 are gone and cannot be recovered.
```

- [ ] **Step 5: Commit**

```bash
git add docs/line-timing-collector.md
git commit -m "docs(spread): record the AN backfill after the collector outage"
```

---

### Task 2: Version B reads scores from `core.fact_game` — **done 2026-09-08** (42 of 42 week-2 games scored; 11–9 ATS on the 20 |x| ≥ 1 bets)

`stg_gql.game` is refreshed only by the GraphQL pull and is stale for 2026; `core.fact_game`
is rebuilt by `CFB-CFBD-Daily` and carries 454 scored week-1 (CFBD numbering) games. PT's
"week 2" slate (Sep 3–7) is CFBD week 1.

**Files:**
- Modify: `research/spread/scripts/eval_version_b.py:75-100` (`margins`)
- Test: `tests/test_spread_version_b.py` (new)

**Interfaces:**
- Produces: `fetch_scores(con, seasons) -> dict[tuple[int, frozenset[str]], tuple[str, float, float]]` keyed by `(season, {home, away})`, value `(cfbd_home_name, home_points, away_points)`; `home_margin(row, scores) -> float` where `row` has `.kick`, `.home`, `.road`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spread_version_b.py
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import eval_version_b as vb  # noqa: E402


def _con():
    con = duckdb.connect()
    con.execute("create schema core")
    con.execute("""create table core.fact_game(season int, home_team varchar, away_team varchar,
                   home_points int, away_points int)""")
    con.execute("insert into core.fact_game values (2026, 'Alabama', 'East Carolina', 45, 10),"
                "(2026, 'Florida State', 'Georgia Tech', 20, 24)")
    return con


def test_fetch_scores_keys_on_unordered_pair():
    s = vb.fetch_scores(_con(), [2026])
    assert s[(2026, frozenset({"Alabama", "East Carolina"}))] == ("Alabama", 45, 10)


def test_home_margin_matches_pt_spelling_and_orientation():
    s = vb.fetch_scores(_con(), [2026])
    g = pd.DataFrame({"kick": ["2026-09-05T16:00:00+00:00", "2026-09-05T16:00:00+00:00"],
                      "home": ["Alabama", "Georgia Tech"], "road": ["E. Carolina", "Florida St."]})
    m = vb.margins(g, s)
    assert m.tolist() == [35.0, 4.0]          # second game: PT home is CFBD away -> flipped sign
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_spread_version_b.py -q`
Expected: FAIL with `AttributeError: module 'eval_version_b' has no attribute 'fetch_scores'`

- [ ] **Step 3: Replace `margins` in `eval_version_b.py`**

Delete the existing `margins` function and insert:

```python
def fetch_scores(con, seasons):
    """{(season, {home, away}): (cfbd_home, home_points, away_points)} from core.fact_game."""
    rows = con.execute(
        "select season, home_team, away_team, home_points, away_points from core.fact_game "
        "where season between ? and ? and home_points is not null",
        [min(seasons), max(seasons)]).fetchall()
    return {(int(s), frozenset((h, a))): (h, float(hp), float(ap)) for s, h, a, hp, ap in rows}


def margins(games: pd.DataFrame, scores: dict) -> pd.Series:
    """Home margin in PT orientation; NaN when unplayed or unmatched."""
    out = []
    for r in games.itertuples():
        season = pd.Timestamp(r.kick).year
        hit = np.nan
        for h in bpt.candidates(r.home):
            for a in bpt.candidates(r.road):
                rec = scores.get((season, frozenset((h, a))))
                if rec:
                    cfbd_home, hp, ap = rec
                    hit = (hp - ap) if cfbd_home == h else (ap - hp)
                    break
            if not np.isnan(hit):
                break
        out.append(hit)
    return pd.Series(out, index=games.index, dtype=float)
```

and in `main()` replace `g["margin"] = margins(g)` with:

```python
    import duckdb
    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    seasons = sorted(set(g.kick_utc.dt.year))
    g["margin"] = margins(g, fetch_scores(con, seasons))
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_spread_version_b.py tests/test_spread_estimators.py -q`
Expected: 5 passed

- [ ] **Step 5: Run the grader and check the score join**

Run: `python research/spread/scripts/eval_version_b.py`
Expected: `42 graded against a close, ≥ 40 with a score` and an `ATS` figure on the `|x| >= 1` row. If fewer than 40 have a score, print the unmatched names and add them to `ALIASES` in `build_prediction_tracker.py` (that is the CFBD alias table `candidates()` reads).

- [ ] **Step 6: Commit**

```bash
git add research/spread/scripts/eval_version_b.py tests/test_spread_version_b.py
git commit -m "fix(spread): version B grades scores from core.fact_game, which the daily refresh keeps current"
```

---

### Task 3: Collector health check

The runbook's safeguard is "count snapshots once a month". The 09-04 outage cost four days
before anyone looked. A script that exits non-zero when the stream is stale gives the Monday
routine (Task 8) something to fail on.

**Files:**
- Create: `research/spread/scripts/collector_health.py`
- Test: `tests/test_spread_collector_health.py`
- Modify: `docs/line-timing-collector.md` ("Checking it is alive")

**Interfaces:**
- Produces: `stale(latest: datetime, now: datetime, max_gap_hours: float = 12) -> bool`; `in_season(now: datetime) -> bool` (Aug 25 – Dec 15).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spread_collector_health.py
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import collector_health as ch  # noqa: E402

UTC = timezone.utc


def test_stale_after_max_gap():
    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    assert ch.stale(datetime(2026, 9, 7, 23, tzinfo=UTC), now)          # 13h
    assert not ch.stale(datetime(2026, 9, 8, 1, tzinfo=UTC), now)       # 11h


def test_in_season_window():
    assert ch.in_season(datetime(2026, 10, 1, tzinfo=UTC))
    assert not ch.in_season(datetime(2026, 2, 1, tzinfo=UTC))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_spread_collector_health.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'collector_health'`

- [ ] **Step 3: Write the script**

```python
# research/spread/scripts/collector_health.py
"""Exit 1 if the Prediction Tracker snapshot stream has gone quiet in season.

PT overwrites one file in place; a missed window is unrecoverable, so silence is the failure
that matters. Checks the newest snapshot's capture time against now. Meant for the Monday
routine and for a human who wants a one-line answer.

    python research/spread/scripts/collector_health.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_line_timing as clt  # noqa: E402

MAX_GAP_HOURS = 12.0        # two missed 6-hour slots


def in_season(now: datetime) -> bool:
    return (now.month, now.day) >= (8, 25) and (now.month, now.day) <= (12, 15)


def stale(latest: datetime, now: datetime, max_gap_hours: float = MAX_GAP_HOURS) -> bool:
    return (now - latest).total_seconds() > max_gap_hours * 3600


def main() -> int:
    now = datetime.now(timezone.utc)
    metas = sorted(clt.SNAP_DIR.glob("ncaapredictions_*.meta.json"))
    if not metas:
        print("no snapshots at all"); return 1
    latest = datetime.fromisoformat(json.loads(metas[-1].read_text())["captured_at"])
    gap = (now - latest).total_seconds() / 3600
    print(f"newest snapshot {metas[-1].name} captured {gap:.1f}h ago; {len(metas)} on disk")
    if in_season(now) and stale(latest, now):
        print(f"STALE: more than {MAX_GAP_HOURS:.0f}h without a capture in season"); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: a snapshot is only written when PT's file changes, so a quiet PT (Sunday night) can
look stale. `MAX_GAP_HOURS = 12` tolerates two unchanged slots; if this false-alarms weekly,
raise it to 18 and record why.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_spread_collector_health.py -q`
Expected: 2 passed

- [ ] **Step 5: Run it for real and add to the runbook**

Run: `python research/spread/scripts/collector_health.py`
Expected: exit 0 and one line naming the newest snapshot.

Add to `docs/line-timing-collector.md` under "Checking it is alive":

```markdown
`python research/spread/scripts/collector_health.py` exits 1 when the newest snapshot is more
than 12 hours old in season. Run it Monday morning before reading version B.
```

- [ ] **Step 6: Commit**

```bash
git add research/spread/scripts/collector_health.py tests/test_spread_collector_health.py docs/line-timing-collector.md
git commit -m "feat(spread): collector health check that fails on a stale snapshot stream"
```

---

### Task 4: When does each model publish? (from the snapshots we already have)

The "get earlier than PT" idea assumes the leading movement forecasters post before PT's Monday
compile. The 6-hourly snapshots already record, per model column, the first capture in which it
is non-null each week — that *is* the publication time. No scraping needed.

**Files:**
- Create: `research/spread/scripts/model_publish_times.py`
- Test: `tests/test_spread_publish_times.py`
- Modify: `research/spread/docs/line-movement-results.md` (new section "When the constituents publish")

**Interfaces:**
- Produces: `first_seen(snapshots: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame` with columns `slate, model, first_capture_utc, hours_after_monday_et`; `slate` is the Monday date (ET) of the week the snapshot's games belong to, computed from the kick dates via `weekly_slate.live_books`? No — kick dates are not in PT's file. Use the game *set*: a new slate starts when > 50% of (road, home) pairs differ from the previous snapshot (same rule as `pt_rollover.NEW_SLATE_FRAC`), and the slate is labelled by the Monday on or before its first capture.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_spread_publish_times.py
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import model_publish_times as mpt  # noqa: E402


def _snap(stamp, games, **cols):
    df = pd.DataFrame({"road": [g[0] for g in games], "home": [g[1] for g in games]})
    for k, v in cols.items():
        df[k] = v
    return stamp, df


def test_first_seen_per_slate_and_model():
    wk1 = [("A", "B"), ("C", "D")]
    wk2 = [("E", "F"), ("G", "H")]
    snaps = [
        _snap("20260831T190505Z", wk1, linesag=[1.0, None], linefpi=[None, None]),   # Mon 15:05 ET
        _snap("20260901T223002Z", wk1, linesag=[1.0, 2.0], linefpi=[3.0, 4.0]),      # Tue 18:30 ET
        _snap("20260907T130000Z", wk2, linesag=[1.0, 1.0], linefpi=[None, None]),    # next Mon
    ]
    out = mpt.first_seen(snaps)
    row = out.set_index(["slate", "model"])
    assert row.loc[("2026-08-31", "linesag"), "hours_after_monday_et"] == 15.0 + 5 / 60
    assert abs(row.loc[("2026-08-31", "linefpi"), "hours_after_monday_et"] - (24 + 18.5)) < 0.01
    assert row.loc[("2026-09-07", "linesag"), "hours_after_monday_et"] == 9.0
    assert ("2026-09-07", "linefpi") not in row.index          # never published that week
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_spread_publish_times.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the script**

```python
# research/spread/scripts/model_publish_times.py
"""When does each Prediction Tracker constituent publish, relative to Monday?

The 6-hourly snapshots record, per model column, the first capture in which the column is
non-null for a slate. That is the model's publication time to within six hours -- the field
the archive lacks. Joined to the movement-skill screen, it answers whether the models that
lead the line are already in the Monday compile or arrive later in the week.

    python research/spread/scripts/model_publish_times.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402
import collect_line_timing as clt  # noqa: E402
from pt_rollover import NEW_SLATE_FRAC  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = base.OUT_DIR / "model_publish_times.csv"
NOT_MODELS = {"road", "home", "line", "lineopen", "linestd"} | base.MARKET_LINES


def _capture(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def first_seen(snapshots):
    """snapshots: [(stamp, frame)] in time order -> one row per (slate, model) first seen."""
    rows, prev_games, slate = [], set(), None
    seen: dict[str, datetime] = {}
    for stamp, df in snapshots:
        cap = _capture(stamp)
        games = set(zip(df.road, df.home))
        if not prev_games or len(games - prev_games) / max(len(games), 1) > NEW_SLATE_FRAC:
            et = cap.astimezone(ET)
            monday = (et - pd.Timedelta(days=et.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            slate, seen = monday.strftime("%Y-%m-%d"), {}
        prev_games = games
        et = cap.astimezone(ET)
        monday = (et - pd.Timedelta(days=et.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for m in df.columns:
            if m in NOT_MODELS or m in seen or not m.startswith("line"):
                continue
            if pd.to_numeric(df[m], errors="coerce").notna().any():
                seen[m] = cap
                rows.append({"slate": slate, "model": m, "first_capture_utc": stamp,
                             "hours_after_monday_et": (et - monday).total_seconds() / 3600})
    return pd.DataFrame(rows)


def movement_rank():
    """Rank of every model by prior movement skill on the full archive (the E4 screen's order)."""
    hist, models = base.load()
    hist = hist[hist["line"].notna() & hist["lineopen"].notna()].copy()
    hist["y"] = -hist["line"].to_numpy(float)
    skill = base.prior_skill(hist, [m for m in models if m not in base.MARKET_LINES], "lineopen",
                             int(hist.season.max()))
    return pd.Series({m: i + 1 for i, m in enumerate(sorted(skill, key=skill.get))}, name="movement_rank")


def main() -> int:
    snaps = [(p.stem.split("_")[-1], pd.read_csv(p)) for p in sorted(clt.SNAP_DIR.glob("ncaapredictions_*.csv"))]
    fs = first_seen(snaps).merge(movement_rank(), left_on="model", right_index=True, how="left")
    fs.to_csv(OUT, index=False)
    top = fs[fs.movement_rank <= base.SCREEN_K]
    print(f"{fs.slate.nunique()} slates, {fs.model.nunique()} models seen; top-{base.SCREEN_K} by movement skill:")
    piv = top.pivot_table(index="model", columns="slate", values="hours_after_monday_et").round(1)
    print(piv.sort_index().to_string())
    for s, g in top.groupby("slate"):
        by_mon = int((g.hours_after_monday_et <= 20).sum())
        print(f"  slate {s}: {by_mon} of {len(g)} top-{base.SCREEN_K} present in the first Monday snapshot (<= 20h)")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_spread_publish_times.py -q`
Expected: 1 passed

- [ ] **Step 5: Run it and write the section**

Run: `python research/spread/scripts/model_publish_times.py`

Add to `line-movement-results.md` a section **"When the constituents publish (from snapshots, <date>)"** with the printed pivot and one sentence per slate: "N of the top-20 movement forecasters were in the first Monday snapshot." Decision recorded there:

- ≥ 15 of 20 present Monday → PT's Monday compile already carries the consensus; "earlier than PT" means scraping constituents Sunday night. Open a scoping note listing those models and their public URLs (PT's model list page names them).
- < 10 present Monday → the consensus is not complete on Monday; amendment B2 (Task 7) must anchor on the first snapshot where ≥ 15 of 20 are present, and the "Monday" read is partly a "which models are in yet" read.

- [ ] **Step 6: Commit**

```bash
git add research/spread/scripts/model_publish_times.py tests/test_spread_publish_times.py research/spread/docs/line-movement-results.md
git commit -m "feat(spread): model publication times from the snapshot stream"
```

---

### Task 5: Amendment A4 — a finer ridge grid, and whether to keep serving E6

E6 sits at the grid edge (λ = 10⁴) in 19 of 20 seasons; the wide grid over-shrank. Decide once
whether ridge earns its place next to E4 on the decontaminated panel, then either keep it in
`weekly_slate.py` or drop it.

**Files:**
- Modify: `research/spread/docs/prereg-line-movement.md` (append A4)
- Modify: `research/spread/scripts/eval_line_movement.py:31-33` (add `--fine-ridge`)
- Modify: `research/spread/docs/line-movement-results.md` (A4 section)
- Modify: `research/spread/scripts/weekly_slate.py:219-221` (`PARAMS`, `MODEL_COLS`) — only if the decision says drop

- [ ] **Step 1: Pre-register, commit before running**

Append to `prereg-line-movement.md`:

```markdown
## Amendment A4 — finer ridge grid on the decontaminated panel (committed before the run)

E6's 1-SE rule chose λ = 10⁴, the grid edge, in 19 of 20 seasons; the wide grid (A2) ran to
10⁶ and lost 0.055 R². Run E6 once on the decontaminated panel (A3) with
λ ∈ {1000, 2000, 5000, 10000, 20000, 50000}. Same support, inference, 1-SE rule.

Expectation: the rule lands inside the grid (5000–20000) in most seasons and R² is within
0.02 of the A3 ridge (0.163), i.e. within 0.03 of E4 (0.153).

Decision rule, fixed now: if R²(E6, A4) − R²(E4, A3) ≤ 0.02, ridge is E4 with more
parameters and is **retired from `weekly_slate.py`**; E4 is the served movement model and the
others stay as reported columns. If > 0.02, E6 is served at the modal A4 λ.
```

```bash
git add research/spread/docs/prereg-line-movement.md
git commit -m "docs(spread): pre-register amendment A4, finer ridge grid"
```

- [ ] **Step 2: Add the flag**

In `eval_line_movement.py`, after `WIDE_LAMBDA = [...]` add `FINE_LAMBDA = [1000.0, 2000.0, 5000.0, 1e4, 2e4, 5e4]`, and in `main()`:

```python
    ap.add_argument("--fine-ridge", action="store_true", help="amendment A4: E6 only, fine lambda grid")
```

after the `--amend` block:

```python
    if args.fine_ridge:
        METHODS = ["E6"]
        grids = {k: list(v) for k, v in sweep.GRIDS.items()}
        grids["E6"] = FINE_LAMBDA
        suffix += "_a4"
```

(`suffix` is built before this; move its assignment below so `_a4` lands after `_decon`.)

- [ ] **Step 3: Run once**

```bash
python research/spread/scripts/eval_line_movement.py --decontaminate --fine-ridge
```

Expected: ~3 minutes; a table with R0, E4, E6 and the chosen λ counts. Output `pt_movement_decon_a4.json`.

- [ ] **Step 4: Write the A4 section and apply the decision**

In `line-movement-results.md` add "Amendment A4 — finer ridge grid" with the R², chosen-λ
distribution and the scorecard line. Then apply the pre-registered rule:

- Retire: in `weekly_slate.py` remove `"E6": 10000.0` from `PARAMS` and `"E6"` from `MODEL_COLS`; update the docstring column list; `pred_close` (median of model columns) then excludes it. Run `python research/spread/scripts/weekly_slate.py --no-books` to confirm it still builds.
- Keep: change `"E6": 10000.0` to the modal A4 λ and cite `pt_movement_decon_a4.json` in the `PARAMS` comment.

- [ ] **Step 5: Commit**

```bash
git add research/spread/scripts/eval_line_movement.py research/spread/scripts/weekly_slate.py research/spread/docs/line-movement-results.md
git commit -m "feat(spread): amendment A4 -- fine ridge grid; serve or retire E6 per the registered rule"
```

---

### Task 6: Does the panel's information extend past PT's last capture?

PT's `line` is 0.7 points short of the consensus close. On the 1,219 matched 2024–25 games
the walk-forward E4 predictions exist (`pt_movement_preds_decon.csv`). If E4's disagreement
with PT's line predicts the remaining PT-line → AN-close move, the panel knows something the
market had not priced by PT's last capture — the only archive evidence that could exist for
"leads" rather than "follows".

**Files:**
- Modify: `research/spread/docs/prereg-line-movement.md` (append A5)
- Modify: `research/spread/scripts/check_pt_line_is_close.py` (second section)
- Modify: `research/spread/docs/line-movement-results.md` (§ target)

- [ ] **Step 1: Pre-register, commit before running**

```markdown
## Amendment A5 — the remaining move after PT's capture (committed before the run)

On the 2024–25 games matched in `check_pt_line_is_close.py`, regress
`y = AN_close − PT_line` on `x = E4_decon − PT_line` (walk-forward predictions from A3, both
in PT sign), season-week clusters. Also E6 and E14 beside it, no selection.

Expectation: slope between 0.0 and 0.10, CI including 0. The panel's edge lives in the first
part of the move; by PT's last capture the market has absorbed it. A slope ≥ 0.2 with a CI
excluding 0 would be the first archive evidence of information the market had not priced,
and would raise the prior on version B.
```

```bash
git add research/spread/docs/prereg-line-movement.md
git commit -m "docs(spread): pre-register amendment A5, the move after PT's capture"
```

- [ ] **Step 2: Add the section to the script**

In `check_pt_line_is_close.py`, after `out = {...}` and before the prints, add:

```python
    preds = pd.read_csv(base.OUT_DIR / "pt_movement_preds_decon.csv")   # PT sign already (margin space)
    jj = j.merge(preds[["game_id", "E4", "E6", "E14"]], on="game_id")
    y = (jj.an_close_pt - jj.pt_close).to_numpy(float)
    cl = (jj.season * 100 + jj.pt_week.fillna(0)).to_numpy(int)
    out["after_capture"] = {}
    print("\nA5  slope of (AN close - PT line) on (pred - PT line), season-week clusters")
    for p in ("E4", "E6", "E14"):
        x = (jj[p] - jj.pt_close).to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(y)
        r = vb.cluster_ols(y[ok], x[ok], cl[ok])
        out["after_capture"][p] = r
        print(f"  {p:4s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  n {r['n']}  clusters {r['clusters']}")
```

with `import eval_version_b as vb` added to the imports (it provides `cluster_ols`). `pt_week` and `game_id` come from `base.load()`; keep them in the frame by not selecting columns before the merge.

- [ ] **Step 3: Run once**

```bash
python research/spread/scripts/check_pt_line_is_close.py
```

Expected: the existing table plus three slope lines; n ≈ 1,100 (games with an E4 prediction, 2024–25 are in the walk-forward support).

- [ ] **Step 4: Record**

In `line-movement-results.md` § "The target", add the A5 table and its scorecard line against the expectation.

- [ ] **Step 5: Commit**

```bash
git add research/spread/scripts/check_pt_line_is_close.py research/spread/docs/line-movement-results.md
git commit -m "feat(spread): amendment A5 -- does the panel predict the move after PT's last capture"
```

---

### Task 7: Amendment B2 — timing decay at live prices (pre-register now, read weekly)

Version B anchors on the first Monday snapshot. The tradeable question is how fast the
predictable move is absorbed *after* that: the same slope at the Monday, Tuesday, Wednesday and
Thursday captures, on a fixed game set.

**Files:**
- Modify: `research/spread/docs/prereg-line-movement.md` (append B2)
- Modify: `research/spread/scripts/eval_version_b.py` (`--by-capture`)
- Test: `tests/test_spread_version_b.py` (add one case)

**Interfaces:**
- Produces: `capture_offsets(log: pd.DataFrame) -> pd.DataFrame` — every (game, snapshot) row with `hours_after_monday_et` and `offset_bucket ∈ {"mon", "tue", "wed", "thu+"}` (0–24, 24–48, 48–72, ≥ 72 h).

- [ ] **Step 1: Pre-register, commit before any in-season read**

```markdown
## Amendment B2 — decay at live prices (committed 2026-09-xx, before the first in-season read)

For every graded game and every snapshot captured on or after its week's Monday 00:00 ET,
compute `y = close − line_at_capture` and `x = E4_at_capture − line_at_capture`, bucket by
hours after Monday (0–24 "mon", 24–48 "tue", 48–72 "wed", ≥ 72 "thu+"), and report the slope
per bucket with season-week clusters. Fixed set: a game contributes to a bucket only if it has
a capture in that bucket; no re-selection by |x|.

Expectation: the slope falls monotonically across buckets and is within noise of 0 by "wed".
Read weekly with B4; decides nothing before the B1 gate. If the "mon" slope clears the B1
gate and "tue" is under half of it, the bet window is Monday only and the constituent-scraping
route (Task 4's decision) is the next step.
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_spread_version_b.py`:

```python
def test_capture_offsets_bucket_by_hours_after_monday():
    log = pd.DataFrame({"event_id": [1, 1, 1], "kick": ["2026-09-12T19:30:00+00:00"] * 3,
                        "captured_utc": ["20260907T190500Z", "20260908T223000Z", "20260910T043000Z"],
                        "line_pt": [7.0, 7.5, 7.5], "E4": [8.0, 8.0, 8.0]})
    o = vb.capture_offsets(log)
    assert o.offset_bucket.tolist() == ["mon", "tue", "wed"]
```

Run: `python -m pytest tests/test_spread_version_b.py -q` → expected FAIL, `no attribute 'capture_offsets'`.

- [ ] **Step 3: Implement**

In `eval_version_b.py`:

```python
BUCKETS = [(0, 24, "mon"), (24, 48, "tue"), (48, 72, "wed"), (72, 1e9, "thu+")]


def capture_offsets(log: pd.DataFrame) -> pd.DataFrame:
    """Every (game, snapshot) on or after the week's Monday, with its offset bucket."""
    log = log[log.event_id.notna() & log.kick.notna()].copy()
    cap = pd.to_datetime(log.captured_utc, format="%Y%m%dT%H%M%SZ", utc=True).dt.tz_convert(ET)
    kick_et = pd.to_datetime(log.kick, utc=True).dt.tz_convert(ET)
    monday = (kick_et - pd.to_timedelta(kick_et.dt.weekday, unit="D")).dt.normalize()
    log["hours_after_monday_et"] = (cap - monday).dt.total_seconds() / 3600
    log["week"] = monday.dt.strftime("%Y-%m-%d")
    log = log[log.hours_after_monday_et >= 0]
    log["offset_bucket"] = pd.cut(log.hours_after_monday_et, [b[0] for b in BUCKETS] + [1e9],
                                  labels=[b[2] for b in BUCKETS], right=False)
    return log
```

and in `main()`, after the B5 block:

```python
    print("\nB2  slope by capture offset (fixed set; season-week clusters)")
    allc = capture_offsets(log)
    allc = allc.merge(graded[["event_id", "close"]], on="event_id")
    out["by_capture"] = {}
    for b in [x[2] for x in BUCKETS]:
        sub = allc[allc.offset_bucket == b]
        if len(sub) < 30:
            print(f"  {b:4s} n {len(sub)} -- too few"); continue
        yy = (sub.close - sub.line_pt).to_numpy(float)
        xx = (sub.E4 - sub.line_pt).to_numpy(float)
        r = cluster_ols(yy, xx, sub.week.to_numpy())
        out["by_capture"][b] = r
        print(f"  {b:4s} slope {r['slope']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]  n {r['n']}  weeks {r['clusters']}")
```

- [ ] **Step 4: Run the tests and the grader**

Run: `python -m pytest tests/test_spread_version_b.py -q` → 3 passed.
Run: `python research/spread/scripts/eval_version_b.py` → a B2 block with `mon`, `tue`, `wed` rows for week 2 (one week; HC1 SE).

- [ ] **Step 5: Commit**

```bash
git add research/spread/docs/prereg-line-movement.md research/spread/scripts/eval_version_b.py tests/test_spread_version_b.py
git commit -m "feat(spread): amendment B2 -- version B slope by capture offset"
```

---

## Phase 2 — every week of the season

### Task 8: The Monday routine, automated

`CFB-AN-History` already runs Mondays 09:00. Make that run also grade version B, so the read
exists without a hand run, and make the health check the first thing it does.

**Files:**
- Modify: `research/spread/scripts/collect_line_timing.py:169-196` (`main`, history branch)
- Modify: `docs/line-timing-collector.md` ("What is registered")
- Modify: `research/spread/docs/line-movement-results.md` (a "Version B reads" table, one row per Monday)

- [ ] **Step 1: Chain the grader after the history pull**

In `collect_line_timing.main()`, replace the history branch with:

```python
    if args.mode in ("history", "both"):
        history(args.season, weeks, force=args.force)
        # Monday routine: health first (its exit code is informational here), then the
        # version B read on whatever closes the backfill just made gradable.
        for script in ("collector_health.py", "eval_version_b.py"):
            subprocess.run([sys.executable, str(Path(__file__).with_name(script))], check=False)
```

- [ ] **Step 2: Run the history mode by hand once to see the chain**

```bash
research\spread\scripts\collect_line_timing.cmd history --season 2026 --weeks 1-16
```

Expected: history summary, then the health line, then the version B tables, all in `logs/line_timing.log`.

- [ ] **Step 3: Add the reads table**

In `line-movement-results.md` § "Version B", add:

```markdown
### Reads (one row per Monday; amendment B1 says none of these is a verdict)

| date | n graded | weeks | E4 slope | 95% | sd(x) | MDE | n for MDE 0.2 | CLV \|x\|≥1 (n) | ATS \|x\|≥1 |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-08 | 42 | 1 | +0.20 | [0.00, +0.40] | 1.17 | 0.28 | 80 | +0.47 (20) | — |
```

and append one row each Monday from `processed/version_b.json`.

- [ ] **Step 4: Update the runbook's registered-task table**

```markdown
| `CFB-AN-History` | `collect_line_timing.cmd history --weeks 1-16` | Mondays 09:00 | Yes — just run it. Also runs `collector_health.py` and `eval_version_b.py`. |
```

- [ ] **Step 5: Commit**

```bash
git add research/spread/scripts/collect_line_timing.py docs/line-timing-collector.md research/spread/docs/line-movement-results.md
git commit -m "feat(spread): Monday routine -- backfill, health check, version B read in one task"
```

---

### Task 9: Line-shopping amendment — outlier guard and price-adjusted value

`combining-predictions.md` §1 lists two defects that must be fixed before the book fair drives
a live bet: no outlier guard in the backtest (the live slate has one), and price ignored. Both
are pre-registered here and run once.

**Files:**
- Modify: `research/spread/docs/prereg-line-shopping.md` (append amendment S1)
- Modify: `research/spread/scripts/eval_line_shopping.py` (guard + value column; read the file first — its `fair`/`best` construction is in the function that groups by `event_id`)
- Modify: `research/spread/docs/line-shopping-results.md` (S1 section)

- [ ] **Step 1: Pre-register, commit before running**

```markdown
## Amendment S1 — outlier guard and price (committed before the rerun)

1. A book's number is ignored when it is more than **2.5 points** from the median of all real
   books on the game and at least two other real books exist (the rule `weekly_slate.shop`
   already applies live).
2. Each side's value is scored on one scale:
   `value = 3.2 × points_gained − 100 × (breakeven(best odds) − breakeven(median-book odds))`,
   `breakeven(o) = |o| / (|o| + 100)` for negative American odds, `100 / (o + 100)` for positive.
   Reported: mean value at gain ≥ 0.5 and ≥ 1.0, and the share of sides where value ≤ 0.

Expectation: P2 falls from +1.26 to about +1.1 win-rate points (the guard removes the
mis-posts); at gain ≥ 1 about 12% of sides have value ≤ 0 once priced (the figure measured
post hoc on 2026-09-02); the gain ≥ 1 ATS at best stays inside [48, 57]. One run.
```

- [ ] **Step 2: Implement the guard**

Where `eval_line_shopping.py` builds the per-game book table (the group over `event_id` that produces `fair`), insert before the median:

```python
        if len(v) >= 3:
            kept = v[(v - v.median()).abs() <= 2.5]
            if len(kept) >= 2:
                v = kept
```

(`v` is the Series of home spreads by book for that game — match the variable name used there.)

- [ ] **Step 3: Implement price-adjusted value**

Add near the top:

```python
def breakeven(odds: float) -> float:
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)
```

and in the per-side table add `value = 3.2 * gain - 100 * (breakeven(best_odds) - breakeven(median_odds))`, where `median_odds` is the odds at the book that supplied the median number (or −110 when the median is an average of two books). Report `value.mean()` at gain ≥ 0.5 and ≥ 1.0 and `(value <= 0).mean()`.

- [ ] **Step 4: Run once and record**

```bash
python research/spread/scripts/eval_line_shopping.py
```

Add "Amendment S1" to `line-shopping-results.md` with the P2 figure, the value means and the scorecard.

- [ ] **Step 5: Commit**

```bash
git add research/spread/docs/prereg-line-shopping.md research/spread/scripts/eval_line_shopping.py research/spread/docs/line-shopping-results.md
git commit -m "feat(spread): amendment S1 -- outlier guard and priced value in the shopping backtest"
```

---

### Task 10: Verify "scoreboard = close" once 2026 closes exist (season end)

Blocked until the Action Network scoreboard for completed 2026 games is re-scraped, which is a
`cfb_system_maker` scraper run, not this tree's. When it has run:

- [ ] **Step 1:** For each 2026 event with both a history file and a scoreboard row, compare book 15's last pre-kick tick (`eval_version_b.close_from_history`) to `stg.an_market` book 15 line for that event. Twenty lines in a scratch script; report mean |Δ| and share exact.
- [ ] **Step 2:** Record in `line-shopping-results.md` "Limits": either "scoreboard = close on X% of games" or the correction to apply.
- [ ] **Step 3:** Commit.

---

## Phase 3 — the decision (at the B1 gate or season end, whichever first)

### Task 11: Read version B and act on the pre-registered table

**Files:**
- Modify: `research/spread/docs/line-movement-results.md` ("Verdict" section)
- Modify: `research/spread/CLAUDE.md`, `research/spread/docs/README.md` (one sentence each, pointing at the verdict)
- Possibly modify: `research/spread/scripts/weekly_slate.py` (bet rule), per branch

- [ ] **Step 1: Confirm the gate is met**

`processed/version_b.json` → `slope.E4.mde_80 ≤ 0.2`, or the date is past the last regular-season Saturday. If neither, stop; there is no read.

- [ ] **Step 2: Apply the table, fixed now**

| E4 slope at Monday (B4) | CI | action |
|---|---|---|
| < 0.10 | excludes 0.20 | **Close** PT-timed spread work. `CLAUDE.md` says so. `weekly_slate.py` keeps running for the book fair and shopping only; the model columns stay as reference. |
| 0.10 – 0.30 | any | **Marginal.** Wire `combining-predictions.md` §3 with `γ = slope` for `|x| ≥ 2` only; track CLV per bet in `movement_forward_log.csv`; no stake beyond quarter-Kelly on the measured p. Re-read at season end. |
| ≥ 0.30 | excludes 0.10 | **Bettable at Monday's number.** Wire §3 at `|x| ≥ 1`. If Task 4 found the leading constituents publish before PT, open the constituent-scraping task as the next tree. |
| any | B2 shows "tue" slope < half of "mon" | Whatever the branch, the window is Monday only; the routine must bet from the first Monday snapshot, not the slate printed later in the week. |

- [ ] **Step 3: Write the verdict section, update the two pointers, commit**

```bash
git add research/spread/docs/line-movement-results.md research/spread/CLAUDE.md research/spread/docs/README.md
git commit -m "docs(spread): version B verdict"
```

---

## Hygiene (any time; each is its own small commit)

### Task 12: Mark the estimator modules' `main()` as archived-era

- [ ] In `eval_prediction_tracker_models.py` and `eval_combination_sweep.py`, change the first docstring line to: `"""Estimator core for the spread tree (imported by the live scripts). main() reproduces the archived margin-era tables: archive/spread-margin-era/."""` keeping the rest.
- [ ] Commit: `git commit -am "docs(spread): mark the core modules' main() as margin-era"`.

### Task 13: Clear the margin-era outputs from the data dir (user's call; not committed data)

- [ ] List first: `ls data/processed/pt_leaderboard_* pt_ensemble_* pt_e4_weights_* pt_sweep_* pt_recency_* pt_neff_* pt_ats_tail_* pt_model_eval.json pt_combination_sweep*.json pt_recency_screen.json pt_model_season_stability.csv weekly_slate_2026w2.csv`.
- [ ] Delete only after the user confirms; they are regenerable from the archived scripts at commit `d212537` except `pt_model_season_stability.csv`, which has no script.

### Task 14: Reconcile the two spread CLV figures outside this tree

`docs/clv-analysis.md` (+0.318 on 154 spreads) and `docs/bet-history-analysis-2023-2025.md` (+0.07 on 250) disagree; the 09-02 review flagged it. Not this tree's data, but version B's CLV will be compared to the user's own record, so:

- [ ] Open both, list the join each uses, and write one paragraph in `docs/clv-analysis.md` saying which number to quote and why. Commit.

---

## Self-review

- Spec coverage: audit §1.1 (done), §1.2–1.3 (Task 2, 7, 8), §1.4 (Task 6 extends it), §1.5 (done), §2 (Task 1, 3), §3 (Task 2, 5, 12), §4 (done; Task 13); results doc "What follows" items 1–3 map to Tasks 7/11, 4, 5. `combining-predictions.md` §4 items 1–4 map to Tasks 9, 10, 8/11, 11.
- Placeholders: none; every code step has its code, every run step its expected output.
- Names: `fetch_scores`/`margins` (Task 2) are used by nothing else; `cluster_ols` (existing) is reused by Task 6 and Task 7; `capture_offsets` (Task 7) is only used in `main()`; `stale`/`in_season` (Task 3) only in `collector_health.main`; `first_seen`/`movement_rank` (Task 4) only in their script.
