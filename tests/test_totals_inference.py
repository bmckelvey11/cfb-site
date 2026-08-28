"""Paired scores and cluster-robust means on toy numbers — no cfb-site data."""

import numpy as np
import pandas as pd
import pytest

from cfb_totals_model.inference import (
    cluster_ids,
    cluster_mean,
    hit_delta_and_clv,
    paired_score_delta,
)
from cfb_totals_model.model import CITABLE_MIN_EDGE


def test_citable_threshold_is_unselected_full_book():
    assert CITABLE_MIN_EDGE == 0


def test_cluster_mean_one_obs_per_cluster_matches_iid_se():
    y = np.array([1.0, 3.0, 5.0, 7.0])
    out = cluster_mean(y, groups=np.arange(4))
    se_iid = float(np.std(y, ddof=1) / np.sqrt(4))
    assert out["n"] == 4
    assert out["n_clusters"] == 4
    assert out["mean"] == pytest.approx(4.0)
    assert out["se"] == pytest.approx(se_iid)
    assert out["mde"] == pytest.approx(2.8 * se_iid)


def test_paired_mspe_delta_uses_the_same_games():
    pts = np.array([40.0, 50.0, 70.0])
    pred = np.array([42.0, 55.0, 60.0])
    line = np.array([41.0, 48.0, 65.0])
    groups = np.array(["a", "a", "b"])
    out = paired_score_delta(pts, pred, line, groups)
    d = (pts - pred) ** 2 - (pts - line) ** 2
    assert out["mspe"]["n"] == out["mae"]["n"] == 3
    assert out["mspe"]["mean"] == pytest.approx(float(d.mean()))
    assert out["mspe"]["mean"] == pytest.approx(
        float(np.mean((pts - pred) ** 2) - np.mean((pts - line) ** 2))
    )


def test_open_close_delta_drops_unpaired_pushes():
    """A close-only push must not enter an unpaired n_open vs n_close subtract."""
    pts = np.array([50.0, 30.0])
    pred = np.array([45.0, 45.0])
    ou_open = np.array([52.0, 50.0])
    close = np.array([50.0, 40.0])  # game 0 pushes the close
    groups = np.array(["w1", "w2"])
    out = hit_delta_and_clv(pts, pred, ou_open, close, groups)
    assert out["n_paired"] == 1
    assert out["hit_delta"]["n"] == 1


def test_clv_under_is_open_minus_close():
    pts = np.array([40.0])
    pred = np.array([48.0])       # edge = 52 - 48 > 0 → UNDER
    ou_open = np.array([52.0])
    close = np.array([50.0])
    out = hit_delta_and_clv(pts, pred, ou_open, close, groups=np.array(["w"]))
    assert out["clv"]["mean"] == pytest.approx(2.0)


def test_cluster_ids_are_season_week():
    frame = pd.DataFrame({"season": [2024, 2024], "week": [5, 6], "game_id": [1, 2]})
    assert list(cluster_ids(frame)) == ["2024-5", "2024-6"]
