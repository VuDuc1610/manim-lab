import pytest
from google.genai import errors

import pipeline.llm as llm
from pipeline.llm import strip_code_fences


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return _FakeResponse(effect)


class _FakeClient:
    def __init__(self, side_effects):
        self.models = _FakeModels(side_effects)


def test_strips_fence_with_language_tag():
    text = "```python\nprint('hi')\n```"
    assert strip_code_fences(text) == "print('hi')"


def test_strips_fence_without_language_tag():
    text = "```\nprint('hi')\n```"
    assert strip_code_fences(text) == "print('hi')"


def test_leaves_unfenced_text_alone():
    text = "print('hi')"
    assert strip_code_fences(text) == "print('hi')"


def test_leaves_fence_in_the_middle_alone():
    text = "before\n```python\ncode\n```\nafter"
    assert strip_code_fences(text) == text


def test_generate_passes_system_via_system_instruction_config(monkeypatch):
    fake = _FakeClient(["ok"])
    monkeypatch.setattr(llm, "_client", fake)

    result = llm.generate("Be terse.", "Say hi", "gemini-2.5-flash")

    assert result == "ok"
    call = fake.models.calls[0]
    assert call["contents"] == "Say hi"
    assert call["config"].system_instruction == "Be terse."


def test_generate_retries_on_429_then_succeeds(monkeypatch):
    fake = _FakeClient([
        errors.ClientError(429, {"error": {"message": "rate limited"}}),
        errors.ClientError(429, {"error": {"message": "rate limited"}}),
        "final answer",
    ])
    monkeypatch.setattr(llm, "_client", fake)
    sleeps = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: sleeps.append(s))

    result = llm.generate("system", "user", "gemini-2.5-flash")

    assert result == "final answer"
    assert sleeps == [1, 2]
    assert len(fake.models.calls) == 3


def test_generate_retries_on_5xx_then_succeeds(monkeypatch):
    fake = _FakeClient([
        errors.ServerError(503, {"error": {"message": "unavailable"}}),
        "ok",
    ])
    monkeypatch.setattr(llm, "_client", fake)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    result = llm.generate("system", "user", "gemini-2.5-flash")

    assert result == "ok"


def test_generate_does_not_retry_on_400(monkeypatch):
    fake = _FakeClient([errors.ClientError(400, {"error": {"message": "bad request"}})])
    monkeypatch.setattr(llm, "_client", fake)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    with pytest.raises(errors.APIError):
        llm.generate("system", "user", "gemini-2.5-flash")

    assert len(fake.models.calls) == 1


def test_generate_gives_up_after_exhausting_retries(monkeypatch):
    fake = _FakeClient(
        [errors.ClientError(429, {"error": {"message": "rate limited"}})] * 5
    )
    monkeypatch.setattr(llm, "_client", fake)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    with pytest.raises(errors.APIError):
        llm.generate("system", "user", "gemini-2.5-flash")

    assert len(fake.models.calls) == 5


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(llm.MissingAPIKeyError):
        llm.generate("system", "user", "gemini-2.5-flash")
