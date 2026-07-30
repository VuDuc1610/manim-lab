export const schdFund = {
  ticker: "SCHD",
  name: "Schwab U.S. Dividend Equity ETF",
  provider: "Charles Schwab Asset Management",
  category: "Dividend / U.S. Large-Cap Value",
  inceptionDate: "2011-10-20",
  expenseRatio: 0.06,
  distributionYieldPct: 3.5,
  distributionFrequency: "Quarterly",
  aumBillions: 68,
  numberOfHoldings: 104,
  benchmark: "Dow Jones U.S. Dividend 100 Index",
  topHoldings: [
    { ticker: "TXN", name: "Texas Instruments", weightPct: 4.6 },
    { ticker: "VZ", name: "Verizon Communications", weightPct: 4.4 },
    { ticker: "CVX", name: "Chevron Corp", weightPct: 4.3 },
    { ticker: "ABBV", name: "AbbVie Inc.", weightPct: 4.2 },
    { ticker: "KO", name: "Coca-Cola Co", weightPct: 4.1 },
    { ticker: "PEP", name: "PepsiCo Inc.", weightPct: 3.9 },
    { ticker: "HD", name: "Home Depot Inc.", weightPct: 3.8 },
    { ticker: "MRK", name: "Merck & Co.", weightPct: 3.6 },
  ],
  distributionHistory: [
    { exDate: "2026-06-20", amount: 0.72 },
    { exDate: "2026-03-21", amount: 0.68 },
    { exDate: "2025-12-19", amount: 0.75 },
    { exDate: "2025-09-19", amount: 0.71 },
  ],
  sectorWeights: [
    { sector: "Financials", pct: 19.2 },
    { sector: "Health Care", pct: 15.4 },
    { sector: "Consumer Staples", pct: 14.8 },
    { sector: "Industrials", pct: 13.1 },
    { sector: "Energy", pct: 9.7 },
    { sector: "Technology", pct: 8.9 },
    { sector: "Other", pct: 18.9 },
  ],
};

export const schdFundContentText = `${schdFund.name} (${schdFund.ticker})
Category: ${schdFund.category}
Provider: ${schdFund.provider}
Inception Date: ${schdFund.inceptionDate}
Expense Ratio: ${schdFund.expenseRatio}%
Dividend Yield (TTM): ${schdFund.distributionYieldPct}% (illustrative)
Distribution Frequency: ${schdFund.distributionFrequency}
Assets Under Management: $${schdFund.aumBillions}B (illustrative)
Benchmark: ${schdFund.benchmark}
Number of Holdings: ${schdFund.numberOfHoldings}

Top Holdings:
${schdFund.topHoldings.map((h) => `- ${h.name} (${h.ticker}): ${h.weightPct}%`).join("\n")}

Recent Distributions (per share):
${schdFund.distributionHistory.map((d) => `- ${d.exDate}: $${d.amount.toFixed(2)}`).join("\n")}

Sector Weights:
${schdFund.sectorWeights.map((s) => `- ${s.sector}: ${s.pct}%`).join("\n")}
`;
