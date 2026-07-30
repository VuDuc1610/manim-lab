export default function FundDetailsTable({ fund, onExplain }) {
  const cells = [
    ["Category", fund.category],
    ["Provider", fund.provider],
    ["Inception date", fund.inceptionDate],
    ["Distribution frequency", fund.distributionFrequency],
    ["Benchmark", fund.benchmark],
    ["Number of holdings", fund.numberOfHoldings],
  ];

  return (
    <section className="fund-section">
      <h2>Fund details</h2>
      <div className="stat-grid">
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
    </section>
  );
}
