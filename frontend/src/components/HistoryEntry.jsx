import { useState } from "react";
import { videoFileUrl } from "../api";
import { useVideoStatus } from "../hooks/useVideoStatus";
import QuickExplainCard from "./QuickExplainCard";
import VideoPlayer from "./VideoPlayer";

export default function HistoryEntry({ videoId, label }) {
  const { status } = useVideoStatus(videoId);
  const [watching, setWatching] = useState(false);

  const ready = status?.status === "done";
  const failed = status?.status === "error";
  const quickExplain = status?.quick_explain_status === "done" ? status.quick_explain : null;

  return (
    <li className="history-entry">
      <p className="history-entry-label">{label}</p>

      {watching && ready ? (
        <VideoPlayer src={videoFileUrl(videoId)} title={label} />
      ) : failed ? (
        <p className="panel-error">Video generation failed: {status.error}</p>
      ) : ready ? (
        <div className="history-entry-ready">
          {quickExplain && <QuickExplainCard data={quickExplain} />}
          <button type="button" className="explain-watch-button" onClick={() => setWatching(true)}>
            ▶ Watch
          </button>
        </div>
      ) : (
        <div className="history-entry-generating">
          {quickExplain && <QuickExplainCard data={quickExplain} />}
          <div className="explain-generating-progress">
            <span className="spinner" aria-hidden="true" />
            <p className="panel-status">{status?.stage_detail || status?.status || "Generating…"}</p>
          </div>
        </div>
      )}
    </li>
  );
}
