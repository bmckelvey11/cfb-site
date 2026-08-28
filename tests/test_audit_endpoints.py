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
    assert "1 registered + 0 client-only + 1 no-client = 2 of 2 spec paths" in out
