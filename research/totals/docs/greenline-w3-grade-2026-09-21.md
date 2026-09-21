# PFF Greenline, 2026 week 3 — graded

**Question.** Did the 22 positive-edge unders PFF Greenline flagged for week 3
(captured 2026-09-17 15:59 ET, `data/ingest/pff_scoreboard/greenline_unders_2026_w3.md`)
win, and did the full week-3 flag board win?

**Method.** Two graders, two questions.

- The **slate question** — did the published under list win, at PFF's number and
  at the book's — is new here:
  `python research/totals/scripts/grade_unders_list.py --week 3`. The population
  is `greenline_unders_2026_w3.csv`, the published list; `book_line` from
  `greenline_unders_2026_w3_draftkings.csv` (repriced at DraftKings by
  `match_greenline_books.py`, capture 2026-09-17 16:15 ET) is joined onto it and
  the two are graded side by side. Half a point of total is worth roughly two
  points of win probability at these numbers, so they are not interchangeable.
  The reprice file is **not** the population: `match_greenline_books.py` keeps
  only games it could match at the book, which in week 2 is 23 of 36 picks. An
  earlier draft of this grader read it as the pick list and silently graded that
  subset; it now joins, reports how many matched, and prints every ungraded pick
  with its reason. Graded against the week 2 doc, it reproduces that doc's 21-15.
- The **signal question** — did every flag on the board win —
  is `python research/totals/scripts/grade_greenline.py --week 3`, unchanged,
  grading at the line in `pff_greenline_2026_w3.csv` (capture 2026-09-17 17:02 ET).

Finals come from the PFF schedule refreshed 2026-09-21 10:16 ET
(`python scripts/pull_pff_scoreboard.py --season 2026`). The Sep 16 schedule and
bet-split captures were copied to `*_20260916T134000.bak.csv` beside them before
that overwrite. The Greenline capture itself was **not** re-pulled: the frozen
decision-time board is what gets graded.

**Decision-time check.** PFF's `kickoff` column is Eastern local, confirmed against
CFBD (SYR@PITT reads `2026-09-17T19:30` in the capture, `2026-09-17T23:30Z` at
CFBD). The earliest week-3 kickoff is that 19:30 ET game; the latest capture used
here is 17:02 ET the same day. Every graded line was posted before its game
started.

**Data.** 22 under picks and 57 total flags, games of 2026-09-17 through
2026-09-19.

## Results — the 22-pick under list

**11-11, -1.00u, ROI -4.5%.** Identical at PFF's number and at DraftKings': all
22 matched at the book, seven were repriced by a half or a full point, and none of
the seven flipped.

| game | PFF line | DK line | final | result |
|---|---:|---:|---:|---|
| SYR @ PITT | 51.5 | 51.5 | 40 | Win |
| KU @ ASU | 50.5 | 50.5 | 41 | Win |
| NEV @ MTSU | 50.5 | 50.5 | 47 | Win |
| JMU @ SDSU | 46.5 | 46.5 | 39 | Win |
| FIU @ FAU | 62.5 | 62.5 | 26 | Win |
| LSU @ MISS | 58.5 | 57.5 | 56 | Win |
| ECU @ ODU | 49.5 | 48.5 | 37 | Win |
| FRES @ SJSU | 50.5 | 49.5 | 36 | Win |
| STAN @ DUKE | 51.5 | 50.5 | 42 | Win |
| UAB @ ULL | 56.5 | 55.5 | 35 | Win |
| CCAR @ DEL | 57.5 | 56.5 | 36 | Win |
| HOU @ TT | 52.5 | 52.5 | 54 | Loss |
| MRSH @ MOST | 52.5 | 52.5 | 54 | Loss |
| UVA @ WVU | 53.5 | 53.5 | 65 | Loss |
| VT @ UMD | 53.5 | 53.5 | 61 | Loss |
| MST @ SCAR | 58.5 | 58.5 | 75 | Loss |
| SMU @ LOU | 59.5 | 59.5 | 72 | Loss |
| CONN @ USM | 54.5 | 54.5 | 68 | Loss |
| UF @ AUB | 53.5 | 53.5 | 83 | Loss |
| UNT @ TXST | 63.5 | 62.5 | 84 | Loss |
| TEM @ TOL | 50.5 | 50.5 | 97 | Loss |
| GASO @ JVST | 52.5 | 52.5 | 58 | Loss |

Two rows — CCAR@DEL and GASO@JVST — the script leaves ungraded. Both carry PFF's
TBD-kickoff marker (`2026-09-19T00:00`), so PFF never posts their score, and the
warehouse fallback cannot supply one: `core.fact_game` has the Sep 18 and Sep 19
rows but no finals on them — the games are loaded, the scores are not. Their finals above are CFBD's (Coastal Carolina 14 – Delaware 22;
Georgia Southern 27 – Jacksonville State 31), taken by hand for this doc; one win,
one loss, so the script's 20-pick view is 10-10 and the full 22-pick list is
11-11 (-1.00u, ROI -4.5%, 95% CI 30.7% to 69.3%). The script names both as
ungraded in its output and will pick them up unchanged on the next warehouse
refresh.

The losses were not near misses. Seven of the eleven landed 7+ points over, and
Temple–Toledo landed 46.5 over a 50.5 total. The wins clustered the other way:
FIU–FAU landed 36.5 under. This was a high-variance slate in both directions, not
a slate of coin-flips.

## Results — all 57 flags

52 graded (5 not yet scored).

| segment | record | win% | units | ROI |
|---|---|---:|---:|---:|
| all | 30-22 | 57.7% | +5.27u | +10.1% |
| under | 23-21 | 52.3% | -0.09u | -0.2% |
| over | 7-1 | 87.5% | +5.36u | +67.0% |

By market total, under flags only: <50 6-5, 50-54.5 8-11, 55-59.5 7-4, 60-64.5
2-1, 65+ none.

By PFF's own `value` bucket, under flags only: <2% 3-5, 2-3% 8-4, 3-4% 7-6, 4%+
5-6.

Projection accuracy (n=52): PFF projection MAE 13.64, mean error +3.43; market
line MAE 13.90, mean error +2.52. PFF was closer in 28 of 52.

## What this does and does not support

- **11-11 is a flat week, and the interval says nothing more than that.** 95% CI
  30.7% to 69.3% on 22 picks. Break-even (52.4%) is inside it, as it will be for
  any single week at this sample size. Do not read the negative ROI as evidence
  against the signal.
- **Pooling with week 2 does not rescue it either.** The under list across both
  published weeks (36 picks in week 2, 22 in week 3) is 32-26: 55.2%, +3.09u,
  ROI +5.3%, 95% CI 42.5% to 67.3%. Break-even is still inside. Per
  `../CLAUDE.md`, this stays below the minimum detectable win rate for its own
  sample and is not an edge until a review says it clears its own floor. (The
  script's own pooled line reads 31-25 because it leaves the two TBD-kickoff
  games below ungraded.)
- **The 7-1 over flags are eight games.** They are the whole week's positive ROI
  on the full board, and eight games of anything is noise. The board's *under*
  half — the half the pick list comes from — was 23-21.
- **The book number did not matter this week, and that is a fact about this week.**
  Seven of 22 shopped better and none flipped. It is not a finding that repricing
  is irrelevant; a half point flips a pick whenever the total lands exactly
  between the two numbers, which simply did not happen here.
- **PFF's `value` still does not rank.** The 4%+ bucket went 5-6 and <2% went
  3-5. That is the third week running with no monotone ordering. The 2-4% window
  had already been dropped from the week 3 list per
  [greenline-edge-cap-revisit-2026-09-17.md](greenline-edge-cap-revisit-2026-09-17.md);
  this week does not argue for bringing it back.
- **The band split did not reappear.** Week 2's whole result came from 55-59.5
  (11-3); this week that band was 7-4 and 50-54.5 was 8-11. Consistent with
  [greenline-band-significance-2026-09-17.md](greenline-band-significance-2026-09-17.md)
  having withdrawn the band ordering.
- **The projection is not beating the market total.** MAE 13.64 vs 13.90, closer
  in 28 of 52 — indistinguishable from a coin flip, as in week 2. Whatever the
  under tilt is, it is not a better number.
- **Which of these got bet is a separate question.** The staking ledger is
  `research/bankroll/scripts/greenline_bet_log.py`; its week-3 rows are seeded but
  ungraded, and nothing in this doc speaks to stake size or realised bankroll.

## Reproduce

```bash
python scripts/pull_pff_scoreboard.py --season 2026
python research/totals/scripts/grade_unders_list.py --week 3
python research/totals/scripts/grade_greenline.py --week 3
```

Pool the under list across weeks with repeated `--week`; pool the full board with
`grade_greenline.py --all`.
