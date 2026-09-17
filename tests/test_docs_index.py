"""Every doc in a docs/ directory is listed in that directory's README.md.

Enforces the docs lifecycle rule in root CLAUDE.md: a write-up that is not in its index
is not done. Archived docs (archive/) are exempt.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIRS = [
    "docs",
    "cfb_system_maker/docs",
    "models/totals/docs",
    "models/over_zero/docs",
    "research/spread/docs",
    "research/totals/docs",
    "research/bankroll/docs",
]


@pytest.mark.parametrize("docs_dir", DOCS_DIRS)
def test_every_doc_is_indexed(docs_dir):
    docs = ROOT / docs_dir
    files = sorted(p.name for p in docs.glob("*.md") if p.name != "README.md") if docs.is_dir() else []
    if not files:
        pytest.skip(f"{docs_dir} has no docs")
    readme = docs / "README.md"
    assert readme.exists(), f"{docs_dir}/README.md is missing; every docs/ dir needs an index"
    text = readme.read_text(encoding="utf-8")
    missing = [f for f in files if f not in text]
    assert not missing, f"{docs_dir}/README.md has no row for: {missing}"
