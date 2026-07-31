from __future__ import annotations

import pytest

from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
from cfb_system_maker.narration import (
    NarrationError,
    build_prompt,
    find_anthropic_key,
    narrate_run,
)


def _sample_run():
    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12, losses=8, pushes=1, roi=0.0524,
        raw_p=0.031, corrected_p=0.062, bh_significant=False,
    )
    return SearchRun(
        name="my-run", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482, finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )


def test_build_prompt_includes_candidate_count_and_finalist_stats():
    prompt = build_prompt(_sample_run())
    assert "482" in prompt
    assert "12" in prompt and "8" in prompt
    assert "0.031" in prompt or "0.0310" in prompt
    assert "0.062" in prompt or "0.0620" in prompt


def test_build_prompt_handles_zero_finalists():
    run = SearchRun(
        name="empty", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=100, finalists_graded=0,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(),
    )
    prompt = build_prompt(run)
    assert "100" in prompt
    assert "no finalist" in prompt.lower() or "0 finalist" in prompt.lower()


def test_find_anthropic_key_from_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    assert find_anthropic_key(tmp_path / "env.env") == "test-key-123"


def test_find_anthropic_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        find_anthropic_key(tmp_path / "env.env")


class _FakeMessages:
    def __init__(self, text="Narration text.", raise_exc=None):
        self._text = text
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc:
            raise self._raise_exc
        block = type("Block", (), {"text": self._text})()
        return type("Message", (), {"content": [block]})()


class _FakeClient:
    def __init__(self, text="Narration text.", raise_exc=None):
        self.messages = _FakeMessages(text=text, raise_exc=raise_exc)


def test_narrate_run_returns_text_from_client():
    result = narrate_run(_sample_run(), client=_FakeClient(text="Some plain-English summary."))
    assert result == "Some plain-English summary."


def test_narrate_run_raises_narration_error_on_client_failure():
    with pytest.raises(NarrationError):
        narrate_run(_sample_run(), client=_FakeClient(raise_exc=RuntimeError("boom")))


def test_narrate_run_raises_narration_error_when_no_key_and_no_client(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NarrationError):
        narrate_run(_sample_run())
