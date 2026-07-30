import { useState } from "react";

export default function WatchlistStar() {
  const [watching, setWatching] = useState(false);

  return (
    <button
      type="button"
      className={`watchlist-star${watching ? " active" : ""}`}
      onClick={() => setWatching((w) => !w)}
      aria-label={watching ? "Remove from watchlist" : "Add to watchlist"}
      aria-pressed={watching}
    >
      {watching ? "★" : "☆"}
    </button>
  );
}
