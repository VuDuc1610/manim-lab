import { useEffect } from "react";

export default function Toast({ message, onDone }) {
  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(onDone, 2500);
    return () => clearTimeout(timer);
  }, [message, onDone]);

  if (!message) return null;
  return <div className="toast">{message}</div>;
}
