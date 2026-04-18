/**
 * fund/[slug]/page.tsx — Fund Detail Page
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
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
           <div className="skeleton" style={{ height: 200, borderRadius: 16 }} />
           <div className="skeleton" style={{ height: 200, borderRadius: 16 }} />
        </div>
      </AppShell>
    );
  }

  const isPositive = !fund.nav_change_1d?.startsWith("-");

  return (
    <AppShell>
      {/* ── 1. Header Section ────────────────────────────────── */}
      <section style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
           <div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                 <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', background: 'var(--bg-surface-2)', borderRadius: 20, color: 'var(--text-secondary)' }}>
                    {fund.category.toUpperCase()}
                 </span>
                 <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', background: 'var(--accent-light)', borderRadius: 20, color: 'var(--accent)' }}>
                    DIRECT PLAN
                 </span>
              </div>
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em' }}>{fund.scheme_name}</h1>
              <p style={{ color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 14 }}>Mirae Asset Mutual Fund • {fund.risk_level || "High"} Risk</p>
           </div>
           
           <div style={{ textAlign: 'right' }}>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>CURRENT NAV ({fund.nav_date})</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                 <span style={{ fontSize: 28, fontWeight: 800 }}>
                    {fund.nav != null ? `₹${fund.nav.toFixed(2)}` : "—"}
                 </span>
                 <span style={{ fontSize: 14, fontWeight: 600, color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                    {isPositive ? "▲" : "▼"} {fund.nav_change_1d}
                 </span>
              </div>
              <a 
                href={fund.source_url} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="promo-banner-btn" 
                style={{ marginTop: 12, marginLeft: 'auto' }}
              >
                Invest Now
              </a>
           </div>
        </div>
      </section>

      {/* ── 2. Chart Section ──────────────────────────────────── */}
      <NavChart slug={fund.slug} />

      {/* ── 3. Key Metrics Grid ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 32 }}>
         {[
            { label: "Expense Ratio", value: fund.expense_ratio, sub: "Excl. GST" },
            { label: "Fund Size (AUM)", value: fund.aum ? `₹${fund.aum}` : "—", sub: "As of Mar 2026" },
            { 
               label: "Exit Load", 
               value: fund.exit_load?.match(/(\d+(?:\.\d+)?%)/)?.[0] || "1.0%", 
               sub: fund.exit_load?.match(/within (\d+ (?:days|months|year|years))/i)?.[0].replace(/within/i, "For") || "For 1 month"
            },
            { label: "Minimum SIP", value: fund.min_sip, sub: "Monthly" }
         ].map((m, i) => (
            <div key={i} style={{ background: 'var(--bg-white)', padding: 20, borderRadius: 16, border: '1px solid var(--border)' }}>
               <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>{m.label}</p>
               <p style={{ margin: '4px 0', fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{m.value || "—"}</p>
               <p style={{ margin: 0, fontSize: 11, color: 'var(--text-secondary)' }}>{m.sub}</p>
            </div>
         ))}
      </div>

      {/* ── 4. Detailed Info Split ────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 32 }}>
         <div className="detail-left">
            <HoldingsTable holdings={fund.top_holdings} totalCount={fund.holdings_count} />
            
            <div style={{ background: 'var(--bg-white)', padding: 24, borderRadius: 16, border: '1px solid var(--border)', marginBottom: 24 }}>
               <h3 style={{ margin: '0 0 16px', fontSize: 18, fontWeight: 700 }}>Investment Objective</h3>
               <p style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                  {fund.objective || "This scheme aims to generate long-term capital appreciation by investing in a diversified portfolio of stocks and equity-related securities."}
               </p>
               <div style={{ marginTop: 20, padding: 16, background: 'var(--bg-surface-2)', borderRadius: 12 }}>
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>BENCHMARK</p>
                  <p style={{ margin: '4px 0 0', fontSize: 14, fontWeight: 600 }}>{fund.benchmark || "Nifty 50 TRI"}</p>
               </div>
            </div>

            <PeerComparison peers={fund.peers} currentFundName={fund.scheme_name} />
         </div>

         <div className="detail-right">
            
            {/* Historical Return Calculator */}
            {Object.keys(fund.returns).length > 0 && (
              <ReturnCalculator returns={fund.returns} />
            )}

            {/* Returns Table */}
            <div style={{ background: 'var(--bg-white)', padding: 24, borderRadius: 16, border: '1px solid var(--border)', marginBottom: 24 }} id="sip-calculator">
               <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700 }}>Returns</h3>
               <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {Object.entries(fund.returns).map(([period, value]) => (
                     <div key={period} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{period} Annualised</span>
                        <span style={{ fontSize: 15, fontWeight: 700, color: value.startsWith('-') ? 'var(--red)' : 'var(--green)' }}>{value}</span>
                     </div>
                  ))}
                  {Object.keys(fund.returns).length === 0 && (
                     <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Historical return summary not available for this fund.</p>
                  )}
               </div>
            </div>

            {/* Fund Manager Suggestion from Mockup */}
            <div style={{ background: 'var(--accent-light)', padding: 20, borderRadius: 16, border: '1px solid var(--accent)', marginBottom: 24 }}>
               <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 700, color: 'var(--accent)' }}>Ask Assistant</h3>
               <p style={{ fontSize: 13, color: 'var(--text-primary)', margin: '0 0 16px', lineHeight: 1.5 }}>
                  &quot;What is the current sector allocation of this fund?&quot;
               </p>
               <button 
                  className="fund-card-invest-btn" 
                  style={{ width: '100%', padding: '10px' }}
                  onClick={() => {
                    const fab = document.querySelector('.chat-fab') as HTMLButtonElement;
                    if (fab) fab.click();
                  }}
               >
                  Ask Now
               </button>
            </div>
            
            {/* Fund House info */}
            <div style={{ padding: 12 }}>
               <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>FUND HOUSE</p>
               <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 40, height: 40, background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>🇲</div>
                  <div>
                     <p style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Mirae Asset Mutual Fund</p>
                     <p style={{ margin: 0, fontSize: 11, color: 'var(--text-muted)' }}>Since 2008 • ₹1.5L Cr AUM</p>
                  </div>
               </div>
            </div>

            {/* SIP Calculator */}
            <div style={{ marginTop: 24 }}>
               <SipCalculator />
            </div>
         </div>
      </div>
    </AppShell>
  );
}
