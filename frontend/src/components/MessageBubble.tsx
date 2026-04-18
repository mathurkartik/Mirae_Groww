/**
 * MessageBubble.tsx — Atelier Advisor Redesign
 * Renders a single chat message — user or assistant.
 */
import type { Message } from "@/lib/api";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isFundPage = typeof window !== "undefined" && window.location.pathname.includes("/fund/");

  if (isUser) {
    return (
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
        <div 
           style={{ 
             background: 'var(--bg-dark-green)', 
             color: 'white', 
             padding: '16px 20px', 
             borderRadius: '24px 24px 4px 24px',
             fontSize: '14px',
             fontWeight: 500,
             maxWidth: '85%',
             boxShadow: '0 4px 12px rgba(0,0,0,0.05)'
           }}
        >
          <p style={{ margin: 0 }}>{message.content}</p>
        </div>
      </div>
    );
  }

  const isError = message.content.startsWith("⚠️");

  return (
    <div style={{ marginBottom: '24px', position: 'relative' }}>
      <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
         
         <div 
            style={{
               background: isError ? '#fef2f2' : 'white',
               color: isError ? '#991b1b' : 'var(--text-primary)',
               border: '1px solid',
               borderColor: isError ? '#fecaca' : 'var(--border)',
               padding: '16px 20px',
               borderRadius: '24px 24px 24px 4px',
               fontSize: '13px',
               lineHeight: '1.6',
               maxWidth: '90%',
               boxShadow: '0 4px 16px rgba(0,0,0,0.03)'
            }}
         >
            {message.is_refusal && !isError && (
               <span style={{ display: 'block', fontSize: '9px', fontWeight: 800, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
                  ADVISORY QUERY — FACTS ONLY
               </span>
            )}
            <p style={{ margin: 0 }}>{message.content}</p>

            {message.is_math_redirect && (
               <a
                  href={isFundPage ? "#sip-calculator" : "/"}
                  style={{
                     marginTop: '16px',
                     display: 'inline-flex',
                     alignItems: 'center',
                     gap: '8px',
                     padding: '8px 16px',
                     background: 'var(--accent)',
                     borderRadius: '8px',
                     fontSize: '12px',
                     fontWeight: 700,
                     color: 'white',
                     textDecoration: 'none'
                  }}
               >
                  {isFundPage ? "Scroll to Calculator ↓" : "Explore funds to calculate →"}
               </a>
            )}

            {/* Citation link */}
            {message.citation && (
               <a
                  href={message.citation}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                     display: 'inline-flex',
                     alignItems: 'center',
                     gap: '6px',
                     marginTop: '12px',
                     fontSize: '11px',
                     fontWeight: 600,
                     color: 'var(--accent)',
                     textDecoration: 'none',
                     opacity: 0.8
                  }}
               >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>
                  View source
               </a>
            )}
         </div>

         {/* Avatar & Badge row below bubble */}
         <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px', paddingLeft: '4px' }}>
            <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px' }}>✨</div>
            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted)' }}>Atelier Assistant</span>
         </div>
      </div>
    </div>
  );
}
