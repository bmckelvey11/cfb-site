"""Glicko version registry: names resolve, CURRENT is P1.1, P1/P1.1 match FROZEN_P1, frozen
bundles read their picks from the frozen files, and the table's default output is unchanged.
In-memory except where marked; the fingerprint check needs CFB_DATA_ROOT (slow)."""
import json
import os

import pandas as pd
import pytest

import scripts.glicko_versions as gv
from scripts.glicko_ratings import FBS, FROZEN_P1, SIGMA_PRED_P1, GlickoMargin, events, run
from scripts.glicko_ratings_table import output_name


def test_current_is_p1_1_and_resolves():
    assert gv.CURRENT == "P1.1"
    v = gv.get()
    assert v.name == "P1.1" and v.status == "current" and v.sigma_pred == SIGMA_PRED_P1
    assert gv.get("P1").params == FROZEN_P1 == v.params


def test_unknown_version_is_an_error():
    with pytest.raises(KeyError, match="unknown Glicko version"):
        gv.get("P9")


def test_every_entry_has_status_date_and_doc():
    allowed = {"adopted", "current", "candidate", "declared", "rejected", "retired"}
    for v in gv.REGISTRY.values():
        assert v.status in allowed and len(v.date) == 10 and v.doc


def test_p3_versions_read_their_frozen_picks():
    if not gv.P3_FROZEN.exists():
        pytest.skip("P3 not frozen in this checkout")
    frozen = json.loads(gv.P3_FROZEN.read_text())["bundles"]
    for b in "ABC":
        v = gv.get(f"P3-{b}")
        assert v.status == "candidate" and v.params == frozen[b]["pick"]
        assert v.sigma_pred == frozen[b]["sigma_pred"]


def test_p1_versions_build_p1():
    g = pd.DataFrame([{"game_id": 1, "season": 2013, "season_type": "regular", "week": 1,
                       "kickoff": pd.Timestamp("2013-09-01", tz="UTC"), "home": "A", "away": "B",
                       "home_div": FBS, "away_div": FBS, "home_conf": "X", "away_conf": "X",
                       "neutral": False, "margin": 7}])
    for name in ("P1", "P1.1"):
        model, runner = gv.build(name, m0=-27.0)
        pd.testing.assert_frame_equal(runner(model, g, events(g)),
                                      run(GlickoMargin(**FROZEN_P1, m0=-27.0), g, events(g)))


def test_table_output_name_and_stamp_keep_todays_default():
    assert output_name(2026, "P1") == "glicko_ratings_2026.csv"
    assert output_name(2026, "P1.1") == "glicko_ratings_2026.csv"
    assert output_name(2026, "P3-A") == "glicko_ratings_2026_P3-A.csv"
    assert gv.get("P1").stamp == "P1/1.0"


@pytest.mark.slow
def test_frozen_versions_reproduce_their_fingerprints():
    if not os.environ.get("CFB_DATA_ROOT"):
        pytest.skip("needs CFB_DATA_ROOT")
    from cfb_paths import DATA_ROOT
    res = gv.check(DATA_ROOT)
    assert res and all(res.values()), res
