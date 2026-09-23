"""Release C, C2: availability-classed features and the as-of screen. In-memory/synthetic."""
import pandas as pd
import pytest

from models.tuning.features import (
    BASELINES, CATALOG, FEATURE_SETS, CatalogEntry, load_feature_set, load_frame, screen_features,
    synthetic_frame,
)
from models.tuning.spec import DatasetSpec, FeatureSetSpec

CUT = pd.Timestamp("2024-09-07T16:00:00Z")


def _fs(*refs) -> FeatureSetSpec:
    return FeatureSetSpec(feature_set_id="t", version=1, features=[
        {"id": i, "version": v, "availability_class": c} for i, v, c in refs])


def _frame(**cols) -> pd.DataFrame:
    base = pd.DataFrame({"game_id": [1, 2, 3], "decision_ts": [CUT] * 3})
    for name, (values, as_of) in cols.items():
        base[name] = values
        base[f"{name}__as_of"] = as_of
    return base


TEST_CATALOG = {
    "x": CatalogEntry(1, "historical_replayable", "fixture"),
    "y": CatalogEntry(1, "historical_replayable", "fixture"),
    "final_score": CatalogEntry(1, "retrospective_descriptive", "known only after the game"),
    "injury_count": CatalogEntry(1, "prospective_only", "not reconstructible historically"),
    "open_total": CatalogEntry(1, "provider_opaque", "untimed vendor open"),
}


def test_a_leaking_row_drops_that_feature_only():
    frame = _frame(x=([1.0, 2.0, 3.0], [CUT] * 3),
                   y=([1.0, 2.0, 3.0], [CUT, CUT, CUT + pd.Timedelta(minutes=1)]))
    kept, dropped = screen_features(
        frame, _fs(("x", 1, "historical_replayable"), ("y", 1, "historical_replayable")),
        TEST_CATALOG)
    assert kept == ["x"]
    assert "after decision_ts" in dropped["y"]


def test_a_value_with_no_as_of_fails_closed_but_a_missing_value_does_not():
    frame = _frame(x=([1.0, None, 3.0], [CUT, pd.NaT, CUT]),
                   y=([1.0, 2.0, 3.0], [CUT, pd.NaT, CUT]))
    kept, dropped = screen_features(
        frame, _fs(("x", 1, "historical_replayable"), ("y", 1, "historical_replayable")),
        TEST_CATALOG)
    assert kept == ["x"] and "y" in dropped


@pytest.mark.parametrize("fid, cls, reason", [
    ("final_score", "retrospective_descriptive", "blocked from prediction"),
    ("injury_count", "prospective_only", "shadow/live only"),
    ("open_total", "provider_opaque", "benchmark-only"),
])
def test_ineligible_classes_are_refused_even_when_timestamps_pass(fid, cls, reason):
    frame = _frame(**{fid: ([1.0, 2.0, 3.0], [CUT] * 3)})
    kept, dropped = screen_features(frame, _fs((fid, 1, cls)), TEST_CATALOG)
    assert kept == [] and reason in dropped[fid]


def test_catalog_mismatch_and_unknown_ids_are_refused():
    frame = _frame(x=([1.0] * 3, [CUT] * 3))
    kept, dropped = screen_features(
        frame, _fs(("x", 2, "historical_replayable"), ("nope", 1, "historical_replayable")),
        TEST_CATALOG)
    assert kept == []
    assert "catalog" in dropped["x"] and "not in the catalog" in dropped["nope"]


def test_a_declared_class_cannot_launder_a_catalog_class():
    frame = _frame(open_total=([50.0] * 3, [CUT] * 3))
    kept, dropped = screen_features(frame, _fs(("open_total", 1, "historical_replayable")),
                                    TEST_CATALOG)
    assert kept == [] and "catalog" in dropped["open_total"]


def test_committed_feature_set_matches_the_catalog_and_is_all_replayable():
    fs = load_feature_set(FEATURE_SETS / "total_ratings_v1.json")
    assert fs.feature_set_id == "total_ratings_v1" and len(fs.features) == 9
    for f in fs.features:
        assert (CATALOG[f.id].version, CATALOG[f.id].availability_class) == \
            (f.version, f.availability_class) == (f.version, "historical_replayable")
    assert CATALOG["open_total"].availability_class == "provider_opaque"


def _synthetic(seed=7):
    ds = DatasetSpec(source="synthetic_v1", snapshot="fx", synthetic_seed=seed,
                     seasons=[2014, 2015, 2016])
    fs = load_feature_set(FEATURE_SETS / "total_ratings_v1.json")
    return ds, fs


def test_synthetic_frame_is_deterministic_with_the_documented_columns():
    ds, fs = _synthetic()
    a, b = synthetic_frame(ds, fs), synthetic_frame(ds, fs)
    pd.testing.assert_frame_equal(a, b)
    ids = [f.id for f in fs.features]
    expected = ["game_id", "season", "week", "kickoff", "decision_ts", "target",
                "home_reg", "away_reg", "ot_points", *ids,
                *[f"{i}__as_of" for i in ids], *BASELINES]
    assert list(a.columns) == expected
    assert a["game_id"].is_unique and (a["kickoff"] >= a["decision_ts"]).all()
    assert not synthetic_frame(_synthetic(seed=8)[0], fs).equals(a)


def test_load_frame_screens_and_reports_on_the_synthetic_source():
    ds, fs = _synthetic()
    frame, report = load_frame(ds, fs)
    assert report.kept == [f.id for f in fs.features] and report.dropped == {}
    assert report.sources == []
    assert set(report.kept) <= set(frame.columns)
