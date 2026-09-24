# Matchup page

A local page for handicapping one game: land on this week's slate, pick a game (or any two
teams, any season, as of any week) and read every warehouse stat for both teams side by side,
with what was knowable before kickoff kept apart from what was not.

Living guide: when the code in `cfb_system_maker/matchup/` changes, fix this page in the same
commit.

## Run it

```powershell
python -m cfb_system_maker matchup            # http://127.0.0.1:5050
```

It binds `127.0.0.1` only: the page reads the whole warehouse and has no auth. The launcher
entry is **Matchup page** in `.claude/launch.json`. Tests: `python -m pytest tests/test_matchup_page.py`
(a fixture warehouse in `tmp_path`, never the real file).

| File | Holds |
| --- | --- |
| `matchup/app.py` | Flask app: `/`, `/api/slate`, `/api/teams`, `/api/matchup`, `/tokens/*.css` |
| `matchup/queries.py` | One function per section; the per-request warehouse connection |
| `matchup/stats.py` | The stat registry: table, column, direction, format, eligibility verdict |
| `matchup/odds.py` | The newest Odds API snapshot, read straight from `data/ingest/oddsapi/` |
| `matchup/static/`, `templates/` | Vanilla JS and CSS on the unit's Saturday Signal tokens |

## How it reads data

- **Warehouse:** every API request opens `cfb.duckdb` with `read_only=True`, runs its queries,
  and closes it before responding. A process holding the file open makes the nightly rebuild's
  swap fail on Windows ([app-vs-warehouse-read-path-2026-09-16.md](app-vs-warehouse-read-path-2026-09-16.md));
  `test_connection_is_closed_after_each_request` proves the file can be replaced after a
  request. While the rebuild holds the file, the page answers "Warehouse rebuilding".
- **Odds snapshot:** the one read outside the warehouse. `CFB-Odds-Snapshot` writes a file every
  6 h but the warehouse loads them only at 05:00, so current DraftKings/FanDuel numbers come from
  the newest file. Names resolve with `oddsapi_schema.candidates()` against `dim_team.school`;
  a snapshot event attaches to a game only when the unordered team pair matches **and** the
  kickoff is within 3 days (the same pair meets in other seasons).
- **Teams:** `dim_team.team_id` everywhere; `stg` tables join through `dim_team.school`, PFF
  through `stg.pff_franchise.cfbd_team_id`. FBS membership is per season from `stg.fbs_teams`
  (`dim_team.is_fbs` is current-state).
- **Timezone:** each connection sets `America/New_York`.

## As-of rules

Selecting "as of week W" sets a **cutoff**: the first kickoff of week W (the calendar start of
the week when no game is scheduled).

| Source | Rule |
| --- | --- |
| Game-grain CFBD tables, drives | Regular-season games with week < W. A postseason selection takes the whole regular season |
| PFF | Each PFF team-week is joined to its CFBD game, and games before the cutoff count (see PFF weeks below) |
| Polls | The poll labelled week N is released before week N's games, so as of W the page reads poll W (else the latest before it, stamped) |
| Massey | Latest edition dated before the cutoff; editions land 2-7 days ahead of kickoff |
| Season-final snapshots (`lookahead_only`) | Last season's value, labelled PRIOR SEASON; this season's appears only in a postgame panel |
| Game card, schedule | A game at or after the cutoff shows no score, line or result |
| Head-to-head | Meetings before the cutoff |

"Full season (postgame)" drops the cutoff and puts a banner on the page.

**PFF weeks.** PFF numbers weeks 0-19. Measured on five 2025 schedules (Iowa State, Kansas
State, Ohio State, Hawai'i, Georgia): PFF week 0 is a team's first CFBD week-1 game (the late-
August openers), 1-14 are CFBD weeks 1-14, 15-17 the late regular season (conference title games,
Army-Navy), 18+ bowls. A naive `week < W` would let a week-0 game into an as-of-week-1 view.
The page precomputes each CFBD game's PFF week and joins on it, so the cutoff applies to real
kickoffs and the FCS toggle sees the opponent. PFF weeks 15+ are left unmapped and enter only
full-season views: never early, occasionally a game short.

## Windows and roll-ups

Stat windows cover the team's games before the cutoff. The page-level roll-up picks how games
combine:

- **Pooled** (default) weights each game by its plays, so it matches recomputing the rate from
  the plays themselves.
- **Game mean** counts every game once.
- **Last 3** pools the team's three most recent games in the window.

$$
\begin{gathered}
\bar{r}_{\text{pooled}} = \frac{\sum_{g} r_g \, w_g}{\sum_{g} w_g}
\\[1em]
\begin{array}{rl}
\text{where}\quad r_g: & \text{the stat for game } g \text{ (a rate such as success rate, 0-1)} \\
w_g: & \text{the plays (or drives, or snaps) behind } r_g \text{ in game } g \\
g: & \text{the team's games inside the window}
\end{array}
\end{gathered}
$$

A team with a 0.40 success rate on 100 plays and 0.50 on 50 plays pools to
$(40 + 25) / 150 = 0.433$, where the game mean says 0.45. The pooled number is the one that
means "their success rate is 43%". Two approximations are documented rather than fixed:
explosiveness is pooled by all plays although CFBD averages it over successful plays, and the
CFBD PPA-by-game and player-PPA feeds carry no play counts, so they pool as game means.

**Toggles.** *Exclude FCS games* (on) drops games against non-FBS opponents from stat windows
and ranks; records, schedules and the betting profile keep them. *Exclude garbage time* (on)
reads the `_ngt` twin of a CFBD table, but only when the twin is as fresh as its all-plays table;
otherwise that section reads all plays and is tagged with the lag. Havoc, drives and all PFF
tables have no twin and are tagged "all plays".

**Ranks** are among FBS teams with data in that source for the same window; the denominator is
shown, conference rank is on hover. Each value also carries last season's full-season value
and rank. The edge dot on a unit row marks whichever unit ranks better (percentile), since an
offense stat and a defense-allowed stat are not one quantity; on A-vs-B rows it marks the better
value, with a 1% tie band (`stats.edge`).

**Freshness.** Each section stamps the week its source reaches and the games counted against the
games played; the stamp turns amber when the source lags the cutoff.

## Sections

| Section | Sources |
| --- | --- |
| Slate | `core.v_game_book_median`, `stg.games` (TBD kickoffs), newest odds snapshot |
| Game card | Snapshot DK/FD now; `core.fact_game_odds` movement (from 2026-09-09); `core.fact_game_line` open/close (Pinnacle, Circa, the rest collapsed; DK/FD closes before tick history); consensus median; venue, weather, `stg.pregame_win_prob` |
| Team profile | Record and conference record, polls, Massey composite, coach and tenure, transfer portal; talent, recruiting and returning production (`pregame_direct`) |
| Ratings | SP+, FPI, SRS, Elo, core ratings (prior season as of a week); Massey per-system ranks as of the week; opponent-adjusted season stats in postgame views |
| Unit matchups | `stg.advanced_game_stats(_ngt)`, `stg.ppa_games(_ngt)`, `stg.game_havoc_stats`, `core.fact_drive_postgame` rolled up per game |
| PFF grades | Offense/defense summaries, receiving, rushing, team pass-block week, 2019 on |
| Special teams | PFF kicking, punting, returns, coverage; kicker PAAR (season-final) |
| Key players | PFF lists (QB by dropbacks, rushers by carries, receivers by routes, defenders by grade among regulars) and CFBD lists (`stg.ppa_players_games`), kept separate: no id crosswalk exists |
| Betting profile | SU, ATS, O/U, average cover and close, splits; the closing consensus median over the window |
| Schedule | Each team's season, opponent AP rank before that game, common opponents |
| Head-to-head | `core.fact_game_historical` (1869-2011, scores only) and `core.fact_game` |
| Trends | Game-by-game CFBD PPA and success rate, PFF offense/defense grade |
| Sources and cutoffs | The cutoff, the snapshot file, the verdict legend, request time |

The page computes no edge, fair price or blended rating. Two slots are reserved for later and
render nothing: `estimate` on every stat row (a current/prior blend) and `model_signals` on the
response (a read-only model panel).

## Verdicts

`stats.py` gives every stat a verdict. Where `scripts/audit_pregame_eligibility.py` covers the
column the registry copies it, and `test_registry_verdicts_match_the_eligibility_audit` fails
when they disagree. Assigned here, with the reason in the registry:

- `stg.sp`, `stg.srs`: season-final snapshots, `lookahead_only`, same shape as the audited `stg.fpi`.
- `stg.ppa_games`, `stg.game_havoc_stats`, `stg.ppa_players_games`, the `_ngt` twins:
  game or player-game grain with a week, `pregame_windowed`, same shape as the audited
  `stg.advanced_game_stats`.
- `core.fact_drive_postgame`: drives of prior games only, `pregame_windowed` (the audited
  `stg.drives` non-score columns are).
- `stg.kicker_paar`: season-final with no week column, `lookahead_only`.
- `core.*` facts, odds and weather feed the game card and records, which are gated by the
  cutoff rather than by verdict.

## Left out, and why

- `core.game_projections`: no rows since 2023.
- `stg.team_stats`: entity-attribute-value with values split across `anyOf` columns.
- `stg.player_usage`: season grain, so it is lookahead for the current season; player lists use
  the game-grain PPA feed instead.
- Model outputs (spread line movement, over-zero, Greenline, tuning-lab shadow): not in the
  warehouse; the `model_signals` slot is where a reader would go.

## Performance

About 2-3 s per matchup warm, most of it the PFF and unit windows (every FBS team is aggregated
for ranks). Opening the 5.3 GB file costs about 0.1 s. One trap found building it: a `CASE`
inside a `LEFT JOIN ... ON` kept DuckDB off a hash join and cost 5 s a request; the PFF join is
now plain equality on a precomputed PFF week. Every request logs its time, and the page shows it.
