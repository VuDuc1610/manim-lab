import { useState } from "react";
import DistributionHistory from "../components/DistributionHistory";
import ExplainModule from "../components/ExplainModule";
import FundDetailsTable from "../components/FundDetailsTable";
import OrderBox from "../components/OrderBox";
import PriceChart from "../components/PriceChart";
import SectorWeights from "../components/SectorWeights";
import TopHoldingsTable from "../components/TopHoldingsTable";
import VerifiedBadge from "../components/VerifiedBadge";
import WatchlistStar from "../components/WatchlistStar";
import Toast from "../components/Toast";
import { schdFund, schdFundContentText } from "../data/schdFund";

export default function SchdFundPage() {
  const [toastMessage, setToastMessage] = useState(null);
  const [contextualQuestion, setContextualQuestion] = useState(null);

  function handleTradeAction(label) {
    setToastMessage(`${label} isn't available in this demo`);
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

      <ExplainModule
        fundContentText={schdFundContentText}
        contextualQuestion={contextualQuestion}
        onContextualHandled={() => setContextualQuestion(null)}
      />

      <FundDetailsTable fund={schdFund} onExplain={setContextualQuestion} />
      <TopHoldingsTable holdings={schdFund.topHoldings} onExplain={setContextualQuestion} />
      <DistributionHistory history={schdFund.distributionHistory} onExplain={setContextualQuestion} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <footer className="fund-footer">
        Illustrative demo data, not live market data.
      </footer>
      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />
    </div>
  );
}
