"""Release E: the live fit-at-cutoff path reproduces the snapshot-CSV path (plan §29.2).

Needs the real data root, so it is `slow` (opt in with `-m slow`).
"""
import numpy as np
import pytest

from models.tuning.features import (
    FEATURE_SETS, live_week_frame, load_feature_set, load_frame,
)
from models.tuning.spec import DatasetSpec

FEATURES = ("rv1_off_home", "rv1_def_home", "rv1_pace_home", "rv1_off_away", "rv1_def_away",
            "rv1_pace_away", "rv1_total", "min_prior_games", "neutral", "past_mean",
            "target", "home_reg", "away_reg", "ot_points")


@pytest.mark.slow
@pytest.mark.parametrize("season, week", [(2025, 6), (2024, 2), (2022, 11)])
def test_live_week_frame_matches_the_snapshot_csv_path(season, week):
    from cfb_paths import DATA_ROOT

    ds = DatasetSpec(source="cfb_release_b", snapshot="parity", seasons=list(range(2014, season + 1)))
    csv, _ = load_frame(ds, load_feature_set(FEATURES_SET_PATH()))
    csv = csv[(csv["season"] == season) & (csv["week"] == week)].set_index("game_id")
    live, meta = live_week_frame(season, week, DATA_ROOT)
    live = live.set_index("game_id")
    common = csv.index.intersection(live.index)
    assert len(common) == len(csv) and len(common) >= 40
    assert (csv["decision_ts"] == live.loc[csv.index, "decision_ts"]).all()
    for col in FEATURES:
        a, b = csv.loc[common, col].to_numpy(float), live.loc[common, col].to_numpy(float)
        # The CSV path reads ratings back from text, so allow the last bits of a float.
        assert np.allclose(a, b, rtol=0, atol=1e-9, equal_nan=True), col


def FEATURES_SET_PATH():
    return FEATURE_SETS / "total_ratings_v1.json"
