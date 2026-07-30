import { useEffect, useRef, useState } from "react";
import { createSession, generateSuggestion, postFollowup, videoFileUrl } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import { useVideoStatus } from "../hooks/useVideoStatus";
import FollowupInput from "./FollowupInput";
import QuestionChip from "./QuestionChip";
import VideoPlayer from "./VideoPlayer";

export default function ExplainOverlay({ fundContentText, open, onClose, pendingQuestion, onPendingHandled }) {
  const [sessionId, setSessionId] = useState(null);
  const [initError, setInitError] = useState(null);
  const { status, error } = useSessionStatus(sessionId);
  const [suggestionVideoIds, setSuggestionVideoIds] = useState({});
  const [pendingSuggestionIds, setPendingSuggestionIds] = useState(() => new Set());
  const [extraQuestions, setExtraQuestions] = useState([]);
  const [askError, setAskError] = useState(null);
  const [focusedVideoId, setFocusedVideoId] = useState(null);
  const [watching, setWatching] = useState(false);
  const sessionInitRef = useRef(false);

  useEffect(() => {
    // StrictMode double-invokes mount effects in dev; without this guard that
    // means two createSession calls (two full decode + base-video pipeline
    // runs) per page load, which burns Gemini's tight free-tier quota.
    if (sessionInitRef.current) return;
    sessionInitRef.current = true;
    createSession(fundContentText)
      .then((result) => setSessionId(result.session_id))
      .catch((err) => setInitError(err.message));
  }, [fundContentText]);

  useEffect(() => {
    if (!open) {
      setFocusedVideoId(null);
      setWatching(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const baseVideo = status?.videos?.base;

  async function handleAsk(question, label = question) {
    setAskError(null);
    try {
      const result = await postFollowup(sessionId, question);
      setExtraQuestions((qs) => [...qs, { videoId: result.video_id, label }]);
      return result;
    } catch (err) {
      setAskError(err.message);
      return null;
    }
  }

  async function handleAskAndFocus(question, label = question) {
    const result = await handleAsk(question, label);
    if (result) setFocusedVideoId(result.video_id);
  }

  useEffect(() => {
    if (!pendingQuestion || !sessionId) return;
    handleAskAndFocus(pendingQuestion.prompt, pendingQuestion.label).finally(onPendingHandled);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion, sessionId]);

  async function handleTriggerSuggestion(suggestionId) {
    // Guard against a second click firing a second real generateSuggestion
    // call (a real Gemini pipeline run) while the first is still in flight —
    // the "pending" video id below is rendered as null to QuestionChip, which
    // alone would leave the chip looking untriggered and clickable again.
    if (pendingSuggestionIds.has(suggestionId)) return;
    setPendingSuggestionIds((s) => new Set(s).add(suggestionId));
    setSuggestionVideoIds((m) => (m[suggestionId] ? m : { ...m, [suggestionId]: "pending" }));
    try {
      const result = await generateSuggestion(sessionId, suggestionId);
      setSuggestionVideoIds((m) => ({ ...m, [suggestionId]: result.video_id }));
    } catch (err) {
      setAskError(err.message);
      setSuggestionVideoIds((m) => {
        const next = { ...m };
        delete next[suggestionId];
        return next;
      });
    } finally {
      setPendingSuggestionIds((s) => {
        const next = new Set(s);
        next.delete(suggestionId);
        return next;
      });
    }
  }

  function labelForVideoId(videoId) {
    if (videoId === baseVideo?.video_id) return baseVideo?.title || "Overview";
    const suggestion = status?.suggestions?.find(
      (s) => (suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id) === videoId,
    );
    if (suggestion) return suggestion.question;
    const extra = extraQuestions.find((q) => q.videoId === videoId);
    if (extra) return extra.label;
    return "Your question";
  }

  if (!open) return null;

  return (
    <div className="explain-overlay-backdrop" onClick={onClose}>
      <div
        className={`explain-overlay${watching ? " watching" : ""}`}
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="explain-overlay-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {initError && <p className="panel-error">{initError}</p>}
        {error && <p className="panel-error">{error}</p>}
        {(status?.decode_status === "pending" || status?.decode_status === "running") && (
          <p className="panel-status">Reading the fund page…</p>
        )}
        {status?.decode_status === "error" && (
          <p className="panel-error">Couldn't read the fund page: {status.decode_error}</p>
        )}

        {status?.decode_status === "done" && focusedVideoId && (
          <FocusedView
            videoId={focusedVideoId}
            label={labelForVideoId(focusedVideoId)}
            watching={watching}
            onWatch={() => setWatching(true)}
            onBack={() => (watching ? setWatching(false) : setFocusedVideoId(null))}
          />
        )}

        {status?.decode_status === "done" && !focusedVideoId && (
          <>
            <div className="explain-overlay-header">
              <span className="explain-overlay-title">✨ Don't understand something?</span>
              <span className="explain-overlay-subtitle">Ask AI to explain any part of this fund, visually.</span>
            </div>

            <div className="chip-row">
              <QuestionChip
                label={baseVideo?.title || "Overview"}
                videoId={baseVideo?.video_id}
                active={false}
                onSelect={setFocusedVideoId}
                onTrigger={() => {}}
              />
              {status.suggestions.map((s) => {
                const videoId = suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id;
                return (
                  <QuestionChip
                    key={s.id}
                    label={s.question}
                    videoId={videoId}
                    active={false}
                    onSelect={setFocusedVideoId}
                    onTrigger={() => handleTriggerSuggestion(s.id)}
                    disabled={pendingSuggestionIds.has(s.id)}
                  />
                );
              })}
              {extraQuestions.map((q) => (
                <QuestionChip
                  key={q.videoId}
                  label={q.label}
                  videoId={q.videoId}
                  active={false}
                  onSelect={setFocusedVideoId}
                  onTrigger={() => {}}
                />
              ))}
            </div>

            <FollowupInput onSubmit={handleAskAndFocus} disabled={false} />
            {askError && <p className="panel-error">{askError}</p>}
          </>
        )}
      </div>
    </div>
  );
}

function FocusedView({ videoId, label, watching, onWatch, onBack }) {
  const { status } = useVideoStatus(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";

  return (
    <div className="explain-focused">
      <button type="button" className="explain-back-link" onClick={onBack}>
        ‹ Back
      </button>

      {watching && ready ? (
        <VideoPlayer src={videoFileUrl(videoId)} title={label} />
      ) : failed ? (
        <p className="panel-error">Video generation failed: {status.error}</p>
      ) : ready ? (
        <div className="explain-ready">
          <p className="explain-ready-title">{label}</p>
          <button type="button" className="explain-watch-button" onClick={onWatch}>
            ▶ Watch
          </button>
        </div>
      ) : (
        <div className="explain-generating">
          <span className="spinner" aria-hidden="true" />
          <p className="explain-generating-title">{label}</p>
          <p className="panel-status">{status?.stage_detail || status?.status || "Generating…"}</p>
        </div>
      )}
    </div>
  );
}
