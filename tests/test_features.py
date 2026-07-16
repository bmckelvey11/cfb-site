from cfb_system_maker.features import FEATURE_BY_KEY, FEATURE_REGISTRY, feature_ok, registry_keys_unique


def test_registry_keys_are_unique():
    assert registry_keys_unique()
    assert len(FEATURE_REGISTRY) >= 20


def test_registry_groups_are_valid():
    allowed = {"pregame", "team_preseason", "metadata", "result_lookahead"}
    for feature in FEATURE_REGISTRY:
        assert feature.group in allowed
        assert feature.key in FEATURE_BY_KEY


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
