"""Network-free checks for the spec-vs-code endpoint audit."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_endpoints  # noqa: E402


def test_client_paths_come_from_the_call_site_not_the_class_name():
    methods = audit_endpoints.client_methods()
    # TeamsApi serves paths that share no prefix with its class name.
    assert methods[("TeamsApi", "get_talent")] == "/talent"
    assert methods[("TeamsApi", "get_roster")] == "/roster"
    assert methods[("TeamsApi", "get_teams_ats")] == "/teams/ats"
    # One entry per path, so the spec diff can't double-count.
    assert len(set(methods.values())) == len(methods)


def test_unknown_spec_path_is_reported_as_missing_a_client_method(tmp_path, capsys, monkeypatch):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"paths": {"/talent": {"get": {}}, "/not/in/client": {"get": {}}}}))
    monkeypatch.setattr(sys, "argv", ["audit_endpoints", "--spec", str(spec)])

    # Registry entries whose paths are absent from this stub spec count as drift -> exit 1.
    assert audit_endpoints.main() == 1
    out = capsys.readouterr().out
    assert "/not/in/client" in out
    assert "REGISTRY DRIFT" in out  # the exit-1 came from drift, not only the no-client bucket
    assert "1 registered + 0 client-only + 1 no-client = 2 of 2 spec paths" in out


def _fake_schema(names):
    return {n: object() for n in names}


def test_graphql_partition_counts_shards_and_flags_unaccounted(tmp_path, capsys, monkeypatch):
    from cfb_system_maker.graphql_client import GQL_DEFAULT_TABLES

    known = GQL_DEFAULT_TABLES[0]
    monkeypatch.setattr(audit_endpoints, "_make_poster", lambda token: None)
    monkeypatch.setattr(audit_endpoints, "find_cfbd_token", lambda *a, **k: "test")
    monkeypatch.setattr(
        audit_endpoints, "_introspect",
        lambda post: _fake_schema([known, "gamePlayerStat", "brandNewTable", "athleteByPk"]),
    )
    (tmp_path / f"{known}.json").write_text("[]")
    # Per-season shards fold into their base table, so this counts as gamePlayerStat.
    (tmp_path / "gamePlayerStat_2024.json").write_text("[]")

    unaccounted = audit_endpoints._audit_graphql(tmp_path, quiet=False)
    out = capsys.readouterr().out

    assert unaccounted == ["brandNewTable"]           # neither defaulted nor documented
    assert "['athleteByPk']" in out                    # wrapper filter names what it drops
    assert "gamePlayerStat           1 file(s) on disk" in out
    assert "UNACCOUNTED: brandNewTable" in out


def test_graphql_section_degrades_to_a_note_when_the_schema_is_unreachable(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(audit_endpoints, "find_cfbd_token", lambda *a, **k: "test")
    monkeypatch.setattr(audit_endpoints, "_make_poster", lambda token: None)

    def _boom(post):
        raise RuntimeError("no tier 3")

    monkeypatch.setattr(audit_endpoints, "_introspect", _boom)

    # No Tier 3 must never fail the run — the REST half works offline and can't be held
    # hostage to a paid tier.
    assert audit_endpoints._audit_graphql(tmp_path, quiet=True) == []
    assert "schema not reached (RuntimeError)" in capsys.readouterr().out
