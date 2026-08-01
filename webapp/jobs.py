"""In-memory session/video job store. No DB — single local process, good enough
for a local demo. All mutation goes through the lock-guarded functions below.
"""

import itertools
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import config
from webapp import history_store

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
    quick_explain_status: str = "pending"  # pending|done|error
    quick_explain: dict | None = None  # {headline, explanation, key_points}


@dataclass
class Session:
    session_id: str
    decode_status: str = "pending"  # pending|running|done|error
    decode_error: str | None = None
    fund_name: str | None = None
    base_topic_prompt: str | None = None
    suggestions: list[dict] = field(default_factory=list)  # [{id, question, topic_prompt}]
    followups: list[dict] = field(default_factory=list)  # [{video_id, question}], append-only, ask order
    video_slots: dict[str, str] = field(default_factory=dict)  # "base" -> video_id, "suggestion_<id>" -> video_id


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


def rehydrate_from_history() -> None:
    """Restores completed videos from the on-disk history store into the
    in-memory _videos dict, and seeds _video_counter past the highest
    persisted id so freshly-created videos never collide with a rehydrated
    video_id. Called once by server.py at real startup — deliberately NOT
    called at module import time, so pytest runs stay hermetic (fully
    mocked, no dependency on whatever's in the real learning_history.json
    on disk) rather than picking up ambient state every test run."""
    global _video_counter
    max_num = 0
    for entry in history_store.load_all():
        video_id = entry["video_id"]
        _videos[video_id] = VideoJob(
            video_id=video_id,
            kind=entry["kind"],
            topic_prompt="",
            label=entry.get("label"),
            status="done",
            title=entry.get("title"),
            out_path=config.OUT_DIR / f"{video_id}.mp4",
            quick_explain_status="done" if entry.get("quick_explain") else "error",
            quick_explain=entry.get("quick_explain"),
        )
        max_num = max(max_num, int(video_id.rsplit("_", 1)[1]))
    _video_counter = itertools.count(max_num + 1)


def persist_history_entry(video_id: str) -> None:
    """Called once a video finishes successfully — writes it to the on-disk
    history store so it still shows up in Learning after a server restart
    (the in-memory _videos/_sessions dicts here don't survive one)."""
    video = get_video(video_id)
    if video is None or video.status != "done":
        return
    history_store.append(
        {
            "video_id": video.video_id,
            "kind": video.kind,
            "label": video.label,
            "title": video.title,
            "quick_explain": video.quick_explain,
        }
    )


def history_entries() -> list[dict]:
    """All persisted (already-completed) videos, regardless of which session
    generated them — sessions themselves don't survive a restart, but their
    finished videos do."""
    return [
        {"video_id": e["video_id"], "label": e.get("label") or e.get("title") or "Untitled"}
        for e in history_store.load_all()
    ]


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
    """Creates the base VideoJob and stores the 3 suggestion prompts. Suggestion
    videos are created on demand via trigger_suggestion(), not here."""
    base_video = create_video("base", decode["base_topic_prompt"])

    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        session.fund_name = decode["fund_name"]
        session.base_topic_prompt = decode["base_topic_prompt"]
        session.suggestions = decode["suggestions"]
        session.video_slots = {"base": base_video.video_id}
        session.decode_status = "done"


def trigger_suggestion(session_id: str, suggestion_id: str) -> tuple[VideoJob | None, bool]:
    """Returns (video, created). created=False means it was already triggered
    (idempotent re-click) or suggestion_id/session_id doesn't exist (video is None)."""
    slot = f"suggestion_{suggestion_id}"
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None, False
        existing_video_id = session.video_slots.get(slot)
        if existing_video_id is not None:
            return _videos.get(existing_video_id), False
        suggestion = next((s for s in session.suggestions if s["id"] == suggestion_id), None)
        if suggestion is None:
            return None, False

    video = create_video("suggestion", suggestion["topic_prompt"], label=suggestion["question"])
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None, False
        session.video_slots[slot] = video.video_id
    return video, True


def record_followup(session_id: str, video_id: str, question: str) -> None:
    """Appends a followup video to the session's followup list, in ask order.
    Unlike trigger_suggestion there's no idempotency key: every /followup
    call is a brand-new question and always gets its own entry."""
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return
        session.followups.append({"video_id": video_id, "question": question})


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
        "quick_explain_status": video.quick_explain_status,
        "quick_explain": video.quick_explain,
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
        "suggestions": [
            {
                "id": s["id"],
                "question": s["question"],
                "video_id": session.video_slots.get(f"suggestion_{s['id']}"),
            }
            for s in session.suggestions
        ],
        "followups": [
            {"video_id": f["video_id"], "question": f["question"]}
            for f in session.followups
        ],
    }
