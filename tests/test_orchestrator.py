"""Regression test for the render/stitch collision fix: renderer.py and
stitch.py write to fixed, scene-id-only paths with no per-video namespacing,
so orchestrator._run_video_pipeline must serialize the render_all()..stitch()
portion across concurrently-running videos via _render_disk_lock. This test
proves that lock actually holds under real concurrent threads.
"""

import threading
import time
from pathlib import Path

from webapp import history_store, jobs, orchestrator


def _fake_make_plan(topic_prompt):
    return {"title": "Mock", "slug": "mock", "scenes": [{"id": 1}]}


def _fake_generate_all_scenes(plan):
    return {1: "mock source"}


def _make_fake_render_all(events, events_lock, delay):
    def fake_render_all(sources, quality, strict=False):
        start = time.perf_counter()
        time.sleep(delay)
        end = time.perf_counter()
        with events_lock:
            events.append((threading.get_ident(), "render", start, end))
        return {1: Path("fake_scene_1.mp4")}

    return fake_render_all


def _make_fake_stitch(events, events_lock, delay):
    def fake_stitch(clips, out_path):
        start = time.perf_counter()
        time.sleep(delay)
        end = time.perf_counter()
        with events_lock:
            events.append((threading.get_ident(), "stitch", start, end))
        return out_path

    return fake_stitch


def test_render_and_stitch_never_overlap_across_concurrent_videos(monkeypatch, tmp_path):
    events = []
    events_lock = threading.Lock()
    delay = 0.05

    # This test drives the real _run_video_pipeline (not a mocked stand-in)
    # through to a genuine status="done", which now also calls
    # jobs.persist_history_entry — without this, it would write "Mock"-titled
    # test fixtures into the real project-root learning_history.json.
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")
    monkeypatch.setattr(orchestrator, "make_plan", _fake_make_plan)
    monkeypatch.setattr(orchestrator, "generate_all_scenes", _fake_generate_all_scenes)
    monkeypatch.setattr(orchestrator, "render_all", _make_fake_render_all(events, events_lock, delay))
    monkeypatch.setattr(orchestrator, "stitch", _make_fake_stitch(events, events_lock, delay))

    video_ids = [jobs.create_video("base", f"topic {i}").video_id for i in range(4)]

    threads = [
        threading.Thread(target=orchestrator._run_video_pipeline, args=(vid, f"topic for {vid}"))
        for vid in video_ids
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    for vid in video_ids:
        video = jobs.get_video(vid)
        assert video.status == "done", video.error

    by_thread = {}
    for thread_id, kind, start, end in events:
        by_thread.setdefault(thread_id, {})[kind] = (start, end)

    assert len(by_thread) == len(video_ids)

    windows = sorted(
        (kinds["render"][0], kinds["stitch"][1]) for kinds in by_thread.values()
    )
    for (start_a, end_a), (start_b, end_b) in zip(windows, windows[1:]):
        assert end_a <= start_b, "render/stitch windows overlapped across concurrent videos"


def test_run_quick_explain_updates_job_on_success(monkeypatch):
    result = {"headline": "h", "explanation": "e", "key_points": ["a", "b"]}
    monkeypatch.setattr(orchestrator, "quick_explain", lambda topic_prompt: result)

    video = jobs.create_video("base", "topic")
    orchestrator._run_quick_explain(video.video_id, "topic")

    updated = jobs.get_video(video.video_id)
    assert updated.quick_explain_status == "done"
    assert updated.quick_explain == result


def test_run_quick_explain_marks_error_on_failure_without_raising(monkeypatch):
    def fake_quick_explain(topic_prompt):
        raise RuntimeError("boom")

    monkeypatch.setattr(orchestrator, "quick_explain", fake_quick_explain)

    video = jobs.create_video("base", "topic")
    orchestrator._run_quick_explain(video.video_id, "topic")

    updated = jobs.get_video(video.video_id)
    assert updated.quick_explain_status == "error"
    assert updated.quick_explain is None


def test_run_session_marks_decode_error_on_unexpected_exception(monkeypatch):
    """Regression test: decode_fund_content can raise something other than
    DecodeError (e.g. a real Gemini API error like 429/503). Before this fix,
    _run_session only caught DecodeError, so any other exception killed the
    background thread silently and left decode_status stuck at "running"
    forever — every /followup call then 409s indefinitely with no way for
    the user to see why."""

    def fake_decode_fund_content(fund_content):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(orchestrator, "decode_fund_content", fake_decode_fund_content)

    session = jobs.create_session()
    orchestrator._run_session(session.session_id, "some fund content")

    updated = jobs.get_session(session.session_id)
    assert updated.decode_status == "error"
    assert "503 UNAVAILABLE" in updated.decode_error
