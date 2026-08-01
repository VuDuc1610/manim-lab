"""Runs the existing pipeline (make_plan -> generate_all_scenes -> render_all ->
stitch) for multiple videos concurrently, without touching pipeline/renderer.py
or pipeline/stitch.py.

Both of those write to fixed, scene-id-only paths (work/scene_{id}.py,
media/videos/scene_{id}/..., work/concat.txt) with no per-video namespacing.
Running two whole-video pipelines' render+stitch steps at the same time would
collide on those paths. _render_disk_lock serializes exactly that portion
across every video; make_plan()/generate_all_scenes() are pure Gemini calls
with no shared disk state, so those stay fully concurrent.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

from pipeline import config
from pipeline.codegen import generate_all_scenes
from pipeline.decode import DecodeError, decode_fund_content
from pipeline.planner import PlanError, make_plan
from pipeline.quick_explain import quick_explain
from pipeline.renderer import RenderError, render_all
from pipeline.stitch import StitchError, stitch
from webapp import jobs

PIPELINE_MAX_WORKERS = 4

_pipeline_pool = ThreadPoolExecutor(max_workers=PIPELINE_MAX_WORKERS)
_render_disk_lock = threading.Lock()


def start_session(session_id: str, fund_content: str) -> None:
    threading.Thread(target=_run_session, args=(session_id, fund_content), daemon=True).start()


def start_followup(video_id: str, topic_prompt: str) -> None:
    _pipeline_pool.submit(_run_video_pipeline, video_id, topic_prompt)
    _pipeline_pool.submit(_run_quick_explain, video_id, topic_prompt)


def _run_session(session_id: str, fund_content: str) -> None:
    jobs.update_session(session_id, decode_status="running")
    try:
        decode = decode_fund_content(fund_content)
    except DecodeError as e:
        jobs.update_session(session_id, decode_status="error", decode_error=str(e))
        return
    except Exception as e:
        jobs.update_session(session_id, decode_status="error", decode_error=f"unexpected error: {e}")
        return

    jobs.attach_decode_result(session_id, decode)
    session = jobs.get_session(session_id)

    base_id = session.video_slots["base"]
    _pipeline_pool.submit(_run_video_pipeline, base_id, decode["base_topic_prompt"])
    _pipeline_pool.submit(_run_quick_explain, base_id, decode["base_topic_prompt"])


def _run_quick_explain(video_id: str, topic_prompt: str) -> None:
    """Runs alongside _run_video_pipeline for the same video, so the frontend
    has something to show while the real video renders. Best-effort only —
    no repair pass, failure just leaves the frontend showing its plain
    spinner instead of a quick-explain card."""
    try:
        result = quick_explain(topic_prompt)
        jobs.update_video(video_id, quick_explain_status="done", quick_explain=result)
    except Exception:
        jobs.update_video(video_id, quick_explain_status="error")


def _run_video_pipeline(video_id: str, topic_prompt: str) -> None:
    try:
        jobs.update_video(video_id, status="planning")
        plan = make_plan(topic_prompt)
        n = len(plan["scenes"])
        jobs.update_video(video_id, title=plan["title"], status="codegen", stage_detail=f"generating {n} scenes")
        sources = generate_all_scenes(plan)

        jobs.update_video(video_id, status="rendering", stage_detail=f"queued for render ({n} scenes)")
        with _render_disk_lock:
            jobs.update_video(video_id, stage_detail=f"rendering {n} scenes")
            # This is a long-lived process, unlike make_video.py's one-shot CLI
            # run — config.py only creates these dirs once at import time, so
            # they need to be re-asserted here in case something (external
            # cleanup, disk issues) removed them since the process started.
            config.WORK_DIR.mkdir(parents=True, exist_ok=True)
            config.OUT_DIR.mkdir(parents=True, exist_ok=True)
            results = render_all(sources, config.DEFAULT_QUALITY, strict=False)
            if not results:
                raise RenderError("all scenes failed to render")

            jobs.update_video(video_id, status="stitching", stage_detail="")
            clips = [results[i] for i in sorted(results)]
            out_path = config.OUT_DIR / f"{video_id}.mp4"
            stitch(clips, out_path)

        jobs.update_video(video_id, status="done", out_path=out_path, stage_detail="")
        jobs.persist_history_entry(video_id)
    except (PlanError, RenderError, StitchError) as e:
        jobs.update_video(video_id, status="error", error=str(e))
    except Exception as e:
        jobs.update_video(video_id, status="error", error=f"unexpected error: {e}")
