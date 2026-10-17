# Odds provenance audit: the CFBD Bovada open — 2026-10-17

**Answer: the open is usable as a pre-kickoff line, with one gap. It is checked on a 2026
sample and assumed for 2021–2025.**

- **No timestamp anywhere.** Line rows in `raw/lines_<season>.json` have no time-like field in
  any season, 2013–2026. The only time in the file is the game's `startDate`.
- **Opens exist only from 2021.** No provider has `spreadOpen` or `overUnderOpen` before
  2021. Bovada rows appear in 2019 (318 FBS games) and 2020 (503) with current lines only.
- **Coverage is near-complete from 2021.** 3,927 of 3,945 FBS-vs-FBS games in 2021–2025 have
  both Bovada open numbers (99.5%). No conference misses more than 1.2%, and no week more than
  2.5%.
- **No duplicates.** No game has more than one Bovada row in any season.
- **The open is not the close.** Open and current spread are equal in only 10–17% of games a
  season, and the spread moves 3 or more points in 10–19%.
- **Pre-kickoff, checked on a 2026 sample.** 156 games appear with a Bovada open in an older
  CFBD pull made before kickoff. All 156 hold the same open in today's file. Nothing on disk
  does the same for 2021–2025.
- **The open is a real Bovada price, mostly.** the-odds-api's first Bovada pull before kickoff
  (2026, median 5 days out) matches CFBD's open spread exactly in 45% of 284 games, and within
  half a point in 73%. CFBD's open spread is on Action Network's Open-book path before kickoff
  in 89% of 273 games, against 56% for CFBD's current spread.

**Question.** Can the Bovada `spreadOpen` and `overUnderOpen` that CFBD serves, which every
Glicko record and the implied-score baseline score against, be treated as known before
kickoff? What does the field mean, how complete is it, and can any other source on disk
confirm it?

**Reproduce:** `python scripts/audit_open_provenance.py`
([`scripts/audit_open_provenance.py`](../../scripts/audit_open_provenance.py)). It is
read-only and prints every table below; `--json OUT` also writes them. **Roadmap:** §5 of
[`rating-model-roadmap.md`](rating-model-roadmap.md). **Builds on, not repeated here:**
[`odds-sources-an-vs-apis-2026-09-11.md`](../../docs/odds-sources-an-vs-apis-2026-09-11.md)
(what each odds source holds),
[`cfbd-lines-coverage-2026-09-17.md`](../../docs/cfbd-lines-coverage-2026-09-17.md) (the 2013
floor and provider eras), and `scripts/audit_line_sign_convention.py` (spread sign).

## Data and dates

| Source | What was read | Dates |
| --- | --- | --- |
| CFBD lines | `raw/lines_2013.json` … `raw/lines_2026.json` | games before 2026-10-17 00:00 UTC |
| Older CFBD pulls | `ingest/snapshots/` (9 files), `ingest/cfbd_completeness/before/raw/` (15), `backups/upcoming-before-refresh-20260928T184802Z/raw/` (1) | pulled 2026-08-26 to 2026-09-29 |
| the-odds-api | `core.fact_game_odds`, book `bovada`, pulls before kickoff | 81 pulls, 2026-09-09 to 2026-10-16 |
| Action Network | `stg.an_history_tick`, book 30 ("Open"), full game, not live, before kickoff | first ticks from 2026-04-02; last load 2026-09-28 |

Nothing at or after 2026-10-17 00:00 UTC is used. A pull's observed-at time is its file's
modification time, or the date in its name when that is earlier.

## What the fields are

| Field | Meaning |
| --- | --- |
| `spread`, `overUnder` | The book's current number when CFBD last saw it. For a finished game this is the last number CFBD stored, close to the close |
| `spreadOpen`, `overUnderOpen` | The first number CFBD stored for that book and game. Held fixed once stored (below) |
| `startDate` (game level) | Kickoff. The only time in the file |

No line row in any season carries an observed-at, updated-at or ingested-at field. CFBD does
not say when it first saw a line, so the open's time can only be bounded from outside.

Which providers carry opens:

| Season | Providers with any open | Bovada rows with `spreadOpen` / `overUnderOpen` |
| --- | --- | --- |
| 2013–2020 | none | — |
| 2021 | Bovada | 878 / 879 |
| 2022 | Bovada | 852 / 855 |
| 2023 | Bovada, DraftKings | 852 / 853 |
| 2024 | Bovada, DraftKings, ESPN Bet | 801 / 798 |
| 2025 | Bovada, DraftKings, ESPN Bet | 934 / 934 |
| 2026 | Bovada, DraftKings | 502 / 502 |

Row counts include non-FBS games. DraftKings' open total is mostly missing in 2024–2025 (161
of 714 rows in 2024, 84 of 683 in 2025), so Bovada is the only book with a complete open in
every season from 2021.

## Coverage

FBS-vs-FBS games that kicked off before the cutoff:

| Season | Games | With a line | With a Bovada row | Bovada open spread | Bovada open total | Both | Games with 2+ Bovada rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2013–2018 | 737–776 a season | all | 0 | 0 | 0 | 0 | 0 |
| 2019 | 774 | 774 | 318 | 0 | 0 | 0 | 0 |
| 2020 | 534 | 534 | 503 | 0 | 0 | 0 | 0 |
| 2021 | 770 | 770 | 770 | 770 | 770 | 770 | 0 |
| 2022 | 776 | 776 | 776 | 769 | 774 | 767 | 0 |
| 2023 | 792 | 792 | 792 | 790 | 792 | 790 | 0 |
| 2024 | 799 | 798 | 798 | 795 | 792 | 792 | 0 |
| 2025 | 808 | 808 | 808 | 808 | 808 | 808 | 0 |
| 2026 to date | 337 | 337 | 337 | 337 | 337 | 337 | 0 |

**Missing by conference, 2021–2025.** A game counts once for each conference in it.

| Conference | Games | Missing |
| --- | --- | --- |
| Conference USA | 434 | 1.2% |
| Sun Belt | 506 | 1.0% |
| FBS Independents | 249 | 0.8% |
| Pac-12 | 309 | 0.6% |
| American Athletic | 490 | 0.4% |
| Big Ten | 600 | 0.3% |
| Mid-American, Mountain West, SEC | 465–586 | 0.2% |
| ACC, Big 12 | 590, 481 | 0.0% |

**Missing by week, 2021–2025.** Week 13 is the worst at 2.5% (8 of 315), then week 4 at 1.4%.
Every other week, and the postseason, is under 1%. The 18 missing games are too few, and too
spread out, to bias a score.

## Open versus current

Bovada's first row, FBS-vs-FBS games with both open and current numbers:

| Season | Games | Spread unchanged | Total unchanged | Mean spread move | Mean total move | Spread moved 3+ |
| --- | --- | --- | --- | --- | --- | --- |
| 2021 | 770 | 16.8% | 13.4% | 1.28 | 1.58 | 10.0% |
| 2022 | 767 | 15.9% | 9.0% | 1.37 | 1.98 | 12.6% |
| 2023 | 790 | 9.9% | 10.0% | 1.81 | 1.86 | 18.9% |
| 2024 | 792 | 14.8% | 13.6% | 1.40 | 1.48 | 12.8% |
| 2025 | 808 | 13.9% | 11.6% | 1.42 | 1.61 | 16.1% |
| 2026 | 337 | 17.2% | 11.0% | 1.23 | 1.44 | 11.3% |

Moves in points. The open is a distinct, earlier number in most games, not a copy of the
close. So the records that score against it are scoring against an early-week line, not the
close.

## Was the open there before kickoff?

**Older CFBD pulls (2026).** Twenty-five pulls of `lines_<season>.json` sit outside `raw/`.
In every pull made before a game's kickoff that already had a Bovada open, today's file holds
the same open spread and total: 156 distinct 2026 games, 156 unchanged. The earliest pull
(2026-08-26) already held the opens for 51 week-1 games before any of them kicked off. Every
pull also agrees with today's file on every game with an open in both, so CFBD does not
rewrite an open once stored.

The 2021–2025 copies in `ingest/cfbd_completeness/before/` were pulled on 2026-08-28, after
every one of those games. They agree with today's file on every open (100%), which shows the
history is stable across re-pulls, but they cannot show the open existed before kickoff.

**the-odds-api (2026).** Bovada prices from every pull before kickoff, matched to CFBD by game
id, 284 FBS-vs-FBS games:

| Comparison | Exact | Within 0.5 | Within 1 | Median gap |
| --- | --- | --- | --- | --- |
| First pull's spread vs CFBD open spread | 44.7% | 72.5% | 86.6% | 0.5 |
| First pull's total vs CFBD open total | 51.8% | 75.0% | 87.7% | 0.0 |
| Last pull's spread vs CFBD current spread | 30.6% | 64.4% | 81.7% | 0.5 |
| Last pull's total vs CFBD current total | 33.1% | 67.3% | 84.9% | 0.5 |

The first pull came a median 123 hours before kickoff. CFBD's open spread equals Bovada's
spread in at least one pre-kickoff pull for 57.0% of games, and its open total for 58.8%. The
rest are most likely games where Bovada had already moved by the first pull: the-odds-api
pulls every 6 hours (every 2 on Saturdays) and started on 2026-09-09. The match is not better
when the first pull is early: for spreads it is 47.7% exact when the first pull is more than 120
hours out, and 39.6% at 48–120 hours. For totals the early pulls match better (65.1% exact
beyond 120 hours, 33.0% at 48–120).

**Action Network (2026).** AN's book 30 is labelled "Open", but its value changes over the
weeks before a game, so it is a slow market line rather than a fixed opener. 444 of AN's 888
2026 events pair to exactly one CFBD game by school names and kickoff within a day; 273 of
those have an Open-book tick before kickoff and a CFBD Bovada open.

| Comparison | Exact | Within 0.5 | Within 1 | Median gap |
| --- | --- | --- | --- | --- |
| AN first Open-book spread vs CFBD open spread | 22.3% | 43.6% | 57.9% | 1.0 |
| AN first Open-book total vs CFBD open total | 14.3% | 29.3% | 50.9% | 1.0 |

AN's first tick comes a median 8 days before kickoff, and the Open book keeps moving after
it, so a first-tick match is a strict test. The better test is whether CFBD's open appears
anywhere on AN's pre-kickoff Open-book path:

| Number from CFBD | Seen on AN's Open-book path before kickoff |
| --- | --- |
| Open spread | 89.4% |
| Current spread (reference) | 56.4% |
| Open total | 69.2% |
| Current total (reference) | 50.2% |

The open lands on the market's pre-kickoff path far more often than the close does. That fits
an open taken early in the week, and not a number recorded at or after kickoff.

## Verdict

- **2026:** the open is checked on a sample. For the 156 games an older pull could show, CFBD
  held it before kickoff and never changed it afterwards. It agrees with independent Bovada and
  market prices at rates an early-week line should. 2026 games after the last older pull
  (2026-09-29) are assumed, like 2021–2025, though with the same behaviour seen weeks earlier.
- **2021–2025:** the open is assumed, on two grounds that are evidence but not proof. CFBD
  behaves the same way in 2026, storing the first number and never rewriting it. The field's
  meaning is the same in every season. No pre-kickoff pull of those seasons exists on disk, and
  CFBD serves no time, so it cannot be checked.
- **Before 2021:** no open exists. Any result that needs a pre-kickoff line for 2013–2020
  needs another source.

Under the evaluation standard's reconstructibility gate, results scored on the 2021–2025 open
(the Glicko records, the implied-score baseline) stay provisional on this one point. They no
longer rest on an untested field. The 2026 checks make "the open is an early, fixed, real
Bovada number" the working assumption for those seasons.

## What this does not support

- **An observed-at time for the open.** The audit bounds it (before kickoff, and for the 2026
  sample at least days before) but cannot time it. A decision rule that needs "the line at Tuesday
  noon" still needs a timestamped source.
- **The close.** CFBD's `spread` is the last number CFBD stored, which may be hours before
  kickoff. It matches the last the-odds-api pull exactly in only 31% of games. It is not a
  verified closing line, and CLV work should keep using AN's timestamped close.
- **Other books.** Only Bovada was audited. DraftKings' open total is mostly missing in
  2024–2025, and ESPN Bet ended in 2025.
- **`model.market_snapshot`.** The roadmap's snapshot table is still not built. This audit
  says which CFBD field may fill its `is_opening_candidate` rows, and with what caveat.
- **Price.** CFBD's open has no price; only the number is audited.

## Trial count

None. This is a data audit; no model was fitted or scored.
