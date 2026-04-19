/**
 * fund/[slug]/page.tsx — Fund Detail Page (Emerald Ledger Redesign)
 * Full analytics dashboard for a single mutual fund scheme.
 */
"use client";

import { use, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { NavChart } from "@/components/NavChart";
import { HoldingsTable } from "@/components/HoldingsTable";
import { SectorChart } from "@/components/SectorChart";
import { PeerComparison } from "@/components/PeerComparison";
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
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
         <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>MUTUAL FUNDS</Link>
         <span>/</span>
         <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>MIRAE ASSET</Link>
         <span>/</span>
         <Link href={`/category/${fund.category_slug}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>{fund.category.toUpperCase()}</Link>
      </div>

      {/* ── 1. Title & NAV Header ── */}
      <header id="top" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
         <div style={{ minWidth: 0 }}>
            <h1 style={{ margin: 0, fontSize: '28px', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', wordBreak: 'break-word' }}>{fund.scheme_name}</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px', flexWrap: 'wrap' }}>
               <span style={{ fontSize: '11px', fontWeight: 800, padding: '4px 12px', background: 'var(--bg-surface-2)', borderRadius: '20px', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                  {fund.category.toUpperCase()}
               </span>
               {fund.rating && (
                 <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#fb923c', fontSize: '14px' }}>
                   {"★".repeat(Math.round(fund.rating))} <span style={{ color: 'var(--text-muted)', fontWeight: 700, marginLeft: '4px', fontSize: '12px' }}>{fund.rating} Rating</span>
                 </div>
               )}
            </div>
         </div>
         <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>CURRENT NAV</p>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', justifyContent: 'flex-end' }}>
               <span style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {fund.nav != null ? `₹${fund.nav.toFixed(2)}` : "—"}
               </span>
               <span style={{ fontSize: '14px', fontWeight: 700, color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                  {isPositive ? "↑" : "↓"} {fund.nav_change_1d}
               </span>
            </div>
         </div>
      </header>

      {/* ── 2. Top Section: Objective + Chart ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2fr)', gap: '24px', marginBottom: '40px' }}>
         
         {/* Left: Objective & Metrics */}
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px', borderLeft: '4px solid var(--accent)' }}>
            <div>
               <h3 style={{ margin: '0 0 12px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>INVESTMENT OBJECTIVE</h3>
               <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                  {fund.objective || "To generate long term capital appreciation by capitalizing on potential investment opportunities."}
               </p>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-light)' }}>
               <div>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>MIN. INVESTMENT</p>
                  <p style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 800 }}>{fund.min_sip || "₹5,000"}</p>
               </div>
               <div>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>EXPENSE RATIO</p>
                  <p style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 800 }}>{fund.expense_ratio || "—"}</p>
               </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-light)' }}>
               {fund.aum && (
                  <div>
                     <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>FUND SIZE (AUM)</p>
                     <p style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 800 }}>₹{fund.aum} Cr</p>
                  </div>
               )}
               <div>
                  <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>EXIT LOAD</p>
                  <p style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 800 }}>{fund.exit_load?.match(/(\d+(?:\.\d+)?%)/)?.[0] || "—"}</p>
                  <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)' }}>{fund.exit_load?.match(/within (\d+ (?:days|months|year|years))/i)?.[0]?.replace(/within/i, "For") || ""}</p>
               </div>
            </div>
         </div>

         {/* Right: NAV Chart */}
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '24px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>NAV HISTORY</h3>
            <NavChart slug={fund.slug} />
         </div>
      </div>

      {/* ── 3. Returns Calculator (FUNCTIONAL) ── */}
      <div id="sip-calculator" style={{ marginBottom: '40px', borderRadius: 'var(--radius-lg)', overflow: 'hidden', border: '1px solid var(--border)' }}>
         <SipCalculator fundName={fund.scheme_name} mfapiCode={fund.mfapi_code} />
      </div>

      {/* ── 4. Bottom Detailed Stats ── */}
      <div id="risk" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px', marginBottom: '48px' }}>
         
         {/* Risk Profile */}
         <div>
            <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>⚠️ RISK PROFILE</h3>
            <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px' }}>
               <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px', height: '50px', marginBottom: '16px' }}>
                  <div style={{ flex: 1, height: '20%', background: 'var(--accent-light)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '40%', background: 'var(--accent-light)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '60%', background: 'var(--accent)', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '80%', background: '#fb923c', borderRadius: '4px' }} />
                  <div style={{ flex: 1, height: '100%', background: '#ef4444', borderRadius: '4px' }} />
               </div>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '13px', fontWeight: 800 }}>{fund.risk_level || "Very High Risk"}</span>
                  <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--accent)', letterSpacing: '0.05em' }}>EQUITY</span>
               </div>
            </div>
         </div>

         {/* Asset Allocation */}
         <div>
            <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>ASSET ALLOCATION</h3>
            <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
               <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px', fontWeight: 700 }}>
                     <span>Equity</span><span style={{ fontWeight: 800 }}>98.4%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-surface-2)', borderRadius: '3px' }}>
                     <div style={{ width: '98.4%', height: '100%', background: 'var(--bg-dark-green)', borderRadius: '3px' }} />
                  </div>
               </div>
               <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px', fontWeight: 700 }}>
                     <span>Cash & Others</span><span style={{ fontWeight: 800 }}>1.6%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-surface-2)', borderRadius: '3px' }}>
                     <div style={{ width: '1.6%', height: '100%', background: 'var(--accent)', borderRadius: '3px' }} />
                  </div>
               </div>
            </div>
         </div>

         {/* Fund Managers */}
         <div>
            <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>FUND MANAGERS</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
               {[
                  { name: 'Gaurav Misra', exp: '25+ YEARS' },
                  { name: 'Ankit Jain', exp: '12+ YEARS' }
               ].map(fm => (
                  <div key={fm.name} style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '12px', padding: '14px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                     <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#1e293b', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px' }}>👤</div>
                     <div>
                        <p style={{ margin: 0, fontSize: '13px', fontWeight: 800 }}>{fm.name}</p>
                        <p style={{ margin: 0, fontSize: '10px', fontWeight: 800, color: 'var(--accent)', letterSpacing: '0.05em' }}>{fm.exp}</p>
                     </div>
                  </div>
               ))}
            </div>
         </div>
      </div>

      {/* ── 5. Holdings & Sectors ── */}
      <div id="holdings" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.3fr) minmax(0, 1fr)', gap: '24px', marginBottom: '40px' }}>
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '28px' }}>
            <HoldingsTable holdings={fund.top_holdings} totalCount={fund.holdings_count} />
         </div>
         <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '28px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>SECTOR ALLOCATION</h3>
            <SectorChart holdings={fund.top_holdings} />
         </div>
      </div>

      {/* ── 6. Peer Comparison ── */}
      <div style={{ marginBottom: '40px' }}>
         <PeerComparison peers={fund.peers} currentFundName={fund.scheme_name} />
      </div>
      
    </AppShell>
  );
}
