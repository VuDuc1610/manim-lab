import { useVideoStatus } from "../hooks/useVideoStatus";

export default function QuestionChip({ label, videoId, active, onSelect, onTrigger, disabled: forceDisabled }) {
  const { status } = useVideoStatus(videoId);
  const started = Boolean(videoId);
  const ready = status?.status === "done";
  const failed = status?.status === "error";

  function handleClick() {
    if (forceDisabled) return;
    if (!started) {
      onTrigger();
      return;
    }
    onSelect(videoId);
  }

  let text = label;
  if (failed) text = `${label} (failed)`;
  else if (started && !ready) text = `${label} — ${status?.stage_detail || status?.status || "generating…"}`;
  else if (forceDisabled) text = `${label} — generating…`;

  return (
    <button
      type="button"
      className={`question-chip${active ? " active" : ""}${failed ? " failed" : ""}`}
      disabled={forceDisabled}
      onClick={handleClick}
    >
      {(forceDisabled || (started && !ready)) && !failed && <span className="spinner" aria-hidden="true" />}
      <span className="question-chip-label">{text}</span>
    </button>
  );
}
