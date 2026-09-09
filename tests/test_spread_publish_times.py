import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "spread" / "scripts"))
import model_publish_times as mpt  # noqa: E402


def _snap(stamp, games, **cols):
    df = pd.DataFrame({"road": [g[0] for g in games], "home": [g[1] for g in games]})
    for k, v in cols.items():
        df[k] = v
    return stamp, df


def test_first_seen_per_slate_and_model():
    wk1 = [("A", "B"), ("C", "D")]
    wk2 = [("E", "F"), ("G", "H")]
    snaps = [
        _snap("20260831T190505Z", wk1, linesag=[1.0, None], linefpi=[None, None]),   # Mon 15:05 ET
        _snap("20260901T223002Z", wk1, linesag=[1.0, 2.0], linefpi=[3.0, 4.0]),      # Tue 18:30 ET
        _snap("20260907T130000Z", wk2, linesag=[1.0, 1.0], linefpi=[None, None]),    # next Mon
    ]
    out = mpt.first_seen(snaps)
    row = out.set_index(["slate", "model"])
    # stamp carries :05 seconds too (15:05:05 ET), so compare with the same tolerance
    # used below rather than an exact match on the truncated-to-minutes expectation.
    assert abs(row.loc[("2026-08-31", "linesag"), "hours_after_monday_et"] - (15.0 + 5 / 60)) < 0.01
    assert abs(row.loc[("2026-08-31", "linefpi"), "hours_after_monday_et"] - (24 + 18.5)) < 0.01
    assert row.loc[("2026-09-07", "linesag"), "hours_after_monday_et"] == 9.0
    assert ("2026-09-07", "linefpi") not in row.index          # never published that week
