export default function SectorWeights({ sectors }) {
  return (
    <section className="fund-section">
      <h2>Sector weights</h2>
      <div className="sector-bars">
        {sectors.map((s) => (
          <div className="sector-row" key={s.sector}>
            <span className="sector-label">{s.sector}</span>
            <div className="sector-bar-track">
              <div className="sector-bar-fill" style={{ width: `${s.pct}%` }} />
            </div>
            <span className="sector-pct">{s.pct}%</span>
          </div>
        ))}
      </div>
    </section>
  );
}
