import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "collect_line_timing",
    Path(__file__).resolve().parents[1] / "scripts" / "collect_line_timing.py",
)
ct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ct)

CSV = b"lineopen,line,road,home,linesag\n9,9.5,Sacramento St.,Eastern Mich.,8.28\n"
AT = datetime(2026, 8, 29, 13, 43, 7, tzinfo=timezone.utc)


@pytest.fixture
def snap_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "SNAP_DIR", tmp_path)
    return tmp_path


def test_snapshot_stamps_the_capture_time(snap_dir, monkeypatch):
    """The timestamp is the whole point -- it's the field the PT archive lacks."""
    monkeypatch.setattr(ct, "_get", lambda *a, **k: CSV)
    path = ct.snapshot(now=AT)
    assert path.name == "ncaapredictions_20260829T134307Z.csv"
    assert path.read_bytes() == CSV
    meta = json.loads((snap_dir / "ncaapredictions_20260829T134307Z.meta.json").read_text())
    assert meta["captured_at"] == "2026-08-29T13:43:07+00:00"
    assert meta["rows"] == 1


def test_snapshot_skips_an_unchanged_file(snap_dir, monkeypatch):
    """PT overwrites in place; running twice a week must not pile up duplicates."""
    monkeypatch.setattr(ct, "_get", lambda *a, **k: CSV)
    assert ct.snapshot(now=AT) is not None
    later = AT.replace(hour=20)
    assert ct.snapshot(now=later) is None
    assert len(list(snap_dir.glob("*.csv"))) == 1


def test_snapshot_writes_again_when_the_file_changes(snap_dir, monkeypatch):
    monkeypatch.setattr(ct, "_get", lambda *a, **k: CSV)
    ct.snapshot(now=AT)
    monkeypatch.setattr(ct, "_get", lambda *a, **k: CSV + b"7,7,Duke,Clemson,6.1\n")
    assert ct.snapshot(now=AT.replace(hour=20)) is not None
    assert len(list(snap_dir.glob("*.csv"))) == 2


def test_snapshot_refuses_an_empty_body(snap_dir, monkeypatch):
    monkeypatch.setattr(ct, "_get", lambda *a, **k: b"   ")
    with pytest.raises(RuntimeError, match="empty body"):
        ct.snapshot(now=AT)


def test_history_asks_for_the_full_game_period(tmp_path, monkeypatch):
    """`event`, not `game` -- `game` returns an empty payload from Action Network."""
    monkeypatch.setattr(ct, "AN_DIR", tmp_path)
    monkeypatch.setattr(ct, "event_ids", lambda season, weeks: [287967])
    seen = {}

    def fake_get(url, params=None, **k):
        seen["url"], seen["params"] = url, params
        return b'{"15":{"event":{"spread":[{"history":[{"updated_at":"2026-04-29T19:10:10Z"}]}]}}}'

    monkeypatch.setattr(ct, "_get", fake_get)
    monkeypatch.setattr(ct.time, "sleep", lambda s: None)
    assert ct.history(2026, range(1, 2)) == 1
    assert seen["params"] == {"periods": "event"}
    assert (tmp_path / "history_event_287967.json").exists()


def test_history_does_not_write_a_payload_with_no_ticks(tmp_path, monkeypatch):
    """An empty payload means AN hasn't posted history yet -- leave it to re-probe."""
    monkeypatch.setattr(ct, "AN_DIR", tmp_path)
    monkeypatch.setattr(ct, "event_ids", lambda season, weeks: [1, 2])
    monkeypatch.setattr(ct, "_get", lambda *a, **k: b"[]")
    monkeypatch.setattr(ct.time, "sleep", lambda s: None)
    assert ct.history(2026, range(1, 2)) == 0
    assert list(tmp_path.glob("*.json")) == []


def test_history_filename_never_collides_with_the_legacy_1h_files(tmp_path, monkeypatch):
    """Legacy history_{id}.json holds firsthalf/firstquarter only -- keep them apart."""
    monkeypatch.setattr(ct, "AN_DIR", tmp_path)
    (tmp_path / "history_99.json").write_bytes(b"[]")  # legacy file for the same event
    monkeypatch.setattr(ct, "event_ids", lambda season, weeks: [99])
    monkeypatch.setattr(ct, "_get", lambda *a, **k: b'{"15":{"event":{"updated_at":"x"}}}')
    monkeypatch.setattr(ct.time, "sleep", lambda s: None)
    ct.history(2026, range(1, 2))
    assert (tmp_path / "history_event_99.json").exists()
    assert (tmp_path / "history_99.json").read_bytes() == b"[]"  # untouched
