"""The lab monitor's data layer: read-only ledger access, the alerts that need the user,
and a hypothesis ledger whose records exist."""
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from models.tuning.ledger import Ledger, read_only
from models.tuning.ui.data import hypotheses, shadow_view

REPO = Path(__file__).resolve().parents[1]
CUT4, CUT5 = pd.Timestamp("2026-09-24T23:30Z"), pd.Timestamp("2026-10-02T00:00Z")


def _shadow(tmp_path) -> Path:
    raw, sd = tmp_path / "raw", tmp_path / "shadow-x"
    raw.mkdir()
    games = [{"week": w, "seasonType": "regular", "homeClassification": "fbs",
              "awayClassification": "fbs", "startDate": c.isoformat()} for w, c in ((4, CUT4), (5, CUT5))]
    (raw / "games_2026.json").write_text(json.dumps(games), encoding="utf-8")
    led = Ledger(sd / "ledger.sqlite3")
    led.append("arm", {"period_weeks": [5], "rehearsal_weeks": [4]})
    led.append("snapshot", {"week": 4, "cutoff": CUT4.isoformat(), "games": [1, 2],
                            "generated_at": (CUT4 - pd.Timedelta(days=1)).isoformat()})
    (sd / "status.md").write_text("ok", encoding="utf-8")
    return sd


def _at(sd: Path, now: pd.Timestamp, tick: pd.Timestamp) -> dict:
    os.utime(sd / "status.md", (tick.timestamp(), tick.timestamp()))
    return shadow_view(sd, sd.parent / "raw", now)


def test_read_only_matches_the_ledger_and_never_creates_a_file(tmp_path):
    sd = _shadow(tmp_path)
    records, (ok, _) = read_only(sd / "ledger.sqlite3")
    assert ok and records == Ledger(sd / "ledger.sqlite3").records()
    with pytest.raises(Exception):
        read_only(tmp_path / "missing.sqlite3")
    assert not (tmp_path / "missing.sqlite3").exists()


def test_alerts_warn_before_a_period_cutoff_and_fail_after_it(tmp_path):
    sd = _shadow(tmp_path)
    early = CUT5 - pd.Timedelta(days=10)
    assert [lvl for lvl, _ in _at(sd, early, early)["alerts"]] == ["info"]  # the next deadline
    before = CUT5 - pd.Timedelta(days=3)
    v = _at(sd, before, before - pd.Timedelta(hours=2))
    assert [lvl for lvl, _ in v["alerts"]] == ["warning"] and "Week 5 needs a snapshot" in v["alerts"][0][1]
    assert v["weeks"].set_index("week").at[4, "games"] == 2
    after = CUT5 + pd.Timedelta(hours=1)
    v = _at(sd, after, after - pd.Timedelta(hours=40))           # and the tick stopped running
    levels = [lvl for lvl, _ in v["alerts"]]
    assert levels == ["error", "error"]
    assert "No tick for 40 h" in v["alerts"][0][1] and "Week 5 MISSED" in v["alerts"][1][1]


def test_over_under_matches_the_pricing_engine():
    import numpy as np

    from models.tuning.market import outcome_probs
    from models.tuning.ui.data import over_under

    pmf = np.random.default_rng(3).dirichlet(np.ones(151))
    for line in (-1, 0, 44, 44.5, 150, 151.5):
        p = over_under(pmf, line)
        assert (p["over"], p["push"], p["under"]) == pytest.approx(outcome_probs(pmf, "over", line))


def test_shadow_predictions_join_both_aliases_and_refuse_a_changed_table(tmp_path):
    import hashlib

    import numpy as np

    from models.tuning.ui.data import shadow_predictions

    sd = _shadow(tmp_path)
    games = json.loads((tmp_path / "raw" / "games_2026.json").read_text(encoding="utf-8"))
    games += [{"id": 7, "homeTeam": "Ohio", "awayTeam": "Akron", "startDate": CUT5.isoformat()}]
    (tmp_path / "raw" / "games_2026.json").write_text(json.dumps(games), encoding="utf-8")
    (sd / "snapshots").mkdir()
    pmf = np.zeros((1, 151))
    pmf[0, 50] = 1.0
    np.save(sd / "snapshots" / "w5.npy", pmf)
    blob = (sd / "snapshots" / "w5.npy").read_bytes()
    led = Ledger(sd / "ledger.sqlite3")
    led.append("snapshot", {"week": 5, "snapshot_id": "5:x", "cutoff": CUT5.isoformat(), "games": [7],
                            "generated_at": CUT5.isoformat(), "pmf_file": "snapshots/w5.npy",
                            "pmf_sha256": hashlib.sha256(blob).hexdigest()})
    common = {"snapshot_id": "5:x", "week": 5, "game_id": 7}
    led.append_many([("prediction", {**common, "alias": "champion", "point": 52.0}),
                     ("prediction", {**common, "alias": "challenger", "point": 50.5, "pmf_row": 0,
                                     "q10": 50, "q50": 50, "q90": 50, "p_home_win": 0.6})])
    df, table, snap = shadow_predictions(sd, tmp_path / "raw", 5)
    row = df.iloc[0]
    assert (row["game"], row["champion"], row["challenger"]) == ("Akron @ Ohio", 52.0, 50.5)
    assert table[int(row["pmf_row"])][50] == 1.0
    np.save(sd / "snapshots" / "w5.npy", pmf * 0.5)
    with pytest.raises(ValueError, match="checksum"):
        shadow_predictions(sd, tmp_path / "raw", 5)


def test_lineage_flags_a_revised_source_and_a_missing_one(tmp_path):
    import hashlib

    from models.tuning.ui.data import lineage

    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    for name in ("a.json", "b.json"):
        (data / "raw" / name).write_text("v1", encoding="utf-8")
    run = tmp_path / "lab" / "runs" / "run-x"
    run.mkdir(parents=True)
    sha = hashlib.sha256(b"v1").hexdigest()
    (run / "manifest.json").write_text(json.dumps({"sources": [
        {"path": f"raw/{n}", "sha256": sha} for n in ("a.json", "b.json", "c.json")]}), encoding="utf-8")
    (data / "raw" / "b.json").write_text("v2", encoding="utf-8")          # revised after the run
    status = lineage(tmp_path / "lab", data).set_index("path")["status"].to_dict()
    assert status == {"raw/a.json": "same", "raw/b.json": "changed", "raw/c.json": "missing"}


@pytest.mark.slow
def test_replay_week_reproduces_release_b_forecasts_from_the_snapshot():
    from cfb_paths import DATA_ROOT, PROCESSED

    from models.tuning.ui.data import replay_week
    from scripts.weekly_ratings_eval import load, run_season

    snaps = pd.read_csv(PROCESSED / "ratings" / "weekly_ratings_snapshots.csv")
    games, _ = load(DATA_ROOT, [2021], [])
    scored, _ = run_season(games, 2021, 40, 8, {})
    shown, _, _ = replay_week(snaps, DATA_ROOT / "raw", 2021, 8)
    both = shown.merge(scored[scored["week"] == 8][["game_id", "ridge"]], on="game_id")
    assert len(both) > 40
    assert both["forecast"].to_numpy() == pytest.approx(both["ridge"].to_numpy(), abs=1e-9)


def test_compare_runs_blocks_incompatible_runs_and_pairs_compatible_ones(tmp_path):
    from models.tuning.ui.data import compare_runs, context

    spec = {"dataset": {"source": "cfb_release_b", "snapshot": "s", "target": "total"},
            "folds": {"outer_test_seasons": [2021, 2022]}}
    games = pd.DataFrame({"season": [2021] * 2 + [2022] * 2, "week": [2, 3, 2, 3],
                          "game_id": [1, 2, 3, 4], "target": [50.0, 60.0, 40.0, 70.0]})
    runs = {}
    for name, y in (("run-a", [51, 58, 44, 70]), ("run-b", [55, 60, 40, 60])):
        d = tmp_path / "runs" / name
        d.mkdir(parents=True)
        (d / "run_spec.json").write_text(json.dumps(spec), encoding="utf-8")
        games.assign(y_hat=y).to_csv(d / "predictions.csv", index=False)
        runs[name] = d
    res = compare_runs(runs["run-a"], runs["run-b"])
    # |err| a: 1, 2, 4, 0; b: 5, 0, 0, 10 -> mean difference (-4 + 2 + 4 - 10) / 4 = -2
    assert res["comparable"] and res["paired"]["diff"] == pytest.approx(-2.0)
    other = dict(spec, folds={"outer_test_seasons": [2021]})
    (runs["run-b"] / "run_spec.json").write_text(json.dumps(other), encoding="utf-8")
    blocked = compare_runs(runs["run-a"], runs["run-b"])
    assert not blocked["comparable"] and "folds.outer_test_seasons" in blocked["differences"][0]
    ctx = context(tmp_path, tmp_path / "raw", pd.Timestamp("2026-09-23T12:00Z"))
    assert ctx["active_jobs"] == 0 and ctx["blocking"] == [] and ctx["games_age_hours"] is None
    assert ctx["snapshot"] is None and ctx["drafts"] == 0


def test_context_names_the_latest_snapshot_and_counts_drafts(tmp_path):
    from models.tuning.ui.data import context

    lab = tmp_path / "lab"
    (lab / "shadow").mkdir(parents=True)
    _shadow(lab / "shadow")
    (lab / "drafts").mkdir()
    (lab / "drafts" / "draft-abc.json").write_text("{}", encoding="utf-8")
    ctx = context(lab, lab / "shadow" / "raw", CUT4 - pd.Timedelta(hours=2))
    assert ctx["snapshot"]["week"] == 4 and ctx["drafts"] == 1


def test_every_hypothesis_points_at_a_record_that_exists():
    h = hypotheses()
    assert h["id"].is_unique and set(h["status"]) <= {"closed", "pending"}
    missing = [r for r in h["record"] if not (REPO / r).exists()]
    assert not missing
