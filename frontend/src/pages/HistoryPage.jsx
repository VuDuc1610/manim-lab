import { useEffect, useState } from "react";
import { getHistory } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import HistoryEntry from "../components/HistoryEntry";

export default function HistoryPage({ sessionId, initError, onBack }) {
  const { status, error } = useSessionStatus(sessionId);
  const [persisted, setPersisted] = useState([]);
  const [persistedError, setPersistedError] = useState(null);

  useEffect(() => {
    getHistory()
      .then((result) => setPersisted(result.entries))
      .catch((err) => setPersistedError(err.message));
  }, []);

  const sessionEntries = [];
  if (status?.decode_status === "done") {
    const baseVideo = status.videos?.base;
    if (baseVideo) {
      sessionEntries.push({ key: baseVideo.video_id, videoId: baseVideo.video_id, label: baseVideo.title || "Overview" });
    }
    for (const s of status.suggestions ?? []) {
      if (s.video_id) sessionEntries.push({ key: s.video_id, videoId: s.video_id, label: s.question });
    }
    for (const f of status.followups ?? []) {
      sessionEntries.push({ key: f.video_id, videoId: f.video_id, label: f.question });
    }
  }

  // Persisted entries survive a server restart and span every past session —
  // skip any video already covered above so this session's own items don't
  // show up twice.
  const seenVideoIds = new Set(sessionEntries.map((e) => e.videoId));
  const entries = [
    ...sessionEntries,
    ...persisted.filter((p) => !seenVideoIds.has(p.video_id)).map((p) => ({ key: p.video_id, videoId: p.video_id, label: p.label })),
  ];

  return (
    <div className="history-page">
      <button type="button" className="explain-back-link" onClick={onBack}>
        ‹ Back
      </button>

      <header className="history-header">
        <h1>📚 Learning</h1>
        <p className="history-subhead">Everything you've asked and generated, saved locally.</p>
      </header>

      {initError && <p className="panel-error">{initError}</p>}
      {error && <p className="panel-error">{error}</p>}
      {persistedError && <p className="panel-error">{persistedError}</p>}

      {entries.length === 0 && (
        <p className="panel-status">Nothing generated yet — ask a question from the fund page first.</p>
      )}

      {entries.length > 0 && (
        <ul className="history-list">
          {entries.map((e) => (
            <HistoryEntry key={e.key} videoId={e.videoId} label={e.label} />
          ))}
        </ul>
      )}
    </div>
  );
}
