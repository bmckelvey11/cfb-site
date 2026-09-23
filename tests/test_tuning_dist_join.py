"""Release D join: a distribution run on a published Release C run, reproducibly.

Synthetic data only. Each root gets its own base run and distribution run from separate
processes; the published tables must be byte-identical.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from models.tuning.dist_run import DistRefused, run_dist
from models.tuning.dist_spec import DistRunSpec
from models.tuning.spec import load_run_spec

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "models" / "tuning" / "specs" / "total_ratings_v1.json"
DIST = REPO / "models" / "tuning" / "specs" / "dist_total_v1.json"


def _specs(tmp_path: Path) -> tuple[Path, Path, str]:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    base["spec_id"] = "dist_join_fixture"
    base["dataset"] = {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 5,
                       "seasons": base["dataset"]["seasons"]}
    base["search"]["n_trials"] = 4
    base["search"]["sampler"]["n_startup_trials"] = 2
    base_path = tmp_path / "base.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    run_id = load_run_spec(base_path).run_id()
    dist = json.loads(DIST.read_text(encoding="utf-8"))
    dist["base_run_id"] = run_id
    dist_path = tmp_path / "dist.json"
    dist_path.write_text(json.dumps(dist), encoding="utf-8")
    return base_path, dist_path, run_id


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "models.tuning", *args], cwd=REPO,
                          capture_output=True, text=True, timeout=600)


def test_committed_dist_spec_names_the_published_base_run():
    spec = DistRunSpec.model_validate_json(DIST.read_text(encoding="utf-8"))
    assert spec.base_run_id == load_run_spec(BASE).run_id() == "run-de1927346ab0"
    assert spec.selection_seasons == (2018, 2019)


def test_distribution_run_is_reproducible_from_clean_roots(tmp_path):
    base_path, dist_path, _ = _specs(tmp_path)
    dist_id = DistRunSpec.model_validate_json(dist_path.read_text(encoding="utf-8")).run_id()
    dirs = []
    for name in ("a", "b"):
        root = tmp_path / name
        assert _cli("run", "--spec", str(base_path), "--root", str(root)).returncode == 0
        done = _cli("dist", "--spec", str(dist_path), "--root", str(root))
        assert done.returncode == 0, done.stderr
        out = json.loads(done.stdout[done.stdout.index("{"):])
        assert out["run_id"] == dist_id
        dirs.append(root / "runs" / dist_id)
    a, b = dirs
    for rel in ("pmf_outer.npy", "predictions.csv", "scores.json", "selective.json"):
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel
    card = (a / "card.md").read_text(encoding="utf-8")
    assert "Calibration gate" in card and dist_id in card

    # A tampered base run is refused before anything is scored.
    (tmp_path / "a" / "runs").joinpath(load_run_spec(base_path).run_id(),
                                       "predictions.csv").write_text("tampered", encoding="utf-8")
    other = DistRunSpec.model_validate_json(dist_path.read_text(encoding="utf-8")).model_copy(
        update={"selection_seasons": (2019,)})
    with pytest.raises(DistRefused, match="checksums"):
        run_dist(other, tmp_path / "a")
