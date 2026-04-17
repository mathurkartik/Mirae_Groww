/**
 * HoldingsTable.tsx — Fund Portfolio Holdings
 * Displays top holdings with sector, instrument, and allocation details.
 */
"use client";

import { useState } from "react";

interface Holding {
  name: string;
  sector: string;
  instrument: string;
  allocation: string;
}

interface HoldingsTableProps {
  holdings: Holding[];
  totalCount: number | null;
}

export function HoldingsTable({ holdings, totalCount }: HoldingsTableProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (!holdings || holdings.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
        No holdings data available for this fund.
      </div>
    );
  }

  const displayedHoldings = isExpanded ? holdings : holdings.slice(0, 5);

  return (
    <div className="holdings-section" style={{ background: 'var(--bg-white)', padding: 24, borderRadius: 16, border: '1px solid var(--border)', marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Top Holdings</h3>
        <button 
          className="top-navbar-link" 
          style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? "Show Less" : "View All"}
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)', textAlign: 'left' }}>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, width: '40%' }}>COMPANY</th>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500 }}>SECTOR</th>
              <th style={{ padding: '12px 0', color: 'var(--text-muted)', fontWeight: 500, textAlign: 'right' }}>ASSETS</th>
            </tr>
          </thead>
          <tbody>
            {displayedHoldings.map((holding, idx) => (
              <tr key={idx} style={{ borderBottom: idx === displayedHoldings.length - 1 ? 'none' : '1px solid var(--border-light)' }}>
                <td style={{ padding: '16px 0', fontWeight: 600 }}>{holding.name}</td>
                <td style={{ padding: '16px 0', color: 'var(--text-secondary)' }}>{holding.sector}</td>
                <td style={{ padding: '16px 0', textAlign: 'right', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {holding.allocation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalCount && totalCount > holdings.length && !isExpanded && (
        <p style={{ margin: '16px 0 0', fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          Showing top {holdings.length} of {totalCount} total holdings.
        </p>
      )}
    </div>
  );
}
