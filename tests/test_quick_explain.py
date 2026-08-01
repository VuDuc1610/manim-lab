import copy
import json

import pytest

from pipeline import quick_explain
from pipeline.quick_explain import QuickExplainError, quick_explain as run_quick_explain, validate_quick_explain

VALID_EXPLAIN = {
    "headline": "SCHD's 0.06% expense ratio",
    "explanation": "SCHD charges very little to hold, so you keep almost all of your returns.",
    "key_points": [
        "0.06% expense ratio means $0.60/year per $1,000 invested",
        "Actively managed funds often charge 10x more",
    ],
}


def _explain():
    return copy.deepcopy(VALID_EXPLAIN)


def test_valid_explain_has_no_problems():
    assert validate_quick_explain(_explain()) == []


def test_rejects_empty_headline():
    d = _explain()
    d["headline"] = ""
    problems = validate_quick_explain(d)
    assert any("headline" in p for p in problems)


def test_rejects_empty_explanation():
    d = _explain()
    d["explanation"] = "   "
    problems = validate_quick_explain(d)
    assert any("explanation" in p for p in problems)


def test_rejects_too_few_key_points():
    d = _explain()
    d["key_points"] = d["key_points"][:1]
    problems = validate_quick_explain(d)
    assert any("key_points" in p for p in problems)


def test_rejects_too_many_key_points():
    d = _explain()
    d["key_points"] = d["key_points"] * 3
    problems = validate_quick_explain(d)
    assert any("key_points" in p for p in problems)


def test_rejects_blank_key_point():
    d = _explain()
    d["key_points"][0] = "   "
    problems = validate_quick_explain(d)
    assert any("key_points" in p for p in problems)


def _fake_generate(response):
    calls = []

    def fake(system, user, model):
        calls.append({"system": system, "user": user, "model": model})
        return response

    fake.calls = calls
    return fake


def test_quick_explain_returns_parsed_result_on_success(monkeypatch):
    fake = _fake_generate(json.dumps(VALID_EXPLAIN))
    monkeypatch.setattr(quick_explain, "generate", fake)

    result = run_quick_explain("Explain SCHD's expense ratio.")

    assert result == VALID_EXPLAIN
    assert len(fake.calls) == 1
    assert "Explain SCHD's expense ratio." in fake.calls[0]["user"]


def test_quick_explain_strips_code_fences_from_response(monkeypatch):
    fenced = "```json\n" + json.dumps(VALID_EXPLAIN) + "\n```"
    fake = _fake_generate(fenced)
    monkeypatch.setattr(quick_explain, "generate", fake)

    result = run_quick_explain("Explain SCHD's expense ratio.")

    assert result == VALID_EXPLAIN


def test_quick_explain_raises_on_invalid_json_with_no_retry(monkeypatch):
    fake = _fake_generate("not json at all")
    monkeypatch.setattr(quick_explain, "generate", fake)

    with pytest.raises(QuickExplainError) as excinfo:
        run_quick_explain("Explain SCHD's expense ratio.")

    assert len(fake.calls) == 1
    assert excinfo.value.raw_response == "not json at all"


def test_quick_explain_raises_on_validation_failure_with_no_retry(monkeypatch):
    bad = _explain()
    bad["headline"] = ""
    fake = _fake_generate(json.dumps(bad))
    monkeypatch.setattr(quick_explain, "generate", fake)

    with pytest.raises(QuickExplainError):
        run_quick_explain("Explain SCHD's expense ratio.")

    assert len(fake.calls) == 1
