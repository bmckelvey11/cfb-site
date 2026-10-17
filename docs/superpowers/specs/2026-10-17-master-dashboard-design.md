# Master dashboard — design

**Status:** approved in brainstorming 2026-10-17 (project thread "master dashboard");
revised the same day after an independent review against the code. This spec covers
**phase 1**, built in three slices (1a, 1b, 1c), each with its own plan. Phases 2–3 are
queued in `TODO.md` (`#dashboard-docs-viewer`, `#dashboard-research-index`,
`#dashboard-todo-page`, `#dashboard-fold-existing-pages`) and get their own specs.

## Goal

One place to open on a Saturday for info and betting. Today the pieces are spread over two
Flask apps, a Streamlit app, several static HTML pages, three Claude-hosted pages, and the
Red Panda overs site on ChatGPT hosting. Phase 1 puts the betting workflow in one app: see
every signal for every game, open a game's preview, log the bet, and track how each source
is actually doing. A read-only copy goes to a private phone page.

Success for phase 1: on a Saturday morning, `python -m cfb_system_maker web` shows the
slate with spread, Red Panda and Greenline signals side by side; a bet can be logged from a
row in under ten seconds; the Tracker shows record, ROI and CLV by source with intervals;
the phone page shows the same board from that morning's snapshot.

## Decisions already made

| Decision | Choice |
| --- | --- |
| Where it runs | Local Flask hub on the Mac (full, live, backtests) **plus** a read-only hosted phone page |
| Build approach | Grow System Maker (`cfb_system_maker/web.py`, port 5000) into the hub. Every new module serves JSON first; its HTML page is one reader of that JSON |
| Home screen | The Board |
| Bet entry | "Log bet" from the Board / game preview **and** import (Action Network export, hand-filled CSV), into one ledger tagged by source |
| Bet storage | Own SQLite file outside `cfb.duckdb` |
| Phone page | Private Claude artifact, republished from a Mac snapshot by a scheduled task; no PFF numbers on it |
| Phase 1 pages | Board, Game preview (the existing Matchup page), Tracker, Greenline |
| Tuning lab | Stays Streamlit in `.venv-lab-ui`; the menu links out to it |
| Red Panda overs | Read `models/over_zero/site/lib/board.json`; do not embed or link the ChatGPT-hosted site |

## Build slices

| Slice | Contents | Why this order |
| --- | --- | --- |
| **1a** | Bet ledger, grading, Tracker page, import, the `hub/` skeleton and menu | Everything else writes to or reads from the ledger |
| **1b** | Source readers, Board, `/preview` mount with the signals panel, Greenline page | Needs the ledger for "my bets" and Log bet |
| **1c** | Snapshot export and the phone page | Reads the 1a and 1b APIs |

Each slice ships on its own, with the suite green, before the next starts.

## Architecture

```
cfb_system_maker/
  web.py                 create_app(): calls register_hub(app); existing routes untouched
  hub/
    __init__.py          register_hub(app): blueprints, menu context, localhost guard
    paths.py             every hub path derived from app.config["DATA_DIR"]
    sources.py           readers for each signal source → (rows, as_of) or a Stale marker
    board.py             /board  +  /api/board
    tracker.py           /tracker  +  /api/tracker/*
    bets_store.py        SQLite ledger: schema, writes, audit, duplicate check
    grading.py           grade_bet(): result, close, CLV, P&L for one bet
    greenline.py         /greenline  +  /api/greenline
    snapshot.py          builds the phone snapshot from pure payload functions
  matchup/
    app.py               make_blueprint(db_path, odds_dir, clock, url_prefix) + the existing
                         create_app(...) wrapper, kept so tests/test_matchup_page.py is unchanged
ledgers/ingest_bets.py   grading logic extracted into importable functions (see Grading)
```

- **One process.** `python -m cfb_system_maker web` serves everything. The `matchup` CLI
  command keeps working by starting the hub and opening `/preview`.
- **`web.py` does not grow.** It is 89 KB; new routes live in `hub/` blueprints. The only
  `web.py` changes are calling `register_hub(app)`, adding the menu to its base template,
  and the CSP change below.
- **Paths come from `app.config["DATA_DIR"]`**, the same root the existing app and its tests
  use, never directly from `cfb_paths`, so tests can point the hub at a temp folder.
- **JSON first.** Each `/api/...` endpoint is a thin wrapper around a pure function
  (`board_payload(date)`, `tracker_summary(season)`, ...). Pages fetch the endpoint; the
  snapshot export calls the same functions directly. Pages are JS-rendered like the
  existing matchup page; there is no separate server-rendered fallback (YAGNI for a
  single-user local tool).
- **Writes are local only.** `web` binds `0.0.0.0` when `PORT`/`FLY_APP_NAME` is set
  (`cli.py:985-991`), so every hub endpoint that writes (`POST`/`PATCH`/`DELETE`) rejects
  requests whose `remote_addr` is not loopback with 403.
- **Menu (phase 1):** Board · Tracker · Greenline · Systems (existing `/`, `/system`,
  `/compare`, `/search-runs`, `/betlog`) · Lab (link to the Streamlit lab). Phase 2–3
  entries appear only when built.
- **Look.** Existing Saturday Signal tokens and PRODUCT.md rules: dense tables,
  tabular-nums, color only for meaning (win/loss/push, positive/negative, active,
  lookahead amber).

## Game preview (`/preview`, slice 1b)

The existing Matchup page as a blueprint at `/preview`. "Unchanged behavior" means the
same features (slate picker, any two teams / season / week, 11 sections, pre-game vs
postgame separation, DK/FD lines); the mount itself needs these changes:

- `matchup.js` calls `/api/slate`, `/api/teams`, `/api/matchup` by absolute path
  (`matchup.js:241,305,703`). The template injects the mount prefix
  (`data-api-base="{{ url_for('preview.page') }}"`) and the JS prefixes every call with it.
- The `/tokens/<name>.css` route and the blueprint's own `static_folder` move into the
  blueprint; `matchup.html:8-11` uses `url_for('preview.static', ...)` and
  `url_for('preview.tokens', ...)`.
- The JSON error handler tests `request.path.startswith(prefix + "/api/")` instead of
  `"/api/"` (`app.py:66`).
- **CSP.** `web.py`'s policy (`web.py:500-506`) blocks the CFBD logo CDN (`matchup.js:94`)
  and the inline `style=` attributes `matchup.js` writes for team colours and bars. The
  `/preview` responses get their own policy adding `img-src 'self' <CFBD logo host>` and
  `style-src 'unsafe-inline'`; the rest of the app keeps the strict one. The test client
  does not enforce CSP, so this is checked by a header test plus one manual browser load.
- `tests/test_matchup_page.py` keeps building `matchup.app.create_app(...)` and passes
  unchanged. A new `tests/test_hub_preview.py` checks the `/preview` mount: page loads, the
  three API calls answer under the prefix, the CSP header is the preview one.
- **Signals panel** (new): that game's spread lean, Red Panda over, Greenline flag, my
  bets, and a **Log bet** button, read from the same `sources.py` readers. Shown only for
  games on a real slate, not custom team pairings.

## Sources and staleness (slice 1b)

| Signal | File read | Key fields | Fresh when |
| --- | --- | --- | --- |
| Slate, lines | `cfb.duckdb` via `matchup/queries.py`: `q.current_week` / `q.weeks` to map the board date to (season, week, season_type), then `q.slate(con, season, week, season_type, snap)` filtered to games kicking off on that local date | game_id, kickoff, teams, DK/FD lines | odds snapshot `pulled_at` within 24 h of the board date |
| TV, weather | `q.slate` returns neither. The plan adds one query for both, reusing the sources `scripts/tv_grid.py` and the weather.football load already read | network, forecast | same as their loaders |
| Spread board | `<DATA_DIR>/boards/spread/picks_<date>.json` | away, home, side, tier, top6, glicko, gap, note | file exists for the board date |
| Red Panda overs | `models/over_zero/site/lib/board.json` (path configurable; that folder is a separate repo and may be absent) | per-game signal and edge | its generated timestamp is in the board's week |
| Greenline | `<DATA_DIR>/ingest/pff_scoreboard/pff_greenline_<season>_w<wk>.csv` | flag side, line, edge | capture for the board's week exists |
| My bets | `<DATA_DIR>/bets/bets.sqlite` | see Tracker | always |

**Schemas are pinned from real files before any fixture is written.** Nothing in this repo
writes `picks_<date>.json` (the Saturday cloud task does) and `models/over_zero/site/` is not
in every checkout, so slice 1b starts by copying one real `picks_2026-10-17.json` and one
real `board.json` into `tests/fixtures/hub/` (checked first for anything that must not be
committed) and writing the readers against them.

Every reader returns rows plus an `as_of`, or a **Stale** marker naming the file and its
date. A stale, missing or malformed source never fails the page: its column shows
"stale · <date>" or "no data", a banner lists stale sources, and the parse error goes to the
server log. A reader also validates the fields it needs and goes Stale on a schema change.

Games are joined to signals on CFBD `game_id` where the source has one; otherwise on team
names through `team_abbreviations.resolve_team` and `core.dim_team`. Unmatched signal rows
are listed under the table ("3 Red Panda rows matched no game"), never dropped silently.

**Spread board transfer.** The Saturday cloud task builds the spread board in the project
folder, not on the Mac. That task gains one step: copy `picks_<date>.json` and
`spread_board_<date>.csv` into `<DATA_DIR>/boards/spread/` on the Mac. Until then the Spread
column shows "no data".

## Board (`/board`, home, slice 1b)

One row per FBS game on the selected date, sorted by kickoff.

| Column | Content |
| --- | --- |
| Game | away @ home, kickoff (local), TV, weather |
| Spread | market median line, model line, gap, tier (strong/lean/small/pass), news note on hover |
| Overs | Red Panda signal and edge |
| Greenline | flag side, PFF line, edge |
| My bets | bets in the ledger for this game_id; **Log bet** button |

- **Agreement marker:** a row is marked when two or more sources point the same way on the
  same market (e.g. Red Panda over and Greenline over), naming which ones.
- **Filters:** date (defaults to the next date with FBS games), "only games with a signal",
  "only my bets".
- **Row click** opens `/preview` on that game.
- `GET /api/board?date=YYYY-MM-DD` → `{date, season, week, sources: {name: {as_of, stale}},
  games: [{game_id, kickoff, away, home, tv, weather, spread, overs, greenline, bets,
  agreement}], unmatched: {source: [rows]}}`.

## Tracker (`/tracker`, slice 1a)

### Storage

`<DATA_DIR>/bets/bets.sqlite`, opened in WAL mode with `busy_timeout = 5000` (waitress runs
8 threads, `cli.py:719`). Table `bets`:

| Column | Type | Notes |
| --- | --- | --- |
| bet_id | integer pk | surrogate key; two identical real bets are two rows |
| placed_at | text | ISO 8601 **with UTC offset**; the Log modal sends the browser's local time with offset |
| game_id | integer null | set at log time when logged from a Board/preview row; set by matching for imports |
| away, home | text | |
| market | text | spread / total / moneyline |
| side | text | team name, OVER, UNDER |
| line | real null | as taken, from the bettor's side (ingest_bets.py convention) |
| odds | integer | American |
| stake | real | dollars |
| book | text null | |
| source | text | spread_board / red_panda / greenline / system:<name> / gut / import |
| notes | text null | |
| origin | text | logged / action_network / csv |
| import_ref | text null | the original row, verbatim, for imported bets |
| close_line, close_source, clv, clv_unit, result, pnl | null until graded | `clv_unit` is `points` (spread, total) or `prob` (moneyline) |
| graded_at, created_at, updated_at | text | |

Table `bet_audit (bet_id, changed_at, field, old, new)` records every edit. Once a bet is
graded its `source` cannot be changed, so per-source records cannot be relabelled after the
result is known. The file is data and is never committed. Before any import it is copied to
`bets.sqlite.bak`.

### Getting bets in

- **Log bet** (Board row, preview panel): a modal pre-filled with game_id, teams, market,
  side, line and source from the clicked signal; Blake types odds, stake, book.
  `POST /api/tracker/bets`.
- **Import** (`POST /api/tracker/import`): an Action Network export (parsed by
  `betlog.parse_betlog_csv`) or the 11-column hand sheet
  (`ledgers/manual_bets_template.csv`). Mapping for Action Network rows:
  - `placed_at` is unknown; AN gives kickoff (`start_time`), stored as `placed_at` and
    flagged `placed_at_estimated` in `notes`.
  - stakes are in units; the import form asks for the dollar value of one unit (default
    from the last import) and stores dollars.
  - abbreviated team names resolve through `team_abbreviations.resolve_team`.
  - our own grading decides `result` and `pnl`; AN's `result` and `units_net` are kept in
    `import_ref` and a mismatch is listed for review.
- **Duplicates.** After an imported row is matched to a game, it is compared with existing
  bets on (game_id, market, side, line, odds, book). Matches are **not** skipped silently:
  the import preview lists them as "possible duplicate" with the existing bet beside it,
  and Blake ticks which to keep. This is what stops a bet logged in the app and later
  imported from Action Network from counting twice.
- **Edit / delete** any bet (`PATCH` / `DELETE /api/tracker/bets/<id>`). Editing a graded
  bet's game, market, side, line, odds or stake clears its grade so it is graded again.

### Grading

The win/loss/push logic in `ledgers/ingest_bets.py` currently lives inline in `build()`
(`ingest_bets.py:357-372`), `build()` hardwires `DB_PATH` and a CSV, and `ledgers/` is not a
package. Slice 1a therefore starts with a **refactor commit, behaviour unchanged**:

- extract `grade_bet(bet, game, lines) -> Grade` (result, close_line, close_source, clv,
  clv_unit, pnl) from `build()`, reusing `resolve_side`, `pick_close`, `compute_clv`,
  `settle`;
- make `build()` call it and take a DuckDB connection argument;
- add `ledgers/__init__.py` and drop the module's `sys.path` edit;
- `ingest_bets.py --self-check` and its CLI output stay identical (checked before and after).

`hub/grading.py` then grades a bet with a known `game_id` directly, and only uses
`find_game` for imports. Grading is **explicit**: a "Grade now" button and the
`python -m cfb_system_maker grade-bets` command run
`UPDATE ... WHERE graded_at IS NULL` in one transaction. GET requests never write. A bet
without a final score stays **pending**, never a loss. Unmatched or reversed-team bets are
flagged for review, as `ingest_bets.py` already reports.

**Greenline marks are not written back in phase 1.** `greenline_bet_log.py --mark`
overwrites existing marks, filters on week but not season, and with no ids marks the whole
week (`greenline_bet_log.py:266-282`), keyed by PFF game id. The Greenline page instead
reads both the ledger and `greenline_bet_log.csv` and shows which flags were bet from
either. A safe write-back (`mark_if_blank(season, week, pff_game_id)` with a self-check)
can come later.

**Old `/betlog` page** stays as it is (its four tests in `tests/test_web_betlog.py` keep
passing) and is reachable under Systems. Its data moves into the ledger with
`python -m cfb_system_maker import-betlog`, run once by hand, never at startup.

### What it shows

`docs/model-evaluation-standard.md` binds any ROI, CLV or hit-rate report. These are real
bets, not a model evaluation, so trial count and walk-forward folds do not apply; the rest
does:

- **Record and win rate:** W-L-P; win rate and its **Wilson 95%** interval use n = W + L
  (pushes excluded, and counted separately).
- **ROI and P&L** with a 95% interval by **block bootstrap over weeks**, where a bet's week
  is its game's (season, week), not `placed_at`. With fewer than 8 weeks of graded bets the
  interval is not shown and the cell says "too few weeks".
- **CLV** reported separately per unit: points (spread, total) and probability
  (moneyline), and by `close_source`. For each: mean, median and share of bets with
  positive CLV, with the same week-block interval on the mean.
- **Max drawdown** of the bankroll line, in dollars and as a share of the peak.
- Splits by source, market and week. Splits with fewer than 20 graded bets are greyed with
  "small sample".
- Model picks (spread board paper picks, Greenline's full graded board) are not mixed into
  the Tracker; they appear on the Board and Greenline pages.

`GET /api/tracker/summary?season=` and `GET /api/tracker/bets?season=&source=&status=`.

## Greenline (`/greenline`, slice 1b)

- **This week:** every flag from the latest `pff_greenline_<season>_w<wk>.csv` capture, with
  whether it was bet (from the ledger or `greenline_bet_log.csv`).
- **Record:** from `research/totals/scripts/pool_totals_record.py`, calling its `load()` and
  `tally()` rather than re-deriving: overall, by era (2020, 2022-23, 2026; the archive eras
  come from `load()`, since `greenline_graded.csv` holds 2026 only), and overs vs unders,
  each with a Wilson interval. If those functions don't return the splits as data, slice 1b
  adds a small function there that does, and the script's own output stays the same.
- **Verdict:** the "one-paragraph answer" section of
  `research/totals/docs/greenline-findings.md`, rendered as-is and labelled with that doc's
  last-commit date. If the live record's n is larger than the record the doc cites, a note
  says the summary is behind the data. The page never edits the doc.
- `GET /api/greenline?season=&week=`.

## Phone page (slice 1c)

- **Content:** the Board (spread lean, Red Panda over, Greenline side), open bets, and the
  Tracker summary with intervals. Tapping a game shows lines, ratings and signals.
  "Updated at" timestamp at the top.
- **Never on it:** PFF grades and projections, Greenline lines and edges, individual bet
  stakes. Whether the Greenline **side** may appear is Blake's call under the PFF
  subscription terms; the allowlist has one switch for it, **off by default**, so the
  phone Board shows no Greenline column until he turns it on.
- **Export:** `python -m cfb_system_maker export-snapshot [--date]` calls the same payload
  functions as the API (no HTTP, no writes) and writes
  `<DATA_DIR>/boards/phone/snapshot_<date>.json`, keeping only fields on an explicit
  **allowlist**, so a new PFF column cannot reach the phone by accident.
- **Publish:** a scheduled task (Thursday 10 PM ET and Saturday 8 AM ET) pulls the latest
  snapshot from the Mac with folder tools and republishes one private artifact at a fixed
  URL. If the Mac is unreachable it republishes nothing, and the page's "updated at" shows
  the age.
- **Not in phase 1:** logging bets from the phone (needs a write-back sync).

## Errors

- Missing `CFB_DATA_ROOT` fails at startup with the existing `cfb_paths.py` message.
- A locked or busy `cfb.duckdb` returns the matchup app's existing 503 JSON; pages show
  "warehouse busy, retry".
- Source files that are missing, unreadable or malformed become Stale markers, never page
  errors.
- SQLite busy beyond the timeout or a failed write returns 500 with the reason; the Log
  modal keeps what was typed.
- Non-loopback writes return 403.

## Testing

`python -m pytest` (fast suite):

- `tests/test_ingest_bets_refactor.py` (1a): `grade_bet` on the `--self-check` cases; CLI
  output identical before and after the refactor.
- `tests/test_bets_store.py` (1a): insert, two identical real bets are two rows, edit
  clears grade, `source` locked after grading, audit rows, backup on import, WAL set.
- `tests/test_hub_import.py` (1a): Action Network mapping (units → dollars, kickoff as
  estimated placed_at, abbreviations), possible-duplicate detection against a logged bet.
- `tests/test_hub_grading.py` (1a): pending vs graded, CLV unit per market, reversed-team
  flag, GET never writes.
- `tests/test_hub_tracker_stats.py` (1a): Wilson with pushes excluded, week-block bootstrap
  on a fixed seed, "too few weeks" below 8, small-sample flag, max drawdown.
- `tests/test_hub_guard.py` (1a): writes from a non-loopback `remote_addr` get 403.
- `tests/test_hub_sources.py` (1b): each reader on the pinned real-file fixtures plus
  stale, missing, malformed and schema-changed cases; team-name join; unmatched rows.
- `tests/test_hub_board.py` (1b): `/api/board` shape, date → week mapping, agreement
  marker, filters, stale banner.
- `tests/test_hub_preview.py` (1b): the `/preview` mount and its CSP header.
- `tests/test_matchup_page.py` and `tests/test_web_betlog.py`: unchanged and passing.
- `tests/test_snapshot.py` (1c): allowlist strips every PFF field, the Greenline switch,
  snapshot equals the payload functions' output.

Fixtures live in `tests/fixtures/hub/`; no bet data or licensed data is committed.

## Out of scope (phase 1)

Docs viewer, Research index, TODO page, Rankings and the Middles calculator in the menu
(phases 2–3, in `TODO.md`); logging bets from the phone; Greenline write-back; automatic
`/betlog` import; server-rendered no-JS pages; a JS frontend rewrite; moneyline-specific
Board columns; any change to how the signal sources are produced.

## Risks

- **Red Panda `board.json` lives in a separate, unpushed repo.** Its schema can change
  without this repo noticing; the reader validates and goes Stale, and the pinned fixture
  documents the expected shape.
- **Scheduled tasks need the Mac awake** (same limitation as the line-timing collector). The
  phone page's "updated at" makes a missed run visible.
- **`greenline-findings.md` is behind** (last synced at week 4). The page says so rather
  than hiding it; updating the doc stays a research task.
- **The `ingest_bets.py` refactor touches working grading code.** It goes first, alone, with
  identical self-check and CLI output as the gate.
