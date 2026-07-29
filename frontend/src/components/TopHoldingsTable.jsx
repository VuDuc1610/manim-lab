export default function TopHoldingsTable({ holdings }) {
  return (
    <section className="fund-section">
      <h2>Top Holdings</h2>
      <table className="fund-table fund-table-grid">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Name</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.ticker}>
              <td className="mono">{h.ticker}</td>
              <td>{h.name}</td>
              <td>{h.weightPct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
