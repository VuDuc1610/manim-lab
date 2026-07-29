import { useEffect, useRef, useState } from "react";
import { getSessionStatus } from "../api";

const POLL_INTERVAL_MS = 2000;

function isSessionTerminal(status) {
  if (!status) return false;
  if (status.decode_status === "error") return true;
  if (status.decode_status !== "done") return false;
  return Object.values(status.videos).every(
    (v) => v.status === "done" || v.status === "error",
  );
}

export function useSessionStatus(sessionId) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return undefined;

    let cancelled = false;

    async function poll() {
      try {
        const data = await getSessionStatus(sessionId);
        if (cancelled) return;
        setStatus(data);
        if (!isSessionTerminal(data)) {
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [sessionId]);

  return { status, error };
}
