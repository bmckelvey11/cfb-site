# the-odds-api.com ingest

Status: **live pull landed, not wired to the warehouse.** Snapshots go to
`data/ingest/oddsapi/`, which `cfb_paths` does not glob. Flatten and loader
wiring are deliberately deferred — see *Before this loads* below.

- Client: `cfb_system_maker/oddsapi_client.py`
- Pull: `scripts/pull_odds.py`
- Tests: `tests/test_oddsapi_client.py`
- Key: `ODDS_API` in `env.env` (gitignored)
- Guide: <https://the-odds-api.com/liveapi/guides/v4/>

```bash
python scripts/pull_odds.py
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
| Every 6h | 360 | yes, ~72% of cap |
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

## Before this loads: the join key

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
