import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import collector_health as ch  # noqa: E402

UTC = timezone.utc


def test_stale_after_max_gap():
    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    assert ch.stale(datetime(2026, 9, 7, 23, tzinfo=UTC), now)          # 13h
    assert not ch.stale(datetime(2026, 9, 8, 1, tzinfo=UTC), now)       # 11h


def test_in_season_window():
    assert ch.in_season(datetime(2026, 10, 1, tzinfo=UTC))
    assert not ch.in_season(datetime(2026, 2, 1, tzinfo=UTC))
