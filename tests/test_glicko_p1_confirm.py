"""glicko_p1_confirm: freeze never overwrites, confirm refuses without one, the verdict is
None unless the look is final and the forecast fingerprint still matches. In-memory where
possible; season_look itself is tested in test_weekly_prior_scale.py and reused here
unchanged."""
import pandas as pd
import pytest

from scripts.glicko_p1_confirm import _verdict, confirm, run_freeze
from scripts.weekly_prior_scale import season_look


def test_freeze_refuses_to_overwrite(tmp_path, monkeypatch):
    from scripts import glicko_p1_confirm as m

    monkeypatch.setattr(m, "FROZEN", tmp_path / "frozen.json")
    monkeypatch.setattr(m, "p1_primary_fingerprint", lambda root: ("deadbeef", 3718))
    run_freeze()
    with pytest.raises(SystemExit, match="already holds"):
        run_freeze()


def test_confirm_refuses_without_a_frozen_file(tmp_path):
    with pytest.raises(SystemExit, match="run `freeze`"):
        confirm(2026, tmp_path / "does_not_exist.json")


def test_interim_look_carries_no_verdict_key():
    # One completed game, one still-scheduled game: season_look must read "interim".
    schedule = [
        {"seasonType": "regular", "homeClassification": "fbs", "awayClassification": "fbs",
         "startDate": "2026-08-28T00:00:00Z", "completed": True},
        {"seasonType": "regular", "homeClassification": "fbs", "awayClassification": "fbs",
         "startDate": "2030-01-01T00:00:00Z", "completed": False},
    ]
    look, state = season_look(schedule, pd.Timestamp("2026-09-24", tz="UTC"))
    assert look == "interim" and state["future_games"] == 1


ENC_POSITIVE = {"beta": 0.19, "ci95": [0.05, 0.33]}
ENC_CROSSES_ZERO = {"beta": 0.06, "ci95": [-0.08, 0.20]}


def test_verdict_is_none_unless_look_is_final():
    assert _verdict("interim", ENC_POSITIVE, fingerprint_ok=True) is None
    assert _verdict("interim", None, fingerprint_ok=True) is None


def test_verdict_is_none_when_the_fingerprint_drifted():
    # A final look with a clearly positive slope must still refuse a verdict if P1's own
    # 2021-2025 forecasts no longer match what was frozen -- the whole point of sealing it.
    assert _verdict("final", ENC_POSITIVE, fingerprint_ok=False) is None


def test_verdict_confirmed_only_when_ci_lower_bound_is_positive():
    assert _verdict("final", ENC_POSITIVE, fingerprint_ok=True) == "confirmed"
    assert _verdict("final", ENC_CROSSES_ZERO, fingerprint_ok=True) == "not confirmed"


# confirm() itself is exercised end to end against real data in a manual run (needs
# CFB_DATA_ROOT); these tests pin the pure decision logic it depends on, which is what makes
# "nothing is decided from an interim or drifted look" true regardless of the data.
