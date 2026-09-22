# Greenline archive: auditing the CFBD joins and the pick flag

2026-09-21

## Question

`greenline_history_archive.csv` is the parsed pre-2026 PFF archive, and
[`greenline-archive-2026-09-17.md`](greenline-archive-2026-09-17.md) already grades the
368 picks in it. This is a different question about the same file: **is the file safe to
query?** Specifically — does every `game_id` point at the game the row actually describes,
and does a naive filter on `is_greenline_pick` return the picks?

Two answers: one trap that will bite the next query written against this file, and two
rows joined to the wrong game.

## Data

`$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_history_archive.csv`, 8,772 rows, written
by [`parse_greenline_history.py`](../scripts/parse_greenline_history.py). Joined against
`core.fact_game` in the local warehouse. Audit script:
[`audit_archive_joins.py`](../scripts/audit_archive_joins.py).

No grading is redone here. The record in the 2026-09-17 doc stands as written; this audit
does not re-score it and does not report a hit rate or an ROI.

## Finding 1 — `is_greenline_pick` is replicated across all three snapshots

Every 2020 game/market appears three times — `open_market`, `open_greenline`, `close` —
and the pick flag is copied onto all three. So:

| filter | rows |
| --- | --- |
| `WHERE is_greenline_pick` | **1,104** |
| `WHERE is_greenline_pick AND snapshot = 'open_greenline'` | **368** |

368 is the pick count. 1,104 is the same 368 picks counted once per snapshot. A filter
that omits the snapshot predicate triples the sample, and because the three snapshots
carry *different lines* for the same pick, the triplicate is not even a clean 3× — it
silently mixes the opening market number, the opening Greenline number, and the close into
one pool.

**Any query against this file must filter `snapshot = 'open_greenline'` to select picks.**
That is also the snapshot the parser derives the flag from, per its no-lookahead rule.

Related shape notes, for the same reason:

- `is_greenline_pick` was **NULL on all 1,020 export rows** (the 2022–23
  `ncaa-best-bets*.csv` slates) although they carry `difference`. Picks were derivable
  there and simply never derived. **Now derived — 220 picks** (see the fix section);
  18 rows keep a NULL flag because their `difference` is NULL.
- 144 `PFF_hist` rows (16 slots × 3 markets × 3 snapshots) have NULL `cover_prob`, so no
  `difference` and no flag. Source holes, not parser holes.
- 6 rows (SMU @ UCF, 2022-10-02) have NULL `season` **and** NULL `week`. Any
  `GROUP BY season` drops them silently. The 2026-09-17 doc discloses this game as
  unmatched; the null season is the part that bites.

## Finding 2 — two slots are joined to the wrong CFBD game

`match_by_name` in the parser matches schools with `strong()` from
[`match_greenline_books.py`](../scripts/match_greenline_books.py), which returns true on
**any shared non-weak token**:

```
{eastern, kentucky} ∩ {western, kentucky} = {kentucky}   → strong() is True
{north, texas, mean, green} ∩ {texas}     = {texas}      → strong() is True
```

The week-scoped pass is orientation-sensitive (home must match home). When PFF's home/away
disagrees with CFBD's, that pass returns nothing and the code falls back to a season-wide
search. The fallback then finds *exactly one* token-sharing candidate, `len(best) == 1`
passes, and the wrong game is locked in without a warning. The parser's docstring claims
the fallback is safe because "a rematch would show up as >1 candidate and stay unmatched"
— that holds only if candidates are matched exactly, not by shared token.

| archive says | joined to | should be | rows | picks |
| --- | --- | --- | --- | --- |
| wk 1, Marshall @ Eastern Kentucky, 0–59 | `401207146` = Marshall @ Western Kentucky, wk 6 | `401237353` = Eastern Kentucky @ Marshall, wk 1 | 18 | 0 |
| wk 15, UTEP @ North Texas, 43–45 | `401236222` = UTEP @ Texas, wk 2 | `401257816` = North Texas @ UTEP, wk 15 | 18 | 3 |

Neither correct game id appears anywhere in the file. `401236222` ends up carrying two
different matchups (its own week-2 game plus the week-15 rows), which is the only reason
the defect is visible to a duplicate-id scan at all.

**Each bad slot has PFF's orientation flipped relative to the true game, and zero of the
624 correctly-joined slots have a flipped orientation.** That is the mechanism confirmed
empirically rather than only read off the source: the flip is what makes the week-scoped
pass miss, and the weak-token fallback is what converts a miss into a wrong answer.

On the underlying vendor data, the two behave differently and should not be pooled:

- **Marshall / Eastern Kentucky**: PFF's team→score pairing is **wrong**. It has Marshall
  scoring 0; Marshall won 59–0. The source settles where the swap comes from — `PFF_hist`
  itself labels the host Eastern Kentucky while booking the home score, the −3000 moneyline
  and the −23.5 spread, all of which are Marshall's. Two name columns transposed in the
  vendor file; every number is right. Fixed below.
- **UTEP / North Texas**: PFF's team→score pairing is **right** (UTEP 43, North Texas 45).
  Only the home/away designation disagrees with CFBD. 2020 had relocations, so PFF is not
  necessarily the wrong one about the venue.

## Method

Two detectors were tried and both are incomplete:

- **Duplicate `game_id`** catches only a wrong match that collides with another slot.
- **Token overlap between archive and CFBD names** flags 24 slots, all of which are
  correct joins with naming variants (`Louisiana-Monroe`/`UL Monroe`,
  `Mississippi`/`Ole Miss`, `Hawaii`/`Hawai'i`). It also *misses* both real defects,
  because both share a token with the game they were wrongly matched to.

**Score consistency is the complete test.** The final scores in the archive come from PFF
(`Game|Home Score` / `Game|Away Score`), independently of the join, so they can referee it:
a slot whose points cannot be reconciled with its joined CFBD game's points — in either
orientation — is matched to the wrong game. Run over all 626 slots that carried a `game_id`
and a final score before the fix, it returned exactly the two above and nothing else.

Six week-number disagreements survive as legitimate: LSU@Florida, Louisville@Virginia,
Air Force@Army, Georgia@Missouri, Minnesota@Wisconsin are 2020 COVID reschedules where
names and scores agree, and PFF's weeks 17–18 are the postseason CFBD restarts at 1.

## What this does not support

- **This is not a re-grade.** The 2026-09-17 record is unchanged and is not re-scored here.
- **The 220 export picks are flags, not a record.** The source carries no result, so all
  220 are ungraded and none of them can be added to any win rate, ROI or CLV figure. They
  say what Greenline flagged on three 2022–23 slates, nothing about whether it won.
- **The defect is latent, not live.** [`greenline_archive_review.py`](../scripts/greenline_archive_review.py)
  never reads `game_id` — it grades off PFF's own `bet_result` — and no other script in the
  repo reads this file. So nothing published today is wrong because of Finding 2. It is a
  trap for the next analysis that joins this file to the warehouse, which is exactly what
  a spread-sign or margin check would do.
- **Three of 368 picks** sit on a wrong game id, all in the UTEP/North Texas slot. That is
  0.8% of picks and would not move a result that was already below its detection floor.
- **The audit gates two defect classes, not one.** Score consistency catches a wrong
  game; `transposed()` catches right-game-wrong-labels. A third class — PFF and CFBD
  disagreeing about the venue with everything else self-consistent — is reported and
  allowed, not failed.
- **Finding 1 is a usage trap, not a defect.** The replication is deliberate — the parser
  carries one flag per bet onto all three snapshots "so a snapshot filter never changes
  the pick set". It was left as-is. Finding 2 and the transposed game were fixed.

## Fix — landed 2026-09-21

Finding 2 fixed in [`parse_greenline_history.py`](../scripts/parse_greenline_history.py);
the archive was re-parsed from the OneDrive sources and now passes the audit.

Two changes, both scoped to this parser so the 2026 pipeline's `strong()` is untouched:

1. **`same_school()`** replaces the bare `strong()` name test. A shared strong token is
   now necessary but not sufficient — a `QUALIFIERS` token held by one name and not the
   other means a different school. The set is empirical, not a rule: `north`/`northern`/
   `south`/`southern`/`east`/`eastern`/`west`/`western`/`central`/`state`/`tech`/`monroe`/
   `m`, where every entry closes a mismatch the audit actually caught. `tech` and `m` were
   added on the second pass, after the orientation search reached Louisiana for
   "Louisiana Tech Bulldogs".
2. **Each scope tries the orientation flip before the next one widens.** A flipped row no
   longer skips its own week and falls through to a season-wide search that can return one
   wrong game. Flips are printed, not silent.

One alias added in `match_greenline_books.py`: `army west point` → `army`. "West" there is
the academy's name, and the new qualifier rule would otherwise have unmatched Army.

3. **`transposed_name_slots()`** repairs the one game whose team-name columns contradict
   its own scores (below).
4. **`is_greenline_pick` is now derived on the export rows too** (below).

Effect on the file — 8,772 rows and 368 picks unchanged, and the only columns that move
are `game_id`, its derived `kickoff_utc` (162 rows, the re-matched slots) and the two
team-name columns (18 rows, one game):

| | slots |
| --- | --- |
| corrected (Marshall/Eastern Kentucky, UTEP/North Texas) | 2 |
| newly matched, previously unmatched | 9 |
| lost | 0 |

`game_id` coverage rises from 8,328 to 8,454 rows. The audit now reports 0 wrong games
and 0 transposed names over 635 slots, and 3 surviving orientation flips (San José State
×2, UTEP/North Texas) — same game, PFF and CFBD disagreeing about who hosted, which is
allowed and left as PFF wrote it.

### The transposed game

`PFF_hist.xlsx` labels the week-1 Marshall game **Marshall @ Eastern Kentucky** while
every number on the row is in true home/away order:

| PFF column | value | whose |
| --- | --- | --- |
| `Home Score` | 59 | Marshall |
| home moneyline | −3000 | Marshall (FBS over an FCS visitor) |
| home spread | −23.5 | Marshall |

So only the two name columns are wrong, and the archive was asserting Marshall scored 0.
The parser now swaps the labels back and leaves every number alone. CFBD referees, and
only where it is unambiguous: the names must point one way, the scores the other, and a
tie is not decidable. Across all 635 slots this fires exactly once.

The score check in the audit cannot see this — the points agree with CFBD positionally —
so `transposed()` was added to the audit as a second detector, name-aware and using the
parser's aliases. Compared with raw tokens it would drown in false positives: Ole Miss /
Mississippi, UL Monroe / Louisiana-Monroe and Hawai'i / Hawaii all fail a naive match.

### Deriving the export picks

The 2022–23 slates carry PFF's per-side `Value` but were never turned into a pick flag.
The same `difference > 0` rule PFF_hist uses applies, and it was verified on these files
rather than assumed — the two properties that make the rule unambiguous both hold:

| property | PFF_hist 2020 | exports 2022–23 |
| --- | --- | --- |
| complete pairs sum to −overround (−0.0476 at −110/−110) | mean −0.0459, median −0.0480 | mean −0.0460, median −0.0465 |
| pairs inside [−0.09, −0.01] | 98.1% | **501 of 501** |
| pairs with two positive sides | 0 of 1,292 | **0 of 510** |

So `> 0` selects at most one side. That gives **220 export picks**:

| source | moneyline | spread | total |
| --- | --- | --- | --- |
| `ncaa-best-bets-pff.csv` (2022) | 23 | 26 | 30 |
| `ncaa-best-bets (1) - Copy…` (2023) | 21 | 21 | 28 |
| `ncaa-best-bets - Copy…` (2023) | 18 | 20 | 33 |

The remaining 18 export rows keep a NULL flag: their `difference` is NULL, so nothing is
derivable. 2020 is untouched at 368 picks.

Two things the rule does **not** decide:

- **`> 0`, not `>= 0`.** 20 export pairs have a best side of exactly 0.00, and
  `ncaa-best-bets-pff.csv` writes about half its values as whole-percent strings, so a
  0.00 there can hide either sign. Those pairs are treated as no-pick. PFF_hist has 19
  pairs in the same position and is treated identically, so the two eras stay comparable.
- **No lookahead question arises.** An export is a single pre-kickoff capture with no
  later snapshot to select on.

Not fixed, deliberately: the `is_greenline_pick` replication of Finding 1.

## Reproduce

```bash
python research/totals/scripts/parse_greenline_history.py
python research/totals/scripts/audit_archive_joins.py
```

Exits 1 while any slot fails, so it can gate a re-parse. `--self-check` runs the built-in
check that the predicate clears a correct join, clears a pure orientation flip, and fails a
wrong game.
