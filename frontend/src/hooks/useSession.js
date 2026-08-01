import { useEffect, useRef, useState } from "react";
import { createSession } from "../api";

export function useSession(fundContentText) {
  const [sessionId, setSessionId] = useState(null);
  const [initError, setInitError] = useState(null);
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

  return { sessionId, initError };
}
