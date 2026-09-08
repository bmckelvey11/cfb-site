import os
from datetime import datetime, timezone
from pathlib import Path

_configured_root = os.environ.get("CFB_DATA_ROOT")
if not _configured_root:
    raise RuntimeError(
        "CFB_DATA_ROOT is required; point it at the external CFB data directory"
    )

DATA_ROOT = Path(_configured_root).expanduser().resolve()
DB_PATH = DATA_ROOT / "cfb.duckdb"

# Warehouse inputs. `build_duckdb` globs RAW/*.json, so everything landing here
# is meant to load -- a stray file becomes a permanent table.
RAW = DATA_ROOT / "raw"

# Landed data the warehouse does NOT read: vendor one-offs, point-in-time
# snapshots, and sources not wired to the loader. Nothing here is globbed.
INGEST = DATA_ROOT / "ingest"

PROCESSED = DATA_ROOT / "processed"


def current_season(now: datetime | None = None) -> int:
    """The CFB season a moment belongs to: calendar year Jul-Dec, year - 1 Jan-Jun.

    Lives here because it is a project-wide convention, not one scraper's rule --
    January's bowls and playoff still belong to the season that started in July,
    so anything defaulting a `--season` has to agree on the boundary.
    """
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1
