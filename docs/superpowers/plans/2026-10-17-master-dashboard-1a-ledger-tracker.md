# Master dashboard slice 1a: bet ledger and Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One SQLite bet ledger with logging, import, explicit grading (separate settle and close states, de-vigged moneyline CLV) and a Tracker page with interval-backed summaries, served from the existing System Maker Flask app.

**Architecture:** A new `cfb_system_maker/hub/` package of blueprints and plain modules. `ledgers/ingest_bets.py` keeps its CLI but exposes a per-bet `grade_bet()` the hub reuses. Every page reads a JSON endpoint that wraps a pure function; writes are loopback-only.

**Tech Stack:** Python 3, Flask (existing app factory `web.create_app`), sqlite3 (stdlib), DuckDB (warehouse, read-only), pandas, numpy, pytest, waitress.

**Spec:** `docs/superpowers/specs/2026-10-17-master-dashboard-design.md` (sections "Build slices", "Architecture", "Tracker", "Errors", "Testing").

## Global Constraints

- Setup once: `python -m pip install -r requirements.txt` (the cloud container starts without Flask/DuckDB/pytest). `CFB_DATA_ROOT` must point at a directory containing a `.cfb-data-root` file before anything imports `cfb_paths`, and `cfb_paths` checks at import time. So the root `tests/conftest.py` (Task 1) sets it at module import, before collection imports any test module, to a session temp dir with the marker, only when the variable is unset. Shared fixtures live in that root conftest so `tests/` and `tests/hub/` both see them.
- Verification: `python -m pytest` (fast suite) green after every task. `tests/test_ingest_bets.py`, `tests/test_web_betlog.py`, `tests/test_matchup_page.py` stay passing unchanged except where a task names the edit.
- Bets file: `<DATA_DIR>/bets/bets.sqlite`, WAL mode, `busy_timeout = 5000`. Never committed (root `CLAUDE.md`: data is never committed).
- All hub paths derive from `app.config["DATA_DIR"]`, never from `cfb_paths` directly.
- Write endpoints (`POST`/`PATCH`/`DELETE`) return 403 unless `request.remote_addr` is `127.0.0.1` or `::1`.
- GET requests never write to the ledger and never create it: they open it with `connect_read` (read-only URI); a missing file reads as an empty ledger.
- Backups: `sqlite3.Connection.backup` only, before every import and every `grade-bets` run, to `<DATA_DIR>/bets/bets-<UTC %Y%m%dT%H%M%S%fZ>-<8 hex>.sqlite`, written as `.part` then `os.replace`d, keep the newest 20.
- Close pass: never looks up a bet before its kickoff. Timed Odds API snapshot in the 90 minutes before kickoff first; else the warehouse close, only if the warehouse was loaded after kickoff. A found close is final. `missing:*` is retried on every run until 48 hours after kickoff; "Grade now" retries it at any age. Full table in Task 5.
- Settlement needs `core.fact_game.completed` true and both scores; scores alone never settle.
- Grading writes are conditional on the bet's `version`; a bet edited mid-run is skipped and picked up next run.
- Stats: Wilson 95% with n = W + L; ROI and mean-CLV intervals by block bootstrap over (season, week), 2000 resamples, seed 7; no interval below 8 weeks ("too few weeks"); splits under 20 settled bets flagged "small sample"; drawdown in dollars only, ordered by `(kickoff_at, placed_at, bet_id)` — never by `settled_at`, which is processing time. CLV summaries use `close_status='found'` bets only, split by source family (`oddsapi` timed, `cfbd` untimed).
- Moneyline CLV: de-vig the paired close multiplicatively; median reference de-vigs each provider first; one side only → `missing:no paired close`.
- Conventional Commits, subject ≤ 72 chars, no `revert` type; end messages with the session's attribution lines.
- Look: existing tokens in `cfb_system_maker/static/tokens/*.css`; PRODUCT.md (dense tables, tabular-nums, color only for meaning).

## Review Focus

1. **Bad odds or stake typed into Log bet** (odds between -99 and +99, decimal odds like 1.91, stake ≤ 0): rejected with 422 and a message, never stored. Test: Task 3 `test_validate_rejects_bad_odds_and_stake`.
2. **Postponed or cancelled game** (score stays null forever): the bet stays pending and out of every total; it is not a loss. Test: Task 5 `test_null_score_stays_pending`.
3. **Imported time with no offset** (`2026-10-17 12:05`): treated as UTC like `ingest_bets.py`, stored with `+00:00`, and the import preview marks it "time assumed UTC". Test: Task 6 `test_naive_time_assumed_utc`.
4. **Empty ledger or a season with no bets**: summary returns zero counts and null rates, no division error, page shows "No bets yet". Test: Task 7 `test_summary_empty`.
5. **Same Board bet clicked twice** (double-submit): two rows are allowed by design, so the Log modal disables its button until the first POST returns. Test: Task 9 manual check, plus `test_two_identical_logged_bets_are_two_rows` in Task 3.

---

## File structure

| File | Responsibility |
| --- | --- |
| `ledgers/ingest_bets.py` (modify) | `grade_bet()` extracted from `build()`; `build(sheet, con=None)`; moneyline de-vig via `pick_moneyline_close()` |
| `ledgers/__init__.py` (create, empty) | make `ledgers` a regular package (tests already import `ledgers.ingest_bets`) |
| `cfb_system_maker/hub/__init__.py` | `register_hub(app)`: blueprints, `hub_nav` context, loopback guard |
| `cfb_system_maker/hub/paths.py` | `bets_db(app_or_dir) -> Path`, `bets_dir(...)` |
| `cfb_system_maker/hub/bets_store.py` | schema, connect, validate, insert, edit rules, soft delete, audit, source lock |
| `cfb_system_maker/hub/backup.py` | `backup(con, bets_dir) -> Path`, retention |
| `cfb_system_maker/hub/grading.py` | settle pass, close pass, `grade_all()` |
| `cfb_system_maker/hub/importer.py` | parse Action Network + hand sheet into candidate rows, duplicate check, commit |
| `cfb_system_maker/hub/stats.py` | `tracker_summary()` and its helpers |
| `cfb_system_maker/hub/tracker.py` | `/tracker` page + `/api/tracker/*` endpoints |
| `cfb_system_maker/templates/hub/_nav.html`, `hub/tracker.html`, `static/hub/tracker.js` | menu and Tracker UI |
| `cfb_system_maker/web.py` (modify) | call `register_hub(app)`; include `_nav.html` in existing page headers |
| `cfb_system_maker/cli.py` (modify) | `grade-bets`, `import-betlog` commands |
| `cfb_system_maker/docs/bet-tracker.md` (create) + `cfb_system_maker/docs/README.md` row | living guide for the ledger |
| `tests/conftest.py` (create) + test files named per task | sets `CFB_DATA_ROOT` at import when unset; fixtures: data root, empty ledger, tiny DuckDB warehouse |

**Spec deviation (record in the spec in Task 10):** the spec says to drop `ingest_bets.py`'s `sys.path` edit. It also imports `match_greenline_books` from `research/totals/scripts/`, which is not a package, so the edit stays; `ledgers/__init__.py` is still added. The hub imports `ledgers.ingest_bets` exactly as `tests/test_ingest_bets.py` does today.

---

### Task 1: Extract `grade_bet()` from `build()` (behaviour unchanged)

**Files:**
- Create: `ledgers/__init__.py`, `tests/conftest.py`, `tests/hub/__init__.py` (empty), `tests/test_ingest_bets_refactor.py`
- Modify: `ledgers/ingest_bets.py:279-379`

**Interfaces:**
- Produces:
  - `Grade` dataclass (frozen): `result: str | None`, `payout/net/roi: float | None`, `open_line/close_line: float | None`, `close_source: str`, `clv: float | None`, `clv_unit: str`.
  - `grade_bet(market: str, side_role: str, line: float | None, odds: float | None, stake: float | None, book: str | None, game_id: int, home_points: int | None, away_points: int | None, lines: pd.DataFrame) -> Grade` — result from the scores (the inline logic now at lines 357-366), close/CLV via `pick_close` + `compute_clv`, settlement via `settle`.
  - `build(sheet: Path, con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame` — opens `DB_PATH` read-only only when `con` is None.
- `tests/conftest.py`: at module level, if `CFB_DATA_ROOT` is unset, create `tempfile.mkdtemp()/.cfb-data-root` and set the variable (this runs before any test module is imported). Fixtures: `data_root` (a fresh marked tmp dir per test, passed to `create_app(data_dir=...)`; it does not touch the env var), `warehouse` (in-memory DuckDB with `core.fact_game` including `completed`, `core.fact_game_line`, `core.fact_game_odds`, `meta.load_report`; helpers `add_game(con, game_id, start_utc, home, away, home_pts, away_pts, completed=True)`, `add_line(con, game_id, provider, **cols)`, `add_odds(...)` and `set_loaded_at(...)` used from Task 5).

- [ ] **Step 1: Write the characterization test against the current code**

`test_build_output_is_pinned(tmp_path, warehouse)`: three games (a home spread win, a total under push, a moneyline away win), a sheet with one bet each plus one unmatched row; call `build(sheet, con=warehouse)`; assert the exact `result`, `net`, `close_line`, `close_source`, `clv`, `clv_unit`, `match_status` for all four rows. Values: spread home -3.5, final 28-21, DK close -4.5 → win, net +100.0 at -110/110, clv 1.0 points; total under 54.0, final 30-24 → push, net 0.0; unmatched row → `match_status == "unmatched"`. The moneyline row asserts today's raw value (`compute_clv("moneyline","away",None,120,150)` shape) and is updated in Task 2.

- [ ] **Step 2: Run it; expect FAIL** — `build()` has no `con` parameter.

Run: `python -m pytest tests/test_ingest_bets_refactor.py -v`

- [ ] **Step 3: Add the `con` parameter only; run again; expect PASS.** Record `python ledgers/ingest_bets.py --self-check` output (`self-check ok`).

- [ ] **Step 4: Extract `Grade` and `grade_bet()`; make `build()` call it per matched row.** No change to `OUT_COLS`, `report()`, or CLI flags.

- [ ] **Step 5: Add `test_grade_bet_matches_build`** — for each fixture bet, `grade_bet(...)` equals the corresponding `build()` row fields.

- [ ] **Step 6: Run** `python -m pytest tests/test_ingest_bets.py tests/test_ingest_bets_refactor.py -v` and `python ledgers/ingest_bets.py --self-check`. Expected: all pass, `self-check ok`.
- [ ] **Step 7: Clean-environment check:** `env -u CFB_DATA_ROOT python -m pytest -q` collects and runs (no `RuntimeError` from `cfb_paths` at collection). Record the pass/fail counts; tests that already skip without a live warehouse keep skipping.

- [ ] **Step 8: Commit** `refactor(ledgers): extract grade_bet from build, accept a connection`

---

### Task 2: De-vigged moneyline CLV

**Files:**
- Modify: `ledgers/ingest_bets.py` (`pick_close`, `compute_clv`, `self_check`, `build`/`grade_bet` moneyline branch)
- Modify: `tests/test_ingest_bets.py:127-134` (`test_moneyline_clv_is_a_probability_not_points` → new semantics)
- Create: `tests/test_clv_moneyline.py`

**Interfaces:**
- Produces: `devig_pair(home_odds: int, away_odds: int) -> tuple[float, float]`; `pick_moneyline_close(lines: pd.DataFrame, game_id: int, side_role: str, book: str | None) -> tuple[float | None, str]` returning (fair close probability of the bettor's side, source). The cutoff and provenance of the close are Task 5's job, not this function's. Source is the book key, `median(<n> providers)`, `no line data`, or `missing:no paired close`.
- `compute_clv("moneyline", side_role, line, close, odds)` now takes `close` = fair probability and returns `(round(close - implied_prob(odds), 4), "probability")`.
- `grade_bet` uses `pick_moneyline_close` for moneyline; `Grade.close_line` holds the fair probability for moneyline.

- [ ] **Step 1: Write failing tests** in `tests/test_clv_moneyline.py`:
  - `test_devig_own_book`: DraftKings `moneyline_home=-150, moneyline_away=130`; bet away +140 at DraftKings → fair 0.420168 (abs 1e-6), source `draftkings`, CLV `0.0035`.
  - `test_devig_median_per_provider_first`: providers A (-150/+130) and B (-120/+100), bet book `SomeLocalBook` → fair away = mean of 0.420168 and 0.478261 (median of two), source `median(2 providers)`, CLV `0.0325`.
  - `test_one_sided_close_is_missing`: only `moneyline_home` present → `(None, "missing:no paired close")`; `grade_bet(...).clv is None`.
- [ ] **Step 2: Run; expect FAIL** (`pick_moneyline_close` undefined).
- [ ] **Step 3: Implement** `pick_moneyline_close`; switch the moneyline branch; update `self_check` moneyline lines and the existing test to the paired form.
- [ ] **Step 4: Update Task 1's pinned moneyline row** to the de-vigged value.
- [ ] **Step 5: Run** the three test files + `--self-check`. Expected PASS.
- [ ] **Step 6: Commit** `fix(ledgers): de-vig paired close for moneyline CLV` with a body saying the `ingest_bets.py` moneyline column changes from raw implied-probability movement to de-vigged probability CLV.

---

### Task 3: Ledger store — schema, validation, edits, audit, source lock, versioned writes

**Files:**
- Create: `cfb_system_maker/hub/__init__.py` (empty `register_hub` stub for now), `cfb_system_maker/hub/paths.py`, `cfb_system_maker/hub/bets_store.py`, `tests/hub/test_bets_store.py`

**Schema** (the whole contract; nothing else is added later in 1a):

`bets`:

| Column | Type | Set by |
| --- | --- | --- |
| `bet_id` | INTEGER PRIMARY KEY | insert |
| `version` | INTEGER NOT NULL DEFAULT 1 | +1 on every update, by edits and by grading |
| `placed_at` | TEXT NOT NULL (ISO 8601 with offset) | insert/edit |
| `placed_at_estimated` | INTEGER NOT NULL DEFAULT 0 | importer (1 = kickoff used) |
| `game_id` | INTEGER NULL | insert/edit/match pass |
| `kickoff_at` | TEXT NULL (UTC ISO) | match pass, from `core.fact_game.start_date`; the economic ordering time |
| `season`, `week` | INTEGER NULL | match pass, from the game |
| `away`, `home` | TEXT NOT NULL | insert/edit |
| `market` | TEXT NOT NULL (`spread`/`total`/`moneyline`) | insert/edit |
| `side` | TEXT NOT NULL (team name as in `away`/`home`, or `OVER`/`UNDER`) | insert/edit |
| `line` | REAL NULL (NULL only for moneyline) | insert/edit |
| `odds` | INTEGER NOT NULL | insert/edit |
| `stake` | REAL NOT NULL | insert/edit |
| `book` | TEXT NULL (stored as `normalize.provider_key(book)`) | insert/edit |
| `source`, `notes` | TEXT NOT NULL, TEXT NULL | insert/edit |
| `origin` | TEXT NOT NULL (`logged`/`action_network`/`csv`) | insert |
| `import_ref` | TEXT NULL (JSON) | importer |
| `result`, `pnl`, `settled_at` | TEXT/REAL/TEXT NULL | settle pass (`settled_at` is processing time only) |
| `first_settled_at` | TEXT NULL | settle pass, once; never cleared or editable |
| `close_status` | TEXT NOT NULL DEFAULT `'pending'` | close pass (`pending`/`found`/`missing:<reason>`) |
| `close_line`, `close_price`, `close_source`, `close_quoted_at`, `clv`, `clv_unit`, `close_checked_at` | NULL | close pass |
| `deleted_at`, `created_at`, `updated_at` | TEXT | store |

`bet_audit`: `audit_id INTEGER PRIMARY KEY, bet_id INTEGER NOT NULL, changed_at TEXT NOT NULL, actor TEXT NOT NULL ('user'/'grader'/'import'), action TEXT NOT NULL ('insert'/'edit'/'grade'/'delete'), field TEXT NULL, old TEXT NULL, new TEXT NULL`. One row per changed field; `insert` and `delete` write one row with `field` NULL.

**Interfaces:**
- `paths.bets_dir(data_dir: Path) -> Path` (`data_dir / "bets"`); `paths.bets_db(data_dir) -> Path`.
- `init_db(db_path: Path) -> None` — creates the folder, file and schema; sets `journal_mode=WAL`. Called only by write paths (POST/PATCH/DELETE, import commit, grading, CLI).
- `connect_write(db_path) -> sqlite3.Connection` — calls `init_db`, then `busy_timeout=5000`, `row_factory=sqlite3.Row`, `foreign_keys=ON`.
- `connect_read(db_path) -> sqlite3.Connection | None` — `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`; returns `None` when the file does not exist (GET handlers then answer as an empty ledger). Never creates anything.
- `class BetError(ValueError)` with `.status: int` (422 validation, 404 missing, 409 lock or stale version).
- `canonical_side(market, side, away, home) -> str` — `home`/`away` → that team's name; totals → `OVER`/`UNDER`; a spread or moneyline side matching neither team → `BetError(422)`.
- `validate(fields: dict) -> dict` — market in the three values; `canonical_side`; `placed_at` must carry an offset (naive → 422; the importer localizes first); `odds` an integer with `odds <= -100 or odds >= 100`; `stake > 0`; `line` required unless moneyline; `source` non-empty; `book` through `provider_key`.
- `insert_bet(con, fields: dict, origin: str, actor: str = "user") -> int`
- `get_bet(con, bet_id) -> sqlite3.Row`; `list_bets(con, season=None, source=None, status=None, include_deleted=False) -> list[sqlite3.Row]` (status `pending|settled|all`).
- `update_bet(con, bet_id, changes: dict, expected_version: int | None = None, actor="user") -> int` (returns the new version) — runs `BEGIN IMMEDIATE`; if `expected_version` is given and differs → `BetError(409, "stale")`. Edit rules: `game_id, market, side, line, odds, stake` clear `result, pnl, settled_at` and every close field (`close_status='pending'`, `kickoff_at/season/week` cleared when `game_id` changes); `book` clears the close fields only; `source` → `BetError(409)` when `first_settled_at` is set; `first_settled_at`, `version`, `origin` are never editable (422).
- `write_grade(con, bet_id, expected_version: int, fields: dict) -> bool` — the grader's only write: `UPDATE bets SET ..., version = version + 1 WHERE bet_id = ? AND version = ? AND deleted_at IS NULL`; returns `False` (no write, no audit) when the row changed since it was read. Audit rows with `actor='grader'`.
- `soft_delete(con, bet_id) -> None` — sets `deleted_at`, bumps `version`, audit `action='delete'`.

- [ ] **Step 1: Write failing tests:** `test_schema_and_pragmas` (WAL, busy_timeout 5000, every column above present), `test_insert_and_audit`, `test_two_identical_logged_bets_are_two_rows`, `test_validate_rejects_bad_odds_and_stake` (odds 50, -99, 1.91; stake 0, -5 → 422), `test_canonical_side` (`home` on Navy @ Notre Dame → `Notre Dame`; `under` → `UNDER`; `Army` → 422), `test_line_edit_clears_settlement_and_close`, `test_book_edit_clears_close_only`, `test_source_lock_survives_cleared_grade` (set `first_settled_at`, edit line, then edit source → 409), `test_first_settled_at_not_editable`, `test_soft_delete_keeps_row_and_audit`, `test_connect_read_never_creates` (missing path → `None`, path still absent), `test_write_grade_rejects_stale_version` (two connections: A reads version 1; B edits stake 100 → 200 (version 2, settlement cleared); A's `write_grade(..., expected_version=1, pnl=90.91)` returns False; row has stake 200, `pnl` NULL, version 2).
- [ ] **Step 2: Run; expect FAIL** (module missing).
- [ ] **Step 3: Implement** per the schema and interface.
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_store.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): add SQLite bet ledger with audit and source lock`

---

### Task 4: WAL-safe backups

**Files:**
- Create: `cfb_system_maker/hub/backup.py`, `tests/hub/test_bets_backup.py`

**Interfaces:**
- `backup(con: sqlite3.Connection, bets_dir: Path, now: datetime | None = None, keep: int = 20) -> Path` — writes `con.backup()` into `bets-<UTC %Y%m%dT%H%M%S%fZ>-<uuid4 hex[:8]>.sqlite.part`, closes it, then `os.replace` to the name without `.part`; deletes the oldest finished backups beyond `keep` (ordered by the timestamp in the name, then name). A leftover `.part` is never counted or restored.

- [ ] **Step 1: Write failing tests:**
  - `test_backup_includes_uncheckpointed_wal`: `PRAGMA wal_autocheckpoint=0`, insert 3 bets, keep the connection open; assert `bets.sqlite-wal` size > 0; `backup()`; open the backup read-only and assert 3 bets.
  - `test_plain_copy_loses_wal_rows` (documents why): `shutil.copy` of the main file alone has fewer than 3 bets.
  - `test_same_second_backups_do_not_collide`: two `backup()` calls with the same `now` → two distinct files, both readable.
  - `test_retention_keeps_newest_20`: 22 backups with increasing `now` → 20 files, the two oldest gone; no `.part` files remain.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_backup.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): back up the ledger with the SQLite backup API`

---

### Task 5: Grading passes

**Files:**
- Create: `cfb_system_maker/hub/grading.py`, `tests/hub/test_bets_lifecycle.py`
- Modify: `ledgers/ingest_bets.py` `load_games` (also select `completed`; `build()` treats `completed` false as no score, so a live score never grades a hand sheet either)

**Interfaces:**
- Consumes: `ledgers.ingest_bets.grade_bet`, `book_lines`, `load_games`, `find_game`, `resolve_side` (Tasks 1–2); `bets_store.connect_write`, `write_grade` (Task 3); `backup.backup` (Task 4).
- `@dataclass GradeReport`: `settled: int`, `closes_found: int`, `closes_missing: int`, `unmatched: list[tuple[int, str]]`, `mismatches: list[tuple[int, str]]` (imported bets whose Action Network `result` in `import_ref` differs from ours), `stale: int` (writes skipped because the bet changed mid-run), `still_pending: int`.
- `grade_all(bets_con, wh_con, now: datetime, bets_dir: Path, force_close_retry: bool = False) -> GradeReport` — backup first. Every pass reads each bet's `version`, computes, and writes through `write_grade(..., expected_version)`; a `False` return counts as `stale` and the bet is picked up on the next run. No transaction spans the warehouse read.
- **Match pass:** `game_id IS NULL` → `find_game` + `resolve_side`; sets `game_id, kickoff_at, season, week`; unmatched or reversed recorded, never guessed. A bet logged with a `game_id` gets `kickoff_at/season/week` the same way.
- **Settle pass:** `settled_at IS NULL AND deleted_at IS NULL` and the game has `completed IS TRUE` with both scores non-null → `result, pnl (= net), settled_at=now`, `first_settled_at` if null. Non-null scores with `completed` false or null → stays pending.
- **Close pass:** the reference close, cutoff and provenance rule:
  1. Only bets whose `kickoff_at <= now` are looked up. Before kickoff nothing is stored, so a Friday "Grade now" cannot freeze a Friday quote.
  2. **Timed quote first:** `core.fact_game_odds` (Odds API snapshots, each with `pulled_at`) — the last snapshot with `kickoff_at − 90 min <= pulled_at <= kickoff_at` for the bet's book (`provider_key` on both sides), else the median across books in that window (moneyline de-vigged per book first, as Task 2). `close_source = "oddsapi:<book>"` or `"oddsapi:median(<n>)"`; `close_quoted_at = pulled_at`.
  3. **Untimed close second:** `core.fact_game_line` `*_close` / `moneyline_*` (Task 2's `pick_close` / `pick_moneyline_close`), accepted only when `max(meta.load_report.loaded_at)` for `game_lines` is after `kickoff_at` — i.e. the vendor's value was read after the game started, so it is the vendor's final pre-game line rather than a Friday quote. `close_source = "cfbd:<book>"` or `"cfbd:median(<n>)"`; `close_quoted_at` NULL. If the warehouse was last loaded before kickoff, the bet stays `pending` (reason in the report: `warehouse older than kickoff`).
  4. A found close is final and never retried, except after an edit resets it to `pending`.
- State transitions (the tests come from this table):

| From | Condition at this run | To |
| --- | --- | --- |
| `pending` | kickoff in the future | `pending` (nothing stored) |
| `pending` / `missing:*` | timed or accepted untimed close exists | `found` |
| `pending` | after kickoff, warehouse loaded before kickoff | `pending` |
| `pending` / `missing:*` | after kickoff, warehouse loaded after kickoff, no usable close | `missing:no line data` or `missing:no paired close` |
| `missing:*` | `now > kickoff_at + 48 h` and not forced | unchanged, not looked up |
| `missing:*` | `force_close_retry=True` | looked up again (any age) |
| `found` | any run, forced or not | unchanged |
| any | edit to game, market, side, line, odds, stake or book | `pending`, close fields cleared (Task 3) |

  `close_checked_at = now` on every lookup.

- [ ] **Step 1: Write failing tests** (shared `warehouse` fixture gains `add_odds(con, game_id, book, pulled_at, market, side, line, odds)` and `set_loaded_at(con, ts)`; fixed `now`):
  - `test_friday_grade_does_not_freeze_quote`: kickoff Sat 19:00Z; Friday 12:00Z run with a DK line of −3 present → `close_status='pending'`, `close_line` NULL; the line moves to −4.5 and a snapshot at Sat 18:45Z says −4.5; Sat 23:00Z run → `found`, `close_line=-4.5`, `close_source='oddsapi:draftkings'`, `close_quoted_at` = 18:45Z.
  - `test_untimed_close_needs_post_kickoff_load`: no snapshots; `fact_game_line` close −4; `loaded_at` Fri → Sunday run leaves `pending`; `loaded_at` Sun 08:00Z → `found`, `close_source='cfbd:draftkings'`.
  - `test_snapshot_outside_window_ignored`: only a snapshot at kickoff − 3 h → falls through to the untimed rule.
  - `test_state_table_missing_and_forced`: no line data, warehouse loaded after kickoff → `missing:no line data`; rerun at kickoff + 47 h → looked up (`close_checked_at` moves); at kickoff + 49 h → not looked up; `force_close_retry=True` at + 49 h → looked up; then add a snapshot and force again → `found`; force once more → still `found`, `close_checked_at` unchanged.
  - `test_live_score_does_not_settle`: scores 14–7 with `completed=False` → pending; refresh to 28–21 `completed=True` → settled with the final score's result.
  - `test_null_score_stays_pending` (Review Focus 2).
  - `test_grade_skips_bet_edited_mid_run`: patch `grading` so that between the read and the write a second connection edits the stake → report `stale == 1`, stored `pnl` NULL, next run settles with the new stake.
  - `test_reversed_teams_flagged`: imported bet with home/away swapped → `unmatched` note contains "looks reversed", `game_id` stays null.
  - `test_first_settled_at_is_never_cleared`.
  - `test_an_result_mismatch_listed`: `import_ref` says `win`, the score says loss → `loss` stored, bet in `mismatches`.
  - `test_grade_all_backs_up_first`.
  - In `tests/test_ingest_bets.py`: `test_build_ignores_incomplete_games` (`completed=False` with scores → `result` empty).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_lifecycle.py tests/test_ingest_bets.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): grade bets in separate settle and close passes`

---

### Task 6: Import with duplicate review

**Files:**
- Create: `cfb_system_maker/hub/importer.py`, `tests/hub/test_hub_import.py`, `tests/hub/fixtures/an_export.csv`, `tests/hub/fixtures/manual_sheet.csv`
- Modify: `cfb_system_maker/betlog.py` — rename `_build_games_by_date` to `build_games_by_date` (keep a private alias); add `parse_betlog_rows`

**Interfaces:**
- `betlog.parse_betlog_rows(path) -> list[BetlogRow]`, `@dataclass(frozen=True) BetlogRow`: `row_number: int` (1-based data row in the file), `raw: dict[str, str]` (every original column), `status: str` (`ok | out_of_scope | malformed`), `reason: str` (e.g. `"14 fields expected, got 12"`, `"Odds is not a number"`, `"live period"`), `parsed: RawBetRow | None`. In scope: `spread_home`, `spread_away`, `over`, `under`, **`ml_home`, `ml_away`** for period `game`. `parse_betlog_csv` becomes a thin wrapper over it that keeps today's output exactly (moneyline rows still count as out of scope there, so `/betlog` and `tests/test_betlog.py` are unchanged).
- `@dataclass Candidate`: `fields: dict`, `status: str` (`new | possible_duplicate | unmatched | malformed | out_of_scope`), `note: str`, `duplicate_of: int | None` (existing bet_id), `duplicate_of_row: int | None` (an earlier row in the same file), `row_number: int`, `import_ref: str` (the original row as JSON plus `unit_dollars`).
- `preview_import(path, kind, data_dir, bets_con, unit_dollars) -> list[Candidate]` — `kind` is `action_network` or `sheet`. Every file row produces one candidate, including malformed and out-of-scope rows with their reason.
  - Action Network: `parse_betlog_rows` → matched with `build_games_by_date`; `side` through `bets_store.canonical_side` (so `spread_home` on `NAVY @ ND` becomes `Notre Dame`); `ml_*` → `market='moneyline'`, `line=None`; `placed_at = start_time`, `placed_at_estimated=1`; `stake = units_wagered * unit_dollars` (required, else `BetError(422)`); `book=None`; `source='import'`.
  - Sheet: columns of `ledgers/manual_bets_template.csv`; naive `placed_at` localized to UTC with note "time assumed UTC"; `side` through `canonical_side`.
  - `last_unit_dollars(bets_con) -> float | None` reads the newest `action_network` row's `import_ref`.
- **Duplicate rule**, applied after matching, against existing non-deleted bets and against earlier rows of the same file: equal `game_id, market, side` (canonical), `line`, `odds`, and books that are **equal or unknown on either side** (`None` matches any book; two different known books are different wagers). A match is `possible_duplicate`, never skipped.
- `commit_import(bets_con, candidates, keep: set[int], bets_dir) -> int` — backup, then insert the kept candidates (UI default: every `new` row ticked, no `possible_duplicate` row ticked; `malformed`/`unmatched`/`out_of_scope` cannot be ticked).

- [ ] **Step 1: Write failing tests:** `test_parse_rows_keeps_raw_and_reasons` (the `tests/fixtures/betlog_sample.csv` rows come back with `row_number`, the full `raw` dict, and a reason on each malformed and out-of-scope row), `test_parse_betlog_csv_unchanged` (same counts as today), `test_an_moneyline_supported` (`ml_home -180` → `market='moneyline'`, `line is None`, side = home team), `test_an_mapping_units_to_dollars` (2 units at $50 → stake 100.0, `placed_at_estimated == 1`, `ND` → Notre Dame, `spread_home` → `side == 'Notre Dame'`), `test_an_requires_unit_dollars`, `test_last_unit_dollars_remembered`, `test_logged_at_named_book_vs_an_row_is_possible_duplicate` (logged at `DraftKings`, AN row with no book → `possible_duplicate`, `duplicate_of` = that bet), `test_different_known_books_are_not_duplicates`, `test_duplicate_within_one_file` (same AN row twice → second has `duplicate_of_row` = first), `test_naive_time_assumed_utc` (Review Focus 3), `test_commit_inserts_only_kept_and_backs_up`.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_hub_import.py tests/test_betlog.py tests/test_web_betlog.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): import bets with reviewed duplicate detection`

---

### Task 7: Tracker statistics

**Files:**
- Create: `cfb_system_maker/hub/stats.py`, `tests/hub/test_hub_tracker_stats.py`

**Interfaces:**
- Consumes: `cfb_system_maker.backtest._wilson_interval(hit_rate: float, n: int)` (reuse, do not copy).
- `tracker_summary(bets: list[Mapping], *, reps: int = 2000, seed: int = 7) -> dict` where each bet has `bet_id, season, week, kickoff_at, placed_at, source, market, stake, pnl, result, clv, clv_unit, close_source, close_status`. Returns:
  - `totals`: `{n, wins, losses, pushes, win_rate, win_rate_ci, staked, pnl, roi, roi_ci, weeks, small_sample, too_few_weeks}`
  - `clv`: list of `{unit, close_source, n, mean, mean_ci, median, positive_rate}` over `close_status='found'` bets only, one entry per unit × source family (`oddsapi`, `cfbd`) plus one per unit with `close_source="all"`
  - `by_source`, `by_market`, `by_week`: dicts of the `totals` shape
  - `drawdown`: `{max_dollars, peak_at_bet_id, trough_at_bet_id}`; `curve`: list of `{bet_id, kickoff_at, cum_pnl}`
- **Curve order is economic, not processing:** `(kickoff_at, placed_at, bet_id)`. `settled_at` is never used for ordering, so batch grading, import order and regrading cannot move a bet.
- Bootstrap: resample whole (season, week) blocks with replacement, recompute ROI = Σpnl/Σstake and mean CLV; 2.5/97.5 percentiles; `None` and `too_few_weeks=True` when weeks < 8.

- [ ] **Step 1: Write failing tests:**
  - `test_wilson_excludes_pushes` (6-4-2 → n=10, CI equals `_wilson_interval(0.6, 10)`).
  - `test_bootstrap_resamples_whole_weeks`: 8 weeks, each week one bet with stake 100 and pnl in `[-100, -50, 0, 10, 20, 50, 90, 100]`. Independently: resampling 8 blocks with replacement gives an ROI whose expectation is the mean (0.15) and whose standard deviation is `pstdev(pnl/100) / sqrt(8)` = 0.2229 (to 4 dp, computed in the test with `statistics.pstdev`). Assert the bootstrap draws (exposed via `_bootstrap_draws(...)`, reps 20000) have mean within 0.005 and sd within 0.01 of those values.
  - `test_bootstrap_keeps_week_together`: two bets per week with opposite pnl (+100/−100) → every draw's ROI is exactly 0, so `roi_ci == (0.0, 0.0)`; resampling single bets would not give this.
  - `test_too_few_weeks` (7 weeks → `roi_ci is None`), `test_small_sample_flag` (19 settled → True, 20 → False).
  - `test_clv_split_by_unit_and_source` (`missing:*` and `pending` bets excluded from CLV).
  - `test_drawdown_ignores_grading_and_import_order`: same 6 bets supplied in two orders with different `settled_at` and `bet_id` assignments but the same `kickoff_at` → identical `max_dollars` and curve P&L sequence; no `pct` key anywhere.
  - `test_summary_empty` (Review Focus 4), `test_pending_and_deleted_excluded`.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** with numpy (`np.random.default_rng(seed)`).
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_hub_tracker_stats.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): tracker summary with Wilson and week-block intervals`

---

### Task 8: Hub registration, Tracker API, loopback guard

**Files:**
- Modify: `cfb_system_maker/hub/__init__.py`, `cfb_system_maker/web.py:473-510` (call `register_hub(app)` after existing routes)
- Create: `cfb_system_maker/hub/tracker.py`, `tests/hub/test_hub_tracker_api.py`, `tests/hub/test_hub_guard.py`

**Interfaces:**
- `register_hub(app: Flask) -> None` — registers blueprint `tracker` (no URL prefix), adds `before_request` loopback guard for non-GET methods on `/api/tracker/`, injects `hub_nav` (list of `{label, href, active}`: Board placeholder hidden until 1b, Tracker, Systems `/`, Lab link from env `CFB_LAB_URL` default `http://127.0.0.1:8501`).
- Endpoints (JSON; errors `{error, message}` with `BetError.status`):
  - `GET /api/tracker/summary?season=` → `tracker_summary(...)`
  - `GET /api/tracker/bets?season=&source=&status=` → `{bets: [...]}`
  - `POST /api/tracker/bets` → `{bet_id}` 201
  - `PATCH /api/tracker/bets/<id>`, `DELETE /api/tracker/bets/<id>` → 204
  - `POST /api/tracker/import/preview` (multipart `file`, `kind`, `unit_dollars`) → `{candidates: [...]}`
  - `POST /api/tracker/import/commit` (JSON `{candidates, keep}`) → `{inserted}`
  - `POST /api/tracker/grade` (`force_close_retry` bool) → `GradeReport` as JSON; opens the warehouse read-only from `<DATA_DIR>/cfb.duckdb`; a locked warehouse → 503 `{error:"warehouse_busy"}`.
- GET handlers use `connect_read` (missing file → empty results, no file created); write handlers use `connect_write`. The connection is opened per request and closed in `teardown_request`. `PATCH` takes the bet's `version` and passes it as `expected_version`, so an edit against a stale page gets 409.

- [ ] **Step 1: Write failing tests:** API round trip (create, list, patch, delete, summary) with `create_app(data_dir=data_root)`; `test_get_never_writes` (file mtime and `bet_audit` count unchanged after every GET endpoint); `test_first_get_creates_nothing` (fresh data dir, every GET → 200 with empty results and `bets/` still absent); `test_non_loopback_write_403` (`environ_base={"REMOTE_ADDR": "10.0.0.5"}` on POST/PATCH/DELETE → 403; same request from 127.0.0.1 → allowed); `test_bet_error_status_mapping` (422/404/409).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub -v` and the full `python -m pytest`. Expected PASS, including `tests/test_web_betlog.py` unchanged.
- [ ] **Step 5: Commit** `feat(hub): register hub and serve the tracker API`

---

### Task 9: Tracker page and menu

**Files:**
- Create: `cfb_system_maker/templates/hub/_nav.html`, `cfb_system_maker/templates/hub/tracker.html`, `cfb_system_maker/templates/hub/_log_bet.html`, `cfb_system_maker/static/hub/tracker.js`, `cfb_system_maker/static/hub/log_bet.js`, `tests/hub/test_hub_tracker_page.py`
- Modify: `cfb_system_maker/templates/dashboard.html`, `index.html`, `compare.html`, `betlog.html`, `search_run.html` — one `{% include "hub/_nav.html" %}` line in each page header

**Interfaces:**
- `GET /tracker` renders `hub/tracker.html`; the JS fetches `/api/tracker/summary` and `/api/tracker/bets`.
- Page sections: season totals row; CLV table per unit; splits table (source / market / week tabs); bankroll curve as inline SVG; bets table with edit, delete, and status filter; Import panel (file, kind, unit dollars → preview table with checkboxes → commit); "Grade now" button.
- Copy: intervals render as `52.1% (47.9–57.8)`; `too_few_weeks` renders "too few weeks"; `small_sample` greys the row and adds "small sample"; empty ledger renders "No bets yet".
- Log bet modal: `_log_bet.html` + `log_bet.js` export `openLogBet(prefill: {game_id?, away?, home?, market?, side?, line?, source?})`. Fields: away, home, market (select), side (select built from the away/home values plus Over/Under), line (hidden for moneyline), odds, stake, book, source (select of the known sources plus free text), notes, placed_at (defaults to browser local time with offset, editable). Prefilled fields are shown read-only with an "edit" toggle; with no prefill every field is editable. A bet with no `game_id` is matched by the next grading run's match pass, exactly like an import, and shows "not matched yet" until then. POSTs `/api/tracker/bets`; a 422 shows inline. The Tracker opens it empty from "Add bet"; slice 1b's Board and preview call it with a prefill.
- The Log/Save buttons disable while a request is in flight (Review Focus 5).

- [ ] **Step 1: Write failing tests:** `/tracker` returns 200 and contains the nav entries; each existing page (`/`, `/compare`, `/betlog`) contains the nav include; CSP header unchanged for `/tracker` (inline `style=` is not used; the curve is SVG attributes only).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** the template, JS and nav include.
- [ ] **Step 4: Run** `python -m pytest`. Expected PASS.
- [ ] **Step 5: Manual check** (`python -m cfb_system_maker web` with a scratch `CFB_DATA_ROOT`): log two bets with Add bet, typing teams, market, side and line by hand (one with odds 1.91 to see the inline error), click Grade now and see both matched to their games, import `tests/hub/fixtures/an_export.csv` at $50/unit, see one possible duplicate unticked, click Grade now, confirm totals, CLV and curve render and no browser console CSP errors. Note results in the PR description.
- [ ] **Step 6: Commit** `feat(hub): tracker page and shared menu`

---

### Task 10: CLI commands, docs, spec note

**Files:**
- Modify: `cfb_system_maker/cli.py` (parser near line 1000, dispatch near line 98)
- Create: `cfb_system_maker/docs/bet-tracker.md`; Modify: `cfb_system_maker/docs/README.md` (one row)
- Modify: `docs/superpowers/specs/2026-10-17-master-dashboard-design.md` (Grading: the `sys.path` deviation; Storage: `placed_at_estimated` is a column rather than a note; Import: preview and commit are two endpoints). The close-pass, settlement, versioning, drawdown-order and backup-name changes from the second plan review are written into the spec in the same commit as this plan revision, not in Task 10.
- Modify: `tests/test_cli.py` (new cases)

**Interfaces:**
- `python -m cfb_system_maker grade-bets [--force-close-retry]` → runs `grade_all` against `<data_dir>/bets/bets.sqlite` and `<data_dir>/cfb.duckdb`, prints the `GradeReport`, exit 0 (1 if the warehouse is locked).
- `python -m cfb_system_maker import-betlog --unit-dollars N [--dry-run]` → reads the legacy `/betlog` store via `betlog.load_betlog(data_dir)`, maps each record to ledger fields with the Task 6 Action Network mapping (`origin='action_network'`, `placed_at` = kickoff with `placed_at_estimated=1`, falling back to the record date at 00:00 UTC when a legacy record has no kickoff; `stake = units_wagered * N`), runs the Task 6 duplicate check, prints counts, and on non-dry-run commits only `new` rows (duplicates are listed, not inserted). Never runs at app startup.
- `bet-tracker.md` (undated living guide): where the file lives, the backup rule, settle vs close states, the CLV definition, the source lock, the two CLI commands, and what the Tracker's intervals mean. Points at `docs/model-evaluation-standard.md`.

- [ ] **Step 1: Write failing CLI tests:** `grade-bets` on an empty ledger prints zero counts and exits 0; `import-betlog --dry-run --unit-dollars 50` on a saved legacy betlog inserts nothing and prints the new/duplicate counts; without `--unit-dollars` exits 2.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** the commands; write the guide and README row; add the spec deviation sentence.
- [ ] **Step 4: Run** `python -m pytest` (includes `tests/test_docs_index.py`). Expected PASS.
- [ ] **Step 5: Commit** `feat(cli): grade-bets and import-betlog; document the bet tracker`

---

## Done when

- Full `python -m pytest` green on the branch; `python ledgers/ingest_bets.py --self-check` prints `self-check ok`.
- The Task 9 manual check is recorded in the PR.
- A draft PR is open from `claude/project-thread-kpqdo0`, and the TODO items for later phases are untouched.
