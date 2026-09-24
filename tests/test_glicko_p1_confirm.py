"""glicko_p1_confirm: freeze never overwrites, confirm refuses without one, an interim look
carries no verdict. In-memory where possible; season_look itself is tested in
test_weekly_prior_scale.py and reused here unchanged."""
import json

import pandas as pd
import pytest

from scripts.glicko_p1_confirm import confirm, run_freeze
from scripts.weekly_prior_scale import season_look


def test_freeze_refuses_to_overwrite(tmp_path, monkeypatch):
    from scripts import glicko_p1_confirm as m

    monkeypatch.setattr(m, "FROZEN", tmp_path / "frozen.json")
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

    # confirm() itself is exercised end to end against real data in a manual run (needs
    # CFB_DATA_ROOT); this test only pins the no-verdict-on-interim contract of the season_look
    # result it depends on, which is what makes "nothing is decided from an interim look" true.
