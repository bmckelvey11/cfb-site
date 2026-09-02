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
- **Book fair** — median closing spread across real sportsbooks (FanDuel, BetMGM, Caesars, Bet365, Pinnacle). Not "composite".
- **Cover margin** — bet team's score plus the line taken, minus the opponent's score. Positive = covered by that much; negative = missed by that much. Defined for spread bets only.
- **Hook loss** — a spread bet with cover margin of exactly −0.5: lost by the half point.
- **Key number** — a spread line on or adjacent to 3 or 7 (2.5–3.5, 6.5–7.5), where NFL/CFB final-margin mass concentrates and books shade hardest.
- **Betting day** — the ET calendar date of kickoff (a 1am UTC kickoff belongs to the previous ET evening).

## Warehouse layers

- **Pair** — one concept arriving from both CFBD APIs as two staging tables (one in `stg_gql`, one in `stg`), under different names and different column sets. A pair is two sources of the same subject, **not** a duplicate; measurement decides whether either side is redundant.
- **Canonical source** — for a given pair, the side designated authoritative after measuring column containment and coverage. Established by measurement per concept, never by row count alone.
- **Scaffolding column** — `season`, `week`, or `season_type` bound from a dump's filename rather than its payload. Where the filename does not carry one it arrives NULL and stays NULL; these are pruned at load. Distinct from a payload column that happens to be empty, which is a finding and is never auto-dropped.
- **Relation-only entity** — a GraphQL root whose identity lives in a to-one relation rather than in its own scalars. It must be nest-selected, or its dump cannot be joined to anything and its sort is not a total order.
- **Merged table** — a `core` table conforming both sides of a pair, carrying every populated column from each and a `_provenance` marker. Merged tables live in `core`; the `stg` sources they were built from stay in place.
