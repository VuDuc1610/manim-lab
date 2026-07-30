import FloatingWidgetButton from "./components/FloatingWidgetButton";
import SchdFundPage from "./pages/SchdFundPage";
import { schdFundContentText } from "./data/schdFund";

export default function App() {
  return (
    <>
      <div className="app-bar">
        <div className="app-bar-brand">
          <span className="app-bar-mark">M</span>
          manim-lab
        </div>
        <div className="app-bar-search">
          <input type="text" placeholder="Search" disabled />
        </div>
        <nav className="app-bar-nav">
          <span>Discover</span>
          <span>Portfolio</span>
          <span>Research</span>
        </nav>
        <div className="app-bar-account" aria-hidden="true">
          <span className="app-bar-account-icon">＠</span>
        </div>
      </div>
      <SchdFundPage />
      <FloatingWidgetButton fundContentText={schdFundContentText} />
    </>
  );
}
