from cfb_system_maker.features import (
    FEATURE_BY_KEY,
    FEATURE_REGISTRY,
    feature_ok,
    format_kickoff_hour,
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


def test_registry_descriptions_are_nonempty():
    for feature in FEATURE_REGISTRY:
        assert feature.description.strip(), f"{feature.key} missing description"


def test_registry_groups_are_valid():
    allowed = {
        "matchup",
        "ratings",
        "betting_lines",
        "weather",
        "season_to_date",
        "team_preseason",
        "metadata",
        "result_lookahead",
    }
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


def test_format_kickoff_hour_is_12_hour_clock():
    assert format_kickoff_hour(0) == "12:00 AM"
    assert format_kickoff_hour(12) == "12:00 PM"
    assert format_kickoff_hour(19) == "7:00 PM"
    assert format_kickoff_hour(19.0) == "7:00 PM"


def test_new_web_features_are_registered():
    kickoff = FEATURE_BY_KEY["kickoff_hour"]
    assert kickoff.group == "matchup"
    assert kickoff.source_kind == "raw_game"
    assert kickoff.control == "numeric"
    assert kickoff.team_scoped is False
    assert kickoff.label == "Kickoff Time (ET)"

    rank = FEATURE_BY_KEY["preseasonRank"]
    assert rank.group == "team_preseason"
    assert rank.source_kind == "raw_team_season"
    assert rank.source_file == "coach_seasons"
    assert rank.team_scoped is True

    overall = FEATURE_BY_KEY["core_overall"]
    assert overall.group == "result_lookahead"
    assert overall.source_file == "core_ratings"
    assert overall.field == "overall"

    ngt_keys = (
        "defense_explosiveness",
        "defense_passingDowns_ppa",
        "defense_ppa",
        "defense_rushingPlays_ppa",
        "defense_successRate",
    )
    for key in ngt_keys:
        feature = FEATURE_BY_KEY[key]
        assert feature.group == "result_lookahead"
        assert feature.source_kind == "raw_adv_ngt"
        assert feature.source_file == "advanced_game_stats_ngt"
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


def test_feature_ok_not_eq_matches_other_value():
    features = {"venue": "Michigan Stadium"}
    filt = _filt("venue", "not_eq", "Ohio Stadium")
    system = _system()
    assert feature_ok(features, filt, system)


def test_feature_ok_not_eq_rejects_the_excluded_value():
    features = {"venue": "Ohio Stadium"}
    filt = _filt("venue", "not_eq", "Ohio Stadium")
    system = _system()
    assert not feature_ok(features, filt, system)


def test_feature_ok_not_eq_null_fails_closed():
    # "not Ohio Stadium" means "has a venue, and it is not Ohio Stadium" --
    # never "venue unknown". Negation must not turn a missing feature into a
    # match.
    features = {}
    filt = _filt("venue", "not_eq", "Ohio Stadium")
    system = _system()
    assert not feature_ok(features, filt, system)


def test_feature_ok_not_in_excludes_listed_values():
    features = {"venue": "Ohio Stadium"}
    filt = _filt("venue", "not_in", ["Ohio Stadium", "Michigan Stadium"])
    system = _system()
    assert not feature_ok(features, filt, system)


def test_feature_ok_not_in_null_fails_closed():
    features = {}
    filt = _filt("venue", "not_in", ["Ohio Stadium"])
    system = _system()
    assert not feature_ok(features, filt, system)


def test_feature_ok_gt_is_strict():
    features = {"weather_temperature": 50.0}
    system = _system()
    assert not feature_ok(features, _filt("weather_temperature", "gt", 50.0), system)
    assert feature_ok(features, _filt("weather_temperature", "gte", 50.0), system)


def test_feature_ok_lt_is_strict():
    features = {"weather_temperature": 50.0}
    system = _system()
    assert not feature_ok(features, _filt("weather_temperature", "lt", 50.0), system)
    assert feature_ok(features, _filt("weather_temperature", "lte", 50.0), system)


def test_feature_ok_gt_lt_null_fails_closed():
    features = {}
    system = _system()
    assert not feature_ok(features, _filt("weather_temperature", "gt", 50.0), system)
    assert not feature_ok(features, _filt("weather_temperature", "lt", 50.0), system)


def test_feature_ok_either_negated_ignores_null_side():
    # The null side must not satisfy a negated op. Only the present side is
    # eligible, and here it is excluded, so the filter fails closed.
    features = {"home_returning_ppa": 0.7, "away_returning_ppa": None}
    filt = _filt("returning_ppa", "not_eq", 0.7, perspective="either")
    system = _system(bet_type="total")
    assert not feature_ok(features, filt, system)


def test_feature_ok_either_negated_matches_on_present_side():
    features = {"home_returning_ppa": 0.2, "away_returning_ppa": None}
    filt = _filt("returning_ppa", "not_eq", 0.7, perspective="either")
    system = _system(bet_type="total")
    assert feature_ok(features, filt, system)
