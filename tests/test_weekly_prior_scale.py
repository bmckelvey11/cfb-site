"""Carryover-scale tuning and the frozen-candidate guard. In-memory: no CFB_DATA_ROOT."""
from pathlib import Path

import pandas as pd
import pytest

from scripts.weekly_prior_scale import confirm, tune_scale
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
