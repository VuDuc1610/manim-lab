from webapp import history_store, jobs


def test_persist_history_entry_writes_completed_video(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    video = jobs.create_video("followup", "topic", label="What is PE ratio?")
    jobs.update_video(
        video.video_id,
        status="done",
        title="PE Ratio Explained",
        quick_explain_status="done",
        quick_explain={"headline": "h", "explanation": "e", "key_points": ["a"]},
    )

    jobs.persist_history_entry(video.video_id)

    entries = history_store.load_all()
    assert len(entries) == 1
    assert entries[0]["video_id"] == video.video_id
    assert entries[0]["label"] == "What is PE ratio?"
    assert entries[0]["title"] == "PE Ratio Explained"
    assert entries[0]["quick_explain"]["headline"] == "h"


def test_persist_history_entry_skips_if_not_done(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    video = jobs.create_video("followup", "topic")  # still "queued"
    jobs.persist_history_entry(video.video_id)

    assert history_store.load_all() == []


def test_persist_history_entry_unknown_video_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    jobs.persist_history_entry("vid_does_not_exist")  # must not raise

    assert history_store.load_all() == []


def test_history_entries_uses_label_or_title_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")
    history_store.append({"video_id": "vid_a", "label": "Explicit label"})
    history_store.append({"video_id": "vid_b", "label": None, "title": "Fallback title"})

    assert jobs.history_entries() == [
        {"video_id": "vid_a", "label": "Explicit label"},
        {"video_id": "vid_b", "label": "Fallback title"},
    ]


def test_rehydrate_from_history_restores_video_and_seeds_counter(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")
    history_store.append(
        {
            "video_id": "vid_997",
            "kind": "base",
            "label": "Overview",
            "title": "How the Fund Works",
            "quick_explain": {"headline": "h", "explanation": "e", "key_points": ["a"]},
        }
    )

    # jobs._videos / _video_counter are shared global state across the whole
    # test session (other tests freely call jobs.create_video without
    # resetting it) — snapshot and restore so this test doesn't leak a
    # rehydrated video or a bumped counter into unrelated tests.
    original_videos = dict(jobs._videos)
    original_counter = jobs._video_counter
    try:
        jobs.rehydrate_from_history()

        video = jobs.get_video("vid_997")
        assert video is not None
        assert video.status == "done"
        assert video.label == "Overview"
        assert video.title == "How the Fund Works"
        assert video.quick_explain_status == "done"
        assert video.quick_explain["headline"] == "h"
        assert video.out_path == jobs.config.OUT_DIR / "vid_997.mp4"

        new_video = jobs.create_video("base", "topic")
        assert new_video.video_id == "vid_998"
    finally:
        jobs._videos.clear()
        jobs._videos.update(original_videos)
        jobs._video_counter = original_counter
