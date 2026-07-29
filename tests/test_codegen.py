import re
import time

import pytest

from pipeline import codegen
from pipeline.codegen import SanitizeError, generate_all_scenes, generate_scene_code, sanitize
from prompts.few_shot_scenes import EXAMPLES

VALID_SCENE_1 = '''from manim import *


class Scene1(Scene):
    def construct(self):
        title = Text("Binary Search", font_size=44)
        self.play(Write(title))
        self.wait(1)
'''


def test_sanitize_returns_valid_code_unchanged():
    assert sanitize(VALID_SCENE_1, 1) == VALID_SCENE_1


def test_sanitize_raises_when_class_name_does_not_match_scene_id():
    with pytest.raises(SanitizeError):
        sanitize(VALID_SCENE_1, 2)


def test_sanitize_raises_on_extra_import():
    code = "import os\n" + VALID_SCENE_1
    with pytest.raises(SanitizeError):
        sanitize(code, 1)


@pytest.mark.parametrize(
    "token",
    ["subprocess", "eval(", "exec(", "__import__", "open(", "socket", "requests"],
)
def test_sanitize_raises_on_forbidden_token(token):
    code = VALID_SCENE_1.replace(
        'title = Text("Binary Search", font_size=44)',
        f'title = Text("Binary Search", font_size=44)  # {token}',
    )
    with pytest.raises(SanitizeError):
        sanitize(code, 1)


def test_sanitize_warns_when_mathtex_used_more_than_twice():
    code = '''from manim import *


class Scene1(Scene):
    def construct(self):
        a = MathTex("x^2")
        b = MathTex("y^2")
        c = MathTex("z^2")
        self.play(Write(a), Write(b), Write(c))
        self.wait(1)
'''
    with pytest.warns(UserWarning):
        sanitize(code, 1)


@pytest.mark.parametrize("scene_id, example", list(enumerate(EXAMPLES, start=1)))
def test_few_shot_examples_pass_sanitize(scene_id, example):
    assert sanitize(example, scene_id) == example


def test_sanitize_does_not_warn_when_mathtex_used_twice_or_fewer():
    code = '''from manim import *


class Scene1(Scene):
    def construct(self):
        a = MathTex("x^2")
        b = MathTex("y^2")
        self.play(Write(a), Write(b))
        self.wait(1)
'''
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sanitize(code, 1)


def _plan_with_n_scenes(n):
    return {
        "title": "How Binary Search Works",
        "slug": "binary_search",
        "scenes": [
            {
                "id": i,
                "goal": f"goal for scene {i}",
                "visuals": ["a square"],
                "narration": f"narration for scene {i}",
                "duration_sec": 6,
            }
            for i in range(1, n + 1)
        ],
    }


def _fake_generate(delay=0.0):
    calls = []

    def fake(system, user, model):
        calls.append({"system": system, "user": user, "model": model})
        if delay:
            time.sleep(delay)
        scene_id = re.search(r"scene (\d+) only", user).group(1)
        return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
        self.wait(1)
'''

    fake.calls = calls
    return fake


def test_generate_scene_code_includes_whole_plan_and_target_scene(monkeypatch):
    plan = _plan_with_n_scenes(2)
    fake = _fake_generate()
    monkeypatch.setattr(codegen, "generate", fake)

    code = generate_scene_code(plan, plan["scenes"][0])

    assert "class Scene1(Scene):" in code
    user_message = fake.calls[0]["user"]
    assert plan["title"] in user_message
    assert "goal for scene 2" in user_message
    assert "scene 1 only" in user_message


def test_generate_scene_code_strips_code_fences(monkeypatch):
    plan = _plan_with_n_scenes(1)

    def fenced_fake(system, user, model):
        return "```python\nfrom manim import *\n\n\nclass Scene1(Scene):\n    def construct(self):\n        self.wait(1)\n```"

    monkeypatch.setattr(codegen, "generate", fenced_fake)

    code = generate_scene_code(plan, plan["scenes"][0])

    assert not code.startswith("```")
    assert "class Scene1(Scene):" in code


def test_generate_scene_code_raises_sanitize_error_on_wrong_class_name(monkeypatch):
    plan = _plan_with_n_scenes(1)

    def bad_fake(system, user, model):
        return "from manim import *\n\n\nclass SceneX(Scene):\n    def construct(self):\n        self.wait(1)\n"

    monkeypatch.setattr(codegen, "generate", bad_fake)

    with pytest.raises(SanitizeError):
        generate_scene_code(plan, plan["scenes"][0])


def test_generate_all_scenes_maps_scene_id_to_source(monkeypatch):
    plan = _plan_with_n_scenes(4)
    fake = _fake_generate()
    monkeypatch.setattr(codegen, "generate", fake)

    result = generate_all_scenes(plan)

    assert set(result.keys()) == {1, 2, 3, 4}
    for scene_id, code in result.items():
        assert f"class Scene{scene_id}(Scene):" in code


def test_generate_all_scenes_runs_concurrently(monkeypatch):
    plan = _plan_with_n_scenes(4)
    fake = _fake_generate(delay=0.2)
    monkeypatch.setattr(codegen, "generate", fake)

    start = time.perf_counter()
    generate_all_scenes(plan)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.4, f"expected roughly one scene's delay, took {elapsed:.2f}s"
