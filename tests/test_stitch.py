from pathlib import Path

import pytest

from pipeline import config, stitch


class _FakeCompletedProcess:
    def __init__(self, returncode, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def _clip(scene_id):
    return config.PROJECT_ROOT / "media" / "videos" / f"scene_{scene_id}" / "480p15" / f"Scene{scene_id}.mp4"


def test_stitch_writes_concat_file_with_absolute_host_paths_in_order(monkeypatch):
    monkeypatch.setattr(stitch.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))

    clips = [_clip(1), _clip(2), _clip(3)]
    out_path = config.OUT_DIR / "test_video.mp4"

    stitch.stitch(clips, out_path)

    concat_content = (config.WORK_DIR / "concat.txt").read_text()
    lines = concat_content.strip().splitlines()
    assert lines == [f"file '{clip.resolve()}'" for clip in clips]


def test_stitch_calls_host_ffmpeg_with_copy_codec_first(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(stitch.subprocess, "run", fake_run)

    clips = [_clip(1)]
    out_path = config.OUT_DIR / "test_video.mp4"
    stitch.stitch(clips, out_path)

    args = captured["args"]
    assert args[0] == "ffmpeg"
    assert "-f" in args and "concat" in args
    assert "-safe" in args and "0" in args
    assert "-i" in args and str(config.WORK_DIR / "concat.txt") in args
    assert "-c" in args and "copy" in args
    assert str(out_path) in args
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True


def test_stitch_returns_out_path_on_success(monkeypatch):
    monkeypatch.setattr(stitch.subprocess, "run", lambda *a, **kw: _FakeCompletedProcess(0))

    out_path = config.OUT_DIR / "test_video.mp4"
    result = stitch.stitch([_clip(1)], out_path)

    assert result == out_path


def test_stitch_falls_back_to_reencode_when_copy_fails(monkeypatch, capsys):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return _FakeCompletedProcess(1, stderr="codec mismatch\n")
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(stitch.subprocess, "run", fake_run)

    out_path = config.OUT_DIR / "test_video.mp4"
    result = stitch.stitch([_clip(1), _clip(2)], out_path)

    assert result == out_path
    assert len(calls) == 2
    assert "-c" in calls[0] and "copy" in calls[0]
    second_args = calls[1]
    assert "-c:v" in second_args and "libx264" in second_args
    assert "-pix_fmt" in second_args and "yuv420p" in second_args
    assert str(out_path) in second_args

    err = capsys.readouterr().err
    assert "re-encode" in err.lower()


def test_stitch_raises_stitch_error_when_both_attempts_fail(monkeypatch):
    def fake_run(args, **kwargs):
        return _FakeCompletedProcess(1, stderr="ffmpeg exploded\n")

    monkeypatch.setattr(stitch.subprocess, "run", fake_run)

    with pytest.raises(stitch.StitchError):
        stitch.stitch([_clip(1)], config.OUT_DIR / "test_video.mp4")
