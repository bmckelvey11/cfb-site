# the-odds-api.com ingest

Status: **pulling on a schedule, not wired to the warehouse.** Snapshots go to
`data/ingest/oddsapi/`, which `cfb_paths` does not glob. Flatten and loader
wiring are deliberately deferred — see *Before this loads* below.

- Client: `cfb_system_maker/oddsapi_client.py`
- Pull: `scripts/pull_odds.py`
- Scheduler wrapper: `scripts/pull_odds.cmd`
- Tests: `tests/test_oddsapi_client.py`
- Key: `ODDS_API` in `env.env` (gitignored)
- Guide: <https://the-odds-api.com/liveapi/guides/v4/>

```bash
python scripts/pull_odds.py
```

## Schedule

Windows Task Scheduler task **`CFB-Odds-Snapshot`**, repeating every 6 hours from
02:00 (so 02:00 / 08:00 / 14:00 / 20:00), running `scripts/pull_odds.cmd` as
`mckel`. `StartWhenAvailable` is on, so a run missed to sleep fires late rather
than being skipped; `MultipleInstances` is `IgnoreNew`. Every run appends to
`data/logs/odds_pull.log`. Registered 2026-09-09 and verified by a manual
`Start-ScheduledTask` (exit 0, snapshot written).

Cadence is the budget: 3 credits × 4/day ≈ **360/month against the free plan's
500**, leaving room for ad-hoc pulls. Changing the interval means redoing that
math. To pause it:

```powershell
Disable-ScheduledTask -TaskName CFB-Odds-Snapshot
```

## Plan and quota — probed 2026-09-09

`x-requests-remaining: 500`, `x-requests-used: 0` on a fresh period: this is the
**free tier**. Two consequences, both confirmed by probe rather than by docs:

- **Historical is 401.** `/v4/historical/sports/americanfootball_ncaaf/odds`
  returns `HISTORICAL_UNAVAILABLE_ON_FREE_USAGE_PLAN`. No backfill is possible
  without upgrading; `models/over_zero/research/b1_first_half/SOURCES.md` priced
  that at $30/mo (20K plan) and recorded that period markets only reach back to
  2023-05-03.
- **A pull costs one credit per region per market.** The default
  (`us` × `h2h,spreads,totals`) is 3 credits, measured off `x-requests-last`.

| Cadence | Credits/month (3 per pull) | Fits in 500? |
| --- | --- | --- |
| Daily | 90 | yes |
| Every 6h | 360 | yes, ~72% of cap — **current schedule** |
| Hourly | 2,160 | no |

`/v4/sports` costs 0, so probing the sport list is free.

## What a snapshot holds

`/v4/sports/{sport}/odds` is a **live snapshot**, not history. 85 events and 9
books on the first pull; `fanduel`, `draftkings`, `betmgm`, `betrivers`,
`bovada` among them. Each run writes a new timestamped file and overwrites
nothing — the difference between two snapshots *is* the line movement, which
only works if each one says when it was taken. `pulled_at` therefore lives in
the envelope, not just the filename, alongside the quota headers the call
returned.

## Read by the spread slate — promoted into `book_fair`

`research/spread/scripts/weekly_slate.py` reads the latest snapshot and its books now **vote in
`book_fair`**, under **amendment S2** of `research/spread/docs/prereg-line-shopping.md`. The
slate went from 4 books per game to 10.

Promotion adds the five books Action Network does not carry — BetOnline.ag, Bovada, LowVig.ag,
BetUS, MyBookie.ag, all offshore. The four it shares (DraftKings, FanDuel, BetRivers, BetMGM) are
**deduped, with Action Network winning**: AN is fetched live at slate time where this snapshot is
up to six hours old, and `book_fair` claims to be the number right now. Without that dedup those
four books would vote twice.

Measured on promotion, 2026 week 3, 49 games: `book_fair` moved a median of 0.00 points, mean
−0.046, max 0.50, no game past 1.5. E4's side flipped on 5 games; the edge ≥ 1 bet set stayed at
20. `oa_fair_pt` stays beside it as the agreement check.

**What this does not touch:** version B. `eval_version_b.py` grades `close − line_Monday` on
`E4 − line_Monday`, where the anchor is Prediction Tracker's line and the close is Action
Network's consensus book 15 — neither is `book_fair`. What `book_fair` does drive is `side`,
`side_line`, `edge`, and the slate's printed bet set.

`BOOK_SET_VERSION` = 2 is stamped on every forward-log row from 2026-09-09 on. The 399 earlier
rows are stamped 1 by `research/spread/scripts/migrate_book_set_version.py` and **cannot be
recomputed** — no snapshot exists for those moments. Any read pooling the two eras must say so.

Names join by stripping the mascot (`oa_resolve`): Odds API says `"Miami Hurricanes"`, PT says
`"Miami"`. Residual spellings live in `OA_ALIASES` and grow the way `ALIASES` did — when a game
shows up in the unpriced list with books actually posted for it.

## Before this loads into the warehouse: the join key

Odds API events carry their own `id`, `commence_time` (UTC ISO8601), and team
names **including the mascot** — `"Miami Hurricanes"`, `"Florida A&M Rattlers"`.
The warehouse's `stg.games` carries school only — `"Youngstown State"`,
`"Ohio Dominican"`. Nothing joins to `game_id` until that gap is closed, and
`normalize.py` does not close it (it normalizes CFBD payloads, not vendor names).
Settle the mapping before designing a flatten, or the landed payloads become
unusable later.

The quota fields (`requests_last`, `requests_used`, `requests_remaining`) are
nullable: they mirror response headers, and a missing header lands as `null`.
A flatten that gates further pulls on `requests_remaining` has to handle that.

No-lookahead: these are pre-game snapshots and safe. Any future historical pull
must keep the snapshot timestamp on the row — a snapshot taken after kickoff is
result-contaminated.
