# Alabama vs Georgia, 2026 season to date

Question: Compare Alabama and Georgia. Working scope: overall teams this season.

Source: `core__fact_game` in `/workspace/data/football.sqlite`, opened read-only. Snapshot export: 2026-09-17T23:51:41.325087+00:00. Warehouse coverage: seasons 2012–2026, 34645 game rows. Analysis season: 2026 only. Population: games involving these two FBS teams, including opponents from all divisions; no FBS-opponent-only filter, no betting-line requirement. Include completed games with both scores and known, timezone-aware kickoff strictly before snapshot export, normalized to UTC. No imputation.

Alabama: 12 scheduled rows, 2 completed, 0 completed rows excluded for missing scores/kickoff or cutoff. 2026-09-05 12:00:00-04:00: Alabama 48, East Carolina 10; 2026-09-12 15:30:00-04:00: Kentucky 17, Alabama 45
Georgia: 12 scheduled rows, 2 completed, 0 completed rows excluded for missing scores/kickoff or cutoff. 2026-09-05 15:00:00-04:00: Georgia 63, Tennessee State 3; 2026-09-12 12:45:00-04:00: Georgia 70, Western Kentucky 20

```json
[
  {
    "team": "Alabama",
    "games": 2,
    "wins": 2,
    "losses": 0,
    "ties": 0,
    "points_for": 93,
    "points_against": 27,
    "points_per_game": 46.5,
    "points_allowed_per_game": 13.5,
    "average_margin": 33.0
  },
  {
    "team": "Georgia",
    "games": 2,
    "wins": 2,
    "losses": 0,
    "ties": 0,
    "points_for": 133,
    "points_against": 23,
    "points_per_game": 66.5,
    "points_allowed_per_game": 11.5,
    "average_margin": 55.0
  }
]
```

Validation: each team's selected game IDs are unique; wins/losses/ties reconcile to games. Four final scores were cross-checked against official team pages accessed September 18, 2026:
- [Alabama schedule](https://rolltide.com/sports/football/schedule/text)
- [Georgia statistics](https://georgiadogs.com/sports/football/stats/2026)

Context sources:
- [Georgia Arkansas preview, September 14](https://georgiadogs.com/news/2026/9/14/football-georgia-opens-sec-play-at-arkansas)
- [Alabama Kentucky recap, September 12](https://rolltide.com/news/2026/9/13/football-second-half-surge-propels-no-12-12-alabama-past-kentucky-45-17)

Interpretation: Georgia has the stronger raw scoring results; Alabama has already won an SEC road game. Opponent quality and game situations differ. Two games per team are insufficient to establish relative strength or a betting edge. Scoring totals include all team points, not only offensive points. No opponent adjustment, model prediction, injury clearance, live line, or betting recommendation is calculated. Required game fields are present; this snapshot has no dedicated current injury feed or player passing-stat table. Public quarterback figures, if discussed, come from official current web sources, not warehouse estimates. Unknown games absent from the snapshot cannot be quantified.
