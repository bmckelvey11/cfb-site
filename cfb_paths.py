import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", Path(__file__).resolve().parent / "data"))
DB_PATH = DATA_ROOT / "cfb.duckdb"
RAW = DATA_ROOT / "raw"
PROCESSED = DATA_ROOT / "processed"
