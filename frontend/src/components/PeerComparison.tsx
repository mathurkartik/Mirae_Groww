/**
 * PeerComparison.tsx — Fund Peer Comparison
 * Compares the current fund with similar funds in the same category.
 */
"use client";

interface PeerFund {
  name: string;
  return_1y: string | null;
  return_3y: string | null;
  fund_size: string | null;
}

interface PeerComparisonProps {
  peers: PeerFund[];
  currentFundName: string;
}

export function PeerComparison({ peers, currentFundName }: PeerComparisonProps) {
  if (!peers || peers.length === 0) {
    return null;
  }

  // Ensure current fund is at the top if it's in the list, or we add it conceptually
  return (
    <div className="peers-section" style={{ background: 'var(--bg-white)', padding: 24, borderRadius: 16, border: '1px solid var(--border)', marginBottom: 24 }}>
      <h3 style={{ margin: '0 0 20px', fontSize: 18, fontWeight: 700 }}>Peer Comparison</h3>
      
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left' }}>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, width: '40%' }}>FUND NAME</th>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>1Y RETURN</th>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>3Y RETURN</th>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>AUM</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((peer, idx) => {
              const isCurrent = peer.name.includes(currentFundName.split(' ')[0]); // Simple heuristic
              
              return (
                <tr 
                  key={idx} 
                  style={{ 
                    borderBottom: idx === peers.length - 1 ? 'none' : '1px solid var(--border-light)',
                    background: isCurrent ? 'var(--accent-light)' : 'transparent'
                  }}
                >
                  <td style={{ padding: '16px 8px', fontWeight: 600, borderRadius: isCurrent ? '8px 0 0 8px' : 0 }}>
                    {peer.name}
                    {isCurrent && <span style={{ marginLeft: 8, fontSize: 10, background: 'var(--accent)', color: 'white', padding: '2px 6px', borderRadius: 4 }}>CURRENT</span>}
                  </td>
                  <td style={{ padding: '16px 8px', textAlign: 'right', color: peer.return_1y?.startsWith('-') ? 'var(--red)' : 'var(--green)', fontWeight: 600 }}>
                    {peer.return_1y || "—"}
                  </td>
                  <td style={{ padding: '16px 8px', textAlign: 'right', color: peer.return_3y?.startsWith('-') ? 'var(--red)' : 'var(--green)', fontWeight: 600 }}>
                    {peer.return_3y || "—"}
                  </td>
                  <td style={{ padding: '16px 8px', textAlign: 'right', color: 'var(--text-secondary)', borderRadius: isCurrent ? '0 8px 8px 0' : 0 }}>
                    {peer.fund_size ? `₹${peer.fund_size}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
