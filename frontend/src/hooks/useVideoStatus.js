import { useEffect, useRef, useState } from "react";
import { getVideoStatus } from "../api";

const POLL_INTERVAL_MS = 2000;

export function useVideoStatus(videoId) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!videoId) return undefined;

    let cancelled = false;

    async function poll() {
      try {
        const data = await getVideoStatus(videoId);
        if (cancelled) return;
        setStatus(data);
        if (data.status !== "done" && data.status !== "error") {
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
  }, [videoId]);

  return { status, error };
}
