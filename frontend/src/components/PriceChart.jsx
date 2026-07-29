import { useState } from "react";

// Illustrative-only trend line (matches the app's existing "illustrative
// demo data" framing) — this is the single most recognizable Robinhood
// visual motif, so it earns its place even though the app has no live price
// series to chart.
const POINTS = [
  [0, 128],
  [60, 118],
  [120, 132],
  [180, 98],
  [240, 108],
  [300, 76],
  [360, 88],
  [420, 58],
  [480, 68],
  [540, 38],
  [600, 22],
];

const LINE_POINTS = POINTS.map(([x, y]) => `${x},${y}`).join(" ");
const AREA_PATH = `M${POINTS.map(([x, y]) => `${x},${y}`).join(" L")} L600,160 L0,160 Z`;

const RANGES = ["1D", "1W", "1M", "3M", "1Y", "ALL"];

export default function PriceChart() {
  const [activeRange, setActiveRange] = useState("1Y");

  return (
    <div className="price-chart-wrap">
      <svg className="price-chart" viewBox="0 0 600 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00c805" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#00c805" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={AREA_PATH} fill="url(#chartFade)" />
        <polyline
          points={LINE_POINTS}
          fill="none"
          stroke="#00c805"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
      <div className="range-pills">
        {RANGES.map((r) => (
          <button
            key={r}
            type="button"
            className={`range-pill${r === activeRange ? " active" : ""}`}
            onClick={() => setActiveRange(r)}
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  );
}
