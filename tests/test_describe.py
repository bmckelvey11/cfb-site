import inspect

import cfb_system_maker.describe as describe_module
from cfb_system_maker.describe import describe
from cfb_system_maker.features import FEATURE_BY_KEY
from cfb_system_maker.models import FeatureFilter, SystemFilter


def test_describe_empty_system_returns_empty_list():
    assert describe(SystemFilter()) == []


def test_describe_favorite_and_underdog_sentences():
    favorite_result = describe(SystemFilter(bet_type="spread", favorite=True))
    assert {"text": "the team is a favorite", "key": "favorite"} in favorite_result

    underdog_result = describe(SystemFilter(bet_type="spread", underdog=True))
    assert {"text": "the team is an underdog", "key": "underdog"} in underdog_result


def test_describe_home_and_away_sentences():
    home_result = describe(SystemFilter(home=True))
    assert {"text": "home games only", "key": "home"} in home_result

    away_result = describe(SystemFilter(away=True))
    assert {"text": "away games only", "key": "away"} in away_result


def test_describe_spread_range_between_at_least_at_most_and_exact():
    between = describe(SystemFilter(bet_type="spread", min_spread=-14, max_spread=-3))
    assert {"text": "the spread is between -14 and -3", "key": "spread_range"} in between

    at_least = describe(SystemFilter(bet_type="spread", min_spread=-14))
    assert {"text": "the spread is at least -14", "key": "spread_range"} in at_least

    at_most = describe(SystemFilter(bet_type="spread", max_spread=-3))
    assert {"text": "the spread is at most -3", "key": "spread_range"} in at_most

    exact = describe(SystemFilter(bet_type="spread", min_spread=-7, max_spread=-7))
    assert {"text": "the spread is exactly -7", "key": "spread_range"} in exact


def test_describe_spread_fields_ignored_for_total_bet_type():
    system = SystemFilter(bet_type="total", favorite=True, min_spread=-14, max_spread=-3)
    result = describe(system)
    keys = [row["key"] for row in result]
    assert "favorite" not in keys
    assert "spread_range" not in keys


def test_describe_total_range_applies_regardless_of_bet_type():
    spread_bet = describe(SystemFilter(bet_type="spread", min_total=45, max_total=55))
    assert {"text": "the total is between 45 and 55", "key": "total_range"} in spread_bet

    total_bet = describe(SystemFilter(bet_type="total", min_total=45, max_total=55))
    assert {"text": "the total is between 45 and 55", "key": "total_range"} in total_bet


def test_describe_seasons_weeks_teams_conferences_providers_join_sorted_and_comma_separated():
    seasons_result = describe(SystemFilter(seasons={2023, 2021, 2022}))
    assert {"text": "the season is 2021, 2022, 2023", "key": "seasons"} in seasons_result

    weeks_result = describe(SystemFilter(weeks={3, 1, 2}))
    assert {"text": "the week is 1, 2, 3", "key": "weeks"} in weeks_result

    teams_result = describe(SystemFilter(teams={"Texas", "Michigan"}))
    assert {"text": "the team is Michigan, Texas", "key": "teams"} in teams_result

    conferences_result = describe(SystemFilter(conferences={"SEC", "Big Ten"}))
    assert {"text": "the conference is Big Ten, SEC", "key": "conferences"} in conferences_result

    providers_result = describe(SystemFilter(providers={"consensus", "Bovada"}))
    assert {"text": "the provider is Bovada, consensus", "key": "providers"} in providers_result


def test_describe_feature_filter_bool_eq_yes_no():
    label = FEATURE_BY_KEY["neutralSite"].label

    yes_system = SystemFilter(feature_filters=(FeatureFilter(key="neutralSite", op="eq", value=True),))
    yes_result = describe(yes_system)
    assert {"text": f"{label} is Yes", "key": "ff:neutralSite"} in yes_result

    no_system = SystemFilter(feature_filters=(FeatureFilter(key="neutralSite", op="eq", value=False),))
    no_result = describe(no_system)
    assert {"text": f"{label} is No", "key": "ff:neutralSite"} in no_result


def test_describe_feature_filter_categorical_eq():
    label = FEATURE_BY_KEY["venue"].label
    system = SystemFilter(feature_filters=(FeatureFilter(key="venue", op="eq", value="Michigan Stadium"),))
    result = describe(system)
    assert {"text": f"{label} is Michigan Stadium", "key": "ff:venue"} in result


def test_describe_feature_filter_categorical_in_list():
    label = FEATURE_BY_KEY["venue"].label
    system = SystemFilter(
        feature_filters=(FeatureFilter(key="venue", op="in", value=["Michigan Stadium", "The Horseshoe"]),)
    )
    result = describe(system)
    assert {"text": f"{label} is one of Michigan Stadium, The Horseshoe", "key": "ff:venue"} in result


def test_describe_feature_filter_numeric_gte_and_lte():
    label = FEATURE_BY_KEY["weather_temperature"].label

    gte_system = SystemFilter(feature_filters=(FeatureFilter(key="weather_temperature", op="gte", value=50.0),))
    gte_result = describe(gte_system)
    assert {"text": f"{label} is at least 50", "key": "ff:weather_temperature"} in gte_result

    lte_system = SystemFilter(feature_filters=(FeatureFilter(key="weather_temperature", op="lte", value=32.5),))
    lte_result = describe(lte_system)
    assert {"text": f"{label} is at most 32.5", "key": "ff:weather_temperature"} in lte_result


def test_describe_feature_filter_numeric_gte_lte_coalesces_to_between():
    label = FEATURE_BY_KEY["weather_temperature"].label
    system = SystemFilter(
        feature_filters=(
            FeatureFilter(key="weather_temperature", op="gte", value=40.0),
            FeatureFilter(key="weather_temperature", op="lte", value=70.0),
        )
    )
    result = describe(system)
    between = [row for row in result if row["key"] == "ff:weather_temperature"]
    assert between == [{"text": f"{label} is between 40 and 70", "key": "ff:weather_temperature"}]


def test_describe_feature_filter_numeric_exact_and_perspective_coalesce():
    label = FEATURE_BY_KEY["returning_ppa"].label
    exact = describe(
        SystemFilter(
            feature_filters=(
                FeatureFilter(key="returning_ppa", op="gte", value=0.5, perspective="bet_side"),
                FeatureFilter(key="returning_ppa", op="lte", value=0.5, perspective="bet_side"),
            )
        )
    )
    assert {"text": f"Bet-side {label} is exactly 0.5", "key": "ff:returning_ppa"} in exact
    keys = [row["key"] for row in exact if row["key"] == "ff:returning_ppa"]
    assert keys == ["ff:returning_ppa"]


def test_describe_unknown_feature_key_renders_warning_sentence():
    system = SystemFilter(feature_filters=(FeatureFilter(key="does_not_exist", op="eq", value=True),))
    result = describe(system)
    assert result == [{"text": 'Unknown filter "does_not_exist" is unavailable', "key": "ff:does_not_exist"}]


def test_describe_feature_filter_perspective_prefixes_team_scoped_label():
    label = FEATURE_BY_KEY["returning_ppa"].label
    cases = [
        ("home", "Home"),
        ("away", "Away"),
        ("bet_side", "Bet-side"),
        ("opponent", "Opponent"),
        ("either", "Either team's"),
    ]
    for perspective, expected_prefix in cases:
        system = SystemFilter(
            feature_filters=(FeatureFilter(key="returning_ppa", op="gte", value=0.5, perspective=perspective),)
        )
        result = describe(system)
        expected_text = f"{expected_prefix} {label} is at least 0.5"
        assert {"text": expected_text, "key": "ff:returning_ppa"} in result


def test_describe_feature_filter_perspective_single_default_has_no_prefix_even_when_team_scoped():
    label = FEATURE_BY_KEY["returning_ppa"].label
    system = SystemFilter(feature_filters=(FeatureFilter(key="returning_ppa", op="gte", value=0.5),))
    result = describe(system)
    assert {"text": f"{label} is at least 0.5", "key": "ff:returning_ppa"} in result


def test_describe_feature_filter_perspective_ignored_for_non_team_scoped():
    label = FEATURE_BY_KEY["venue"].label
    system = SystemFilter(
        feature_filters=(FeatureFilter(key="venue", op="eq", value="Michigan Stadium", perspective="home"),)
    )
    result = describe(system)
    assert {"text": f"{label} is Michigan Stadium", "key": "ff:venue"} in result


def test_describe_output_order_is_fixed_and_deterministic():
    system = SystemFilter(bet_type="spread", favorite=True, min_total=45, seasons={2023})
    result = describe(system)
    assert [row["key"] for row in result] == ["favorite", "total_range", "seasons"]


def test_describe_is_pure_no_side_effects_call_twice_returns_equal_lists():
    system = SystemFilter(
        bet_type="spread",
        favorite=True,
        home=True,
        min_spread=-14,
        max_spread=-3,
        seasons={2023, 2022},
        feature_filters=(FeatureFilter(key="neutralSite", op="eq", value=True),),
    )
    first = describe(system)
    second = describe(system)
    assert first == second


def test_describe_module_has_no_flask_dependency():
    source = inspect.getsource(describe_module)
    assert "flask" not in source.lower()
    assert "request" not in source.lower()


def test_describe_non_finite_numbers_do_not_crash():
    spread_system = SystemFilter(bet_type="spread", min_spread=float("nan"))
    result = describe(spread_system)
    assert all(isinstance(row["text"], str) for row in result)

    feature_system = SystemFilter(
        feature_filters=(FeatureFilter(key="weather_temperature", op="gte", value=float("inf")),)
    )
    feature_result = describe(feature_system)
    assert all(isinstance(row["text"], str) for row in feature_result)
