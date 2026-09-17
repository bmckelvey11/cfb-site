from scripts.build_ppa_opponent_adjusted_ratings import VERSION, shrink_toward_prior


def test_version_is_stamped():
    assert VERSION == "1.0"


def test_low_confidence_current_leans_toward_prior():
    # Early season: current estimate has a wide SE (few games played).
    current = {"Team A": {"estimate": 1.0, "se": 1.0}}
    prior = {"Team A": {"estimate": 0.0, "se": 0.1}}
    blended = shrink_toward_prior(current, prior)
    assert blended["Team A"]["source"] == "blended"
    # Prior is 100x more precise, so the blend should sit much closer to 0.0 than 1.0.
    assert blended["Team A"]["estimate"] < 0.2


def test_high_confidence_current_dominates():
    # Late season: current estimate is as precise as the prior.
    current = {"Team A": {"estimate": 1.0, "se": 0.1}}
    prior = {"Team A": {"estimate": 0.0, "se": 0.1}}
    blended = shrink_toward_prior(current, prior)
    # Equal precision => simple average.
    assert blended["Team A"]["estimate"] == 0.5


def test_current_only_team_passes_through():
    current = {"New Team": {"estimate": 0.4, "se": 0.2}}
    blended = shrink_toward_prior(current, {})
    assert blended["New Team"] == {"estimate": 0.4, "se": 0.2, "source": "current_only"}


def test_prior_only_team_passes_through():
    prior = {"Idle Team": {"estimate": -0.3, "se": 0.15}}
    blended = shrink_toward_prior({}, prior)
    assert blended["Idle Team"] == {"estimate": -0.3, "se": 0.15, "source": "prior_only"}


def test_missing_from_both_is_dropped():
    blended = shrink_toward_prior({}, {})
    assert blended == {}
