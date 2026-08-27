from cfb_system_maker.team_abbreviations import AN_TO_CFBD, resolve_team


def test_resolve_known_team_returns_cfbd_name():
    assert resolve_team("NAVY") == "Navy"
    assert resolve_team("ND") == "Notre Dame"
    assert resolve_team("OHIO") == "Ohio"
    assert resolve_team("SDSU") == "San Diego State"


def test_resolve_unknown_team_returns_none():
    assert resolve_team("NOT_A_REAL_TEAM_XYZ") is None


def test_an_to_cfbd_has_no_duplicate_keys_with_different_casing():
    lowered = [key.lower() for key in AN_TO_CFBD]
    assert len(lowered) == len(set(lowered))
