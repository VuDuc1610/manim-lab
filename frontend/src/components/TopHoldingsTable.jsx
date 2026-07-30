export default function TopHoldingsTable({ holdings, onExplain }) {
  const maxWeight = Math.max(...holdings.map((h) => h.weightPct));

  return (
    <section className="fund-section">
      <h2>Top holdings</h2>
      <div className="holdings-list">
        {holdings.map((h) => (
          <div className="holding-row" key={h.ticker}>
            <div className="holding-id">
              <span className="holding-ticker">{h.ticker}</span>
              <span className="holding-name">{h.name}</span>
            </div>
            <div className="holding-bar-track">
              <div className="holding-bar-fill" style={{ width: `${(h.weightPct / maxWeight) * 100}%` }} />
            </div>
            <span className="holding-weight">{h.weightPct}%</span>
            <button
              type="button"
              className="explain-trigger"
              aria-label={`Explain ${h.name}`}
              onClick={() => onExplain(`Explain why ${h.name} (${h.ticker}) is ${h.weightPct}% of this fund.`)}
            >
              ✨
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
