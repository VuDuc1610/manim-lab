export default function SuggestionButton({ video, active, onSelect, fallbackLabel = "Loading suggestion…" }) {
  const ready = video?.status === "done";
  const failed = video?.status === "error";
  const label = video?.label || fallbackLabel;

  return (
    <button
      type="button"
      className={`suggestion-button${active ? " active" : ""}${failed ? " failed" : ""}`}
      disabled={!ready}
      onClick={() => ready && onSelect(video.video_id)}
    >
      {!ready && !failed && <span className="spinner" aria-hidden="true" />}
      <span className="suggestion-label">{failed ? `${label} (failed)` : label}</span>
    </button>
  );
}
