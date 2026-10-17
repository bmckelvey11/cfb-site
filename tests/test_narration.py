from __future__ import annotations

import pytest

from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
from cfb_system_maker.narration import (
    NarrationError,
    build_prompt,
    find_openai_key,
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


def test_find_openai_key_from_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    assert find_openai_key(tmp_path / "env.env") == "test-key-123"


def test_find_openai_key_reads_openai_api_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API", raising=False)
    env_file = tmp_path / "env.env"
    env_file.write_text("CFBD_API_KEY=x\nOPENAI_API=sk-from-file\n", encoding="utf-8")
    assert find_openai_key(env_file) == "sk-from-file"


def test_find_openai_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API", raising=False)
    with pytest.raises(RuntimeError):
        find_openai_key(tmp_path / "env.env")


class _FakeCompletions:
    def __init__(self, text="Narration text.", raise_exc=None):
        self._text = text
        self._raise_exc = raise_exc
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self._raise_exc:
            raise self._raise_exc
        message = type("Message", (), {"content": self._text})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class _FakeClient:
    def __init__(self, text="Narration text.", raise_exc=None):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _FakeCompletions(text=text, raise_exc=raise_exc)


def test_narrate_run_returns_text_from_client():
    result = narrate_run(_sample_run(), client=_FakeClient(text="Some plain-English summary."))
    assert result == "Some plain-English summary."


def test_narrate_run_calls_cheap_model_with_minimal_reasoning():
    client = _FakeClient()
    narrate_run(_sample_run(), client=client)
    kwargs = client.chat.completions.kwargs
    assert kwargs["model"] == "gpt-5-nano"
    assert kwargs["reasoning_effort"] == "minimal"
    assert kwargs["max_completion_tokens"] == 300


def test_narrate_run_raises_narration_error_on_none_content():
    with pytest.raises(NarrationError):
        narrate_run(_sample_run(), client=_FakeClient(text=None))


def test_narrate_run_raises_narration_error_on_client_failure():
    with pytest.raises(NarrationError):
        narrate_run(_sample_run(), client=_FakeClient(raise_exc=RuntimeError("boom")))


def test_narrate_run_raises_narration_error_on_empty_text():
    with pytest.raises(NarrationError):
        narrate_run(_sample_run(), client=_FakeClient(text="   "))


def test_narrate_run_raises_narration_error_when_no_key_and_no_client(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NarrationError):
        narrate_run(_sample_run())
