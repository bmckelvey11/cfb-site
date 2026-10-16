# `research/bankroll/` index

How much to bet, across strategies, from a stated bankroll. The strategies themselves
live elsewhere — floor-bias OVERs in [`models/over_zero/`](../../../models/over_zero/),
Greenline vendor-pick evaluation in [`research/totals/`](../../totals/). Unit rules are
in [`../CLAUDE.md`](../CLAUDE.md).

---

## The question this tree exists to answer

Two totals strategies. One bankroll. Betting both, at what size, gets you where by the
end of the season — and how much of that answer is evidence rather than assumption?

The short version: **the bankroll is a multi-season growth vehicle, the Greenline
planning prior is the published under list (55–49 through 2026 week 4, updated
2026-09-28 from 32–26) pooled at κ = 0.5 with the 2023–25 personal unders, and the unit
is the smaller of quarter Kelly off that prior and the largest unit under a 3%
per-season chance of a 25% loss.** On 55–49 the planning mean is 54.7% (56.1% on the
old prior); the cap still allows 1% (P(−25%) 0.8%), but quarter Kelly is **0.83%**, so
**Kelly now binds: Greenline 0.83%**, over-zero 1%. At the 1% grid row the rest-of-2026
median is +5.3% (was +8.2%), bracketed by +1.2% on the list alone — which also fails the
cap at 1% (3.1%) — and +6.8% pooled
([sweep 09-28](bankroll-config-sweep-2026-09-28.md); the 0.83% is not in that record's
tables — `bankroll_config_sweep.py` prints it as `kelly_unit(planning_p_gl(), -110)`). The
0.6% cut recommended by [greenline-prior-revision-2026-09-22.md](greenline-prior-revision-2026-09-22.md)
was not adopted; the planning prior above is still the κ = 0.5 pool. The sweep still starts at week 4
from $20,000, like-for-like with 09-21. Not rerun on the new prior: the two-season
figures (+21% through 2027, +16.8% CAGR, median week +$125). Over-zero is ~11 bets for
the rest of 2026 and about a third of 2027's expected profit.

---

## Documents

| Doc | What it reports |
| --- | --- |
| [bankroll-stress-2026-09-17.md](bankroll-stress-2026-09-17.md) | Answer to the outside review, plus the Kelly comparison. Under the 3% cap: 0.5% passes all 25 skeptical scenarios, 1% passes 17 (15 at the time of writing), quarter Kelly 13. Drawdown and expected shortfall on every row. Full grid regenerated on the week-3 prior as `bankroll-stress-table-2026-09-21.md`; the 09-17 table is in `archive/docs/` |
| [mc-method-2026-09-17.md](mc-method-2026-09-17.md) | The full method for outside review: every input, distribution, correlation formula, staking rule, output, and the unit-size decision rule, with pseudocode and a list of things to challenge |
| [mc-combined-totals-2026-09-17.md](mc-combined-totals-2026-09-17.md) | $20,000 across both legs, weeks 4–15 of 2026. 100k paths, win rates drawn per path, nine scenarios, both Greenline priors side by side |
| [under-selection-profile-2026-09-17.md](under-selection-profile-2026-09-17.md) | Which unders got bet 2023–25, against every FBS game on the same days. The selection is a high-total rule, and the bet unders sit six points above where Greenline flags |
| [seed-bankroll-proposal-2026-09-21.md](seed-bankroll-proposal-2026-09-21.md) | The family-facing ask: $20,000 as a gift seeding a multi-season bankroll, what it funds, the planning prior and its bracket, the Monday unit rule (1% today), the two-season projection, the growth rate (a full 2027 season and one CAGR over the funded window, never an annualised 12-week season), week-level cash flow with a chart, risk, and what the numbers do not support. Rebuilt on the week-3 record and on the published under list as the bet population. PDF, an editable .docx and an 11-slide deck alongside. Supersedes the 2026-09-17 version in `archive/docs/` |
| [pooled-bankroll-growth-2026-09-17.md](pooled-bankroll-growth-2026-09-17.md) | Week-by-week fan charts over two seasons under the planning prior, three units (0.5%, 1%, quarter Kelly), re-sized weekly and flat |
| [greenline-prior-revision-2026-09-22.md](greenline-prior-revision-2026-09-22.md) | **Recommends cutting the Greenline unit from 1% to 0.6%.** The current prior is 259 picks of which 201 are our own bets; 212 pure Greenline picks from 2020 and 2022-23 were never in it. All-era Greenline unders are 54.1%, not 56.4%, which moves the binding constraint from the 3% cap to quarter Kelly and raises P(Greenline below break-even) from 10% to 29%. Not adopted; the 09-28 sweep sizes on the κ = 0.5 planning prior |
| [bankroll-stress-table-2026-09-21.md](bankroll-stress-table-2026-09-21.md) | The full `bankroll_stress.py` grid on the week-3 prior: 25 scenarios × Greenline units 0.5%, 1%, 1.2%, with drawdown, weeks under water, ES5 and bust counts. Supersedes the 09-17 table (archived) |
| [bankroll-config-sweep-2026-09-28.md](bankroll-config-sweep-2026-09-28.md) | The same grid on the week-4 prior (under list 55-49, planning mean 54.7%), same seed and horizon as 09-21. 1% still passes the cap on the planning prior (P(−25%) 0.8%, median +5.3%) but quarter Kelly is 0.83% (printed by the script, not in the tables), so Kelly binds. The list-only prior is nearly flat across units (+0.9% to +1.2%) and fails the cap at 1%. Supersedes the 09-21 sweep (`.md` archived; its `.csv` and figure stay here because `build_proposal_deliverables.py` rebuilds the 09-21 proposal from them) |

### Figures

[`figs/mc-combined-totals-2026-09-17.png`](figs/mc-combined-totals-2026-09-17.png) —
two fan charts (one per prior), overlaid terminal distributions, and a scenario dot
plot. Regenerated by `mc_combined_totals.py --figs`.

[`figs/weekly-pnl-2026-09-21.png`](figs/weekly-pnl-2026-09-21.png) — the week, not
the season: one median-outcome season as green/red bars with the bankroll over them,
and the spread of a single week at 1% and 0.5%. Regenerated by
`mc_combined_totals.py --weekly-fig <path>`.

[`figs/bankroll-config-sweep-2026-09-28.png`](figs/bankroll-config-sweep-2026-09-28.png) —
median gain and P(−25%) against Greenline stake, one line per coverage, one column per
prior (09-21 version beside it). Regenerated, under the run date, by
`bankroll_config_sweep.py --out research/bankroll/docs`.
[`figs/bankroll-config-sweep-2026-09-21.png`](figs/bankroll-config-sweep-2026-09-21.png) is
the 09-21 version, kept as a `build_proposal_deliverables.py` input.

[`figs/pooled-bankroll-growth-2026-09-17.png`](figs/pooled-bankroll-growth-2026-09-17.png),
[`figs/pooled-bankroll-growth-2026-09-21.png`](figs/pooled-bankroll-growth-2026-09-21.png) —
the pooled-prior fan charts by week; the 09-21 one is what `pooled_growth_chart.py` now
writes and what the 09-21 proposal embeds.

---

## Scripts

| Script | What it does |
| --- | --- |
| [`../scripts/mc_combined_totals.py`](../scripts/mc_combined_totals.py) | The projection. Gaussian-copula slate correlation, Beta-posterior win rates, per-week percentiles, mid-season bust rate, and the figures. `--growth` prints the growth-rate and week-level tables; it refuses to annualise a horizon under a year |
| [`../scripts/under_selection_profile.py`](../scripts/under_selection_profile.py) | Joins the 201 personal unders to `core.fact_game` and profiles them against the slate they were picked from |
| [`../scripts/bankroll_config_sweep.py`](../scripts/bankroll_config_sweep.py) | Grid over Greenline unit and prior (and coverage, with `--gl-volume slate`) on top of `mc_combined_totals.simulate`. Picks the max-median row that keeps P(−25%) ≤ 3% (`MAX_P_M25`) and bust = 0 under the planning prior (κ = 0.5); n58 and pooled are reported as the bracket. Prints quarter Kelly off the planning prior. Writes the CSV, the table and the figure |
| [`../scripts/bankroll_stress.py`](../scripts/bankroll_stress.py) | 25 skeptical scenarios × 3 Greenline units (0.5%, 1%, 1.2%) through `simulate`'s stress knobs (`oz_center`, `oz_extra_sd`, `gl_kappa`, `gl_marginal_penalty`, `rho`). Reports drawdown, weeks under water, ES5, bust counts |
| [`../scripts/pooled_growth_chart.py`](../scripts/pooled_growth_chart.py) | Fan chart of bankroll by week, pooled prior only, three units side by side; `--flat-stakes` adds a flat row |
| [`../scripts/md_to_docx.py`](../scripts/md_to_docx.py) | Markdown to .docx through the officecli binary — headings, tables, images, bold, code. Exists because this machine has neither pandoc nor python-docx and the proposal has to be editable in Word |
| [`../scripts/build_proposal_deliverables.py`](../scripts/build_proposal_deliverables.py) | The proposal's PDF, .docx and deck. `--no-pdf` / `--no-docx` to skip the slow steps |
| [`../scripts/greenline_bet_log.py`](../scripts/greenline_bet_log.py) | **The ledger of which flags actually got bet.** Seed after each capture, mark before the games grade |
| [`../scripts/bet_history_summary.py`](../scripts/bet_history_summary.py) | Hit rate / ROI table + cumulative-units graph from a book export (`--src`, `--by week\|month\|type`) |

Every script takes `--self-check`. There is no pytest suite in this tree.

---

## The weekly habit

Capture and grading are [`research/totals/`](../../totals/docs/README.md)'s pipeline.
This unit adds one step, and it is the only one that is not automated: **marking which
flags got funded.** An unmarked week is lost data — no later work recovers it, which is
exactly why the 2023–25 coverage question is unanswerable. The ledger distinguishes `y`,
`n`, and blank, and blank means *not yet marked*: coverage refuses to compute on a week
that still has blanks, because defaulting them to "no" manufactures the very number the
ledger exists to measure.

```
python research/bankroll/scripts/greenline_bet_log.py --seed          # after each capture
python research/bankroll/scripts/greenline_bet_log.py --import-book   # after a book re-export
python research/bankroll/scripts/greenline_bet_log.py --show 4        # review the week
python research/bankroll/scripts/greenline_bet_log.py --mark 4 31190  # or --none 4
python research/bankroll/scripts/greenline_bet_log.py --coverage
```

`--import-book` is the low-effort path: re-export the book to
`data/ingest/bet_history/history.csv` and it marks a whole week in one pass — `y` for
flags it finds a matching total on, `n` for the rest of that day's flags. It resolves
both sides to CFBD team ids first, because PFF and the book disagree on 32 of 137
abbreviations, and it only touches days the export actually covers.

---

## Open items

1. ~~**No conflict rule exists.**~~ **Done 2026-09-17.** Rule: over-zero takes the game,
   Greenline skips it and the skipped flag is marked not bet so the control still grades
   it. Stated in the proposal §3. Week 3 produced no conflict.
2. **Coverage is unmeasured.** As last recorded here (2026-09-21): 106 flags seeded for
   2026 weeks 2–3, none marked. This count is not refreshed weekly; run
   `greenline_bet_log.py --coverage` for the current one. Until flags are marked, whether the personal under record transfers to Greenline's flag population
   stays open — and the bracket around the planning prior stays wide. As of 2026-09-21
   the prior is built on the 58 published under picks instead, which is the nearest
   stand-in for the bet population and not a substitute for the ledger.
3. **`research/totals/scripts/greenline_unders.py`'s `BANDS` constant does not
   reconcile.** Its rows sum to 202 bets and 88 losses against a record of 201 and 87.
   Noted, not touched — it belongs to that unit.

---

## Provenance

Created 2026-09-17; rebuilt on the week-3 record 2026-09-21. The three scripts and two documents were written that first day under
root `scripts/`, `docs/`, and `research/totals/`, then moved here: root `docs/` is
scoped to shared warehouse, design-system and data-coverage material, and the work
spans `models/over_zero/` and `research/totals/` rather than sitting inside either.
