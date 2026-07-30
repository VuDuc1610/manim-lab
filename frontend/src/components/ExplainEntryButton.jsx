export default function ExplainEntryButton({ onClick }) {
  return (
    <button type="button" className="explain-entry-button" onClick={onClick} aria-label="Explain this fund">
      ✨
    </button>
  );
}
