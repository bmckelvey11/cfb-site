"""Acceptance check: feature sidecar regen under a held read handle + refresh with Flask up.

The feature store uses in-place CREATE OR REPLACE TABLE so enrich must succeed
while another process holds features.duckdb open read-only, and the daily
refresh_cfbd job must still complete while the dev server is running.

    python scripts/check_feature_store_refresh_under_reader.py
    python scripts/check_feature_store_refresh_under_reader.py --skip-refresh

Exit 0 when every step succeeds; non-zero on first failure.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import duckdb

REPO = next(parent for parent in Path(__file__).resolve().parents if (parent / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

FEATURES_DB = cfb_paths.DATA_ROOT / "processed" / "features.duckdb"
WEB_URL = "http://127.0.0.1:5000/system"
_VENV_CFBD = REPO / ".venv-cfbd" / "Scripts" / "python.exe"
PYTHON = str(_VENV_CFBD) if _VENV_CFBD.is_file() else sys.executable


def _poll_reader(path: Path, stop: threading.Event) -> None:
    """Mimic the web app: read-only connect, one query, close (no long-lived handle)."""
    while not stop.is_set():
        try:
            con = duckdb.connect(str(path), read_only=True)
            try:
                con.execute("SELECT count(*) FROM features").fetchone()
            finally:
                con.close()
        except duckdb.IOException:
            pass
        time.sleep(0.2)


def _run(label: str, args: list[str], *, cwd: Path | None = None) -> None:
    print(f"=== {label} ===")
    proc = subprocess.run(args, cwd=cwd or REPO, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"{label} failed with exit {proc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Only run enrich-under-reader (skips the long refresh_cfbd.py step).",
    )
    ap.add_argument("--web-port", type=int, default=5000)
    args = ap.parse_args()
    global WEB_URL
    WEB_URL = f"http://127.0.0.1:{args.web_port}/system"

    if not FEATURES_DB.is_file():
        print(f"Missing {FEATURES_DB}; run enrich first.", file=sys.stderr)
        return 1

    stop = threading.Event()
    poller = threading.Thread(target=_poll_reader, args=(FEATURES_DB, stop), daemon=True)
    poller.start()
    print("=== polling read-only loads against features.duckdb ===")

    env = os.environ.copy()
    env["CFB_DATA_ROOT"] = str(cfb_paths.DATA_ROOT)
    web = subprocess.Popen(
        [PYTHON, "-m", "cfb_system_maker", "web", "--data-dir", str(cfb_paths.DATA_ROOT), "--port", str(args.web_port)],
        cwd=REPO,
        env=env,
    )
    try:
        for _ in range(300):
            try:
                urllib.request.urlopen(WEB_URL, timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            print("Flask did not become reachable", file=sys.stderr)
            return 1
        print("=== Flask reachable (features loaded at least once) ===")

        _run(
            "enrich under reader",
            [PYTHON, "-m", "cfb_system_maker", "enrich", "--data-dir", str(cfb_paths.DATA_ROOT)],
        )

        if not args.skip_refresh:
            _run("refresh_cfbd", [PYTHON, "scripts/refresh_cfbd.py"], cwd=REPO)
    finally:
        stop.set()
        poller.join(timeout=5)
        web.terminate()
        try:
            web.wait(timeout=15)
        except subprocess.TimeoutExpired:
            web.kill()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
