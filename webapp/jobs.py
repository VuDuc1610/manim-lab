"""In-memory session/video job store. No DB — single local process, good enough
for a local demo. All mutation goes through the lock-guarded functions below.
"""

import itertools
import threading
from dataclasses import dataclass, field
from pathlib import Path

_lock = threading.Lock()
_sessions: dict[str, "Session"] = {}
_videos: dict[str, "VideoJob"] = {}
_session_counter = itertools.count(1)
_video_counter = itertools.count(1)


@dataclass
class VideoJob:
    video_id: str
    kind: str  # base | suggestion | followup
    topic_prompt: str
    label: str | None = None
    status: str = "queued"  # queued|planning|codegen|rendering|stitching|done|error
    stage_detail: str = ""
    title: str | None = None
    out_path: Path | None = None
    error: str | None = None


@dataclass
class Session:
    session_id: str
    decode_status: str = "pending"  # pending|running|done|error
    decode_error: str | None = None
    fund_name: str | None = None
    base_topic_prompt: str | None = None
    video_slots: dict[str, str] = field(default_factory=dict)  # "base" -> video_id, "suggestion_1" -> video_id, ...


def create_session() -> Session:
    with _lock:
        session_id = f"sess_{next(_session_counter)}"
        session = Session(session_id=session_id)
        _sessions[session_id] = session
        return session


def get_session(session_id: str) -> Session | None:
    with _lock:
        return _sessions.get(session_id)


def update_session(session_id: str, **fields) -> None:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        for key, value in fields.items():
            setattr(session, key, value)


def create_video(kind: str, topic_prompt: str, label: str | None = None) -> VideoJob:
    with _lock:
        video_id = f"vid_{next(_video_counter)}"
        video = VideoJob(video_id=video_id, kind=kind, topic_prompt=topic_prompt, label=label)
        _videos[video_id] = video
        return video


def get_video(video_id: str) -> VideoJob | None:
    with _lock:
        return _videos.get(video_id)


def update_video(video_id: str, **fields) -> None:
    with _lock:
        video = _videos.get(video_id)
        if video is None:
            return
        for key, value in fields.items():
            setattr(video, key, value)


def attach_decode_result(session_id: str, decode: dict) -> None:
    """Creates the base + 3 suggestion VideoJobs and wires them into the session."""
    base_video = create_video("base", decode["base_topic_prompt"])
    slots = {"base": base_video.video_id}
    for i, suggestion in enumerate(decode["suggestions"], start=1):
        video = create_video("suggestion", suggestion["topic_prompt"], label=suggestion["question"])
        slots[f"suggestion_{i}"] = video.video_id

    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        session.fund_name = decode["fund_name"]
        session.base_topic_prompt = decode["base_topic_prompt"]
        session.video_slots = slots
        session.decode_status = "done"


def video_status_dict(video_id: str) -> dict | None:
    video = get_video(video_id)
    if video is None:
        return None
    return {
        "video_id": video.video_id,
        "kind": video.kind,
        "label": video.label,
        "status": video.status,
        "stage_detail": video.stage_detail,
        "title": video.title,
        "video_url": f"/api/videos/{video.video_id}/file" if video.status == "done" else None,
        "error": video.error,
    }


def session_status_dict(session_id: str) -> dict | None:
    session = get_session(session_id)
    if session is None:
        return None
    return {
        "session_id": session.session_id,
        "decode_status": session.decode_status,
        "decode_error": session.decode_error,
        "fund_name": session.fund_name,
        "base_topic_prompt": session.base_topic_prompt,
        "videos": {slot: video_status_dict(vid) for slot, vid in session.video_slots.items()},
    }
