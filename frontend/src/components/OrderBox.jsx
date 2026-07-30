import { useState } from "react";

// Decorative order-entry panel mimicking Robinhood's real trade box — every
// control here is illustrative only (per the app's existing "illustrative
// demo data" framing); onAction just routes to the same toast used by the
// rest of the app's non-functional trade affordances.
export default function OrderBox({ ticker, onAction }) {
  const [side, setSide] = useState("buy");

  return (
    <div className="order-box">
      <div className="order-box-tabs">
        <button
          type="button"
          className={`order-box-tab${side === "buy" ? " active" : ""}`}
          onClick={() => setSide("buy")}
        >
          Buy {ticker}
        </button>
        <button
          type="button"
          className={`order-box-tab${side === "short" ? " active" : ""}`}
          onClick={() => setSide("short")}
        >
          Short {ticker}
        </button>
      </div>

      <div className="order-box-row">
        <div className="order-box-row-label">
          <span>Order type</span>
          <span className="order-box-row-sublabel">
            Market
            <span className="order-box-info" aria-hidden="true">
              ⓘ
            </span>
          </span>
        </div>
        <div className="order-box-select">
          Buy order <span className="order-box-chevron">⌄</span>
        </div>
      </div>

      <div className="order-box-row">
        <div className="order-box-row-label">
          <span>Buy in</span>
        </div>
        <div className="order-box-select">
          Dollars <span className="order-box-chevron">⌄</span>
        </div>
      </div>

      <div className="order-box-row">
        <div className="order-box-row-label">
          <span>Amount</span>
        </div>
        <div className="order-box-amount">$0.00</div>
      </div>

      <div className="order-box-divider" />

      <div className="order-box-summary-row">
        <span>Estimated quantity</span>
        <span>0</span>
      </div>

      <button type="button" className="order-box-review" onClick={() => onAction("Review order")}>
        Review order
      </button>

      <div className="order-box-divider" />

      <div className="order-box-buying-power">$19,671.98 buying power available</div>

      <div className="order-box-account-row">
        <span>Individual investing · Individual</span>
        <span className="order-box-chevron" aria-hidden="true">
          ⇅
        </span>
      </div>

      <div className="order-box-extra-actions">
        <button
          type="button"
          className="order-box-outline-button"
          onClick={() => onAction(`Trade ${ticker} Options`)}
        >
          Trade {ticker} Options
        </button>
        <button type="button" className="order-box-outline-button" onClick={() => onAction("Add to Lists")}>
          ✓ Add to Lists
        </button>
      </div>
    </div>
  );
}
