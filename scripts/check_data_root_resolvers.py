"""Fail if anything resolves the data root without going through cfb_paths.

`cfb_paths.py` requires CFB_DATA_ROOT and checks for a `.cfb-data-root` marker, so a
wrong, stale, or unset root fails loudly there. Every resolver that bypasses it opts out
of that guarantee -- and the failure mode is not an error, it is a silent write to the
wrong directory, invisible to `git status` because `.gitignore` carries an unanchored
`data/`.

Two phases, because the sweep and the cutover land in separate commits:

    phase 1  executable fallbacks only -- runnable after the sweep, while the data
             root is still inside the repo
    phase 2  adds the location literals -- only meaningful after the cutover

Usage:
    python scripts/check_data_root_resolvers.py --phase 1
    python scripts/check_data_root_resolvers.py --phase 2
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Superseded records, vendored code, and generated output are not live resolvers.
SKIP_DIRS = {
    ".git", ".venv", ".venv-cfbd", "archive", "graphify-out", "node_modules",
    "cfbd-python", "data", ".planning", "__pycache__", ".pytest_cache",
    "__marimo__", ".ipynb_checkpoints",
}
SKIP_PARTS = (".claude/worktrees",)

# Records, not living instructions. The docs lifecycle rule in root CLAUDE.md is
# explicit that a dated doc is never rewritten after the fact, and plans/specs/backlog
# entries describe what was true when they were written. A command quoted in one is
# history; a command in a living guide is something someone will paste tomorrow.
RECORD_DIRS = ("docs/superpowers/plans/", "docs/superpowers/specs/", ".solopreneur/")
DATED_DOC = re.compile(r"-\d{4}-\d{2}-\d{2}\.md$")
RECORD_FILES = ("floor_bias_1h_chat_history.md",)

SCAN_SUFFIXES = {".py", ".cmd", ".bat", ".ps1", ".json", ".md", ".toml", ".ini", ".cfg"}

PHASE_1 = [
    (re.compile(r'set "CFB_DATA_ROOT=%'), "batch fallback to a repo-relative data root"),
    (re.compile(r'environ\.get\(\s*["\']CFB_DATA_ROOT["\']\s*,'), "os.environ.get with a fallback"),
    (re.compile(r'os\.environ\[\s*["\']CFB_DATA_ROOT["\']\s*\]'), "direct env read, bypasses the marker check"),
    (re.compile(r'--data-dir\s+data(?=\s|$)'), "documented command pinned to a repo-relative data dir"),
    (re.compile(r'Path\(\s*["\']data["\']\s*\)'), 'Path("data") resolves against cwd'),
    # test_browser_smoke.py slipped past the first draft of this scan: it never names
    # `data` as a Path, it embeds the whole relative path in a string literal.
    (re.compile(r'["\']data/(processed|raw|exports|logs|ingest|graphql)/'), "cwd-relative data path literal"),
    (re.compile(r'create_app\(\s*["\']data["\']\s*\)'), "app pointed at a cwd-relative data dir"),
]

PHASE_2 = PHASE_1 + [
    (re.compile(r"dev[\\/]{1,2}cfb[\\/]{1,2}data"), "hardcoded pre-move data root"),
]

# Lines that legitimately match. Each needs a reason, not just an exemption.
ALLOW = {
    # The canonical resolver itself: this *is* the CFB_DATA_ROOT read.
    ("cfb_paths.py", 'environ.get("CFB_DATA_ROOT")'),
    # The scanner's own pattern table.
    ("scripts/check_data_root_resolvers.py", None),
    # The plan and its review log quote the defects they exist to remove.
    ("docs/superpowers/plans/2026-09-21-data-root-move.md", None),
    ("docs/superpowers/plans/2026-09-21-data-root-move-review-log.md", None),
    ("docs/data-location-2026-09-21.md", None),
}
ALLOWED_FILES = {f for f, line in ALLOW if line is None}


def iter_files():
    for path in REPO.rglob("*"):
        if path.suffix not in SCAN_SUFFIXES or not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        if any(part in SKIP_DIRS for part in path.relative_to(REPO).parts):
            continue
        if any(s in rel for s in SKIP_PARTS):
            continue
        if rel.startswith(RECORD_DIRS) or DATED_DOC.search(rel) or rel.endswith(RECORD_FILES):
            continue
        yield path, rel


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", type=int, choices=(1, 2), default=1)
    args = ap.parse_args()
    patterns = PHASE_1 if args.phase == 1 else PHASE_2

    hits = []
    for path, rel in iter_files():
        if rel in ALLOWED_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pat, why in patterns:
                if pat.search(line):
                    hits.append((rel, lineno, why, line.strip()[:110]))

    if not hits:
        print(f"phase {args.phase}: clean -- no unguarded data-root resolvers")
        return 0

    print(f"phase {args.phase}: {len(hits)} unguarded resolver(s)\n", file=sys.stderr)
    for rel, lineno, why, line in hits:
        print(f"{rel}:{lineno}: {why}", file=sys.stderr)
        print(f"    {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
