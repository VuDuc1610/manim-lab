import { useState } from "react";
import { createSession } from "../api";
import VideoPanel from "./VideoPanel";

export default function FloatingWidgetButton({ fundContentText }) {
  const [sessionId, setSessionId] = useState(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  async function handleClick() {
    setError(null);
    if (sessionId) {
      setOpen(true);
      return;
    }
    setStarting(true);
    try {
      const result = await createSession(fundContentText);
      setSessionId(result.session_id);
      setOpen(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setStarting(false);
    }
  }

  return (
    <>
      <button type="button" className="floating-widget-button" onClick={handleClick} disabled={starting}>
        <span className="floating-widget-icon" aria-hidden="true">
          ▶
        </span>
        {starting ? "Starting…" : "Explain this fund"}
      </button>
      {error && <div className="floating-widget-error">{error}</div>}
      {open && sessionId && <VideoPanel sessionId={sessionId} onClose={() => setOpen(false)} />}
    </>
  );
}
