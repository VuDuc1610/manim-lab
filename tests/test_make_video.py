import pytest

import make_video
from pipeline.planner import PlanError
from pipeline.renderer import RenderError
from pipeline.stitch import StitchError


def _plan(n=2, slug="binary_search", title="How Binary Search Works"):
    return {
        "title": title,
        "slug": slug,
        "scenes": [
            {"id": i, "goal": f"goal {i}", "visuals": ["x"], "narration": f"n{i}", "duration_sec": 6}
            for i in range(1, n + 1)
        ],
    }


def _scene_code(scene_id):
    return f"from manim import *\n\n\nclass Scene{scene_id}(Scene):\n    def construct(self):\n        self.wait(1)\n"


class _Recorder:
    def __init__(self):
        self.calls = []


def test_run_calls_stages_in_order_and_returns_out_path(monkeypatch, tmp_path):
    rec = _Recorder()
    plan = _plan(2)

    def fake_make_plan(prompt):
        rec.calls.append(("plan", prompt))
        return plan

    def fake_generate_all_scenes(p):
        rec.calls.append(("codegen", p))
        return {1: _scene_code(1), 2: _scene_code(2)}

    def fake_render_all(sources, quality, strict):
        rec.calls.append(("render", sources, quality, strict))
        return {1: tmp_path / "Scene1.mp4", 2: tmp_path / "Scene2.mp4"}

    def fake_stitch(clips, out_path):
        rec.calls.append(("stitch", clips, out_path))
        return out_path

    monkeypatch.setattr(make_video, "make_plan", fake_make_plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", fake_generate_all_scenes)
    monkeypatch.setattr(make_video, "render_all", fake_render_all)
    monkeypatch.setattr(make_video, "stitch", fake_stitch)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    out_path = make_video.run("explain binary search", quality="qm", keep_work=True)

    assert out_path == tmp_path / "binary_search.mp4"
    assert [c[0] for c in rec.calls] == ["plan", "codegen", "render", "stitch"]
    assert rec.calls[0][1] == "explain binary search"
    assert rec.calls[2][2] == "-qm"
    assert rec.calls[2][3] is False
    assert rec.calls[3][1] == [tmp_path / "Scene1.mp4", tmp_path / "Scene2.mp4"]


def test_run_folds_scenes_hint_into_prompt(monkeypatch, tmp_path):
    plan = _plan(1)
    captured = {}

    def fake_make_plan(prompt):
        captured["prompt"] = prompt
        return plan

    monkeypatch.setattr(make_video, "make_plan", fake_make_plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1)})
    monkeypatch.setattr(make_video, "render_all", lambda sources, quality, strict: {1: tmp_path / "Scene1.mp4"})
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    make_video.run("explain recursion", scenes_hint=3, keep_work=True)

    assert "explain recursion" in captured["prompt"]
    assert "3" in captured["prompt"]


def test_run_sequential_uses_per_scene_functions(monkeypatch, tmp_path):
    plan = _plan(2)
    rec = _Recorder()

    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)

    def fake_generate_scene_code(p, scene):
        rec.calls.append(("codegen_one", scene["id"]))
        return _scene_code(scene["id"])

    def fake_render_scene(code, scene_id, quality):
        rec.calls.append(("render_one", scene_id, quality))
        return tmp_path / f"Scene{scene_id}.mp4"

    def fail_if_called(*a, **kw):
        raise AssertionError("should not call the *_all variant in sequential mode")

    monkeypatch.setattr(make_video, "generate_scene_code", fake_generate_scene_code)
    monkeypatch.setattr(make_video, "render_scene", fake_render_scene)
    monkeypatch.setattr(make_video, "generate_all_scenes", fail_if_called)
    monkeypatch.setattr(make_video, "render_all", fail_if_called)
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    make_video.run("explain binary search", keep_work=True, sequential=True)

    assert ("codegen_one", 1) in rec.calls
    assert ("codegen_one", 2) in rec.calls
    assert ("render_one", 1, "-qm") in rec.calls
    assert ("render_one", 2, "-qm") in rec.calls


def test_run_passes_strict_to_render_all(monkeypatch, tmp_path):
    plan = _plan(1)
    captured = {}

    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1)})

    def fake_render_all(sources, quality, strict):
        captured["strict"] = strict
        return {1: tmp_path / "Scene1.mp4"}

    monkeypatch.setattr(make_video, "render_all", fake_render_all)
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    make_video.run("explain binary search", keep_work=True, strict=True)

    assert captured["strict"] is True


def test_run_raises_render_error_when_all_scenes_fail(monkeypatch, tmp_path):
    plan = _plan(2)

    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1), 2: _scene_code(2)})
    monkeypatch.setattr(make_video, "render_all", lambda sources, quality, strict: {})
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    with pytest.raises(RenderError):
        make_video.run("explain binary search", keep_work=True)


def test_run_prints_timing_report_with_all_stage_names(monkeypatch, tmp_path, capsys):
    plan = _plan(1)

    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1)})
    monkeypatch.setattr(make_video, "render_all", lambda sources, quality, strict: {1: tmp_path / "Scene1.mp4"})
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    make_video.run("explain binary search", keep_work=True)

    out = capsys.readouterr().out
    for stage in ["plan", "codegen", "render", "stitch", "total"]:
        assert stage in out


def test_run_prints_partial_timing_and_reraises_on_early_failure(monkeypatch, tmp_path, capsys):
    def fake_make_plan(prompt):
        raise PlanError("model output was garbage", raw_response="garbage")

    monkeypatch.setattr(make_video, "make_plan", fake_make_plan)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)

    with pytest.raises(PlanError):
        make_video.run("explain binary search", keep_work=True)

    out = capsys.readouterr().out
    assert "total" in out


def test_run_cleans_work_dir_by_default(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "scene_1.py").write_text("leftover")

    plan = _plan(1)
    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1)})
    monkeypatch.setattr(make_video, "render_all", lambda sources, quality, strict: {1: tmp_path / "Scene1.mp4"})
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(make_video.config, "WORK_DIR", work_dir)

    make_video.run("explain binary search", keep_work=False)

    assert not (work_dir / "scene_1.py").exists()


def test_run_keeps_work_dir_when_keep_work_true(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "scene_1.py").write_text("leftover")

    plan = _plan(1)
    monkeypatch.setattr(make_video, "make_plan", lambda prompt: plan)
    monkeypatch.setattr(make_video, "generate_all_scenes", lambda p: {1: _scene_code(1)})
    monkeypatch.setattr(make_video, "render_all", lambda sources, quality, strict: {1: tmp_path / "Scene1.mp4"})
    monkeypatch.setattr(make_video, "stitch", lambda clips, out_path: out_path)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(make_video.config, "WORK_DIR", work_dir)

    make_video.run("explain binary search", keep_work=True)

    assert (work_dir / "scene_1.py").exists()


def test_run_cleans_work_dir_even_on_failure(monkeypatch, tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "scene_1.py").write_text("leftover")

    def fake_make_plan(prompt):
        raise PlanError("model output was garbage", raw_response="garbage")

    monkeypatch.setattr(make_video, "make_plan", fake_make_plan)
    monkeypatch.setattr(make_video.config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(make_video.config, "WORK_DIR", work_dir)

    with pytest.raises(PlanError):
        make_video.run("explain binary search", keep_work=False)

    assert not (work_dir / "scene_1.py").exists()


def test_parse_args_maps_cli_flags():
    args = make_video.parse_args(
        ["explain recursion", "--quality", "qh", "--scenes", "3", "--keep-work", "--strict", "--sequential"]
    )
    assert args.prompt == "explain recursion"
    assert args.quality == "qh"
    assert args.scenes_hint == 3
    assert args.keep_work is True
    assert args.strict is True
    assert args.sequential is True


def test_parse_args_defaults():
    args = make_video.parse_args(["explain binary search"])
    assert args.quality == "qm"
    assert args.scenes_hint is None
    assert args.keep_work is False
    assert args.strict is False
    assert args.sequential is False


def test_main_exits_with_code_1_on_render_error(monkeypatch, capsys):
    def fake_run(*a, **kw):
        raise RenderError("boom")

    monkeypatch.setattr(make_video, "run", fake_run)

    with pytest.raises(SystemExit) as excinfo:
        make_video.main(["explain binary search"])

    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "boom" in err


def test_main_exits_with_code_1_on_plan_error(monkeypatch, capsys):
    def fake_run(*a, **kw):
        raise PlanError("bad plan", raw_response="junk")

    monkeypatch.setattr(make_video, "run", fake_run)

    with pytest.raises(SystemExit) as excinfo:
        make_video.main(["explain binary search"])

    assert excinfo.value.code == 1


def test_main_exits_with_code_1_on_stitch_error(monkeypatch, capsys):
    def fake_run(*a, **kw):
        raise StitchError("ffmpeg exploded")

    monkeypatch.setattr(make_video, "run", fake_run)

    with pytest.raises(SystemExit) as excinfo:
        make_video.main(["explain binary search"])

    assert excinfo.value.code == 1


def test_main_prints_out_path_on_success(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(make_video, "run", lambda *a, **kw: tmp_path / "binary_search.mp4")

    make_video.main(["explain binary search"])

    out = capsys.readouterr().out
    assert "binary_search.mp4" in out
