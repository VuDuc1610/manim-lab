import os
import sys
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

_client = None

_RETRY_DELAYS_SEC = [1, 2, 4, 8]


class MissingAPIKeyError(RuntimeError):
    pass


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise MissingAPIKeyError(
                "GEMINI_API_KEY is not set. Add it to a .env file at the project root."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def generate(system: str, user: str, model: str) -> str:
    """Single-turn call. Returns raw text."""
    if os.environ.get("MOCK_LLM"):
        from pipeline.mock_llm import generate as mock_generate

        return mock_generate(system, user, model)

    client = _get_client()
    config = types.GenerateContentConfig(system_instruction=system)

    delays = [0] + _RETRY_DELAYS_SEC
    for attempt, delay in enumerate(delays):
        if delay:
            print(
                f"[llm] retrying in {delay}s (attempt {attempt + 1}/{len(delays)})",
                file=sys.stderr,
            )
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=model, contents=user, config=config
            )
            return response.text
        except errors.APIError as e:
            retryable = e.code == 429 or 500 <= e.code < 600
            if not retryable or attempt == len(delays) - 1:
                raise


def strip_code_fences(text: str) -> str:
    """Remove leading ```python / ``` and trailing ``` if present."""
    stripped = text.strip()
    if not (stripped.startswith("```") and stripped.endswith("```")):
        return text

    lines = stripped.split("\n")
    if len(lines) < 2:
        return text

    lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    else:
        return text

    return "\n".join(lines)
