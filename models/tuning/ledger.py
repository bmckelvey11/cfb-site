"""Append-only prediction ledger for the live shadow system (plan §34.2).

Each record is hash-chained to the one before it:
`sha256(prev_sha256 + "\\n" + kind + "\\n" + created_at + "\\n" + canonical_payload)`.
Triggers on `records` reject UPDATE/DELETE at the database level, so a bug or a
stray script touching the file directly cannot rewrite history without `verify()`
catching it. `append`/`append_many` read the last hash and insert inside one
`BEGIN IMMEDIATE` transaction (mirrors `models.tuning.worker.LabStore`), so two
processes appending concurrently still produce one valid chain.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("arm", "alias", "snapshot", "prediction", "missed", "score", "revision",
         "quotes_archived", "period_verdict")

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_sha256 TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS records_no_update
BEFORE UPDATE ON records
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;
CREATE TRIGGER IF NOT EXISTS records_no_delete
BEFORE DELETE ON records
BEGIN
    SELECT RAISE(ABORT, 'ledger is append-only');
END;
"""


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    seq: int
    kind: str
    created_at: str  # UTC ISO-8601, seconds precision
    payload: dict
    prev_sha256: str  # "" for the first record
    sha256: str


def _canonical(payload: dict) -> str:
    """Deterministic JSON encoding; raises LedgerError before anything is written."""
    if not isinstance(payload, dict):
        raise LedgerError(f"payload must be a dict, got {type(payload).__name__}")
    try:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)
        text.encode("utf-8")  # surfaces lone surrogates the dump itself would accept
    except (TypeError, ValueError) as e:
        raise LedgerError(f"payload is not JSON-encodable: {e}") from e
    return text


def _digest(prev_sha256: str, kind: str, created_at: str, canonical: str) -> str:
    return hashlib.sha256(f"{prev_sha256}\n{kind}\n{created_at}\n{canonical}"
                          .encode("utf-8")).hexdigest()


def _record(row: sqlite3.Row) -> Record:
    return Record(seq=row["seq"], kind=row["kind"], created_at=row["created_at"],
                 payload=json.loads(row["payload"]), prev_sha256=row["prev_sha256"],
                 sha256=row["sha256"])


class Ledger:
    """One hash-chained, append-only sqlite table at `path`."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=30)
        try:
            con.executescript(SCHEMA)
        finally:
            con.close()

    @contextmanager
    def _tx(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def append(self, kind: str, payload: dict, created_at: str | None = None) -> Record:
        return self.append_many([(kind, payload)], created_at=created_at)[0]

    def append_many(self, items: list[tuple[str, dict]],
                    created_at: str | None = None) -> list[Record]:
        """Validate every item, then insert all of them in one transaction, or none."""
        if not items:
            return []
        prepared = []
        for kind, payload in items:
            if kind not in KINDS:
                raise LedgerError(f"unknown kind: {kind!r}")
            prepared.append((kind, _canonical(payload)))
        with self._tx() as con:
            # Taken after the write lock is held so seq order and timestamp order agree.
            ts = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
            prev = self._last_sha(con)
            out = []
            for kind, canonical in prepared:
                sha = _digest(prev, kind, ts, canonical)
                cur = con.execute(
                    "INSERT INTO records (kind, created_at, payload, prev_sha256, sha256) "
                    "VALUES (?, ?, ?, ?, ?)", (kind, ts, canonical, prev, sha))
                out.append(Record(seq=cur.lastrowid, kind=kind, created_at=ts,
                                  payload=json.loads(canonical), prev_sha256=prev, sha256=sha))
                prev = sha
            return out

    @staticmethod
    def _last_sha(con: sqlite3.Connection) -> str:
        row = con.execute("SELECT sha256 FROM records ORDER BY seq DESC LIMIT 1").fetchone()
        return row["sha256"] if row else ""

    def records(self, kind: str | None = None) -> list[Record]:
        with self._tx() as con:
            if kind is None:
                rows = con.execute("SELECT * FROM records ORDER BY seq").fetchall()
            else:
                rows = con.execute("SELECT * FROM records WHERE kind = ? ORDER BY seq",
                                   (kind,)).fetchall()
        return [_record(r) for r in rows]

    def verify(self) -> tuple[bool, str]:
        """Recompute every hash in seq order; names the first bad seq.

        A gap in `seq` (AUTOINCREMENT can leave one after a rolled-back insert) is not
        a failure -- only a bad hash or a prev_sha256 that doesn't match the actual
        previous record's sha256 is.
        """
        with self._tx() as con:
            rows = con.execute("SELECT * FROM records ORDER BY seq").fetchall()
        prev = ""
        for row in rows:
            if row["prev_sha256"] != prev:
                return False, f"seq {row['seq']}: prev_sha256 does not chain from the prior record"
            expected = _digest(row["prev_sha256"], row["kind"], row["created_at"], row["payload"])
            if expected != row["sha256"]:
                return False, f"seq {row['seq']}: sha256 does not match its stored fields"
            prev = row["sha256"]
        return True, f"ok: {len(rows)} records"
