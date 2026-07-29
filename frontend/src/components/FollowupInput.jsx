import { useState } from "react";

export default function FollowupInput({ onSubmit, disabled }) {
  const [question, setQuestion] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setQuestion("");
  }

  return (
    <form className="followup-form" onSubmit={handleSubmit}>
      <input
        type="text"
        className="followup-input"
        placeholder="Ask your own what-if question…"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        disabled={disabled}
      />
      <button type="submit" className="followup-submit" disabled={disabled || !question.trim()}>
        Ask
      </button>
    </form>
  );
}
