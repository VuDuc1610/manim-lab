export default function DistributionHistory({ history }) {
  return (
    <section className="fund-section">
      <h2>Recent distributions</h2>
      <div className="distribution-list">
        {history.map((d) => (
          <div className="distribution-row" key={d.exDate}>
            <span className="distribution-date">{d.exDate}</span>
            <span className="distribution-amount">+${d.amount.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
