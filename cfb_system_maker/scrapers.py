"""Generic scraper framework over the full CFBD API.

Every CFBD endpoint is registered as an ``Endpoint`` with a *mode* describing
how it is parameterized. One runner drives them all, saving raw JSON under
``data/raw/`` (one file per endpoint, suffixed by season/week when relevant).
Raw JSON is the load format for Postgres later (a JSONB staging column).
"""

from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cfb_system_maker.cfbd_client import _load_cfbd_module, _to_dict, find_cfbd_token
from cfb_system_maker.storage import load_raw_json, save_raw

# Scrape modes.
ONCE = "once"          # no per-season params; one file `{name}.json`
SEASON = "season"      # loop seasons; one file per season
SEASON_WEEK = "season_week"  # loop seasons x weeks (year + week both required)
GRID = "grid"          # predicted points: down x distance grid, one file
PER_GAME = "per_game"  # fan out over game ids from scraped games (opt-in)
PER_PLAYER = "per_player"  # fan out over player ids from scraped rosters (opt-in)
ON_DEMAND = "on_demand"    # live/lookup-by-key; not run in bulk


@dataclass(frozen=True)
class Endpoint:
    name: str             # output file prefix
    api: str              # cfbd Api class name
    method: str           # method on that class
    mode: str
    fixed: dict[str, Any] = field(default_factory=dict)  # constant kwargs
    min_season: int | None = None  # endpoint has no data before this year; earlier ones are skipped


ENDPOINTS: list[Endpoint] = [
    # Adjusted metrics
    Endpoint("adjusted_player_passing", "AdjustedMetricsApi", "get_adjusted_player_passing_stats", SEASON),
    Endpoint("adjusted_player_rushing", "AdjustedMetricsApi", "get_adjusted_player_rushing_stats", SEASON),
    Endpoint("adjusted_team_season", "AdjustedMetricsApi", "get_adjusted_team_season_stats", SEASON),
    Endpoint("kicker_paar", "AdjustedMetricsApi", "get_kicker_paar", SEASON),
    # Betting
    Endpoint("lines", "BettingApi", "get_lines", SEASON),
    # Coaches
    Endpoint("coaches", "CoachesApi", "get_coaches", SEASON),
    Endpoint("coach_seasons", "CoachesApi", "get_coach_seasons", SEASON),  # 400s unfiltered
    Endpoint("coach_profile", "CoachesApi", "get_coach_profile", ON_DEMAND),   # requires coach_id
    Endpoint("coach_tenures", "CoachesApi", "get_coach_tenures", ON_DEMAND),   # 400s without team/coach_id
    # Conferences
    Endpoint("conferences", "ConferencesApi", "get_conferences", ONCE),
    # Full affiliation history in one call (3.6k rows); per-season would just duplicate spans.
    Endpoint("conference_affiliations", "ConferencesApi", "get_team_conference_affiliations", ONCE),
    Endpoint("conference_changes", "ConferencesApi", "get_team_conference_changes", SEASON),
    # Draft
    Endpoint("draft_picks", "DraftApi", "get_draft_picks", SEASON),
    Endpoint("draft_positions", "DraftApi", "get_draft_positions", ONCE),
    Endpoint("draft_teams", "DraftApi", "get_draft_teams", ONCE),
    # Drives
    Endpoint("drives", "DrivesApi", "get_drives", SEASON),
    # Games
    Endpoint("advanced_box_score", "GamesApi", "get_advanced_box_score", PER_GAME),
    Endpoint("calendar", "GamesApi", "get_calendar", SEASON),
    Endpoint("game_player_stats", "GamesApi", "get_game_player_stats", SEASON_WEEK),  # requires week/team/conf
    Endpoint("game_team_stats", "GamesApi", "get_game_team_stats", SEASON_WEEK),      # requires week/team/conf
    Endpoint("games", "GamesApi", "get_games", SEASON),
    Endpoint("media", "GamesApi", "get_media", SEASON),
    Endpoint("records", "GamesApi", "get_records", SEASON),
    Endpoint("scoreboard", "GamesApi", "get_scoreboard", ON_DEMAND),
    Endpoint("weather", "GamesApi", "get_weather", SEASON),  # Patreon-only; may 4xx
    # Info
    Endpoint("user_info", "InfoApi", "get_user_info", ONCE),
    # Metrics
    Endpoint("field_goal_ep", "MetricsApi", "get_field_goal_expected_points", ONCE),
    Endpoint("predicted_points", "MetricsApi", "get_predicted_points", GRID),
    Endpoint("ppa_games", "MetricsApi", "get_predicted_points_added_by_game", SEASON),
    Endpoint("ppa_players_games", "MetricsApi", "get_predicted_points_added_by_player_game", SEASON_WEEK),  # requires week or team
    Endpoint("ppa_players_season", "MetricsApi", "get_predicted_points_added_by_player_season", SEASON),
    Endpoint("ppa_teams", "MetricsApi", "get_predicted_points_added_by_team", SEASON),
    Endpoint("pregame_win_prob", "MetricsApi", "get_pregame_win_probabilities", SEASON),
    Endpoint("win_probability", "MetricsApi", "get_win_probability", PER_GAME),
    # Players
    Endpoint("player_season_overview", "PlayersApi", "get_player_season_overview", PER_PLAYER),
    Endpoint("player_usage", "PlayersApi", "get_player_usage", SEASON),
    Endpoint("returning_production", "PlayersApi", "get_returning_production", SEASON),
    Endpoint("transfer_portal", "PlayersApi", "get_transfer_portal", SEASON),
    Endpoint("player_search", "PlayersApi", "search_players", ON_DEMAND),
    # Plays
    Endpoint("live_plays", "PlaysApi", "get_live_plays", ON_DEMAND),
    Endpoint("play_stat_types", "PlaysApi", "get_play_stat_types", ONCE),
    Endpoint("play_stats", "PlaysApi", "get_play_stats", SEASON_WEEK),  # requires week or team
    Endpoint("play_types", "PlaysApi", "get_play_types", ONCE),
    Endpoint("plays", "PlaysApi", "get_plays", SEASON_WEEK),
    # Playoffs (CFP began in 2014; earlier seasons error rather than returning empty)
    Endpoint("cfp_playoff", "PlayoffsApi", "get_cfp_playoff", SEASON, min_season=2014),
    Endpoint("cfp_games", "PlayoffsApi", "get_cfp_games", SEASON, min_season=2014),
    Endpoint("cfp_participants", "PlayoffsApi", "get_cfp_participants", SEASON, min_season=2014),
    # Rankings
    Endpoint("rankings", "RankingsApi", "get_rankings", SEASON),
    # Ratings
    Endpoint("conference_sp", "RatingsApi", "get_conference_sp", SEASON),
    Endpoint("elo", "RatingsApi", "get_elo", SEASON),
    Endpoint("fpi", "RatingsApi", "get_fpi", SEASON),
    Endpoint("sp", "RatingsApi", "get_sp", SEASON),
    Endpoint("srs", "RatingsApi", "get_srs", SEASON),
    Endpoint("core_ratings", "RatingsApi", "get_core", SEASON),      # empty before the rollout
    Endpoint("srs_expanded", "RatingsApi", "get_expanded_srs", SEASON),  # FCS included
    # Recruiting
    Endpoint("recruiting_groups", "RecruitingApi", "get_aggregated_team_recruiting_ratings", ONCE),
    Endpoint("recruits", "RecruitingApi", "get_recruits", SEASON),
    Endpoint("recruiting_teams", "RecruitingApi", "get_team_recruiting_rankings", SEASON),
    # Stats
    Endpoint("advanced_game_stats", "StatsApi", "get_advanced_game_stats", SEASON),
    Endpoint("advanced_season_stats", "StatsApi", "get_advanced_season_stats", SEASON),
    Endpoint("stat_categories", "StatsApi", "get_categories", ONCE),
    Endpoint("game_havoc_stats", "StatsApi", "get_game_havoc_stats", SEASON),
    Endpoint("player_season_stats", "StatsApi", "get_player_season_stats", SEASON),
    Endpoint("player_success_season", "StatsApi", "get_player_season_success_rates", SEASON),
    Endpoint("player_success_game", "StatsApi", "get_player_game_success_rates", SEASON_WEEK),  # requires week or team
    Endpoint("team_stats", "StatsApi", "get_team_stats", SEASON),
    # Teams
    Endpoint("fbs_teams", "TeamsApi", "get_fbs_teams", SEASON),
    Endpoint("matchup", "TeamsApi", "get_matchup", ON_DEMAND),
    Endpoint("roster", "TeamsApi", "get_roster", SEASON),
    Endpoint("talent", "TeamsApi", "get_talent", SEASON),
    Endpoint("teams", "TeamsApi", "get_teams", SEASON),
    Endpoint("teams_ats", "TeamsApi", "get_teams_ats", SEASON),
    # Venues
    Endpoint("venues", "VenuesApi", "get_venues", ONCE),
]


@dataclass(frozen=True)
class ScrapeReport:
    name: str
    mode: str
    files: int   # files written this run
    rows: int    # records pulled this run
    skipped: int = 0  # files already present, skipped (resume)
    error: str | None = None


def scrape(
    seasons: list[int],
    *,
    data_dir: str | Path = "data",
    season_type: str = "both",
    weeks: range = range(1, 16),
    include_per_game: bool = False,
    include_per_player: bool = False,
    only: set[str] | None = None,
    token: str | None = None,
    delay: float = 1.0,
    resume: bool = True,
    fbs_only: bool = False,
    cfbd_module: Any = None,
) -> list[ScrapeReport]:
    """Run every applicable endpoint. ``cfbd_module`` is injectable for tests."""
    cfbd = cfbd_module or _load_cfbd_module()
    configuration = cfbd.Configuration(access_token=token or find_cfbd_token())

    reports: list[ScrapeReport] = []
    with cfbd.ApiClient(configuration) as client:
        api_cache: dict[str, Any] = {}
        for endpoint in ENDPOINTS:
            if only is not None and endpoint.name not in only:
                continue
            if endpoint.mode == ON_DEMAND:
                continue
            if endpoint.mode == PER_GAME and not include_per_game:
                continue
            if endpoint.mode == PER_PLAYER and not include_per_player:
                continue

            api = api_cache.setdefault(endpoint.api, getattr(cfbd, endpoint.api)(client))
            func = getattr(api, endpoint.method)
            reports.append(
                _run_endpoint(endpoint, func, seasons, data_dir, season_type, weeks, delay, resume, fbs_only)
            )
    return reports


def _run_endpoint(
    endpoint: Endpoint,
    func: Callable[..., Any],
    seasons: list[int],
    data_dir: str | Path,
    season_type: str,
    weeks: range,
    delay: float,
    resume: bool,
    fbs_only: bool,
) -> ScrapeReport:
    try:
        if endpoint.mode == ONCE:
            return _scrape_once(endpoint, func, data_dir, delay, resume)
        if endpoint.mode == SEASON:
            return _scrape_season(endpoint, func, seasons, data_dir, season_type, delay, resume)
        if endpoint.mode == SEASON_WEEK:
            return _scrape_season_week(endpoint, func, seasons, data_dir, season_type, weeks, delay, resume)
        if endpoint.mode == GRID:
            return _scrape_grid(endpoint, func, data_dir, delay, resume)
        if endpoint.mode == PER_GAME:
            return _scrape_per_game(endpoint, func, seasons, data_dir, delay, resume, fbs_only)
        if endpoint.mode == PER_PLAYER:
            return _scrape_per_player(endpoint, func, seasons, data_dir, delay, resume)
        raise ValueError(f"unknown mode {endpoint.mode}")
    except Exception as exc:  # one failing endpoint must not abort the run
        return ScrapeReport(endpoint.name, endpoint.mode, files=0, rows=0, error=f"{type(exc).__name__}: {exc}")


def _call(func: Callable[..., Any], kwargs: dict[str, Any], delay: float) -> list[dict[str, Any]]:
    """Call func with rate-limit retry and raw-JSON fallback for model validation errors."""
    time.sleep(delay)
    last: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return _rows(func(**kwargs))
        except Exception as exc:
            # Pydantic ValidationError or dict conversion error — bypass deserialization.
            # Checked first: a model error is not transient, so retrying cannot help.
            if _is_model_error(exc):
                return _call_raw(func, kwargs)
            backoff = _retry_backoff(exc, attempt)
            if backoff is None or attempt == _MAX_ATTEMPTS - 1:
                raise
            last = exc
            time.sleep(backoff)
    raise RuntimeError(f"max retries exceeded: {last}")  # unreachable; guards future edits


_MAX_ATTEMPTS = 3
_HTTP_RETRY_CODES = (500, 502, 503, 504)


def _retry_backoff(exc: Exception, attempt: int) -> float | None:
    """Seconds to wait before retrying ``exc``, or None if it is not retryable."""
    # Network-layer failure (DNS, connection reset, read timeout). urllib3.HTTPError is
    # the common base for MaxRetryError/NameResolutionError/ProtocolError/timeouts, and
    # the generated client lets these propagate unwrapped. A DNS outage can outlast the
    # HTTP schedule, so back off harder: 15/30s.
    if isinstance(exc, _urllib3_http_error()):
        return 15.0 * (2 ** attempt)
    # 429 = rate limit; 5xx = transient CFBD/Cloudflare outage.
    err = str(exc)
    if "429" in err or any(f"({code})" in err for code in _HTTP_RETRY_CODES):
        return 5.0 * (2 ** attempt)
    return None


def _urllib3_http_error() -> tuple[type[BaseException], ...]:
    try:
        import urllib3.exceptions  # noqa: PLC0415
    except Exception:  # urllib3 always present via the client, but never fail on import
        return ()
    return (urllib3.exceptions.HTTPError,)


def _is_model_error(exc: Exception) -> bool:
    name = type(exc).__name__
    return "ValidationError" in name or (isinstance(exc, ValueError) and "dictionary" in str(exc))


def _call_raw(func: Callable[..., Any], kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Bypass pydantic via the _with_http_info variant with _preload_content=False."""
    api = func.__self__
    raw_func = getattr(api, func.__func__.__name__ + "_with_http_info")
    response = raw_func(**{**kwargs, "_preload_content": False})
    data = json.loads(response.raw_data)
    return _rows(data)


def _scrape_once(endpoint: Endpoint, func: Callable[..., Any], data_dir: str | Path, delay: float, resume: bool) -> ScrapeReport:
    if resume and _exists(data_dir, f"{endpoint.name}.json"):
        return ScrapeReport(endpoint.name, endpoint.mode, files=0, rows=0, skipped=1)
    rows = _call(func, endpoint.fixed, delay)
    save_raw(data_dir, f"{endpoint.name}.json", rows)
    return ScrapeReport(endpoint.name, endpoint.mode, files=1, rows=len(rows))


def _scrape_season(
    endpoint: Endpoint,
    func: Callable[..., Any],
    seasons: list[int],
    data_dir: str | Path,
    season_type: str,
    delay: float,
    resume: bool,
) -> ScrapeReport:
    files = 0
    total = 0
    skipped = 0
    for season in seasons:
        # A season before the endpoint existed isn't an empty payload — CFBD errors, and
        # that error aborts every remaining season of this endpoint (see _run_endpoint).
        if endpoint.min_season is not None and season < endpoint.min_season:
            skipped += 1
            continue
        if resume and _exists(data_dir, f"{endpoint.name}_{season}.json"):
            skipped += 1
            continue
        kwargs = _accepted(func, {"year": season, "season_type": season_type}) | endpoint.fixed
        rows = _call(func, kwargs, delay)
        save_raw(data_dir, f"{endpoint.name}_{season}.json", rows)
        files += 1
        total += len(rows)
    return ScrapeReport(endpoint.name, endpoint.mode, files=files, rows=total, skipped=skipped)


def _postseason_weeks(data_dir: str | Path, season: int) -> list[int]:
    """Weeks that actually hold postseason games, read off the scraped games seed.

    Postseason is week 1 in most seasons, but not all: 2025 also has weeks 13 and 14
    (Division II/III playoffs begin in mid-November). Hardcoding week 1 would silently
    drop those 32 games, so the weeks come from the data rather than an assumption.
    Seasons whose seed file is missing get no postseason pass, the same way `per_game`
    skips a season with no game-id seed.
    """
    path = Path(data_dir) / "raw" / f"games_{season}.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return sorted({
        row["week"] for row in rows
        if (row.get("seasonType") or row.get("season_type")) == "postseason"
        and row.get("week") is not None
    })


# Filename prefix per season type. Regular keeps the original `_wk{n}` name so existing
# files stay valid; everything else gets its own axis and can never collide with it.
_WEEK_PREFIX = {"regular": "", "postseason": "post_"}


def _scrape_season_week(
    endpoint: Endpoint,
    func: Callable[..., Any],
    seasons: list[int],
    data_dir: str | Path,
    season_type: str,
    weeks: range,
    delay: float,
    resume: bool,
) -> ScrapeReport:
    """One pass per season type, each writing its own file — never the same one.

    Postseason week numbering restarts at 1, so a single `season_type="both"` call
    returns regular week 1 merged with postseason week 1 (probed 2026-08-28:
    game_team_stats 2024 wk1 gave regular=137, postseason=50, both=187, the union
    exactly). `{name}_{season}_wk{week}.json` has no season-type axis to hold them
    apart, so each pass asks for one type and postseason lands in
    `{name}_{season}_post_wk{week}.json` instead.
    """
    passes = ["regular", "postseason"] if season_type == "both" else [season_type]
    files = 0
    total = 0
    skipped = 0
    for season in seasons:
        for stype in passes:
            prefix = _WEEK_PREFIX.get(stype, f"{stype}_")
            week_list = _postseason_weeks(data_dir, season) if stype == "postseason" else weeks
            for week in week_list:
                filename = f"{endpoint.name}_{season}_{prefix}wk{week}.json"
                if resume and _exists(data_dir, filename):
                    skipped += 1
                    continue
                kwargs = _accepted(func, {"year": season, "week": week, "season_type": stype})
                rows = _call(func, kwargs, delay)
                if not rows:
                    continue
                save_raw(data_dir, filename, rows)
                files += 1
                total += len(rows)
    return ScrapeReport(endpoint.name, endpoint.mode, files=files, rows=total, skipped=skipped)


def _scrape_grid(endpoint: Endpoint, func: Callable[..., Any], data_dir: str | Path, delay: float, resume: bool) -> ScrapeReport:
    if resume and _exists(data_dir, f"{endpoint.name}.json"):
        return ScrapeReport(endpoint.name, endpoint.mode, files=0, rows=0, skipped=1)
    rows: list[dict[str, Any]] = []
    for down in range(1, 5):
        for distance in range(1, 31):
            rows.extend(_call(func, _accepted(func, {"down": down, "distance": distance}), delay))
    save_raw(data_dir, f"{endpoint.name}.json", rows)
    return ScrapeReport(endpoint.name, endpoint.mode, files=1, rows=len(rows))


def _scrape_per_game(
    endpoint: Endpoint,
    func: Callable[..., Any],
    seasons: list[int],
    data_dir: str | Path,
    delay: float,
    resume: bool,
    fbs_only: bool,
) -> ScrapeReport:
    files = 0
    total = 0
    skipped = 0
    failed_games = 0
    for season in seasons:
        # A season before the endpoint existed isn't an empty payload — CFBD errors, and
        # that error aborts every remaining season of this endpoint (see _run_endpoint).
        if endpoint.min_season is not None and season < endpoint.min_season:
            skipped += 1
            continue
        if resume and _exists(data_dir, f"{endpoint.name}_{season}.json"):
            skipped += 1
            continue
        try:
            game_ids = _seed_game_ids(data_dir, season, fbs_only)
        except FileNotFoundError:
            continue
        rows: list[dict[str, Any]] = []
        for game_id in game_ids:
            # A single game can 500 permanently upstream (retries exhausted). Skip it
            # rather than discarding every game already collected for this season.
            try:
                rows.extend(_call(func, _accepted(func, {"id": game_id, "game_id": game_id}), delay))
            except Exception:
                failed_games += 1
        if not rows:
            continue
        save_raw(data_dir, f"{endpoint.name}_{season}.json", rows)
        files += 1
        total += len(rows)
    if failed_games:
        # Not an endpoint-level failure: the season still wrote. Surface it so a
        # silent hole in per-game coverage is never mistaken for complete data.
        print(f"  {endpoint.name}: skipped {failed_games} game(s) that failed after retries")
    return ScrapeReport(endpoint.name, endpoint.mode, files=files, rows=total, skipped=skipped)


def _scrape_per_player(
    endpoint: Endpoint,
    func: Callable[..., Any],
    seasons: list[int],
    data_dir: str | Path,
    delay: float,
    resume: bool,
) -> ScrapeReport:
    files = 0
    total = 0
    skipped = 0
    for season in seasons:
        # A season before the endpoint existed isn't an empty payload — CFBD errors, and
        # that error aborts every remaining season of this endpoint (see _run_endpoint).
        if endpoint.min_season is not None and season < endpoint.min_season:
            skipped += 1
            continue
        if resume and _exists(data_dir, f"{endpoint.name}_{season}.json"):
            skipped += 1
            continue
        try:
            player_ids = _seed_ids(data_dir, f"roster_{season}.json", ("id", "playerId", "player_id"))
        except FileNotFoundError:
            continue
        rows: list[dict[str, Any]] = []
        for player_id in player_ids:
            kwargs = _accepted(func, {"year": season, "player_id": player_id})
            rows.extend(_call(func, kwargs, delay))
        if not rows:
            continue
        save_raw(data_dir, f"{endpoint.name}_{season}.json", rows)
        files += 1
        total += len(rows)
    return ScrapeReport(endpoint.name, endpoint.mode, files=files, rows=total, skipped=skipped)


def _exists(data_dir: str | Path, filename: str) -> bool:
    return (Path(data_dir) / "raw" / filename).exists()


def _seed_game_ids(data_dir: str | Path, season: int, fbs_only: bool) -> list[int]:
    """Game ids from games_{season}.json, optionally FBS-only (home or away in FBS)."""
    rows = load_raw_json(data_dir, "games", season)  # raises FileNotFoundError if unscraped
    ids: list[int] = []
    for row in rows:
        if fbs_only:
            home = str(_first(row, "homeClassification", "home_classification") or "").lower()
            away = str(_first(row, "awayClassification", "away_classification") or "").lower()
            if home != "fbs" and away != "fbs":
                continue
        gid = _first(row, "id", "gameId", "game_id")
        if gid is not None:
            ids.append(int(gid))
    return ids


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def _seed_ids(data_dir: str | Path, filename: str, keys: tuple[str, ...]) -> list[int]:
    name, _, season = filename.partition("_")
    season_num = int(season.removesuffix(".json"))
    try:
        rows = load_raw_json(data_dir, name, season_num)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"seed file {filename} missing; scrape its parent endpoint first") from exc
    ids: list[int] = []
    for row in rows:
        for key in keys:
            if row.get(key) is not None:
                ids.append(int(row[key]))
                break
    return ids


def _accepted(func: Callable[..., Any], candidates: dict[str, Any]) -> dict[str, Any]:
    params = inspect.signature(func).parameters
    return {key: value for key, value in candidates.items() if key in params}


def _rows(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [_to_dict(item) if not isinstance(item, (str, int, float, bool)) else {"value": item} for item in result]
    if isinstance(result, (str, int, float, bool)):
        return [{"value": result}]
    return [_to_dict(result)]
