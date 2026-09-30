# Pre-registration — DraftKings Sunday-number forward log

**Committed 2026-09-30, before the first included decision (Sunday 2026-10-04 12:00 ET).**
The script is `scripts/dk_opener_log.py`. Rows whose decision time falls before 2026-10-04
12:00 ET are logged with `in_test = False` and graded by nothing.

**Amendment 1, 2026-09-30 — made before the first included decision, so no included data had
been seen.** Two changes:

- **The log is frozen.** Rows are appended and never rewritten. Grading reads the frozen file.
- **Stale lines are kept out of the fair.** The staleness rule now also applies to the books
  that form the fair.

Both are marked **(A1)** below.

## Question

Is DraftKings' Sunday number worth taking when it sits at least 1 point better than the other
real books' median? The primary test is whether it earns closing-line value (CLV) against
DraftKings' own close.

**Where this comes from.** The exploratory record
[`docs/massey-vs-opener-and-system-scan-2026-09-30.md`](../../../docs/massey-vs-opener-and-system-scan-2026-09-30.md)
(its O4 table, post-hoc) found that DraftKings' 2023–25 open-to-close move follows its gap to
Bovada's opener: it closes about 69% of that gap (t 3.6). That finding has three limits:

- It is post-hoc.
- The 2023–25 openers have no timestamps.
- Half of DraftKings' 2026 opens were look-ahead lines.

This log tests the same idea forward, at a fixed and timestamped decision time. It is a
line-shopping question (the outlier book is the bet, as in `prereg-line-shopping.md`), not a
ranking signal.

## Data

**Lines at decision time** come from Action Network tick paths in `stg.an_history_tick`,
collected every 5 h by `CFB-AN-History`. Each pull returns the whole timestamped path, so a
missed weekend pull does not lose Sunday's lines, as long as some pull lands before the event
settles.

**Books.** AN's own book list gives the ids, and the warehouse loader's labels are not used
(master mislabels them until `ea9aedca` merges). The real books are:

| id | Book |
| --- | --- |
| 49 | Caesars |
| 68 | DraftKings |
| 69 | FanDuel |
| 71 | BetRivers |
| 75 | BetMGM |

15 (consensus) and 30 (consensus opener) are not books.

**DraftKings close** is CFBD's REST payload, `stg.lines__lines` provider DraftKings. On 2026
weeks 1–5 it matched AN's DraftKings line at kickoff on 90% of the 49 games whose AN path runs
through kickoff (mean gap 0.09). AN's own path stops before kickoff on 86% of games, and there
it agreed only 48% of the time. So AN is not the close.

**Scores** come from `stg.games`.

**Games.** FBS vs FBS, regular season, 2026, and only AN events that map to a CFBD game on
the home team, away team and Eastern date.

## Decision time and the lines at it

- **T** is 12:00 ET on the last Sunday strictly before the game's Eastern kickoff date.
- **A book's line at T** is its last tick at or before T, whatever the tick's status. That
  tick counts as posted only if all three hold:
  - its status is `normal`, `opener` or null (`opener` is AN's mark on a book's first posting);
  - its odds are within [−135, +125];
  - it is not a live or alternate market.

  A book whose last tick is `unavailable` is off the board.
- **Fair**, `fair_ex`, is the median of the other real books posted at T, after amendment S1's
  guard: a book more than 2.5 points from the all-books median is dropped, when at least 3
  books are posted and at least 2 remain. The guard never drops the book being bet.
  - At least 2 other books are required.
  - **(A1)** Before the S1 guard, drop any other book whose last tick is more than 36 h before T.
    BetRivers, like DraftKings, has no `unavailable` ticks, so a pulled BetRivers line would
    otherwise feed the fair as if it were posted.
- **Stale.** AN records no `unavailable` ticks for DraftKings, so a line DraftKings has pulled
  still looks posted. A bet-book line whose last tick is more than 36 h before T is flagged
  `stale`: it was last priced before the previous Saturday. The primary analysis excludes
  stale rows.

## Rule

`diff = line_T − fair_ex`, in home-spread convention (negative = home favoured).

- If `diff ≥ +1.0`, bet **home** at DraftKings: DraftKings gives the home side 1 point or more
  over the fair.
- If `diff ≤ −1.0`, bet **away**.
- Otherwise, no bet.

The 1.0 threshold is `prereg-line-shopping.md`'s actionable cell. One bet per game, at
DraftKings' number and price at T.

## Outcomes

**Primary.**
- **CLV in points**, DraftKings rows, fresh, in test. For a home bet it is `line_T − close`;
  for an away bet it is `close − line_T`.
- **Reported with it:** mean CLV with a 95% interval from resampling whole decision Sundays;
  median; share positive; share zero; number of bets and of Sundays.
- **Holds** if the mean CLV is above 0 and its interval excludes 0.

**Secondary. None of these can change the primary verdict.**
1. **ATS at DraftKings' number and ROI at its price at T.** Report the Wilson interval, the ROI
   interval (clustered by Sunday) and the maximum drawdown in units. Pushes grade as pushes,
   and a missing price is taken as −110.
2. **FanDuel (69), same rule, ATS and ROI only.** CFBD's REST feed has no FanDuel close, and
   AN's path is too often stale to serve as one, so FanDuel gets no CLV.
3. **Dose-response.** Mean CLV by |diff| in [1, 1.5), [1.5, 2.5) and ≥ 2.5. The ≥ 2.5 band is
   where stale or erroneous lines concentrate.
4. **Stale rows,** graded separately with the same measures.

**Logged, not tested.** Sagarin's rank gap as of the last Massey edition dated before T's day.
The Massey pull runs Tuesday, so a Sunday-dated edition is not yet available at T. No test on
it is registered here; any use of it is exploratory.

## Size and power (decision-time data only; no close or score was looked at)

- **Expected bets.** On 2026 weeks 2–5 the rule fires on 18 fresh DraftKings rows: 1, 2, 8 and
  7 per week, while AN coverage ran 14–32 games a week. Ten decision Sundays remain, from
  Oct 4 to Dec 6. That suggests about **50–75 bets**.
- **CLV.** With DraftKings' move SD of 3.5 points as the planning SD, the minimum detectable
  mean CLV at n = 60 is 2.8 × 3.5 / √60 ≈ **1.3 points**. Clustering by Sunday makes it larger.
  The post-hoc record implies about 0.7 × 1.25 ≈ **0.9 points** for a typical triggered gap.
- **So the primary test is likely underpowered this season.** A null result is below floor,
  not evidence against the idea.
- **ATS.** The minimum detectable win rate (one-sided α .05, power .8, n = 60, against 0.5238)
  is about **0.68**. ATS is below floor this season whatever happens.

## The log (A1)

`dk_opener_log.py log` is append-only.

- **When a row is written.** A (game, book) row is written once, and only if both hold:
  - the game has not kicked off;
  - the collector has cycled at least 6 h past the game's decision time, measured as the
    latest AN tick in the warehouse being at least T + 6 h.
- **After that,** the row is never rewritten. A row that was not written before kickoff never
  is.
- **When it runs.** `collect_line_timing.cmd` runs `log` after every `history` pull (the
  `CFB-AN-History` task, every 5 h as registered on 2026-09-30). The warehouse the log reads is rebuilt daily at 05:00, so
  a Sunday decision's rows are normally frozen by Monday morning. Games kicking off before then
  can be missed. That is a coverage loss, not a bias from knowing outcomes.
- **`grade` reads the frozen file.** Only closes and scores come from the warehouse at grade
  time. So a later loss of AN tick paths, or a rebuild dropping `stg.an_scoreboard`, cannot
  change which bets exist.

## Read and trial count

- **One registered read,** on or after **2026-12-14** (the day after the last regular-season
  game): `python research/spread/scripts/dk_opener_log.py grade`.
- **Interim runs** print INTERIM and are not reads. Count each one in the results doc.
- **Trials registered here:** the primary test, plus secondaries 1–4. Anything else run on this
  log is exploratory and counted.
- **If it holds,** betting it needs a separate amendment. That amendment covers execution:
  DraftKings' Sunday limits, whether the number was clickable, and the key-number mix.
- **If it is below floor,** extending it into 2027 needs an amendment written before 2027's
  first included Sunday.

## What this does not do

- It does not touch `movement_forward_log.csv` (version B's dataset) or `weekly_slate.py`.
- It does not claim what was actually clickable. T's lines are rebuilt from AN's path, and
  AN's DraftKings feed carries no "off the board" status. The staleness flag is the only guard.
