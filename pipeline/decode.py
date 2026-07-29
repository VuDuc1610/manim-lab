import json
import re

from pipeline import config
from pipeline.llm import generate, strip_code_fences

_ID_RE = re.compile(r"^[a-z0-9_]+$")

DECODE_SYSTEM = (config.PROMPTS_DIR / "decode_system.md").read_text()


class DecodeError(Exception):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


def decode_fund_content(page_text: str) -> dict:
    """Returns a validated decode dict. Raises DecodeError after one repair attempt."""
    user_message = f"Fund page content:\n\n{page_text}\n\nProduce the JSON output described in your instructions."
    raw = generate(DECODE_SYSTEM, user_message, config.DECODE_MODEL)
    decode, problems = _parse_and_validate(raw)
    if not problems:
        return decode

    repair_message = (
        "Your previous response failed validation with these problems:\n"
        + "\n".join(f"- {p}" for p in problems)
        + f"\n\nYour previous response was:\n{raw}\n\n"
        "Return a corrected JSON object only. No prose, no markdown fences."
    )
    raw = generate(DECODE_SYSTEM, repair_message, config.DECODE_MODEL)
    decode, problems = _parse_and_validate(raw)
    if not problems:
        return decode

    raise DecodeError(
        f"Decode failed validation after repair attempt: {problems}",
        raw_response=raw,
    )


def _parse_and_validate(raw: str):
    text = strip_code_fences(raw)
    try:
        decode = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]
    return decode, validate_decode(decode)


def validate_decode(decode: dict) -> list[str]:
    if not isinstance(decode, dict):
        return ["decode output must be a JSON object"]

    problems = []

    fund_name = decode.get("fund_name")
    if not isinstance(fund_name, str) or not fund_name.strip():
        problems.append("fund_name must be a non-empty string")

    base_topic_prompt = decode.get("base_topic_prompt")
    if not isinstance(base_topic_prompt, str) or not base_topic_prompt.strip():
        problems.append("base_topic_prompt must be a non-empty string")

    suggestions = decode.get("suggestions")
    if not isinstance(suggestions, list):
        problems.append("suggestions must be a list")
        return problems

    if len(suggestions) != 3:
        problems.append(f"suggestions must contain exactly 3 items, got {len(suggestions)}")

    seen_ids = set()
    for i, suggestion in enumerate(suggestions):
        if not isinstance(suggestion, dict):
            problems.append(f"suggestion at index {i} is not an object")
            continue

        label = suggestion.get("id", i)

        sid = suggestion.get("id")
        if not isinstance(sid, str) or not sid:
            problems.append(f"suggestion {label}: id must be a non-empty string")
        elif not _ID_RE.match(sid):
            problems.append(f"suggestion {label}: id '{sid}' must match ^[a-z0-9_]+$")
        elif sid in seen_ids:
            problems.append(f"suggestion {label}: id '{sid}' is not unique")
        else:
            seen_ids.add(sid)

        question = suggestion.get("question")
        if not isinstance(question, str) or not question.strip():
            problems.append(f"suggestion {label}: question must be a non-empty string")

        topic_prompt = suggestion.get("topic_prompt")
        if not isinstance(topic_prompt, str) or not topic_prompt.strip():
            problems.append(f"suggestion {label}: topic_prompt must be a non-empty string")

    return problems
