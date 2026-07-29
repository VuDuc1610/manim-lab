import subprocess
import time
from pathlib import Path

import pytest

from pipeline import config, renderer
from pipeline.renderer import RenderError


class _FakeCompletedProcess:
    def __init__(self, returncode, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def _scene_code(scene_id, body="        self.wait(1)"):
    return f'''from manim import *


class Scene{scene_id}(Scene):
    def construct(self):
{body}
'''


def test_render_scene_returns_path_on_first_success(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / f"Scene{scene_id}.mp4")

    result = renderer.render_scene(_scene_code(1), 1, "-qm")

    assert result == tmp_path / "Scene1.mp4"


def test_render_scene_calls_docker_with_expected_args(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    renderer.render_scene(_scene_code(1), 1, "-qm")

    args = captured["args"]
    assert args[0:3] == ["docker", "run", "--rm"]
    assert "-v" in args
    assert f"{config.PROJECT_ROOT}:/manim" in args
    assert "manimcommunity/manim" in args
    assert "-qm" in args
    assert "work/scene_1.py" in args
    assert "Scene1" in args
    assert "-p" not in args
    assert "--disable_caching" not in args
    assert captured["kwargs"]["timeout"] == config.RENDER_TIMEOUT_SEC
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_render_scene_writes_source_to_work_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene7.mp4")

    code = _scene_code(7)
    renderer.render_scene(code, 7, "-qm")

    written = config.WORK_DIR / "scene_7.py"
    assert written.read_text() == code


def test_render_scene_repairs_after_failure_then_succeeds(monkeypatch, tmp_path):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] == 1:
            return _FakeCompletedProcess(1, stderr="NameError: name 'Arrow3D' is not defined\n")
        return _FakeCompletedProcess(0)

    gen_calls = {"n": 0}

    def fake_generate(system, user, model):
        gen_calls["n"] += 1
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    result = renderer.render_scene(_scene_code(1, "        self.undefined_thing()"), 1, "-qm")

    assert result == tmp_path / "Scene1.mp4"
    assert run_calls["n"] == 2
    assert gen_calls["n"] == 1


def test_render_scene_repair_message_uses_last_30_lines_of_stderr(monkeypatch, tmp_path):
    long_stderr = "\n".join(f"line {i}" for i in range(1, 61))

    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] == 1:
            return _FakeCompletedProcess(1, stderr=long_stderr)
        return _FakeCompletedProcess(0)

    captured = {}

    def fake_generate(system, user, model):
        captured["user"] = user
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    renderer.render_scene(_scene_code(1), 1, "-qm")

    assert "line 31" in captured["user"]
    assert "line 60" in captured["user"]
    assert "line 30" not in captured["user"]
    assert "line 1\n" not in captured["user"]


def test_render_scene_treats_timeout_as_render_failure(monkeypatch, tmp_path):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="manim", timeout=config.RENDER_TIMEOUT_SEC)
        return _FakeCompletedProcess(0)

    captured = {}

    def fake_generate(system, user, model):
        captured["user"] = user
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    renderer.render_scene(_scene_code(1), 1, "-qm")

    assert f"exceeded {config.RENDER_TIMEOUT_SEC}s" in captured["user"]


def test_render_scene_raises_render_error_after_max_attempts(monkeypatch):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        return _FakeCompletedProcess(1, stderr="SyntaxError: invalid syntax\n")

    gen_calls = {"n": 0}

    def fake_generate(system, user, model):
        gen_calls["n"] += 1
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)

    with pytest.raises(RenderError):
        renderer.render_scene(_scene_code(1), 1, "-qm")

    assert run_calls["n"] == config.MAX_RENDER_ATTEMPTS
    assert gen_calls["n"] == config.MAX_RENDER_ATTEMPTS - 1


def test_render_scene_logs_attempt_with_error_summary(monkeypatch, tmp_path, capsys):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] == 1:
            return _FakeCompletedProcess(
                1, stderr="Traceback (most recent call last):\nNameError: name 'Arrow3D' is not defined\n"
            )
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", lambda s, u, m: _scene_code(1))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    renderer.render_scene(_scene_code(1), 1, "-qm")

    err = capsys.readouterr().err
    assert f"[scene 1] attempt 1/{config.MAX_RENDER_ATTEMPTS}" in err
    assert "NameError: name 'Arrow3D' is not defined" in err


def test_render_scene_retries_when_repair_output_fails_sanitize(monkeypatch, tmp_path):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] < 3:
            return _FakeCompletedProcess(1, stderr="boom\n")
        return _FakeCompletedProcess(0)

    gen_calls = {"n": 0}

    def fake_generate(system, user, model):
        gen_calls["n"] += 1
        if gen_calls["n"] == 1:
            return "class SceneWrong(Scene):\n    def construct(self):\n        pass\n"
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    result = renderer.render_scene(_scene_code(1), 1, "-qm")

    assert result == tmp_path / "Scene1.mp4"
    assert run_calls["n"] == 3
    assert gen_calls["n"] == 2


def test_render_scene_retries_when_repair_call_raises(monkeypatch, tmp_path):
    run_calls = {"n": 0}

    def fake_run(*a, **kw):
        run_calls["n"] += 1
        if run_calls["n"] < 3:
            return _FakeCompletedProcess(1, stderr="boom\n")
        return _FakeCompletedProcess(0)

    gen_calls = {"n": 0}

    def fake_generate(system, user, model):
        gen_calls["n"] += 1
        if gen_calls["n"] == 1:
            raise RuntimeError("simulated API outage")
        return _scene_code(1)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", fake_generate)
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: tmp_path / "Scene1.mp4")

    result = renderer.render_scene(_scene_code(1), 1, "-qm")

    assert result == tmp_path / "Scene1.mp4"
    assert run_calls["n"] == 3
    assert gen_calls["n"] == 2


def test_render_all_maps_scene_id_to_path(monkeypatch):
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: Path(f"/tmp/Scene{scene_id}.mp4"))

    sources = {i: _scene_code(i) for i in range(1, 4)}
    result = renderer.render_all(sources, "-qm")

    assert result == {i: Path(f"/tmp/Scene{i}.mp4") for i in range(1, 4)}


def test_render_all_caps_workers_at_four(monkeypatch):
    captured = {}
    real_executor = renderer.ThreadPoolExecutor

    class SpyExecutor(real_executor):
        def __init__(self, max_workers=None, *a, **kw):
            captured["max_workers"] = max_workers
            super().__init__(max_workers=max_workers, *a, **kw)

    monkeypatch.setattr(renderer, "ThreadPoolExecutor", SpyExecutor)
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: Path(f"/tmp/Scene{scene_id}.mp4"))

    sources = {i: _scene_code(i) for i in range(1, 6)}
    renderer.render_all(sources, "-qm")

    assert captured["max_workers"] == 4


def test_render_all_runs_concurrently(monkeypatch):
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: Path(f"/tmp/Scene{scene_id}.mp4"))

    def fake_run(*a, **kw):
        time.sleep(0.15)
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    sources = {i: _scene_code(i) for i in range(1, 5)}

    start = time.perf_counter()
    result = renderer.render_all(sources, "-qm")
    elapsed = time.perf_counter() - start

    assert set(result.keys()) == {1, 2, 3, 4}
    assert elapsed < 0.3, f"expected near-parallel timing, took {elapsed:.2f}s"


def test_render_all_drops_failed_scene_by_default(monkeypatch):
    def fake_run(args, **kw):
        if "work/scene_2.py" in args:
            return _FakeCompletedProcess(1, stderr="boom\n")
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", lambda s, u, m: _scene_code(2))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: Path(f"/tmp/Scene{scene_id}.mp4"))

    sources = {1: _scene_code(1), 2: _scene_code(2), 3: _scene_code(3)}
    result = renderer.render_all(sources, "-qm")

    assert set(result.keys()) == {1, 3}


def test_render_all_strict_raises_on_any_failure(monkeypatch):
    def fake_run(args, **kw):
        if "work/scene_2.py" in args:
            return _FakeCompletedProcess(1, stderr="boom\n")
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    monkeypatch.setattr(renderer, "generate", lambda s, u, m: _scene_code(2))
    monkeypatch.setattr(renderer, "_locate_output", lambda scene_id: Path(f"/tmp/Scene{scene_id}.mp4"))

    sources = {1: _scene_code(1), 2: _scene_code(2), 3: _scene_code(3)}

    with pytest.raises(RenderError):
        renderer.render_all(sources, "-qm", strict=True)
