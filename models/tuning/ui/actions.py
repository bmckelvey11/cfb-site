"""The only things the lab GUI does that write, all through the lab's own CLI.

- a draft spec file under `<lab root>/drafts/`, named by its content hash, so the file
  that was validated is the file that launches;
- a detached worker (`python -m models.tuning run`) in the main `.venv`, logging to
  `<lab root>/logs/<run_id>.log`; it keeps running if the GUI stops;
- a cancel request (`python -m models.tuning cancel`).

Nothing here writes in the repo, and no command goes through a shell.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MAIN_PY = REPO / ".venv" / "Scripts" / "python.exe"
DETACHED = (getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


class Refused(Exception):
    pass


def api(root: Path, *args: str) -> dict:
    """One call to `models.tuning.ui.api` in the main `.venv`; its JSON answer."""
    r = subprocess.run([str(MAIN_PY), "-m", "models.tuning.ui.api", *args, "--root", str(root)],
                       cwd=REPO, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Refused(f"lab api failed: {r.stderr.strip()[-2000:]}")
    return json.loads(r.stdout)


def write_draft(root: Path, doc: dict) -> Path:
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    path = root / "drafts" / f"draft-{hashlib.sha256(text.encode()).hexdigest()[:12]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return path


def launch(root: Path, draft: Path, replicate: int) -> tuple[str, Path]:
    """Re-validate the exact file, then start a detached worker on it."""
    check = api(root, "validate", "--spec", str(draft))
    if not check["ok"]:
        raise Refused("; ".join(check["errors"]))
    if check["launch"]["replicate"] != replicate:
        raise Refused(f"the lab changed since validation: replicate is now "
                      f"{check['launch']['replicate']}, not {replicate}. Validate again.")
    run_id = check["launch"]["run_id"]
    log = root / "logs" / f"{run_id}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as fh:
        subprocess.Popen([str(MAIN_PY), "-u", "-m", "models.tuning", "run", "--spec", str(draft),
                          "--root", str(root), "--replicate", str(replicate)],
                         cwd=REPO, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                         creationflags=DETACHED if sys.platform == "win32" else 0,
                         start_new_session=sys.platform != "win32", close_fds=True)
    return run_id, log


def cancel(root: Path, run_id: str) -> str:
    r = subprocess.run([str(MAIN_PY), "-m", "models.tuning", "cancel", "--run-id", run_id,
                        "--root", str(root)], cwd=REPO, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()
