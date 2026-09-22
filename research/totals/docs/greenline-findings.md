# Greenline totals: everything settled, and what is still open

**Living doc — undated on purpose.** The dated docs in this folder are records of what was
known on their day and are never rewritten. This one is the current state of the question,
kept in sync with them, so nobody has to read fourteen files to find out where things stand.
Every claim points at the dated record that establishes it; if the two disagree, the dated
record is right and this file is stale.

---

## The one-paragraph answer

PFF Greenline's totals board wins **175-149 (54.0%)** over every era we have graded, against
a 52.38% break-even. The eras are statistically one thing (p 0.91), the money interval still
contains zero, and **no filter on it survives testing** — not bands, not edge thresholds, not
situational splits, not Pinnacle agreement. The honest position is a small, mechanical,
unfiltered allocation sized for uncertainty, and a recommendation on the table to cut the
unit from 1% to 0.6%.

---

## Settled

| # | Finding | Established in |
| --- | --- | --- |
| 1 | **The pooled board is 175-149, 54.0%, Wilson 48.6–59.4.** Below its own 59.3% detection floor, so it is a bound, not proof. Posterior P(true rate > break-even) 72%. | [pooled](greenline-totals-pooled-2026-09-22.md) |
| 2 | **The three eras are one thing.** Chi-square 0.15 on 2 df, p 0.93 across 2020, 2022-23 and 2026. This is what licenses quoting a pooled number at all. | [pooled](greenline-totals-pooled-2026-09-22.md) |
| 3 | **Overs match unders.** 53.7% vs 54.1%, p 0.96. No story that needs the edge to live on the under side is supported. | [pooled](greenline-totals-pooled-2026-09-22.md) |
| 4 | **No edge × band rule exists.** Best cell of 60 is 63.6%; a within-era shuffle matches it 54.7% of the time. The walk-forward is not runnable — the eras' boards barely share cells. | [rule search](greenline-totals-rule-search-2026-09-22.md) |
| 5 | **Nothing survives Holm** across four pre-registered splits (top quintile, middle quintiles, 55+, 4%+). Smallest adjusted p 0.232. | [rule search](greenline-totals-rule-search-2026-09-22.md) |
| 6 | **The 55+ / sub-4% cell is a 2026 artifact.** 57.6% pooled, but 54.5% / 52.0% / **77.4%** by era, p 0.049 — it fails the homogeneity test the whole board passes. | [rule search](greenline-totals-rule-search-2026-09-22.md) |
| 7 | **Overs are not estimable.** n=54, largest cell 13, would need ~87% to separate from break-even. | [rule search](greenline-totals-rule-search-2026-09-22.md) |
| 8 | **The personal 2023-25 unders overlap the board partially.** 7 of 12 checkable bets the same pick, **3 the opposite side**, 2 unflagged. Neither independent evidence nor poolable. | [pooled](greenline-totals-pooled-2026-09-22.md) |
| 9 | **No situational filter works.** Line move, wind, pace, big favorite, night, short rest — nothing survives Holm. | [under filters](greenline-under-filters-2026-09-17.md) |
| 10 | **Pinnacle's position does not rank the unders.** Juice lean, line vs PFF's, distance from projection, limit — n=38, nothing survives Holm. | [pinnacle shade](greenline-pinnacle-shade-2026-09-17.md) |
| 11 | **The 2022-23 exports carry no price**, so they contribute a record and never a return. Integrity gate, not a rounding choice. | [export picks](greenline-export-picks-graded-2026-09-21.md) |
| 12 | **The archive's CFBD joins are clean** after one repaired transposition and a matcher fix. `is_greenline_pick` is copied onto all three snapshots — a known trap. | [join audit](greenline-archive-join-audit-2026-09-21.md) |

## Open

| # | Question | Status |
| --- | --- | --- |
| A | **Does a Greenline flag beat a real market close?** CLV is worth far more per observation than win/loss — hundreds of picks rather than thousands. Today's CLV is computed against PFF's *own* board close, which asks whether PFF agrees with itself. | Not started. The highest-value test available. |
| B | **Were the 2020 prices real?** That era is priced at PFF's published break-evens, median implied −107. Strip 2020 and the unders pool goes +4.0% → **−0.2%**. | Not started. Cheap, and it either confirms or deflates every ROI here. |
| C | **Do unders at `value` ≥ 0.04 underperform?** Registered 2026-09-22 at a frozen raw cut. Currently 8-16 against 138-108. | **Registered. No look until 56 prospective picks have graded** (from week 4 forward, ~6 weeks). |
| D | **Does a flag predict line movement?** A bet-free test of whether PFF knows anything, accruing every week regardless of what gets bet. | Not started. |
| E | **Closed — do not reopen.** Bands, edge thresholds, overs, Pinnacle shade, situational filters. Each tested at least twice, each null. Further looks on the same 324 picks cost multiplicity and buy nothing. | Closed. |

## Standing cautions

- **Read the MDE before quoting any record.** Every split so far sits below the smallest win
  rate its own sample could detect. That is not evidence of an edge *or* against one.
- **Waiting will not settle this.** Separating a 54% true rate from break-even needs roughly
  **5,900 graded picks** — eight-plus seasons at this board's volume. Size for uncertainty;
  do not plan on significance arriving.
- **`greenline_unders.BANDS` carries the personal under record in its own table.** Those
  cutpoints were drawn looking at that record, and that record partly *is* the evaluation
  sample. Never reuse them as an analysis grid.
- **PFF's `value` is not one scale across eras.** 2020 tops out at 2.9%, 2026 reaches 5.3%.
  Raw edge bins are era labels unless ranked within era.
- **Grade at the line in the capture**, never the close, and never PFF's number when a book
  number exists. Half a point of total is worth about two points of win probability.
- **The published under list is nested inside the flag board.** Never add them.

## What this implies for money

`research/bankroll/` owns staking. The current recommendation there is to cut the Greenline
unit from 1% to 0.6% of bankroll and to swap the planning prior for the Greenline-only
history, because the live prior is 259 picks of which 201 are our own bets and it had never
seen the 212 pre-2026 vendor picks —
[greenline-prior-revision-2026-09-22.md](../../bankroll/docs/greenline-prior-revision-2026-09-22.md).
That recommendation is not yet adopted.

## Keeping this file honest

It is undated, so it must match the dated records. When a new dated doc lands in this folder,
update the relevant row here in the same commit or delete the row. If this file and a dated
record disagree, the dated record wins.
