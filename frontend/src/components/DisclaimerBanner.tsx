/**
 * DisclaimerBanner — always-visible fixed top bar.
 * "Facts-only. No investment advice."
 */
export function DisclaimerBanner() {
  return (
    <div
      className="disclaimer-banner"
      role="banner"
      aria-label="Compliance disclaimer"
    >
      <span className="disclaimer-icon" aria-hidden="true">
        🔒
      </span>
      <span className="disclaimer-text">
        <strong>Facts-only.</strong> No investment advice. Answers sourced
        exclusively from official Mirae Asset &amp; Groww pages.
      </span>
    </div>
  );
}
