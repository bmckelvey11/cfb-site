# Greenline's 2022-23 export picks, graded against CFBD finals

2026-09-21

## Question

[`greenline-archive-join-audit-2026-09-21.md`](greenline-archive-join-audit-2026-09-21.md)
derived 220 picks on the three `ncaa-best-bets*.csv` slates that had never carried a pick
flag. The source has no result column. Graded against final scores, what is their record —
and does it mean anything?

Short answer: **80-73 on spread and total combined, which is the assumed break-even to
within a tenth of a point, and far below the floor this sample could detect.** The
moneyline picks cannot be judged at all.

## Data

`$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_history_archive.csv`, `snapshot = 'export'`
and `is_greenline_pick`. Three slates: 2022-09-30→10-02, 2023-10-17→22, 2023-11-02→05.
Finals from `core.fact_game`. Graded by
[`grade_export_picks.py`](../scripts/grade_export_picks.py).

220 picks, **217 graded**, 128 distinct games. The 3 ungraded are the SMU @ UCF slot of
2022-10-02, which never matched a CFBD game (no kickoff within ±6h) and so has no final.

Graded **at the line in the capture**, per the unit's standing rule — the export's own
number, not a close and not a book's.

## What this cannot be, and why there is no ROI

**The exports carry no price.** `breakeven_prob` is NULL on every export row, so the price
each pick was offered at is not reconstructible at decision time. Executable prices are an
integrity gate in [`model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md),
and a failure at the integrity layer "should invalidate the financial score rather than
merely reduce it". **So this document reports a record and never a return.** No ROI, no
units, no CLV.

**Moneyline is not judgeable at all.** A moneyline pick's break-even is entirely a function
of its price: a +300 dog hitting 30% is profitable, a −3000 favourite hitting 90% is not.
Its 36.1% is printed below for completeness and carries no verdict in either direction.

**Spread and total are judged against an assumed 52.38%** (−110 both ways). That is an
assumption about a price we do not have, not an observation. It is the reason these
verdicts are weaker than the PFF_hist ones in
[`greenline-archive-2026-09-17.md`](greenline-archive-2026-09-17.md), where PFF published a
break-even per bet and grading could be genuinely price-aware.

**No proper score is reported.** The exports give PFF's `Value` — its edge over its own
break-even — without that break-even, so its cover probability is not recoverable and no
Brier or log score against a de-vigged market can be computed. Omitted by necessity, not
oversight.

## Numbers

`mde%` is the minimum win rate this n could distinguish from 52.38% (one-sided, α 0.05,
power 0.80). `wil` is the Wilson interval over picks; `gm` resamples **games** rather than
rows, because a game can contribute more than one pick.

| split | n | W | L | push | games | hit% | wilson 95% | game-clustered 95% | mde% | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| spread + total | 153 | 80 | 73 | 3 | 119 | 52.3 | 44.4 – 60.0 | 44.4 – 60.3 | 62.4 | below floor |
| spread | 65 | 34 | 31 | 1 | 65 | 52.3 | 40.4 – 64.0 | 40.0 – 64.6 | 67.8 | below floor |
| total | 88 | 46 | 42 | 2 | 88 | 52.3 | 42.0 – 62.4 | 42.0 – 62.5 | 65.6 | below floor |
| moneyline | 61 | 22 | 39 | 0 | 61 | 36.1 | 25.2 – 48.6 | 24.6 – 47.5 | — | not judgeable — no price |

**Every judgeable split sits below the floor its own sample could detect**, which is the
same conclusion the 2020 archive and the 2026 season reviews reach. The combined 52.3%
against an assumed 52.38% break-even is not "roughly break-even as a finding" — it is a
sample far too small to distinguish any of break-even, a real edge, or a real loss.

Clustering barely moves the intervals because within each market there is exactly one pick
per game (spread n=65 over 65 games, total n=88 over 88 games). The pooled row only widens
because 34 games carry both a spread and a total pick.

## Method

Each pick is graded from the final score at its captured line. `market_line` is already
signed for the side taking it (`side_line` in the parser), so the rule is uniform:

- **total** — over wins when `home + away > line`, under when `<`, push on exact.
- **spread** — the side's own margin plus its own line: `> 0` covers, `= 0` pushes.
- **moneyline** — more points wins; the line is ignored.

Pushes are excluded from the denominator, not counted as losses (3 of 220).

The grader's conventions were checked by hand against CFBD on eight real rows before the
run, including the two that are easy to get backwards — Akron at home +9.5 losing by 3 is a
cover, UL Monroe +7 losing by 17 is not. `--self-check` pins the same cases plus the push
boundaries, the Wilson interval, the MDE monotonicity, and that game-clustering genuinely
widens the interval on correlated picks.

**Trials: one.** The `> 0` selection rule is PFF's own, applied as published. No threshold
was fitted, and no variant was searched over, so there is no multiple-testing correction to
apply here.

## What this does not support

- **Not evidence Greenline wins or loses**, in either direction. Every split is below its
  MDE. The hit rates are descriptive.
- **Not a return.** No price, so no ROI is computable and none should be quoted from this
  record. Anything that needs units has to wait for a priced capture.
- **Not comparable to the 2026 season record.** Those picks are graded at a real book
  number with a known price; these are graded at PFF's number against an assumed one.
- **Not out-of-sample confirmation of the 2020 archive.** Same vendor, self-selected,
  and three slates is not a season. Three slates also means the sample is dominated by
  whatever those particular weeks looked like.
- **The moneyline record is not a red flag.** 22-39 looks alarming and means nothing
  without the prices; Greenline flags value, which on moneylines will skew toward dogs,
  and dogs lose more than half their games by construction.
- **These 217 do not join any pooled Greenline record** without first resolving the price
  question, and per the unit's standing rule the personal 2023-25 unders are not an
  independent sample to pool them with either.

## Replaying through the standard grader

[`format_exports_for_grading.py`](../scripts/format_exports_for_grading.py) reshapes the
total picks into the weekly capture format (`pff_greenline_<season>_w<week>.csv` plus a
`pff_schedule_<season>.csv`) so [`grade_greenline.py`](../scripts/grade_greenline.py) can
read them. That grader is totals-only, so **only the 91 total picks replay** — the 67
spread and 62 moneyline picks have no home in that format and stay with
`grade_export_picks.py`.

Three things kept separate on purpose:

- **Files go to `<ingest>/pff_scoreboard/export_replay/`, not beside the real captures.**
  These are synthesized from a vendor export, not pulled from PFF; a file named
  `pff_greenline_2022_w5.csv` sitting next to the genuine 2026 captures would eventually
  be read as one. `grade_greenline.py` gained `--in-dir` and `--out` for this; both
  default to the old behaviour, so the 2026 pipeline is untouched.
- **Graded output stays out of `greenline_graded.csv`**, which is the 2026 pooled record.
- **No final scores are written into the synthesized schedule.** `is_over` is left empty so
  `pff_final()` declines and the grader falls through to its documented warehouse lookup.
  CFBD stays the single source of truth rather than this adapter copying results in.

### The two paths agree exactly

| | overlap | side agrees | line agrees | **result disagreements** |
| --- | --- | --- | --- | --- |
| `grade_export_picks.py` vs `grade_greenline.py` | 77 picks | yes | yes | **0** |

Two independently written graders returning identical W/L/P on all 77 shared picks is the
main reason to have built the adapter at all.

### But the capture path grades 13 fewer

| path | graded | record |
| --- | --- | --- |
| `grade_export_picks.py` (joins on the archive's `game_id`) | 90 | 46-42, 2 push |
| `grade_greenline.py` replay | 77 | 40-35, 2 push |

The 13 missing picks (6 W, 7 L — so their absence is not directional) are ones
`grade_greenline.py`'s warehouse fallback cannot resolve: it matches on calendar day plus
a strong shared token in both names and requires one clear best hit, whereas the archive
already carries a `game_id` resolved by the parser. **The replay is strictly weaker at
finding the game**, which is why the headline record in this document is the one from
`grade_export_picks.py`.

### `projection` and `d` come out blank

The exports publish an edge without the projection it came from, so the replay's
`projection` column is empty and `d` — the projection's disagreement with the line — is
empty with it. `grade_greenline.py` previously computed `d` as `(projection or 0) - line`,
which turned a missing projection into `-line` and read as a 60-point gap between model and
market rather than a blank. Fixed in the same change; the 2026 output is unaffected, where
a projection is always present, and regrading it reproduces `greenline_graded.csv` byte for
byte.

### Ignore the replay's ROI column

`grade_greenline.py` prints units and ROI at a flat −110 (`PAYOUT = 100/110`), which is
sound for the 2026 captures and **not** sound here: these picks have no price, which is the
integrity-gate failure described above. Its `+7.9%` for 2022 and `−0.9%` for 2023 are
arithmetic on an assumed price and must not be quoted as returns. Read the replay for its
record and its agreement with the other grader, nothing else.

## Reproduce

```bash
python research/totals/scripts/grade_export_picks.py
```

The replay, whose inputs land in `$CFB_DATA_ROOT` and are regenerable, not committed:

```bash
python research/totals/scripts/format_exports_for_grading.py
```
