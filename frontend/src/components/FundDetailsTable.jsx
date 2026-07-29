export default function FundDetailsTable({ fund }) {
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
            <span className="stat-label">{label}</span>
            <span className="stat-value">{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
