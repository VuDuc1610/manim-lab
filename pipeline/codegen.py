import json
import re
import warnings
from concurrent.futures import ThreadPoolExecutor

from pipeline import config
from pipeline.llm import generate, strip_code_fences

_ALLOWED_IMPORT = "from manim import *"

_FORBIDDEN_TOKENS = [
    "subprocess",
    "eval(",
    "exec(",
    "__import__",
    "open(",
    "socket",
    "requests",
]


class SanitizeError(Exception):
    pass


def sanitize(code: str, scene_id: int) -> str:
    class_decl = f"class Scene{scene_id}(Scene):"
    if class_decl not in code:
        raise SanitizeError(
            f"scene {scene_id}: expected '{class_decl}' not found in generated source"
        )

    import_lines = [
        line.strip()
        for line in code.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    if import_lines != [_ALLOWED_IMPORT]:
        raise SanitizeError(
            f"scene {scene_id}: only '{_ALLOWED_IMPORT}' is allowed as an import, "
            f"found {import_lines}"
        )

    for token in _FORBIDDEN_TOKENS:
        if token in code:
            raise SanitizeError(
                f"scene {scene_id}: forbidden token '{token}' found in generated source"
            )

    tex_count = len(re.findall(r"\bMathTex\b", code)) + len(re.findall(r"\bTex\b", code))
    if tex_count > 2:
        warnings.warn(
            f"scene {scene_id}: MathTex/Tex used {tex_count} times — "
            "prefer Text for performance",
            stacklevel=2,
        )

    return code


_codegen_system_cache = None


def _codegen_system() -> str:
    global _codegen_system_cache
    if _codegen_system_cache is None:
        base = (config.PROMPTS_DIR / "codegen_system.md").read_text()
        from prompts.few_shot_scenes import EXAMPLES

        examples = "\n\n".join(
            f"### Example {i}\n\n```python\n{example}```"
            for i, example in enumerate(EXAMPLES, start=1)
        )
        _codegen_system_cache = f"{base}\n\n{examples}"
    return _codegen_system_cache


def generate_scene_code(plan: dict, scene: dict) -> str:
    """Returns Python source for one scene."""
    user_message = (
        "Full video plan (for context and continuity):\n"
        f"{json.dumps(plan, indent=2)}\n\n"
        f"Generate the Manim source for scene {scene['id']} only. "
        f"The class must be named Scene{scene['id']} exactly."
    )
    raw = generate(_codegen_system(), user_message, config.CODEGEN_MODEL)
    code = strip_code_fences(raw)
    return sanitize(code, scene["id"])


def generate_all_scenes(plan: dict) -> dict[int, str]:
    """scene id -> source. Runs concurrently."""
    scenes = plan["scenes"]
    with ThreadPoolExecutor(max_workers=len(scenes)) as executor:
        futures = {
            executor.submit(generate_scene_code, plan, scene): scene["id"]
            for scene in scenes
        }
        return {futures[future]: future.result() for future in futures}
