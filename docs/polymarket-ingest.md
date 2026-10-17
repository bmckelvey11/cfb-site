# Polymarket ingest

Status: **client, flatten and loader written; not scheduled.** Snapshots go to
`data/ingest/polymarket/`, the flatten writes `data/processed/polymarket/`, and a rebuild
loads `stg.pm_market_tick` and `stg.pm_snapshot`. No `core` join yet: rows carry
`home_school`/`away_school` in CFBD spelling but no `game_id`.

- Client: `cfb_system_maker/polymarket_client.py`
- Schema + name rule: `cfb_system_maker/polymarket_schema.py`
- Pull: `scripts/pull_polymarket.py`
- Flatten: `scripts/polymarket_flatten.py` (also run by `scripts/refresh_cfbd.py`)
- Tests: `tests/test_polymarket.py`
- Key: none. Gamma is Polymarket's public read-only API. Nothing here trades, signs, or
  touches a wallet; trading is a separate API (CLOB) this repo never calls.
- Docs: <https://docs.polymarket.com/market-data/discover-markets>

```bash
python scripts/pull_polymarket.py
python scripts/polymarket_flatten.py
```

## What a pull does

1. `GET /sports`, take the `sport == "cfb"` entry's `series` (2026: `12756`, slug
   `cfb-2026`). Read every run because the series is per season.
2. `GET /events/keyset?series_id=<series>&closed=false&limit=100`, following
   `after_cursor=<next_cursor>` until `next_cursor` is absent (2026-10-17: 4 pages, 357
   events).
3. Keep real games that have not kicked off: drop `<slug>-exact-margin` companion events,
   `ended == true` (closed=false still returns September games), and entries with no
   `startTime` (AP-poll futures). Pre-kickoff only, so no stored price is in-play.
4. Keep only `sportsMarketType` in `moneyline`, `spreads`, `totals`, with a trimmed field
   set. An untrimmed game is ~800KB (about 220 markets: quarter/half lines, team totals,
   exact margin, stat props).

Measured 2026-10-17 for that week: 111 games, all with moneyline, spreads and totals, and
roughly 50 full-game ladder rungs each (one game: 31 spreads, 21 totals from 35.5 to 75.5).
A live pull at 10:31Z the same day listed 218 upcoming games (two weekends' worth),
8,027 kept markets, 16,054 tick rows, and a 3.2MB snapshot file.

## Reading the rows

- `price` is Polymarket's displayed price (`outcomePrices`), a probability 0-1. It is not
  American odds and carries no book vig; the cost of trading is the bid/ask spread, so
  `best_bid`/`best_ask` are the prices you could actually sell/buy at.
- `best_bid`/`best_ask`/`last_trade_price` are quoted by Polymarket for the market's first
  outcome. The flatten gives the second outcome the complement (`bid = 1 - ask`).
- `line` is the row's own team's handicap, the `oa_odds_tick` convention. Polymarket puts
  the line on the first outcome only ("Spread: James Madison (-12.5)" has line -12.5 and
  outcomes James Madison, Georgia State), so the second outcome gets `+12.5`.
- No market is flagged as the main line, and **price nearest 0.5 alone picks dead
  markets.** A rung nobody quotes shows a placeholder price of 0.495/0.505 with a 0.01/0.99
  book, so it lands on an empty bid or ask (measured 2026-10-17: 476 of 16,054 rows; one
  game's "nearest 0.5" was Georgia State -20.5 while James Madison was a 0.765 moneyline
  favourite). Filter first, then pick:

  ```sql
  SELECT * FROM stg.pm_market_tick
   WHERE market = 'spreads' AND best_bid IS NOT NULL AND best_ask IS NOT NULL
     AND best_ask - best_bid <= 0.05 AND liquidity >= 100
  QUALIFY row_number() OVER (PARTITION BY pulled_at, event_id, side
                             ORDER BY abs(price - 0.5), liquidity DESC) = 1
  ```
- `market` keeps Polymarket's word `moneyline` (`oa_odds_tick` says `h2h`).

## Team names

Polymarket names teams by school (`teams[].alias`: "Georgia State", "James Madison"), so
the rule is `norm()` plus `polymarket_schema.ALIASES`, with no mascot strip. The flatten
exits 1 and lists any name that does not match a CFBD school; add it to `ALIASES`.

## Live odds page

`python -m cfb_system_maker live` serves <http://127.0.0.1:5070>: every game in progress with
its score, clock, win chance, and main live spread and total, plus games kicking off in the
next 3 hours. Code: `cfb_system_maker/live/` (`board.py` holds the rules), tests:
`tests/test_live_odds.py`. Run it on the Mac; the cloud gets 403 from Gamma.

- **Stores nothing.** These are in-play prices; keeping them out of `ingest/` keeps them out of
  anything that joins a "line". `polymarket_client.is_upcoming_game` still drops started games
  from snapshots.
- **Refresh:** the page polls every 30 s. `/events/keyset` is served from a cache a few
  minutes behind (measured 2026-10-17: at 19:02Z it held Clemson at Q4 7:52, updated 18:58Z,
  while `/events?slug=` had 6:42, updated 19:01Z), so the server walks it (~4 pages) only every
  2 minutes for the game list, and re-reads live and just-started games every 20 s through
  `/events?slug=a&slug=b...` in batches of 20. Each card shows its event's `updatedAt`. Gamma
  needs no key and has no quota we have hit.
- **Just kicked off:** a game past its `startTime` with no `live`/`ended` flag yet is listed
  with the live games as "Kicking off" (up to 4 hours), not dropped.
- **Game state** is on the event (measured 2026-10-17): `live`, `ended`, `score` as
  "away-home" in `teams[].ordering` order, `period` (`Q1`..`Q4`, `End Q2`, `End Q3`, `VFT`
  final, `CAN` cancelled) and `elapsed` (mm:ss, empty at a break). A game not yet started has
  none of these keys.
- **Main line** is the same filter-then-pick rule as above, tighter for live books: both a bid
  and an ask, at most 10 cents apart, at least $100 liquidity, priced 15-85%, then nearest 50%.
  The 15-85% band matters in blowouts, where the only tight book can be a decided rung (Army
  -2.5 at 98.6% while up 49-24, measured 2026-10-17). The moneyline skips the width and band
  rules and is greyed when its book is wider than 10 cents. A wide book's
  `outcomePrices` is stale (one live O/U 35.5 showed 0.5275 against a 0.055/1.0 book), so the
  page shows the bid/ask midpoint, never `outcomePrices`. With no rung passing, the card shows
  a dash: blowouts often have no live spread at all.
- **FBS only** (on by default, remembered per browser) keeps games with at least one FBS
  team, so Clemson vs Charleston Southern stays and Idaho vs Montana goes. The FBS list is
  CFBD's `raw/fbs_teams_{season}.json` (last season's if this season's is not scraped yet),
  matched through `polymarket_schema.school_key`. With neither file, the toggle is hidden.
