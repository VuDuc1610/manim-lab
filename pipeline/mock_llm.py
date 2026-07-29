"""Canned stand-in for pipeline.llm.generate, used when MOCK_LLM is set.

Produces output that satisfies the same contracts real Gemini responses have
to meet (planner.validate_plan, codegen.sanitize), so the rest of the
pipeline — codegen, Docker render, ffmpeg stitch — runs unmodified against
real output shapes without spending API quota.

Optional env vars inject failure modes to exercise retry/repair paths that
a normal successful run never touches:

  MOCK_LLM_FAIL_PLAN=1           first planner response is invalid JSON,
                                  forcing planner.py's one repair pass.
  MOCK_LLM_FAIL_RENDER=2,4       those scene ids render-fail once, then the
                                  repair call returns working code (tests the
                                  render-fail -> repair -> success path).
  MOCK_LLM_ALWAYS_FAIL_RENDER=5  those scene ids never recover, exhausting
                                  MAX_RENDER_ATTEMPTS (tests the drop /
                                  --strict path).
  MOCK_LLM_FAIL_DECODE=1         first decode response is invalid JSON,
                                  forcing decode.py's one repair pass.

The SCHD demo's 4 topics (base + 3 suggestions) are hand-written real content
(pipeline/schd_content.py), not generic filler — detected via the topic
prompt / embedded plan slug, so the demo shows real, good-quality Docker
renders instead of placeholder templates while still spending zero Gemini
quota.
"""

import json
import os
import re

from pipeline.schd_content import PLANS as _SCHD_PLANS
from pipeline.schd_content import SCENES as _SCHD_SCENES
from pipeline.schd_content import (
    SCHD_BASE_TOPIC_PROMPT,
    SCHD_HIGHER_FEE_TOPIC_PROMPT,
    SCHD_REINVEST_TOPIC_PROMPT,
    SCHD_START_EARLIER_TOPIC_PROMPT,
)
from pipeline.schd_content import TOPIC_PROMPTS as _SCHD_TOPIC_PROMPTS

_SCENE_ID_RE = re.compile(r"[Ss]cene ?(\d+)(?: only| failed to render)")
_SCHD_SLUG_MARKER_RE = re.compile(r"SCHD_SLUG: (\S+)")

# Set by the initial (non-repair) planner call so the repair call — which
# only sees the previous bad response, not the original prompt — can still
# produce a plan about the right topic.
_last_topic = "mock topic"
_last_n_scenes = 3


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "mock_video"


def _env_ids(name: str) -> set[int]:
    raw = os.environ.get(name, "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


_INVALID_PLAN_JSON = '{"title": "", "slug": "bad slug!", "scenes": []}'


def _mock_plan(user_prompt: str) -> str:
    global _last_topic, _last_n_scenes

    is_repair = "failed validation with these problems" in user_prompt
    if not is_repair:
        for slug, topic_prompt in _SCHD_TOPIC_PROMPTS.items():
            if user_prompt.strip() == topic_prompt.strip():
                return json.dumps(_SCHD_PLANS[slug])

        hint = re.search(r"aim for about (\d+) scenes", user_prompt)
        _last_n_scenes = max(3, min(6, int(hint.group(1)))) if hint else 3
        _last_topic = re.sub(r"\s*\(aim for about \d+ scenes\)", "", user_prompt).strip()

        if os.environ.get("MOCK_LLM_FAIL_PLAN"):
            return _INVALID_PLAN_JSON

    scenes = [
        {
            "id": i,
            "goal": f"Mock goal {i} for: {_last_topic}",
            "visuals": [f"mock shape {i}a", f"mock shape {i}b"],
            "narration": f"Mock narration {i} about {_last_topic}.",
            "duration_sec": 6,
        }
        for i in range(1, _last_n_scenes + 1)
    ]
    plan = {
        "title": f"Mock: {_last_topic}"[:60],
        "slug": _slugify(_last_topic),
        "scenes": scenes,
    }
    return json.dumps(plan)


def _template_intro(scene_id: int) -> str:
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        title = Text("Mock Scene {scene_id}: Introduction", font_size=40)
        subtitle = Text("Rotating mock template", font_size=24, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.4)
        self.play(Write(title))
        self.play(FadeIn(subtitle))
        self.wait(1)
'''


def _template_shapes(scene_id: int) -> str:
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        values = [4, 9, 15, 22, 30]
        squares = VGroup(*[Square(side_length=0.8) for _ in values])
        squares.arrange(RIGHT, buff=0.15)
        labels = VGroup(*[
            Text(str(v), font_size=24).move_to(sq)
            for v, sq in zip(values, squares)
        ])
        self.play(FadeIn(squares), FadeIn(labels))
        self.wait(1)
        self.play(squares.animate.shift(UP * 0.5), labels.animate.shift(UP * 0.5))
        self.wait(1)
'''


def _template_axes(scene_id: int) -> str:
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3, 1], y_range=[-1, 9, 2], x_length=6, y_length=4)
        curve = axes.plot(lambda x: x ** 2, color=BLUE)
        self.play(FadeIn(axes), Create(curve))
        self.wait(1)
'''


def _template_math(scene_id: int) -> str:
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        formula = MathTex(r"f(x) = x^2")
        derivative = MathTex(r"f'(x) = 2x").next_to(formula, DOWN, buff=0.5)
        self.play(Write(formula))
        self.play(Write(derivative))
        self.wait(1)
'''


def _template_transform(scene_id: int) -> str:
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        square = Square(color=YELLOW)
        self.play(Create(circle))
        self.play(Transform(circle, square))
        self.wait(1)
'''


_TEMPLATES = [
    _template_intro,
    _template_shapes,
    _template_axes,
    _template_math,
    _template_transform,
]


def _mock_scene_code(scene_id: int) -> str:
    template = _TEMPLATES[(scene_id - 1) % len(_TEMPLATES)]
    return template(scene_id)


_INVALID_DECODE_JSON = '{"fund_name": "", "base_topic_prompt": "", "suggestions": []}'


def _mock_decode(user_prompt: str) -> str:
    is_repair = "failed validation with these problems" in user_prompt
    if not is_repair and os.environ.get("MOCK_LLM_FAIL_DECODE"):
        return _INVALID_DECODE_JSON

    decode = {
        "fund_name": "Schwab U.S. Dividend Equity ETF (SCHD)",
        "base_topic_prompt": SCHD_BASE_TOPIC_PROMPT,
        "suggestions": [
            {
                "id": "higher_expense_ratio",
                "question": "What if the fee were 0.75% instead of 0.06%?",
                "topic_prompt": SCHD_HIGHER_FEE_TOPIC_PROMPT,
            },
            {
                "id": "reinvested_dividends",
                "question": "What if you reinvested every dividend?",
                "topic_prompt": SCHD_REINVEST_TOPIC_PROMPT,
            },
            {
                "id": "started_five_years_earlier",
                "question": "What if you'd started investing 5 years earlier?",
                "topic_prompt": SCHD_START_EARLIER_TOPIC_PROMPT,
            },
        ],
    }
    return json.dumps(decode)


def _mock_broken_scene(scene_id: int) -> str:
    """Passes sanitize() but throws inside Docker at render time."""
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        self.play(Write(this_name_does_not_exist))
        self.wait(1)
'''


def _lookup_schd_scene(user: str, scene_id: int) -> str | None:
    for slug in _SCHD_PLANS:
        if slug in user:
            return _SCHD_SCENES.get((slug, scene_id))

    marker = _SCHD_SLUG_MARKER_RE.search(user)
    if marker:
        return _SCHD_SCENES.get((marker.group(1), scene_id))

    return None


def generate(system: str, user: str, model: str) -> str:
    is_codegen = "Generate the Manim source for scene" in user
    is_render_repair = "failed to render" in user
    is_decode = "Fund page content:" in user

    if is_codegen or is_render_repair:
        match = _SCENE_ID_RE.search(user)
        scene_id = int(match.group(1)) if match else 1

        schd_scene = _lookup_schd_scene(user, scene_id)
        if schd_scene:
            return schd_scene

        if scene_id in _env_ids("MOCK_LLM_ALWAYS_FAIL_RENDER"):
            return _mock_broken_scene(scene_id)
        if scene_id in _env_ids("MOCK_LLM_FAIL_RENDER") and is_codegen:
            return _mock_broken_scene(scene_id)

        return _mock_scene_code(scene_id)

    if is_decode:
        return _mock_decode(user)

    return _mock_plan(user)
