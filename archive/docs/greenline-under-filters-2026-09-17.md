**Superseded by** [greenline-under-filters-2026-09-22.md](../../research/totals/docs/greenline-under-filters-2026-09-22.md).
This run pooled the 2023-25 personal unders with the 2026 flags on the premise that they were
mostly the same picks. `pool_totals_record.overlap()` (2026-09-22) measured that premise for
the first time and found it false on 3 of 12 checkable days -- personal bets that took the side
Greenline flagged *against*. The rerun uses the 270 Greenline-only unders across all three eras
instead, stratified by era via CMH. Its strongest candidate here, `big_fav` (pooled Fisher p
0.043, Holm 0.256), weakens to CMH p 0.151, Holm 0.906 on the corrected population.

# Situational filters on Greenline unders, 2026-09-17

Reproduce: `python research/totals/scripts/under_filters.py --out research/totals/docs`.

## Question

Does any pre-registered, pregame situational filter separate winning Greenline unders from losing ones?
The 2023-25 personal unders are treated as Greenline unders and pooled with the graded 2026 flags,
kept as strata so a population difference cannot pass as a filter effect.

## Data

- History 2023-25: 200 bet unders matched to `core.fact_game` (`data/ingest/bet_history/history.csv`).
- 2026 flags: 39 graded under flags matched through `pff_franchise.cfbd_team_id`.
- Pooled: 136-103 (56.9%, 95% Wilson 51–63%). MDE for the whole pool: 60.4%. Break-even 52.38%.
- Features from the local warehouse: `core.fact_game_line` (open/close), `stg.weather` (wind, indoors),
  `stg.advanced_game_stats` (plays, season-to-date before kickoff), `core.fact_game` (spread, kickoff, rest).
  A row missing a feature is dropped from that filter only; the count is in the table.

## Filters, fixed before running

| filter | rule |
|---|---|
| line_fell | total closed below open |
| windy | wind >= 12 mph outdoors |
| slow | both teams below FBS mean pace |
| big_fav | |spread| >= 14 |
| night | kickoff >= 19:00 ET |
| short_rest | either team <= 6 days rest |

## Records: filter on vs off

| filter | stratum | on | off | Fisher p |
|---|---|---|---|---:|
| line_fell | history | 22-18 (55%, 40–69%) | 31-19 (62%, 48–74%) | 0.525 |
| line_fell | 2026 | 12-7 (63%, 41–81%) | 6-7 (46%, 23–71%) | 0.473 |
| line_fell | pooled | 34-25 (58%, 45–69%) | 37-26 (59%, 46–70%) | 1.000 |
| windy | history | 13-11 (54%, 35–72%) | 97-72 (57%, 50–65%) | 0.827 |
| windy | 2026 | -- | -- | nan |
| windy | pooled | 13-11 (54%, 35–72%) | 97-72 (57%, 50–65%) | 0.827 |
| slow | history | 13-10 (57%, 37–74%) | 101-76 (57%, 50–64%) | 1.000 |
| slow | 2026 | 3-0 (100%, 44–100%) | 19-17 (53%, 37–68%) | 0.243 |
| slow | pooled | 16-10 (62%, 43–78%) | 120-93 (56%, 50–63%) | 0.679 |
| big_fav | history | 25-28 (47%, 34–60%) | 89-58 (61%, 52–68%) | 0.107 |
| big_fav | 2026 | 6-8 (43%, 21–67%) | 16-9 (64%, 45–80%) | 0.314 |
| big_fav | pooled | 31-36 (46%, 35–58%) | 105-67 (61%, 54–68%) | 0.043 |
| night | history | 41-37 (53%, 42–63%) | 73-49 (60%, 51–68%) | 0.380 |
| night | 2026 | 9-9 (50%, 29–71%) | 13-8 (62%, 41–79%) | 0.528 |
| night | pooled | 50-46 (52%, 42–62%) | 86-57 (60%, 52–68%) | 0.233 |
| short_rest | history | 9-6 (60%, 36–80%) | 93-67 (58%, 50–65%) | 1.000 |
| short_rest | 2026 | 4-0 (100%, 51–100%) | 18-17 (51%, 36–67%) | 0.118 |
| short_rest | pooled | 13-6 (68%, 46–85%) | 111-84 (57%, 50–64%) | 0.466 |

## Pooled test with the strata inside it

Logistic: win ~ filter + source + filter×source, SE clustered by calendar day. `b_filter` is the
log-odds shift the filter gives in the history stratum; `b_inter` is how much that shift differs in 2026.
A filter whose interaction is large and opposite-signed is a population difference, not a filter.
`sep` means a filter×source cell had no losses (or no rows), so the interaction is not identified
and the fit is filter + source only.
Holm corrects the pooled Fisher p across the six filters. `MDE on` is the smallest win rate the
filter's kept rows could distinguish from break-even at their own n.

| filter | n tagged | missing | b_filter ± se | p | b_inter ± se | p_inter | Fisher p (pooled) | Holm p | MDE on |
|---|---:|---:|---|---:|---|---:|---:|---:|---:|
| line_fell | 122 | 117 | -0.29 ± 0.38 | 0.450 | +0.98 ± 0.43 | 0.024 | 1.000 | 1.000 | 69% |
| windy | 193 | 46 | -0.13 ± 0.51 | 0.799 | sep | -- | 0.827 | 1.000 | 78% |
| slow | 239 | 0 | +0.21 ± 0.49 | 0.663 | sep | -- | 0.679 | 1.000 | 77% |
| big_fav | 239 | 0 | -0.54 ± 0.29 | 0.063 | -0.32 ± 0.33 | 0.333 | 0.043 | 0.256 | 68% |
| night | 239 | 0 | -0.30 ± 0.27 | 0.277 | -0.19 ± 0.32 | 0.548 | 0.233 | 1.000 | 65% |
| short_rest | 214 | 25 | +0.50 ± 0.62 | 0.423 | sep | -- | 0.466 | 1.000 | 81% |

## Reading

- No filter survives the Holm correction at 5%. None of the six is a rule yet.
- Strongest raw split is `big_fav` (pooled Fisher p 0.043, Holm 0.256): on 31-36 (46%, 35–58%) vs off 105-67 (61%, 54–68%).
- The strata differ in population (history is a high-total selection, 2026 flags sit six points
  lower), so a filter that only shows in one stratum is a selection artifact until the other confirms it.

Hand notes on this run (2026-09-17):

- `big_fav` is the only filter with the same sign in both strata (history 47% vs 61%, 2026 43% vs 64%)
  and a flat interaction (p 0.33). Direction: unders on 14+ point favorites lose. Holm p 0.256, so it
  is a hypothesis for the 2026 confirmation set, not a rule. Mechanism is plausible (garbage-time
  scoring and backups on both sides make big-favorite totals noisier), which is why it was pre-registered.
- `line_fell` flips sign between strata (history 55% vs 62%, 2026 63% vs 46%; interaction p 0.024).
  That is the population difference the design was built to catch. Also 117 rows have no open total,
  so the tagged set is half the pool. Not a filter.
- `windy`, `slow`, `short_rest` carry 3-0 / 4-0 cells in 2026 and no 2026 weather rows at all
  (`stg.weather` has 168 of 755 2026 games). Unreadable until the weather load catches up.

## What this does not support

- Applying any filter to a live slate. Six looks at ~240 rows; the Holm column is the honest p.
- Reading a missing-feature filter (wind, pace) as null: 2026 weather coverage is a fifth of games,
  so those rows are mostly history.
- Treating history as out-of-sample. It was not selected by these filters, but it was selected by
  a high-total rule that correlates with several of them (pace, big favorites).

## What settles it

- Rerun after each graded week. The 2026 stratum is the confirmation set; at ~150 2026 unders a
  filter needs ~64% on its kept half to clear floor on 2026 alone.
- A filter that holds: same sign in both strata, interaction p > 0.10, Holm p < 0.05.
