export default function QuickExplainCard({ data }) {
  return (
    <div className="quick-explain-card">
      <p className="quick-explain-headline">
        <span aria-hidden="true">💡</span> {data.headline}
      </p>
      <p className="quick-explain-text">{data.explanation}</p>
      <ul className="quick-explain-points">
        {data.key_points.map((point, i) => (
          <li key={i} className="quick-explain-point">
            <span className="quick-explain-point-icon" aria-hidden="true">
              ✓
            </span>
            <span>{point}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
