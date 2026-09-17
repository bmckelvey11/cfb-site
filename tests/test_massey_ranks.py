import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import massey_ranks as mr  # noqa: E402


def test_current_season_rolls_in_august():
    assert mr.current_season(dt.date(2026, 1, 20)) == 2025
    assert mr.current_season(dt.date(2026, 7, 31)) == 2025
    assert mr.current_season(dt.date(2026, 8, 1)) == 2026


def test_update_merges_index_and_fetches_only_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "OUT_DIR", tmp_path)
    (tmp_path / "editions.json").write_text(json.dumps({"2025": ["20251207"]}))
    (tmp_path / "ranks_20260823.json").write_text("{}")
    monkeypatch.setattr(mr, "season_editions", lambda year, delay: ["20260823", "20260830"])
    fetched = []
    monkeypatch.setattr(mr, "cmd_fetch", lambda ns: fetched.extend(ns.date) or 0)

    import argparse

    assert mr.cmd_update(argparse.Namespace(season=2026, delay=0)) == 0
    assert fetched == ["20260830"]
    index = json.loads((tmp_path / "editions.json").read_text())
    assert index == {"2025": ["20251207"], "2026": ["20260823", "20260830"]}
