import { useEffect, useState } from "react";
import { postFollowup, videoFileUrl } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import { useVideoStatus } from "../hooks/useVideoStatus";
import FollowupInput from "./FollowupInput";
import SuggestionButton from "./SuggestionButton";
import VideoPlayer from "./VideoPlayer";

const SUGGESTION_SLOTS = ["suggestion_1", "suggestion_2", "suggestion_3"];

function FollowupEntry({ videoId, active, onSelect, onReady }) {
  const { status } = useVideoStatus(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";
  const label = status?.label || "Your question";

  useEffect(() => {
    if (ready) onReady(videoId);
  }, [ready, videoId, onReady]);

  return (
    <button
      type="button"
      className={`suggestion-button followup-entry${active ? " active" : ""}${failed ? " failed" : ""}`}
      disabled={!ready}
      onClick={() => ready && onSelect(videoId)}
    >
      {!ready && !failed && <span className="spinner" aria-hidden="true" />}
      <span className="suggestion-label">
        {failed ? `${label} (failed)` : ready ? label : `${label} — ${status?.stage_detail || "generating…"}`}
      </span>
    </button>
  );
}

export default function VideoPanel({ sessionId, onClose }) {
  const { status, error } = useSessionStatus(sessionId);
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [followupIds, setFollowupIds] = useState([]);
  const [followupError, setFollowupError] = useState(null);
  // Only build a video URL once the backend actually reports status "done" —
  // a video_id exists as soon as the job is queued, long before the file is
  // ready, so gating on "the id exists" instead of "the video is done" was
  // causing the player to fetch a video that returns 409.
  const [readyVideoIds, setReadyVideoIds] = useState(() => new Set());

  const baseVideo = status?.videos?.base;
  const currentVideoId = activeVideoId || baseVideo?.video_id;
  const currentVideoUrl =
    currentVideoId && readyVideoIds.has(currentVideoId) ? videoFileUrl(currentVideoId) : null;

  const markReady = (videoId) => {
    setReadyVideoIds((prev) => (prev.has(videoId) ? prev : new Set(prev).add(videoId)));
  };

  useEffect(() => {
    if (!status) return;
    for (const video of Object.values(status.videos)) {
      if (video.status === "done") markReady(video.video_id);
    }
  }, [status]);

  async function handleFollowup(question) {
    setFollowupError(null);
    try {
      const result = await postFollowup(sessionId, question);
      setFollowupIds((ids) => [...ids, result.video_id]);
    } catch (err) {
      setFollowupError(err.message);
    }
  }

  return (
    <div className="video-panel-overlay" onClick={onClose}>
      <div className="video-panel" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="video-panel-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {error && <p className="panel-error">{error}</p>}
        {!status && !error && <p className="panel-status">Connecting…</p>}

        {(status?.decode_status === "pending" || status?.decode_status === "running") && (
          <p className="panel-status">Reading the fund page…</p>
        )}

        {status?.decode_status === "error" && (
          <p className="panel-error">Couldn't read the fund page: {status.decode_error}</p>
        )}

        {baseVideo && baseVideo.status !== "done" && baseVideo.status !== "error" && (
          <p className="panel-status">
            Generating your video — {baseVideo.stage_detail || baseVideo.status}…
          </p>
        )}

        {baseVideo?.status === "error" && (
          <p className="panel-error">Video generation failed: {baseVideo.error}</p>
        )}

        {currentVideoUrl && (
          <VideoPlayer
            src={currentVideoUrl}
            title={currentVideoId === baseVideo?.video_id ? status.fund_name : undefined}
          />
        )}

        {status?.decode_status === "done" && (
          <div className="suggestion-row">
            <SuggestionButton
              video={baseVideo}
              active={currentVideoId === baseVideo?.video_id}
              onSelect={setActiveVideoId}
              fallbackLabel={baseVideo?.title || "Base video"}
            />
            {SUGGESTION_SLOTS.map((slot) => {
              const video = status.videos[slot];
              if (!video) return null;
              return (
                <SuggestionButton
                  key={slot}
                  video={video}
                  active={currentVideoId === video.video_id}
                  onSelect={setActiveVideoId}
                />
              );
            })}
            {followupIds.map((videoId) => (
              <FollowupEntry
                key={videoId}
                videoId={videoId}
                active={currentVideoId === videoId}
                onSelect={setActiveVideoId}
                onReady={markReady}
              />
            ))}
          </div>
        )}

        {status?.decode_status === "done" && (
          <>
            <FollowupInput onSubmit={handleFollowup} disabled={false} />
            {followupError && <p className="panel-error">{followupError}</p>}
          </>
        )}
      </div>
    </div>
  );
}
