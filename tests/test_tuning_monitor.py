"""The lab monitor's data layer: read-only ledger access, the alerts that need the user,
and a hypothesis ledger whose records exist."""
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from models.tuning.ledger import Ledger, read_only
from models.tuning.monitor_data import hypotheses, shadow_view

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


def test_every_hypothesis_points_at_a_record_that_exists():
    h = hypotheses()
    assert h["id"].is_unique and set(h["status"]) <= {"closed", "pending"}
    missing = [r for r in h["record"] if not (REPO / r).exists()]
    assert not missing
