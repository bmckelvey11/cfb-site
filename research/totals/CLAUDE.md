# Totals research instructions

Scope: totals work that is **not yet in a harness**. Two strands live here — PFF Greenline
vendor-pick evaluation (scripts and graded results) and totals modeling research (reading
and prompt material, no code behind it). Shared data, archive, and no-lookahead rules live
in root `CLAUDE.md`.

`models/totals/` is the different thing: the implemented backtest harness
(`python -m models.totals backtest`). A question about running or citing that harness
belongs there, not here. A question about whether a vendor's picks win, or about a modeling
idea that has no code yet, belongs here.

`docs/README.md` indexes every document, script, and data artifact in this tree. Start there.

## Greenline vendor-pick evaluation

- Pipeline order matters — the scripts hand off through CSVs under
  `$CFB_DATA_ROOT/ingest/pff_scoreboard/`, and running them out of order silently reads a
  stale capture:

  `scripts/pull_pff_scoreboard.py` (upstream, lives in **root** `scripts/`)
  → `greenline_unders.py`
  → `match_greenline_books.py` / `greenline_vs_pinnacle.py`
  → `grade_greenline.py`
  → `greenline_season_review.py`
  → `greenline_bet_stats.py` / `greenline_bet_bounds.py` / `greenline_edge_window.py`

- **The pooled record is underpowered and the reviews say so in their own words.** Every
  split so far sits below the minimum detectable win rate for its own sample size, which
  means it is not evidence either way — in either direction. Cite
  `docs/greenline-season-review-2026-09-16.md` for the record and its MDE; do not restate
  the numbers here, and do not describe any split as an edge until a review says it clears
  its own floor.

- **The personal 2023-25 unders are not an independent sample.** They were mostly the same
  Greenline flags, taken as bets — see `greenline_bet_stats.py`'s docstring. Pool them as
  prior evidence if a method calls for it, never as an independent baseline and never as
  out-of-sample confirmation of a Greenline result.

- PFF's `value` is its stated win probability minus the 52.38% break-even at -110. It is
  PFF's own claim, not a measured edge; `greenline_edge_window.py` is the script that asks
  whether it ranks anything.

- Grade at the line in the capture, not the close. PFF shows its own number, which is not
  the one you bet — `match_greenline_books.py` reprices at a book, and half a point of
  total is worth roughly two points of win probability at these numbers.

- Pinnacle is the reference price, not another book. Greenline vs a retail book says what
  number you can get; Greenline vs Pinnacle says whether the projection disagrees with the
  sharpest available opinion.

## Totals modeling research

- `docs/fbs-totals-frontier-models.md`, `docs/fbs-totals-system-research-report.md`, and
  `docs/research-prompts/fbs-totals/` are **reading and prompt material**. Nothing in this
  strand has been implemented or tested here. Treat every claim in it as a hypothesis to
  test against the warehouse, not as a result, and do not cite it as a finding.
- Anything from this strand that gets built and backtested belongs in `models/totals/`.

## Not in this unit

- **Which flags actually got bet** is a staking question, not a "does Greenline win"
  question, so the ledger lives in `research/bankroll/` (`greenline_bet_log.py`). It
  reads this unit's captures and never writes to them. Seed it after every capture —
  an unmarked week cannot be recovered later, which is exactly why the 2023-25
  coverage question has no answer.
- **Bankroll, staking, and any projection that combines Greenline with another
  strategy** belong to `research/bankroll/` as well. A question about whether
  Greenline's picks win belongs here; a question about how much to bet on them
  does not.
