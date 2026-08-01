import json

from pipeline import config
from pipeline.llm import generate, strip_code_fences

QUICK_EXPLAIN_SYSTEM = (config.PROMPTS_DIR / "quick_explain_system.md").read_text()


class QuickExplainError(Exception):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


def quick_explain(topic_prompt: str) -> dict:
    """Returns a validated {headline, explanation, key_points} dict. No repair
    retry — this is supplementary UI content shown while the real video
    renders, not pipeline-critical, so a bad response just raises rather
    than spending another Gemini call to fix it."""
    user_message = f"Quick explanation request:\n\n{topic_prompt}"
    raw = generate(QUICK_EXPLAIN_SYSTEM, user_message, config.QUICK_EXPLAIN_MODEL)

    text = strip_code_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise QuickExplainError(f"invalid JSON: {e}", raw_response=raw) from e

    problems = validate_quick_explain(data)
    if problems:
        raise QuickExplainError(f"quick explain failed validation: {problems}", raw_response=raw)

    return data


def validate_quick_explain(data) -> list[str]:
    if not isinstance(data, dict):
        return ["quick explain output must be a JSON object"]

    problems = []

    headline = data.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        problems.append("headline must be a non-empty string")

    explanation = data.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        problems.append("explanation must be a non-empty string")

    key_points = data.get("key_points")
    if not isinstance(key_points, list) or not (2 <= len(key_points) <= 4):
        problems.append("key_points must be a list of 2 to 4 items")
    elif not all(isinstance(p, str) and p.strip() for p in key_points):
        problems.append("all key_points must be non-empty strings")

    return problems
