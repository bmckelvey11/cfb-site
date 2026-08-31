import os
from pathlib import Path

_configured_root = os.environ.get("CFB_DATA_ROOT")
if not _configured_root:
    raise RuntimeError(
        "CFB_DATA_ROOT is required; point it at the external CFB data directory"
    )

DATA_ROOT = Path(_configured_root).expanduser().resolve()
DB_PATH = DATA_ROOT / "cfb.duckdb"
RAW = DATA_ROOT / "raw"
PROCESSED = DATA_ROOT / "processed"
