/**
 * WelcomeScreen.tsx
 * Shown when the active thread has no messages yet.
 * Displays the 3 canonical example questions from the spec.
 */
interface Props {
  onQuestion: (q: string) => void;
}

const EXAMPLES = [
  "What is the expense ratio of Mirae Asset Large Cap Direct?",
  "What is the exit load for Mirae Asset ELSS Tax Saver Fund?",
  "What is the minimum SIP for Mirae Asset Flexi Cap Fund?",
];

export function WelcomeScreen({ onQuestion }: Props) {
  return (
    <div className="welcome">
      {/* Logo mark */}
      <div className="welcome-icon" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
          <rect width="48" height="48" rx="14" fill="url(#wg)" />
          <path
            d="M14 34L24 14l10 20H14z"
            fill="white"
            fillOpacity="0.9"
          />
          <defs>
            <linearGradient id="wg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
              <stop stopColor="#6366f1" />
              <stop offset="1" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <h1 className="welcome-title">Mirae Asset FAQ Assistant</h1>
      <p className="welcome-subtitle">
        Ask factual questions about Mirae Asset mutual fund schemes.
        <br />
        Answers are sourced exclusively from official Groww pages.
      </p>

      {/* Example questions */}
      <div className="example-grid" role="list">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            id={`example-${q.slice(0, 20).replace(/\s+/g, "-").toLowerCase()}`}
            className="example-chip"
            onClick={() => onQuestion(q)}
            role="listitem"
            type="button"
          >
            <span className="example-chip-icon" aria-hidden="true">✦</span>
            <span>{q}</span>
          </button>
        ))}
      </div>

      <p className="welcome-disclaimer">
        🔒 Facts-only &mdash; No investment advice
      </p>
    </div>
  );
}
