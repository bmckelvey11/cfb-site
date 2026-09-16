# Betting line coverage — 2026-09-16

## Question

What betting-line coverage does the warehouse actually have — which books, which
markets, which seasons, and where are the holes?

## Method

`scripts/audit_line_coverage.py` (read-only) against local `cfb.duckdb` as loaded
at 13:16 today. Reproduce with:

```
python scripts/audit_line_coverage.py --min-season 2012
```

Counts are **distinct games**, not rows — a season with three books posts three
rows per game, and row counts flatter the picture badly.

Coverage is judged on what a line-movement model needs, which is three separate
things that arrived in three different years: a **closing** line (grades the
bet), an **opening** line (the other end of the move the model predicts), and
**tick** history (when the move happened, so CLV has a timestamp).

## The shape: four eras, not one dataset

| Era | Close | Open | Books | Tick movement | 1H/1Q |
| --- | --- | --- | --- | --- | --- |
| 2012 | **none** | — | 0 | — | — |
| 2013–2020 | yes | **no** | 3 → 8 | no | no |
| 2021–2023 | yes | yes | 5–7 | no | no |
| 2024–2025 | yes | yes | 8–9 | no | AN snapshot |
| 2026 | yes | yes | 8 | AN tick + odds-api | yes |

Per season, distinct games:

| season | games | lined | spread close | spread open | moneyline | books |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2012 | 1,379 | 0 | 0 | 0 | 0 | 0 |
| 2013 | 1,534 | 848 | 848 | 0 | 0 | 3 |
| 2017 | 1,551 | 874 | 873 | 0 | 0 | 3 |
| 2020 | 1,125 | 567 | 567 | 0 | 0 | 8 |
| 2021 | 2,454 | 887 | 887 | 878 | 739 | 7 |
| 2023 | 3,734 | 1,413 | 1,413 | 873 | 797 | 7 |
| 2024 | 3,801 | 1,570 | 1,570 | 864 | 917 | 8 |
| 2025 | 3,831 | 1,599 | 1,599 | 938 | 908 | 9 |
| 2026 | 3,679 | 422 | 422 | 409 | 343 | 8 |

`lined` never exceeds ~1,600 because the `games` denominator counts every
division CFBD lists, and books only price FBS-involved games.

## The four findings that matter

### 1. No opening line before 2021

`spread_open` is zero for every season 2013–2020. Eight seasons have a closing
line and nothing to compare it against. **Any opener→close movement study starts
in 2021**, which is five usable seasons, not thirteen.

Even after 2021 the opener is not universal: it covers 864 of 1,570 lined games
in 2024 and 938 of 1,599 in 2025 — **about 55–60%**, not the whole slate.

### 2. The book panel breaks between 2023 and 2024

This is the finding with the most consequence for modelling, and it is invisible
in any row count.

| Book | First | Last | Seasons |
| --- | ---: | ---: | ---: |
| `consensus` | 2013 | **2023** | 11 |
| `teamrankings` | 2013 | **2023** | 11 |
| `numberfire` | 2013 | 2021 | 9 |
| `espn bet` | 2023 | 2025 | 3 |
| `circa` | **2024** | 2026 | 3 |
| `fanduel` | **2024** | 2026 | 3 |
| `betmgm` | **2024** | 2026 | 3 |
| `bet365` | **2024** | 2026 | 3 |
| `pinnacle` | **2025** | 2026 | 2 |

The three books with real history all stop at or before 2023. Every sharp book
starts in 2024 or later. **There is no season in which `consensus` and `pinnacle`
both appear** — zero overlap, so the two cannot be calibrated against each other
on this data.

A backtest running 2013→2026 on "the line" is therefore quietly switching which
market it is measuring partway through. `bovada` (2019–2026, 8 seasons) and
`caesars` (2018–2026, 6) are the only books that straddle the cut.

### 3. Tick-level movement is 2026-only

The Action Network scoreboard reaches back to 2015 — ~930 events a season, every
season. **The odds attached to it do not.**

| season | scoreboard events | market | 1H/1Q | tick events | ticks |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2015–2023 | 694–943 each | **0** | **0** | 0 | 0 |
| 2024 | 907 | 899 | 858 | 0 | 0 |
| 2025 | 910 | 892 | 872 | 0 | 0 |
| 2026 | 888 | 106 | 263 | 263 | 410,845 |

Per-book AN odds exist for **2024 onward only**, and the timestamped tick tape —
the only source that says *when* a line moved — exists for **2026 only**, 263
events so far. The-odds-api tape is younger still: 2026-09-09 to 2026-09-16, 9
books, 160 games.

So: CLV as a *number* is computable back to 2021 (open vs close). CLV with
*timing* — did we beat the close by acting at the right hour — is a 2026-and-
forward question with a few hundred games behind it.

### 4. 2012 is empty at the source, and it explains the `gameLines` audit gap

All 840 of CFBD's 2012 `lines` payloads contain an empty `lines[]` array. The
games are listed; no book priced them. These games can never reach
`core.fact_game_line`, and re-scraping will not change it.

This also closes the loose end left open in
[data-currency-check-2026-09-16.md](data-currency-check-2026-09-16.md). The
`audit_graphql_dump_age.py` "gameLines BEHIND by 1,508 games" decomposes
completely, with nothing left over:

| Segment | Games | Cause |
| --- | ---: | --- |
| 2012 | 840 | empty `lines[]` upstream |
| 2014–2024 scattered | 96 | same, a few games a season (2015 alone is 38) |
| 2026 | 572 | unplayed games in weeks 4+; REST posts forward lines, GraphQL does not |
| | **1,508** | **no pipeline defect** |

## What this does *not* support

- **This measures presence, not quality.** A season showing a closing line says
  a number is there; it says nothing about whether it is the true close, the
  right side of the spread convention, or a stale scrape. `scripts/audit_line_sign_convention.py`
  owns the sign question.
- **"Books" is a count of `provider_key` values, not of independent opinions.**
  `consensus`, `teamrankings` and `numberfire` are aggregators or models, not
  sportsbooks. Counting 2013 as "3 books" overstates the market depth of that
  era considerably — arguably it has zero real books.
- **The 55–60% opener coverage is not characterised.** Whether the games with an
  opener differ systematically from those without (bigger games? earlier kickoffs?)
  was not tested, and if they do, any movement model fit on them is selected.
- **Nothing here validates the 2026 AN tick tape.** 263 of 888 events is what the
  collector has reached, not a checked sample; `market` covering only 106 events
  while `1H/1Q` covers 263 is unexplained and worth a look.
- **No claim about edge.** Coverage is the input to a model, not evidence that
  any of it is predictive.

## What follows from it

1. **Fix the era in any backtest, or fix the book.** 2021–2026 is the honest
   window for opener→close work. If a longer window is needed, `bovada` is the
   only book with both meaningful history and current presence.
2. **The 2026 tick tape is the scarce asset.** It is the only timestamped record
   and it only accumulates going forward, which argues for keeping
   `CFB-AN-History` (Mondays 09:00) healthy — a missed week is not recoverable
   by re-scraping.
3. **Treat pre-2021 as close-only.** Eight seasons of closing lines are still
   usable for grading and for margin-vs-close work; they just cannot answer a
   movement question.
