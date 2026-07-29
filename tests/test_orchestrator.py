"""Regression test for the render/stitch collision fix: renderer.py and
stitch.py write to fixed, scene-id-only paths with no per-video namespacing,
so orchestrator._run_video_pipeline must serialize the render_all()..stitch()
portion across concurrently-running videos via _render_disk_lock. This test
proves that lock actually holds under real concurrent threads.
"""

import threading
import time
from pathlib import Path

from webapp import jobs, orchestrator


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


def test_render_and_stitch_never_overlap_across_concurrent_videos(monkeypatch):
    events = []
    events_lock = threading.Lock()
    delay = 0.05

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
