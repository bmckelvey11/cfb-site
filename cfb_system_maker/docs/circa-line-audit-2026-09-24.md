# `circa` on the line tape: the consensus opener, not Circa — 2026-09-24

**Question.** The matchup page (branch `feat/matchup-page`) shows `circa` next to `pinnacle`
as a sharp reference. On 401869941 (2026 wk 4, Liberty @ Coastal Carolina) `circa` closes
Coastal −1.5 while every book closes +2.5; on 401757282 (2025 wk 8) it is −7.5 against −10.5
to −12.0. Every `circa` row is `_source = 'gql'` with `spread_open` NULL. Is it a stale opener
or an early snapshot? Is it ever flipped home/away? How far off is it, and is it worse far from
kickoff? Can it serve as a sharp close?

**Verdict.** `circa` is **not a sportsbook**. It is Action Network's book id 30, which is the
consensus **opener**. The loader labels it "Circa". It never updates, so it is useless as a
close. Drop it from `SHARP_BOOKS`. The same mislabelling also covers `pinnacle`, so the page's
sharp panel currently shows no sharp book at all.

**Method.** `python scripts/audit_an_book_labels.py` opens `cfb.duckdb` read-only. It compares:

- `core.fact_game_line` and the 2026 AN tick tape (`stg.an_history_tick`)
- the-odds-api pulls (`core.fact_game_odds`, from 2026-09-09)
- oddspapi Pinnacle snapshots (`data/ingest/oddspapi/`, 14 pulls, 2026-09-09 to 09-23)

Seasons covered are 2024–2026. The book-identity test (§4) is 2026 only, because the tick
tape starts 2026-04-02. Warehouse as rebuilt 2026-09-24 00:46.

## Where `circa` comes from

`duckdb_load._AN_PROVIDER_NAMES` maps AN book 30 to "Circa", as id 9000030. From there:

1. `backfill_gamelines_from_actionnetwork` writes the AN book's current offering into
   `stg.game_lines` (`line_source = 'actionnetwork'`, no opener column).
2. `duckdb_core._merge_game_lines` unions it into `core.fact_game_line` as `_source = 'gql'`.

The name is wrong. Circa's line never reaches the warehouse. `pull_oddspapi.py` accepts
`circasports`, but no Circa snapshot has ever been pulled.

## Findings

**1. A stale opener, not an early snapshot.** On 2026 games, the `circa` value equals AN's
consensus opener (book 15's first tick, `line_status = 'opener'`) on 99.1% of 322 games, and is
within 0.5 on 99.4%. It equals the consensus's last tick on only 17.4%.

For 401869941 the tape shows the cause:
- The consensus opened Coastal −1.5 at 2026-09-20 03:09 and moved through +1.5 to +2.5.
- Book 30's offering still reads −1.5, and its moneyline (−118/−102) is the opener's.

For 2024–25 there is no tick tape. The weaker check is CFBD's per-book REST openers: `circa`
equals DraftKings' REST open on 42–47% of games, but its REST close on only 7–24%.

A subtlety in the tape: book 30's `history[]` is a copy of book 15's (10,843 of 10,843 ticks
identical at the same instant). So on the tick tape, 30 looks like the live consensus. Only the
offering's own value (the one the loader keeps) is frozen at the open.

**2. Not flipped.** With the close median at 3 or more points, `circa` equals the mirrored close
on 1, 2 and 2 games in 2024–26 (of 744 / 757 / 302). It equals the mirrored REST opener on 1,
1 and 0. The sign disagreements (22 / 15 / 4 at |close| ≥ 3) are openers that moved through
zero; the 2026 ones match the consensus opener. Against realised margins,
`scripts/audit_line_sign_convention.py` gives `circa` a mean residual of +1.16 and 51.6% home
cover. An inverted book lands near twice the mean spread and a cover rate near 0 or 100%.
Home-relative throughout.

**3. How far off.** Gap from the leave-one-out median of the other books' closes:

| | 2024 | 2025 | 2026 |
|---|---|---|---|
| `circa` mean abs gap | 2.79 | 2.11 | 2.03 |
| `circa` within 0.5 | 16% | 29% | 26% |
| other AN-tape books, mean abs gap | 0.24–0.35 | 0.26–0.30 | 0.19–0.42 |

The gap does not grow for games far from kickoff. By week of season it is flat: 2.55 / 2.47 /
2.68 / 2.06 for weeks 0–1 / 2–4 / 5–8 / 9+. By how long before kickoff the 2026 line opened,
it is not monotonic: 1.96 under 7 days, 2.09 at 7–14, 2.60 at 14–60, 1.65 at 60+ (n = 145 /
62 / 53 / 61). The gap is simply the open-to-close move, whatever its size.

**4. The other AN labels are wrong too.** Each AN id's line in effect at each reference pull
was matched on line **and** price. The true book is the one that matches:

| AN id | Loader's label → `provider_key` | Exact match | Is |
|---|---|---|---|
| 68 | FanDuel → `fanduel` | DraftKings 0.99 | **DraftKings** |
| 69 | BetMGM → `betmgm` | FanDuel 0.96 | **FanDuel** |
| 75 | Bet365 → `bet365` | BetMGM 0.95 | **BetMGM** |
| 71 | → CFBD 38 → `caesars` | BetRivers 0.88 | **BetRivers** |
| 49 | Pinnacle → `pinnacle` | real Pinnacle 0.05 (line only 0.61); no reference above 0.15 | **not Pinnacle** |
| 15 | → CFBD 888888 → `draftkings` | no book above 0.45 | AN consensus |
| 30 | Circa → `circa` | see §1 | consensus opener |

675 Pinnacle pulls and 2,283–3,922 pulls per odds-api book, over 159–222 events.

These results agree with AN's own `/web/v1/books` list, recorded in
[research/spread/docs/README.md](../../research/spread/docs/README.md) on 2026-09-08. That list
calls 49 "Caesars NV". No Caesars feed is on disk to confirm it, so this doc claims only
"not Pinnacle". The correction already exists as commit `ea9aedc` on the unmerged branch
`claude/epic-elbakyan-c814f2`; master never took it.

**Blast radius in `core.fact_game_line`, 2024+.** Every row below is AN-tape
(`line_source = 'actionnetwork'`):

- `circa`: 2,082 rows.
- `fanduel`: 2,082 rows, really DraftKings.
- `betmgm`: 2,037 rows, really FanDuel.
- `bet365`: 598 rows, really BetMGM.
- `caesars`: 2,053 rows, really BetRivers. This is the book the spread session guide caught
  mis-posting by 10–25 points.
- `pinnacle`: 222 rows, not Pinnacle.
- `draftkings`: 269 AN-only rows that are the consensus. A further 1,813 `cfbd+an` rows had
  CFBD nulls filled from the consensus.

[line-coverage-2026-09-16.md](line-coverage-2026-09-16.md) counted these under the loader's
names, so its "sharp books start in 2024" inherits the error. It is a dated record and is left
as written.

## What this does not support

- It says nothing about Circa's or Pinnacle's real lines. Neither is in the warehouse.
- "49 is Caesars" rests on AN's list alone. The data shows only that it is not Pinnacle.
- The 2024–25 opener claim is inferred from 2026 plus the weaker REST-opener check. There is no
  2024–25 tick tape.
- It does not show that a relabel changes any published model result. Nothing that reads these
  rows was re-run.

## Recommendation

- **Matchup page:**
  - Drop `circa` from `SHARP_BOOKS`.
  - Drop `pinnacle` too while it is AN 49. The page then has no sharp close before 2026-09-09.
    From 2026-09-09 the oddspapi snapshots are a real Pinnacle source.
  - Until the loader is fixed:
    - The `other_books` panel shows `betmgm`, `bet365` and `caesars` under the wrong names.
    - The fallback close for `fanduel` in `_main_books` (games before 2026-09-09) is really
      DraftKings.
    - The live DK/FD panel reads `core.fact_game_odds` and is correct.
- **Loader:** not changed here. `ea9aedc` does not cherry-pick cleanly. Master has since moved
  AN ids into the `_AN_ID_OFFSET` range (`7e89d011`), and `tests/test_duckdb_load.py` pins the
  current names. A relabel also renames `provider_key` values that downstream readers select
  on, the matchup page among them.
