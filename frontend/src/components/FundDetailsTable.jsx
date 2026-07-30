export default function FundDetailsTable({ fund, onExplain }) {
  const cells = [
    ["AUM", `$${fund.aumBillions}B`],
    ["Price-Earnings ratio", fund.peRatio],
    ["30-Day yield", `${fund.thirtyDayYieldPct}%`],
    ["Average volume", fund.avgVolume],
    ["High today", `$${fund.highToday.toFixed(2)}`],
    ["Low today", `$${fund.lowToday.toFixed(2)}`],
    ["Open price", `$${fund.openPrice.toFixed(2)}`],
    ["Volume", fund.volume],
    ["52 Week high", `$${fund.week52High.toFixed(2)}`],
    ["52 Week low", `$${fund.week52Low.toFixed(2)}`],
    ["Expense ratio", `${fund.expenseRatio}%`],
    ["Short inventory", fund.shortInventory],
    ["Borrow rate", `${fund.borrowRatePct.toFixed(2)}%`],
  ];

  return (
    <section className="fund-section">
      <h2>Key statistics</h2>
      <div className="stat-grid stat-grid-4">
        {cells.map(([label, value]) => (
          <div className="stat-cell" key={label}>
            <div className="stat-cell-label-row">
              <span className="stat-label">{label}</span>
              <button
                type="button"
                className="explain-trigger"
                aria-label={`Explain ${label}`}
                onClick={() => onExplain(`Explain what "${label}" (${value}) means for this fund.`)}
              >
                ✨
              </button>
            </div>
            <span className="stat-value">{value}</span>
          </div>
        ))}
      </div>
      <a
        className="fund-details-link"
        href="#"
        onClick={(e) => e.preventDefault()}
      >
        View Prospectus and Reports
      </a>
    </section>
  );
}
