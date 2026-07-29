export default function VerifiedBadge() {
  return (
    <span className="verified-badge" title="Illustrative demo data, not live market data">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
        <path
          d="M12 2l2.4 1.4 2.8-.3 1.1 2.6 2.6 1.1-.3 2.8L22 12l-1.4 2.4.3 2.8-2.6 1.1-1.1 2.6-2.8-.3L12 22l-2.4-1.4-2.8.3-1.1-2.6-2.6-1.1.3-2.8L2 12l1.4-2.4-.3-2.8 2.6-1.1L6.8 3.1l2.8.3L12 2z"
          fill="currentColor"
        />
        <path d="M8.5 12.2l2.3 2.3 4.7-4.9" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Verified fund data
    </span>
  );
}
