export default function DistributionHistory({ history }) {
  return (
    <section className="fund-section">
      <h2>Recent Distributions</h2>
      <table className="fund-table fund-table-grid">
        <thead>
          <tr>
            <th>Ex-Date</th>
            <th>Amount / Share</th>
          </tr>
        </thead>
        <tbody>
          {history.map((d) => (
            <tr key={d.exDate}>
              <td className="mono">{d.exDate}</td>
              <td>${d.amount.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
