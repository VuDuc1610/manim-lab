import { useState } from "react";
import DistributionHistory from "../components/DistributionHistory";
import ExplainEntryButton from "../components/ExplainEntryButton";
import ExplainOverlay from "../components/ExplainOverlay";
import FundDetailsTable from "../components/FundDetailsTable";
import OrderBox from "../components/OrderBox";
import PriceChart from "../components/PriceChart";
import SectorWeights from "../components/SectorWeights";
import SelectionExplainButton from "../components/SelectionExplainButton";
import TopHoldingsTable from "../components/TopHoldingsTable";
import VerifiedBadge from "../components/VerifiedBadge";
import WatchlistStar from "../components/WatchlistStar";
import Toast from "../components/Toast";
import { useTextSelection } from "../hooks/useTextSelection";
import { schdFund, schdFundContentText } from "../data/schdFund";

export default function SchdFundPage() {
  const [toastMessage, setToastMessage] = useState(null);
  const [explainOpen, setExplainOpen] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const { selection, clear: clearSelection } = useTextSelection();

  function handleTradeAction(label) {
    setToastMessage(`${label} isn't available in this demo`);
  }

  function handleSelectionExplain(text) {
    const truncated = text.length > 120 ? text.slice(0, 120) + "…" : text;
    setPendingQuestion({
      prompt: `Explain what "${truncated}" means in the context of ${schdFund.name}.`,
      label: truncated,
    });
    setExplainOpen(true);
    clearSelection();
  }

  return (
    <div className="fund-page">
      <header className="fund-header">
        <div className="fund-header-top">
          <span className="fund-ticker">{schdFund.ticker}</span>
          <VerifiedBadge />
          <WatchlistStar />
        </div>
        <h1>{schdFund.name}</h1>
        <p className="fund-subhead">{schdFund.category}</p>

        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-value">{schdFund.expenseRatio}%</span>
            <span className="hero-stat-label">Expense ratio</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value accent">{schdFund.distributionYieldPct}%</span>
            <span className="hero-stat-label">Dividend yield (TTM)</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value">${schdFund.aumBillions}B</span>
            <span className="hero-stat-label">Net assets</span>
          </div>
        </div>

        <div className="chart-order-row">
          <PriceChart
            price={schdFund.price}
            dayChange={schdFund.dayChange}
            dayChangePct={schdFund.dayChangePct}
          />
          <OrderBox ticker={schdFund.ticker} onAction={handleTradeAction} />
        </div>
      </header>

      <FundDetailsTable fund={schdFund} />
      <TopHoldingsTable holdings={schdFund.topHoldings} />
      <DistributionHistory history={schdFund.distributionHistory} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <footer className="fund-footer">Illustrative demo data, not live market data.</footer>

      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />

      <ExplainEntryButton onClick={() => setExplainOpen(true)} />
      {!explainOpen && <SelectionExplainButton selection={selection} onExplain={handleSelectionExplain} />}
      <ExplainOverlay
        fundContentText={schdFundContentText}
        open={explainOpen}
        onClose={() => setExplainOpen(false)}
        pendingQuestion={pendingQuestion}
        onPendingHandled={() => setPendingQuestion(null)}
      />
    </div>
  );
}
