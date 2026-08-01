import { useState } from "react";
import { schdFundContentText } from "./data/schdFund";
import { useSession } from "./hooks/useSession";
import HistoryPage from "./pages/HistoryPage";
import SchdFundPage from "./pages/SchdFundPage";

export default function App() {
  const [view, setView] = useState("fund"); // "fund" | "history"
  const { sessionId, initError } = useSession(schdFundContentText);

  return (
    <>
      <div className="app-bar">
        <div className="app-bar-brand">
          <span className="app-bar-mark">M</span>
          3blue1brown Investing
        </div>
        <div className="app-bar-search">
          <input type="text" placeholder="Search" disabled />
        </div>
        <nav className="app-bar-nav">
          <span>Discover</span>
          <button
            type="button"
            className={`app-bar-nav-link${view === "fund" ? " active" : ""}`}
            onClick={() => setView("fund")}
          >
            Portfolio
          </button>
          <button
            type="button"
            className={`app-bar-nav-link${view === "history" ? " active" : ""}`}
            onClick={() => setView("history")}
          >
            Learning
          </button>
        </nav>
        <div className="app-bar-account" aria-hidden="true">
          <span className="app-bar-account-icon">＠</span>
        </div>
      </div>
      {view === "fund" ? (
        <SchdFundPage sessionId={sessionId} initError={initError} />
      ) : (
        <HistoryPage sessionId={sessionId} initError={initError} onBack={() => setView("fund")} />
      )}
    </>
  );
}
