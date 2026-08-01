import pytest

from webapp import history_store, jobs, orchestrator
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
    assert data["followups"] == []


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
    assert "Explain mock fund." in video.topic_prompt


def test_followup_ungrounded_uses_question_as_topic_prompt_directly(client):
    """grounded=False (highlight-to-explain's term-definition questions)
    skips merging the fund's base_topic_prompt in — the question is already
    self-contained, and prepending the full fund overview drowns it out."""
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    question = 'Explain what "PE ratio" means in the context of Mock Fund.'
    resp = client.post(f"/api/sessions/{session_id}/followup", json={"question": question, "grounded": False})
    assert resp.status_code == 202

    video = jobs.get_video(resp.get_json()["video_id"])
    assert video.topic_prompt == question


def test_followup_records_on_session(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/followup", json={"question": "what about fees?"})
    video_id = resp.get_json()["video_id"]

    session = jobs.get_session(session_id)
    assert session.followups == [{"video_id": video_id, "question": "what about fees?"}]


def test_followup_multiple_appends_in_ask_order(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    first = client.post(f"/api/sessions/{session_id}/followup", json={"question": "q1"}).get_json()
    second = client.post(f"/api/sessions/{session_id}/followup", json={"question": "q2"}).get_json()

    session = jobs.get_session(session_id)
    assert session.followups == [
        {"video_id": first["video_id"], "question": "q1"},
        {"video_id": second["video_id"], "question": "q2"},
    ]


def test_session_status_includes_followups(client):
    create_resp = client.post("/api/sessions", json={"fund_content": "SCHD"})
    session_id = create_resp.get_json()["session_id"]
    jobs.attach_decode_result(session_id, _decode_result())

    resp = client.post(f"/api/sessions/{session_id}/followup", json={"question": "what about fees?"})
    video_id = resp.get_json()["video_id"]

    status = client.get(f"/api/sessions/{session_id}").get_json()
    assert status["followups"] == [{"video_id": video_id, "question": "what about fees?"}]


def test_record_followup_unknown_session_is_noop():
    jobs.record_followup("sess_does_not_exist", "vid_1", "q")  # must not raise


def test_get_history_empty(client, tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    resp = client.get("/api/history")
    assert resp.status_code == 200
    assert resp.get_json() == {"entries": []}


def test_get_history_returns_persisted_entries(client, tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")
    history_store.append({"video_id": "vid_1", "label": "Overview"})

    resp = client.get("/api/history")
    assert resp.get_json() == {"entries": [{"video_id": "vid_1", "label": "Overview"}]}


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
    assert data["quick_explain_status"] == "pending"
    assert data["quick_explain"] is None


def test_video_status_includes_quick_explain_once_done(client):
    video = jobs.create_video("base", "explain mock fund")
    result = {"headline": "h", "explanation": "e", "key_points": ["a", "b"]}
    jobs.update_video(video.video_id, quick_explain_status="done", quick_explain=result)

    resp = client.get(f"/api/videos/{video.video_id}/status")
    data = resp.get_json()
    assert data["quick_explain_status"] == "done"
    assert data["quick_explain"] == result


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
