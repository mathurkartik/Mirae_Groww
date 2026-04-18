/**
 * WelcomeScreen.tsx — Atelier Advisor Redesign
 * Shown when the active thread has no messages yet.
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
    <div className="welcome" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '40px 24px' }}>
      {/* Logo mark */}
      <div className="welcome-icon" aria-hidden="true" style={{ background: 'var(--bg-dark-green)', color: 'white', borderRadius: '16px', width: '56px', height: '56px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '28px', marginBottom: '24px', boxShadow: '0 8px 24px rgba(0,0,0,0.1)' }}>
        ✨
      </div>

      <h1 className="welcome-title" style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '12px', letterSpacing: '-0.01em' }}>Atelier Advisor</h1>
      <p className="welcome-subtitle" style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '32px', lineHeight: 1.6, maxWidth: '280px' }}>
        Sovereign-grade analysis on fund details, fees, and regulatory facts.
      </p>

      {/* Example questions */}
      <div className="example-grid" role="list" style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%' }}>
        {EXAMPLES.map((q) => (
          <button
            key={q}
            className="filter-pill"
            style={{ 
               textAlign: 'left', 
               width: '100%', 
               borderRadius: '12px', 
               padding: '14px 16px', 
               background: 'white', 
               border: '1px solid var(--border)',
               fontSize: '13px',
               fontWeight: 600,
               color: 'var(--text-secondary)',
               cursor: 'pointer',
               transition: 'all 0.15s ease'
            }}
            onClick={() => onQuestion(q)}
            type="button"
          >
            <span>{q}</span>
          </button>
        ))}
      </div>

      <p className="welcome-disclaimer" style={{ marginTop: 'auto', fontSize: '11px', color: 'var(--text-muted)', paddingTop: '40px', fontWeight: 600, letterSpacing: '0.05em' }}>
        INSTITUTIONAL DATA SOURCE • MIRAE ASSET
      </p>
    </div>
  );
}
