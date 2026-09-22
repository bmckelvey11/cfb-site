"""Markdown math uses $ delimiters, never \\( \\) or \\[ \\].

Enforces the delimiter part of the "Math in Markdown" rule in root CLAUDE.md: GitHub and
Obsidian do not render backslash delimiters. The other two parts of that rule (declare
variables, explain in prose) need a reader, not a regex.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PREFIXES = ("cfbd-python/", "archive/", ".planning/")

# Dated records predate the rule and are never rewritten (root CLAUDE.md docs lifecycle).
EXEMPT: set[str] = set()

FENCE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")
# ponytail: heuristic. `\( ... \)` on one line, or `\[` alone on a line; a Markdown-escaped
# bracket like `\[1\]` mid-sentence is legal and is not flagged.
BAD = re.compile(r"(?<!\\)\\\(.+?(?<!\\)\\\)|^[ \t]*\\\[[ \t]*$", re.M)


def offenders(text: str) -> list[str]:
    return BAD.findall(INLINE_CODE.sub("", FENCE.sub("", text)))


def test_detector():
    assert offenders(r"for family \(G\):")
    assert offenders("\\[\nM_0\n\\]")
    assert not offenders("$G$ and $$\n\\begin{gathered} a \\\\[1em] b \\end{gathered}\n$$")
    assert not offenders(r"see \[1\] and `\(x\)`")
    assert not offenders("```\n\\(x\\)\n```")


def test_no_backslash_math_delimiters():
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    bad = {
        f: len(hits)
        for f in tracked
        if not f.startswith(SKIP_PREFIXES) and f not in EXEMPT
        and (ROOT / f).exists()
        and (hits := offenders((ROOT / f).read_text(encoding="utf-8", errors="replace")))
    }
    assert not bad, f"use $...$ / $$ instead of \\( \\) or \\[ \\]: {bad}"
