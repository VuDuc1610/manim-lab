export default function DistributionHistory({ history, onExplain }) {
  return (
    <section className="fund-section">
      <h2>Recent distributions</h2>
      <div className="distribution-list">
        {history.map((d) => (
          <div className="distribution-row" key={d.exDate}>
            <span className="distribution-date">{d.exDate}</span>
            <span className="distribution-amount">+${d.amount.toFixed(2)}</span>
            <button
              type="button"
              className="explain-trigger"
              aria-label={`Explain the ${d.exDate} distribution`}
              onClick={() => onExplain(`Explain the $${d.amount.toFixed(2)} distribution paid on ${d.exDate}.`)}
            >
              ✨
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
