"""A payload key null through the sample window must survive the explode.

`json_group_structure` types such a key "NULL", and the struct built from that
type discards the real values in every unsampled row. That is how `lines`
lost spreadOpen, overUnderOpen and both moneylines across all 38,689 staged
rows -- see docs/duckdb-audit-2026-09-02.md S9.
"""

import json

import duckdb
import pytest

from cfb_system_maker import duckdb_load
from cfb_system_maker.duckdb_load import (
    _has_null_typed_key,
    _payload_structure,
    explode_payloads,
)


def _seed(con, n_null, n_valued, sample_rows):
    """`n_null` rows with spreadOpen null, then `n_valued` rows carrying a value."""
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE TABLE raw.lines (payload JSON, source_file VARCHAR)")
    for i in range(n_null):
        con.execute(
            "INSERT INTO raw.lines VALUES (?::JSON, 'f.json')",
            [json.dumps({"id": i, "spread": -3.5, "spreadOpen": None})],
        )
    for i in range(n_valued):
        con.execute(
            "INSERT INTO raw.lines VALUES (?::JSON, 'f.json')",
            [json.dumps({"id": 1000 + i, "spread": -7.0, "spreadOpen": -6.5})],
        )
    return sample_rows


def test_has_null_typed_key_detects_at_any_depth():
    assert _has_null_typed_key('{"a":"DOUBLE","b":"NULL"}')
    assert _has_null_typed_key('{"lines":[{"spread":"DOUBLE","spreadOpen":"NULL"}]}')
    assert not _has_null_typed_key('{"a":"DOUBLE","b":"VARCHAR"}')
    assert not _has_null_typed_key('{"lines":[{"spread":"DOUBLE"}]}')
    # A key literally named NULL is not a NULL *type*.
    assert not _has_null_typed_key('{"NULL":"DOUBLE"}')
    assert not _has_null_typed_key("not json")


def test_sampled_null_key_is_retyped_from_the_full_column(monkeypatch):
    con = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb_load, "_STRUCTURE_SAMPLE_ROWS", 5)
    _seed(con, n_null=5, n_valued=5, sample_rows=5)

    structure = _payload_structure(con, "raw.lines")
    assert '"spreadOpen":"NULL"' not in structure
    assert '"spreadOpen":"DOUBLE"' in structure


def test_values_outside_the_sample_survive_the_explode(monkeypatch):
    con = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb_load, "_STRUCTURE_SAMPLE_ROWS", 5)
    _seed(con, n_null=5, n_valued=5, sample_rows=5)

    explode_payloads(con)

    rows, populated = con.execute(
        'SELECT count(*), count("spreadOpen") FROM stg.lines'
    ).fetchone()
    assert rows == 10
    assert populated == 5, "values past the sample window were discarded"


def test_all_null_key_stays_null_typed_without_a_crash(monkeypatch):
    """Genuinely empty upstream: nothing to recover, and nothing should break."""
    con = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb_load, "_STRUCTURE_SAMPLE_ROWS", 5)
    _seed(con, n_null=10, n_valued=0, sample_rows=5)

    explode_payloads(con)
    assert con.execute("SELECT count(*) FROM stg.lines").fetchone()[0] == 10


def test_no_null_typed_key_takes_the_sampled_path(monkeypatch):
    """The full re-scan must not fire when the sample already typed everything."""
    con = duckdb.connect(":memory:")
    monkeypatch.setattr(duckdb_load, "_STRUCTURE_SAMPLE_ROWS", 5)
    _seed(con, n_null=0, n_valued=10, sample_rows=5)

    calls: list[str] = []

    class CountingCon:
        """DuckDBPyConnection.execute is read-only, so proxy instead of patching."""

        def execute(self, sql, *a, **k):
            calls.append(sql)
            return con.execute(sql, *a, **k)

    structure = _payload_structure(CountingCon(), "raw.lines")

    assert '"spreadOpen":"DOUBLE"' in structure
    assert len(calls) == 1, "sampled structure was complete; no re-scan should run"


def test_re_scan_failure_falls_back_to_the_sampled_structure():
    """A full scan that OOMs must not kill the load; keep the sampled type."""

    class FailingRescanCon:
        def __init__(self):
            self.n = 0

        def execute(self, sql, *a, **k):
            self.n += 1
            if self.n == 1:
                return _Result('{"spread":"DOUBLE","spreadOpen":"NULL"}')
            raise duckdb.Error("simulated OOM on full scan")

    class _Result:
        def __init__(self, v):
            self.v = v

        def fetchone(self):
            return (self.v,)

    structure = _payload_structure(FailingRescanCon(), "raw.lines")
    assert structure == '{"spread":"DOUBLE","spreadOpen":"NULL"}'
