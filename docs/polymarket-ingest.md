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

## Reading the rows

- `price` is Polymarket's displayed price (`outcomePrices`), a probability 0-1. It is not
  American odds and carries no book vig; the cost of trading is the bid/ask spread, so
  `best_bid`/`best_ask` are the prices you could actually sell/buy at.
- `best_bid`/`best_ask`/`last_trade_price` are quoted by Polymarket for the market's first
  outcome. The flatten gives the second outcome the complement (`bid = 1 - ask`).
- `line` is the row's own team's handicap, the `oa_odds_tick` convention. Polymarket puts
  the line on the first outcome only ("Spread: James Madison (-12.5)" has line -12.5 and
  outcomes James Madison, Georgia State), so the second outcome gets `+12.5`.
- No market is flagged as the main line. Pick it in the query: price nearest 0.5, or the
  highest `liquidity`.
- `market` keeps Polymarket's word `moneyline` (`oa_odds_tick` says `h2h`).

## Team names

Polymarket names teams by school (`teams[].alias`: "Georgia State", "James Madison"), so
the rule is `norm()` plus `polymarket_schema.ALIASES`, with no mascot strip. The flatten
exits 1 and lists any name that does not match a CFBD school; add it to `ALIASES`.
