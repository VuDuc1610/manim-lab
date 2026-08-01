from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from webapp import jobs, orchestrator


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

    @app.post("/api/sessions")
    def create_session():
        data = request.get_json(silent=True) or {}
        fund_content = data.get("fund_content")
        if not isinstance(fund_content, str) or not fund_content.strip():
            return jsonify({"error": "fund_content is required"}), 400

        session = jobs.create_session()
        orchestrator.start_session(session.session_id, fund_content)
        return jsonify({"session_id": session.session_id, "status": "decoding"}), 202

    @app.get("/api/sessions/<session_id>")
    def get_session_status(session_id):
        status = jobs.session_status_dict(session_id)
        if status is None:
            return jsonify({"error": "session not found"}), 404
        return jsonify(status)

    @app.post("/api/sessions/<session_id>/followup")
    def followup(session_id):
        session = jobs.get_session(session_id)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        if session.decode_status != "done":
            return jsonify({"error": "session not ready"}), 409

        data = request.get_json(silent=True) or {}
        question = data.get("question")
        if not isinstance(question, str) or not question.strip():
            return jsonify({"error": "question is required"}), 400

        # grounded=True (default) is for "what if" hypotheticals typed into the
        # free-text box — they need the fund's real numbers to reason about a
        # change. grounded=False is for highlight-to-explain's term-definition
        # questions, which are already self-contained (e.g. 'Explain what "PE
        # ratio" means...') — merging the full fund overview in front of those
        # drowns out the actual question, so the video ends up mostly about the
        # fund in general instead of the highlighted term.
        grounded = data.get("grounded", True)
        if grounded:
            topic_prompt = (
                f"{question} Background on the fund, for grounding only — the video "
                f"should stay focused on answering the question above, not restate "
                f"this: {session.base_topic_prompt}"
            )
        else:
            topic_prompt = question
        video = jobs.create_video("followup", topic_prompt, label=question)
        jobs.record_followup(session_id, video.video_id, question)
        orchestrator.start_followup(video.video_id, topic_prompt)
        return jsonify({"video_id": video.video_id, "status": "queued"}), 202

    @app.post("/api/sessions/<session_id>/suggestions/<suggestion_id>/generate")
    def generate_suggestion(session_id, suggestion_id):
        session = jobs.get_session(session_id)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        if session.decode_status != "done":
            return jsonify({"error": "session not ready"}), 409

        video, created = jobs.trigger_suggestion(session_id, suggestion_id)
        if video is None:
            return jsonify({"error": "unknown suggestion id"}), 404
        if created:
            orchestrator.start_followup(video.video_id, video.topic_prompt)
        return jsonify({"video_id": video.video_id, "status": "queued"}), 202

    @app.get("/api/history")
    def get_history():
        return jsonify({"entries": jobs.history_entries()})

    @app.get("/api/videos/<video_id>/status")
    def video_status(video_id):
        status = jobs.video_status_dict(video_id)
        if status is None:
            return jsonify({"error": "video not found"}), 404
        return jsonify(status)

    @app.get("/api/videos/<video_id>/file")
    def video_file(video_id):
        video = jobs.get_video(video_id)
        if video is None:
            return jsonify({"error": "video not found"}), 404
        if video.status != "done" or video.out_path is None:
            return jsonify({"error": "video not ready"}), 409
        response = send_file(video.out_path, mimetype="video/mp4", conditional=True)
        # A <video src> load is a cross-origin no-cors resource fetch, not a
        # fetch()/XHR call — flask-cors' Access-Control-Allow-Origin doesn't
        # cover it. Without this header Chrome's Opaque Response Blocking
        # rejects the response outright.
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return response

    return app
