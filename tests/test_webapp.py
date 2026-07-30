import pytest

from webapp import jobs, orchestrator
from webapp.app import create_app


def _decode_result():
    return {
        "fund_name": "Mock Fund",
        "base_topic_prompt": "Explain mock fund.",
        "suggestions": [
            {"id": "a", "question": "What if A?", "topic_prompt": "Explain A."},
            {"id": "b", "question": "What if B?", "topic_prompt": "Explain B."},
            {"id": "c", "question": "What if C?", "topic_prompt": "Explain C."},
        ],
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(orchestrator, "start_session", lambda session_id, fund_content: None)
    monkeypatch.setattr(orchestrator, "start_followup", lambda video_id, topic_prompt: None)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_create_session_requires_fund_content(client):
    resp = client.post("/api/sessions", json={})
    assert resp.status_code == 400


def test_create_session_rejects_blank_fund_content(client):
    resp = client.post("/api/sessions", json={"fund_content": "   "})
    assert resp.status_code == 400


def test_create_session_success(client):
    resp = client.post("/api/sessions", json={"fund_content": "SCHD expense ratio 0.06%"})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "decoding"
    assert data["session_id"].startswith("sess_")


def test_get_session_status_404_for_unknown_session(client):
    resp = client.get("/api/sessions/sess_does_not_exist")
    assert resp.status_code == 404


def test_get_session_status_full_shape(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]

    resp = client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_id"] == session_id
    assert data["decode_status"] == "pending"
    assert data["videos"] == {}

    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.get(f"/api/sessions/{session_id}")
    data = resp.get_json()
    assert data["decode_status"] == "done"
    assert data["fund_name"] == "Mock Fund"
    assert set(data["videos"].keys()) == {"base"}
    assert data["videos"]["base"]["status"] == "queued"
    assert data["videos"]["base"]["video_url"] is None
    assert [s["id"] for s in data["suggestions"]] == ["a", "b", "c"]
    assert data["suggestions"][0] == {"id": "a", "question": "What if A?", "video_id": None}


def test_followup_404_for_unknown_session(client):
    resp = client.post("/api/sessions/sess_nope/followup", json={"question": "what if?"})
    assert resp.status_code == 404


def test_followup_409_when_session_not_ready(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]

    resp = client.post(f"/api/sessions/{session_id}/followup", json={"question": "what if?"})
    assert resp.status_code == 409


def test_followup_400_for_missing_question(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/followup", json={})
    assert resp.status_code == 400


def test_followup_success(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/followup", json={"question": "what about fees?"})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "queued"
    assert data["video_id"].startswith("vid_")

    video = jobs.get_video(data["video_id"])
    assert video.kind == "followup"
    assert video.label == "what about fees?"
    assert "what about fees?" in video.topic_prompt


def test_video_status_404_for_unknown_video(client):
    resp = client.get("/api/videos/vid_does_not_exist/status")
    assert resp.status_code == 404


def test_video_status_success(client):
    video = jobs.create_video("base", "explain mock fund")
    resp = client.get(f"/api/videos/{video.video_id}/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["video_id"] == video.video_id
    assert data["status"] == "queued"


def test_video_file_404_for_unknown_video(client):
    resp = client.get("/api/videos/vid_does_not_exist/file")
    assert resp.status_code == 404


def test_video_file_409_when_not_ready(client):
    video = jobs.create_video("base", "explain mock fund")
    resp = client.get(f"/api/videos/{video.video_id}/file")
    assert resp.status_code == 409


def test_video_file_success(client, tmp_path):
    video_file = tmp_path / "out.mp4"
    video_file.write_bytes(b"fake mp4 bytes")

    video = jobs.create_video("base", "explain mock fund")
    jobs.update_video(video.video_id, status="done", out_path=video_file)

    resp = client.get(f"/api/videos/{video.video_id}/file")
    assert resp.status_code == 200
    assert resp.data == b"fake mp4 bytes"


def test_trigger_suggestion_creates_video_on_first_call():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    video, created = jobs.trigger_suggestion(session.session_id, "a")

    assert created is True
    assert video.kind == "suggestion"
    assert video.label == "What if A?"
    assert video.topic_prompt == "Explain A."


def test_trigger_suggestion_is_idempotent():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    first, first_created = jobs.trigger_suggestion(session.session_id, "a")
    second, second_created = jobs.trigger_suggestion(session.session_id, "a")

    assert first_created is True
    assert second_created is False
    assert first.video_id == second.video_id


def test_trigger_suggestion_unknown_id_returns_none():
    session = jobs.create_session()
    jobs.attach_decode_result(session.session_id, _decode_result())

    video, created = jobs.trigger_suggestion(session.session_id, "does_not_exist")

    assert video is None
    assert created is False


def test_generate_suggestion_success(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/suggestions/a/generate")
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["video_id"].startswith("vid_")

    video = jobs.get_video(data["video_id"])
    assert video.kind == "suggestion"
    assert video.label == "What if A?"


def test_generate_suggestion_idempotent_returns_same_video_id(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    first = client.post(f"/api/sessions/{session_id}/suggestions/a/generate").get_json()
    second = client.post(f"/api/sessions/{session_id}/suggestions/a/generate").get_json()

    assert first["video_id"] == second["video_id"]


def test_generate_suggestion_404_unknown_suggestion_id(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/suggestions/does_not_exist/generate")
    assert resp.status_code == 404


def test_generate_suggestion_404_unknown_session(client):
    resp = client.post("/api/sessions/sess_nope/suggestions/a/generate")
    assert resp.status_code == 404


def test_generate_suggestion_409_when_session_not_ready(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]

    resp = client.post(f"/api/sessions/{session_id}/suggestions/a/generate")
    assert resp.status_code == 409
