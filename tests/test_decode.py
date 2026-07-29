import copy
import json

import pytest

from pipeline import decode
from pipeline.decode import DecodeError, decode_fund_content, validate_decode

VALID_DECODE = {
    "fund_name": "Schwab U.S. Dividend Equity ETF (SCHD)",
    "base_topic_prompt": "Explain how SCHD works: its 0.06% expense ratio and quarterly dividends.",
    "suggestions": [
        {
            "id": "higher_expense_ratio",
            "question": "What if the fee were 0.75% instead of 0.06%?",
            "topic_prompt": "Explain how returns differ if the expense ratio were 0.75% instead of 0.06%.",
        },
        {
            "id": "reinvested_dividends",
            "question": "What if you reinvested every dividend?",
            "topic_prompt": "Explain how reinvesting dividends compounds growth over time.",
        },
        {
            "id": "started_five_years_earlier",
            "question": "What if you'd started 5 years earlier?",
            "topic_prompt": "Explain how starting 5 years earlier changes total returns by now.",
        },
    ],
}


def _decode():
    return copy.deepcopy(VALID_DECODE)


def test_valid_decode_has_no_problems():
    assert validate_decode(_decode()) == []


def test_rejects_empty_fund_name():
    d = _decode()
    d["fund_name"] = ""
    problems = validate_decode(d)
    assert any("fund_name" in p for p in problems)


def test_rejects_empty_base_topic_prompt():
    d = _decode()
    d["base_topic_prompt"] = "   "
    problems = validate_decode(d)
    assert any("base_topic_prompt" in p for p in problems)


def test_rejects_wrong_number_of_suggestions():
    d = _decode()
    d["suggestions"] = d["suggestions"][:2]
    problems = validate_decode(d)
    assert any("suggestions" in p for p in problems)


def test_rejects_too_many_suggestions():
    d = _decode()
    d["suggestions"].append(copy.deepcopy(d["suggestions"][0]))
    problems = validate_decode(d)
    assert any("suggestions" in p for p in problems)


def test_rejects_invalid_suggestion_id():
    d = _decode()
    d["suggestions"][0]["id"] = "Not Valid!"
    problems = validate_decode(d)
    assert any("id" in p for p in problems)


def test_rejects_duplicate_suggestion_ids():
    d = _decode()
    d["suggestions"][1]["id"] = d["suggestions"][0]["id"]
    problems = validate_decode(d)
    assert any("not unique" in p for p in problems)


def test_rejects_empty_suggestion_question():
    d = _decode()
    d["suggestions"][0]["question"] = ""
    problems = validate_decode(d)
    assert any("question" in p for p in problems)


def test_rejects_empty_suggestion_topic_prompt():
    d = _decode()
    d["suggestions"][0]["topic_prompt"] = "  "
    problems = validate_decode(d)
    assert any("topic_prompt" in p for p in problems)


def _fake_generate(responses):
    calls = []

    def fake(system, user, model):
        calls.append({"system": system, "user": user, "model": model})
        return responses[len(calls) - 1]

    fake.calls = calls
    return fake


def test_decode_fund_content_returns_parsed_result_on_first_success(monkeypatch):
    fake = _fake_generate([json.dumps(VALID_DECODE)])
    monkeypatch.setattr(decode, "generate", fake)

    result = decode_fund_content("some fund page text")

    assert result == VALID_DECODE
    assert len(fake.calls) == 1
    assert "some fund page text" in fake.calls[0]["user"]


def test_decode_fund_content_strips_code_fences_from_response(monkeypatch):
    fenced = "```json\n" + json.dumps(VALID_DECODE) + "\n```"
    fake = _fake_generate([fenced])
    monkeypatch.setattr(decode, "generate", fake)

    result = decode_fund_content("some fund page text")

    assert result == VALID_DECODE


def test_decode_fund_content_repairs_invalid_json_then_succeeds(monkeypatch):
    fake = _fake_generate(["not json at all", json.dumps(VALID_DECODE)])
    monkeypatch.setattr(decode, "generate", fake)

    result = decode_fund_content("some fund page text")

    assert result == VALID_DECODE
    assert len(fake.calls) == 2


def test_decode_fund_content_repair_message_includes_validation_problems(monkeypatch):
    bad = _decode()
    bad["suggestions"] = bad["suggestions"][:1]
    fake = _fake_generate([json.dumps(bad), json.dumps(VALID_DECODE)])
    monkeypatch.setattr(decode, "generate", fake)

    decode_fund_content("some fund page text")

    repair_message = fake.calls[1]["user"]
    assert "suggestions" in repair_message


def test_decode_fund_content_raises_decode_error_after_two_failed_attempts(monkeypatch):
    fake = _fake_generate(["not json", "still not json"])
    monkeypatch.setattr(decode, "generate", fake)

    with pytest.raises(DecodeError) as excinfo:
        decode_fund_content("some fund page text")

    assert len(fake.calls) == 2
    assert excinfo.value.raw_response == "still not json"


def test_decode_fund_content_raises_decode_error_when_json_is_not_an_object(monkeypatch):
    fake = _fake_generate([json.dumps([1, 2, 3])] * 2)
    monkeypatch.setattr(decode, "generate", fake)

    with pytest.raises(DecodeError):
        decode_fund_content("some fund page text")

    assert len(fake.calls) == 2
