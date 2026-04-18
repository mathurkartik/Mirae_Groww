/**
 * fund/[slug]/page.tsx — Fund Detail Page (Emerald Ledger Redesign)
 * Full analytics dashboard for a single mutual fund scheme.
 */
"use client";

import { use } from "react";
import { AppShell } from "@/components/AppShell";
import { NavChart } from "@/components/NavChart";
import { HoldingsTable } from "@/components/HoldingsTable";
import { PeerComparison } from "@/components/PeerComparison";
import { ReturnCalculator } from "@/components/ReturnCalculator";
import SipCalculator from "@/components/SipCalculator";
import { useFundDetail } from "@/hooks/useFundData";

export default function FundDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { fund, isLoading, error } = useFundDetail(slug);

  if (error) {
    return (
      <AppShell>
        <div style={{ padding: 60, textAlign: 'center' }}>
          <h2 style={{ color: 'var(--red)' }}>Error Loading Fund</h2>
          <p>{error}</p>
        </div>
      </AppShell>
    );
  }

  if (isLoading || !fund) {
    return (
      <AppShell>
        <div className="skeleton" style={{ height: 40, width: '60%', marginBottom: 20 }} />
        <div className="skeleton" style={{ height: 350, width: '100%', marginBottom: 24, borderRadius: 16 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 32 }}>
           <div className="skeleton" style={{ height: 400, borderRadius: 16 }} />
           <div className="skeleton" style={{ height: 400, borderRadius: 16 }} />
        </div>
      </AppShell>
    );
  }

  const isPositive = !fund.nav_change_1d?.startsWith("-");

  return (
    <AppShell>
      {/* ── Breadcrumbs ── */}
      <div style={{ display: 'flex', gap: '8px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
         MUTUAL FUNDS / MIRAE ASSET / <span style={{ color: 'var(--accent)' }}>{fund.category.toUpperCase()}</span>
      </div>

      {/* ── 1. Title & NAV Header ── */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
         <div>
            <h1 style={{ margin: 0, fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>{fund.scheme_name}</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
               <span style={{ fontSize: '11px', fontWeight: 800, padding: '4px 12px', background: 'var(--bg-surface-2)', borderRadius: '20px', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                  EQUITY: {fund.category.toUpperCase()}
               </span>
               <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#fb923c', fontSize: '14px' }}>
                  ★★★★★ <span style={{ color: 'var(--text-muted)', fontWeight: 700, marginLeft: '4px', fontSize: '12px' }}>4.2 Rating</span>
               </div>
            </div>
         </div>
         <div style={{ textAlign: 'right' }}>
            <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>CURRENT NAV</p>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', justifyContent: 'flex-end' }}>
               <span style={{ fontSize: '36px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {fund.nav != null ? `₹${fund.nav.toFixed(2)}` : "—"}
               </span>
               <span style={{ fontSize: '16px', fontWeight: 700, color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                  {isPositive ? "↑" : "↓"} {fund.nav_change_1d}
               </span>
            </div>
         </div>
      </header>

      {/* ── 2. Top Section Columns ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2fr)', gap: '32px', marginBottom: '40px' }}>
         
         {/* Detail Left: Objective & Small Metrics */}
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px', borderLeft: '4px solid var(--accent)' }}>
            <div>
               <h3 style={{ margin: '0 0 12px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>INVESTMENT OBJECTIVE</h3>
               <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                  {fund.objective || "To generate long term capital appreciation by capitalizing on potential investment opportunities by predominantly investing in equities of large cap companies that are part of the Top 100 stocks by market capitalization."}
               </p>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-light)' }}>
               <div>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>MIN. INVESTMENT</p>
                  <p style={{ margin: '4px 0 0', fontSize: '16px', fontWeight: 800 }}>{fund.min_sip || "₹5,000"}</p>
               </div>
               <div>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>EXPENSE RATIO</p>
                  <p style={{ margin: '4px 0 0', fontSize: '16px', fontWeight: 800 }}>{fund.expense_ratio || "0.52%"}</p>
               </div>
            </div>
            {fund.aum && (
               <div style={{ paddingTop: '16px', borderTop: '1px solid var(--border-light)' }}>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>FUND SIZE (AUM)</p>
                  <p style={{ margin: '4px 0 0', fontSize: '16px', fontWeight: 800 }}>₹{fund.aum} Cr</p>
               </div>
            )}
         </div>

         {/* Detail Right: Chart */}
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
               <h3 style={{ margin: 0, fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>GROWTH OF ₹10,000</h3>
               <div style={{ display: 'flex', gap: '4px' }}>
                  {['1M', '6M', '1Y', '3Y', 'ALL'].map(p => (
                     <button key={p} style={{ padding: '4px 10px', fontSize: '10px', fontWeight: 800, borderRadius: '20px', border: 'none', cursor: 'pointer', background: p === '1Y' ? 'var(--bg-dark-green)' : 'var(--bg-surface-2)', color: p === '1Y' ? 'white' : 'var(--text-secondary)' }}>{p}</button>
                  ))}
               </div>
            </div>
            <NavChart slug={fund.slug} />
         </div>
      </div>

      {/* ── 3. Middle Section: Returns Table & Calculator ── */}
      <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '40px', marginBottom: '40px' }}>
         <h2 style={{ margin: '0 0 8px', fontSize: '24px', fontWeight: 800 }}>Returns Calculator</h2>
         <p style={{ margin: '0 0 32px', fontSize: '14px', color: 'var(--text-secondary)' }}>Estimate your future wealth based on historical performance of this fund.</p>
         
         <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.5fr)', gap: '64px' }}>
            {/* Calculator Control */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>MONTHLY INVESTMENT AMOUNT</span>
                  <span style={{ background: 'var(--accent-light)', color: 'var(--accent-dark)', padding: '6px 16px', borderRadius: '8px', fontSize: '18px', fontWeight: 800 }}>₹5,000</span>
               </div>
               
               {/* Simplified UI version of the calculator sliders for the redesign */}
               <div style={{ width: '100%', height: '4px', background: 'var(--border)', borderRadius: '2px', position: 'relative' }}>
                  <div style={{ position: 'absolute', left: 0, width: '40%', height: '100%', background: 'var(--accent)', borderRadius: '2px' }} />
                  <div style={{ position: 'absolute', left: '40%', top: '-8px', width: '20px', height: '20px', borderRadius: '50%', background: 'var(--accent)', border: '4px solid white', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }} />
               </div>
               <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700 }}>
                  <span>₹500</span>
                  <span>₹1,00,000</span>
               </div>

               <button style={{ 
                  marginTop: '16px', padding: '16px', borderRadius: '12px', background: 'linear-gradient(135deg, var(--accent), var(--accent-dark))', color: 'white', border: 'none', fontSize: '16px', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', boxShadow: '0 8px 24px rgba(0, 168, 132, 0.25)' 
               }}>
                  INVEST NOW <span>→</span>
               </button>
            </div>

            {/* Returns Result Table */}
            <div style={{ background: 'var(--bg-surface-2)', borderRadius: '16px', padding: '24px' }}>
               <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800 }}>
                     <tr>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em' }}>OVER THE PAST</th>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em' }}>TOTAL INVESTMENT</th>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em', textAlign: 'right' }}>WOULD&apos;VE BECOME</th>
                     </tr>
                  </thead>
                  <tbody style={{ fontSize: '13px', fontWeight: 700 }}>
                     {[
                        { p: '1 Year', inv: '₹60,000', corpus: '₹68,450' },
                        { p: '3 Years', inv: '₹1,80,000', corpus: '₹2,35,120' },
                        { p: '5 Years', inv: '₹3,00,000', corpus: '₹4,82,900' },
                        { p: 'All Time', inv: '₹6,00,000', corpus: '₹12,45,000' }
                     ].map((row, i) => (
                        <tr key={row.p} style={{ borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}>
                           <td style={{ padding: '16px 12px' }}>{row.p}</td>
                           <td style={{ padding: '16px 12px', color: 'var(--text-secondary)' }}>{row.inv}</td>
                           <td style={{ padding: '16px 12px', textAlign: 'right', color: 'var(--green)', fontSize: '15px' }}>{row.corpus}</td>
                        </tr>
                     ))}
                  </tbody>
               </table>
            </div>
         </div>
      </div>

      {/* ── 4. Bottom Detailed Stats ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '32px', marginBottom: '64px' }}>
         
         {/* Risk Profile */}
         <div>
            <h3 style={{ margin: '0 0 20px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '8px' }}>
               ⚠️ RISK PROFILE
            </h3>
            <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px' }}>
               <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '60px', marginBottom: '16px' }}>
                  <div style={{ flex: 1, height: '20%', background: 'var(--accent-light)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '40%', background: 'var(--accent-light)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '60%', background: 'var(--accent)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '80%', background: '#fb923c', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '100%', background: '#ef4444', borderRadius: '4px', border: '2px dashed white', outline: '1px solid #ef4444' }} />
               </div>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '14px', fontWeight: 800 }}>Very High Risk</span>
                  <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--accent)', letterSpacing: '0.05em' }}>EQUITY STANDARD</span>
               </div>
            </div>
         </div>

         {/* Asset Allocation */}
         <div>
            <h3 style={{ margin: '0 0 20px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>ASSET ALLOCATION</h3>
            <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
               <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px', fontWeight: 700 }}>
                     <span>Equity</span>
                     <span style={{ fontWeight: 800 }}>98.4%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-surface-2)', borderRadius: '3px' }}>
                     <div style={{ width: '98.4%', height: '100%', background: 'var(--bg-dark-green)', borderRadius: '3px' }} />
                  </div>
               </div>
               <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px', fontWeight: 700 }}>
                     <span>Cash & Others</span>
                     <span style={{ fontWeight: 800 }}>1.6%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-surface-2)', borderRadius: '3px' }}>
                     <div style={{ width: '1.6%', height: '100%', background: 'var(--accent)', borderRadius: '3px' }} />
                  </div>
               </div>
            </div>
         </div>

         {/* Fund Managers */}
         <div>
            <h3 style={{ margin: '0 0 20px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>FUND MANAGERS</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
               {[
                  { name: 'Gaurav Misra', exp: '25+ YEARS' },
                  { name: 'Ankit Jain', exp: '12+ YEARS' }
               ].map(fm => (
                  <div key={fm.name} style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                     <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: '#1e293b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>👤</div>
                     <div>
                        <p style={{ margin: 0, fontSize: '14px', fontWeight: 800 }}>{fm.name}</p>
                        <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--accent)', letterSpacing: '0.05em' }}>EXPERIENCE: {fm.exp}</p>
                     </div>
                  </div>
               ))}
            </div>
         </div>
      </div>

      {/* ── 5. Holdings & Peer Comparison (Using existing components) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: '32px' }}>
         <div>
            <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '32px' }}>
               <HoldingsTable holdings={fund.top_holdings} totalCount={fund.holdings_count} />
            </div>
         </div>
         <div>
            <PeerComparison peers={fund.peers} currentFundName={fund.scheme_name} />
         </div>
      </div>
      
    </AppShell>
  );
}
