# Where to get pre-2013 college football lines — 2026-09-17

**Reproduce:** `python scripts/probe_pre2013_lines.py`

## The question

`core.fact_game_line` is empty for every season before 2013, and
[cfbd-lines-coverage-2026-09-17.md](cfbd-lines-coverage-2026-09-17.md) established that
this is CFBD's floor, not a pull gap. What source can fill 2012 and earlier?

## Headline: the spread half is already solved, in this repo

`{CFB_DATA_ROOT}/ingest/prediction_tracker_lines.csv` already carries a market spread for
2001–2012, one row per game, each with a CFBD `game_id` attached. It is built by
`research/spread/scripts/build_prediction_tracker.py` from the season CSVs already sitting
in `ingest/prediction_tracker/`, and it is documented in detail at
[research/spread/docs/prediction-tracker.md](../research/spread/docs/prediction-tracker.md).
The spread research has been running on it since at least 2026-09-02.

| season | rows | with `game_id` | close (`line`) | open (`lineopen`) |
| ---: | ---: | ---: | ---: | ---: |
| 2001 | 652 | 652 | 650 | 0 |
| 2002 | 707 | 707 | 700 | 646 |
| 2003 | 698 | 698 | 695 | 694 |
| 2004 | 656 | 656 | 656 | 656 |
| 2005 | 665 | 665 | 662 | 661 |
| 2006 | 281 | 281 | 281 | 280 |
| 2007 | 712 | 712 | 712 | 712 |
| 2008 | 718 | 718 | 718 | 716 |
| 2009 | 714 | 714 | 714 | 714 |
| 2010 | 718 | 718 | 718 | 716 |
| 2011 | 715 | 715 | 715 | 715 |
| 2012 | 732 | 732 | 731 | 731 |

Match quality is high: 17,731 of 17,755 rows across 2001–2025 are `matched`, 23 are
`matched_score_mismatch`, 1 is `ambiguous`.

Two known holes: **2006 is 281 rows against ~700 elsewhere**, and **2001 has no opening
line at all**.

### 2006 is an upstream gap, not a truncated download (checked 2026-09-17)

Re-pulled `https://www.thepredictiontracker.com/ncaa2006.csv` (HTTP 200, 141,620 bytes).
It is **byte-identical** to the copy on disk — both 281 rows, MD5
`bef9c98b5fdc8f2372f5a7a45ba4787b`. The season file upstream simply stops early:

| CFBD week | 1 | 2 | 3 | 4 | 5 | 6 | 7–9 | 10 | 11+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| games | 44 | 50 | 50 | 49 | 50 | 34 | 0 | 4 | 0 |

Weeks 1–5 run at the same rate as 2005 and 2007, week 6 is half, weeks 7–9 are empty, and
four stray games sit at week 10. So 2006 is usable for weeks 1–6 and absent afterwards —
not a file to re-fetch. Whether an older, fuller capture exists could not be checked: the
Internet Archive was returning "Temporarily Offline" throughout this session.

## The totals half has no source

The Prediction Tracker tape carries **no over/under, in any season**. Its `total` column
is the final combined score — it equals `home_points + away_points` on 11,332 of 11,344
rows where both are present. There is no `ou`-style column in any of the 179 columns or in
any season header from 2001 to 2025.

Candidates checked for a pre-2013 over/under, all on 2026-09-17:

| Candidate | Earliest season | Book or model | Access | Verdict |
| --- | --- | --- | --- | --- |
| Prediction Tracker (on disk) | 2001 | market line, book unnamed | local, already built | **spread only — no O/U** |
| **Sportsbook Reviews Online** | **2007** | **book (offshore + Nevada)** | **live HTML tables, scrape** | **verified — closes 2007–2012, see below** |
| Sunshine Forecast (repole.com) | — | — | domain is now a personal homelab | gone |
| `jackschooley/cfb-betting` (GitHub) | **2014** | book (SBR-derived) | public repo | fails the 2013 test |
| Killersports / SDQL | unknown | book | query page returns no table rows to a plain GET; JS-driven | unverified, scrape-hostile |
| sports-statistics.com CFB Games | unknown | "opening spread/OU when available" | per-dataset pages | unverified, field text suggests CFBD upstream |
| BigDataBall, SportsDataIO | unknown | book | paid | not priced |

### Sportsbook Reviews Online is live — corrected 2026-09-17

An earlier pass in this session recorded the archive as dead on a 404. That was wrong:
the site **404s unrecognised user agents**. With a browser user-agent string the index and
every season page return HTTP 200. `robots.txt` disallows only `/go/` and allows
`/scoresoddsarchives/`, so reading the archive is permitted.

Index: `/scoresoddsarchives/ncaafootball/ncaafootballoddsarchives.htm`. It links **16
season pages**, `ncaa-football-2007-08` through `ncaa-football-2022-23` — so 2007 is the
floor, and **six seasons (2007–2012) fall inside the gap**.

Measured by `scripts/probe_sbr_ncaaf_archive.py`:

| season | rows | games | Open | Close | ML | 2H |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2007 | 1424 | 712 | 1421 | 1423 | 1388 | 1414 |
| 2008 | 1436 | 718 | 1436 | 1436 | 1428 | 1436 |
| 2009 | 1540 | 770 | 1484 | 1485 | 1436 | 1430 |
| 2010 | 1616 | 808 | 1526 | 1601 | 1584 | 1558 |
| 2011 | 1624 | 812 | 1528 | 1584 | 1418 | 1503 |
| 2012 | 1674 | 837 | 1564 | 1567 | 1610 | 1518 |

~4,457 games, near-total field fill. Game counts line up closely with CFBD's own
(CFBD 2010/2011 = 808/812 against SBR's 808/812), which is a good sign for the join.

Columns are `Date, Rot, VH, Team, 1st, 2nd, 3rd, 4th, Final, Open, Close, ML, 2H` — so
opening and closing prices, a moneyline, and a second-half line, from real books rather
than aggregators. **This is the only verified pre-2013 source of totals and moneylines.**

Three costs to price before building anything on it:

1. **No file download.** Each season is an inline HTML table; this is a scrape, not a
   fetch. 16 pages total, so the volume is trivial.
2. **Spread and total are not labelled.** Two rows per game (V then H). Within a pair,
   one row's `Open`/`Close` is the spread and the other's is the game total, and *nothing
   in the markup says which*. The usual heuristic is that the larger absolute value is
   the total, but 2007 LSU–Mississippi State carries `Open 16.5 / Close 19.5` against
   `Open 27 / Close 44`, which that rule reads wrong. This is the real work in the task,
   not the fetching.
3. **Team names are unspaced** (`MiamiOhio`, `MississippiSt`, `BuffaloU`) and need a
   crosswalk to CFBD names before a `game_id` join. `build_prediction_tracker.py` already
   solves the same problem for a different vendor's spellings and is the model to copy.

## Recommendation

1. **Spreads:** stop looking. The proposed next task — not done here, and not yet
   agreed — is to promote the existing Prediction Tracker tape into
   `core.fact_game_line` as a `_source`-tagged provider so 2001–2012 stops reading as
   "no lines". The join to `game_id` is already done, but this is **not an insert**:
   `core.fact_game_line` is rebuilt by `build_core` on every refresh, so it needs a
   loader entry plus a decision on what `provider_key` an unnamed market line gets.
2. **Totals and moneylines, 2007–2012:** scrape the Sportsbook Reviews Online archive.
   It is verified live, permitted by robots.txt, and carries open/close spread, total, ML
   and a 2H line for ~4,457 games. Because it also carries spreads from real books, it is
   a *better* pre-2013 spread source than PT for 2007 onward and would partly supersede
   point 1. Budget the effort against the spread-vs-total disambiguation and the team-name
   crosswalk, not the download.
3. **Totals, 2001–2006:** still no source. SBR starts at 2007 and PT has no over/under
   at any date, so these six seasons remain spread-only.
4. **2006:** nothing to re-pull — the upstream file is identical to the local copy and
   covers only weeks 1–6 (see above). Either accept 2006 as a partial season or try the
   Wayback Machine for an older capture once the Internet Archive is reachable.

## Caveats that survive any of the above

- **PT's `line` is not a book line.** It is a single unnamed market number. It has no
  provider, no timestamp, and cannot be pooled with `fact_game_line`'s named providers
  without a `_source` distinction. The repo's own
  [cfbd-lines-coverage doc](cfbd-lines-coverage-2026-09-17.md) already notes that even
  CFBD's 2013–2017 rows are aggregators and model lines rather than real sportsbooks, so
  a provider-naive pre-2013 series is consistent with the era, not an anomaly.
- **`line` is *treated as* the close, not proven to be one.** The repo inherited that
  reading from `research/spread/docs/session-guide-2026-09-02.md`; nothing here
  establishes whether the pre-2013 values are true closing numbers or a stale midweek
  snapshot.
- **`lineopen` is a look-ahead number for early-season games**, posted months ahead.
  `research/spread/docs/session-guide-2026-09-02.md` already flags this, along with the
  UCLA–California `lineopen = −55.0` typo. Anything using the opener as a bettable anchor
  pre-season is measuring a price nobody could take.
- **Spread orientation is PT's, not CFBD's.** On the 409 rows where
  `orientation_flipped = 1`, `line` refers to `away_team`. Negate again on those rows.

## What this does not support

- **No parse of the SBR archive was performed.** Coverage was counted from the HTML
  tables; no row was converted into a spread or total, and the spread-vs-total
  disambiguation above is an unsolved problem, not a described solution. The field-fill
  numbers say a value is present, not that it is correct or correctly attributed.
- No source of any kind was found for 2001–2006 totals. That is an absence of evidence
  from this session's searches, not evidence that none exists.
- No pricing on the paid options. BigDataBall and SportsDataIO were not contacted and
  their pre-2013 coverage was not established.
- No value-level validation of PT's pre-2013 spreads against an independent source. The
  spreads are believed correct because the repo's spread research already depends on them,
  not because they were cross-checked here.
- No moneyline source for any pre-2013 season was found or looked for beyond what the
  table records.
