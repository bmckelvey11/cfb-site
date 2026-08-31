# Reminders

## Held: gamePlayerStat GraphQL pull

**Status:** built + tested, NOT run. Run only after base data (REST `scrape` + 24 default GraphQL tables) fully downloaded.

**Run command (all years):**
```powershell
.venv\Scripts\python.exe -m cfb_system_maker graphql --season 2020 2021 2022 2023 2024 --game-player-stats
```
- ~2.9M rows, ~2,900 requests, ~425MB. Per-season files `data/graphql/gamePlayerStat_{season}.json`. Resume-safe.

**Columns pulled (flattened, labeled):**

| Column | Source | Example |
|--------|--------|---------|
| `id` | scalar | 22506095 |
| `stat` | scalar | "19/30" |
| `athleteId` | scalar | 5081405 |
| `athlete.name` | relation | "AJ Swann" |
| `statType.name` | relation (playerStatType) | "C/ATT" |
| `category.name` | relation (playerStatCategory) | "passing" |
| `gameTeam.gameId` | relation | — |
| `gameTeam.teamId` | relation | 238 |
| `gameTeam.homeAway` | relation | "home" |
| `gameTeam.game.season` | nested relation | 2023 |
| `gameTeam.game.week` | nested relation | 1 |
| `gameTeam.game.seasonType` | nested relation | "regular" |

---

## Other pending data (REST, opt-in, not yet scraped)

- `advanced_box_score` — per-game, `--include-per-game` (use `--fbs-only` to cut FCS)
- `win_probability` — per-game, `--include-per-game`
- `player_season_overview` — per-player, `--include-per-player`
- on-demand (skipped in bulk): `scoreboard`, `matchup`, `player_search`, `live_plays`
