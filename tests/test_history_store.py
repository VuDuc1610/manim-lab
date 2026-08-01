from webapp import history_store


def test_load_all_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    assert history_store.load_all() == []


def test_append_creates_file_and_persists_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    history_store.append({"video_id": "vid_1", "kind": "base", "label": "Overview"})

    assert history_store.load_all() == [{"video_id": "vid_1", "kind": "base", "label": "Overview"}]


def test_append_accumulates_multiple_entries_in_order(tmp_path, monkeypatch):
    monkeypatch.setattr(history_store, "HISTORY_FILE", tmp_path / "learning_history.json")

    history_store.append({"video_id": "vid_1"})
    history_store.append({"video_id": "vid_2"})

    assert [e["video_id"] for e in history_store.load_all()] == ["vid_1", "vid_2"]
