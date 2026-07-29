import DistributionHistory from "../components/DistributionHistory";
import FundDetailsTable from "../components/FundDetailsTable";
import SectorWeights from "../components/SectorWeights";
import TopHoldingsTable from "../components/TopHoldingsTable";
import VerifiedBadge from "../components/VerifiedBadge";
import { schdFund } from "../data/schdFund";

export default function SchdFundPage() {
  return (
    <div className="fund-page">
      <header className="fund-header">
        <div className="fund-header-top">
          <span className="fund-ticker">{schdFund.ticker}</span>
          <VerifiedBadge />
        </div>
        <h1>{schdFund.name}</h1>
        <p className="fund-subhead">{schdFund.category}</p>
      </header>

      <FundDetailsTable fund={schdFund} />
      <TopHoldingsTable holdings={schdFund.topHoldings} />
      <DistributionHistory history={schdFund.distributionHistory} />
      <SectorWeights sectors={schdFund.sectorWeights} />

      <footer className="fund-footer">
        Illustrative demo data, not live market data.
      </footer>
    </div>
  );
}
