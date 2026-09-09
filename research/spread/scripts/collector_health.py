"""Exit 1 if the Prediction Tracker snapshot stream has gone quiet in season.

PT overwrites one file in place; a missed window is unrecoverable, so silence is the failure
that matters. Checks the newest snapshot's capture time against now. Meant for the Monday
routine and for a human who wants a one-line answer.

    python research/spread/scripts/collector_health.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_line_timing as clt  # noqa: E402

MAX_GAP_HOURS = 12.0        # two missed 6-hour slots


def in_season(now: datetime) -> bool:
    return (now.month, now.day) >= (8, 25) and (now.month, now.day) <= (12, 15)


def stale(latest: datetime, now: datetime, max_gap_hours: float = MAX_GAP_HOURS) -> bool:
    return (now - latest).total_seconds() > max_gap_hours * 3600


def main() -> int:
    now = datetime.now(timezone.utc)
    metas = sorted(clt.SNAP_DIR.glob("ncaapredictions_*.meta.json"))
    if not metas:
        print("no snapshots at all"); return 1
    latest = datetime.fromisoformat(json.loads(metas[-1].read_text())["captured_at"])
    gap = (now - latest).total_seconds() / 3600
    print(f"newest snapshot {metas[-1].name} captured {gap:.1f}h ago; {len(metas)} on disk")
    if in_season(now) and stale(latest, now):
        print(f"STALE: more than {MAX_GAP_HOURS:.0f}h without a capture in season"); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
