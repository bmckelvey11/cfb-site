from cfb_system_maker.features import (
    FEATURE_BY_KEY,
    FEATURE_REGISTRY,
    feature_ok,
    registry_keys_unique,
    registry_version,
)

RUNNING_KEYS = (
    "running_games_played",
    "running_win_pct",
    "running_ats_pct",
    "running_ppa_off",
    "running_ppa_def",
    "running_success_off",
    "running_success_def",
    "running_explosiveness_off",
    "running_explosiveness_def",
)


def test_registry_keys_are_unique():
    assert registry_keys_unique()
    assert len(FEATURE_REGISTRY) >= 20


def test_registry_groups_are_valid():
    allowed = {"pregame", "season_to_date", "team_preseason", "metadata", "result_lookahead"}
    for feature in FEATURE_REGISTRY:
        assert feature.group in allowed
        assert feature.key in FEATURE_BY_KEY


def test_season_to_date_features_registered():
    assert registry_keys_unique()
    for key in RUNNING_KEYS:
        feature = FEATURE_BY_KEY[key]
        assert feature.group == "season_to_date"
        assert feature.source_kind == "computed_running"
        assert feature.control == "numeric"
        assert feature.team_scoped is True


def test_season_to_date_fields_match_running_stats_output():
    expected = {
        "games_played",
        "win_pct",
        "ats_pct",
        "ppa_off",
        "ppa_def",
        "adv_success_off",
        "adv_success_def",
        "adv_explosiveness_off",
        "adv_explosiveness_def",
    }
    fields = {FEATURE_BY_KEY[key].field for key in RUNNING_KEYS}
    assert fields == expected


def test_prior_off_wepa_is_team_preseason_player_agg():
    feature = FEATURE_BY_KEY["prior_off_wepa"]
    assert feature.group == "team_preseason"
    assert feature.source_kind == "raw_player_agg"
    assert feature.team_scoped is True


def test_registry_version_changed_from_phase3_baseline():
    assert registry_version() != "69084ed55504"


def test_feature_ok_numeric_gte():
    features = {"weather_temperature": 55.0}
    filt = _filt("weather_temperature", "gte", 50.0)
    system = _system()
    assert feature_ok(features, filt, system)


def test_feature_ok_null_fails_closed():
    features = {}
    filt = _filt("weather_temperature", "gte", 50.0)
    system = _system()
    assert not feature_ok(features, filt, system)


def test_feature_ok_either_passes_when_one_side_matches():
    features = {"home_returning_ppa": 0.2, "away_returning_ppa": 0.7}
    filt = _filt("returning_ppa", "gte", 0.6, perspective="either")
    system = _system(bet_type="total")
    assert feature_ok(features, filt, system)


def test_feature_ok_bet_side_resolves_from_system_side():
    features = {"home_returning_ppa": 0.7, "away_returning_ppa": 0.2}
    filt = _filt("returning_ppa", "gte", 0.6, perspective="bet_side")
    system = _system(side="home")
    assert feature_ok(features, filt, system)
    system_away = _system(side="away")
    assert not feature_ok(features, filt, system_away)


class _Filter:
    def __init__(self, key: str, op: str, value: object, perspective: str = "single"):
        self.key = key
        self.op = op
        self.value = value
        self.perspective = perspective


class _System:
    def __init__(self, side: str = "home", bet_type: str = "spread"):
        self.side = side
        self.bet_type = bet_type


def _filt(key: str, op: str, value: object, perspective: str = "single") -> _Filter:
    return _Filter(key, op, value, perspective)


def _system(side: str = "home", bet_type: str = "spread") -> _System:
    return _System(side=side, bet_type=bet_type)
