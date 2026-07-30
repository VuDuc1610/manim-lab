import { useEffect, useState } from "react";
import { createSession, generateSuggestion, postFollowup, videoFileUrl } from "../api";
import { useSessionStatus } from "../hooks/useSessionStatus";
import FollowupInput from "./FollowupInput";
import QuestionChip from "./QuestionChip";
import VideoPlayer from "./VideoPlayer";

export default function ExplainModule({ fundContentText, contextualQuestion, onContextualHandled }) {
  const [sessionId, setSessionId] = useState(null);
  const [initError, setInitError] = useState(null);
  const { status, error } = useSessionStatus(sessionId);
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [suggestionVideoIds, setSuggestionVideoIds] = useState({});
  const [extraQuestions, setExtraQuestions] = useState([]);
  const [askError, setAskError] = useState(null);

  useEffect(() => {
    createSession(fundContentText)
      .then((result) => setSessionId(result.session_id))
      .catch((err) => setInitError(err.message));
  }, [fundContentText]);

  const baseVideo = status?.videos?.base;
  const currentVideoId = activeVideoId || baseVideo?.video_id;
  const currentVideoReady = currentVideoId && currentVideoId === baseVideo?.video_id
    ? baseVideo.status === "done"
    : true; // non-base chips only become selectable once QuestionChip confirms "done"
  const currentVideoUrl = currentVideoId && currentVideoReady ? videoFileUrl(currentVideoId) : null;

  async function handleAsk(question) {
    setAskError(null);
    try {
      const result = await postFollowup(sessionId, question);
      setExtraQuestions((qs) => [...qs, { videoId: result.video_id, label: question }]);
    } catch (err) {
      setAskError(err.message);
    }
  }

  useEffect(() => {
    if (!contextualQuestion || !sessionId) return;
    handleAsk(contextualQuestion).finally(onContextualHandled);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contextualQuestion, sessionId]);

  async function handleTriggerSuggestion(suggestionId) {
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
    }
  }

  return (
    <section className="explain-module">
      <div className="explain-module-header">
        <span className="explain-module-title">✨ Don't understand something?</span>
        <span className="explain-module-subtitle">Ask AI to explain any part of this fund, visually.</span>
      </div>

      {initError && <p className="panel-error">{initError}</p>}
      {error && <p className="panel-error">{error}</p>}

      {(status?.decode_status === "pending" || status?.decode_status === "running") && (
        <p className="panel-status">Reading the fund page…</p>
      )}
      {status?.decode_status === "error" && (
        <p className="panel-error">Couldn't read the fund page: {status.decode_error}</p>
      )}
      {baseVideo && baseVideo.status !== "done" && baseVideo.status !== "error" && !activeVideoId && (
        <p className="panel-status">
          Generating your explanation — {baseVideo.stage_detail || baseVideo.status}…
        </p>
      )}
      {baseVideo?.status === "error" && !activeVideoId && (
        <p className="panel-error">Video generation failed: {baseVideo.error}</p>
      )}

      {currentVideoUrl && (
        <VideoPlayer
          src={currentVideoUrl}
          title={currentVideoId === baseVideo?.video_id ? status.fund_name : undefined}
        />
      )}

      {status?.decode_status === "done" && (
        <div className="chip-row">
          <QuestionChip
            label={baseVideo?.title || "Overview"}
            videoId={baseVideo?.video_id}
            active={currentVideoId === baseVideo?.video_id}
            onSelect={setActiveVideoId}
            onTrigger={() => {}}
          />
          {status.suggestions.map((s) => {
            const videoId = suggestionVideoIds[s.id] === "pending" ? null : suggestionVideoIds[s.id] || s.video_id;
            return (
              <QuestionChip
                key={s.id}
                label={s.question}
                videoId={videoId}
                active={currentVideoId === videoId}
                onSelect={setActiveVideoId}
                onTrigger={() => handleTriggerSuggestion(s.id)}
              />
            );
          })}
          {extraQuestions.map((q) => (
            <QuestionChip
              key={q.videoId}
              label={q.label}
              videoId={q.videoId}
              active={currentVideoId === q.videoId}
              onSelect={setActiveVideoId}
              onTrigger={() => {}}
            />
          ))}
        </div>
      )}

      {status?.decode_status === "done" && (
        <>
          <FollowupInput onSubmit={handleAsk} disabled={false} />
          {askError && <p className="panel-error">{askError}</p>}
        </>
      )}
    </section>
  );
}
