# CFBD endpoint field reference

Auto-generated from the vendored `cfbd-python` client (spec version pinned in `cfbd-python/README.md`). Every field description below is authored by us — CFBD's OpenAPI spec ships descriptions for request *parameters* only (see `cfbd/api/*.py`), never for response fields, so nothing here is copied from upstream docs. Regenerate by rerunning the generator script if the vendored client is bumped; verify names against the model source under `cfbd-python/cfbd/models/` if in doubt.

Endpoint list mirrors the `ENDPOINTS` registry in [`cfb_system_maker/scrapers.py`](../cfb_system_maker/scrapers.py) — see [`docs/data-coverage.md`](data-coverage.md) for which endpoints are actually scraped, on what cadence, and known data floors/gaps.

## Glossary

- **EPA / PPA** — Expected Points Added / Predicted Points Added: value of a play in expected-points terms. CFBD calls its own implementation PPA; EPA appears on a few adjusted-metrics models.
- **SP+** — Bill Connelly's predictive team-strength rating.
- **FPI** — ESPN's Football Power Index.
- **SRS** — Simple Rating System (margin of victory, strength-of-schedule adjusted).
- **Elo** — Chess-style rating updated after each game result.
- **Havoc rate** — share of defensive plays with a TFL, forced fumble, pass breakup, or interception.
- **Success rate** — share of plays gaining enough yardage to stay "on schedule" (Football Outsiders rules: 50% of yards to go on 1st down, 70% on 2nd, 100% on 3rd/4th).
- **Line yards / second-level yards / open-field yards** — run yardage split by how far past the line of scrimmage it was gained (offensive-line credit vs. runner credit).
- **`excludeGarbageTime` (`_ngt` endpoints)** — drops blowout garbage-time plays before aggregating, so values differ from the unfiltered endpoint rather than being a strict subset.

## Adjusted metrics (EPA, weighted, opponent-adjusted)

### `adjusted_player_passing`

- **CFBD method:** `AdjustedMetricsApi.get_adjusted_player_passing_stats`
- **Scrape mode:** per season

_Player EPA weighted by game importance/leverage._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `wepa` | float | Weighted EPA — EPA contribution weighted by the game's leverage/importance. |
| `plays` | int | Number of plays. |

### `adjusted_player_rushing`

- **CFBD method:** `AdjustedMetricsApi.get_adjusted_player_rushing_stats`
- **Scrape mode:** per season

_Player EPA weighted by game importance/leverage._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `wepa` | float | Weighted EPA — EPA contribution weighted by the game's leverage/importance. |
| `plays` | int | Number of plays. |

### `adjusted_team_season`

- **CFBD method:** `AdjustedMetricsApi.get_adjusted_team_season_stats`
- **Scrape mode:** per season

_Opponent-adjusted EPA/success-rate metrics at the team-season level._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `epa` | AdjustedTeamMetricsEpa | Expected Points Added — value of a play/drive/game in expected-points terms. — see [AdjustedTeamMetricsEpa](#adjustedteammetricsepa) |
| `epaAllowed` | AdjustedTeamMetricsEpa | Expected Points Added allowed (defensive perspective). — see [AdjustedTeamMetricsEpa](#adjustedteammetricsepa) |
| `successRate` | AdjustedTeamMetricsSuccessRate | Success rate. — see [AdjustedTeamMetricsSuccessRate](#adjustedteammetricssuccessrate) |
| `successRateAllowed` | AdjustedTeamMetricsSuccessRate | Success rate allowed. — see [AdjustedTeamMetricsSuccessRate](#adjustedteammetricssuccessrate) |
| `rushing` | AdjustedTeamMetricsRushing | Rushing. — see [AdjustedTeamMetricsRushing](#adjustedteammetricsrushing) |
| `rushingAllowed` | AdjustedTeamMetricsRushing | Rushing allowed. — see [AdjustedTeamMetricsRushing](#adjustedteammetricsrushing) |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `explosivenessAllowed` | float | Explosiveness allowed. |

### `kicker_paar`

- **CFBD method:** `AdjustedMetricsApi.get_kicker_paar`
- **Scrape mode:** per season

_Points Above Average Replacement for kickers on field goals._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `paar` | float | Points Above Average Replacement on field goal attempts. |
| `attempts` | int | Attempts. |

## Betting lines

### `lines`

- **CFBD method:** `BettingApi.get_lines`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `homeTeamId` | int | Home team ID. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `homeClassification` | DivisionClassification | Home team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `homeScore` | int | Home score. |
| `awayTeamId` | int | Away team ID. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `awayClassification` | DivisionClassification | Away team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `awayScore` | int | Away score. |
| `lines` | List[GameLine] | Lines. |

## Coaches

### `coaches`

- **CFBD method:** `CoachesApi.get_coaches`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `hireDate` | datetime | Date the coach was hired. |
| `seasons` | List[CoachSeason] | Seasons. |

### `coach_seasons`

- **CFBD method:** `CoachesApi.get_coach_seasons`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `games` | int | Games coached. |
| `wins` | int | Win count. |
| `losses` | int | Loss count. |
| `ties` | int | Tie count. |
| `winPercentage` | float | Win percentage. |
| `coach` | CoachReference | Coach name. — see [CoachReference](#coachreference) |
| `team` | CoachSeasonTeamReference | Team name. — see [CoachSeasonTeamReference](#coachseasonteamreference) |
| `year` | int | Season year. |
| `preseasonRank` | int | Preseason poll rank. |
| `postseasonRank` | int | Final/postseason poll rank. |
| `srs` | float | SRS. |
| `spOverall` | float | SP+ overall. |
| `spOffense` | float | SP+ offense. |
| `spDefense` | float | SP+ defense. |
| `teamMetrics` | CoachRatingContext | Team metrics. — see [CoachRatingContext](#coachratingcontext) |
| `recruiting` | CoachRecruitingContext | Recruiting. — see [CoachRecruitingContext](#coachrecruitingcontext) |
| `pollResume` | CoachPollResume | Poll resume. — see [CoachPollResume](#coachpollresume) |
| `attributionComplete` | bool | Attribution complete. |
| `recordSplits` | CoachRecordSplits | Record splits. — see [CoachRecordSplits](#coachrecordsplits) |
| `scoring` | CoachScoring | True if the play resulted in points. — see [CoachScoring](#coachscoring) |
| `cfp` | CoachCfpContext | Cfp. — see [CoachCfpContext](#coachcfpcontext) |
| `draftFollowingSeason` | CoachDraftContext | Draft following season. — see [CoachDraftContext](#coachdraftcontext) |

### `coach_profile`

- **CFBD method:** `CoachesApi.get_coach_profile`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `displayName` | str | Full display name. |
| `currentTeam` | CoachSeasonTeamReference | Current team. — see [CoachSeasonTeamReference](#coachseasonteamreference) |
| `career` | CoachCareer | Career. — see [CoachCareer](#coachcareer) |
| `birthDate` | str | Birth date. |
| `almaMater` | CoachAlmaMater | Alma mater. — see [CoachAlmaMater](#coachalmamater) |
| `graduationYear` | int | Graduation year. |
| `wikidataId` | str | Wikidata ID. |
| `hallOfFameYear` | int | Hall of fame year. |

### `coach_tenures`

- **CFBD method:** `CoachesApi.get_coach_tenures`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `coach` | CoachReference | Coach name. — see [CoachReference](#coachreference) |
| `team` | CoachTeamReference | Team name. — see [CoachTeamReference](#coachteamreference) |
| `hireDate` | str | Date the coach was hired. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |
| `effectiveStart` | datetime | Effective start. |
| `effectiveEnd` | datetime | Effective end. |
| `isInterim` | bool | Is interim. |
| `active` | bool | Active. |
| `seasons` | int | Seasons. |
| `record` | CoachRecord | Record. — see [CoachRecord](#coachrecord) |
| `attributionComplete` | bool | Attribution complete. |

## Conferences

### `conferences`

- **CFBD method:** `ConferencesApi.get_conferences`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |
| `shortName` | str | Short name. |
| `abbreviation` | str | Short abbreviation. |
| `classification` | ConferenceClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `memberCount` | int | Member count. |

### `conference_affiliations`

- **CFBD method:** `ConferencesApi.get_team_conference_affiliations`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conferenceId` | int | Conference identifier, joins to the conferences endpoint. |
| `conference` | str | Conference name. |
| `conferenceAbbreviation` | str | Conference abbreviation. |
| `classification` | ConferenceClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `conferenceDivision` | str | Conference division. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |

### `conference_changes`

- **CFBD method:** `ConferencesApi.get_team_conference_changes`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `fromConferenceId` | int | From conference ID. |
| `fromConference` | str | From conference. |
| `fromConferenceAbbreviation` | str | From conference abbreviation. |
| `fromClassification` | ConferenceClassification | From classification. (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `toConferenceId` | int | To conference ID. |
| `toConference` | str | To conference. |
| `toConferenceAbbreviation` | str | To conference abbreviation. |
| `toClassification` | ConferenceClassification | To classification. (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `effectiveYear` | int | Effective year. |

## NFL draft

### `draft_picks`

- **CFBD method:** `DraftApi.get_draft_picks`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `collegeAthleteId` | int | College player identifier. |
| `nflAthleteId` | int | NFL.com player identifier. |
| `collegeId` | int | College ID. |
| `collegeTeam` | str | College the player was drafted from. |
| `collegeConference` | str | College conference the player was drafted from. |
| `nflTeamId` | int | Nfl team ID. |
| `nflTeam` | str | NFL team that drafted the player. |
| `year` | int | Season year. |
| `overall` | int | Overall (combined) rating. |
| `round` | int | Round. |
| `pick` | int | Overall draft pick number. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `preDraftRanking` | int | Pre draft ranking. |
| `preDraftPositionRanking` | int | Pre draft position ranking. |
| `preDraftGrade` | int | Pre draft grade. |
| `hometownInfo` | DraftPickHometownInfo | Recruit's hometown details. — see [DraftPickHometownInfo](#draftpickhometowninfo) |

### `draft_positions`

- **CFBD method:** `DraftApi.get_draft_positions`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `name` | str | Name. |
| `abbreviation` | str | Short abbreviation. |

### `draft_teams`

- **CFBD method:** `DraftApi.get_draft_teams`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `location` | str | Location details (city/state/lat/lon). |
| `nickname` | str | Nickname. |
| `displayName` | str | Full display name. |
| `logo` | str | Logo. |

## Drives

### `drives`

- **CFBD method:** `DrivesApi.get_drives`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `offense` | str | Offensive-side breakdown. |
| `offenseConference` | str | Offense team's conference. |
| `defense` | str | Defensive-side breakdown. |
| `defenseConference` | str | Defense team's conference. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `id` | str | Unique identifier for the record. |
| `driveNumber` | int | Drive number. |
| `scoring` | bool | True if the play resulted in points. |
| `startPeriod` | int | Start period. |
| `startYardline` | int | Start yardline. |
| `startYardsToGoal` | int | Start yards to goal. |
| `startTime` | PlayClock | Start time. — see [PlayClock](#playclock) |
| `endPeriod` | int | End period. |
| `endYardline` | int | End yardline. |
| `endYardsToGoal` | int | End yards to goal. |
| `endTime` | PlayClock | End time. — see [PlayClock](#playclock) |
| `elapsed` | PlayClock | Elapsed. — see [PlayClock](#playclock) |
| `plays` | int | Number of plays. |
| `yards` | int | Yards. |
| `driveResult` | str | Drive result. |
| `isHomeOffense` | bool | Is home offense. |
| `startOffenseScore` | int | Start offense score. |
| `startDefenseScore` | int | Start defense score. |
| `endOffenseScore` | int | End offense score. |
| `endDefenseScore` | int | End defense score. |

## Games

### `advanced_box_score`

- **CFBD method:** `GamesApi.get_advanced_box_score`
- **Scrape mode:** per game (fan-out, opt-in)

| Field | Type | Description |
|---|---|---|
| `gameInfo` | AdvancedBoxScoreGameInfo | Game info. — see [AdvancedBoxScoreGameInfo](#advancedboxscoregameinfo) |
| `teams` | AdvancedBoxScoreTeams | Teams. — see [AdvancedBoxScoreTeams](#advancedboxscoreteams) |
| `players` | AdvancedBoxScorePlayers | Players. — see [AdvancedBoxScorePlayers](#advancedboxscoreplayers) |

### `calendar`

- **CFBD method:** `GamesApi.get_calendar`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `endDate` | datetime | End date. |
| `firstGameStart` | datetime | First game start. |
| `lastGameStart` | datetime | Last game start. |

### `game_player_stats`

- **CFBD method:** `GamesApi.get_game_player_stats`
- **Scrape mode:** per season x week

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `teams` | List[GamePlayerStatsTeam] | Teams. |

### `game_team_stats`

- **CFBD method:** `GamesApi.get_game_team_stats`
- **Scrape mode:** per season x week

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `teams` | List[GameTeamStatsTeam] | Teams. |

### `games`

- **CFBD method:** `GamesApi.get_games`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `startTimeTBD` | bool | True if kickoff time was not yet announced. |
| `completed` | bool | True once the game has finished. |
| `neutralSite` | bool | True if played at a neutral (non-home) site. |
| `conferenceGame` | bool | True if both teams share a conference. |
| `attendance` | int | Reported attendance. |
| `venueId` | int | Venue identifier, joins to the venues endpoint. |
| `venue` | str | Venue name. |
| `homeId` | int | Home team identifier. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `homeClassification` | DivisionClassification | Home team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `homePoints` | int | Home team's final score. |
| `homeLineScores` | List[Union[float] | Home team's score by quarter/period. |
| `homePostgameWinProbability` | float | Model-estimated home win probability after the game. |
| `homePregameElo` | int | Home team's Elo rating entering the game. |
| `homePostgameElo` | int | Home team's Elo rating after the game. |
| `awayId` | int | Away team identifier. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `awayClassification` | DivisionClassification | Away team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `awayPoints` | int | Away team's final score. |
| `awayLineScores` | List[Union[float] | Away team's score by quarter/period. |
| `awayPostgameWinProbability` | float | Model-estimated away win probability after the game. |
| `awayPregameElo` | int | Away team's Elo rating entering the game. |
| `awayPostgameElo` | int | Away team's Elo rating after the game. |
| `excitementIndex` | float | CFBD's game-excitement metric, derived from win-probability swings. |
| `highlights` | str | Highlight video URL, if available. |
| `notes` | str | Free-text notes about the game (e.g. bowl name). |
| `playoff` | GamePlayoff | Playoff context for the game (round/bracket), if applicable. — see [GamePlayoff](#gameplayoff) |

### `media`

- **CFBD method:** `GamesApi.get_media`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startTime` | datetime | Start time. |
| `isStartTimeTBD` | bool | Is start time t b d. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `mediaType` | MediaType | Media type. (`tv`, `radio`, `web`, `ppv`, `mobile`) |
| `outlet` | str | Outlet. |

### `records`

- **CFBD method:** `GamesApi.get_records`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `classification` | DivisionClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `expectedWins` | float | Expected wins. |
| `total` | TeamRecord | Total. — see [TeamRecord](#teamrecord) |
| `conferenceGames` | TeamRecord | Conference games. — see [TeamRecord](#teamrecord) |
| `homeGames` | TeamRecord | Home games. — see [TeamRecord](#teamrecord) |
| `awayGames` | TeamRecord | Away games. — see [TeamRecord](#teamrecord) |
| `neutralSiteGames` | TeamRecord | Neutral site games. — see [TeamRecord](#teamrecord) |
| `regularSeason` | TeamRecord | Regular season. — see [TeamRecord](#teamrecord) |
| `postseason` | TeamRecord | Postseason. — see [TeamRecord](#teamrecord) |

### `scoreboard`

- **CFBD method:** `GamesApi.get_scoreboard`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `startTimeTBD` | bool | True if kickoff time was not yet announced. |
| `tv` | str | Tv. |
| `neutralSite` | bool | True if played at a neutral (non-home) site. |
| `conferenceGame` | bool | True if both teams share a conference. |
| `status` | GameStatus | Status. (`scheduled`, `in_progress`, `completed`) |
| `period` | int | Quarter/period number. |
| `clock` | str | Game clock at the time of the play/event. |
| `situation` | str | Situation. |
| `possession` | str | Possession. |
| `lastPlay` | str | Last play. |
| `venue` | ScoreboardGameVenue | Venue name. — see [ScoreboardGameVenue](#scoreboardgamevenue) |
| `homeTeam` | ScoreboardGameHomeTeam | Home team name. — see [ScoreboardGameHomeTeam](#scoreboardgamehometeam) |
| `awayTeam` | ScoreboardGameHomeTeam | Away team name. — see [ScoreboardGameHomeTeam](#scoreboardgamehometeam) |
| `weather` | ScoreboardGameWeather | Weather. — see [ScoreboardGameWeather](#scoreboardgameweather) |
| `betting` | ScoreboardGameBetting | Betting. — see [ScoreboardGameBetting](#scoreboardgamebetting) |

### `weather`

- **CFBD method:** `GamesApi.get_weather`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startTime` | datetime | Start time. |
| `gameIndoors` | bool | Game indoors. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `venueId` | int | Venue identifier, joins to the venues endpoint. |
| `venue` | str | Venue name. |
| `temperature` | float | Temperature. |
| `dewPoint` | float | Dew point. |
| `humidity` | float | Humidity. |
| `precipitation` | float | Precipitation. |
| `snowfall` | float | Snowfall. |
| `windDirection` | float | Wind direction. |
| `windSpeed` | float | Wind speed. |
| `pressure` | float | Pressure. |
| `weatherConditionCode` | float | Weather condition code. |
| `weatherCondition` | str | Weather condition. |

## Info / account

### `user_info`

- **CFBD method:** `InfoApi.get_user_info`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `patronLevel` | float | Patron level. |
| `tierName` | str | Tier name. |
| `monthlyLimit` | float | Monthly limit. |
| `remainingCalls` | float | Remaining calls. |
| `usedCalls` | float | Used calls. |
| `resetAt` | str | Reset at. |
| `sharedPool` | bool | Shared pool. |
| `products` | List[str] | Products. |
| `features` | UserFeatureAccess | Features. — see [UserFeatureAccess](#userfeatureaccess) |

## Advanced metrics (PPA, win probability, predicted points)

### `field_goal_ep`

- **CFBD method:** `MetricsApi.get_field_goal_expected_points`
- **Scrape mode:** once (no params)

_Expected points value of attempting a field goal, by distance._

| Field | Type | Description |
|---|---|---|
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `distance` | int | Yards to go for a first down. |
| `expectedPoints` | float | Expected points. |

### `predicted_points`

- **CFBD method:** `MetricsApi.get_predicted_points`
- **Scrape mode:** down x distance grid

_Expected points value for a given down/distance (predicted-points model lookup table)._

| Field | Type | Description |
|---|---|---|
| `yardLine` | int | Yard line (0-100, own end zone to opponent's). |
| `predictedPoints` | float | Predicted points. |

### `ppa_games`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_game`
- **Scrape mode:** per season

_PPA aggregated to team-game level, split offense/defense._

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `offense` | TeamGamePredictedPointsAddedOffense | Offensive-side breakdown. — see [TeamGamePredictedPointsAddedOffense](#teamgamepredictedpointsaddedoffense) |
| `defense` | TeamGamePredictedPointsAddedOffense | Defensive-side breakdown. — see [TeamGamePredictedPointsAddedOffense](#teamgamepredictedpointsaddedoffense) |

### `ppa_players_games`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_player_game`
- **Scrape mode:** per season x week

_PPA aggregated to player-game level._

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `opponent` | str | Opponent team name. |
| `averagePPA` | PlayerGamePredictedPointsAddedAveragePPA | Average p p a. — see [PlayerGamePredictedPointsAddedAveragePPA](#playergamepredictedpointsaddedaverageppa) |

### `ppa_players_season`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_player_season`
- **Scrape mode:** per season

_PPA aggregated to player-season level._

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `averagePPA` | PlayerSeasonOverviewPPAAverage | Average p p a. — see [PlayerSeasonOverviewPPAAverage](#playerseasonoverviewppaaverage) |
| `totalPPA` | PlayerSeasonOverviewPPAAverage | Sum of PPA across plays. — see [PlayerSeasonOverviewPPAAverage](#playerseasonoverviewppaaverage) |

### `ppa_teams`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_team`
- **Scrape mode:** per season

_PPA aggregated to team-season level, split offense/defense._

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `conference` | str | Conference name. |
| `team` | str | Team name. |
| `offense` | TeamSeasonPredictedPointsAddedOffense | Offensive-side breakdown. — see [TeamSeasonPredictedPointsAddedOffense](#teamseasonpredictedpointsaddedoffense) |
| `defense` | TeamSeasonPredictedPointsAddedOffense | Defensive-side breakdown. — see [TeamSeasonPredictedPointsAddedOffense](#teamseasonpredictedpointsaddedoffense) |

### `pregame_win_prob`

- **CFBD method:** `MetricsApi.get_pregame_win_probabilities`
- **Scrape mode:** per season

_Pregame win-probability model output for a game._

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `homeTeam` | str | Home team name. |
| `awayTeam` | str | Away team name. |
| `spread` | float | Closing point spread (negative = favorite by that many points), home-team perspective unless noted. |
| `homeWinProbability` | float | Home win probability. |

### `win_probability`

- **CFBD method:** `MetricsApi.get_win_probability`
- **Scrape mode:** per game (fan-out, opt-in)

_Live win probability after each play in a game._

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `playId` | str | Play ID. |
| `playText` | str | Human-readable play description. |
| `homeId` | int | Home team identifier. |
| `home` | str | Home. |
| `awayId` | int | Away team identifier. |
| `away` | str | Away. |
| `spread` | float | Closing point spread (negative = favorite by that many points), home-team perspective unless noted. |
| `homeBall` | bool | Home ball. |
| `homeScore` | int | Home score. |
| `awayScore` | int | Away score. |
| `yardLine` | int | Yard line (0-100, own end zone to opponent's). |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `homeWinProbability` | float | Home win probability. |
| `playNumber` | int | Play number. |

### `ppa_games_ngt`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_game`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `ppa_teams_ngt`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_team`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `ppa_players_season_ngt`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_player_season`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `ppa_players_games_ngt`

- **CFBD method:** `MetricsApi.get_predicted_points_added_by_player_game`
- **Scrape mode:** per season x week

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

## Players

### `player_season_overview`

- **CFBD method:** `PlayersApi.get_player_season_overview`
- **Scrape mode:** per player (fan-out, opt-in)

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `games` | int | Games coached. |
| `boxScoreStats` | PlayerSeasonOverviewBoxScoreStats | Box score stats. — see [PlayerSeasonOverviewBoxScoreStats](#playerseasonoverviewboxscorestats) |

### `player_usage`

- **CFBD method:** `PlayersApi.get_player_usage`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `usage` | PlayerUsageUsage | Share of team plays/snaps the player was involved in, by situation. — see [PlayerUsageUsage](#playerusageusage) |

### `returning_production`

- **CFBD method:** `PlayersApi.get_returning_production`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `totalPPA` | float | Sum of PPA across plays. |
| `totalPassingPPA` | float | Total passing p p a. |
| `totalReceivingPPA` | float | Total receiving p p a. |
| `totalRushingPPA` | float | Total rushing p p a. |
| `percentPPA` | float | Percent p p a. |
| `percentPassingPPA` | float | Percent passing p p a. |
| `percentReceivingPPA` | float | Percent receiving p p a. |
| `percentRushingPPA` | float | Percent rushing p p a. |
| `usage` | float | Share of team plays/snaps the player was involved in, by situation. |
| `passingUsage` | float | Passing usage. |
| `receivingUsage` | float | Receiving usage. |
| `rushingUsage` | float | Rushing usage. |

### `transfer_portal`

- **CFBD method:** `PlayersApi.get_transfer_portal`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `position` | str | Position abbreviation. |
| `origin` | str | Origin. |
| `destination` | str | Destination. |
| `transferDate` | datetime | Transfer date. |
| `rating` | float | Composite rating score. |
| `stars` | int | Recruit star rating (1-5). |
| `eligibility` | TransferEligibility | Player eligibility/class status. (`Withdrawn`, `TBD`, `PendingAppeal`, `SittingOne`, `Immediate`) |

### `player_search`

- **CFBD method:** `PlayersApi.search_players`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `team` | str | Team name. |
| `name` | str | Name. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `weight` | int | Weight in pounds. |
| `height` | float | Height in inches. |
| `jersey` | int | Jersey number. |
| `position` | str | Position abbreviation. |
| `hometown` | str | Hometown. |
| `teamColor` | str | Team color. |
| `teamColorSecondary` | str | Team color secondary. |
| `activeStartYear` | int | Active start year. |
| `activeEndYear` | int | Active end year. |
| `teamStints` | List[PlayerSearchTeamStint] | Team stints. |

### `player_usage_ngt`

- **CFBD method:** `PlayersApi.get_player_usage`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

## Plays

### `live_plays`

- **CFBD method:** `PlaysApi.get_live_plays`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `status` | str | Status. |
| `period` | int | Quarter/period number. |
| `clock` | str | Game clock at the time of the play/event. |
| `possession` | str | Possession. |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `teams` | List[LiveGameTeam] | Teams. |
| `drives` | List[LiveGameDrive] | Number of drives. |

### `play_stat_types`

- **CFBD method:** `PlaysApi.get_play_stat_types`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |

### `play_stats`

- **CFBD method:** `PlaysApi.get_play_stats`
- **Scrape mode:** per season x week

| Field | Type | Description |
|---|---|---|
| `gameId` | float | Game identifier, joins to the games endpoint. |
| `season` | float | Season year. |
| `week` | float | Week number within the season. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `teamScore` | float | Team score. |
| `opponentScore` | float | Opponent score. |
| `driveId` | str | Drive ID. |
| `playId` | str | Play ID. |
| `period` | float | Quarter/period number. |
| `clock` | PlayStatClock | Game clock at the time of the play/event. — see [PlayStatClock](#playstatclock) |
| `yardsToGoal` | float | Yards remaining to the opponent's goal line. |
| `down` | float | Down number (1-4). |
| `distance` | float | Yards to go for a first down. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `statType` | str | Category of statistic being recorded. |
| `stat` | float | Statistic value. |

### `play_types`

- **CFBD method:** `PlaysApi.get_play_types`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `text` | str | Text. |
| `abbreviation` | str | Short abbreviation. |

### `plays`

- **CFBD method:** `PlaysApi.get_plays`
- **Scrape mode:** per season x week

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `driveId` | str | Drive ID. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `driveNumber` | int | Drive number. |
| `playNumber` | int | Play number. |
| `offense` | str | Offensive-side breakdown. |
| `offenseConference` | str | Offense team's conference. |
| `offenseScore` | int | Offense team's score at the time of the play. |
| `defense` | str | Defensive-side breakdown. |
| `home` | str | Home. |
| `away` | str | Away. |
| `defenseConference` | str | Defense team's conference. |
| `defenseScore` | int | Defense team's score at the time of the play. |
| `period` | int | Quarter/period number. |
| `clock` | PlayClock | Game clock at the time of the play/event. — see [PlayClock](#playclock) |
| `offenseTimeouts` | int | Offense timeouts. |
| `defenseTimeouts` | int | Defense timeouts. |
| `yardline` | int | Yardline. |
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `yardsGained` | int | Yards gained on the play. |
| `scoring` | bool | True if the play resulted in points. |
| `playType` | str | Play type (run/pass/punt/etc). |
| `playText` | str | Human-readable play description. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `wallclock` | str | Real-world timestamp of the event. |

## College Football Playoff (CFP)

### `cfp_playoff`

- **CFBD method:** `PlayoffsApi.get_cfp_playoff`
- **Scrape mode:** per season
- **Data floor:** no data before 2014

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `competition` | PlayoffCompetitionCfp | Competition. (`cfp`) |
| `format` | str | Format. |
| `teamCount` | int | Team count. |
| `status` | PlayoffStatus | Status. (`scheduled`, `selected`, `in_progress`, `completed`) |
| `participants` | List[PlayoffParticipant] | Participants. |
| `rounds` | List[PlayoffRoundRecord] | Rounds. |
| `champion` | PlayoffTeam | Champion. — see [PlayoffTeam](#playoffteam) |

### `cfp_games`

- **CFBD method:** `PlayoffsApi.get_cfp_games`
- **Scrape mode:** per season
- **Data floor:** no data before 2014

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `bracketSlot` | str | Bracket slot. |
| `round` | PlayoffRound | Round. (`first_round`, `quarterfinal`, `semifinal`, `championship`) |
| `roundName` | str | Round name. |
| `roundOrder` | int | Round order. |
| `matchupOrder` | int | Matchup order. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `bowlName` | str | Bowl name. |
| `slots` | List[PlayoffMatchupSlot] | Slots. |
| `game` | PlayoffLinkedGame | Game. — see [PlayoffLinkedGame](#playofflinkedgame) |
| `advancesTo` | PlayoffAdvancement | Advances to. — see [PlayoffAdvancement](#playoffadvancement) |

### `cfp_participants`

- **CFBD method:** `PlayoffsApi.get_cfp_participants`
- **Scrape mode:** per season
- **Data floor:** no data before 2014

| Field | Type | Description |
|---|---|---|
| `team` | PlayoffTeam | Team name. — see [PlayoffTeam](#playoffteam) |
| `committeeRank` | int | Committee rank. |
| `seed` | int | Seed. |
| `bidType` | PlayoffBidType | Bid type. (`automatic`, `at_large`) |
| `qualificationReason` | str | Qualification reason. |
| `conferenceChampion` | bool | Conference champion. |
| `qualifyingConference` | str | Qualifying conference. |
| `firstRoundBye` | bool | First round bye. |
| `outcome` | PlayoffOutcome | Outcome. (`active`, `eliminated`, `champion`) |
| `eliminatedRound` | PlayoffRound | Eliminated round. (`first_round`, `quarterfinal`, `semifinal`, `championship`) |

## Rankings / polls

### `rankings`

- **CFBD method:** `RankingsApi.get_rankings`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `polls` | List[Poll] | Polls. |

## Ratings (SP+, FPI, Elo, SRS)

### `conference_sp`

- **CFBD method:** `RatingsApi.get_conference_sp`
- **Scrape mode:** per season

_SP+ averaged to the conference level._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `conference` | str | Conference name. |
| `rating` | float | Composite rating score. |
| `secondOrderWins` | float | Second-order (efficiency-based expected) win total. |
| `sos` | float | Strength of schedule rating. |
| `offense` | ConferenceSPOffense | Offensive-side breakdown. — see [ConferenceSPOffense](#conferencespoffense) |
| `defense` | ConferenceSPDefense | Defensive-side breakdown. — see [ConferenceSPDefense](#conferencespdefense) |
| `specialTeams` | TeamSPSpecialTeams | Special-teams breakdown. — see [TeamSPSpecialTeams](#teamspspecialteams) |

### `elo`

- **CFBD method:** `RatingsApi.get_elo`
- **Scrape mode:** per season

_Elo rating (chess-style rating updated after each game)._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `elo` | int | Elo. |

### `fpi`

- **CFBD method:** `RatingsApi.get_fpi`
- **Scrape mode:** per season

_ESPN's Football Power Index rating._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `fpi` | float | FPI. |
| `resumeRanks` | TeamFPIResumeRanks | Resume ranks. — see [TeamFPIResumeRanks](#teamfpiresumeranks) |
| `efficiencies` | TeamFPIEfficiencies | Efficiencies. — see [TeamFPIEfficiencies](#teamfpiefficiencies) |

### `sp`

- **CFBD method:** `RatingsApi.get_sp`
- **Scrape mode:** per season

_Bill Connelly's SP+ rating: predictive team strength on a scale where 0 is average._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `secondOrderWins` | float | Second-order (efficiency-based expected) win total. |
| `sos` | float | Strength of schedule rating. |
| `offense` | TeamSPOffense | Offensive-side breakdown. — see [TeamSPOffense](#teamspoffense) |
| `defense` | TeamSPDefense | Defensive-side breakdown. — see [TeamSPDefense](#teamspdefense) |
| `specialTeams` | TeamSPSpecialTeams | Special-teams breakdown. — see [TeamSPSpecialTeams](#teamspspecialteams) |

### `srs`

- **CFBD method:** `RatingsApi.get_srs`
- **Scrape mode:** per season

_Simple Rating System: margin-of-victory rating adjusted for strength of schedule._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |

### `core_ratings`

- **CFBD method:** `RatingsApi.get_core`
- **Scrape mode:** per season

_CFBD's blended "core" rating combining multiple underlying models._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `throughSeasonType` | CoreRatingSeasonType | Through season type. (`regular`, `postseason`) |
| `throughWeek` | int | Through week. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `overall` | float | Overall (combined) rating. |
| `offense` | float | Offensive-side breakdown. |
| `defense` | float | Defensive-side breakdown. |
| `offensePlays` | int | Offense plays. |
| `defensePlays` | int | Defense plays. |
| `modelVersion` | str | Model version. |

### `srs_expanded`

- **CFBD method:** `RatingsApi.get_expanded_srs`
- **Scrape mode:** per season

_SRS including FCS opponents, with additional sub-components._

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `classification` | DivisionClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |

## Recruiting

### `recruiting_groups`

- **CFBD method:** `RecruitingApi.get_aggregated_team_recruiting_ratings`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `positionGroup` | str | Position group. |
| `averageRating` | float | Average rating. |
| `totalRating` | float | Total rating. |
| `commits` | int | Commits. |
| `averageStars` | float | Average stars. |

### `recruits`

- **CFBD method:** `RecruitingApi.get_recruits`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `athleteId` | str | Player identifier. |
| `recruitType` | RecruitClassification | Recruit type (HighSchool/JUCO/PrepSchool/Transfer). (`JUCO`, `PrepSchool`, `HighSchool`) |
| `year` | int | Season year. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `name` | str | Name. |
| `school` | str | School coached. |
| `committedTo` | str | School the recruit committed to. |
| `position` | str | Position abbreviation. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `stars` | int | Recruit star rating (1-5). |
| `rating` | float | Composite rating score. |
| `city` | str | City name. |
| `stateProvince` | str | State province. |
| `country` | str | Country. |
| `hometownInfo` | RecruitHometownInfo | Recruit's hometown details. — see [RecruitHometownInfo](#recruithometowninfo) |

### `recruiting_teams`

- **CFBD method:** `RecruitingApi.get_team_recruiting_rankings`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `rank` | int | Rank (1 = best) within the given scope. |
| `team` | str | Team name. |
| `points` | float | Points value for this rating component. |

## Stats

### `advanced_game_stats`

- **CFBD method:** `StatsApi.get_advanced_game_stats`
- **Scrape mode:** per season

_Per-game advanced efficiency stats (PPA, success rate, explosiveness, line yards, havoc) split by offense/defense and situation (standard downs / passing downs / rushing / passing)._

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `team` | str | Team name. |
| `opponent` | str | Opponent team name. |
| `offense` | AdvancedGameStatOffense | Offensive-side breakdown. — see [AdvancedGameStatOffense](#advancedgamestatoffense) |
| `defense` | AdvancedGameStatDefense | Defensive-side breakdown. — see [AdvancedGameStatDefense](#advancedgamestatdefense) |

### `advanced_season_stats`

- **CFBD method:** `StatsApi.get_advanced_season_stats`
- **Scrape mode:** per season

_Season-aggregated version of AdvancedGameStat._

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `offense` | AdvancedSeasonStatOffense | Offensive-side breakdown. — see [AdvancedSeasonStatOffense](#advancedseasonstatoffense) |
| `defense` | AdvancedSeasonStatDefense | Defensive-side breakdown. — see [AdvancedSeasonStatDefense](#advancedseasonstatdefense) |

### `stat_categories`

- **CFBD method:** `StatsApi.get_categories`
- **Scrape mode:** once (no params)

Returns `List[str]` — a plain list of values, no object fields.

### `game_havoc_stats`

- **CFBD method:** `StatsApi.get_game_havoc_stats`
- **Scrape mode:** per season

_Havoc-rate breakdown (TFL/FF/PBU/INT share) for a game._

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `opponentConference` | str | Opponent conference. |
| `offense` | GameHavocStatsOffense | Offensive-side breakdown. — see [GameHavocStatsOffense](#gamehavocstatsoffense) |
| `defense` | GameHavocStatsOffense | Defensive-side breakdown. — see [GameHavocStatsOffense](#gamehavocstatsoffense) |

### `player_season_stats`

- **CFBD method:** `StatsApi.get_player_season_stats`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `playerId` | str | Player ID. |
| `player` | str | Player. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `category` | str | Statistic category/group. |
| `statType` | str | Category of statistic being recorded. |
| `stat` | str | Statistic value. |

### `player_success_season`

- **CFBD method:** `StatsApi.get_player_season_success_rates`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `passing` | PlayerSuccessRateSplit | Passing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |
| `rushing` | PlayerSuccessRateSplit | Rushing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |

### `player_success_game`

- **CFBD method:** `StatsApi.get_player_game_success_rates`
- **Scrape mode:** per season x week

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `passing` | PlayerSuccessRateSplit | Passing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |
| `rushing` | PlayerSuccessRateSplit | Rushing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |

### `team_stats`

- **CFBD method:** `StatsApi.get_team_stats`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `statName` | str | Stat name. |
| `statValue` | TeamStatStatValue | Stat value. — see [TeamStatStatValue](#teamstatstatvalue) |

### `advanced_game_stats_ngt`

- **CFBD method:** `StatsApi.get_advanced_game_stats`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `advanced_season_stats_ngt`

- **CFBD method:** `StatsApi.get_advanced_season_stats`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `player_success_season_ngt`

- **CFBD method:** `StatsApi.get_player_season_success_rates`
- **Scrape mode:** per season

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

### `player_success_game_ngt`

- **CFBD method:** `StatsApi.get_player_game_success_rates`
- **Scrape mode:** per season x week

Same schema as its base endpoint above. `excludeGarbageTime=true` — drops garbage-time plays before aggregating, so values differ from the unfiltered twin.

## Teams

### `fbs_teams`

- **CFBD method:** `TeamsApi.get_fbs_teams`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |
| `mascot` | str | Team mascot name. |
| `abbreviation` | str | Short abbreviation. |
| `alternateNames` | List[str] | Alternate names. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `classification` | str | Division classification (FBS/FCS/II/III). |
| `color` | str | Primary brand color (hex). |
| `alternateColor` | str | Alternate color. |
| `logos` | List[str] | Logo image URLs. |
| `twitter` | str | Twitter/X handle. |
| `location` | Venue | Location details (city/state/lat/lon). — see [Venue](#venue) |

### `matchup`

- **CFBD method:** `TeamsApi.get_matchup`
- **Scrape mode:** on-demand (not bulk-scraped)

| Field | Type | Description |
|---|---|---|
| `team1` | str | Team1. |
| `team2` | str | Team2. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |
| `team1Wins` | int | Team1 wins. |
| `team2Wins` | int | Team2 wins. |
| `ties` | int | Tie count. |
| `games` | List[MatchupGame] | Games coached. |

### `roster`

- **CFBD method:** `TeamsApi.get_roster`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `team` | str | Team name. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `jersey` | int | Jersey number. |
| `year` | int | Season year. |
| `position` | str | Position abbreviation. |
| `homeCity` | str | Home city. |
| `homeState` | str | Home state. |
| `homeCountry` | str | Home country. |
| `homeLatitude` | float | Home latitude. |
| `homeLongitude` | float | Home longitude. |
| `homeCountyFIPS` | str | Home county f i p s. |
| `recruitIds` | List[str] | Recruit IDs. |

### `talent`

- **CFBD method:** `TeamsApi.get_talent`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `talent` | float | Talent. |

### `teams`

- **CFBD method:** `TeamsApi.get_teams`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |
| `mascot` | str | Team mascot name. |
| `abbreviation` | str | Short abbreviation. |
| `alternateNames` | List[str] | Alternate names. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `classification` | str | Division classification (FBS/FCS/II/III). |
| `color` | str | Primary brand color (hex). |
| `alternateColor` | str | Alternate color. |
| `logos` | List[str] | Logo image URLs. |
| `twitter` | str | Twitter/X handle. |
| `location` | Venue | Location details (city/state/lat/lon). — see [Venue](#venue) |

### `teams_ats`

- **CFBD method:** `TeamsApi.get_teams_ats`
- **Scrape mode:** per season

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `games` | int | Games coached. |
| `atsWins` | int | Ats wins. |
| `atsLosses` | int | Ats losses. |
| `atsPushes` | int | Ats pushes. |
| `avgCoverMargin` | float | Avg cover margin. |

## Venues

### `venues`

- **CFBD method:** `VenuesApi.get_venues`
- **Scrape mode:** once (no params)

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |
| `city` | str | City name. |
| `state` | str | State/province abbreviation. |
| `zip` | str | Postal code. |
| `countryCode` | str | ISO country code. |
| `timezone` | str | IANA timezone name. |
| `latitude` | float | Latitude in decimal degrees. |
| `longitude` | float | Longitude in decimal degrees. |
| `elevation` | str | Elevation in feet. |
| `capacity` | int | Stadium capacity. |
| `constructionYear` | int | Year the venue was built. |

## Not bulk-scraped

`/info/usage` (`InfoApi.get_usage`) is registered in the live spec but has no scraper entry — it reports API account metering (request counts), not football data. See `docs/data-coverage.md` for the full rationale.

## Nested / shared types

Object and enum types referenced by the response fields above, expanded once here instead of repeating inline.

### AdjustedTeamMetrics

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `epa` | AdjustedTeamMetricsEpa | Expected Points Added — value of a play/drive/game in expected-points terms. — see [AdjustedTeamMetricsEpa](#adjustedteammetricsepa) |
| `epaAllowed` | AdjustedTeamMetricsEpa | Expected Points Added allowed (defensive perspective). — see [AdjustedTeamMetricsEpa](#adjustedteammetricsepa) |
| `successRate` | AdjustedTeamMetricsSuccessRate | Success rate. — see [AdjustedTeamMetricsSuccessRate](#adjustedteammetricssuccessrate) |
| `successRateAllowed` | AdjustedTeamMetricsSuccessRate | Success rate allowed. — see [AdjustedTeamMetricsSuccessRate](#adjustedteammetricssuccessrate) |
| `rushing` | AdjustedTeamMetricsRushing | Rushing. — see [AdjustedTeamMetricsRushing](#adjustedteammetricsrushing) |
| `rushingAllowed` | AdjustedTeamMetricsRushing | Rushing allowed. — see [AdjustedTeamMetricsRushing](#adjustedteammetricsrushing) |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `explosivenessAllowed` | float | Explosiveness allowed. |

### AdjustedTeamMetricsEpa

| Field | Type | Description |
|---|---|---|
| `rushing` | float | Rushing. |
| `passing` | float | Passing. |
| `total` | float | Total. |

### AdjustedTeamMetricsRushing

| Field | Type | Description |
|---|---|---|
| `highlightYards` | float | Highlight yards. |
| `openFieldYards` | float | Run yards gained 10+ yards past the line of scrimmage. |
| `secondLevelYards` | float | Run yards gained 5-10 yards past the line of scrimmage. |
| `lineYards` | float | Yards attributable to the offensive line on run plays (Football Outsiders-style stat). |

### AdjustedTeamMetricsSuccessRate

| Field | Type | Description |
|---|---|---|
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `total` | float | Total. |

### AdvancedBoxScore

| Field | Type | Description |
|---|---|---|
| `gameInfo` | AdvancedBoxScoreGameInfo | Game info. — see [AdvancedBoxScoreGameInfo](#advancedboxscoregameinfo) |
| `teams` | AdvancedBoxScoreTeams | Teams. — see [AdvancedBoxScoreTeams](#advancedboxscoreteams) |
| `players` | AdvancedBoxScorePlayers | Players. — see [AdvancedBoxScorePlayers](#advancedboxscoreplayers) |

### AdvancedBoxScoreGameInfo

| Field | Type | Description |
|---|---|---|
| `excitement` | float | Excitement. |
| `homeWinner` | bool | Home winner. |
| `awayWinProb` | float | Away win prob. |
| `awayPoints` | int | Away team's final score. |
| `awayTeam` | str | Away team name. |
| `homeWinProb` | float | Home win prob. |
| `homePoints` | int | Home team's final score. |
| `homeTeam` | str | Home team name. |

### AdvancedBoxScorePlayers

| Field | Type | Description |
|---|---|---|
| `ppa` | List[PlayerPPA] | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `usage` | List[PlayerGameUsage] | Share of team plays/snaps the player was involved in, by situation. |

### AdvancedBoxScoreTeams

| Field | Type | Description |
|---|---|---|
| `fieldPosition` | List[TeamFieldPosition] | Field position. |
| `scoringOpportunities` | List[TeamScoringOpportunities] | Scoring opportunities. |
| `havoc` | List[TeamHavoc] | Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception. |
| `rushing` | List[TeamRushingStats] | Rushing. |
| `explosiveness` | List[TeamExplosiveness] | Average PPA on successful plays — a measure of big-play ability. |
| `successRates` | List[TeamSuccessRates] | Success rates. |
| `cumulativePpa` | List[TeamPPA] | Cumulative PPA. |
| `ppa` | List[TeamPPA] | Predicted Points Added — CFBD's play-value metric, similar to EPA. |

### AdvancedGameStat

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `team` | str | Team name. |
| `opponent` | str | Opponent team name. |
| `offense` | AdvancedGameStatOffense | Offensive-side breakdown. — see [AdvancedGameStatOffense](#advancedgamestatoffense) |
| `defense` | AdvancedGameStatDefense | Defensive-side breakdown. — see [AdvancedGameStatDefense](#advancedgamestatdefense) |

### AdvancedGameStatDefense

| Field | Type | Description |
|---|---|---|
| `passingPlays` | AdvancedGameStatOffensePassingPlays | Passing plays. — see [AdvancedGameStatOffensePassingPlays](#advancedgamestatoffensepassingplays) |
| `rushingPlays` | AdvancedGameStatOffensePassingPlays | Rushing plays. — see [AdvancedGameStatOffensePassingPlays](#advancedgamestatoffensepassingplays) |
| `passingDowns` | AdvancedGameStatOffensePassingDowns | Passing downs. — see [AdvancedGameStatOffensePassingDowns](#advancedgamestatoffensepassingdowns) |
| `standardDowns` | AdvancedGameStatOffensePassingDowns | Standard downs. — see [AdvancedGameStatOffensePassingDowns](#advancedgamestatoffensepassingdowns) |
| `openFieldYardsTotal` | int | Open field yards total. |
| `openFieldYards` | float | Run yards gained 10+ yards past the line of scrimmage. |
| `secondLevelYardsTotal` | int | Second level yards total. |
| `secondLevelYards` | float | Run yards gained 5-10 yards past the line of scrimmage. |
| `lineYardsTotal` | int | Line yards total. |
| `lineYards` | float | Yards attributable to the offensive line on run plays (Football Outsiders-style stat). |
| `stuffRate` | float | Share of opponent run plays stopped at or behind the line of scrimmage. |
| `powerSuccess` | float | Power success. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `drives` | int | Number of drives. |
| `plays` | int | Number of plays. |

### AdvancedGameStatOffense

| Field | Type | Description |
|---|---|---|
| `passingPlays` | AdvancedGameStatOffensePassingPlays | Passing plays. — see [AdvancedGameStatOffensePassingPlays](#advancedgamestatoffensepassingplays) |
| `rushingPlays` | AdvancedGameStatOffensePassingPlays | Rushing plays. — see [AdvancedGameStatOffensePassingPlays](#advancedgamestatoffensepassingplays) |
| `passingDowns` | AdvancedGameStatOffensePassingDowns | Passing downs. — see [AdvancedGameStatOffensePassingDowns](#advancedgamestatoffensepassingdowns) |
| `standardDowns` | AdvancedGameStatOffensePassingDowns | Standard downs. — see [AdvancedGameStatOffensePassingDowns](#advancedgamestatoffensepassingdowns) |
| `openFieldYardsTotal` | int | Open field yards total. |
| `openFieldYards` | float | Run yards gained 10+ yards past the line of scrimmage. |
| `secondLevelYardsTotal` | int | Second level yards total. |
| `secondLevelYards` | float | Run yards gained 5-10 yards past the line of scrimmage. |
| `lineYardsTotal` | int | Line yards total. |
| `lineYards` | float | Yards attributable to the offensive line on run plays (Football Outsiders-style stat). |
| `stuffRate` | float | Share of opponent run plays stopped at or behind the line of scrimmage. |
| `powerSuccess` | float | Power success. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `drives` | int | Number of drives. |
| `plays` | int | Number of plays. |

### AdvancedGameStatOffensePassingDowns

| Field | Type | Description |
|---|---|---|
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |

### AdvancedGameStatOffensePassingPlays

| Field | Type | Description |
|---|---|---|
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |

### AdvancedSeasonStat

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `offense` | AdvancedSeasonStatOffense | Offensive-side breakdown. — see [AdvancedSeasonStatOffense](#advancedseasonstatoffense) |
| `defense` | AdvancedSeasonStatDefense | Defensive-side breakdown. — see [AdvancedSeasonStatDefense](#advancedseasonstatdefense) |

### AdvancedSeasonStatDefense

| Field | Type | Description |
|---|---|---|
| `passingPlays` | AdvancedSeasonStatOffensePassingPlays | Passing plays. — see [AdvancedSeasonStatOffensePassingPlays](#advancedseasonstatoffensepassingplays) |
| `rushingPlays` | AdvancedSeasonStatOffensePassingPlays | Rushing plays. — see [AdvancedSeasonStatOffensePassingPlays](#advancedseasonstatoffensepassingplays) |
| `passingDowns` | AdvancedSeasonStatOffensePassingPlays | Passing downs. — see [AdvancedSeasonStatOffensePassingPlays](#advancedseasonstatoffensepassingplays) |
| `standardDowns` | AdvancedSeasonStatOffensePassingDowns | Standard downs. — see [AdvancedSeasonStatOffensePassingDowns](#advancedseasonstatoffensepassingdowns) |
| `havoc` | AdvancedSeasonStatOffenseHavoc | Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception. — see [AdvancedSeasonStatOffenseHavoc](#advancedseasonstatoffensehavoc) |
| `fieldPosition` | AdvancedSeasonStatOffenseFieldPosition | Field position. — see [AdvancedSeasonStatOffenseFieldPosition](#advancedseasonstatoffensefieldposition) |
| `pointsPerOpportunity` | float | Points per opportunity. |
| `totalOpportunies` | int | Total opportunies. |
| `openFieldYardsTotal` | int | Open field yards total. |
| `openFieldYards` | float | Run yards gained 10+ yards past the line of scrimmage. |
| `secondLevelYardsTotal` | int | Second level yards total. |
| `secondLevelYards` | float | Run yards gained 5-10 yards past the line of scrimmage. |
| `lineYardsTotal` | int | Line yards total. |
| `lineYards` | float | Yards attributable to the offensive line on run plays (Football Outsiders-style stat). |
| `stuffRate` | float | Share of opponent run plays stopped at or behind the line of scrimmage. |
| `powerSuccess` | float | Power success. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `drives` | int | Number of drives. |
| `plays` | int | Number of plays. |

### AdvancedSeasonStatOffense

| Field | Type | Description |
|---|---|---|
| `passingPlays` | AdvancedSeasonStatOffensePassingPlays | Passing plays. — see [AdvancedSeasonStatOffensePassingPlays](#advancedseasonstatoffensepassingplays) |
| `rushingPlays` | AdvancedSeasonStatOffensePassingPlays | Rushing plays. — see [AdvancedSeasonStatOffensePassingPlays](#advancedseasonstatoffensepassingplays) |
| `passingDowns` | AdvancedSeasonStatOffensePassingDowns | Passing downs. — see [AdvancedSeasonStatOffensePassingDowns](#advancedseasonstatoffensepassingdowns) |
| `standardDowns` | AdvancedSeasonStatOffensePassingDowns | Standard downs. — see [AdvancedSeasonStatOffensePassingDowns](#advancedseasonstatoffensepassingdowns) |
| `havoc` | AdvancedSeasonStatOffenseHavoc | Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception. — see [AdvancedSeasonStatOffenseHavoc](#advancedseasonstatoffensehavoc) |
| `fieldPosition` | AdvancedSeasonStatOffenseFieldPosition | Field position. — see [AdvancedSeasonStatOffenseFieldPosition](#advancedseasonstatoffensefieldposition) |
| `pointsPerOpportunity` | float | Points per opportunity. |
| `totalOpportunies` | int | Total opportunies. |
| `openFieldYardsTotal` | int | Open field yards total. |
| `openFieldYards` | float | Run yards gained 10+ yards past the line of scrimmage. |
| `secondLevelYardsTotal` | int | Second level yards total. |
| `secondLevelYards` | float | Run yards gained 5-10 yards past the line of scrimmage. |
| `lineYardsTotal` | int | Line yards total. |
| `lineYards` | float | Yards attributable to the offensive line on run plays (Football Outsiders-style stat). |
| `stuffRate` | float | Share of opponent run plays stopped at or behind the line of scrimmage. |
| `powerSuccess` | float | Power success. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `drives` | int | Number of drives. |
| `plays` | int | Number of plays. |

### AdvancedSeasonStatOffenseFieldPosition

| Field | Type | Description |
|---|---|---|
| `averagePredictedPoints` | float | Average predicted points. |
| `averageStart` | float | Average start. |

### AdvancedSeasonStatOffenseHavoc

| Field | Type | Description |
|---|---|---|
| `db` | float | Havoc rate credited to defensive backs specifically. |
| `frontSeven` | float | Front seven. |
| `total` | float | Total. |

### AdvancedSeasonStatOffensePassingDowns

| Field | Type | Description |
|---|---|---|
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `rate` | float | Rate. |

### AdvancedSeasonStatOffensePassingPlays

| Field | Type | Description |
|---|---|---|
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `successRate` | float | Success rate. |
| `totalPPA` | float | Sum of PPA across plays. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `rate` | float | Rate. |

### AggregatedTeamRecruiting

| Field | Type | Description |
|---|---|---|
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `positionGroup` | str | Position group. |
| `averageRating` | float | Average rating. |
| `totalRating` | float | Total rating. |
| `commits` | int | Commits. |
| `averageStars` | float | Average stars. |

### BettingGame

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `homeTeamId` | int | Home team ID. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `homeClassification` | DivisionClassification | Home team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `homeScore` | int | Home score. |
| `awayTeamId` | int | Away team ID. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `awayClassification` | DivisionClassification | Away team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `awayScore` | int | Away score. |
| `lines` | List[GameLine] | Lines. |

### CalendarWeek

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `endDate` | datetime | End date. |
| `firstGameStart` | datetime | First game start. |
| `lastGameStart` | datetime | Last game start. |

### CfpCoachSeasonOutcome

Enum values: `active`, `eliminated`, `champion`

### CfpPlayoff

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `competition` | PlayoffCompetitionCfp | Competition. (`cfp`) |
| `format` | str | Format. |
| `teamCount` | int | Team count. |
| `status` | PlayoffStatus | Status. (`scheduled`, `selected`, `in_progress`, `completed`) |
| `participants` | List[PlayoffParticipant] | Participants. |
| `rounds` | List[PlayoffRoundRecord] | Rounds. |
| `champion` | PlayoffTeam | Champion. — see [PlayoffTeam](#playoffteam) |

### Coach

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `hireDate` | datetime | Date the coach was hired. |
| `seasons` | List[CoachSeason] | Seasons. |

### CoachAlmaMater

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |

### CoachCareer

| Field | Type | Description |
|---|---|---|
| `games` | int | Games coached. |
| `wins` | int | Win count. |
| `losses` | int | Loss count. |
| `ties` | int | Tie count. |
| `winPercentage` | float | Win percentage. |
| `seasons` | int | Seasons. |
| `teams` | int | Teams. |
| `firstYear` | int | First year. |
| `lastYear` | int | Last year. |

### CoachCfpContext

| Field | Type | Description |
|---|---|---|
| `appeared` | bool | Appeared. |
| `seed` | int | Seed. |
| `outcome` | CfpCoachSeasonOutcome | Outcome. (`active`, `eliminated`, `champion`) |

### CoachDraftContext

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `totalPicks` | int | Total picks. |
| `firstRoundPicks` | int | First round picks. |

### CoachPollResume

| Field | Type | Description |
|---|---|---|
| `preseasonRank` | int | Preseason poll rank. |
| `postseasonRank` | int | Final/postseason poll rank. |
| `bestRank` | int | Best rank. |
| `weeksRanked` | int | Weeks ranked. |
| `weeksTopTen` | int | Weeks top ten. |

### CoachProfile

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `displayName` | str | Full display name. |
| `currentTeam` | CoachSeasonTeamReference | Current team. — see [CoachSeasonTeamReference](#coachseasonteamreference) |
| `career` | CoachCareer | Career. — see [CoachCareer](#coachcareer) |
| `birthDate` | str | Birth date. |
| `almaMater` | CoachAlmaMater | Alma mater. — see [CoachAlmaMater](#coachalmamater) |
| `graduationYear` | int | Graduation year. |
| `wikidataId` | str | Wikidata ID. |
| `hallOfFameYear` | int | Hall of fame year. |

### CoachRatingContext

| Field | Type | Description |
|---|---|---|
| `spSpecialTeams` | float | SP+ special teams. |
| `strengthOfSchedule` | float | Strength of schedule. |
| `secondOrderWins` | float | Second-order (efficiency-based expected) win total. |
| `fpi` | float | FPI. |
| `yearOverYear` | CoachRatingContextYearOverYear | Year over year. — see [CoachRatingContextYearOverYear](#coachratingcontextyearoveryear) |

### CoachRatingContextYearOverYear

| Field | Type | Description |
|---|---|---|
| `spOverall` | float | SP+ overall. |
| `srs` | float | SRS. |
| `wins` | int | Win count. |

### CoachRecord

| Field | Type | Description |
|---|---|---|
| `games` | int | Games coached. |
| `wins` | int | Win count. |
| `losses` | int | Loss count. |
| `ties` | int | Tie count. |
| `winPercentage` | float | Win percentage. |

### CoachRecordSplits

| Field | Type | Description |
|---|---|---|
| `conference` | CoachRecord | Conference name. — see [CoachRecord](#coachrecord) |
| `postseason` | CoachRecord | Postseason. — see [CoachRecord](#coachrecord) |
| `home` | CoachRecord | Home. — see [CoachRecord](#coachrecord) |
| `away` | CoachRecord | Away. — see [CoachRecord](#coachrecord) |
| `neutral` | CoachRecord | Neutral. — see [CoachRecord](#coachrecord) |

### CoachRecruitingContext

| Field | Type | Description |
|---|---|---|
| `rank` | int | Rank (1 = best) within the given scope. |
| `points` | float | Points value for this rating component. |
| `talent` | float | Talent. |

### CoachReference

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |

### CoachScoring

| Field | Type | Description |
|---|---|---|
| `pointsFor` | int | Points for. |
| `pointsAgainst` | int | Points against. |
| `averagePointDifferential` | float | Average point differential. |

### CoachSeasonTeamReference

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |
| `conference` | str | Conference name. |

### CoachTeamReference

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |

### CoachTenure

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `coach` | CoachReference | Coach name. — see [CoachReference](#coachreference) |
| `team` | CoachTeamReference | Team name. — see [CoachTeamReference](#coachteamreference) |
| `hireDate` | str | Date the coach was hired. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |
| `effectiveStart` | datetime | Effective start. |
| `effectiveEnd` | datetime | Effective end. |
| `isInterim` | bool | Is interim. |
| `active` | bool | Active. |
| `seasons` | int | Seasons. |
| `record` | CoachRecord | Record. — see [CoachRecord](#coachrecord) |
| `attributionComplete` | bool | Attribution complete. |

### Conference

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |
| `shortName` | str | Short name. |
| `abbreviation` | str | Short abbreviation. |
| `classification` | ConferenceClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `memberCount` | int | Member count. |

### ConferenceClassification

Enum values: `fbs`, `fcs`, `ii`, `ii/iii`, `iii`

### ConferenceSP

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `conference` | str | Conference name. |
| `rating` | float | Composite rating score. |
| `secondOrderWins` | float | Second-order (efficiency-based expected) win total. |
| `sos` | float | Strength of schedule rating. |
| `offense` | ConferenceSPOffense | Offensive-side breakdown. — see [ConferenceSPOffense](#conferencespoffense) |
| `defense` | ConferenceSPDefense | Defensive-side breakdown. — see [ConferenceSPDefense](#conferencespdefense) |
| `specialTeams` | TeamSPSpecialTeams | Special-teams breakdown. — see [TeamSPSpecialTeams](#teamspspecialteams) |

### ConferenceSPDefense

| Field | Type | Description |
|---|---|---|
| `havoc` | AdvancedSeasonStatOffenseHavoc | Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception. — see [AdvancedSeasonStatOffenseHavoc](#advancedseasonstatoffensehavoc) |
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `passing` | float | Passing. |
| `rushing` | float | Rushing. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `success` | float | Success rate — share of plays gaining enough yardage to be an on-schedule down (per Football Outsiders rules). |
| `rating` | float | Composite rating score. |

### ConferenceSPOffense

| Field | Type | Description |
|---|---|---|
| `pace` | float | Plays run per minute of possession (tempo). |
| `runRate` | float | Run rate. |
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `passing` | float | Passing. |
| `rushing` | float | Rushing. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `success` | float | Success rate — share of plays gaining enough yardage to be an on-schedule down (per Football Outsiders rules). |
| `rating` | float | Composite rating score. |

### CoreRatingSeasonType

Enum values: `regular`, `postseason`

### DetailedCoachSeason

| Field | Type | Description |
|---|---|---|
| `games` | int | Games coached. |
| `wins` | int | Win count. |
| `losses` | int | Loss count. |
| `ties` | int | Tie count. |
| `winPercentage` | float | Win percentage. |
| `coach` | CoachReference | Coach name. — see [CoachReference](#coachreference) |
| `team` | CoachSeasonTeamReference | Team name. — see [CoachSeasonTeamReference](#coachseasonteamreference) |
| `year` | int | Season year. |
| `preseasonRank` | int | Preseason poll rank. |
| `postseasonRank` | int | Final/postseason poll rank. |
| `srs` | float | SRS. |
| `spOverall` | float | SP+ overall. |
| `spOffense` | float | SP+ offense. |
| `spDefense` | float | SP+ defense. |
| `teamMetrics` | CoachRatingContext | Team metrics. — see [CoachRatingContext](#coachratingcontext) |
| `recruiting` | CoachRecruitingContext | Recruiting. — see [CoachRecruitingContext](#coachrecruitingcontext) |
| `pollResume` | CoachPollResume | Poll resume. — see [CoachPollResume](#coachpollresume) |
| `attributionComplete` | bool | Attribution complete. |
| `recordSplits` | CoachRecordSplits | Record splits. — see [CoachRecordSplits](#coachrecordsplits) |
| `scoring` | CoachScoring | True if the play resulted in points. — see [CoachScoring](#coachscoring) |
| `cfp` | CoachCfpContext | Cfp. — see [CoachCfpContext](#coachcfpcontext) |
| `draftFollowingSeason` | CoachDraftContext | Draft following season. — see [CoachDraftContext](#coachdraftcontext) |

### DivisionClassification

Enum values: `fbs`, `fcs`, `ii`, `ii/iii`, `iii`

### DraftPick

| Field | Type | Description |
|---|---|---|
| `collegeAthleteId` | int | College player identifier. |
| `nflAthleteId` | int | NFL.com player identifier. |
| `collegeId` | int | College ID. |
| `collegeTeam` | str | College the player was drafted from. |
| `collegeConference` | str | College conference the player was drafted from. |
| `nflTeamId` | int | Nfl team ID. |
| `nflTeam` | str | NFL team that drafted the player. |
| `year` | int | Season year. |
| `overall` | int | Overall (combined) rating. |
| `round` | int | Round. |
| `pick` | int | Overall draft pick number. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `preDraftRanking` | int | Pre draft ranking. |
| `preDraftPositionRanking` | int | Pre draft position ranking. |
| `preDraftGrade` | int | Pre draft grade. |
| `hometownInfo` | DraftPickHometownInfo | Recruit's hometown details. — see [DraftPickHometownInfo](#draftpickhometowninfo) |

### DraftPickHometownInfo

| Field | Type | Description |
|---|---|---|
| `countyFips` | str | County fips. |
| `longitude` | str | Longitude in decimal degrees. |
| `latitude` | str | Latitude in decimal degrees. |
| `country` | str | Country. |
| `state` | str | State/province abbreviation. |
| `city` | str | City name. |

### DraftPosition

| Field | Type | Description |
|---|---|---|
| `name` | str | Name. |
| `abbreviation` | str | Short abbreviation. |

### DraftTeam

| Field | Type | Description |
|---|---|---|
| `location` | str | Location details (city/state/lat/lon). |
| `nickname` | str | Nickname. |
| `displayName` | str | Full display name. |
| `logo` | str | Logo. |

### Drive

| Field | Type | Description |
|---|---|---|
| `offense` | str | Offensive-side breakdown. |
| `offenseConference` | str | Offense team's conference. |
| `defense` | str | Defensive-side breakdown. |
| `defenseConference` | str | Defense team's conference. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `id` | str | Unique identifier for the record. |
| `driveNumber` | int | Drive number. |
| `scoring` | bool | True if the play resulted in points. |
| `startPeriod` | int | Start period. |
| `startYardline` | int | Start yardline. |
| `startYardsToGoal` | int | Start yards to goal. |
| `startTime` | PlayClock | Start time. — see [PlayClock](#playclock) |
| `endPeriod` | int | End period. |
| `endYardline` | int | End yardline. |
| `endYardsToGoal` | int | End yards to goal. |
| `endTime` | PlayClock | End time. — see [PlayClock](#playclock) |
| `elapsed` | PlayClock | Elapsed. — see [PlayClock](#playclock) |
| `plays` | int | Number of plays. |
| `yards` | int | Yards. |
| `driveResult` | str | Drive result. |
| `isHomeOffense` | bool | Is home offense. |
| `startOffenseScore` | int | Start offense score. |
| `startDefenseScore` | int | Start defense score. |
| `endOffenseScore` | int | End offense score. |
| `endDefenseScore` | int | End defense score. |

### ExpandedTeamSRS

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `classification` | DivisionClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |

### FieldGoalEP

| Field | Type | Description |
|---|---|---|
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `distance` | int | Yards to go for a first down. |
| `expectedPoints` | float | Expected points. |

### Game

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `startTimeTBD` | bool | True if kickoff time was not yet announced. |
| `completed` | bool | True once the game has finished. |
| `neutralSite` | bool | True if played at a neutral (non-home) site. |
| `conferenceGame` | bool | True if both teams share a conference. |
| `attendance` | int | Reported attendance. |
| `venueId` | int | Venue identifier, joins to the venues endpoint. |
| `venue` | str | Venue name. |
| `homeId` | int | Home team identifier. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `homeClassification` | DivisionClassification | Home team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `homePoints` | int | Home team's final score. |
| `homeLineScores` | List[Union[float] | Home team's score by quarter/period. |
| `homePostgameWinProbability` | float | Model-estimated home win probability after the game. |
| `homePregameElo` | int | Home team's Elo rating entering the game. |
| `homePostgameElo` | int | Home team's Elo rating after the game. |
| `awayId` | int | Away team identifier. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `awayClassification` | DivisionClassification | Away team's division (FBS/FCS/etc). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `awayPoints` | int | Away team's final score. |
| `awayLineScores` | List[Union[float] | Away team's score by quarter/period. |
| `awayPostgameWinProbability` | float | Model-estimated away win probability after the game. |
| `awayPregameElo` | int | Away team's Elo rating entering the game. |
| `awayPostgameElo` | int | Away team's Elo rating after the game. |
| `excitementIndex` | float | CFBD's game-excitement metric, derived from win-probability swings. |
| `highlights` | str | Highlight video URL, if available. |
| `notes` | str | Free-text notes about the game (e.g. bowl name). |
| `playoff` | GamePlayoff | Playoff context for the game (round/bracket), if applicable. — see [GamePlayoff](#gameplayoff) |

### GameHavocStats

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `opponentConference` | str | Opponent conference. |
| `offense` | GameHavocStatsOffense | Offensive-side breakdown. — see [GameHavocStatsOffense](#gamehavocstatsoffense) |
| `defense` | GameHavocStatsOffense | Defensive-side breakdown. — see [GameHavocStatsOffense](#gamehavocstatsoffense) |

### GameHavocStatsOffense

| Field | Type | Description |
|---|---|---|
| `dbHavocRate` | float | Db havoc rate. |
| `frontSevenHavocRate` | float | Front seven havoc rate. |
| `havocRate` | float | Havoc rate. |
| `dbHavocEvents` | float | Db havoc events. |
| `frontSevenHavocEvents` | float | Front seven havoc events. |
| `totalHavocEvents` | float | Total havoc events. |
| `totalPlays` | float | Total plays. |

### GameMedia

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startTime` | datetime | Start time. |
| `isStartTimeTBD` | bool | Is start time t b d. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `mediaType` | MediaType | Media type. (`tv`, `radio`, `web`, `ppv`, `mobile`) |
| `outlet` | str | Outlet. |

### GamePlayerStats

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `teams` | List[GamePlayerStatsTeam] | Teams. |

### GamePlayoff

| Field | Type | Description |
|---|---|---|
| `competition` | PlayoffCompetition | Competition. (`cfp`) |
| `format` | str | Format. |
| `round` | PlayoffRound | Round. (`first_round`, `quarterfinal`, `semifinal`, `championship`) |
| `roundName` | str | Round name. |
| `bracketSlot` | str | Bracket slot. |
| `homeSeed` | int | Home seed. |
| `awaySeed` | int | Away seed. |
| `bowlName` | str | Bowl name. |

### GameStatus

Enum values: `scheduled`, `in_progress`, `completed`

### GameTeamStats

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `teams` | List[GameTeamStatsTeam] | Teams. |

### GameWeather

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `startTime` | datetime | Start time. |
| `gameIndoors` | bool | Game indoors. |
| `homeTeam` | str | Home team name. |
| `homeConference` | str | Home team's conference at the time of the game. |
| `awayTeam` | str | Away team name. |
| `awayConference` | str | Away team's conference at the time of the game. |
| `venueId` | int | Venue identifier, joins to the venues endpoint. |
| `venue` | str | Venue name. |
| `temperature` | float | Temperature. |
| `dewPoint` | float | Dew point. |
| `humidity` | float | Humidity. |
| `precipitation` | float | Precipitation. |
| `snowfall` | float | Snowfall. |
| `windDirection` | float | Wind direction. |
| `windSpeed` | float | Wind speed. |
| `pressure` | float | Pressure. |
| `weatherConditionCode` | float | Weather condition code. |
| `weatherCondition` | str | Weather condition. |

### KickerPAAR

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `paar` | float | Points Above Average Replacement on field goal attempts. |
| `attempts` | int | Attempts. |

### LiveGame

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `status` | str | Status. |
| `period` | int | Quarter/period number. |
| `clock` | str | Game clock at the time of the play/event. |
| `possession` | str | Possession. |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `teams` | List[LiveGameTeam] | Teams. |
| `drives` | List[LiveGameDrive] | Number of drives. |

### Matchup

| Field | Type | Description |
|---|---|---|
| `team1` | str | Team1. |
| `team2` | str | Team2. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |
| `team1Wins` | int | Team1 wins. |
| `team2Wins` | int | Team2 wins. |
| `ties` | int | Tie count. |
| `games` | List[MatchupGame] | Games coached. |

### MediaType

Enum values: `tv`, `radio`, `web`, `ppv`, `mobile`

### Play

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `driveId` | str | Drive ID. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `driveNumber` | int | Drive number. |
| `playNumber` | int | Play number. |
| `offense` | str | Offensive-side breakdown. |
| `offenseConference` | str | Offense team's conference. |
| `offenseScore` | int | Offense team's score at the time of the play. |
| `defense` | str | Defensive-side breakdown. |
| `home` | str | Home. |
| `away` | str | Away. |
| `defenseConference` | str | Defense team's conference. |
| `defenseScore` | int | Defense team's score at the time of the play. |
| `period` | int | Quarter/period number. |
| `clock` | PlayClock | Game clock at the time of the play/event. — see [PlayClock](#playclock) |
| `offenseTimeouts` | int | Offense timeouts. |
| `defenseTimeouts` | int | Defense timeouts. |
| `yardline` | int | Yardline. |
| `yardsToGoal` | int | Yards remaining to the opponent's goal line. |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `yardsGained` | int | Yards gained on the play. |
| `scoring` | bool | True if the play resulted in points. |
| `playType` | str | Play type (run/pass/punt/etc). |
| `playText` | str | Human-readable play description. |
| `ppa` | float | Predicted Points Added — CFBD's play-value metric, similar to EPA. |
| `wallclock` | str | Real-world timestamp of the event. |

### PlayClock

| Field | Type | Description |
|---|---|---|
| `seconds` | int | Seconds. |
| `minutes` | int | Minutes. |

### PlayStat

| Field | Type | Description |
|---|---|---|
| `gameId` | float | Game identifier, joins to the games endpoint. |
| `season` | float | Season year. |
| `week` | float | Week number within the season. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `teamScore` | float | Team score. |
| `opponentScore` | float | Opponent score. |
| `driveId` | str | Drive ID. |
| `playId` | str | Play ID. |
| `period` | float | Quarter/period number. |
| `clock` | PlayStatClock | Game clock at the time of the play/event. — see [PlayStatClock](#playstatclock) |
| `yardsToGoal` | float | Yards remaining to the opponent's goal line. |
| `down` | float | Down number (1-4). |
| `distance` | float | Yards to go for a first down. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `statType` | str | Category of statistic being recorded. |
| `stat` | float | Statistic value. |

### PlayStatClock

| Field | Type | Description |
|---|---|---|
| `seconds` | float | Seconds. |
| `minutes` | float | Minutes. |

### PlayStatType

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |

### PlayType

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `text` | str | Text. |
| `abbreviation` | str | Short abbreviation. |

### PlayWinProbability

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `playId` | str | Play ID. |
| `playText` | str | Human-readable play description. |
| `homeId` | int | Home team identifier. |
| `home` | str | Home. |
| `awayId` | int | Away team identifier. |
| `away` | str | Away. |
| `spread` | float | Closing point spread (negative = favorite by that many points), home-team perspective unless noted. |
| `homeBall` | bool | Home ball. |
| `homeScore` | int | Home score. |
| `awayScore` | int | Away score. |
| `yardLine` | int | Yard line (0-100, own end zone to opponent's). |
| `down` | int | Down number (1-4). |
| `distance` | int | Yards to go for a first down. |
| `homeWinProbability` | float | Home win probability. |
| `playNumber` | int | Play number. |

### PlayerGamePredictedPointsAdded

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `opponent` | str | Opponent team name. |
| `averagePPA` | PlayerGamePredictedPointsAddedAveragePPA | Average p p a. — see [PlayerGamePredictedPointsAddedAveragePPA](#playergamepredictedpointsaddedaverageppa) |

### PlayerGamePredictedPointsAddedAveragePPA

| Field | Type | Description |
|---|---|---|
| `pass` | float | Pass. |
| `all` | float | All. |

### PlayerGameSuccessRate

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonTypeDB | `regular` or `postseason`. (`allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`) |
| `week` | int | Week number within the season. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `passing` | PlayerSuccessRateSplit | Passing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |
| `rushing` | PlayerSuccessRateSplit | Rushing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |

### PlayerSearchResult

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `team` | str | Team name. |
| `name` | str | Name. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `weight` | int | Weight in pounds. |
| `height` | float | Height in inches. |
| `jersey` | int | Jersey number. |
| `position` | str | Position abbreviation. |
| `hometown` | str | Hometown. |
| `teamColor` | str | Team color. |
| `teamColorSecondary` | str | Team color secondary. |
| `activeStartYear` | int | Active start year. |
| `activeEndYear` | int | Active end year. |
| `teamStints` | List[PlayerSearchTeamStint] | Team stints. |

### PlayerSeasonOverview

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `games` | int | Games coached. |
| `boxScoreStats` | PlayerSeasonOverviewBoxScoreStats | Box score stats. — see [PlayerSeasonOverviewBoxScoreStats](#playerseasonoverviewboxscorestats) |

### PlayerSeasonOverviewBoxScoreStats

| Field | Type | Description |
|---|---|---|
| `categories` | List[PlayerSeasonOverviewCategory] | Categories. |

### PlayerSeasonOverviewPPAAverage

| Field | Type | Description |
|---|---|---|
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `thirdDown` | float | Third down. |
| `secondDown` | float | Second down. |
| `firstDown` | float | First down. |
| `pass` | float | Pass. |
| `all` | float | All. |

### PlayerSeasonPredictedPointsAdded

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `averagePPA` | PlayerSeasonOverviewPPAAverage | Average p p a. — see [PlayerSeasonOverviewPPAAverage](#playerseasonoverviewppaaverage) |
| `totalPPA` | PlayerSeasonOverviewPPAAverage | Sum of PPA across plays. — see [PlayerSeasonOverviewPPAAverage](#playerseasonoverviewppaaverage) |

### PlayerSeasonSuccessRate

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `passing` | PlayerSuccessRateSplit | Passing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |
| `rushing` | PlayerSuccessRateSplit | Rushing. — see [PlayerSuccessRateSplit](#playersuccessratesplit) |

### PlayerStat

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `playerId` | str | Player ID. |
| `player` | str | Player. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `category` | str | Statistic category/group. |
| `statType` | str | Category of statistic being recorded. |
| `stat` | str | Statistic value. |

### PlayerSuccessRateSplit

| Field | Type | Description |
|---|---|---|
| `plays` | int | Number of plays. |
| `successes` | int | Successes. |
| `successRate` | float | Success rate. |

### PlayerTransfer

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `position` | str | Position abbreviation. |
| `origin` | str | Origin. |
| `destination` | str | Destination. |
| `transferDate` | datetime | Transfer date. |
| `rating` | float | Composite rating score. |
| `stars` | int | Recruit star rating (1-5). |
| `eligibility` | TransferEligibility | Player eligibility/class status. (`Withdrawn`, `TBD`, `PendingAppeal`, `SittingOne`, `Immediate`) |

### PlayerUsage

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `id` | str | Unique identifier for the record. |
| `name` | str | Name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `usage` | PlayerUsageUsage | Share of team plays/snaps the player was involved in, by situation. — see [PlayerUsageUsage](#playerusageusage) |

### PlayerUsageUsage

| Field | Type | Description |
|---|---|---|
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `thirdDown` | float | Third down. |
| `secondDown` | float | Second down. |
| `firstDown` | float | First down. |
| `rush` | float | Rush. |
| `pass` | float | Pass. |
| `overall` | float | Overall (combined) rating. |

### PlayerWeightedEPA

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `athleteId` | str | Player identifier. |
| `athleteName` | str | Player name. |
| `position` | str | Position abbreviation. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `wepa` | float | Weighted EPA — EPA contribution weighted by the game's leverage/importance. |
| `plays` | int | Number of plays. |

### PlayoffAdvancement

| Field | Type | Description |
|---|---|---|
| `matchupId` | int | Matchup ID. |
| `bracketSlot` | str | Bracket slot. |
| `position` | int | Position abbreviation. |

### PlayoffBidType

Enum values: `automatic`, `at_large`

### PlayoffCompetition

Enum values: `cfp`

### PlayoffCompetitionCfp

Enum values: `cfp`

### PlayoffLinkedGame

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `completed` | bool | True once the game has finished. |
| `homeTeam` | PlayoffTeam | Home team name. — see [PlayoffTeam](#playoffteam) |
| `homePoints` | int | Home team's final score. |
| `awayTeam` | PlayoffTeam | Away team name. — see [PlayoffTeam](#playoffteam) |
| `awayPoints` | int | Away team's final score. |
| `venueId` | int | Venue identifier, joins to the venues endpoint. |
| `venue` | str | Venue name. |

### PlayoffMatchup

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `bracketSlot` | str | Bracket slot. |
| `round` | PlayoffRound | Round. (`first_round`, `quarterfinal`, `semifinal`, `championship`) |
| `roundName` | str | Round name. |
| `roundOrder` | int | Round order. |
| `matchupOrder` | int | Matchup order. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `bowlName` | str | Bowl name. |
| `slots` | List[PlayoffMatchupSlot] | Slots. |
| `game` | PlayoffLinkedGame | Game. — see [PlayoffLinkedGame](#playofflinkedgame) |
| `advancesTo` | PlayoffAdvancement | Advances to. — see [PlayoffAdvancement](#playoffadvancement) |

### PlayoffOutcome

Enum values: `active`, `eliminated`, `champion`

### PlayoffParticipant

| Field | Type | Description |
|---|---|---|
| `team` | PlayoffTeam | Team name. — see [PlayoffTeam](#playoffteam) |
| `committeeRank` | int | Committee rank. |
| `seed` | int | Seed. |
| `bidType` | PlayoffBidType | Bid type. (`automatic`, `at_large`) |
| `qualificationReason` | str | Qualification reason. |
| `conferenceChampion` | bool | Conference champion. |
| `qualifyingConference` | str | Qualifying conference. |
| `firstRoundBye` | bool | First round bye. |
| `outcome` | PlayoffOutcome | Outcome. (`active`, `eliminated`, `champion`) |
| `eliminatedRound` | PlayoffRound | Eliminated round. (`first_round`, `quarterfinal`, `semifinal`, `championship`) |

### PlayoffRound

Enum values: `first_round`, `quarterfinal`, `semifinal`, `championship`

### PlayoffStatus

Enum values: `scheduled`, `selected`, `in_progress`, `completed`

### PlayoffTeam

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |
| `conference` | str | Conference name. |

### PollWeek

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `polls` | List[Poll] | Polls. |

### PredictedPointsValue

| Field | Type | Description |
|---|---|---|
| `yardLine` | int | Yard line (0-100, own end zone to opponent's). |
| `predictedPoints` | float | Predicted points. |

### PregameWinProbability

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `week` | int | Week number within the season. |
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `homeTeam` | str | Home team name. |
| `awayTeam` | str | Away team name. |
| `spread` | float | Closing point spread (negative = favorite by that many points), home-team perspective unless noted. |
| `homeWinProbability` | float | Home win probability. |

### Recruit

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `athleteId` | str | Player identifier. |
| `recruitType` | RecruitClassification | Recruit type (HighSchool/JUCO/PrepSchool/Transfer). (`JUCO`, `PrepSchool`, `HighSchool`) |
| `year` | int | Season year. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `name` | str | Name. |
| `school` | str | School coached. |
| `committedTo` | str | School the recruit committed to. |
| `position` | str | Position abbreviation. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `stars` | int | Recruit star rating (1-5). |
| `rating` | float | Composite rating score. |
| `city` | str | City name. |
| `stateProvince` | str | State province. |
| `country` | str | Country. |
| `hometownInfo` | RecruitHometownInfo | Recruit's hometown details. — see [RecruitHometownInfo](#recruithometowninfo) |

### RecruitClassification

Enum values: `JUCO`, `PrepSchool`, `HighSchool`

### RecruitHometownInfo

| Field | Type | Description |
|---|---|---|
| `fipsCode` | str | Fips code. |
| `longitude` | float | Longitude in decimal degrees. |
| `latitude` | float | Latitude in decimal degrees. |

### ReturningProduction

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `totalPPA` | float | Sum of PPA across plays. |
| `totalPassingPPA` | float | Total passing p p a. |
| `totalReceivingPPA` | float | Total receiving p p a. |
| `totalRushingPPA` | float | Total rushing p p a. |
| `percentPPA` | float | Percent p p a. |
| `percentPassingPPA` | float | Percent passing p p a. |
| `percentReceivingPPA` | float | Percent receiving p p a. |
| `percentRushingPPA` | float | Percent rushing p p a. |
| `usage` | float | Share of team plays/snaps the player was involved in, by situation. |
| `passingUsage` | float | Passing usage. |
| `receivingUsage` | float | Receiving usage. |
| `rushingUsage` | float | Rushing usage. |

### RosterPlayer

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique identifier for the record. |
| `firstName` | str | First name. |
| `lastName` | str | Last name. |
| `team` | str | Team name. |
| `height` | float | Height in inches. |
| `weight` | int | Weight in pounds. |
| `jersey` | int | Jersey number. |
| `year` | int | Season year. |
| `position` | str | Position abbreviation. |
| `homeCity` | str | Home city. |
| `homeState` | str | Home state. |
| `homeCountry` | str | Home country. |
| `homeLatitude` | float | Home latitude. |
| `homeLongitude` | float | Home longitude. |
| `homeCountyFIPS` | str | Home county f i p s. |
| `recruitIds` | List[str] | Recruit IDs. |

### ScoreboardGame

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `startDate` | datetime | Kickoff date/time (UTC). |
| `startTimeTBD` | bool | True if kickoff time was not yet announced. |
| `tv` | str | Tv. |
| `neutralSite` | bool | True if played at a neutral (non-home) site. |
| `conferenceGame` | bool | True if both teams share a conference. |
| `status` | GameStatus | Status. (`scheduled`, `in_progress`, `completed`) |
| `period` | int | Quarter/period number. |
| `clock` | str | Game clock at the time of the play/event. |
| `situation` | str | Situation. |
| `possession` | str | Possession. |
| `lastPlay` | str | Last play. |
| `venue` | ScoreboardGameVenue | Venue name. — see [ScoreboardGameVenue](#scoreboardgamevenue) |
| `homeTeam` | ScoreboardGameHomeTeam | Home team name. — see [ScoreboardGameHomeTeam](#scoreboardgamehometeam) |
| `awayTeam` | ScoreboardGameHomeTeam | Away team name. — see [ScoreboardGameHomeTeam](#scoreboardgamehometeam) |
| `weather` | ScoreboardGameWeather | Weather. — see [ScoreboardGameWeather](#scoreboardgameweather) |
| `betting` | ScoreboardGameBetting | Betting. — see [ScoreboardGameBetting](#scoreboardgamebetting) |

### ScoreboardGameBetting

| Field | Type | Description |
|---|---|---|
| `awayMoneyline` | float | Away moneyline. |
| `homeMoneyline` | float | Home moneyline. |
| `overUnder` | float | Total (over/under) line. |
| `spread` | float | Closing point spread (negative = favorite by that many points), home-team perspective unless noted. |

### ScoreboardGameHomeTeam

| Field | Type | Description |
|---|---|---|
| `winProbability` | float | Win probability. |
| `lineScores` | List[int] | Line scores. |
| `points` | int | Points value for this rating component. |
| `classification` | DivisionClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `conference` | str | Conference name. |
| `name` | str | Name. |
| `id` | int | Unique identifier for the record. |

### ScoreboardGameVenue

| Field | Type | Description |
|---|---|---|
| `state` | str | State/province abbreviation. |
| `city` | str | City name. |
| `name` | str | Name. |

### ScoreboardGameWeather

| Field | Type | Description |
|---|---|---|
| `windDirection` | float | Wind direction. |
| `windSpeed` | float | Wind speed. |
| `description` | str | Description. |
| `temperature` | float | Temperature. |

### SeasonType

Enum values: `regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`

### SeasonTypeDB

Enum values: `allstar`, `postseason`, `preseason`, `regular`, `spring_postseason`, `spring_regular`

### Team

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `school` | str | School coached. |
| `mascot` | str | Team mascot name. |
| `abbreviation` | str | Short abbreviation. |
| `alternateNames` | List[str] | Alternate names. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `classification` | str | Division classification (FBS/FCS/II/III). |
| `color` | str | Primary brand color (hex). |
| `alternateColor` | str | Alternate color. |
| `logos` | List[str] | Logo image URLs. |
| `twitter` | str | Twitter/X handle. |
| `location` | Venue | Location details (city/state/lat/lon). — see [Venue](#venue) |

### TeamATS

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `games` | int | Games coached. |
| `atsWins` | int | Ats wins. |
| `atsLosses` | int | Ats losses. |
| `atsPushes` | int | Ats pushes. |
| `avgCoverMargin` | float | Avg cover margin. |

### TeamConferenceAffiliation

| Field | Type | Description |
|---|---|---|
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `conferenceId` | int | Conference identifier, joins to the conferences endpoint. |
| `conference` | str | Conference name. |
| `conferenceAbbreviation` | str | Conference abbreviation. |
| `classification` | ConferenceClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `conferenceDivision` | str | Conference division. |
| `startYear` | int | Start year. |
| `endYear` | int | End year. |

### TeamConferenceChange

| Field | Type | Description |
|---|---|---|
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `fromConferenceId` | int | From conference ID. |
| `fromConference` | str | From conference. |
| `fromConferenceAbbreviation` | str | From conference abbreviation. |
| `fromClassification` | ConferenceClassification | From classification. (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `toConferenceId` | int | To conference ID. |
| `toConference` | str | To conference. |
| `toConferenceAbbreviation` | str | To conference abbreviation. |
| `toClassification` | ConferenceClassification | To classification. (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `effectiveYear` | int | Effective year. |

### TeamCoreRating

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `throughSeasonType` | CoreRatingSeasonType | Through season type. (`regular`, `postseason`) |
| `throughWeek` | int | Through week. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `overall` | float | Overall (combined) rating. |
| `offense` | float | Offensive-side breakdown. |
| `defense` | float | Defensive-side breakdown. |
| `offensePlays` | int | Offense plays. |
| `defensePlays` | int | Defense plays. |
| `modelVersion` | str | Model version. |

### TeamElo

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `elo` | int | Elo. |

### TeamFPI

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `fpi` | float | FPI. |
| `resumeRanks` | TeamFPIResumeRanks | Resume ranks. — see [TeamFPIResumeRanks](#teamfpiresumeranks) |
| `efficiencies` | TeamFPIEfficiencies | Efficiencies. — see [TeamFPIEfficiencies](#teamfpiefficiencies) |

### TeamFPIEfficiencies

| Field | Type | Description |
|---|---|---|
| `specialTeams` | float | Special-teams breakdown. |
| `defense` | float | Defensive-side breakdown. |
| `offense` | float | Offensive-side breakdown. |
| `overall` | float | Overall (combined) rating. |

### TeamFPIResumeRanks

| Field | Type | Description |
|---|---|---|
| `gameControl` | int | Game control. |
| `remainingStrengthOfSchedule` | int | Remaining strength of schedule. |
| `strengthOfSchedule` | int | Strength of schedule. |
| `averageWinProbability` | int | Average win probability. |
| `fpi` | int | FPI. |
| `strengthOfRecord` | int | Strength of record. |

### TeamGamePredictedPointsAdded

| Field | Type | Description |
|---|---|---|
| `gameId` | int | Game identifier, joins to the games endpoint. |
| `season` | int | Season year. |
| `week` | int | Week number within the season. |
| `seasonType` | SeasonType | `regular` or `postseason`. (`regular`, `postseason`, `both`, `allstar`, `spring_regular`, `spring_postseason`) |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `opponent` | str | Opponent team name. |
| `offense` | TeamGamePredictedPointsAddedOffense | Offensive-side breakdown. — see [TeamGamePredictedPointsAddedOffense](#teamgamepredictedpointsaddedoffense) |
| `defense` | TeamGamePredictedPointsAddedOffense | Defensive-side breakdown. — see [TeamGamePredictedPointsAddedOffense](#teamgamepredictedpointsaddedoffense) |

### TeamGamePredictedPointsAddedOffense

| Field | Type | Description |
|---|---|---|
| `thirdDown` | float | Third down. |
| `secondDown` | float | Second down. |
| `firstDown` | float | First down. |
| `rushing` | float | Rushing. |
| `passing` | float | Passing. |
| `overall` | float | Overall (combined) rating. |

### TeamRecord

| Field | Type | Description |
|---|---|---|
| `games` | int | Games coached. |
| `wins` | int | Win count. |
| `losses` | int | Loss count. |
| `ties` | int | Tie count. |

### TeamRecords

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `teamId` | int | Team identifier. |
| `team` | str | Team name. |
| `classification` | DivisionClassification | Division classification (FBS/FCS/II/III). (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `expectedWins` | float | Expected wins. |
| `total` | TeamRecord | Total. — see [TeamRecord](#teamrecord) |
| `conferenceGames` | TeamRecord | Conference games. — see [TeamRecord](#teamrecord) |
| `homeGames` | TeamRecord | Home games. — see [TeamRecord](#teamrecord) |
| `awayGames` | TeamRecord | Away games. — see [TeamRecord](#teamrecord) |
| `neutralSiteGames` | TeamRecord | Neutral site games. — see [TeamRecord](#teamrecord) |
| `regularSeason` | TeamRecord | Regular season. — see [TeamRecord](#teamrecord) |
| `postseason` | TeamRecord | Postseason. — see [TeamRecord](#teamrecord) |

### TeamRecruitingRanking

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `rank` | int | Rank (1 = best) within the given scope. |
| `team` | str | Team name. |
| `points` | float | Points value for this rating component. |

### TeamSP

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |
| `secondOrderWins` | float | Second-order (efficiency-based expected) win total. |
| `sos` | float | Strength of schedule rating. |
| `offense` | TeamSPOffense | Offensive-side breakdown. — see [TeamSPOffense](#teamspoffense) |
| `defense` | TeamSPDefense | Defensive-side breakdown. — see [TeamSPDefense](#teamspdefense) |
| `specialTeams` | TeamSPSpecialTeams | Special-teams breakdown. — see [TeamSPSpecialTeams](#teamspspecialteams) |

### TeamSPDefense

| Field | Type | Description |
|---|---|---|
| `havoc` | AdvancedSeasonStatOffenseHavoc | Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception. — see [AdvancedSeasonStatOffenseHavoc](#advancedseasonstatoffensehavoc) |
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `passing` | float | Passing. |
| `rushing` | float | Rushing. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `success` | float | Success rate — share of plays gaining enough yardage to be an on-schedule down (per Football Outsiders rules). |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |

### TeamSPOffense

| Field | Type | Description |
|---|---|---|
| `pace` | float | Plays run per minute of possession (tempo). |
| `runRate` | float | Run rate. |
| `passingDowns` | float | Passing downs. |
| `standardDowns` | float | Standard downs. |
| `passing` | float | Passing. |
| `rushing` | float | Rushing. |
| `explosiveness` | float | Average PPA on successful plays — a measure of big-play ability. |
| `success` | float | Success rate — share of plays gaining enough yardage to be an on-schedule down (per Football Outsiders rules). |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |

### TeamSPSpecialTeams

| Field | Type | Description |
|---|---|---|
| `rating` | float | Composite rating score. |

### TeamSRS

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `division` | str | Conference division (e.g. East/West), if applicable. |
| `rating` | float | Composite rating score. |
| `ranking` | int | Rank (1 = best) within the given scope. |

### TeamSeasonPredictedPointsAdded

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `conference` | str | Conference name. |
| `team` | str | Team name. |
| `offense` | TeamSeasonPredictedPointsAddedOffense | Offensive-side breakdown. — see [TeamSeasonPredictedPointsAddedOffense](#teamseasonpredictedpointsaddedoffense) |
| `defense` | TeamSeasonPredictedPointsAddedOffense | Defensive-side breakdown. — see [TeamSeasonPredictedPointsAddedOffense](#teamseasonpredictedpointsaddedoffense) |

### TeamSeasonPredictedPointsAddedOffense

| Field | Type | Description |
|---|---|---|
| `cumulative` | AdjustedTeamMetricsEpa | Cumulative. — see [AdjustedTeamMetricsEpa](#adjustedteammetricsepa) |
| `thirdDown` | float | Third down. |
| `secondDown` | float | Second down. |
| `firstDown` | float | First down. |
| `rushing` | float | Rushing. |
| `passing` | float | Passing. |
| `overall` | float | Overall (combined) rating. |

### TeamStat

| Field | Type | Description |
|---|---|---|
| `season` | int | Season year. |
| `team` | str | Team name. |
| `conference` | str | Conference name. |
| `statName` | str | Stat name. |
| `statValue` | TeamStatStatValue | Stat value. — see [TeamStatStatValue](#teamstatstatvalue) |

### TeamStatStatValue

| Field | Type | Description |
|---|---|---|
| `any_of_schemas` | List[str] | Any of schemas. |

### TeamTalent

| Field | Type | Description |
|---|---|---|
| `year` | int | Season year. |
| `team` | str | Team name. |
| `talent` | float | Talent. |

### TransferEligibility

Enum values: `Withdrawn`, `TBD`, `PendingAppeal`, `SittingOne`, `Immediate`

### UserFeatureAccess

| Field | Type | Description |
|---|---|---|
| `adjustedMetrics` | bool | Adjusted metrics. |
| `weather` | bool | Weather. |
| `scoreboard` | bool | Scoreboard. |
| `livePlayByPlay` | bool | Live play by play. |
| `graphQl` | bool | Graph ql. |

### UserInfo

| Field | Type | Description |
|---|---|---|
| `patronLevel` | float | Patron level. |
| `tierName` | str | Tier name. |
| `monthlyLimit` | float | Monthly limit. |
| `remainingCalls` | float | Remaining calls. |
| `usedCalls` | float | Used calls. |
| `resetAt` | str | Reset at. |
| `sharedPool` | bool | Shared pool. |
| `products` | List[str] | Products. |
| `features` | UserFeatureAccess | Features. — see [UserFeatureAccess](#userfeatureaccess) |

### Venue

| Field | Type | Description |
|---|---|---|
| `id` | int | Unique identifier for the record. |
| `name` | str | Name. |
| `city` | str | City name. |
| `state` | str | State/province abbreviation. |
| `zip` | str | Postal code. |
| `countryCode` | str | ISO country code. |
| `timezone` | str | IANA timezone name. |
| `latitude` | float | Latitude in decimal degrees. |
| `longitude` | float | Longitude in decimal degrees. |
| `elevation` | str | Elevation in feet. |
| `capacity` | int | Stadium capacity. |
| `constructionYear` | int | Year the venue was built. |
