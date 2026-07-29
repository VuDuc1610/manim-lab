import { useEffect, useState } from "react";

// Fetch-and-blob instead of a direct <video src="cross-origin URL">: the
// Flask dev server's Range-request handling doesn't play nicely with
// Chromium's native media-element network path in this environment, even
// though the same bytes load fine via fetch(). A short demo clip fits
// comfortably in memory, so downloading it up front (no progressive
// streaming) is an acceptable tradeoff here.
export default function VideoPlayer({ src, title }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!src) return undefined;

    let cancelled = false;
    let objectUrl = null;
    setBlobUrl(null);
    setError(null);

    fetch(src)
      .then((resp) => {
        if (!resp.ok) throw new Error(`failed to load video: ${resp.status}`);
        return resp.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  return (
    <div className="video-player-wrap">
      {title && <div className="video-title">{title}</div>}
      {error && <p className="panel-error">{error}</p>}
      {blobUrl ? (
        <video key={blobUrl} className="video-player" src={blobUrl} controls autoPlay />
      ) : (
        !error && <p className="panel-status">Loading video…</p>
      )}
    </div>
  );
}
