# Does every book quote a home-relative spread?

**2026-09-10.** Reproduce with `python scripts/audit_line_sign_convention.py`. Follows
[the DraftKings key collapse](lines-provider-key-split-2026-09-10.md) and
[the Bucket C merges](core-merge-bucket-c-2026-09-10.md), which added the rows in question.

## The question

`GameRecord.spread` and `core.fact_game.selected_spread` are **home-relative** — negative
when the home team is favoured. `_build_fact_game_line` inherits that from CFBD's REST
payload without ever checking it, and `_merge_game_lines` then carried **8,575 rows** in from
the ActionNetwork tape under five books `core` had never held: circa, fanduel, betmgm,
bet365, pinnacle. `formatted_spread` is NULL on every one of them, so the usual eyeball check
is unavailable.

An inverted book is silent. Nothing raises, no row count moves; a backtest simply reads the
favourite as the underdog for that book and the result looks like a bad model rather than a
bad sign. So: does any book disagree with the convention?

## Method

Two independent checks, because either alone has an excuse.

1. **Against a reference book on the same game.** A per-game reference spread is the average
   of four long-running, broad-coverage books (consensus, bovada, espn bet, teamrankings) —
   averaged rather than picked, so one stale capture cannot flip the reference's sign. What
   matters is not the raw count of sign disagreements but those where `|ref| > 3`: books
   straddle zero on pick'em games, so -1.5 against +1.5 is normal and -14 against +14 is not.
2. **Against the realised margin.** `spread + (home_points - away_points)` cancels to ~0 when
   the spread is home-relative. An inverted book lands at roughly **twice** the mean spread
   instead, and its cover rate goes to ~0% or ~100%.

**Data:** local `cfb.duckdb`, `core.fact_game_line` 47,366 rows, 2013–2026; graded games
only for check 2.

## Result: all 17 books are home-relative

| provider | rows | opp. sign, `|ref|>3` | mean&nbsp;\|diff\| | cover % | mean resid |
|---|---|---|---|---|---|
| consensus | 8,537 | 4 | 0.47 | 48.2 | −0.26 |
| teamrankings | 7,380 | 3 | 0.55 | 48.3 | −0.34 |
| numberfire | 5,918 | 7 | 0.75 | 48.1 | −0.22 |
| bovada | 5,301 | 4 | 0.24 | 49.5 | 0.11 |
| caesars | 3,754 | 3 | 0.50 | 49.8 | 0.60 |
| espn bet | 3,549 | 0 | 0.17 | 50.5 | 0.70 |
| draftkings | 2,752 | 4 | 0.64 | 50.0 | 0.69 |
| william hill (new jersey) | 2,663 | 1 | 0.24 | 48.3 | −0.33 |
| **circa** | 1,871 | **33** | **2.46** | 51.7 | 1.18 |
| **fanduel** | 1,869 | 0 | 0.47 | 50.8 | 1.02 |
| **betmgm** | 1,832 | 0 | 0.47 | 51.5 | 1.03 |
| **bet365** | 381 | 1 | 0.55 | 48.2 | 0.21 |
| **pinnacle** | 110 | 1 | 0.68 | 48.3 | 1.04 |
| sugarhouse | 94 | 0 | 0.57 | 45.7 | −1.31 |
| caesars sportsbook (colorado) | 49 | 0 | 0.55 | 55.5 | 2.46 |

Bold are the five the union added. **No book is inverted.** Every cover rate sits in 45–56%
and every residual within ±2.5 of zero. An inversion would put the cover rate near 0 or 100
and the residual near ±20 — nothing is remotely close.

### Circa is noisier, and it is not a sign problem

Circa disagrees on sign with the reference in 33 rows where `|ref| > 3` — 1.8% of its rows,
against roughly 0.1% for every other book — and its mean absolute difference is 2.46 against
~0.5 elsewhere. That is a real outlier and worth naming.

It is not an inversion. An inverted book disagrees ~100% of the time, not 1.8%, and Circa's
cover rate (51.7%) and residual (1.18) are unremarkable. The likelier explanations are that
Circa posts early and moves independently — it is a sharp, low-limit book whose number is
often the first one up — or that its AN captures are timestamped further from kickoff than
the reference books'. Neither is settled here, and neither calls for negation.

## What changed

Nothing in the data. The rows were already correct; what was missing was any check saying so.
`scripts/audit_line_sign_convention.py` is that check, and `tests/test_core_merges.py` pins
the verdict three ways: no book's residual outside ±5, no book's cover rate outside 25–75%,
and the five ActionNetwork books present in the graded set at all — so the first two cannot
pass vacuously if those books stop arriving.

The bounds are deliberately loose. They exist to catch a sign flip, not to police how sharp a
book is; tightening them would make the suite fail on a quiet week rather than on a defect.

## What this does not support

- **It does not validate the spread *values*.** Only their orientation. A book could be
  systematically two points off and pass every check here.
- **It does not explain Circa.** Two hypotheses are offered and neither is tested. If Circa's
  numbers are used for anything sensitive, the capture timestamps are the thing to look at.
- **It says nothing about `spread_open`.** Only `spread_close` is graded, because the
  reference and the margin are both close-side. An inverted *open* on one book would survive
  this entirely.
- **Totals and moneylines are unchecked.** Totals have no sign to get wrong, but the
  moneylines the AN tape brought in (29–33 per book) are unvalidated for home/away
  orientation, which is the same class of silent defect. Not tracked separately — it is a
  narrower version of this question and the same script would answer it.
- **`caesars sportsbook (colorado)` at 2.46 and `sugarhouse` at −1.31 are small samples**
  (49 and 94 rows). Their residuals are noise, not evidence of anything.
