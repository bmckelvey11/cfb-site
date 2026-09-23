"""Release C join: one command runs a spec end to end, reproducibly, from a clean root.

Each run is a separate process into a fresh root, as a clean environment would be.
"""
import json
import subprocess
import sys
from pathlib import Path

from models.tuning.features import FEATURE_SETS, load_feature_set
from models.tuning.spec import load_run_spec

REPO = Path(__file__).resolve().parents[1]
COMMITTED = REPO / "models" / "tuning" / "specs" / "total_ratings_v1.json"


def _synthetic_spec(tmp_path: Path) -> Path:
    spec = json.loads(COMMITTED.read_text(encoding="utf-8"))
    spec["spec_id"] = "join_fixture"
    spec["dataset"] = {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 3,
                       "seasons": spec["dataset"]["seasons"]}
    spec["search"]["n_trials"] = 8
    spec["search"]["sampler"]["n_startup_trials"] = 4
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "models.tuning", *args], cwd=REPO,
                          capture_output=True, text=True, timeout=300)


def test_committed_spec_keeps_its_published_run_id():
    # Docs cite this run id; any change to RunSpec's canonical JSON (even a new null
    # field) would silently fork it. New spec types get their own hash instead.
    assert load_run_spec(COMMITTED).run_id() == "run-de1927346ab0"


def test_committed_spec_is_valid_and_embeds_the_committed_feature_set():
    spec = load_run_spec(COMMITTED)
    assert spec.feature_set == load_feature_set(FEATURE_SETS / "total_ratings_v1.json")
    assert spec.folds.inner_test_seasons == (2015, 2016, 2017, 2018, 2019)
    assert spec.folds.outer_test_seasons == (2021, 2022, 2023, 2024, 2025)
    assert "holdout" in spec.notes.lower()


def test_same_spec_in_two_clean_roots_gives_the_same_run_and_predictions(tmp_path):
    spec_path = _synthetic_spec(tmp_path)
    run_id = load_run_spec(spec_path).run_id()
    outs = []
    for name in ("a", "b"):
        done = _cli("run", "--spec", str(spec_path), "--root", str(tmp_path / name))
        assert done.returncode == 0, done.stderr
        result = json.loads(done.stdout[done.stdout.index("{"):])
        assert result["run_id"] == run_id and result["state"] == "completed"
        outs.append(tmp_path / name / "runs" / run_id)
    a, b = outs
    compared = ["predictions.csv", "trials.csv", *sorted(p.relative_to(a).as_posix()
                                                         for p in (a / "outer").glob("*.json"))]
    assert len(compared) == 2 + 5
    for rel in compared:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


def test_resubmitting_a_completed_spec_returns_the_existing_run(tmp_path):
    spec_path = _synthetic_spec(tmp_path)
    root = tmp_path / "lab"
    assert _cli("run", "--spec", str(spec_path), "--root", str(root)).returncode == 0
    card = next((root / "runs").glob("*/card.md"))
    before = card.stat().st_mtime_ns
    again = _cli("run", "--spec", str(spec_path), "--root", str(root))
    assert again.returncode == 0 and "already completed" in again.stdout
    assert card.stat().st_mtime_ns == before
    status = _cli("status", "--root", str(root))
    assert "completed" in status.stdout
