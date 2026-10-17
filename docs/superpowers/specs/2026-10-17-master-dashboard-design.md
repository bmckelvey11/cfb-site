# Master dashboard — design

**Status:** approved in brainstorming 2026-10-17 (project thread "master dashboard"); this
spec covers **phase 1**. Phases 2–3 are queued in `TODO.md`
(`#dashboard-docs-viewer`, `#dashboard-research-index`, `#dashboard-todo-page`,
`#dashboard-fold-existing-pages`) and get their own specs.

## Goal

One place to open on a Saturday for info and betting. Today the pieces are spread over two
Flask apps, a Streamlit app, several static HTML pages, three Claude-hosted pages, and the
Red Panda overs site on ChatGPT hosting. Phase 1 puts the betting workflow in one app:
see every signal for every game, open a game's preview, log the bet, and track how each
source is actually doing. A read-only copy goes to a private phone page.

Success for phase 1: on a Saturday morning, `python -m cfb_system_maker web` shows the
slate with spread, Red Panda and Greenline signals side by side; a bet can be logged from
a row in under ten seconds; the Tracker shows record, ROI and CLV by source with
intervals; the phone page shows the same board from that morning's snapshot.

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

## Architecture

```
cfb_system_maker/
  web.py                 create_app(): registers the hub blueprints, keeps existing routes
  hub/
    __init__.py          register_hub(app): blueprints + shared nav context
    sources.py           readers for each signal source, each returns (rows, as_of) or a Stale marker
    board.py             /board  +  /api/board
    tracker.py           /tracker  +  /api/tracker/*
    bets_store.py        SQLite ledger: schema, insert/update/delete, dedupe keys
    grading.py           wraps ledgers/ingest_bets.py matching, settle and CLV
    greenline.py         /greenline  +  /api/greenline
    snapshot.py          builds the phone snapshot from the /api payloads
  matchup/               becomes a blueprint mounted at /preview (its /api/* moves under /preview/api/*)
  templates/
    _hub_base.html       left menu, shared tokens (static/tokens/*.css), stale-source banner
    board.html  tracker.html  greenline.html
```

- **One process.** `python -m cfb_system_maker web` serves everything. The `matchup` CLI
  command keeps working by starting the hub and opening `/preview`, so nothing Blake
  runs today breaks.
- **`web.py` does not grow.** It is 89 KB; new routes live in `hub/` blueprints. The only
  `web.py` change is calling `register_hub(app)` and adding the menu to existing templates.
- **JSON first.** Each page fetches its own `/api/...` endpoint and renders from it, so the
  phone snapshot, a scheduled task, or a later JS frontend reads exactly what the Mac page
  shows. Pages degrade to a server-rendered table when JS is off (PRODUCT.md
  progressive-enhancement rule).
- **Menu (phase 1):** Board · Tracker · Greenline · Systems (existing `/`, `/system`,
  `/compare`, `/search-runs`) · Lab (link to the Streamlit lab). Phase 2–3 entries appear
  only when built.
- **Look.** Existing Saturday Signal tokens and PRODUCT.md rules: dense tables,
  tabular-nums, color only for meaning (win/loss/push, positive/negative, active,
  lookahead amber).

## Sources and staleness

| Signal | File read | Key fields | Fresh when |
| --- | --- | --- | --- |
| Slate, lines, TV, weather | `cfb.duckdb` via `matchup/queries.py` (`q.slate`) and the odds snapshot it already uses | game_id, kickoff, teams, DK/FD lines | odds snapshot `pulled_at` within 24 h of the board date |
| Spread board | `$CFB_DATA_ROOT/boards/spread/picks_<date>.json` (+ `spread_board_<date>.csv`) | away, home, side, tier, top6, glicko, gap, note | file exists for the board date |
| Red Panda overs | `models/over_zero/site/lib/board.json` | per-game signal and edge | its generated timestamp is in the board's week |
| Greenline | `$CFB_DATA_ROOT/ingest/pff_scoreboard/pff_greenline_<season>_w<wk>.csv` | flag side, line, edge | capture for the board's week exists |
| My bets | `$CFB_DATA_ROOT/bets/bets.sqlite` | see Tracker | always |

Every reader in `sources.py` resolves paths through `cfb_paths.py` (`CFB_DATA_ROOT`) and
returns either rows plus an `as_of` timestamp, or a **Stale** marker naming the file and
its date. A stale or missing source never fails the page: its column shows "stale ·
<date>" (or "no data"), and a banner above the table lists which sources are stale.

Games are joined to signals on CFBD `game_id` where the source has one; otherwise on
team names resolved through `team_names.py` / `team_abbreviations.py`. Unmatched signal
rows are listed under the table ("3 Red Panda rows matched no game") rather than dropped.

**Spread board transfer.** The spread board is built by the Saturday cloud task into the
project folder, not on the Mac. That task gains one step: copy `picks_<date>.json` and
`spread_board_<date>.csv` into `$CFB_DATA_ROOT/boards/spread/` on the Mac (folder tools,
`device_commit_files`). Until that step exists the Spread column shows "no data", which is
the honest state.

## Board (`/board`, home)

One row per FBS game on the selected date, sorted by kickoff.

| Column | Content |
| --- | --- |
| Game | away @ home, kickoff (local), TV, weather |
| Spread | market median line, model line, gap, tier (strong/lean/small/pass), news note on hover |
| Overs | Red Panda signal and edge |
| Greenline | flag side, PFF line, edge |
| My bets | bets already in the ledger for this game_id; **Log bet** button |

- **Agreement marker:** a row is marked when two or more sources point the same way on
  the same market (e.g. Red Panda over and Greenline over). The marker states which ones.
- **Filters:** date (defaults to the next date with FBS games), "only games with a signal",
  "only my bets".
- **Row click** opens `/preview?game_id=...`.
- `GET /api/board?date=YYYY-MM-DD` returns `{date, sources: {name: {as_of, stale}}, games:
  [{game_id, kickoff, away, home, tv, weather, spread, overs, greenline, bets, agreement}]}`.

## Game preview (`/preview`)

The existing Matchup page, mounted as a blueprint, unchanged in behavior (slate picker,
any two teams / season / week, 11 sections, pre-game vs postgame separation, DK/FD lines).
Phase 1 adds the **signals panel** the original branch reserved but never built: that
game's spread lean, Red Panda over, Greenline flag, and my bets, read from the same
`sources.py` readers and a **Log bet** button. The panel is only shown for games on a
real slate, not custom team pairings.

## Tracker (`/tracker`)

### Storage

`$CFB_DATA_ROOT/bets/bets.sqlite`, table `bets`:

| Column | Type | Notes |
| --- | --- | --- |
| bet_id | integer pk | |
| placed_at | text (ISO) | |
| away, home | text | as typed or as imported |
| market | text | spread / total / moneyline |
| side | text | team name, OVER, UNDER |
| line | real null | as taken, from the bettor's side (ingest_bets.py convention) |
| odds | integer | American |
| stake | real | dollars |
| book | text null | |
| source | text | spread_board / red_panda / greenline / system:<name> / gut / import |
| notes | text null | |
| origin | text | logged / action_network / csv |
| dedupe_key | text unique | placed_at date + teams + market + side + line + odds + stake |
| game_id | integer null | filled by grading |
| close_line, clv, result, pnl | null until graded | |
| graded_at, created_at, updated_at | text | |

The file is created on first use. It is data, so it is never committed (root CLAUDE.md).
Every write is a single transaction; before any import the file is copied to
`bets.sqlite.bak` so a bad import is one file copy away from undone.

### Getting bets in

- **Log bet** (Board row, preview panel): modal pre-filled with teams, market, side, line
  and source from the clicked signal; Blake types odds, stake, book. `POST
  /api/tracker/bets`.
- **Import**: upload an Action Network export (parsed by `betlog.parse_betlog_csv`) or the
  11-column hand sheet (`ledgers/manual_bets_template.csv` format). Rows whose
  `dedupe_key` already exists are skipped and counted; malformed rows are listed with the
  reason. `POST /api/tracker/import`.
- **Edit / delete** any bet. `PATCH` / `DELETE /api/tracker/bets/<id>`.

### Grading

`grading.py` calls the existing functions in `ledgers/ingest_bets.py` (`find_game`,
`resolve_side`, `pick_close`, `compute_clv`, `settle`) rather than re-implementing them;
if they need to be importable as a module, that move is a separate commit. Grading runs on
Tracker page load for ungraded bets and from a "Grade now" button. A bet without a final
score is **pending**, never a loss. A bet that matches no game, or matches with home/away
reversed, is flagged for review, as `ingest_bets.py` already reports.

**Greenline marks.** When a bet with `source = greenline` grades to a game with a
Greenline flag that week, the matching row in `greenline_bet_log.csv` is marked `y` using
the same append-only rules as `greenline_bet_log.py --mark` (existing marks are never
overwritten).

The old `/betlog` page redirects to `/tracker`; its Action Network data is imported once
on first run.

### What it shows

- Season totals: record (W-L-P), win rate, P&L, ROI, mean CLV, number of bets.
- Splits by source, market, and week; a bankroll line over time.
- **Intervals on every rate** (`docs/model-evaluation-standard.md`): Wilson 95% for win rate;
  95% interval for ROI and mean CLV by bootstrap resampling **whole weeks** (bets in one
  week are not independent). Splits with fewer than 20 graded bets show the numbers greyed
  with "small sample".
- These are records of real bets, not a model evaluation, so the standard's
  trial-count and walk-forward items do not apply; the intervals do.
- Model picks (spread board paper picks, Greenline's full graded board) are **not** mixed
  into the Tracker; they appear on the Board and Greenline pages.

`GET /api/tracker/summary?season=` and `GET /api/tracker/bets?season=&source=&status=`.

## Greenline (`/greenline`)

- **This week:** every flag from the latest `pff_greenline_<season>_w<wk>.csv` capture,
  with whether Blake bet it (from the ledger, falling back to `greenline_bet_log.csv`).
- **Record:** computed live from `greenline_graded.csv` — overall, by era, overs vs unders —
  with Wilson intervals, using the same pooling rules as
  `research/totals/scripts/pool_totals_record.py` (call it, don't re-derive).
- **Verdict:** the "one-paragraph answer" section of
  `research/totals/docs/greenline-findings.md`, rendered as-is, labelled with that doc's
  last-commit date. If the live record's n is larger than the record the doc cites, a note
  says the summary is behind the data. The page never rewrites the doc.
- `GET /api/greenline?season=&week=`.

## Phone page

- **Content:** the Board (spread lean, Red Panda over, Greenline **side only**), open bets,
  and the Tracker summary with intervals. Tapping a game shows a short preview: lines,
  ratings, signals. "Updated at" timestamp at the top.
- **Never on it:** PFF grades, PFF projections, Greenline lines/edges (licensed data), and
  bet stakes beyond the summary. The artifact is private; the link is not shared.
- **Export:** `python -m cfb_system_maker export-snapshot [--date]` writes
  `$CFB_DATA_ROOT/boards/phone/snapshot_<date>.json` from the same `/api/board` and
  `/api/tracker/summary` payloads (via the Flask test client, so there is one code path),
  with PFF fields stripped by an explicit allowlist, not a denylist.
- **Publish:** a scheduled task (Thursday 10 PM ET and Saturday 8 AM ET) pulls the latest
  snapshot from the Mac with folder tools and republishes one private artifact at a fixed
  URL. If the Mac is unreachable, the task republishes nothing and the page keeps its last
  "updated at".
- **Not in phase 1:** logging bets from the phone (needs a write-back sync).

## Errors

- Missing `CFB_DATA_ROOT` fails at startup with the existing `cfb_paths.py` message.
- A locked or busy `cfb.duckdb` returns the matchup app's existing 503 JSON; pages show
  "warehouse busy, retry".
- Source files that are missing, unreadable or malformed become **Stale** markers, never
  exceptions on the page; the parse error goes to the server log.
- SQLite write failures return 500 with the reason; the modal keeps what was typed.

## Testing

`python -m pytest` (fast suite) gains:

- `tests/test_hub_sources.py` — each reader against small fixture files: fresh, stale,
  missing, malformed; team-name join and unmatched-row reporting.
- `tests/test_hub_board.py` — `/api/board` shape, agreement marker, filters, stale banner.
- `tests/test_bets_store.py` — insert, dedupe on re-import, edit, delete, backup on import.
- `tests/test_hub_grading.py` — pending vs graded, CLV sign per market (reuse
  `ingest_bets.py --self-check` cases), reversed-team flag, Greenline mark append-only.
- `tests/test_hub_tracker_stats.py` — Wilson bounds and week-block bootstrap on a fixed
  seed; small-sample flag.
- `tests/test_snapshot.py` — allowlist strips every PFF field; snapshot equals the API
  payloads.
- Existing `tests/test_matchup_page.py` passes unchanged against the `/preview` mount.

Fixtures are small hand-written CSV/JSON in `tests/fixtures/hub/`; no real data is
committed.

## Out of scope (phase 1)

Docs viewer, Research index, TODO page, Rankings, Middles calculator in the menu
(phases 2–3, in `TODO.md`); logging bets from the phone; a JS frontend rewrite;
moneyline-specific Board columns; any change to how the signal sources are produced.

## Risks

- **Red Panda `board.json` lives in a separate, unpushed repo** (`models/over_zero/site/`).
  Its schema can change without this repo noticing; the reader validates the fields it
  needs and goes Stale on mismatch, and a fixture pins the expected shape.
- **Scheduled tasks need the Mac awake** (same limitation as the line-timing collector).
  The phone page's "updated at" makes a missed run visible.
- **`greenline-findings.md` is behind** (last synced at week 4). The page shows that
  rather than hiding it; updating the doc stays a research task.
