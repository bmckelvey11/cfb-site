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

- `is_greenline_pick` is **NULL on all 1,020 export rows** (the 2022–23
  `ncaa-best-bets*.csv` slates). Those rows do carry `difference`, and 220 of them are
  positive, so picks are derivable there — they were simply never derived. Treat the
  export slates as unflagged, not as zero picks.
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
  scoring 0; Marshall won 59–0. Swapping the two team-name columns reproduces CFBD exactly,
  so one swap explains it — but it cannot be told from here whether the swap is PFF's or
  the parser's column mapping.
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

**Score consistency is the complete test.** The final scores in the archive come from PFF,
independently of the join, so they can referee it: a slot whose points cannot be reconciled
with its joined CFBD game's points — in either orientation — is matched to the wrong game.
Run over all 626 slots that carry a `game_id` and a final score, it returns exactly the two
above and nothing else.

Six week-number disagreements survive as legitimate: LSU@Florida, Louisville@Virginia,
Air Force@Army, Georgia@Missouri, Minnesota@Wisconsin are 2020 COVID reschedules where
names and scores agree, and PFF's weeks 17–18 are the postseason CFBD restarts at 1.

## What this does not support

- **This is not a re-grade.** The 2026-09-17 record is unchanged and is not re-scored here.
- **The defect is latent, not live.** [`greenline_archive_review.py`](../scripts/greenline_archive_review.py)
  never reads `game_id` — it grades off PFF's own `bet_result` — and no other script in the
  repo reads this file. So nothing published today is wrong because of Finding 2. It is a
  trap for the next analysis that joins this file to the warehouse, which is exactly what
  a spread-sign or margin check would do.
- **Three of 368 picks** sit on a wrong game id, all in the UTEP/North Texas slot. That is
  0.8% of picks and would not move a result that was already below its detection floor.
- **The parser is not fixed here.** This audit was scoped to inspecting the file. The fix
  is to try the flipped orientation in the week-scoped pass before falling back, and to
  make the season-wide fallback reject a match whose only shared token drops a directional
  qualifier (`Eastern`/`Western`/`North`/`South`). Re-running the parser also requires the
  OneDrive sources, which are outside the repo.

## Reproduce

```bash
python research/totals/scripts/audit_archive_joins.py
```

Exits 1 while any slot fails, so it can gate a re-parse. `--self-check` runs the built-in
check that the predicate clears a correct join, clears a pure orientation flip, and fails a
wrong game.
