# Bankroll research instructions

Scope: **how much to bet, across strategies, from a stated bankroll.** The individual
strategies live elsewhere — floor-bias OVERs in `models/over_zero/`, PFF Greenline
vendor-pick evaluation in `research/totals/`. This unit answers what happens when they
are bet *together*, at a size, from a number. Shared data, archive, and no-lookahead
rules live in root `CLAUDE.md`.

A question about whether a strategy wins belongs to that strategy's unit. A question
about staking, ruin, terminal bankroll, or which of several strategies to fund belongs
here.

`docs/README.md` indexes every document and script in this tree. Start there.

## Standing rules for this unit

- **Never fix a win rate at a point estimate.** Every projection draws its win rates
  per path from the Beta posterior of a graded record. A bankroll curve conditioned on
  a single number reads as a forecast and is not one. `mc_combined_totals.py`'s
  `--self-check` asserts that the thin prior keeps real mass below break-even; keep
  that kind of assertion on any new model here.

- **Report the bracket, not the pick.** Where two priors are both defensible — as the
  pooled and graded-flags-only Greenline records are — show both and say the answer is
  bracketed. Do not quietly select the one that reads better.

- **Volume and stake are separate decisions, and volume is usually the live one.**
  Say which population a leg bets and how many bets that is. Most of the surprises in
  this tree have come from volume assumptions, not staking ones.

- **Flat stakes here come off the *starting* bankroll, and paths can go through zero.**
  There is no stop-loss in the model. Every scenario reports how often a path busts
  mid-season; a scenario with a non-trivial bust rate has percentiles that no real
  bankroll could reach, and the writeup has to say so rather than quoting the median.

- **Correlation is assumed, not measured.** Bets on one slate share a scoring
  environment. State the assumed ρ, run a sensitivity, and never present a tail number
  as if ρ were estimated.

- **The personal bet history is prior evidence, never an independent baseline.** The
  2023-25 unders were mostly the same Greenline flags, taken as bets. Root memory and
  `research/totals/CLAUDE.md` both say so. Pooling is legitimate; "PFF vs you" is not.

- No dedicated pytest suite. Every script takes `--self-check`; run it after changes.

## Ledger

`greenline_bet_log.py` writes `$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_bet_log.csv`.
It sits in this unit rather than `research/totals/` because what it measures is a
staking question — which flags get funded — not a question about whether Greenline
wins. It reads that unit's captures and does not write to them.

`bet` is three-valued: `y`, `n`, blank. **Blank means not yet marked.** Anything that
aggregates the ledger must refuse to compute on a week that still has blanks; treating
blank as "not bet" manufactures the coverage number the ledger exists to measure.
