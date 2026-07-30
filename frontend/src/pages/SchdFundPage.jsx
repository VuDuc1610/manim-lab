import { useState } from "react";
import DistributionHistory from "../components/DistributionHistory";
import FundDetailsTable from "../components/FundDetailsTable";
import PriceChart from "../components/PriceChart";
import SectorWeights from "../components/SectorWeights";
import TopHoldingsTable from "../components/TopHoldingsTable";
import VerifiedBadge from "../components/VerifiedBadge";
import WatchlistStar from "../components/WatchlistStar";
import Toast from "../components/Toast";
import TradeBar from "../components/TradeBar";
import { schdFund } from "../data/schdFund";

export default function SchdFundPage() {
  const [toastMessage, setToastMessage] = useState(null);

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
            <span className="hero-stat-label">Distribution yield</span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-value">${schdFund.aumBillions}B</span>
            <span className="hero-stat-label">AUM</span>
          </div>
        </div>

        <PriceChart />
      </header>

      <FundDetailsTable fund={schdFund} />
      <TopHoldingsTable holdings={schdFund.topHoldings} />
      <DistributionHistory history={schdFund.distributionHistory} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <TradeBar onAction={handleTradeAction} />
      <footer className="fund-footer">
        Illustrative demo data, not live market data.
      </footer>
      <Toast message={toastMessage} onDone={() => setToastMessage(null)} />
    </div>
  );
}
