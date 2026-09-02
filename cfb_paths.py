import os
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
