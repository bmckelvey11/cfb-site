"""Release E: the shadow lifecycle on a synthetic data root (no CFB_DATA_ROOT needed).

A two-season synthetic league; a hand-built freeze (the challenger predicts the ridge
total, split evenly home/away). Covers snapshot timing, supersession, scoring against
the prediction made last before kickoff, a missed week, a tracked revision, tampering,
and the period verdict.
"""
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from models.tuning.dist_spec import DecisionPolicySpec
from models.tuning.estimators import build_pipeline
from models.tuning.ledger import Ledger
from models.tuning.shadow import (
    ShadowRefused, an_crosswalk, freeze, predict_params, shadow_dir, tick,
)
from models.tuning.shadow_spec import ShadowSpec
from models.tuning.spec import ModelSpec

TEAMS = list("ABCDEFGH")
FEATURES = ["rv1_off_home", "rv1_def_home", "rv1_pace_home", "rv1_off_away", "rv1_def_away",
            "rv1_pace_away", "rv1_total", "min_prior_games", "neutral"]


def _kick(season, week, i):
    return pd.Timestamp(f"{season}-09-01T16:00:00Z") + pd.Timedelta(days=7 * (week - 1), hours=i)


def _league(done_through: dict[int, int], bump=0) -> tuple[dict, dict]:
    """games and drives payloads per season; weeks <= done_through[season] are final."""
    rng = np.random.default_rng(1)
    games, drives = {}, {}
    for season in (2025, 2026):
        g_rows, d_rows = [], []
        for week in range(1, 7):
            order = list(rng.permutation(TEAMS))
            for i in range(4):
                gid = season * 1000 + week * 10 + i
                home, away = order[2 * i], order[2 * i + 1]
                done = week <= done_through[season]
                hls = [int(v) for v in rng.integers(0, 11, 4)]
                als = [int(v) for v in rng.integers(0, 11, 4)]
                if done and season == 2026 and week == 1 and i == 0:
                    hls[0] += bump                                 # a later correction
                g = {"id": gid, "season": season, "week": week, "seasonType": "regular",
                     "completed": done, "startDate": _kick(season, week, i).isoformat(),
                     "neutralSite": False, "homeTeam": home, "awayTeam": away,
                     "homeClassification": "fbs", "awayClassification": "fbs",
                     "homeLineScores": hls if done else None, "awayLineScores": als if done else None,
                     "homePoints": sum(hls) if done else None, "awayPoints": sum(als) if done else None}
                g_rows.append(g)
                if done:
                    for team, is_home in ((home, True), (away, False)):
                        d_rows += [{"gameId": gid, "offense": team, "isHomeOffense": is_home,
                                    "startPeriod": 1} for _ in range(12)]
        games[season], drives[season] = g_rows, d_rows
    return games, drives


def _write_data(root: Path, done_through: dict[int, int], bump=0, undone=(), moved=None,
                extra=()):
    """`undone`: game ids left unfinished; `moved`: game id -> new kickoff; `extra`: games
    appended to the 2026 schedule (added late)."""
    games, drives = _league(done_through, bump)
    for g in games[2026]:
        if g["id"] in undone:
            g.update(completed=False, homeLineScores=None, awayLineScores=None,
                     homePoints=None, awayPoints=None)
        if moved and g["id"] in moved:
            g["startDate"] = moved[g["id"]]
    drives[2026] = [d for d in drives[2026] if d["gameId"] not in set(undone)]
    games[2026] += list(extra)
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for s in games:
        (raw / f"games_{s}.json").write_text(json.dumps(games[s]), encoding="utf-8")
        (raw / f"drives_{s}.json").write_text(json.dumps(drives[s]), encoding="utf-8")
        (raw / f"lines_{s}.json").write_text("[]", encoding="utf-8")


def _spec(**over) -> ShadowSpec:
    d = {"spec_id": "shadow_fixture", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
         "season": 2026, "period_weeks": [5, 6], "rehearsal_weeks": [4],
         "base_run_id": "run-aaaaaaaaaaaa", "dist_run_id": "dist-bbbbbbbbbbbb",
         "window_seasons": [2025], "first_season": 2025,
         "policy": {"policy_id": "shadow_min_ev", "version": 1, "kind": "min_ev", "threshold": 0.03}}
    d.update(over)
    return ShadowSpec.model_validate(d)


def _npy(a):
    buf = io.BytesIO()
    np.save(buf, np.asarray(a, dtype=np.float64), allow_pickle=False)
    return buf.getvalue()


def _freeze(lab: Path, spec: ShadowSpec) -> Path:
    one_hot = [0.0] * 9
    one_hot[6] = 1.0
    half = [0.0] * 9
    half[6] = 0.5
    base = {"impute_median": [0.0] * 9, "scale_mean": [0.0] * 9, "scale_sd": [1.0] * 9}
    params = {"target": {**base, "coef": one_hot, "intercept": 0.0},
              "home_reg": {**base, "coef": half, "intercept": 0.0},
              "away_reg": {**base, "coef": half, "intercept": 0.0}}
    pairs = [[0.0, 0.0], [3.0, -3.0], [-7.0, 7.0], [10.0, 4.0], [-4.0, -6.0]]
    files = {"challenger.json": json.dumps({"features": FEATURES, "params": params}).encode(),
             "pairs_early.npy": _npy(pairs), "pairs_primary.npy": _npy(pairs),
             "ot.npy": _npy([3.0, 7.0])}
    frozen = shadow_dir(lab, spec) / "frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    for n, b in files.items():
        (frozen / n).write_bytes(b)
    doc = {"shadow_id": spec.shadow_id(), "spec_config_hash": spec.config_hash,
           "support_max": 150, "early_min_prior_games": 3, "features": FEATURES,
           "artifacts": {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
           "drift_reference": {}}
    path = lab / "freeze.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def world(tmp_path):
    data, lab = tmp_path / "data", tmp_path / "lab"
    spec = _spec()
    _write_data(data, {2025: 6, 2026: 3})
    return spec, data, lab, _freeze(lab, spec)


def _ledger(lab, spec) -> Ledger:
    return Ledger(shadow_dir(lab, spec) / "ledger.sqlite3")


def _run(world, when, **kw):
    spec, data, lab, fz = world
    return tick(spec, lab, data, now=pd.Timestamp(when), freeze_file=fz, **kw)


def test_snapshot_only_between_weeks_and_supersede_same_week(world):
    spec, data, lab, _ = world
    assert _run(world, "2026-09-15T18:30:00Z") == 0          # week 3 still being played
    assert not _ledger(lab, spec).records("snapshot")
    assert _run(world, "2026-09-16T12:00:00Z") == 0          # between weeks: rehearsal week 4
    assert _run(world, "2026-09-18T12:00:00Z") == 0          # again: supersedes
    snaps = _ledger(lab, spec).records("snapshot")
    assert [s.payload["week"] for s in snaps] == [4, 4] and snaps[0].payload["rehearsal"]
    preds = _ledger(lab, spec).records("prediction")
    assert len(preds) == 2 * 2 * 4                           # 2 snapshots x 2 aliases x 4 games
    ch = [p.payload for p in preds if p.payload["alias"] == "challenger"][0]
    assert ch["q10"] <= ch["q50"] <= ch["q90"]
    status = (shadow_dir(lab, spec) / "status.md").read_text(encoding="utf-8")
    assert "rehearsal" in status and "Chain: ok" in status


def test_full_period_scores_the_last_pre_kickoff_prediction_and_decides(world):
    spec, data, lab, _ = world
    _run(world, "2026-09-16T12:00:00Z")                      # week 4 rehearsal snapshot
    _write_data(data, {2025: 6, 2026: 4})
    assert _run(world, "2026-09-23T12:00:00Z") == 0          # score week 4, snapshot week 5
    led = _ledger(lab, spec)
    scores = [s.payload for s in led.records("score")]
    assert len(scores) == 8 and all(s["timing_ok"] and s["artifact_ok"] for s in scores)
    assert {"crps", "pit", "cover_80"} <= set(next(s for s in scores if s["alias"] == "challenger"))
    _write_data(data, {2025: 6, 2026: 5})
    _run(world, "2026-09-30T12:00:00Z")                      # score week 5, snapshot week 6
    _write_data(data, {2025: 6, 2026: 6})
    _run(world, "2026-10-07T12:00:00Z")                      # score week 6 -> verdict
    verdict = _ledger(lab, spec).records("period_verdict")
    assert len(verdict) == 1
    v = verdict[0].payload
    assert v["go"] and v["expected"] == 8 and v["scored"] == 8 and not v["missing"]
    assert "GO" in (shadow_dir(lab, spec) / "status.md").read_text(encoding="utf-8")


def test_a_week_with_no_snapshot_before_its_cutoff_is_missed_and_fails_the_period(world):
    spec, data, lab, _ = world
    _write_data(data, {2025: 6, 2026: 5})                    # nobody ticked during week 5's window
    _run(world, "2026-09-30T12:00:00Z")
    missed = _ledger(lab, spec).records("missed")
    assert {m.payload["week"] for m in missed} == {4, 5}
    _write_data(data, {2025: 6, 2026: 6})
    _run(world, "2026-10-07T12:00:00Z")
    v = _ledger(lab, spec).records("period_verdict")[0].payload
    assert not v["go"] and v["missed_weeks"] == [5]


def test_a_changed_past_result_is_logged_as_a_revision(world):
    spec, data, lab, _ = world
    _run(world, "2026-09-16T12:00:00Z")
    _write_data(data, {2025: 6, 2026: 4}, bump=3)            # a week-1 score corrected later
    _run(world, "2026-09-23T12:00:00Z")
    revs = _ledger(lab, spec).records("revision")
    assert [r.payload["week"] for r in revs] == [4]
    _run(world, "2026-09-24T12:00:00Z")                      # logged once, not every run
    assert len(_ledger(lab, spec).records("revision")) == 1


def test_tampered_artifacts_stop_predictions_and_fail_scoring(world):
    spec, data, lab, _ = world
    _run(world, "2026-09-16T12:00:00Z")
    snap = _ledger(lab, spec).records("snapshot")[0].payload
    (shadow_dir(lab, spec) / snap["pmf_file"]).write_bytes(b"tampered")
    _write_data(data, {2025: 6, 2026: 4})
    _run(world, "2026-09-23T12:00:00Z")
    ch = [s.payload for s in _ledger(lab, spec).records("score") if s.payload["alias"] == "challenger"]
    assert ch and not any(s["artifact_ok"] for s in ch)
    (shadow_dir(lab, spec) / "frozen" / "ot.npy").write_bytes(_npy([1.0]))
    before = len(_ledger(lab, spec).records())
    assert _run(world, "2026-09-24T12:00:00Z") == 1
    assert len(_ledger(lab, spec).records()) == before


def test_a_game_never_marked_final_blocks_the_next_snapshot_only_briefly(world):
    spec, data, lab, _ = world
    stuck = 2026 * 1000 + 4 * 10 + 0                         # week 4, kicked off 09-22 16:00Z
    _write_data(data, {2025: 6, 2026: 4}, undone={stuck})
    _run(world, "2026-09-23T12:00:00Z")                      # 20 h later: still waits
    assert not [s for s in _ledger(lab, spec).records("snapshot") if s.payload["week"] == 5]
    _run(world, "2026-09-24T12:00:00Z")                      # 44 h later, 4 days before cutoff
    week5 = [s.payload for s in _ledger(lab, spec).records("snapshot") if s.payload["week"] == 5]
    assert week5 and any("never marked final" in w for w in week5[0]["warnings"])


def test_a_kickoff_moved_before_the_snapshot_is_a_timing_violation(world):
    spec, data, lab, _ = world
    _write_data(data, {2025: 6, 2026: 4})
    _run(world, "2026-09-23T12:00:00Z")                      # week 5 snapshot at 12:00Z
    early = 2026 * 1000 + 5 * 10 + 3
    _write_data(data, {2025: 6, 2026: 5}, moved={early: "2026-09-23T06:00:00+00:00"})
    _run(world, "2026-09-30T12:00:00Z")
    week5 = [s.payload for s in _ledger(lab, spec).records("score") if s.payload["week"] == 5]
    assert week5 and not any(s["timing_ok"] for s in week5)  # the week's decision time moved
    assert not any(s["game_id"] == early for s in week5)     # no prediction before its kickoff


def test_postponed_games_are_no_action_and_late_additions_are_unscheduled(world):
    spec, data, lab, _ = world
    _write_data(data, {2025: 6, 2026: 4})
    _run(world, "2026-09-23T12:00:00Z")                      # week 5 snapshot
    _write_data(data, {2025: 6, 2026: 5})
    _run(world, "2026-09-30T12:00:00Z")                      # week 6 snapshot
    postponed = 2026 * 1000 + 6 * 10 + 1
    added = {"id": 999, "season": 2026, "week": 6, "seasonType": "regular", "completed": True,
             "startDate": "2026-10-06T20:00:00+00:00", "neutralSite": False, "homeTeam": "A",
             "awayTeam": "B", "homeClassification": "fbs", "awayClassification": "fbs",
             "homeLineScores": [7, 7, 7, 7], "awayLineScores": [3, 3, 3, 3],
             "homePoints": 28, "awayPoints": 12}
    _write_data(data, {2025: 6, 2026: 6}, undone={postponed},
                moved={postponed: "2026-11-21T20:00:00+00:00"}, extra=[added])
    _run(world, "2026-10-07T12:00:00Z")
    v = _ledger(lab, spec).records("period_verdict")[0].payload
    assert v["go"] and v["no_action"] == 1 and v["unscheduled"] == [999]
    assert v["expected"] == 8 and v["scored"] == 7 and len(v["code_sha256"]) == 1


def test_crosswalk_matches_by_team_location_with_aliases(tmp_path):
    board = {"games": [
        {"id": 7, "home_team_id": 1, "away_team_id": 2,
         "teams": [{"id": 1, "location": "Miami (FL)"}, {"id": 2, "location": "Duke"}]},
        {"id": 8, "home_team_id": 3, "away_team_id": 4,
         "teams": [{"id": 3, "location": "Nowhere"}, {"id": 4, "location": "Duke"}]}]}
    an = tmp_path / "raw" / "actionnetwork"
    an.mkdir(parents=True)
    (an / "scoreboard_2026_wk5.json").write_text(json.dumps(board), encoding="utf-8")
    payload = [{"id": 401, "week": 5, "seasonType": "regular", "homeTeam": "Miami", "awayTeam": "Duke"}]
    assert an_crosswalk(tmp_path, 2026, 5, payload) == ({7: 401}, [8])


def test_frozen_arithmetic_matches_the_pipeline_and_freeze_is_never_rewritten(tmp_path):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 3))
    x[::17, 1] = np.nan
    y = x[:, 0] * 2 - np.nan_to_num(x[:, 1]) + rng.normal(0, 0.1, 200)
    pipe = build_pipeline(ModelSpec(family="elastic_net", alpha=0.01, l1_ratio=0.3), 0).fit(x, y)
    from models.tuning.shadow import _fit_params
    assert np.allclose(predict_params(_fit_params(pipe), x), pipe.predict(x), atol=1e-9)
    out = tmp_path / "existing.freeze.json"
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(ShadowRefused, match="never rewritten"):
        freeze(_spec(), tmp_path, tmp_path, out=out)
