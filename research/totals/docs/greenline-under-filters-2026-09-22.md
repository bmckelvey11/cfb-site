# Situational filters on Greenline unders, 2026-09-22

Reproduce: `python research/totals/scripts/under_filters.py --out research/totals/docs`.

**Supersedes** [greenline-under-filters-2026-09-17.md](../../../archive/docs/greenline-under-filters-2026-09-17.md), which pooled the 2023-25 personal unders with the 2026 flags on the premise that they were mostly the same picks -- a premise `pool_totals_record.overlap()` later measured and found false on 3 of 12 checkable days.

## Question

Does any pre-registered, pregame situational filter separate winning Greenline unders from losing ones?
Runs on the 270 Greenline-only unders across all three graded eras, stratified by era via
Cochran-Mantel-Haenszel so a filter that is really era composition (2020 has no weather rows, 2026 sits
on different totals) cancels here instead of reporting itself as a finding.

## Data

- 2020 PFF_hist: 122 graded unders.
- 2022-23 exports: 57 graded unders.
- 2026 flags: 88 graded unders.
- 3 of the pooled 270 graded Greenline unders (all 2020 PFF_hist) carry a result but no CFBD `game_id` -- their final came with the archive row directly rather than through a CFBD join -- so they cannot be joined to a feature and are excluded here, not miscounted.

- Pooled: 144-123 (53.9%, 95% Wilson 48–60%). MDE for the whole pool: 60.0%. Break-even 52.38%.
- Features from the local warehouse: `core.fact_game_line` (open/close), `stg.weather` (wind, indoors),
  `stg.advanced_game_stats` (plays, season-to-date before kickoff, 2022+ only), `core.fact_game`
  (spread, kickoff, rest). A row missing a feature is dropped from that filter only; the count is in
  the table.

## Filters, fixed before running

| filter | rule |
|---|---|
| line_fell | total closed below open |
| windy | wind >= 12 mph outdoors |
| slow | both teams below FBS mean pace |
| big_fav | |spread| >= 14 |
| night | kickoff >= 19:00 ET |
| short_rest | either team <= 6 days rest |

## Records: filter on vs off, by era

| filter | era | on | off | Fisher p |
|---|---|---|---|---:|
| line_fell | 2020 PFF_hist | -- | -- | nan |
| line_fell | 2022-23 exports | 11-1 (92%, 65–99%) | 3-3 (50%, 19–81%) | 0.083 |
| line_fell | 2026 flags | 23-21 (52%, 38–66%) | 19-17 (53%, 37–68%) | 1.000 |
| line_fell | pooled (descriptive) | 34-22 (61%, 48–72%) | 22-20 (52%, 38–67%) | 0.419 |
| windy | 2020 PFF_hist | 12-8 (60%, 39–78%) | 53-47 (53%, 43–62%) | 0.629 |
| windy | 2022-23 exports | 6-2 (75%, 41–93%) | 24-24 (50%, 36–64%) | 0.263 |
| windy | 2026 flags | 3-2 (60%, 23–88%) | 43-40 (52%, 41–62%) | 1.000 |
| windy | pooled (descriptive) | 21-12 (64%, 47–78%) | 120-111 (52%, 46–58%) | 0.264 |
| slow | 2020 PFF_hist | -- | -- | nan |
| slow | 2022-23 exports | 1-1 (50%, 9–91%) | 30-25 (55%, 42–67%) | 1.000 |
| slow | 2026 flags | 6-4 (60%, 31–83%) | 40-38 (51%, 40–62%) | 0.742 |
| slow | pooled (descriptive) | 7-5 (58%, 32–81%) | 70-63 (53%, 44–61%) | 0.770 |
| big_fav | 2020 PFF_hist | 22-20 (52%, 38–67%) | 45-35 (56%, 45–67%) | 0.706 |
| big_fav | 2022-23 exports | 5-9 (36%, 16–61%) | 26-17 (60%, 46–74%) | 0.131 |
| big_fav | 2026 flags | 18-21 (46%, 32–61%) | 28-21 (57%, 43–70%) | 0.391 |
| big_fav | pooled (descriptive) | 45-50 (47%, 38–57%) | 99-73 (58%, 50–65%) | 0.124 |
| night | 2020 PFF_hist | 27-24 (53%, 40–66%) | 40-31 (56%, 45–67%) | 0.717 |
| night | 2022-23 exports | 16-10 (62%, 43–78%) | 15-16 (48%, 32–65%) | 0.425 |
| night | 2026 flags | 24-18 (57%, 42–71%) | 22-24 (48%, 34–62%) | 0.402 |
| night | pooled (descriptive) | 67-52 (56%, 47–65%) | 77-71 (52%, 44–60%) | 0.537 |
| short_rest | 2020 PFF_hist | 6-6 (50%, 25–75%) | 49-41 (54%, 44–64%) | 1.000 |
| short_rest | 2022-23 exports | 2-3 (40%, 12–77%) | 29-23 (56%, 42–68%) | 0.651 |
| short_rest | 2026 flags | 6-1 (86%, 49–97%) | 40-41 (49%, 39–60%) | 0.113 |
| short_rest | pooled (descriptive) | 14-10 (58%, 39–76%) | 118-105 (53%, 46–59%) | 0.671 |

## Era-stratified test

Cochran-Mantel-Haenszel across the three eras -- the pooled Fisher p above is descriptive only; this
is the inferential test, because it cancels a split that is really era composition instead of reporting
it as a finding. Holm corrects across the six filters. `MDE on` is the smallest win rate the filter's
kept rows could distinguish from break-even at their own pooled n.

| filter | n tagged | missing | CMH stat | CMH p | Holm p | MDE on |
|---|---:|---:|---:|---:|---:|---:|
| line_fell | 98 | 169 | 0.20 | 0.656 | 1.000 | 69% |
| windy | 264 | 3 | 1.08 | 0.299 | 1.000 | 74% |
| slow | 145 | 122 | 0.01 | 0.911 | 1.000 | 88% |
| big_fav | 267 | 0 | 2.06 | 0.151 | 0.906 | 65% |
| night | 267 | 0 | 0.35 | 0.555 | 1.000 | 64% |
| short_rest | 247 | 20 | 0.08 | 0.780 | 1.000 | 78% |

## Reading

- No filter survives the Holm correction at 5%. None of the six is a rule yet.
- Strongest era-stratified split is `big_fav` (CMH p 0.151, Holm 0.906): pooled on 45-50 (47%, 38–57%) vs off 99-73 (58%, 50–65%).
- Per-era rows are printed above precisely so a filter that only shows up in one era (a selection
  artifact or a feature-coverage gap) is visible before the CMH line averages it away.

## What this does not support

- Applying any filter to a live slate. Six looks at 270 rows; the Holm column is the honest p.
- Reading a missing-feature filter (wind, pace) as null on 2020: `stg.weather` and
  `stg.advanced_game_stats` do not cover that era, so those rows are dropped, not zero.
- Treating any era as out-of-sample for the others. All three are graded Greenline flags; none was
  selected by these filters.

## What settles it

- Rerun after each graded 2026 week; it is the era that keeps growing.
- A filter that holds: consistent sign across eras (see the per-era table), CMH p Holm < 0.05.
