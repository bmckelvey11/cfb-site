# Master dashboard slice 1a: bet ledger and Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One SQLite bet ledger with logging, import, explicit grading (separate settle and close states, de-vigged moneyline CLV) and a Tracker page with interval-backed summaries, served from the existing System Maker Flask app.

**Architecture:** A new `cfb_system_maker/hub/` package of blueprints and plain modules. `ledgers/ingest_bets.py` keeps its CLI but exposes a per-bet `grade_bet()` the hub reuses. Every page reads a JSON endpoint that wraps a pure function; writes are loopback-only.

**Tech Stack:** Python 3, Flask (existing app factory `web.create_app`), sqlite3 (stdlib), DuckDB (warehouse, read-only), pandas, numpy, pytest, waitress.

**Spec:** `docs/superpowers/specs/2026-10-17-master-dashboard-design.md` (sections "Build slices", "Architecture", "Tracker", "Errors", "Testing").

## Global Constraints

- Setup once: `python -m pip install -r requirements.txt` (the cloud container starts without Flask/DuckDB/pytest). `CFB_DATA_ROOT` must point at a directory containing a `.cfb-data-root` file before anything imports `cfb_paths`; tests create one under `tmp_path` and set the env var in `tests/hub/conftest.py`.
- Verification: `python -m pytest` (fast suite) green after every task. `tests/test_ingest_bets.py`, `tests/test_web_betlog.py`, `tests/test_matchup_page.py` stay passing unchanged except where a task names the edit.
- Bets file: `<DATA_DIR>/bets/bets.sqlite`, WAL mode, `busy_timeout = 5000`. Never committed (root `CLAUDE.md`: data is never committed).
- All hub paths derive from `app.config["DATA_DIR"]`, never from `cfb_paths` directly.
- Write endpoints (`POST`/`PATCH`/`DELETE`) return 403 unless `request.remote_addr` is `127.0.0.1` or `::1`.
- GET requests never write to the ledger.
- Backups: `sqlite3.Connection.backup` only, before every import and every `grade-bets` run, to `<DATA_DIR>/bets/bets-<UTC %Y%m%dT%H%M%SZ>.sqlite`, keep the newest 20.
- Close pass: retry `missing:*` after 6 hours; stop automatic retries 48 hours after kickoff.
- Stats: Wilson 95% with n = W + L; ROI and mean-CLV intervals by block bootstrap over (season, week), 2000 resamples, seed 7; no interval below 8 weeks ("too few weeks"); splits under 20 settled bets flagged "small sample"; drawdown in dollars only, ordered by `settled_at` then `bet_id`.
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
| `tests/hub/conftest.py` + test files named per task | fixtures: data root, empty ledger, tiny DuckDB warehouse |

**Spec deviation (record in the spec in Task 10):** the spec says to drop `ingest_bets.py`'s `sys.path` edit. It also imports `match_greenline_books` from `research/totals/scripts/`, which is not a package, so the edit stays; `ledgers/__init__.py` is still added. The hub imports `ledgers.ingest_bets` exactly as `tests/test_ingest_bets.py` does today.

---

### Task 1: Extract `grade_bet()` from `build()` (behaviour unchanged)

**Files:**
- Create: `ledgers/__init__.py`, `tests/hub/conftest.py`, `tests/test_ingest_bets_refactor.py`
- Modify: `ledgers/ingest_bets.py:279-379`

**Interfaces:**
- Produces:
  - `Grade` dataclass (frozen): `result: str | None`, `payout/net/roi: float | None`, `open_line/close_line: float | None`, `close_source: str`, `clv: float | None`, `clv_unit: str`.
  - `grade_bet(market: str, side_role: str, line: float | None, odds: float | None, stake: float | None, book: str | None, game_id: int, home_points: int | None, away_points: int | None, lines: pd.DataFrame) -> Grade` — result from the scores (the inline logic now at lines 357-366), close/CLV via `pick_close` + `compute_clv`, settlement via `settle`.
  - `build(sheet: Path, con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame` — opens `DB_PATH` read-only only when `con` is None.
- `tests/hub/conftest.py` fixtures: `data_root` (tmp dir with `.cfb-data-root`, sets `CFB_DATA_ROOT` via monkeypatch), `warehouse` (in-memory DuckDB with `core.fact_game` and `core.fact_game_line` holding the rows each test inserts; helper `add_game(con, game_id, start_utc, home, away, home_pts, away_pts)` and `add_line(con, game_id, provider, **cols)`).

- [ ] **Step 1: Write the characterization test against the current code**

`test_build_output_is_pinned(tmp_path, warehouse)`: three games (a home spread win, a total under push, a moneyline away win), a sheet with one bet each plus one unmatched row; call `build(sheet, con=warehouse)`; assert the exact `result`, `net`, `close_line`, `close_source`, `clv`, `clv_unit`, `match_status` for all four rows. Values: spread home -3.5, final 28-21, DK close -4.5 → win, net +100.0 at -110/110, clv 1.0 points; total under 54.0, final 30-24 → push, net 0.0; unmatched row → `match_status == "unmatched"`. The moneyline row asserts today's raw value (`compute_clv("moneyline","away",None,120,150)` shape) and is updated in Task 2.

- [ ] **Step 2: Run it; expect FAIL** — `build()` has no `con` parameter.

Run: `python -m pytest tests/test_ingest_bets_refactor.py -v`

- [ ] **Step 3: Add the `con` parameter only; run again; expect PASS.** Record `python ledgers/ingest_bets.py --self-check` output (`self-check ok`).

- [ ] **Step 4: Extract `Grade` and `grade_bet()`; make `build()` call it per matched row.** No change to `OUT_COLS`, `report()`, or CLI flags.

- [ ] **Step 5: Add `test_grade_bet_matches_build`** — for each fixture bet, `grade_bet(...)` equals the corresponding `build()` row fields.

- [ ] **Step 6: Run** `python -m pytest tests/test_ingest_bets.py tests/test_ingest_bets_refactor.py -v` and `python ledgers/ingest_bets.py --self-check`. Expected: all pass, `self-check ok`.

- [ ] **Step 7: Commit** `refactor(ledgers): extract grade_bet from build, accept a connection`

---

### Task 2: De-vigged moneyline CLV

**Files:**
- Modify: `ledgers/ingest_bets.py` (`pick_close`, `compute_clv`, `self_check`, `build`/`grade_bet` moneyline branch)
- Modify: `tests/test_ingest_bets.py:127-134` (`test_moneyline_clv_is_a_probability_not_points` → new semantics)
- Create: `tests/test_clv_moneyline.py`

**Interfaces:**
- Produces: `pick_moneyline_close(lines: pd.DataFrame, game_id: int, side_role: str, book: str | None) -> tuple[float | None, str]` returning (fair close probability of the bettor's side, source). Source is the book key, `median(<n> providers)`, `no line data`, or `missing:no paired close`.
- `compute_clv("moneyline", side_role, line, close, odds)` now takes `close` = fair probability and returns `(round(close - implied_prob(odds), 4), "probability")`.
- `grade_bet` uses `pick_moneyline_close` for moneyline; `Grade.close_line` holds the fair probability for moneyline.

- [ ] **Step 1: Write failing tests** in `tests/test_clv_moneyline.py`:
  - `test_devig_own_book`: DraftKings `moneyline_home=-150, moneyline_away=130`; bet away +140 at DraftKings → fair 0.420168 (abs 1e-6), source `draftkings`, CLV `0.0035`.
  - `test_devig_median_per_provider_first`: providers A (-150/+130) and B (-120/+100), bet book `SomeLocalBook` → fair away = mean of 0.420168 and 0.478261 (median of two), source `median(2 providers)`, CLV `0.0325`.
  - `test_one_sided_close_is_missing`: only `moneyline_home` present → `(None, "missing:no paired close")`; `grade_bet(...).clv is None`.
  - `test_post_kickoff_quotes_not_used`: `book_lines` reads only `*_close`/`moneyline_*` columns (the warehouse's pre-kickoff close); assert the query selects no live/in-game column (guard against a future edit).
- [ ] **Step 2: Run; expect FAIL** (`pick_moneyline_close` undefined).
- [ ] **Step 3: Implement** `pick_moneyline_close`; switch the moneyline branch; update `self_check` moneyline lines and the existing test to the paired form.
- [ ] **Step 4: Update Task 1's pinned moneyline row** to the de-vigged value.
- [ ] **Step 5: Run** the three test files + `--self-check`. Expected PASS.
- [ ] **Step 6: Commit** `fix(ledgers): de-vig paired close for moneyline CLV` with a body saying the `ingest_bets.py` moneyline column changes from raw implied-probability movement to de-vigged probability CLV.

---

### Task 3: Ledger store — schema, validation, edits, audit, source lock

**Files:**
- Create: `cfb_system_maker/hub/__init__.py` (empty `register_hub` stub for now), `cfb_system_maker/hub/paths.py`, `cfb_system_maker/hub/bets_store.py`, `tests/hub/test_bets_store.py`

**Interfaces:**
- `paths.bets_dir(data_dir: Path) -> Path` (`data_dir / "bets"`, created on demand); `paths.bets_db(data_dir) -> Path`.
- `connect(db_path: Path) -> sqlite3.Connection` — creates schema if absent (tables `bets` and `bet_audit` with the spec's columns, plus `placed_at_estimated INTEGER DEFAULT 0`), sets `journal_mode=WAL`, `busy_timeout=5000`, `row_factory=sqlite3.Row`, `foreign_keys=ON`.
- `class BetError(ValueError)` with `.status: int` (422 validation, 404 missing, 409 lock).
- `validate(fields: dict) -> dict` — normalizes market (`spread|total|moneyline`), side (OVER/UNDER upper for totals), requires `placed_at` with offset (naive → error here; importer handles naive input), odds integer with `odds <= -100 or odds >= 100`, stake > 0, `line` required unless moneyline, `source` non-empty.
- `insert_bet(con, fields: dict, origin: str) -> int`
- `get_bet(con, bet_id) -> sqlite3.Row`; `list_bets(con, season: int | None = None, source: str | None = None, status: str | None = None, include_deleted=False) -> list[sqlite3.Row]` (status: `pending|settled|all`).
- `update_bet(con, bet_id, changes: dict) -> None` — audit every changed field; settlement-affecting fields (`game_id, market, side, line, odds, stake`) clear `result, pnl, settled_at` and all close fields (`close_line, close_price, close_source, clv, clv_unit, close_checked_at`, `close_status='pending'`); `book` clears close fields only; `source` raises `BetError(409)` when `first_settled_at` is set.
- `soft_delete(con, bet_id) -> None` — sets `deleted_at`, audit row `action='delete'`.
- All writes in one transaction each (`with con:`).

- [ ] **Step 1: Write failing tests:** `test_schema_and_pragmas` (WAL, busy_timeout 5000), `test_insert_and_audit`, `test_two_identical_logged_bets_are_two_rows`, `test_validate_rejects_bad_odds_and_stake` (odds 50, -99, 1.91; stake 0, -5 → 422), `test_line_edit_clears_settlement_and_close`, `test_book_edit_clears_close_only`, `test_source_lock_survives_cleared_grade` (set `first_settled_at`, edit line, then edit source → 409), `test_soft_delete_keeps_row_and_audit` (row present with `include_deleted=True`, absent by default).
- [ ] **Step 2: Run; expect FAIL** (module missing).
- [ ] **Step 3: Implement** per the interface.
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_store.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): add SQLite bet ledger with audit and source lock`

---

### Task 4: WAL-safe backups

**Files:**
- Create: `cfb_system_maker/hub/backup.py`, `tests/hub/test_bets_backup.py`

**Interfaces:**
- `backup(con: sqlite3.Connection, bets_dir: Path, now: datetime | None = None, keep: int = 20) -> Path` — `sqlite3.connect(target)` then `con.backup(dest)`; filename `bets-<UTC %Y%m%dT%H%M%SZ>.sqlite`; deletes the oldest beyond `keep`.

- [ ] **Step 1: Write failing tests:**
  - `test_backup_includes_uncheckpointed_wal`: `PRAGMA wal_autocheckpoint=0`, insert 3 bets, keep the connection open; assert `bets.sqlite-wal` size > 0; `backup()`; open the backup file read-only and assert 3 bets.
  - `test_plain_copy_loses_wal_rows` (documents why): `shutil.copy` of the main file alone has fewer than 3 bets.
  - `test_retention_keeps_newest_20`: 22 backups with increasing `now` → 20 files, the two oldest gone.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_backup.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): back up the ledger with the SQLite backup API`

---

### Task 5: Grading passes

**Files:**
- Create: `cfb_system_maker/hub/grading.py`, `tests/hub/test_bets_lifecycle.py`

**Interfaces:**
- Consumes: `ledgers.ingest_bets.grade_bet`, `book_lines`, `load_games`, `find_game`, `resolve_side` (Task 1–2); `bets_store` (Task 3); `backup.backup` (Task 4).
- `@dataclass GradeReport`: `settled: int`, `closes_found: int`, `closes_missing: int`, `unmatched: list[tuple[int, str]]` (bet_id, note), `mismatches: list[tuple[int, str]]` (imported bets whose Action Network `result` in `import_ref` differs from ours), `still_pending: int`.
- `grade_all(bets_con: sqlite3.Connection, wh_con: duckdb.DuckDBPyConnection, now: datetime, bets_dir: Path) -> GradeReport` — backup first, then:
  - match pass: bets with `game_id IS NULL` → `find_game` + `resolve_side`; unmatched/reversed recorded, never guessed.
  - settle pass: `settled_at IS NULL AND deleted_at IS NULL` with both scores non-null → `result, pnl (= net), settled_at=now`, `first_settled_at` if null.
  - close pass: `close_status='pending'`, or `close_status LIKE 'missing:%'` with `close_checked_at` < now − 6 h and kickoff > now − 48 h → fill close fields from `grade_bet`; none found → `missing:<close_source>`; always set `close_checked_at=now`.
  - `force_close_retry: bool = False` keyword retries every `missing:*` regardless of age ("Grade now").

- [ ] **Step 1: Write failing tests** (use the `warehouse` fixture and fixed `now`):
  - `test_score_before_close`: score present, no line rows → settled, `close_status='pending'`; add line rows, run again 1 h later → close found, CLV set.
  - `test_missing_close_retry_window`: no lines → `missing:no line data`; rerun after 2 h → not checked again (`close_checked_at` unchanged); rerun after 7 h → checked; rerun at kickoff + 49 h → not checked; `force_close_retry=True` → checked.
  - `test_null_score_stays_pending` (Review Focus 2).
  - `test_reversed_teams_flagged`: imported bet with home/away swapped → `unmatched` note contains "looks reversed", `game_id` stays null.
  - `test_first_settled_at_is_never_cleared`: settle, edit line (clears settlement), regrade → `first_settled_at` equals the first value.
  - `test_grade_all_backs_up_first`: a backup file exists after the call.
  - `test_an_result_mismatch_listed`: imported bet whose `import_ref` says `win` but the score says loss → our `loss` stored, bet_id in `mismatches`.
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest tests/hub/test_bets_lifecycle.py -v`. Expected PASS.
- [ ] **Step 5: Commit** `feat(hub): grade bets in separate settle and close passes`

---

### Task 6: Import with duplicate review

**Files:**
- Create: `cfb_system_maker/hub/importer.py`, `tests/hub/test_hub_import.py`, `tests/hub/fixtures/an_export.csv`, `tests/hub/fixtures/manual_sheet.csv`
- Modify: `cfb_system_maker/betlog.py` — rename `_build_games_by_date` to `build_games_by_date` (keep a private alias for existing callers)

**Interfaces:**
- `@dataclass Candidate`: `fields: dict` (ledger fields), `status: str` (`new | possible_duplicate | unmatched | malformed`), `note: str`, `duplicate_of: int | None`, `import_ref: str` (original row as JSON).
- `preview_import(path: Path, kind: str, data_dir: Path, bets_con, unit_dollars: float | None) -> list[Candidate]` — `kind` is `action_network` or `sheet`.
  - Action Network: `betlog.parse_betlog_csv` → `betlog.match_to_game` with `build_games_by_date`; `placed_at = start_time` with `placed_at_estimated=1`; `stake = units_wagered * unit_dollars` (`unit_dollars` required, else `BetError(422)`; stored in `import_ref` so `last_unit_dollars(bets_con) -> float | None` can pre-fill the next import form); `book=None`; `source='import'`; AN `result`/`units_net` kept only in `import_ref`.
  - Sheet: columns of `ledgers/manual_bets_template.csv`; a naive `placed_at` is localized to UTC and the note says "time assumed UTC".
  - Duplicate check after matching: an existing non-deleted bet with equal `(game_id, market, side, line, odds, book)` → `possible_duplicate`, `duplicate_of` set.
- `commit_import(bets_con, candidates: list[Candidate], keep: set[int], bets_dir: Path) -> int` — backup, then insert the candidates whose index is in `keep` (default UI ticks every `new` row and no `possible_duplicate` row); returns inserted count.

- [ ] **Step 1: Write failing tests:** `test_an_mapping_units_to_dollars` (2 units at $50 → stake 100.0, `placed_at_estimated == 1`, abbreviation `ND` resolves to Notre Dame), `test_an_requires_unit_dollars`, `test_last_unit_dollars_remembered`, `test_logged_then_imported_is_possible_duplicate`, `test_naive_time_assumed_utc` (Review Focus 3), `test_malformed_rows_listed_with_reason`, `test_commit_inserts_only_kept_and_backs_up`.
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
- `tracker_summary(bets: list[Mapping], *, reps: int = 2000, seed: int = 7) -> dict` where each bet mapping has `bet_id, season, week, source, market, stake, pnl, result, settled_at, clv, clv_unit, close_source`. Returns:
  - `totals`: `{n, wins, losses, pushes, win_rate, win_rate_ci, staked, pnl, roi, roi_ci, weeks, small_sample, too_few_weeks}`
  - `clv`: list of `{unit, close_source, n, mean, mean_ci, median, positive_rate}` (one entry per unit × close_source, plus one per unit with `close_source="all"`)
  - `by_source`, `by_market`, `by_week`: dicts of the `totals` shape
  - `drawdown`: `{max_dollars, peak_at_bet_id, trough_at_bet_id}`; `curve`: list of `{bet_id, settled_at, cum_pnl}`
- Season/week of a bet comes from its game (joined by the caller), not `placed_at`.
- Bootstrap: resample whole (season, week) blocks with replacement, recompute ROI = Σpnl/Σstake and mean CLV; 2.5/97.5 percentiles; `None` and `too_few_weeks=True` when weeks < 8.

- [ ] **Step 1: Write failing tests:** `test_wilson_excludes_pushes` (6-4-2 → n=10, CI equals `_wilson_interval(0.6, 10)`), `test_block_bootstrap_fixed_seed` (10 weeks fixture → `roi_ci` equals values recorded on first green run, asserted to 4 dp, and the interval contains the point ROI), `test_too_few_weeks` (7 weeks → `roi_ci is None`), `test_small_sample_flag` (19 settled → True, 20 → False), `test_clv_split_by_unit_and_source`, `test_dollar_drawdown_ties_by_bet_id` (no `pct` key anywhere), `test_summary_empty` (Review Focus 4), `test_pending_and_deleted_excluded` (caller passes only non-deleted; pending rows have `result is None` and are not counted).
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
- The bets connection is opened per request and closed in `teardown_request`.

- [ ] **Step 1: Write failing tests:** API round trip (create, list, patch, delete, summary) with `create_app(data_dir=data_root)`; `test_get_never_writes` (file mtime and `bet_audit` count unchanged after every GET endpoint); `test_non_loopback_write_403` (`environ_base={"REMOTE_ADDR": "10.0.0.5"}` on POST/PATCH/DELETE → 403; same request from 127.0.0.1 → allowed); `test_bet_error_status_mapping` (422/404/409).
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
- Log bet modal: `_log_bet.html` + `log_bet.js` export `openLogBet(prefill: {game_id?, away?, home?, market?, side?, line?, source?})`; fields odds, stake, book, notes; `placed_at` = browser local time with offset; POSTs `/api/tracker/bets` and shows a 422 message inline. The Tracker opens it empty from an "Add bet" button; slice 1b's Board and preview call the same function with a prefill.
- The Log/Save buttons disable while a request is in flight (Review Focus 5).

- [ ] **Step 1: Write failing tests:** `/tracker` returns 200 and contains the nav entries; each existing page (`/`, `/compare`, `/betlog`) contains the nav include; CSP header unchanged for `/tracker` (inline `style=` is not used; the curve is SVG attributes only).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** the template, JS and nav include.
- [ ] **Step 4: Run** `python -m pytest`. Expected PASS.
- [ ] **Step 5: Manual check** (`python -m cfb_system_maker web` with a scratch `CFB_DATA_ROOT`): log two bets with Add bet (one with odds 1.91 to see the inline error), import `tests/hub/fixtures/an_export.csv` at $50/unit, see one possible duplicate unticked, click Grade now, confirm totals, CLV and curve render and no browser console CSP errors. Note results in the PR description.
- [ ] **Step 6: Commit** `feat(hub): tracker page and shared menu`

---

### Task 10: CLI commands, docs, spec note

**Files:**
- Modify: `cfb_system_maker/cli.py` (parser near line 1000, dispatch near line 98)
- Create: `cfb_system_maker/docs/bet-tracker.md`; Modify: `cfb_system_maker/docs/README.md` (one row)
- Modify: `docs/superpowers/specs/2026-10-17-master-dashboard-design.md` (Grading: the `sys.path` deviation; Storage: `placed_at_estimated` is a column rather than a note; Import: preview and commit are two endpoints)
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
