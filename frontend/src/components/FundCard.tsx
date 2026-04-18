/**
 * FundCard.tsx — Fund summary card (Emerald Ledger Redesign)
 * Displays key metrics: name, category, 3Y return, expense ratio, AUM, risk.
 */
import Link from "next/link";
import { useWatchlist } from "@/hooks/useWatchlist";
import type { FundSummary } from "@/lib/api";

interface FundCardProps {
  fund: FundSummary;
}

export function FundCard({ fund }: FundCardProps) {
  const ret3y = fund.returns_3y_annualized;
  const isPositive = ret3y ? !ret3y.startsWith("-") : true;
  const { isInWatchlist, addToWatchlist, removeFromWatchlist } = useWatchlist();
  const isWatched = isInWatchlist(fund.slug);

  const toggleWatch = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isWatched) removeFromWatchlist(fund.slug);
    else addToWatchlist(fund);
  };

  return (
    <div className="fund-card" id={`fund-${fund.slug}`} style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '24px', transition: 'all 0.2s ease', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Link
        href={`/fund/${fund.slug}`}
        style={{ textDecoration: "none", color: "inherit", display: 'flex', flexDirection: 'column', gap: '20px' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
           <div style={{ flex: 1, minWidth: 0 }}>
             <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--bg-surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>📈</div>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                   {fund.scheme_name}
                </h3>
             </div>
             <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                {fund.category} / CORE • DIRECT GROWTH
             </p>
           </div>
           
           <div style={{ textAlign: 'right' }}>
              <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>3Y ANNUALIZED</p>
              <p style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                 {ret3y || "—"}
              </p>
           </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
          <div style={{ padding: '8px', background: 'var(--bg-surface-2)', borderRadius: '8px' }}>
            <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>AUM</p>
            <p style={{ margin: '2px 0 0', fontSize: '13px', fontWeight: 700 }}>{fund.aum ? `₹${fund.aum} Cr` : "—"}</p>
          </div>
          <div style={{ padding: '8px', background: 'var(--bg-surface-2)', borderRadius: '8px' }}>
            <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>EXP. RATIO</p>
            <p style={{ margin: '2px 0 0', fontSize: '13px', fontWeight: 700 }}>{fund.expense_ratio || "—"}</p>
          </div>
          <div style={{ padding: '8px', background: 'var(--bg-surface-2)', borderRadius: '8px' }}>
            <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700 }}>RISK LEVEL</p>
            <p style={{ margin: '2px 0 0', fontSize: '13px', fontWeight: 700, color: fund.risk_level?.includes('Very High') ? '#dc2626' : 'inherit' }}>{fund.risk_level || "—"}</p>
          </div>
        </div>
      </Link>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-light)', paddingTop: '16px', marginTop: 'auto' }}>
        <div style={{ display: 'flex', gap: '4px' }}>
           <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>JD</div>
           <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#cbd5e1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 800 }}>MS</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={toggleWatch} 
            style={{ 
              background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', 
              color: isWatched ? 'var(--accent)' : '#cbd5e1', padding: 0 
            }}
          >
            {isWatched ? '★' : '☆'}
          </button>
          <a
            href={fund.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ background: 'var(--accent-dark)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '30px', fontSize: '12px', fontWeight: 700, textDecoration: 'none' }}
            onClick={(e) => e.stopPropagation()}
          >
            Invest Now
          </a>
        </div>
      </div>
    </div>
  );
}
