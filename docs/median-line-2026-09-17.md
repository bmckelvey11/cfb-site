# The system builder grades against the median line

**Date:** 2026-09-17
**Code:** `cfb_system_maker/normalize.py` (`median_line`), `enrich.py` (`_build_line_move_index`)

## The change

The builder used to grade against one book: the named provider if a system pinned one,
otherwise `usable[0]` — array order. It now grades against the **median across books**,
per number, snapped to the nearest half point. `GameRecord.provider` is the literal
string `median` for every row, and the Provider filter has been removed from the editor.

## Why one book was the wrong default

`docs/cfbd-lines-coverage-2026-09-17.md` establishes the provider mix turns over
completely across the era: `consensus` carries 2013–2022 and then dies (1244 rows in
2022, 29 in 2023, none after), while DraftKings and ESPN Bet only appear from 2023. A
system pinned to a book therefore silently loses whole seasons, and the unpinned default
was array order, which is not a decision at all.

## How it is built

1. **Collapse to books, not rows.** CFBD posts one book twice in the same array
   (`DraftKings` / `Draft Kings`; the Caesars family), so a median over raw entries
   double-weights the duplicated book. Rows are grouped by `provider_key` first, keeping
   each book's most complete row — the rule `_best_of_book` already applied.
2. **Median per number.** Spread, total, spread-open and total-open are each medianed
   over the books that posted *that* number.
3. **Snap to a half point.** An even book count averages to quarters (-6.75), which no
   book posts and which can never push — leaving them would silently delete pushes from
   every backtest. Ties go away from zero (-6.75 → -7.0, +6.75 → +7.0), deliberately not
   Python's `round`, whose banker's rounding is asymmetric between a home and away price.

Opens are medianed the same way so `enrich`'s line-move features compare median-open
against median-close rather than mixing constructions.

## Measured impact

Rebuilt `games.csv` for 2013–2026 (13,936 games, all `provider=median`) and diffed
against the pre-change file:

| | |
| --- | --- |
| games whose spread changed | 4,240 of 13,936 (30.4%) |
| median absolute change | 1.0 pt |
| mean absolute change | 1.72 pt |
| max absolute change | 44.5 pt |

`sec-primetime-unders` moved from 186-130-3 / +$3,909 / 12.25% ROI to
**188-130-1 / +$4,091 / 12.82% ROI** on the same 319 bets. Two pushes became decisions,
which is the snapping rule doing what it is supposed to do.

That 44.5 max is worth understanding rather than dismissing: with only two books, the
median *is* the midpoint, so one bad line drags it. The observed extreme matches the
pattern in the normalize fixture (DraftKings -35.5 against consensus -14.5 on the same
game). This construction has no outlier rejection.

## Deliberate divergence from the warehouse

`core.fact_game` / `core.fact_game_line` still hold **per-book** rows and are untouched.
Per-book truth is required for CLV, which is per book by construction. So `games.csv` and
the warehouse now legitimately disagree on the line columns while still agreeing on every
identity column. `tests/test_core_agreement.py` asserts that divergence positively rather
than dropping the guard: the CSV must say `median`, the warehouse must name a real book,
and the median must sit inside the range of what the books posted.

## What this does not support

- **No outlier rejection.** A single bad book moves a two-book median by half the error.
  Nothing here trims, winsorises, or weights by book quality.
- **Open and close can rest on different book sets** when only some books published an
  open. Accepted over dropping the game; it means a line-move feature is not strictly a
  same-book difference.
- **Provider filters are parsed and dropped**, not rejected. Legacy URLs and saved systems
  carrying `providers` read as "no filter" rather than matching zero games. Both saved
  systems were checked first and carry empty provider lists, so nothing changed meaning.
- The 30.4% figure is against the *previous* file, whose unpinned rows were array order.
  It measures the change from an arbitrary baseline, not an error rate.
