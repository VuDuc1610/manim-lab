import json
import re

from pipeline import config
from pipeline.llm import generate, strip_code_fences

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")

PLANNER_SYSTEM = (config.PROMPTS_DIR / "planner_system.md").read_text()


class PlanError(Exception):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


def make_plan(user_prompt: str) -> dict:
    """Returns a validated plan dict. Raises PlanError after retries."""
    raw = generate(PLANNER_SYSTEM, user_prompt, config.PLANNER_MODEL)
    plan, problems = _parse_and_validate(raw)
    if not problems:
        return plan

    repair_message = (
        "Your previous response failed validation with these problems:\n"
        + "\n".join(f"- {p}" for p in problems)
        + f"\n\nYour previous response was:\n{raw}\n\n"
        "Return a corrected JSON object only. No prose, no markdown fences."
    )
    raw = generate(PLANNER_SYSTEM, repair_message, config.PLANNER_MODEL)
    plan, problems = _parse_and_validate(raw)
    if not problems:
        return plan

    raise PlanError(
        f"Plan failed validation after repair attempt: {problems}",
        raw_response=raw,
    )


def _parse_and_validate(raw: str):
    text = strip_code_fences(raw)
    try:
        plan = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]
    return plan, validate_plan(plan)


def validate_plan(plan: dict) -> list[str]:
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]

    problems = []

    title = plan.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("title must be a non-empty string")

    slug = plan.get("slug")
    if not isinstance(slug, str) or not slug:
        problems.append("slug must be a non-empty string")
    elif not _SLUG_RE.match(slug):
        problems.append(f"slug '{slug}' must match ^[a-z0-9_]+$")

    scenes = plan.get("scenes")
    if not isinstance(scenes, list):
        problems.append("scenes must be a list")
        return problems

    if not (config.MIN_SCENES <= len(scenes) <= config.MAX_SCENES):
        problems.append(
            f"scenes length must be between {config.MIN_SCENES} and "
            f"{config.MAX_SCENES}, got {len(scenes)}"
        )

    ids = [s.get("id") if isinstance(s, dict) else None for s in scenes]
    if sorted(i for i in ids if isinstance(i, int)) != list(range(1, len(scenes) + 1)) or None in ids:
        problems.append(f"scene ids must be exactly 1..{len(scenes)} with no gaps, got {ids}")

    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            problems.append(f"scene at index {i} is not an object")
            continue

        label = scene.get("id", i + 1)

        duration = scene.get("duration_sec")
        if not isinstance(duration, (int, float)) or not (
            config.MIN_SCENE_SEC <= duration <= config.MAX_SCENE_SEC
        ):
            problems.append(
                f"scene {label}: duration_sec must be between "
                f"{config.MIN_SCENE_SEC} and {config.MAX_SCENE_SEC}"
            )

        goal = scene.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            problems.append(f"scene {label}: goal must be a non-empty string")

        narration = scene.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            problems.append(f"scene {label}: narration must be a non-empty string")

        visuals = scene.get("visuals")
        if (
            not isinstance(visuals, list)
            or not visuals
            or not all(isinstance(v, str) for v in visuals)
        ):
            problems.append(f"scene {label}: visuals must be a non-empty list of strings")

    return problems
