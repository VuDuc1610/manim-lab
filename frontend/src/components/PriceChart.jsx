import { useMemo, useState } from "react";

const RANGES = ["1D", "1W", "1M", "3M", "YTD", "1Y", "5Y", "MAX"];

// Deterministic pseudo-random walk seeded by range name — illustrative only
// (matches the app's existing "illustrative demo data" framing), but gives
// each range a visibly distinct line instead of reusing one static shape.
function seededPoints(seed, count) {
  let x = [...seed].reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const next = () => {
    x = (x * 1103515245 + 12345) & 0x7fffffff;
    return x / 0x7fffffff;
  };
  const points = [];
  let y = 90 + next() * 20;
  for (let i = 0; i < count; i++) {
    y = Math.max(10, Math.min(150, y + (next() - 0.5) * 30));
    points.push([Math.round((600 * i) / (count - 1)), Math.round(y)]);
  }
  return points;
}

const POINTS_BY_RANGE = Object.fromEntries(RANGES.map((r) => [r, seededPoints(r, 24)]));

export default function PriceChart({ price, dayChange, dayChangePct }) {
  const [activeRange, setActiveRange] = useState("1Y");

  const { linePoints, areaPath } = useMemo(() => {
    const points = POINTS_BY_RANGE[activeRange];
    return {
      linePoints: points.map(([x, y]) => `${x},${y}`).join(" "),
      areaPath: `M${points.map(([x, y]) => `${x},${y}`).join(" L")} L600,160 L0,160 Z`,
    };
  }, [activeRange]);

  const isUp = dayChange >= 0;
  const sign = isUp ? "+" : "-";

  return (
    <div className="price-chart-wrap">
      <div className="price-header">
        <span className="price-current">${price.toFixed(2)}</span>
        <span className={`price-change${isUp ? " positive" : " negative"}`}>
          {sign}${Math.abs(dayChange).toFixed(2)} ({sign}
          {Math.abs(dayChangePct).toFixed(2)}%) Today
        </span>
      </div>
      <svg className="price-chart" viewBox="0 0 600 160" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00c805" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#00c805" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#chartFade)" />
        <polyline
          points={linePoints}
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
