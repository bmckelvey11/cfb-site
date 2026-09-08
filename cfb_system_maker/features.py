from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

Group = Literal[
    "matchup",
    "ratings",
    "betting_lines",
    "weather",
    "season_to_date",
    "team_preseason",
    "metadata",
    "result_lookahead",
]
Control = Literal["bool", "categorical", "numeric"]
Join = Literal["game_id", "team_season", "team_name", "conference_name"]
SourceKind = Literal[
    "raw_game",
    "raw_lines",
    "raw_weather",
    "raw_media",
    "raw_team_season",
    "raw_teams",
    "raw_coaches",
    "raw_havoc",
    "raw_adv_ngt",
    "raw_venues",
    "raw_conferences",
    "raw_pregame_wp",
    "raw_player_agg",
    "raw_prior_team_season",
    "raw_conference_change",
    "computed_running",
    "computed_v1",
    "computed_line_move",
    "computed_wind",
    "graphql_game",
    "graphql_weather",
    "graphql_lines",
    "graphql_game_team",
]


@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    group: Group
    source_kind: SourceKind
    field: str
    join: Join
    control: Control
    team_scoped: bool = False
    lines_field: str | None = None  # nested under lines[0] for raw_lines
    source_file: str | None = None  # raw/json basename without season suffix
    description: str = ""  # plain-text About Filter copy (D-19)


FEATURE_REGISTRY: tuple[FeatureDef, ...] = (
    # --- matchup (game_id) ---
    FeatureDef(
        "neutralSite", "Neutral Site", "matchup", "raw_game", "neutralSite", "game_id", "bool",
        description="Whether the game is at a neutral site (true/false). Pregame schedule flag.",
    ),
    FeatureDef(
        "conferenceGame", "Conference Game", "matchup", "raw_game", "conferenceGame", "game_id", "bool",
        description="Whether both teams are in the same conference (true/false). Pregame schedule flag.",
    ),
    FeatureDef(
        "venue", "Venue", "matchup", "raw_game", "venue", "game_id", "categorical",
        description="Stadium or site name for the game. Categorical pregame location label.",
    ),
    FeatureDef(
        "seasonType", "Season Type", "matchup", "raw_game", "seasonType", "game_id", "categorical",
        description="Season segment label (for example regular or postseason). Pregame schedule category.",
    ),
    FeatureDef(
        "kickoff_hour",
        "Kickoff Time (ET)",
        "matchup",
        "raw_game",
        "kickoff_hour",
        "game_id",
        "numeric",
        description=(
            "Scheduled kickoff time in Eastern Time, stored as hour 0–23 and shown "
            "as a clock time (for example 7:00 PM). Pregame schedule. "
            "Null when the clock time is TBD."
        ),
    ),
    # --- ratings (game_id) ---
    FeatureDef(
        "homePregameElo", "Home Pregame Elo", "ratings", "raw_game", "homePregameElo", "game_id", "numeric",
        description="Home team's Elo rating entering the game. Higher means stronger; pregame value.",
    ),
    FeatureDef(
        "awayPregameElo", "Away Pregame Elo", "ratings", "raw_game", "awayPregameElo", "game_id", "numeric",
        description="Away team's Elo rating entering the game. Higher means stronger; pregame value.",
    ),
    FeatureDef(
        "pregame_win_prob",
        "Win Prob (contaminated — not pregame)",
        "result_lookahead",
        "graphql_game_team",
        "winProb",
        "game_id",
        "numeric",
        team_scoped=True,
        description=(
            "Team-scoped win probability (0–1 scale) from graphql gameTeam. Despite the key name "
            "this is NOT an entering-game value: the source row carries endElo and final points, "
            "and the field's tail encodes the outcome. Measured on the built data, the team with "
            "the higher winProb wins 86.2% of games overall, but teams at winProb >= 0.977 win "
            "7182/7244 = 99.1% — an accuracy no genuine pregame model reaches. Quarantined as "
            "lookahead so candidate search cannot select it (see search.py _CANDIDATE_FEATURES). "
            "Analysis-only; do not use as a betting input."
        ),
    ),
    FeatureDef(
        "pregame_home_win_prob", "Home Win Prob (pregame)", "ratings", "raw_pregame_wp", "homeWinProbability", "game_id", "numeric",
        description="Home win probability entering the game (0–1). Higher favors home; pregame model output.",
    ),
    # --- betting lines (game_id) ---
    FeatureDef(
        "spreadOpen", "Spread Open", "betting_lines", "raw_lines", "spreadOpen", "game_id", "numeric",
        lines_field="spreadOpen",
        description="Opening home spread from the lines feed. Negative favors home; pregame market open.",
    ),
    FeatureDef(
        "overUnderOpen", "Over/Under Open", "betting_lines", "raw_lines", "overUnderOpen", "game_id", "numeric",
        lines_field="overUnderOpen",
        description="Opening total (over/under) points from the lines feed. Pregame market open.",
    ),
    FeatureDef(
        "moneylineHome", "Home Moneyline", "betting_lines", "raw_lines", "homeMoneyline", "game_id", "numeric",
        lines_field="homeMoneyline",
        description="Home moneyline in American odds. Negative is favored; pregame market number.",
    ),
    FeatureDef(
        "moneylineAway", "Away Moneyline", "betting_lines", "raw_lines", "awayMoneyline", "game_id", "numeric",
        lines_field="awayMoneyline",
        description="Away moneyline in American odds. Negative is favored; pregame market number.",
    ),
    FeatureDef(
        "spread_open", "Spread Open (book-matched)", "betting_lines", "computed_line_move", "spread_open",
        "game_id", "numeric",
        description=(
            "Opening home spread, read from the SAME book row that supplied the built close "
            "(GameRecord.spread). Negative favors home, matching GameRecord.spread's sign. Null "
            "whenever that book published no opener for the game — which is most games, since "
            "far fewer books report opens than closes. Populated on no games before 2021 and on "
            "roughly half of games 2023-2025. For a spread open regardless of book match, see "
            "the legacy 'Spread Open' feature — that one is populated far more often but may not "
            "come from the same book as the close."
        ),
    ),
    FeatureDef(
        "spread_move", "Spread Move (close − open)", "betting_lines", "computed_line_move", "spread_move",
        "game_id", "numeric",
        description=(
            "close − open, both from the same book row as the built close. Negative means the "
            "line moved toward the home team (home became a bigger favorite or a smaller "
            "underdog); positive means it moved toward the away team. Null whenever spread_open "
            "is null (see that feature's description for coverage)."
        ),
    ),
    FeatureDef(
        "total_open", "Total Open (book-matched)", "betting_lines", "computed_line_move", "total_open",
        "game_id", "numeric",
        description=(
            "Opening total, read from the same book row that supplied the built close "
            "(GameRecord.total) — which may be a different book than the one that supplied the "
            "spread, per normalize's total-selection fallback. Null whenever that book published "
            "no opener for the game. Populated on no games before 2021 and on roughly a "
            "quarter to a half of games 2023-2025."
        ),
    ),
    FeatureDef(
        "total_move", "Total Move (close − open)", "betting_lines", "computed_line_move", "total_move",
        "game_id", "numeric",
        description=(
            "close − open, both from the same book row as the built close total. Positive means "
            "the total went up; negative means it went down. Null whenever total_open is null "
            "(see that feature's description for coverage)."
        ),
    ),
    # --- weather (game_id) ---
    FeatureDef(
        "weather_temperature", "Temperature (F)", "weather", "raw_weather", "temperature", "game_id", "numeric",
        description="Forecast or reported game temperature in degrees Fahrenheit. Pregame weather.",
    ),
    FeatureDef(
        "weather_windSpeed", "Wind Speed", "weather", "raw_weather", "windSpeed", "game_id", "numeric",
        description="Wind speed for the game site (mph). Higher is windier; pregame weather.",
    ),
    FeatureDef(
        "weather_precipitation", "Precipitation", "weather", "raw_weather", "precipitation", "game_id", "numeric",
        description="Precipitation amount for the game site. Higher means wetter; pregame weather.",
    ),
    FeatureDef(
        "weather_humidity", "Humidity", "weather", "raw_weather", "humidity", "game_id", "numeric",
        description="Relative humidity percentage for the game site. Pregame weather.",
    ),
    FeatureDef(
        "weather_dewPoint", "Dew Point", "weather", "raw_weather", "dewPoint", "game_id", "numeric",
        description="Dew point temperature (F) for the game site. Pregame weather.",
    ),
    FeatureDef(
        "weather_pressure", "Pressure", "weather", "raw_weather", "pressure", "game_id", "numeric",
        description="Barometric pressure for the game site. Pregame weather.",
    ),
    FeatureDef(
        "weather_snowfall", "Snowfall", "weather", "raw_weather", "snowfall", "game_id", "numeric",
        description="Snowfall amount for the game site. Higher means more snow; pregame weather.",
    ),
    FeatureDef(
        "gameIndoors", "Game Indoors", "weather", "raw_weather", "gameIndoors", "game_id", "bool",
        description="Whether the game is played indoors (true/false). Pregame venue/weather flag.",
    ),
    FeatureDef(
        "weather_condition", "Weather Condition", "weather", "raw_weather", "weatherCondition", "game_id", "categorical",
        description="Categorical weather condition label (for example Clear or Rain). Pregame weather.",
    ),
    FeatureDef(
        "weather_windDirection", "Wind Direction (deg)", "weather", "raw_weather", "windDirection", "game_id", "numeric",
        description="Wind direction in degrees. Pregame weather compass heading.",
    ),
    FeatureDef(
        "wind_relative_cardinal", "Wind vs Field + Direction", "weather", "computed_wind",
        "wind_relative_cardinal", "game_id", "categorical",
        description=(
            "Wind relative to the field's long axis, split by the compass point the wind "
            "blows from: for example Crosswind (NW) or Headwind (S). Headwind means the wind "
            "runs goalpost to goalpost -- a headwind one direction and a tailwind the other, "
            "since teams swap ends. Calm below 3 mph, where direction is noise. Null indoors "
            "and at venues with no trustworthy field orientation (about 56% of games have one)."
        ),
    ),
    FeatureDef(
        "wind_relative", "Wind vs Field", "weather", "computed_wind", "wind_relative",
        "game_id", "categorical",
        description=(
            "Wind relative to the field's long axis, ignoring compass direction: Headwind "
            "(within 30 degrees of the goalpost axis), Crosswind (within 30 degrees of "
            "sideline to sideline), Quartering in between, or Calm below 3 mph. Null indoors "
            "and where field orientation is unknown."
        ),
    ),
    FeatureDef(
        "wind_cross_mph", "Crosswind Speed (mph)", "weather", "computed_wind", "wind_cross_mph",
        "game_id", "numeric",
        description=(
            "Component of wind speed blowing sideline to sideline (mph). Higher means more "
            "of the wind pushes kicks and passes sideways. Null indoors and where field "
            "orientation is unknown."
        ),
    ),
    FeatureDef(
        "wind_along_mph", "Headwind Speed (mph)", "weather", "computed_wind", "wind_along_mph",
        "game_id", "numeric",
        description=(
            "Component of wind speed blowing goalpost to goalpost (mph). Higher means more "
            "of the wind runs up and down the field, helping one direction of play and "
            "hurting the other. Null indoors and where field orientation is unknown."
        ),
    ),
    FeatureDef(
        "wind_axis_angle", "Wind Angle Off Field Axis (deg)", "weather", "computed_wind",
        "wind_axis_angle", "game_id", "numeric",
        description=(
            "Angle between the wind line and the field's long axis, 0 to 90 degrees. 0 is "
            "straight up the field, 90 is straight across it. Null indoors and where field "
            "orientation is unknown."
        ),
    ),
    # --- team preseason ---
    FeatureDef(
        "returning_ppa",
        "Returning PPA %",
        "team_preseason",
        "raw_team_season",
        "percentPPA",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="returning_production",
        description=(
            "Share of prior-season PPA returning (0–1). Higher means more production returns. "
            "Team-scoped; use perspective to pick which team. Preseason / entering-season value."
        ),
    ),
    FeatureDef(
        "returning_usage",
        "Returning Usage",
        "team_preseason",
        "raw_team_season",
        "usage",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="returning_production",
        description=(
            "Share of prior-season usage returning (0–1). Higher means more usage returns. "
            "Team-scoped; use perspective to pick which team. Preseason / entering-season value."
        ),
    ),
    FeatureDef(
        "team_talent",
        "Team Talent",
        "team_preseason",
        "raw_team_season",
        "talent",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="talent",
        description=(
            "Composite team talent rating for the season. Higher means more talent. "
            "Team-scoped; use perspective to pick which team. Preseason rating."
        ),
    ),
    FeatureDef(
        "recruiting_rank",
        "Recruiting Rank",
        "team_preseason",
        "raw_team_season",
        "rank",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="recruiting_teams",
        description=(
            "Team recruiting class rank (1 is best). Lower rank is stronger. "
            "Team-scoped; use perspective to pick which team. Preseason ranking."
        ),
    ),
    FeatureDef(
        "recruiting_points",
        "Recruiting Points",
        "team_preseason",
        "raw_team_season",
        "points",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="recruiting_teams",
        description=(
            "Team recruiting class points. Higher means a stronger class. "
            "Team-scoped; use perspective to pick which team. Preseason score."
        ),
    ),
    FeatureDef(
        "prior_core_overall",
        "Prior-Season Core Rating",
        "team_preseason",
        "raw_prior_team_season",
        "overall",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="core_ratings",
        description=(
            "CFBD core rating (overall) from the PREVIOUS season. Higher is stronger. Core ratings "
            "are season-final values, so the prior season is used to keep the feature pregame."
        ),
    ),
    FeatureDef(
        "prior_core_offense",
        "Prior-Season Core Offense",
        "team_preseason",
        "raw_prior_team_season",
        "offense",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="core_ratings",
        description=(
            "CFBD core offense rating from the PREVIOUS season. Higher is a better offense. "
            "Season-final value, lagged one year to stay pregame."
        ),
    ),
    FeatureDef(
        "prior_core_defense",
        "Prior-Season Core Defense",
        "team_preseason",
        "raw_prior_team_season",
        "defense",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="core_ratings",
        description=(
            "CFBD core defense rating from the PREVIOUS season. Lower (more negative) is a better "
            "defense. Season-final value, lagged one year to stay pregame."
        ),
    ),
    FeatureDef(
        "prior_srs_rating",
        "Prior-Season SRS",
        "team_preseason",
        "raw_prior_team_season",
        "rating",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="srs_expanded",
        description=(
            "Simple Rating System value from the PREVIOUS season, expanded to cover FCS teams as "
            "well as FBS. Season-final value, lagged one year to stay pregame."
        ),
    ),
    FeatureDef(
        "conference_change",
        "First Year In New Conference",
        "team_preseason",
        "raw_conference_change",
        "changed",
        "team_season",
        "bool",
        team_scoped=True,
        description=(
            "Whether this is the team's first season in a conference it just moved to "
            "(realignment). Known before kickoff, so it reads the current season."
        ),
    ),
    FeatureDef(
        "prior_off_wepa",
        "Prior-Season Off wEPA",
        "team_preseason",
        "raw_player_agg",
        "prior_off_wepa",
        "team_season",
        "numeric",
        team_scoped=True,
        description=(
            "Prior-season offensive weighted EPA aggregate for the team. Higher is more productive. "
            "Team-scoped; use perspective to pick which team. Preseason / prior-season value."
        ),
    ),
    FeatureDef(
        "preseasonRank",
        "Preseason Poll Rank",
        "team_preseason",
        "raw_team_season",
        "preseasonRank",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="coach_seasons",
        description=(
            "Preseason poll rank from the team's coach-season row (1 is best). "
            "Team-scoped; use perspective to pick which team. Pregame ranking."
        ),
    ),
    # --- metadata ---
    FeatureDef(
        "team_state", "Team State", "metadata", "raw_teams", "location.state", "team_name", "categorical",
        team_scoped=True,
        description="US state (or region) of the team's home location. Team-scoped categorical metadata.",
    ),
    FeatureDef(
        "team_timezone", "Team Timezone", "metadata", "raw_teams", "location.timezone", "team_name", "categorical",
        team_scoped=True,
        description="Timezone of the team's home location. Team-scoped categorical metadata.",
    ),
    FeatureDef(
        "team_capacity", "Stadium Capacity", "metadata", "raw_teams", "location.capacity", "team_name", "numeric",
        team_scoped=True,
        description="Home stadium listed capacity (seats). Team-scoped numeric metadata.",
    ),
    FeatureDef(
        "team_conference", "Team Conference", "metadata", "raw_teams", "conference", "team_name", "categorical",
        team_scoped=True,
        description="Conference affiliation of the team. Team-scoped categorical metadata.",
    ),
    FeatureDef(
        "coach_name", "Head Coach", "metadata", "raw_coaches", "coach_name", "team_season", "categorical",
        team_scoped=True,
        description="Head coach name for the team-season. Team-scoped categorical metadata.",
    ),
    FeatureDef(
        "coach_hire_date", "Coach Hire Date", "metadata", "raw_coaches", "hireDate", "team_season", "categorical",
        team_scoped=True,
        description="Hire date string for the head coach. Team-scoped categorical metadata.",
    ),
    FeatureDef(
        "venue_dome", "Dome", "metadata", "raw_venues", "dome", "game_id", "bool",
        description="Whether the game venue is a dome (true/false). Venue metadata for the game.",
    ),
    FeatureDef(
        "venue_grass", "Grass Field", "metadata", "raw_venues", "grass", "game_id", "bool",
        description="Whether the game venue has a grass field (true/false). Venue metadata.",
    ),
    FeatureDef(
        "venue_elevation", "Venue Elevation", "metadata", "raw_venues", "elevation", "game_id", "numeric",
        description="Venue elevation (feet). Higher means higher altitude. Venue metadata.",
    ),
    FeatureDef(
        "venue_capacity", "Venue Capacity", "metadata", "raw_venues", "capacity", "game_id", "numeric",
        description="Venue seating capacity for the game site. Venue metadata.",
    ),
    FeatureDef(
        "conference_classification", "Conference Classification", "metadata", "raw_conferences",
        "classification", "conference_name", "categorical",
        team_scoped=True,
        description=(
            "Conference classification (for example fbs/fcs). Team-scoped via the team's conference."
        ),
    ),
    # --- season to date (computed, as-of-game) ---
    FeatureDef(
        "running_games_played", "Games Played (to date)", "season_to_date", "computed_running",
        "games_played", "game_id", "numeric", team_scoped=True,
        description=(
            "Games already played by the team entering this game (excludes the current game). "
            "Team-scoped entering-game season-to-date count."
        ),
    ),
    FeatureDef(
        "running_rest_days", "Days of Rest", "season_to_date", "computed_running",
        "rest_days", "game_id", "numeric", team_scoped=True,
        description=(
            "Calendar days (Eastern) between this game's kickoff and the team's previous "
            "game this season. Schedule-derived and fully pregame. Team-scoped -- use "
            "perspective to pick home, away, the bet side, or either. Null on a season "
            "opener (the offseason is not rest), and null when either kickoff date is "
            "missing rather than measuring rest from two games back."
        ),
    ),
    FeatureDef(
        "running_win_pct", "Win % (to date)", "season_to_date", "computed_running",
        "win_pct", "game_id", "numeric", team_scoped=True,
        description=(
            "Win percentage from prior games this season (0–1). Entering-game value; current game excluded. "
            "Team-scoped; use perspective to pick which team."
        ),
    ),
    FeatureDef(
        "running_ats_pct", "ATS Win % (to date)", "season_to_date", "computed_running",
        "ats_pct", "game_id", "numeric", team_scoped=True,
        description=(
            "Against-the-spread win percentage from prior games this season (0–1). "
            "Entering-game value; current game excluded. Team-scoped."
        ),
    ),
    FeatureDef(
        "running_streak", "Win/Loss Streak (to date)", "season_to_date", "computed_running",
        "streak", "game_id", "numeric", team_scoped=True,
        description=(
            "Signed current win/loss run entering this game: +3 means won the last 3, "
            "-2 means lost the last 2, 0 for a season opener or after a tie. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_ats_streak", "ATS Streak (to date)", "season_to_date", "computed_running",
        "ats_streak", "game_id", "numeric", team_scoped=True,
        description=(
            "Signed current against-the-spread run entering this game: +3 means covered the "
            "last 3, -2 means failed to cover the last 2, 0 for a season opener or after an "
            "ATS push. Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_ppa_off", "Off PPA (to date)", "season_to_date", "computed_running",
        "ppa_off", "game_id", "numeric", team_scoped=True,
        description=(
            "Average offensive PPA from prior games this season. Higher is more productive. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_ppa_def", "Def PPA (to date)", "season_to_date", "computed_running",
        "ppa_def", "game_id", "numeric", team_scoped=True,
        description=(
            "Average defensive PPA allowed from prior games this season. Lower is better defense. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_success_off", "Off Success Rate (to date)", "season_to_date", "computed_running",
        "adv_success_off", "game_id", "numeric", team_scoped=True,
        description=(
            "Offensive success rate from prior games this season (0–1). Higher is better. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_success_def", "Def Success Rate (to date)", "season_to_date", "computed_running",
        "adv_success_def", "game_id", "numeric", team_scoped=True,
        description=(
            "Defensive success rate allowed from prior games this season (0–1). Lower is better. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_explosiveness_off", "Off Explosiveness (to date)", "season_to_date", "computed_running",
        "adv_explosiveness_off", "game_id", "numeric", team_scoped=True,
        description=(
            "Offensive explosiveness from prior games this season. Higher means more big plays. "
            "Entering-game value; team-scoped."
        ),
    ),
    FeatureDef(
        "running_explosiveness_def", "Def Explosiveness (to date)", "season_to_date", "computed_running",
        "adv_explosiveness_def", "game_id", "numeric", team_scoped=True,
        description=(
            "Defensive explosiveness allowed from prior games this season. Lower is better. "
            "Entering-game value; team-scoped."
        ),
    ),
    # --- v1 model (computed, fit-cached) ---
    FeatureDef(
        "v1_over_prob",
        "V1 Over Probability",
        "betting_lines",
        "computed_v1",
        "over_prob",
        "game_id",
        "numeric",
        description=(
            "P(over) from the over-zero v1 censoring-bias model (Arscott 2022 recreation), "
            "fit on historical games.csv and applied to this game's spread/total (no scores "
            "needed). Run `cfb-system-maker refit-v1` to (re)fit; null until a fit is cached. "
            "Break-even at standard -110 pricing is 0.5238."
        ),
    ),
    # --- result lookahead ---
    FeatureDef(
        "havoc_offense_rate",
        "Offense Havoc Rate",
        "result_lookahead",
        "raw_havoc",
        "offense.havocRate",
        "game_id",
        "numeric",
        team_scoped=True,
        description=(
            "Offense havoc rate for this completed game. Team-scoped. "
            "Analysis-only / lookahead — uses post-game result data, not available for live betting."
        ),
    ),
    FeatureDef(
        "havoc_defense_rate",
        "Defense Havoc Rate",
        "result_lookahead",
        "raw_havoc",
        "defense.havocRate",
        "game_id",
        "numeric",
        team_scoped=True,
        description=(
            "Defense havoc rate for this completed game. Team-scoped. "
            "Analysis-only / lookahead — uses post-game result data, not available for live betting."
        ),
    ),
    FeatureDef(
        "attendance", "Attendance", "result_lookahead", "raw_game", "attendance", "game_id", "numeric",
        description=(
            "Reported game attendance (people). Analysis-only / lookahead — typically known after kickoff "
            "or final, not a pure pregame betting input."
        ),
    ),
    FeatureDef(
        "coach_style_cluster",
        "Coach Playstyle Cluster",
        "result_lookahead",
        "raw_coaches",
        "coach_style_cluster",
        "team_season",
        "categorical",
        team_scoped=True,
        description=(
            "Head coach playstyle group: one of option_ground, attack_defense, bend_dont_break, "
            "pass_first_efficient, balanced_spread. k=5 k-means over quality-stripped (SP+-residualized) "
            "advanced season stats 2016-2024, coaches with 3+ seasons; regenerate with "
            "scripts/build_coach_style_clusters.py. Career-level label, so early-season games read a "
            "label informed by the coach's later seasons — quarantined as lookahead; use for grouping "
            "and analysis, not as a discovered betting edge."
        ),
    ),
    FeatureDef(
        "core_overall",
        "Core Rating (this season)",
        "result_lookahead",
        "raw_team_season",
        "overall",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="core_ratings",
        description=(
            "CFBD core rating (overall) for THIS season. Season-final (through postseason). "
            "Analysis-only / lookahead — not an entering-game value. For a pregame number use "
            "Prior-Season Core Rating."
        ),
    ),
    FeatureDef(
        "defense_explosiveness",
        "Def Explosiveness (this game, NGT)",
        "result_lookahead",
        "raw_adv_ngt",
        "defense.explosiveness",
        "game_id",
        "numeric",
        team_scoped=True,
        source_file="advanced_game_stats_ngt",
        description=(
            "Defensive explosiveness allowed in this completed game, garbage time excluded. "
            "Team-scoped. Analysis-only / lookahead — post-game, not available for live betting. "
            "For an entering-game value use Def Explosiveness (to date)."
        ),
    ),
    FeatureDef(
        "defense_passingDowns_ppa",
        "Def Passing-Downs PPA (this game, NGT)",
        "result_lookahead",
        "raw_adv_ngt",
        "defense.passingDowns.ppa",
        "game_id",
        "numeric",
        team_scoped=True,
        source_file="advanced_game_stats_ngt",
        description=(
            "Defensive PPA allowed on passing downs in this completed game, garbage time excluded. "
            "Team-scoped. Analysis-only / lookahead — post-game, not available for live betting."
        ),
    ),
    FeatureDef(
        "defense_ppa",
        "Def PPA (this game, NGT)",
        "result_lookahead",
        "raw_adv_ngt",
        "defense.ppa",
        "game_id",
        "numeric",
        team_scoped=True,
        source_file="advanced_game_stats_ngt",
        description=(
            "Defensive PPA allowed in this completed game, garbage time excluded. Team-scoped. "
            "Analysis-only / lookahead — post-game, not available for live betting. "
            "For an entering-game value use Def PPA (to date)."
        ),
    ),
    FeatureDef(
        "defense_rushingPlays_ppa",
        "Def Rushing PPA (this game, NGT)",
        "result_lookahead",
        "raw_adv_ngt",
        "defense.rushingPlays.ppa",
        "game_id",
        "numeric",
        team_scoped=True,
        source_file="advanced_game_stats_ngt",
        description=(
            "Defensive PPA allowed on rushing plays in this completed game, garbage time excluded. "
            "Team-scoped. Analysis-only / lookahead — post-game, not available for live betting."
        ),
    ),
    FeatureDef(
        "defense_successRate",
        "Def Success Rate (this game, NGT)",
        "result_lookahead",
        "raw_adv_ngt",
        "defense.successRate",
        "game_id",
        "numeric",
        team_scoped=True,
        source_file="advanced_game_stats_ngt",
        description=(
            "Defensive success rate allowed in this completed game (0–1), garbage time excluded. "
            "Team-scoped. Analysis-only / lookahead — post-game, not available for live betting. "
            "For an entering-game value use Def Success Rate (to date)."
        ),
    ),
)

FEATURE_BY_KEY: dict[str, FeatureDef] = {feature.key: feature for feature in FEATURE_REGISTRY}


def format_kickoff_hour(value: object) -> str:
    """Display a 0–23 Eastern hour as a 12-hour clock time."""
    try:
        hour = int(value)
    except (TypeError, ValueError):
        return str(value)
    hour = hour % 24
    meridiem = "AM" if hour < 12 else "PM"
    display = hour % 12 or 12
    return f"{display}:00 {meridiem}"


def registry_keys_unique() -> bool:
    return len(FEATURE_BY_KEY) == len(FEATURE_REGISTRY)


def registry_version() -> str:
    digest = hashlib.sha256(",".join(sorted(FEATURE_BY_KEY)).encode("utf-8")).hexdigest()
    return digest[:12]


def get_nested(row: dict[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def effective_perspective(bet_type: str, perspective: str) -> str:
    """bet_side/opponent need a spread's home/away side; a total bet has none.

    On total systems those perspectives used to fall through to the vestigial
    SystemFilter.side default and silently resolve to a fixed home/away side.
    They collapse to "either" instead, which describe() discloses as
    "Either team's ...".
    """
    if bet_type == "total" and perspective in {"bet_side", "opponent"}:
        return "either"
    return perspective


def resolve_storage_key(feature: FeatureDef, perspective: str) -> str:
    if not feature.team_scoped or perspective in {"single", ""}:
        return feature.key
    if perspective in {"home", "away", "bet_side", "opponent", "either"}:
        side = "home" if perspective in {"home", "bet_side"} else "away"
        if perspective == "opponent":
            side = "away"
        if perspective == "either":
            return f"either_{feature.key}"
        return f"{side}_{feature.key}"
    return feature.key


def resolve_feature_value(
    features: dict[str, Any],
    feature: FeatureDef,
    filt: FeatureFilterLike,
    system: SystemFilterLike,
) -> Any:
    perspective = filt.perspective or "single"
    if not feature.team_scoped or perspective in {"single", ""}:
        return features.get(feature.key)

    if perspective == "either":
        home_val = features.get(f"home_{feature.key}")
        away_val = features.get(f"away_{feature.key}")
        return (home_val, away_val)

    side = _perspective_to_side(perspective, system)
    return features.get(f"{side}_{feature.key}")


def _perspective_to_side(perspective: str, system: SystemFilterLike) -> str:
    if perspective == "home":
        return "home"
    if perspective == "away":
        return "away"
    if perspective == "bet_side":
        return system.side.lower()
    if perspective == "opponent":
        return "away" if system.side.lower() == "home" else "home"
    return "home"


class FeatureFilterLike:
    key: str
    perspective: str
    op: str
    value: object


class SystemFilterLike:
    side: str
    bet_type: str


def feature_ok(
    features: dict[str, Any],
    filt: FeatureFilterLike,
    system: SystemFilterLike,
) -> bool:
    feature = FEATURE_BY_KEY.get(filt.key)
    if feature is None:
        return False

    value = resolve_feature_value(features, feature, filt, system)
    if value is None:
        return False

    if filt.perspective == "either" and isinstance(value, tuple):
        home_val, away_val = value
        return any(
            candidate is not None and _value_matches(filt.op, filt.value, candidate)
            for candidate in (home_val, away_val)
        )

    return _value_matches(filt.op, filt.value, value)


def _value_matches(op: str, expected: object, actual: Any) -> bool:
    # Negated ops are spelled out rather than wrapping the positive result in
    # `not`. Callers (feature_ok) drop null values before dispatching here, so
    # "not X" always means "has a value, and it is not X" -- a missing feature
    # never satisfies a negation.
    if op == "eq":
        return actual == expected
    if op == "not_eq":
        return actual != expected
    if op == "in":
        return actual in expected  # type: ignore[operator]
    if op == "not_in":
        return actual not in expected  # type: ignore[operator]
    if op == "gte":
        return float(actual) >= float(expected)  # type: ignore[arg-type]
    if op == "lte":
        return float(actual) <= float(expected)  # type: ignore[arg-type]
    if op == "gt":
        return float(actual) > float(expected)  # type: ignore[arg-type]
    if op == "lt":
        return float(actual) < float(expected)  # type: ignore[arg-type]
    raise ValueError(f"unsupported op: {op}")
