import { useEffect, useState } from "react";

export function useTextSelection() {
  const [selection, setSelection] = useState(null);

  useEffect(() => {
    function handleSelectionChange() {
      const sel = window.getSelection();
      const text = sel ? sel.toString().trim() : "";
      if (!text || sel.rangeCount === 0) {
        setSelection(null);
        return;
      }
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      setSelection({ text, rect });
    }

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, []);

  function clear() {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }

  return { selection, clear };
}
