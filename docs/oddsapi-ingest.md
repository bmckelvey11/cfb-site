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

**Saturday pulls, added 2026-09-11.** A second task, **`CFB-Odds-Snapshot-Saturday`**, runs
the same wrapper every two hours from 10:00 to 18:00 ET on Saturdays — five extra pulls; the
daily task already fires at 20:00 — with the same battery and `StartWhenAvailable` settings.
About 65 more credits a month, ~425 of 500 in total, off-season included: the endpoint charges
per pull whether or not events are listed. Registered because both slates now price every book
from this snapshot ([`odds-sources-an-vs-apis-2026-09-11.md`](odds-sources-an-vs-apis-2026-09-11.md),
*Decision*); a six-hour-old number on a Saturday afternoon is what this shortens. Verified by a
manual `Start-ScheduledTask` (snapshot written, 470 credits remaining). Pause with
`Disable-ScheduledTask -TaskName CFB-Odds-Snapshot-Saturday`.

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

**Since amendment S4 (2026-09-11) this snapshot plus Pinnacle is the whole live fair.** Action
Network no longer votes; Caesars left the set and the four shared books are priced from here
rather than live. `book_set_version` 4. Measured on 2026 week 3, 49 games, both versions built
minutes apart: `book_fair` moved on 8 games, median 0.00, max 0.50 points; E4's side flipped on
2; the edge ≥ 1 set went 24 → 23. The paragraphs below describe the S2 promotion as it was made
and stand as the record of it.

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

## Read by the over-zero board — the only feed ✅ 2026-09-11

`models/over_zero/scripts/best_line_slate.py` takes its game list and every quote from the
latest snapshot (`oa_games`); the Action Network scoreboard is not read. The fair spread and
fair total are the median of the four regulated books — DraftKings, FanDuel, BetRivers, BetMGM,
the previous set minus Caesars — and the offshore five keep their single-book views. School
names come from `oddsapi_flatten.school_of`, so the board prints CFBD spellings ("Miami",
"James Madison") where it printed Action Network's ("Miami (FL)", "JMU").

Measured against the last AN-fair run, minutes apart on the same snapshot: 10 picks on 85 games
→ 10 on 84. On the 38 games whose names join across the two spellings, the fair spread moved on
3 and the fair total on 6, none by more than a point, and all 4 picks in that set agree. Every
view's `asOf` is now the snapshot time, not the run time.

## It loads — `stg.oa_odds_tick`, `stg.oa_snapshot`, `core.fact_game_odds` ✅ 2026-09-10

`scripts/oddsapi_flatten.py` turns the snapshots into two flat CSVs under
`data/processed/oddsapi/`, which load to `stg` under types pinned in
`cfb_system_maker/oddsapi_schema.py` — the same shape PFF's ingest uses, and for
the same reason: `line` is empty on every `h2h` row, so `read_csv_auto` would
sniff it VARCHAR on a moneyline-only snapshot and refuse the next load.

- **`stg.oa_odds_tick`** — one row per outcome per snapshot, `(pulled_at,
  event_id, book, market, side)` with line and price. Long and narrow like
  `stg.an_history_tick`; a wide row would need a column per book.
- **`stg.oa_snapshot`** — one row per pull, carrying the nullable quota fields.
  Per-snapshot metadata does not belong on twenty thousand tick rows.
- **`core.fact_game_odds`** — the same ticks resolved onto `game_id`.

**Why the resolution is in `core`, not the flatten.** `refresh_cfbd.py` runs every
flatten *before* it rebuilds, so a flatten that joined games would read the
previous run's `stg.games` — and this week's kickoffs are what goes stale. The
flatten does resolve *names* (that needs no warehouse) and writes CFBD's own
spelling into `home_school`/`away_school`, so `core` joins on exact equality
rather than carrying a second copy of the mascot strip in SQL that would not know
about `ALIASES`.

**Every snapshot's rows are kept**, including ones identical to the pull before.
Content dedupe would save 72% (18,776 outcome rows → 5,309 distinct quotes,
measured 2026-09-10), but storing every sample keeps "observed unchanged at T"
distinguishable from "not observed". Revisit if volume bites.

An unresolved team name leaves `game_id` NULL rather than guessing, and the
flatten exits 1 so a scheduled run surfaces it.

## Before this loads into the warehouse: the join key

Odds API events carry their own `id`, `commence_time` (UTC ISO8601), and team
names **including the mascot** — `"Miami Hurricanes"`, `"Florida A&M Rattlers"`.
The warehouse's `stg.games` carries school only. `normalize.py` does not close
that gap (it normalizes CFBD payloads, not vendor names).

**Measured 2026-09-10 and the gap is small** —
[`oddsapi-team-name-join-2026-09-10.md`](oddsapi-team-name-join-2026-09-10.md),
`python scripts/audit_oddsapi_team_names.py --list`. Of 173 distinct names in the
snapshots on disk, 170 resolve to exactly one `core.dim_team` row under the same
mascot strip `oa_resolve` uses, **none resolve ambiguously**, and 3 need an alias
(`Appalachian State`→`App State`, `Southern Mississippi`→`Southern Miss`,
`UMass`→`Massachusetts`). Accents and apostrophes have to be folded, not blanked:
CFBD spells them `San José State` and `Hawai'i`.

The FCS half of the original worry does not hold — 39 of the resolved names are
FCS and all 39 land. The example above (`"Ohio Dominican"`) is misleading for a
different reason: the-odds-api only lists games with posted markets, so a D2
opponent never appears in a snapshot at all.

**Still open before a flatten:** resolving a name to a `team_id` is one of three
keys — pairing `(home_team_id, away_team_id, commence_time)` onto a `game_id`
still has to survive kickoff drift and neutral sites, which is unmeasured. And a
one-sided resolve does not inherit the protection the spread slate gets from
merging on both teams, so a flatten should fail loudly on a name it cannot
resolve rather than guessing.

The quota fields (`requests_last`, `requests_used`, `requests_remaining`) are
nullable: they mirror response headers, and a missing header lands as `null`.
A flatten that gates further pulls on `requests_remaining` has to handle that.

No-lookahead: these are pre-game snapshots and safe. Any future historical pull
must keep the snapshot timestamp on the row — a snapshot taken after kickoff is
result-contaminated.

## Pinnacle via oddspapi.io — a second vendor, observation only

the-odds-api's NCAAF feed has no Pinnacle. **oddspapi.io** does, on its free plan, and
`scripts/pull_oddspapi.py` pulls it into `data/ingest/oddspapi/` (a different directory from
`oddsapi/`; the names are one letter apart, so check which one you are in).

- **Auth** is `apiKey` as a query parameter, read from `ODDSPAPI_API` in `.env`. The API sits
  behind Cloudflare, which 403s urllib's default User-Agent (error 1010); the puller sends its own.
- **One request per pull** via `/v4/odds-by-tournaments?tournamentIds=27653&bookmakers=pinnacle`.
  27653 is "NCAA, Regular Season" under sportId 14. The per-fixture `/v4/odds` endpoint costs one
  request *per game*, so never use it for the slate. `/v4/account` echoes the API key back in its
  response body; do not print it.
- **Budget:** free plan is 250 requests/month. Task **`CFB-Pinnacle-Snapshot`** runs
  `scripts/pull_oddspapi.cmd` daily at 08:00, ~30/month. Log: `data/logs/oddspapi_pull.log`.
- **Spread parsing.** Pinnacle's `bookmakerMarketId` is `line/<...>/<period>/spreads`; only
  period 0 is the full game. Periods 1+ are halves and quarters and `altLine/...` are alternate
  numbers, all also flagged `mainLine` within their own market — a period-blind parse returns the
  first-half line at roughly half the number. `bookmakerOutcomeId` is `<home spread>/home` in
  betting sign. `participant1` is the home team (46/46 joined that way on 2026-09-09, 0 swapped).
- **Read by the slate** into `Pinnacle_home`, `Pinnacle_odds`, `pin_limit`, `pin_vs_fair`, and
  Pinnacle **votes in `book_fair`** as one book of up to eleven under **amendment S3** of
  `research/spread/docs/prereg-line-shopping.md` (`book_set_version` 3 on forward-log rows).

```powershell
schtasks /Query /TN "CFB-Pinnacle-Snapshot" /FO LIST /V | Select-String "Last Run Time|Last Result|Next Run Time"
Start-ScheduledTask -TaskName CFB-Pinnacle-Snapshot          # fire once by hand
Disable-ScheduledTask -TaskName CFB-Pinnacle-Snapshot
```
