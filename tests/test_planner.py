import copy
import json

import pytest

from pipeline import planner
from pipeline.planner import PlanError, make_plan, validate_plan

VALID_PLAN = {
    "title": "How binary search works",
    "slug": "binary_search",
    "scenes": [
        {
            "id": 1,
            "goal": "Show a sorted array of numbers",
            "visuals": ["16 squares in a row with values"],
            "narration": "Here's a sorted list of numbers.",
            "duration_sec": 6,
        },
        {
            "id": 2,
            "goal": "Pick the middle element",
            "visuals": ["highlight the middle square"],
            "narration": "We start by looking at the middle.",
            "duration_sec": 7,
        },
        {
            "id": 3,
            "goal": "Eliminate half the array",
            "visuals": ["fade out the excluded half"],
            "narration": "Since it's smaller, we discard the right half.",
            "duration_sec": 6,
        },
    ],
}


def _plan():
    return copy.deepcopy(VALID_PLAN)


def test_valid_plan_has_no_problems():
    assert validate_plan(_plan()) == []


def test_rejects_slug_with_invalid_characters():
    plan = _plan()
    plan["slug"] = "Binary Search!"
    problems = validate_plan(plan)
    assert any("slug" in p for p in problems)


def test_rejects_empty_title():
    plan = _plan()
    plan["title"] = ""
    problems = validate_plan(plan)
    assert any("title" in p for p in problems)


def test_rejects_too_few_scenes():
    plan = _plan()
    plan["scenes"] = plan["scenes"][:2]
    problems = validate_plan(plan)
    assert any("scenes" in p for p in problems)


def test_rejects_too_many_scenes():
    plan = _plan()
    extra = copy.deepcopy(plan["scenes"][0])
    for i in range(4, 8):
        scene = copy.deepcopy(extra)
        scene["id"] = i
        plan["scenes"].append(scene)
    problems = validate_plan(plan)
    assert any("scenes" in p for p in problems)


def test_rejects_gap_in_scene_ids():
    plan = _plan()
    plan["scenes"][2]["id"] = 4
    problems = validate_plan(plan)
    assert any("id" in p for p in problems)


def test_rejects_duration_out_of_range():
    plan = _plan()
    plan["scenes"][0]["duration_sec"] = 30
    problems = validate_plan(plan)
    assert any("duration_sec" in p for p in problems)


def test_rejects_empty_goal():
    plan = _plan()
    plan["scenes"][0]["goal"] = ""
    problems = validate_plan(plan)
    assert any("goal" in p for p in problems)


def test_rejects_empty_narration():
    plan = _plan()
    plan["scenes"][0]["narration"] = "  "
    problems = validate_plan(plan)
    assert any("narration" in p for p in problems)


def test_rejects_empty_visuals_list():
    plan = _plan()
    plan["scenes"][0]["visuals"] = []
    problems = validate_plan(plan)
    assert any("visuals" in p for p in problems)


def _fake_generate(responses):
    calls = []

    def fake(system, user, model):
        calls.append({"system": system, "user": user, "model": model})
        return responses[len(calls) - 1]

    fake.calls = calls
    return fake


def test_make_plan_returns_parsed_plan_on_first_success(monkeypatch):
    fake = _fake_generate([json.dumps(VALID_PLAN)])
    monkeypatch.setattr(planner, "generate", fake)

    result = make_plan("explain binary search")

    assert result == VALID_PLAN
    assert len(fake.calls) == 1


def test_make_plan_strips_code_fences_from_response(monkeypatch):
    fenced = "```json\n" + json.dumps(VALID_PLAN) + "\n```"
    fake = _fake_generate([fenced])
    monkeypatch.setattr(planner, "generate", fake)

    result = make_plan("explain binary search")

    assert result == VALID_PLAN


def test_make_plan_repairs_invalid_json_then_succeeds(monkeypatch):
    fake = _fake_generate(["not json at all", json.dumps(VALID_PLAN)])
    monkeypatch.setattr(planner, "generate", fake)

    result = make_plan("explain binary search")

    assert result == VALID_PLAN
    assert len(fake.calls) == 2


def test_make_plan_repair_message_includes_validation_problems(monkeypatch):
    bad_plan = _plan()
    bad_plan["slug"] = "Not Valid!"
    fake = _fake_generate([json.dumps(bad_plan), json.dumps(VALID_PLAN)])
    monkeypatch.setattr(planner, "generate", fake)

    make_plan("explain binary search")

    repair_message = fake.calls[1]["user"]
    assert "slug" in repair_message


def test_make_plan_raises_plan_error_after_two_failed_attempts(monkeypatch):
    fake = _fake_generate(["not json", "still not json"])
    monkeypatch.setattr(planner, "generate", fake)

    with pytest.raises(PlanError) as excinfo:
        make_plan("explain binary search")

    assert len(fake.calls) == 2
    assert excinfo.value.raw_response == "still not json"


def test_make_plan_raises_plan_error_when_json_is_not_an_object(monkeypatch):
    fake = _fake_generate([json.dumps([1, 2, 3])] * 2)
    monkeypatch.setattr(planner, "generate", fake)

    with pytest.raises(PlanError):
        make_plan("explain binary search")

    assert len(fake.calls) == 2
