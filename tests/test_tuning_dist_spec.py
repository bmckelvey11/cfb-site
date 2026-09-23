"""Release D, D0: distribution-run, policy, and execution specs. In-memory."""
import pytest
from pydantic import ValidationError

from models.tuning.dist_spec import (
    CalibrationGate, DecisionPolicySpec, DistRunSpec, DistributionSpec, ExecutionSpec,
)


def _dist(**over) -> dict:
    d = {"spec_id": "d", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
         "base_run_id": "run-de1927346ab0", "selection_seasons": [2018, 2019]}
    d.update(over)
    return d


def test_defaults_are_the_declared_design():
    s = DistRunSpec.model_validate(_dist())
    assert s.distribution.candidates == ("empirical_total", "joint_bootstrap", "normal_const")
    assert s.distribution.baseline == "normal_const" and s.distribution.window_seasons == 3
    assert s.distribution.interval_levels == (0.5, 0.8, 0.9)
    g = s.gate
    assert (g.pooled_coverage_tol, g.season_coverage_level, g.season_coverage_tol,
            g.pit_decile_tol) == (0.03, 0.8, 0.06, 0.02)
    assert s.open_label_pushes == "exclude"


def test_hash_ignores_provenance_and_set_order_but_not_results_inputs():
    a = DistRunSpec.model_validate(_dist())
    b = DistRunSpec.model_validate(_dist(selection_seasons=[2019, 2018], notes="n",
                                         created_at="2027-01-01T00:00:00Z"))
    assert a.config_hash == b.config_hash and a.run_id() == f"dist-{a.config_hash[:12]}"
    c = DistRunSpec.model_validate(_dist(distribution={"window_seasons": 4}))
    assert c.config_hash != a.config_hash


@pytest.mark.parametrize("over, message", [
    ({"surprise": 1}, "Extra inputs"),
    ({"gate": {"surprise": 1}}, "Extra inputs"),
    ({"base_run_id": "dist-abc"}, "base_run_id"),
    ({"distribution": {"candidates": ["empirical_total"]}}, "baseline"),
    ({"selection_seasons": []}, "selection_seasons"),
])
def test_invalid_distribution_specs_are_rejected(over, message):
    with pytest.raises(ValidationError, match=message):
        DistRunSpec.model_validate(_dist(**over))


@pytest.mark.parametrize("policy, ok", [
    ({"policy_id": "p", "version": 1, "kind": "no_bet"}, True),
    ({"policy_id": "p", "version": 1, "kind": "min_ev", "threshold": 0.03}, True),
    ({"policy_id": "p", "version": 1, "kind": "point_edge", "threshold": 3.0,
      "min_prior_games": 3}, True),
    ({"policy_id": "p", "version": 1, "kind": "no_bet", "threshold": 0.1}, False),
    ({"policy_id": "p", "version": 1, "kind": "min_ev", "threshold": -0.1}, False),
])
def test_policy_spec(policy, ok):
    if ok:
        DecisionPolicySpec.model_validate(policy)
    else:
        with pytest.raises(ValidationError):
            DecisionPolicySpec.model_validate(policy)


@pytest.mark.parametrize("execution, ok", [
    ({}, True),
    ({"quote_rule": "named", "book": "DraftKings"}, True),
    ({"quote_rule": "named"}, False),
    ({"quote_rule": "best", "book": "DraftKings"}, False),
    ({"missed_fill_rate": 1.0}, False),
    ({"stake": 2.0}, False),
])
def test_execution_spec(execution, ok):
    if ok:
        ExecutionSpec.model_validate(execution)
    else:
        with pytest.raises(ValidationError):
            ExecutionSpec.model_validate(execution)


def test_distribution_and_gate_reject_unknown_fields_standalone():
    with pytest.raises(ValidationError):
        DistributionSpec.model_validate({"bins": 10})
    with pytest.raises(ValidationError):
        CalibrationGate.model_validate({"coverage": 0.1})
