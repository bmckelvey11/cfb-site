"""Amendment A6: the decontamination screen must not see the seasons it screens for.

A3's screen computed rho_i over ALL of 2001-2025 before fitting anything, so the retained
panel's identity was chosen with knowledge of the evaluation seasons. The walk-forward fix
is only worth anything if the drop list for season s provably never touches rows from s or
later -- that is the one thing this file checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"
))

elm = pytest.importorskip("eval_line_movement")


def _synthetic(seasons=range(2001, 2008), n_per_season=500, seed=0):
    """A small panel shaped like the real one: lineopen/line plus model columns in PT's
    spread sign, with one model that mechanically reprints the close (high rho) and several
    that don't."""
    rng = np.random.default_rng(seed)
    frames = []
    for s in seasons:
        n = n_per_season
        openv = rng.normal(0, 10, n)
        move = rng.normal(0, 2, n)
        closev = openv + move
        cols = {
            "season": s,
            "lineopen": openv,
            "line": closev,
            # mechanical copy of the close -> rho with move near 1
            "market_proxy": closev + rng.normal(0, 0.2, n),
            # a real forecaster: close to the opener, mostly independent of the move
            "independent": openv + rng.normal(0, 3, n),
        }
        for i in range(8):
            cols[f"filler{i}"] = openv + rng.normal(0, 3, n)
        frames.append(pd.DataFrame(cols))
    return pd.concat(frames, ignore_index=True)


MODELS = ["market_proxy", "independent"] + [f"filler{i}" for i in range(8)]


def test_walk_forward_drop_list_matches_truncated_full_sample_screen():
    """The whole point of the amendment: the season-s drop list must be identical whether
    you ask decontaminate() to look 'before season s' on the full frame, or hand it a frame
    that has had season s and later deleted outright."""
    df = _synthetic()
    s = 2006

    kept_wf, dropped_wf, rho_wf = elm.decontaminate(df, MODELS, before_season=s)

    truncated = df[df["season"] < s].reset_index(drop=True)
    kept_trunc, dropped_trunc, rho_trunc = elm.decontaminate(truncated, MODELS, before_season=None)

    assert dropped_wf == dropped_trunc
    assert kept_wf == kept_trunc
    assert rho_wf == pytest.approx(rho_trunc)


def test_walk_forward_screen_is_unaffected_by_evaluation_season_rows():
    """Scrambling every row from season s onward must not move the season-s drop list --
    if it did, the screen would be reading the rows it is supposed to be blind to."""
    df = _synthetic()
    s = 2006

    _, dropped_before, _ = elm.decontaminate(df, MODELS, before_season=s)

    corrupted = df.copy()
    mask = (corrupted["season"] >= s).to_numpy()
    rng = np.random.default_rng(99)
    for col in MODELS + ["lineopen", "line"]:
        corrupted.loc[mask, col] = rng.normal(0, 500, int(mask.sum()))

    _, dropped_after, _ = elm.decontaminate(corrupted, MODELS, before_season=s)
    assert dropped_before == dropped_after


def test_full_sample_screen_unchanged_when_before_season_is_none():
    """decontaminate(df, models, before_season=None) must reproduce the ORIGINAL --decontaminate
    behaviour: rho computed on every row handed to it, no season restriction."""
    df = _synthetic()
    kept, dropped, rho = elm.decontaminate(df, MODELS, before_season=None)

    open_m, close_m = df["lineopen"].to_numpy(float), df["line"].to_numpy(float)
    move = close_m - open_m
    expect_rho = {}
    for m in MODELS:
        f = df[m].to_numpy(float)
        ok = np.isfinite(f) & np.isfinite(move)
        if ok.sum() >= 400 and (f[ok] - open_m[ok]).std() > 0:
            expect_rho[m] = float(np.corrcoef(f[ok] - open_m[ok], move[ok])[0, 1])
    assert set(rho) == set(expect_rho)
    for m in rho:
        assert rho[m] == pytest.approx(expect_rho[m])

    cut = float(np.quantile(list(expect_rho.values()), 0.90))
    expect_dropped = sorted((m for m, r in expect_rho.items() if r >= cut),
                            key=expect_rho.get, reverse=True)
    assert dropped == expect_dropped
    assert kept == [m for m in MODELS if m not in set(expect_dropped)]


def test_walk_forward_drop_list_never_includes_a_model_with_no_prior_history():
    """A model that only starts publishing in the evaluation seasons must never be
    droppable before it has any history to compute rho on."""
    df = _synthetic()
    s = 2003
    # 'independent' never appears before season 2003
    df.loc[df["season"] < s, "independent"] = np.nan
    _, dropped, rho = elm.decontaminate(df, MODELS, before_season=s)
    assert "independent" not in rho
    assert "independent" not in dropped
