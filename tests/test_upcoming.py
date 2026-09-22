"""Network-free tests for the upcoming-games data path.

The fake CFBD module follows the class shape in tests/test_scrapers.py, extended
with ``get_calendar`` and a ``BettingApi``. Every test passes ``now`` explicitly so
week resolution is deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from cfb_system_maker.upcoming import build_upcoming, resolve_target_week

UTC = timezone.utc

# Anchor for the multi-week accumulation fixture: week N runs [_week_start(N), _week_start(N+1)).
_SEASON_ANCHOR = datetime(2026, 8, 31, tzinfo=UTC)


def _dt(year, month, day, hour=19):
    return datetime(year, month, day, hour, tzinfo=UTC)


def _week_start(week):
    return _SEASON_ANCHOR + timedelta(days=7 * (week - 1))


def _kickoff(week):
    return _week_start(week) + timedelta(days=5, hours=19)


def _game(game_id, season, week, season_type, start, *, completed, tbd=False, home="Alpha", away="Beta"):
    return {
        "id": game_id,
        "season": season,
        "week": week,
        "seasonType": season_type,
        "startDate": start,
        "startTimeTBD": tbd,
        "completed": completed,
        "homeTeam": home,
        "awayTeam": away,
        "homeConference": "SEC",
        "awayConference": "Big Ten",
        "homePoints": 28 if completed else None,
        "awayPoints": 21 if completed else None,
    }


def _lined(game_id, spread=-7.0, total=52.5):
    return {
        "id": game_id,
        "lines": [{"provider": "DraftKings", "spread": spread, "overUnder": total}],
    }


def _calendar_week(season, week, season_type, start, end):
    return {
        "season": season,
        "week": week,
        "seasonType": season_type,
        "startDate": start,
        "endDate": end,
    }


def default_data():
    """Fresh (calendars, games, lines) fixtures. Tests mutate before building a module.

    2025 is a finished season: regular weeks 1-2 plus a postseason week 1 played in
    January 2026 -- the postseason week is the LATEST by start date even though its
    week number is lower, which is why resolution must never compare week numbers
    across season types.

    2026 is the current season: a calendar exists but no game has been played.
    """
    calendars = {
        2025: [
            _calendar_week(2025, 1, "regular", _dt(2025, 8, 30), _dt(2025, 9, 8)),
            _calendar_week(2025, 2, "regular", _dt(2025, 9, 8), _dt(2025, 9, 15)),
            _calendar_week(2025, 1, "postseason", _dt(2025, 12, 15), _dt(2026, 1, 15)),
        ],
        2026: [
            _calendar_week(2026, 1, "regular", _dt(2026, 8, 29, 7), _dt(2026, 9, 8, 6)),
            _calendar_week(2026, 2, "regular", _dt(2026, 9, 8, 7), _dt(2026, 9, 14, 6)),
            _calendar_week(2026, 3, "regular", _dt(2026, 9, 14, 7), _dt(2026, 9, 21, 6)),
        ],
    }
    games = {
        2025: [
            _game(1001, 2025, 1, "regular", _dt(2025, 9, 6), completed=True, home="Alpha", away="Beta"),
            _game(1002, 2025, 2, "regular", _dt(2025, 9, 13), completed=True, home="Gamma", away="Delta"),
            _game(1003, 2025, 1, "postseason", _dt(2026, 1, 2), completed=True, home="Echo", away="Foxtrot"),
            _game(1004, 2025, 1, "postseason", _dt(2026, 1, 3), completed=True, home="Golf", away="Hotel"),
        ],
        2026: [
            _game(2001, 2026, 1, "regular", _dt(2026, 9, 5), completed=False, home="India", away="Juliet"),
            _game(2002, 2026, 1, "regular", _dt(2026, 9, 5), completed=False, tbd=True, home="Kilo", away="Lima"),
            _game(2003, 2026, 1, "regular", _dt(2026, 9, 6), completed=False, home="Mike", away="November"),
            _game(2004, 2026, 2, "regular", _dt(2026, 9, 12), completed=False, home="Oscar", away="Papa"),
        ],
    }
    lines = {
        # 1004 is deliberately unlined -> must never appear in the output (D-04).
        2025: [_lined(1001), _lined(1002), _lined(1003)],
        # 2003 carries a line row with no usable spread and no usable total -> also excluded.
        2026: [
            _lined(2001),
            _lined(2002),
            {"id": 2003, "lines": [{"provider": "DraftKings", "spread": None, "overUnder": None}]},
            _lined(2004),
        ],
    }
    return calendars, games, lines


def accumulating_season_data():
    """A 2026 season whose weeks 1-4 are played and whose week 5 is not.

    Alpha plays (and wins) all four completed weeks, so entering week 5 it must
    carry games_played=4 -- the assertion that catches an accumulation base built
    from the target week alone.

    Gamma's only completed game is unlined, so it is dropped by ``normalize_games``
    and Gamma legitimately enters week 5 with nothing accumulated.
    """
    calendars = {
        2026: [
            _calendar_week(2026, week, "regular", _week_start(week), _week_start(week + 1))
            for week in range(1, 6)
        ]
    }
    games = {
        2026: [
            _game(3000 + week, 2026, week, "regular", _kickoff(week), completed=True, home="Alpha", away="Beta")
            for week in range(1, 5)
        ]
        + [
            # Completed but unlined -> dropped from the accumulation base.
            _game(3010, 2026, 2, "regular", _kickoff(2), completed=True, home="Gamma", away="Delta"),
            # The target week: two unplayed games, both involving Alpha.
            _game(3005, 2026, 5, "regular", _kickoff(5), completed=False, home="Alpha", away="Gamma"),
            _game(3006, 2026, 5, "regular", _kickoff(5), completed=False, home="Echo", away="Alpha"),
        ]
    }
    lines = {2026: [_lined(3001), _lined(3002), _lined(3003), _lined(3004), _lined(3005), _lined(3006)]}
    return calendars, games, lines


def make_module(calendars, games, lines):
    """Return (fake cfbd module, recorded calls)."""
    calls: list[tuple[str, dict]] = []

    class _Config:
        def __init__(self, access_token=None):
            self.access_token = access_token

    class _Client:
        def __init__(self, configuration):
            self.configuration = configuration

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _slice(rows, season_type, week):
        if season_type and season_type != "both":
            rows = [row for row in rows if row["seasonType"] == season_type]
        if week is not None:
            rows = [row for row in rows if row["week"] == week]
        return rows

    class _GamesApi:
        def __init__(self, client):
            pass

        def get_calendar(self, year=None):
            calls.append(("get_calendar", {"year": year}))
            return [dict(row) for row in calendars.get(year, [])]

        def get_games(self, year=None, week=None, season_type=None, **rest):
            calls.append(("get_games", {"year": year, "week": week, "season_type": season_type}))
            return [dict(row) for row in _slice(games.get(year, []), season_type, week)]

    class _BettingApi:
        def __init__(self, client):
            pass

        def get_lines(self, year=None, week=None, season_type=None, provider=None, **rest):
            calls.append(("get_lines", {"year": year, "week": week, "season_type": season_type}))
            wanted = {row["id"] for row in _slice(games.get(year, []), season_type, week)}
            return [dict(row) for row in lines.get(year, []) if row["id"] in wanted]

    module = SimpleNamespace(
        Configuration=_Config,
        ApiClient=_Client,
        GamesApi=_GamesApi,
        BettingApi=_BettingApi,
    )
    return module, calls


def _fake(**mutate):
    calendars, games, lines = default_data()
    for key, fn in mutate.items():
        fn({"calendars": calendars, "games": games, "lines": lines}[key])
    return make_module(calendars, games, lines)


# --- week resolution -------------------------------------------------------


def test_in_season_now_inside_calendar_window_resolves_that_week():
    module, _ = _fake()

    resolution = resolve_target_week(_dt(2026, 9, 1), cfbd_module=module, token="test")

    assert (resolution.season, resolution.week, resolution.season_type) == (2026, 1, "regular")
    assert resolution.is_fallback is False


def test_offseason_same_season_falls_back_to_latest_completed_week():
    def add_completed(games):
        games[2026].append(
            _game(2100, 2026, 3, "regular", _dt(2026, 9, 19), completed=True, home="Quebec", away="Romeo")
        )

    module, _ = _fake(games=add_completed)

    # After the last 2026 calendar window ends, but 2026 has a completed week.
    resolution = resolve_target_week(_dt(2026, 12, 20), cfbd_module=module, token="test")

    assert (resolution.season, resolution.week, resolution.season_type) == (2026, 3, "regular")
    assert resolution.is_fallback is True


def test_offseason_with_no_completed_games_steps_back_to_prior_season():
    module, _ = _fake()

    # Today's real state: 2026 has a calendar but no game has been played yet.
    resolution = resolve_target_week(_dt(2026, 7, 20), cfbd_module=module, token="test")

    assert resolution.season == 2025
    assert resolution.is_fallback is True


def test_fallback_prefers_latest_start_date_not_highest_week_number():
    module, _ = _fake()

    resolution = resolve_target_week(_dt(2026, 7, 20), cfbd_module=module, token="test")

    # Postseason week 1 (Jan 2026) is later than regular week 2 (Sep 2025),
    # even though its week number is lower.
    assert (resolution.week, resolution.season_type) == (1, "postseason")


def test_postseason_calendar_window_resolves_with_postseason_season_type():
    module, _ = _fake()

    resolution = resolve_target_week(_dt(2026, 1, 2), cfbd_module=module, token="test")

    assert (resolution.season, resolution.week, resolution.season_type) == (2025, 1, "postseason")
    assert resolution.is_fallback is False


def test_no_resolvable_week_returns_empty_resolution():
    module, _ = make_module({}, {}, {})

    resolution = resolve_target_week(_dt(2026, 7, 20), cfbd_module=module, token="test")

    assert resolution.season is None
    assert resolution.week is None


# --- build -----------------------------------------------------------------


def _build(tmp_path, now, **mutate):
    module, calls = _fake(**mutate)
    result = build_upcoming(tmp_path, now=now, cfbd_module=module, token="test")
    return result, calls


def test_build_writes_upcoming_files_and_never_touches_games_csv(tmp_path):
    _build(tmp_path, _dt(2026, 9, 1))

    assert (tmp_path / "processed" / "upcoming.csv").exists()
    assert (tmp_path / "processed" / "upcoming_meta.json").exists()
    assert not (tmp_path / "processed" / "games.csv").exists()


def test_unlined_games_produce_no_row(tmp_path):
    result, _ = _build(tmp_path, _dt(2026, 9, 1))

    ids = {record.game_id for record in result.records}
    assert ids == {2001, 2002}  # 2003 has no usable line; 2004 is a different week


def test_postseason_fallback_build_returns_only_that_weeks_lined_games(tmp_path):
    result, _ = _build(tmp_path, _dt(2026, 7, 20))

    assert result.meta["season"] == 2025
    assert result.meta["season_type"] == "postseason"
    assert result.meta["week"] == 1
    assert result.meta["is_fallback"] is True
    # 1003 is lined; 1004 is not; 1001/1002 are earlier regular-season weeks.
    assert {record.game_id for record in result.records} == {1003}


def test_raw_dumps_cover_the_full_season_not_just_the_target_week(tmp_path):
    _build(tmp_path, _dt(2026, 7, 20))

    games = json.loads((tmp_path / "raw" / "games_2025.json").read_text(encoding="utf-8"))
    lines = json.loads((tmp_path / "raw" / "lines_2025.json").read_text(encoding="utf-8"))

    # Plan 05-04 rebuilds its running-stats accumulation base from these files and
    # cannot recover a completed game that was never written.
    assert 1001 in {row["id"] for row in games}
    assert 1001 in {row["id"] for row in lines}


def test_every_row_carries_kickoff_and_the_tbd_flag(tmp_path):
    result, _ = _build(tmp_path, _dt(2026, 9, 1))

    for record in result.records:
        assert record.game_id in result.kickoffs
        assert result.kickoffs[record.game_id]["start_date"] is not None

    assert result.kickoffs[2001]["start_time_tbd"] is False
    assert result.kickoffs[2002]["start_time_tbd"] is True


def test_meta_records_resolution_and_fetch_timestamp(tmp_path):
    result, _ = _build(tmp_path, _dt(2026, 9, 1))

    meta = json.loads((tmp_path / "processed" / "upcoming_meta.json").read_text(encoding="utf-8"))
    assert meta["season"] == 2026
    assert meta["week"] == 1
    assert meta["season_type"] == "regular"
    assert meta["is_fallback"] is False
    assert meta["row_count"] == 2
    assert meta["fetched_at"]
    assert meta == result.meta


def test_no_resolution_writes_empty_but_valid_output(tmp_path):
    module, _ = make_module({}, {}, {})

    result = build_upcoming(tmp_path, now=_dt(2026, 7, 20), cfbd_module=module, token="test")

    meta = json.loads((tmp_path / "processed" / "upcoming_meta.json").read_text(encoding="utf-8"))
    assert result.records == []
    assert meta["season"] is None
    assert meta["row_count"] == 0
    assert (tmp_path / "processed" / "upcoming.csv").exists()


def test_saved_upcoming_round_trips_with_null_scores(tmp_path):
    from cfb_system_maker.storage import load_upcoming_games

    _build(tmp_path, _dt(2026, 9, 1))

    records, kickoffs = load_upcoming_games(tmp_path)

    assert {record.game_id for record in records} == {2001, 2002}
    for record in records:
        assert record.home_points is None
        assert record.away_points is None
    assert kickoffs[2002]["start_time_tbd"] is True


# --- running-stats accumulation over the union (D-05) ----------------------


def _upcoming_features(tmp_path):
    from cfb_system_maker.enrich import load_features_from, upcoming_features_path

    return {
        str(game_id): row
        for game_id, row in load_features_from(upcoming_features_path(tmp_path)).items()
    }


def _build_accumulating(tmp_path):
    module, _ = make_module(*accumulating_season_data())
    # Inside the week-5 calendar window: week 5 is the target, weeks 1-4 are played.
    build_upcoming(tmp_path, now=_week_start(5) + timedelta(days=1), cfbd_module=module, token="test")
    return _upcoming_features(tmp_path)


def test_unplayed_game_carries_entering_game_values_from_its_prior_weeks(tmp_path):
    features = _build_accumulating(tmp_path)

    row = features["3005"]
    # Alpha played and won weeks 1-4, all lined. Zero here would mean the completed
    # weeks never reached compute_running_stats -- the silent D-05 failure.
    assert row["home_running_games_played"] == 4
    assert row["home_running_win_pct"] == 1.0


def test_unlined_completed_game_is_dropped_from_the_accumulation_base(tmp_path):
    features = _build_accumulating(tmp_path)

    # Gamma's only completed game (3010) carries no line, so normalize_games drops it.
    assert features["3005"]["away_running_games_played"] == 0
    assert features["3005"]["away_running_win_pct"] is None


def test_unplayed_games_do_not_contaminate_each_other(tmp_path):
    features = _build_accumulating(tmp_path)

    # Alpha appears in both unplayed week-5 games; neither folds into the other.
    assert features["3005"]["home_running_games_played"] == 4
    assert features["3006"]["away_running_games_played"] == 4
    assert features["3006"]["away_running_win_pct"] == 1.0


def test_only_target_week_games_are_emitted(tmp_path):
    features = _build_accumulating(tmp_path)

    # Weeks 1-4 are accumulation input, not output.
    assert set(features) == {"3005", "3006"}


def test_week_one_unplayed_game_legitimately_has_no_prior_state(tmp_path):
    _build(tmp_path, _dt(2026, 9, 1))

    row = _upcoming_features(tmp_path)["2001"]
    # Correct behavior, not a bug: a season-to-date filter should not fire in week 1.
    assert row["home_running_games_played"] == 0
    assert row["home_running_win_pct"] is None


def test_post_game_sourced_features_are_null_for_an_unplayed_game(tmp_path):
    features = _build_accumulating(tmp_path)

    row = features["3005"]
    assert "attendance" not in row
    assert row["weather_temperature"] is None  # near-game, never fetched here


def test_no_resolution_still_writes_a_valid_empty_sidecar(tmp_path):
    module, _ = make_module({}, {}, {})

    build_upcoming(tmp_path, now=_dt(2026, 7, 20), cfbd_module=module, token="test")

    assert _upcoming_features(tmp_path) == {}


def test_season_type_enum_is_normalized_to_its_value(tmp_path):
    """Real CFBD rows carry a SeasonType enum, not a plain string."""

    class _SeasonType(str):
        def __str__(self):
            return "SeasonType.POSTSEASON"

        @property
        def value(self):
            return "postseason"

    def enumify(games):
        for row in games[2025]:
            if row["seasonType"] == "postseason":
                row["seasonType"] = _SeasonType("postseason")

    module, _ = _fake(games=enumify)
    result = build_upcoming(tmp_path, now=_dt(2026, 7, 20), cfbd_module=module, token="test")

    assert result.meta["season_type"] == "postseason"
    assert {record.game_id for record in result.records} == {1003}
