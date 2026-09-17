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

## The totals half has no source

The Prediction Tracker tape carries **no over/under, in any season**. Its `total` column
is the final combined score — it equals `home_points + away_points` on 11,332 of 11,344
rows where both are present. There is no `ou`-style column in any of the 179 columns or in
any season header from 2001 to 2025.

Candidates checked for a pre-2013 over/under, all on 2026-09-17:

| Candidate | Earliest season | Book or model | Access | Verdict |
| --- | --- | --- | --- | --- |
| Prediction Tracker (on disk) | 2001 | market line, book unnamed | local, already built | **spread only — no O/U** |
| Sportsbook Reviews Online | 2007 (per search result text) | book (offshore + Nevada) | site returns **404** | dead; Wayback unverifiable, see below |
| Sunshine Forecast (repole.com) | — | — | domain is now a personal homelab | gone |
| `jackschooley/cfb-betting` (GitHub) | **2014** | book (SBR-derived) | public repo | fails the 2013 test |
| Killersports / SDQL | unknown | book | query page returns no table rows to a plain GET; JS-driven | unverified, scrape-hostile |
| sports-statistics.com CFB Games | unknown | "opening spread/OU when available" | per-dataset pages | unverified, field text suggests CFBD upstream |
| BigDataBall, SportsDataIO | unknown | book | paid | not priced |

Sportsbook Reviews Online was the standard free archive — search results describe it as
carrying "moneylines, 2nd half lines, opening and closing point spreads and totals" from
offshore and Nevada books, with a Perma.cc capture dated 2022-02-20. **The live site now
404s, and archive.org was returning "Temporarily Offline" during this session**, so neither
its season range nor the retrievability of its files could be verified. It is the single
best lead for pre-2013 totals and should be retried against the Wayback Machine when the
Internet Archive is back up.

## Recommendation

1. **Spreads:** stop looking. The proposed next task — not done here, and not yet
   agreed — is to promote the existing Prediction Tracker tape into
   `core.fact_game_line` as a `_source`-tagged provider so 2001–2012 stops reading as
   "no lines". The join to `game_id` is already done, but this is **not an insert**:
   `core.fact_game_line` is rebuilt by `build_core` on every refresh, so it needs a
   loader entry plus a decision on what `provider_key` an unnamed market line gets.
2. **Totals:** retry the Sportsbook Reviews Online archive through the Wayback Machine
   once the Internet Archive is reachable. If its files come back, it covers spread,
   total, and moneyline together and would supersede point 1 as well.
3. **2006:** re-pull `ncaa2006.csv` from upstream before promoting anything — 281 rows is
   a truncated file, not a thin season.

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

- No claim that pre-2013 totals are unobtainable — only that no *reachable, verified*
  source was found in this session, with the best lead blocked by an Internet Archive
  outage rather than by absence.
- No pricing on the paid options. BigDataBall and SportsDataIO were not contacted and
  their pre-2013 coverage was not established.
- No value-level validation of PT's pre-2013 spreads against an independent source. The
  spreads are believed correct because the repo's spread research already depends on them,
  not because they were cross-checked here.
- No moneyline source for any pre-2013 season was found or looked for beyond what the
  table records.
