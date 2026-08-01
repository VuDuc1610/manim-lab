"""Persists completed video generations to disk so the Learning/History page
survives server restarts. webapp/jobs.py's _sessions/_videos dicts are pure
in-memory state that resets every process start; this file is the durable
record of anything already generated. jobs.py rehydrates from it at import
time — see jobs._rehydrate_from_history().
"""

import json
import threading

from pipeline import config

HISTORY_FILE = config.PROJECT_ROOT / "learning_history.json"

_lock = threading.Lock()


def load_all() -> list[dict]:
    with _lock:
        if not HISTORY_FILE.exists():
            return []
        return json.loads(HISTORY_FILE.read_text())


def append(entry: dict) -> None:
    with _lock:
        entries = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
        entries.append(entry)
        HISTORY_FILE.write_text(json.dumps(entries, indent=2))
