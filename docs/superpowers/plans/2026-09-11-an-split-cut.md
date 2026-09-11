# Action Network split cut — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** all four tasks done 2026-09-11 — commits c0713e6 (spread, S4), 6ecf0e9 (over-zero), the Saturday task registered and test-fired, docs in the closing commit.

**Goal:** Stop the bulk Action Network scrape now, move both live slates onto the-odds-api and oddspapi, and keep only the one-call-per-game `CFB-AN-History` task running until version B closes in January 2027.

**Architecture:** `weekly_slate.py` prices `book_fair` from the-odds-api snapshot plus Pinnacle (book set version 4, prereg amendment S4) and keeps a price-free Action Network scoreboard call only for the event id version B keys its close on. `best_line_slate.py` takes its game list and every quote from the-odds-api snapshot; the fair is the median of the four regulated books. A Saturday the-odds-api trigger cuts snapshot age on game day. Docs record the retirement and the January sunset.

**Tech Stack:** Python 3.14, pandas, pytest; Windows Task Scheduler via `schtasks`.

**Spec:** `docs/odds-sources-an-vs-apis-2026-09-11.md` (inventory and verdict) and the decision recorded in this session: split the cut.

## Global Constraints

- Root `CLAUDE.md`: no lookahead; data never committed; run from repo root; `python -m pytest` is the default verification.
- `models/over_zero/CLAUDE.md`: no pytest suite in that unit — verify end to end against local data and extend the script's own `_check()`.
- `research/spread/docs/prereg-line-shopping.md`: any change to the live fair set is a numbered amendment with a `BOOK_SET_VERSION` bump and a measured-on-commit paragraph.
- Conventional Commits, subject ≤ 72 chars, stage by path.
- Pre-change baselines already captured to the scratchpad: `spread_fair_v3.csv` (49 games, snapshot `ncaapredictions_20260910T163007Z.csv`) and `oz_old/board_old.json` + `oz_old/best_line_slate_latest.csv` (85 games, AN fair, run 2026-09-11T11:24Z).

---

### Task 1: `weekly_slate.py` — book set version 4

**Files:**
- Modify: `research/spread/scripts/weekly_slate.py` (docstring lines 8–13; constants 104–138; `live_books` 221–255; `build` 486–528; `main` `--no-books` help; `oddsapi_books` docstring)
- Test: `tests/test_spread_oddsapi_books.py`

**Interfaces:**
- Produces: `ws.BOOKS` = the nine `OA_BOOKS` display names + `"Pinnacle"`; `ws.BOOK_SET_VERSION == 4`; `ws.live_books(now)` returns columns `event_id, kick, an_home, an_road, key, rkey` and **no** `quotes`.

- [x] **Step 1: Replace the AN-dedup test with two failing tests**

Delete `test_overlapping_books_are_deduped_with_action_network_winning` and add:

```python
def test_action_network_no_longer_votes():
    """Amendment S4: the fair is the-odds-api's books plus Pinnacle; Caesars left with AN."""
    assert ws.BOOK_SET_VERSION == 4
    assert set(ws.BOOKS) == set(ws.OA_BOOKS.values()) | {"Pinnacle"}
    assert "Caesars" not in ws.BOOKS


def test_live_books_carries_join_keys_and_no_prices(monkeypatch):
    """The AN scoreboard is still read for the event id version B keys its close on -- nothing else."""
    payload = {"games": [{"id": 7, "start_time": "2026-09-12T23:00:00Z",
                          "home_team_id": 1, "away_team_id": 2,
                          "teams": [{"id": 1, "display_name": "Marshall"},
                                    {"id": 2, "display_name": "Middle Tenn"}],
                          "markets": {"68": {"event": {"spread": [
                              {"side": "home", "value": -7.5, "odds": -110}]}}}}]}
    monkeypatch.setattr(ws.clt, "_get", lambda url, params=None, **kw: json.dumps(payload).encode())
    monkeypatch.setattr(ws.time, "sleep", lambda s: None)

    books = ws.live_books(NOW)

    assert list(books.event_id) == [7] and books.key.iloc[0] == "marshall"
    assert "quotes" not in books.columns
```

- [x] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_spread_oddsapi_books.py -q`
Expected: 2 failures (`BOOK_SET_VERSION` is 3; `quotes` column present).

- [x] **Step 3: Edit `weekly_slate.py`**

Constants block (replace `REAL_BOOKS` … `BOOKS`):

```python
# the-odds-api book keys -> display names. Since amendment S4 (2026-09-11) this snapshot plus
# Pinnacle IS the book set: Action Network prices nothing here any more. Its scoreboard is
# still called once per slate, for the event id -- see live_books.
OA_BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betrivers": "BetRivers",
            "betmgm": "BetMGM", "betonlineag": "BetOnline.ag", "bovada": "Bovada",
            "lowvig": "LowVig.ag", "betus": "BetUS", "mybookieag": "MyBookie.ag"}
# Amendment S3 (2026-09-09): Pinnacle, from the oddspapi snapshot (pinnacle_lines), votes too.
# One book, one vote, same as the rest; it is the sharpest book but the median does not know
# that. Its quote is up to 24h old (daily pull); the outlier guard is what stops a stale number
# on a moved line from dragging the fair.
BOOKS = tuple(OA_BOOKS.values()) + ("Pinnacle",)
```

`BOOK_SET_VERSION` comment gains `#   4 = the-odds-api's nine books + Pinnacle; Action Network no longer votes (2026-09-11 on; amendment S4)` and the value becomes `4`.

`live_books`: docstring becomes "Event ids and join keys for games kicking off in the next eight days, from the Action Network scoreboard. No prices since amendment S4 — the fair is the-odds-api's. This call survives only so the forward log carries the `event_id` that `eval_version_b.py` keys the consensus close on; it retires with `CFB-AN-History` (docs/line-timing-collector.md, *Sunset*)." Delete the `quotes = {}` loop and the `"quotes": quotes` entry.

`build`: delete the `an_qs = …` line; `qs = [{**o, **p} for o, p in zip(oa_qs, pin_qs)]` with the comment "the-odds-api and Pinnacle share no book, so this is a plain union"; `t.drop(columns=["oa_quotes"])`.

`oddsapi_books` docstring: replace the "OBSERVATION ONLY … never feed `book_fair`" paragraph with "Since amendment S2 these books vote in `book_fair`; since S4 they and Pinnacle are the whole set." Keep the read-from-disk paragraph.

`main`: `--no-books` help → `"skip the book feeds and the Action Network event-id lookup"`.

Module docstring lines 8–13: `book_fair` = "median home spread across the nine the-odds-api books (DraftKings, FanDuel, BetRivers, BetMGM, BetOnline.ag, Bovada, LowVig.ag, BetUS, MyBookie.ag) plus Pinnacle from oddspapi, after the outlier guard, as of the latest snapshot (≤ 6 h old). Amendment S4; `book_set_version` 4."

- [x] **Step 4: Run the tests**

Run: `python -m pytest tests/test_spread_oddsapi_books.py tests/test_collect_line_timing.py -q`
Expected: all pass.

- [x] **Step 5: Measure the shift and write amendment S4**

Run the scratchpad `measure_spread_fair.py` to `spread_fair_v4.csv`, then compare with v3 on `(road, home)`: games priced, games where `book_fair` moved, median/mean/max |Δ|, `side` flips, count of `edge ≥ 1`. Insert **Amendment S4 — the-odds-api and Pinnacle are the whole live fair (committed 2026-09-11)** above S3 in `research/spread/docs/prereg-line-shopping.md`, same shape as S3: names/extends, motivation (Action Network scrape retired — cite the odds-sources doc), fixed now (set, staleness, ≥ 2 books, guard, tag 4, scope: version B untouched, its close is still AN book 15 from `CFB-AN-History` through the season), measured on commit.

- [x] **Step 6: Commit**

```bash
git add research/spread/scripts/weekly_slate.py tests/test_spread_oddsapi_books.py research/spread/docs/prereg-line-shopping.md
git commit -m "feat(spread): price book_fair from the-odds-api and Pinnacle alone (S4)"
```

---

### Task 2: `best_line_slate.py` — game list and quotes from the-odds-api

**Files:**
- Modify: `models/over_zero/scripts/best_line_slate.py`

**Interfaces:**
- Produces: `oa_games(now, days) -> tuple[pd.DataFrame, str | None]` with columns `kick, home, away, spreads, totals`; `FAIR_BOOKS = ("DraftKings", "FanDuel", "BetRivers", "BetMGM")`; `BOOKS = FAIR_BOOKS + five offshore`.
- Removes: `live_markets`, `join_oa`, `attach_oa`, `_toks`, `_usable`, `OA_ONLY_BOOKS`, the `collect_line_timing` import.

- [x] **Step 1: Extend `_check()` with a failing parse check**

Replace the `join_oa` block at the end of `_check()` with:

```python
    # oa_games: one row per event in the window, schools in CFBD's spelling, the home side's
    # spread and the over's total per book, and the snapshot's own timestamp.
    import tempfile
    global OA_SNAP_DIR
    saved = OA_SNAP_DIR
    with tempfile.TemporaryDirectory() as tmp:
        OA_SNAP_DIR = Path(tmp)
        (OA_SNAP_DIR / "odds_americanfootball_ncaaf_20260911T060004Z.json").write_text(json.dumps({
            "pulled_at": "2026-09-11T06:00:04Z", "events": [{
                "commence_time": "2026-09-12T23:30:00Z", "home_team": "Miami Hurricanes",
                "away_team": "Florida A&M Rattlers", "bookmakers": [{"key": "draftkings", "markets": [
                    {"key": "spreads", "outcomes": [
                        {"name": "Miami Hurricanes", "point": -57.5, "price": -110},
                        {"name": "Florida A&M Rattlers", "point": 57.5, "price": -110}]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 62.5, "price": -108},
                        {"name": "Under", "point": 62.5, "price": -112}]}]}]}]}), encoding="utf-8")
        games, as_of = oa_games(datetime(2026, 9, 11, 12, tzinfo=timezone.utc), 8)
    OA_SNAP_DIR = saved
    assert as_of == "2026-09-11T06:00:04Z" and len(games) == 1, games
    g = games.iloc[0]
    assert g.spreads == {"DraftKings": -57.5} and g.totals == {"DraftKings": (62.5, -108)}, (g.spreads, g.totals)
    assert (g.home, g.away) == ("Miami", "Florida A&M"), (g.home, g.away)
```

Run: `python -c "import sys; sys.argv=['x']; sys.path.insert(0,'models/over_zero/scripts'); import best_line_slate as b; b._check(); print('ok')"`
Expected: `NameError: oa_games`.

- [x] **Step 2: Rewrite the feed**

Imports: drop `import collect_line_timing as clt`; add `sys.path.insert(0, str(REPO))`, `sys.path.insert(0, str(REPO / "scripts"))`, `from oddsapi_flatten import cfbd_schools, school_of`.

Constants:

```python
# the-odds-api book keys -> display names. Since 2026-09-11 this snapshot is the only feed:
# the Action Network scoreboard is no longer read (docs/odds-sources-an-vs-apis-2026-09-11.md).
OA_BOOKS = {...unchanged...}
OA_SNAP_DIR = Path(os.environ["CFB_DATA_ROOT"]) / "ingest" / "oddsapi"
# Only the regulated books vote in the fair spread and fair total. The 1.75 gate was
# calibrated on games.csv -- one CFBD line per game -- and the regulated median is the closest
# live stand-in for that number; until 2026-09-11 it was these four plus Caesars, read live
# from Action Network. The offshore books get their own single-book views, where the number
# is openly one book's number. To let them vote, add them here -- and recalibrate.
FAIR_BOOKS = ("DraftKings", "FanDuel", "BetRivers", "BetMGM")
BOOKS = FAIR_BOOKS + tuple(n for n in OA_BOOKS.values() if n not in FAIR_BOOKS)
```

`oa_games` replaces `live_markets`/`oa_quotes`/`join_oa`/`attach_oa`:

```python
def oa_games(now: datetime, days: int) -> tuple[pd.DataFrame, str | None]:
    """Per-book spread and total for games kicking off in the next `days` days.

    Read from the latest the-odds-api snapshot on disk, never fetched: `CFB-Odds-Snapshot`
    pulls every 6 hours plus Saturdays (see `docs/oddsapi-ingest.md`) and the free plan is 500
    credits a month, so a slate run costs no credits. Every number is therefore AS OF
    `pulled_at`, which the board prints beside every view.
    """
    snaps = sorted(OA_SNAP_DIR.glob("odds_americanfootball_ncaaf_*.json"))
    if not snaps:
        print(f"  no the-odds-api snapshot in {OA_SNAP_DIR}; nothing to score", file=sys.stderr)
        return pd.DataFrame(), None
    payload = json.loads(snaps[-1].read_text(encoding="utf-8"))
    as_of = datetime.fromisoformat(payload["pulled_at"].replace("Z", "+00:00"))
    age_h = (now - as_of).total_seconds() / 3600
    print(f"  the-odds-api snapshot {snaps[-1].name}: {len(payload['events'])} events, "
          f"{age_h:.1f}h old")
    if age_h > 12:
        print(f"  WARNING: snapshot is {age_h:.0f}h old -- is CFB-Odds-Snapshot still "
              f"running?", file=sys.stderr)
    schools = cfbd_schools()
    lo, hi = now, now + timedelta(days=days)
    rows = []
    for e in payload["events"]:
        ko = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        if not (lo <= ko <= hi):
            continue
        spreads, totals = {}, {}
        for b in e.get("bookmakers", []):
            name = OA_BOOKS.get(b.get("key"))
            if name is None:          # a new book must be named before it reaches the board
                print(f"  the-odds-api: unmapped book {b.get('key')!r}, not counted",
                      file=sys.stderr)
                continue
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    if o.get("point") is None or o.get("price") is None:
                        continue
                    # The home team's own outcome carries the home spread in betting sign
                    # (negative = home favored), the convention the model was fit on.
                    if m.get("key") == "spreads" and o.get("name") == e["home_team"]:
                        spreads[name] = float(o["point"])
                    elif m.get("key") == "totals" and o.get("name") == "Over":
                        totals[name] = (float(o["point"]), int(o["price"]))
        rows.append({"kick": ko,
                     # CFBD's spelling of the school, so the board reads as it always has; a
                     # name the strip cannot resolve keeps the vendor's rather than vanishing.
                     "home": school_of(e["home_team"], schools) or e["home_team"],
                     "away": school_of(e["away_team"], schools) or e["away_team"],
                     "spreads": spreads, "totals": totals})
    return pd.DataFrame(rows), payload["pulled_at"]
```

`score`: comment "Only the Action Network books set the number the 1.75 gate reads" → "Only FAIR_BOOKS set the number the 1.75 gate reads; the offshore books reach the board through their own views."

`export_json`: `"asOf": oa_as_of or run_at` for every view; comment: "Every price on the board is as of the snapshot, not this run."

`main`: `games, oa_as_of = oa_games(now, args.days)` and `print(f"{len(games)} games kicking off in the next {args.days} days, priced as of {oa_as_of}")`; `attach_oa` call removed.

Module docstring: "qualify on the fair number -- median spread and median total across the four regulated books in the the-odds-api snapshot (`FAIR_BOOKS`, outlier-guarded), the closest live stand-in for the one-line-per-game distribution the 1.75 threshold was calibrated against".

- [x] **Step 3: Run `_check()` and the script end to end to the scratchpad**

Run: the `_check` one-liner above → `ok`.
Run: `python models/over_zero/scripts/best_line_slate.py --out-dir <scratch>/oz_new --json <scratch>/oz_new/board_new.json`
Expected: exits 0; per-view counts printed; no `Caesars` view.

- [x] **Step 4: Compare with the AN-fair run**

Join `oz_old/best_line_slate_latest.csv` and `oz_new/best_line_slate_latest.csv` on `(kick, home, away)`; report games scored, `spread_fair`/`total_fair` moved (count, median/max |Δ|), pick agreement. Record in `docs/oddsapi-ingest.md` (Task 4).

- [x] **Step 5: Commit**

```bash
git add models/over_zero/scripts/best_line_slate.py
git commit -m "feat(over-zero): score the board from the-odds-api snapshot, not AN"
```

---

### Task 3: Saturday the-odds-api pulls

**Files:** none in git (Task Scheduler); documented in Task 4.

- [x] **Step 1: Register**

```powershell
schtasks /Create /TN "CFB-Odds-Snapshot-Saturday" /SC WEEKLY /D SAT /ST 10:00 /RI 120 /DU 09:59 /TR "\"C:\Users\mckel\dev\cfb\scripts\pull_odds.cmd\"" /F
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Set-ScheduledTask -TaskName CFB-Odds-Snapshot-Saturday -Settings $s
```

Runs 10:00, 12:00, 14:00, 16:00, 18:00 ET Saturdays (the daily task already fires at 20:00). Budget: 5 × 3 credits × ~4.3 Saturdays ≈ 65/month on top of 360 → ~425 of 500.

- [x] **Step 2: Verify**

`Start-ScheduledTask -TaskName CFB-Odds-Snapshot-Saturday`, then `Get-Content data\logs\odds_pull.log -Tail 5` shows a snapshot written and `task_runs.csv` shows `odds_snapshot … 0`.

---

### Task 4: Docs and the January sunset

**Files:**
- Modify: `docs/oddsapi-ingest.md` (Schedule; "Read by the spread slate"; new over-zero paragraph)
- Modify: `docs/line-timing-collector.md` (new `## Sunset — January 2027`)
- Modify: `cfb_system_maker/CLAUDE.md:63`
- Modify: `docs/odds-sources-an-vs-apis-2026-09-11.md` (new `## Decision`)
- Modify: `TODO.md` §2 (new `#an-history-sunset` item)

- [x] **Step 1: Write them** (content in the commit; every number from Tasks 1–3's measurements).
- [x] **Step 2: Full test suite** — `python -m pytest -q` — must be no worse than before the split.
- [x] **Step 3: Commit**

```bash
git add docs/oddsapi-ingest.md docs/line-timing-collector.md cfb_system_maker/CLAUDE.md docs/odds-sources-an-vs-apis-2026-09-11.md TODO.md docs/superpowers/plans/2026-09-11-an-split-cut.md
git commit -m "docs(odds): retire the bulk AN scrape, sunset the history task in January"
```
