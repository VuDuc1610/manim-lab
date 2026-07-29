export default function FundDetailsTable({ fund }) {
  const rows = [
    ["Category", fund.category],
    ["Provider", fund.provider],
    ["Inception Date", fund.inceptionDate],
    ["Expense Ratio", `${fund.expenseRatio}%`],
    ["Distribution Yield", `${fund.distributionYieldPct}%`],
    ["Distribution Frequency", fund.distributionFrequency],
    ["Assets Under Management", `$${fund.aumBillions}B`],
    ["Benchmark", fund.benchmark],
    ["Number of Holdings", fund.numberOfHoldings],
  ];

  return (
    <section className="fund-section">
      <h2>Fund Details</h2>
      <table className="fund-table">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <th>{label}</th>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
