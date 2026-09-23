"""The code fingerprint a run is pinned to (standard library only, so it imports fast).

`worker` re-exports `code_fingerprint` and `FINGERPRINTED`. `models/tuning/ui/` is outside
the glob on purpose: the GUI never changes a result, so editing it must not make a
completed run look like it ran on different code.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FINGERPRINTED = ("models/tuning/*.py", "models/tuning/feature_sets/*.json",
                 "scripts/weekly_ratings.py", "scripts/weekly_ratings_eval.py",
                 "scripts/pregame_replay_audit.py")


def code_fingerprint() -> str:
    """sha256 over the code a run depends on, line endings normalized (git may rewrite them)."""
    h = hashlib.sha256()
    for pattern in FINGERPRINTED:
        for path in sorted(REPO.glob(pattern)):
            h.update(path.relative_to(REPO).as_posix().encode() + b"\0")
            h.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()
