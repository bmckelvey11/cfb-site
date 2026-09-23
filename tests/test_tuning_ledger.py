"""Release, shadow-system prediction ledger (plan §34.2): hash chain, append-only,
concurrency-safe appends. Synthetic data only; no network, no CFB_DATA_ROOT.
"""
import hashlib
import json
import multiprocessing
import sqlite3
from contextlib import closing

import pytest

from models.tuning.ledger import KINDS, Ledger, LedgerError


def _mp_append_worker(path_str: str, n: int, barrier) -> None:
    """Module-level so multiprocessing (spawn, required on Windows) can pickle it."""
    ledger = Ledger(path_str)
    barrier.wait()  # release both workers together so their appends actually overlap
    for i in range(n):
        ledger.append("prediction", {"worker_i": i})


def test_append_and_records_round_trip(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    a = ledger.append("arm", {"arm_id": "x"}, created_at="2026-09-23T00:00:00+00:00")
    b = ledger.append("score", {"game_id": 1}, created_at="2026-09-23T00:00:01+00:00")
    recs = ledger.records()
    assert [r.kind for r in recs] == ["arm", "score"]
    assert [r.payload for r in recs] == [{"arm_id": "x"}, {"game_id": 1}]
    assert recs[0].prev_sha256 == ""
    assert recs[1].prev_sha256 == a.sha256 == recs[0].sha256
    assert b.seq == a.seq + 1
    assert ledger.verify() == (True, "ok: 2 records")


def test_records_filters_by_kind(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.append("arm", {"i": 1})
    ledger.append("score", {"i": 2})
    ledger.append("arm", {"i": 3})
    assert [r.payload["i"] for r in ledger.records(kind="arm")] == [1, 3]


def test_update_and_delete_through_raw_connection_raise(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = Ledger(path)
    ledger.append("prediction", {"a": 1})
    with closing(sqlite3.connect(path, isolation_level=None)) as con:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute("UPDATE records SET payload = '{}' WHERE seq = 1")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute("DELETE FROM records WHERE seq = 1")
    # the failed raw statements did not leave a lingering lock on the file
    ledger.append("prediction", {"a": 2})
    assert len(ledger.records()) == 2


def test_tampering_after_dropping_triggers_is_caught_by_verify(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = Ledger(path)
    for i in range(4):
        ledger.append("score", {"i": i})
    with closing(sqlite3.connect(path, isolation_level=None)) as con:
        con.execute("DROP TRIGGER records_no_update")
        con.execute("UPDATE records SET payload = '{\"i\":99}' WHERE seq = 2")
    ok, reason = ledger.verify()
    assert ok is False
    assert "seq 2:" in reason


def test_unknown_kind_raises_and_writes_nothing(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    with pytest.raises(LedgerError):
        ledger.append("not_a_kind", {"a": 1})
    assert ledger.records() == []


def test_nan_payload_raises_and_writes_nothing(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    with pytest.raises(LedgerError):
        ledger.append("score", {"value": float("nan")})
    assert ledger.records() == []


def test_non_dict_payload_raises(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    with pytest.raises(LedgerError):
        ledger.append("score", ["not", "a", "dict"])


def test_append_many_with_one_bad_item_writes_nothing(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.append("arm", {"seed": True})
    with pytest.raises(LedgerError):
        # the bad item is last, so an implementation that validated lazily would still
        # have written the two good ones first -- it must not.
        ledger.append_many([("score", {"i": 1}), ("score", {"i": 2}), ("bogus", {"i": 3})])
    assert [r.payload for r in ledger.records()] == [{"seed": True}]


def test_append_many_writes_contiguous_chained_records(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    recs = ledger.append_many([("arm", {"i": 1}), ("score", {"i": 2}), ("revision", {"i": 3})],
                              created_at="2026-09-23T00:00:00+00:00")
    assert [r.seq for r in recs] == [1, 2, 3]
    assert recs[0].prev_sha256 == ""
    assert recs[1].prev_sha256 == recs[0].sha256
    assert recs[2].prev_sha256 == recs[1].sha256
    assert ledger.verify() == (True, "ok: 3 records")


def test_two_ledger_objects_alternating_appends_verify(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    a, b = Ledger(path), Ledger(path)
    for i in range(10):
        (a if i % 2 == 0 else b).append("prediction", {"i": i})
    ok, reason = a.verify()
    assert ok, reason
    assert len(a.records()) == 10


def test_concurrent_processes_appending_leave_a_verifying_chain(tmp_path):
    path = str(tmp_path / "ledger.sqlite3")
    Ledger(path)  # create the schema in the parent so the children don't race on it
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    procs = [ctx.Process(target=_mp_append_worker, args=(path, 20, barrier)) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    assert [p.exitcode for p in procs] == [0, 0]
    ledger = Ledger(path)
    ok, reason = ledger.verify()
    assert ok, reason
    assert len(ledger.records()) == 40


def test_same_payload_and_created_at_and_prev_give_the_same_sha(tmp_path):
    created_at = "2026-09-23T00:00:00+00:00"
    a = Ledger(tmp_path / "a.sqlite3").append("arm", {"b": 2, "a": 1}, created_at=created_at)
    b = Ledger(tmp_path / "b.sqlite3").append("arm", {"a": 1, "b": 2}, created_at=created_at)
    assert a.sha256 == b.sha256
    canonical = json.dumps({"a": 1, "b": 2}, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(f"\narm\n{created_at}\n{canonical}".encode("utf-8")).hexdigest()
    assert a.sha256 == expected


def test_kinds_lists_the_documented_record_types():
    assert KINDS == ("arm", "alias", "snapshot", "prediction", "missed", "score", "revision",
                     "quotes_archived", "period_verdict")
