# CONTEXT

Glossary of canonical terms for CFB System Maker. Add terms as they are resolved; keep implementation details out.

## Football identity

- **Team** — a school/program that persists across seasons (Ohio State). Identity only; record, ratings, and play shape do not live here.
- **FBS Team** — a Team whose classification is FBS. The Team-season profile picker is FBS Teams only.
- **Team-season** — that school in one season, built from regular and postseason games only (2020 spring types are out). Record, conference, ratings, and play shape attach here, not to the Team forever.
- **Completed Team-season** — a Team-season with at least one completed game. Distinct from a scheduled-only Team-season (slate exists, no result yet). The profile lands on the newest Completed Team-season; the picker may still open a scheduled-only year.
- **Team-season profile** — a one-subject view of a Team-season (identity, SU record, ATS record, ratings strip, play shape, coach cluster, game log). Complementary to league-wide comparison. Not a betting book.
  _Avoid_: Team summary, Team P&L, Team involvement
- **Ratings strip** — SP+, FPI, and Elo as equal-rank quality numbers for a Team-season. There is no single canonical rating.
  _Avoid_: “the” rating, SP+ as the headline
- **Play shape** — how this Team-season plays: pace, run rate, success. Not the coach’s career label.
- **Coach cluster** — the career playstyle label for a head coach on that Team-season, shown with identity (not with play shape) and always qualified as career, not this year. If two HCs served, both appear, each with a cluster.
  _Avoid_: style (that word meant both)
- **Head coaches** — every HC who served that Team-season, labeled. Not file-order last-write-wins.
- **SU record** — wins and losses on the scoreboard for Team-season games. Ties count for neither side.
- **ATS record** — covers and non-covers against the selected close, equal rank to the SU record on the profile. Pushes and unlined games count for neither side. The selected book is named on each game, not as a season-level house book. Not Team P&L: no units, no “taken” side.
- **Game log** — every Team-season game in date order. SU, ATS, and the selected book sit on the row. Unplayed slate rows appear only on a scheduled-only Team-season; they do not enter SU or ATS.

## Bet-history analysis

- **Team P&L** — net units from bets where that team was _taken_ (spread or moneyline sides only). Totals bets never contribute to Team P&L, because a totals bet backs no team.
- **Team involvement** — any core bet placed on a game that team played in, including totals. Measures where betting attention goes, not who was backed.
- **Core bet** — NCAAF full-game straight bet (spread, total, or moneyline). Excludes first-half/second-half/live/team-total bets, parlays, and teasers.
- **Break-even rate** — 52.38%, the win rate needed to profit at −110 juice.
- **CLV (closing line value)** — the difference between the number taken and the consensus closing number, signed so positive = better than close.
- **Model consensus** — screened, equal-weighted average of Prediction Tracker model spreads (E4 input). Not "composite".
- **Book fair** — median closing spread across real sportsbooks (Action Network ids 49 Caesars, 68 DraftKings, 69 FanDuel, 71 BetRivers, 75 BetMGM; names per AN's own book list, corrected 2026-09-08). Not "composite".
- **Cover margin** — bet team's score plus the line taken, minus the opponent's score. Positive = covered by that much; negative = missed by that much. Defined for spread bets only.
- **Hook loss** — a spread bet with cover margin of exactly −0.5: lost by the half point.
- **Key number** — a spread line on or adjacent to 3 or 7 (2.5–3.5, 6.5–7.5), where NFL/CFB final-margin mass concentrates and books shade hardest.
- **Betting day** — the ET calendar date of kickoff (a 1am UTC kickoff belongs to the previous ET evening).

## Bankroll

- **Seed bankroll** — money given to fund a betting bankroll with nothing owed back. A gift, not an investment, loan, or security. Profit and bankroll stay in the operation.
  _Avoid_: investment, seed money, stake (that word means bet size)
- **Leg** — one strategy bet from a shared bankroll. Two legs today: over-zero OVERs and Greenline totals. A leg has its own record, price, and volume.
- **Coverage** — the fraction of a leg's available flags that actually get bet. Historical Greenline coverage is ~13%. Coverage above that is conditional: the picked-flag record says nothing about the flags passed on.
- **Prior** — the graded record a leg's win rate is drawn from. Where two records are both defensible (`pooled`, `n49`), projections carry both and the answer is a **bracket**, never one number.
- **Bust** — a simulated path whose running bankroll passes through zero mid-season. Reported as a rate on every scenario; percentiles on a busting row are unreachable.
- **Conflict** — the same game flagged on opposite sides by two legs. Rule: Greenline takes the game, over-zero skips it.
- **Unit** — one flat bet as a fraction of the *starting* bankroll. Never compounded; Saturday kickoffs are simultaneous.

## Warehouse layers

- **Pair** — one concept arriving from both CFBD APIs as two staging tables. Both live in `stg` since the 2026-09-10 collapse (ADR-0003); the GraphQL side carries a `_gql` suffix only where it would collide (`calendar_gql`, `draft_picks_gql`, `predicted_points_gql`). Different names and different column sets. A pair is two sources of the same subject, **not** a duplicate; measurement decides whether either side is redundant.
- **Canonical source** — for a given pair, the side designated authoritative after measuring column containment and coverage. Established by measurement per concept, never by row count alone.
- **Scaffolding column** — `season`, `week`, or `season_type` bound from a dump's filename rather than its payload. Where the filename does not carry one it arrives NULL and stays NULL; these are pruned at load. Distinct from a payload column that happens to be empty, which is a finding and is never auto-dropped.
- **Relation-only entity** — a GraphQL root whose identity lives in a to-one relation rather than in its own scalars. It must be nest-selected, or its dump cannot be joined to anything and its sort is not a total order.
- **Merged table** — a `core` table conforming both sides of a pair, carrying every populated column from each and a `_provenance` marker. Merged tables live in `core`; the `stg` sources they were built from stay in place.
