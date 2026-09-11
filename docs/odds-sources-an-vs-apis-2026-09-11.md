# Do we still need the Action Network scrape?

**2026-09-11.** Reproduce the inventory with `python scripts/audit_odds_sources.py`
(read-only; prints every table below). Follows [`oddsapi-ingest.md`](oddsapi-ingest.md),
which wired the-odds-api and oddspapi in, and
[`line-timing-collector.md`](line-timing-collector.md), which owns the AN history task.

## The question

Three odds sources now run on a schedule: the Action Network (AN) scrape, the-odds-api
snapshots, and oddspapi's Pinnacle feed. CFBD's `lines` endpoint is a fourth, pulled with the
rest of the CFBD refresh. AN is the only one that is an unofficial, Cloudflare-fronted web API
with no terms of use, and it is the one that just broke the rebuild (`stg.an_scoreboard` OOM,
[`refresh-break-2026-09-11.md`](../cfb_system_maker/docs/refresh-break-2026-09-11.md)). Can
the paid or documented APIs do what it does, so it can be retired?

## Method

Inventory what each source holds — markets, periods, books, seasons, history depth — from the
files on disk and the warehouse, then walk every consumer in the repo that reads AN data and
ask whether one of the other sources could feed it. No modelling; this is a coverage audit.

**Data:** `data/raw/actionnetwork/`, `data/ingest/oddsapi/`, `data/ingest/oddspapi/`,
`data/raw/lines_*.json`, and local `cfb.duckdb` as of 2026-09-11 (the post-OOM rebuild, which
is missing the `stg.an_scoreboard` family — noted where it matters).

## What each source holds

| | Action Network | the-odds-api | oddspapi | CFBD `lines` |
|---|---|---|---|---|
| Status | unofficial web API, browser UA required | free plan, 500 credits/mo, 6-hourly | free plan, 250 req/mo, daily | official, in the CFBD refresh |
| Seasons on disk | scoreboards 2015–2026 (175 weeks, ~900 events/season) | 2026-09-09 onward, 9 snapshots | 2026-09-09 onward, 3 snapshots | 2013–2026 |
| Books (2026) | consensus 15, Open 30, Caesars 49, DraftKings 68, FanDuel 69, BetRivers 71, BetMGM 75 | betmgm, betrivers, draftkings, fanduel + offshore betonlineag, betus, bovada, lowvig, mybookieag | Pinnacle only | DraftKings, Bovada (2026); ESPN Bet through 2025 |
| Markets | spread, total, moneyline, team total | h2h, spreads, totals | spreads (parsed) | spread, total, moneyline |
| Periods | full game, **first half, first quarter** | full game only on the free tier | full game (periods present, parsed to 0 only) | full game only |
| Timestamps | **every tick**, replayed back to the opener (April) in one call | snapshot `pulled_at` only | snapshot `pulled_at` only | none — `spreadOpen` / `spread`, no times |
| Historical backfill | yes, any time before AN pulls the event | **401 on the free plan**; $30/mo, period markets only since 2023-05 | no | open and close only |
| Public betting splits | **money % and ticket % per offer** | no | no | no |
| Live at slate time | fetched live by both slates | up to 6 h old | up to 24 h old | daily |

Warehouse counts, 2026-09-11:

| AN table | rows | events | books | note |
|---|---|---|---|---|
| `stg.an_history` firsthalf/firstquarter spread | 16,557 / 16,393 | 1,736 / 1,717 | 6–7 | seasons **2024 and 2025 only** (858 + 869 1H events); 2015–2023 history files came back empty upstream |
| `stg.an_history` full-game spread | 2,308 | 199 | 7 | 2026 only, from `history_event_*.json` |
| `stg.an_history_tick` full-game | 273,314 ticks | 199 | 7 | first tick 2026-04-02, last 2026-09-11 |
| `stg.an_history_tick` 1H / 1Q | 5,670 / 3,892 | 9 | 5–6 | the nine 2026 files that carried `history[]` |
| `stg.an_history` rows with splits | 120,222 | 1,929 | — | loaded, **read by nothing** |
| `core.fact_game_odds` (the-odds-api) | 28,422 | 100 | 9 | 9 snapshots over two days |

## Who reads AN, and whether another source could feed them

| Consumer | What it takes from AN | Replaceable? |
|---|---|---|
| `research/spread/scripts/weekly_slate.py` — book fair, `side`, `edge`, forward log | live scoreboard: 5 real books + consensus, this minute | **Partly.** the-odds-api carries DraftKings, FanDuel, BetRivers, BetMGM; not Caesars, not consensus. Its snapshot is up to 6 h old and hourly pulls (2,160 credits/mo) do not fit the free plan. `book_fair` would lose one vote and go stale between pulls. |
| `research/spread/scripts/eval_version_b.py` — the version B verdict | **close = consensus book 15, last full-game tick before kickoff** from `history_event_*.json` | **No.** Nothing else serves a consensus book, and the "last tick before kickoff" needs a timestamped path. the-odds-api gives a 6-hourly snapshot, so the close would be 0–6 h stale; the prereg names AN book 15. |
| `research/spread/scripts/eval_timing_decay.py` — when the move happens | full tick path per book, opener to close | **No.** Only AN replays the path. the-odds-api historical is paywalled and snapshot-based; CFBD has no timestamps. |
| `research/spread/scripts/eval_line_shopping.py`, `check_pt_line_is_close.py` | per-book closes 2024–25 from `stg.an_market` + `stg.an_scoreboard` | **No, and currently broken** — those tables are absent after the OOM rebuild. CFBD carries one to three books per game (DraftKings, Bovada, ESPN Bet) with no dispersion tail worth measuring. |
| `models/over_zero/scripts/best_line_slate.py` — the served board | live scoreboard: fair spread and total = median of the 5 AN books; the-odds-api books for execution only | **Partly**, same shape as the spread slate. `FAIR_BOOKS` is pinned to the AN set because the 1.75 calibration was fit on it; switching the fair to the-odds-api books means recalibrating (`best_line_slate.py:65`). |
| `models/over_zero/scripts/build_1h_lines.py`, `build_1h_games.py`, b7 research | **first-half spreads and totals**, 2024–25 | **No.** CFBD has no period markets (`b1_first_half/SOURCES.md`). the-odds-api period markets need the paid plan and only exist from 2023-05. oddspapi has periods for Pinnacle only, live only. |
| `duckdb_load.backfill_gamelines_from_actionnetwork` → `core.fact_game_line` | 8,575 rows under circa, fanduel, betmgm, bet365, pinnacle that CFBD never carried | **No.** Those books are not in CFBD at all; the-odds-api has no history. |
| `scripts/audit_line_sign_convention.py`, `tests/test_core_merges.py` | the five AN books must be present in the graded set | follows from the row above |

## Result

**The scrape cannot be retired.** Four things only AN provides, and each has a live consumer:

1. **Timestamped tick history back to the opener.** Version B, the only open question in the
   spread tree, is graded on the AN consensus close. The timing-decay read exists only because
   of these ticks. the-odds-api historical is paywalled and is a snapshot series even when paid.
2. **A consensus book.** No vendor API serves one. Building one from the-odds-api books changes
   the definition the prereg fixed.
3. **First-half and first-quarter markets, 2024–2025.** The over-zero 1H work has no other
   source; CFBD has none, the-odds-api's begin 2023-05 behind a paywall.
4. **Per-book closes across seven books, 2024–2025, and five books CFBD never had.** The
   line-shopping backtest and the `core.fact_game_line` union both rest on this.

What the other APIs **do** add is real and already in use: five offshore books, Pinnacle, an
official quota, and a `pulled_at` on every snapshot. They widen `book_fair`; they do not
replace its AN core.

**What AN carries that nobody reads yet:** money % and ticket % on 1,929 events, loaded into
`stg.an_history` and referenced by no script. If a public-betting feature is ever tested, this
is the only source for it on hand — a further reason not to drop the scrape, though not a
reason it is needed today.

## What could be cut

- **The 2015–2023 first-half backfill files.** 10,868 `history_<id>.json` files exist but only
  the 2024–2025 ones carry offers; earlier seasons came back empty and are closed upstream.
  Re-scraping them is pointless; keeping them costs nothing but the OOM the scoreboard explode
  just hit is a volume problem, and trimming `raw.an_scoreboard` to seasons the consumers use
  (2024+) is the cheaper fix than dropping the source.
- **`DEFAULT_PERIODS` in the client** still asks only for 1H/1Q on the bulk scrape, while the
  full-game path is pulled by `collect_line_timing.py`. That is a split of one job across two
  scripts, not a reason either half is unnecessary.

## What this does not support

- **It does not price an upgrade.** the-odds-api's paid plan ($30/mo) would give period
  markets and historical snapshots from 2023-05. Whether that is worth it as a *second* source
  for 2026 forward is a separate decision; it still would not reach 2024 first-half history or
  any consensus book.
- **It does not test the-odds-api as a fair-value source.** Swapping the `book_fair` core to
  its four shared books was not measured here. `oddsapi-ingest.md` measured promotion of the
  extra books (median shift 0.00), not removal of AN's.
- **It does not assess AN's terms of use or durability.** The scrape depends on an undocumented
  endpoint and a browser User-Agent; the risk that it closes is real and unquantified. The
  correct hedge is to keep the-odds-api running so a 2026-forward record exists if AN goes
  dark, not to turn AN off first.
- **It does not repair `stg.an_scoreboard`.** The consumers marked *currently broken* stay so
  until the OOM in the explode is fixed; that is tracked in
  [`refresh-break-2026-09-11.md`](../cfb_system_maker/docs/refresh-break-2026-09-11.md).
