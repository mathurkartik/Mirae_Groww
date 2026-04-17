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
      <div className="welcome-icon" aria-hidden="true" style={{ background: 'var(--accent-light)', color: 'var(--accent)', borderRadius: '12px', width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px', marginBottom: '16px' }}>
        🤖
      </div>

      <h1 className="welcome-title" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '8px' }}>MiraeExplorer AI</h1>
      <p className="welcome-subtitle" style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px', lineHeight: 1.5 }}>
        Quick answers about scheme facts, fees, and rules.
      </p>

      {/* Example questions */}
      <div className="example-grid" role="list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {EXAMPLES.map((q) => (
          <button
            key={q}
            className="filter-pill"
            style={{ textAlign: 'left', width: '100%', borderRadius: '10px' }}
            onClick={() => onQuestion(q)}
            type="button"
          >
            <span>{q}</span>
          </button>
        ))}
      </div>

      <p className="welcome-disclaimer" style={{ marginTop: 'auto', fontSize: '11px', color: 'var(--text-muted)', paddingTop: '20px' }}>
        Facts-only • No investment advice
      </p>
    </div>
  );
}
