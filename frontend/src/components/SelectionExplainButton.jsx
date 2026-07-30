export default function SelectionExplainButton({ selection, onExplain }) {
  if (!selection) return null;
  const { text, rect } = selection;

  const style = {
    top: Math.max(8, rect.top - 40),
    left: rect.left + rect.width / 2,
  };

  return (
    <button
      type="button"
      className="selection-explain-button"
      style={style}
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => onExplain(text)}
    >
      ✨ Explain this
    </button>
  );
}
