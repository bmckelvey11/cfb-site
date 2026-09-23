"""Carryover-scale tuning and the frozen-candidate guard. In-memory: no CFB_DATA_ROOT."""
from pathlib import Path

import pandas as pd
import pytest

from scripts.weekly_prior_scale import confirm, season_look, tune_scale, write_freeze
from scripts.weekly_ratings import fit_ridge
from test_weekly_priors import COEFS
from test_weekly_total_tuning import _season

GRID = dict(grid_ppp=(10, 40, 160), grid_pace=(2, 8, 32))


def _setup():
    prev = _season(2023)
    cur = _season(2024)
    games = pd.concat([prev, cur], ignore_index=True)
    finals = {2023: fit_ridge(prev, 40, 8)}
    rp = {2024: pd.Series(0.6, index=sorted(set(cur["home"]) | set(cur["away"])))}
    return games, finals, rp


def test_scale_tuner_returns_the_minimum_over_scales_and_lambdas():
    games, finals, rp = _setup()
    out = tune_scale(games, [2024], finals, rp, COEFS, scales=(0.0, 0.5, 1.0), **GRID)
    best = min(out["by_scale"].items(), key=lambda kv: kv[1]["mae"])
    assert out["scale"] == float(best[0])
    assert (out["lambda_ppp"], out["lambda_pace"]) == (best[1]["lambda_ppp"], best[1]["lambda_pace"])
    assert set(out["by_scale"]) == {"0", "0.5", "1"}


def test_scale_tuner_reads_no_season_outside_its_tuning_seasons():
    games, finals, rp = _setup()
    later = _season(2025)
    later["total"] = later["total"] + 400.0
    alone = tune_scale(games, [2024], finals, rp, COEFS, scales=(0.0, 1.0), **GRID)
    mixed = tune_scale(pd.concat([games, later], ignore_index=True), [2024], finals, rp, COEFS,
                       scales=(0.0, 1.0), **GRID)
    assert alone == mixed


def test_confirm_refuses_without_a_frozen_candidate(tmp_path: Path):
    with pytest.raises(SystemExit, match="frozen"):
        confirm(2026, frozen_path=tmp_path / "missing.json")


def test_freeze_is_never_overwritten(tmp_path: Path):
    path = tmp_path / "freeze.json"
    write_freeze(path, {"scale": 1.0})
    with pytest.raises(SystemExit, match="not rewritten"):
        write_freeze(path, {"scale": 0.5})
    assert '"scale": 1.0' in path.read_text()


def _g(gid, start, completed, cls="fbs", season_type="regular"):
    return {"id": gid, "startDate": start, "completed": completed, "seasonType": season_type,
            "homeClassification": "fbs", "awayClassification": cls}


NOW = pd.Timestamp("2026-12-20T00:00:00Z")


def test_finished_season_with_a_cancelled_game_is_final():
    look, state = season_look([_g(1, "2026-11-28T20:00:00Z", True),
                               _g(2, "2026-11-29T20:00:00Z", False),       # cancelled
                               _g(3, "2026-12-30T20:00:00Z", False, cls="fcs"),
                               _g(4, "2027-01-01T20:00:00Z", False, season_type="postseason")],
                              NOW)
    assert look == "final"
    assert state == {"future_games": 0, "not_played": 1}


def test_season_with_a_game_still_scheduled_is_interim():
    look, state = season_look([_g(1, "2026-11-28T20:00:00Z", True),
                               _g(2, "2026-12-21T20:00:00Z", False)], NOW)
    assert look == "interim" and state["future_games"] == 1
    assert season_look([_g(1, None, False)], NOW)[0] == "interim"  # no kickoff: not placed
