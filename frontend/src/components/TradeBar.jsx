export default function TradeBar({ onAction }) {
  return (
    <div className="trade-bar">
      <button type="button" className="trade-button trade-sell" onClick={() => onAction("Sell")}>
        Sell
      </button>
      <button type="button" className="trade-button trade-buy" onClick={() => onAction("Buy")}>
        Buy
      </button>
    </div>
  );
}
