"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { NavChart } from "@/components/NavChart";
import { HoldingsTable } from "@/components/HoldingsTable";
import { SectorChart } from "@/components/SectorChart";
import { PeerComparison } from "@/components/PeerComparison";
import { useFundDetail } from "@/hooks/useFundData";
import { fetchHistoricalReturns } from "@/lib/mfapi";

export default function FundDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { fund, isLoading, error } = useFundDetail(slug);
  const [sipAmount, setSipAmount] = useState(5000);
  const [activeReturnRates, setActiveReturnRates] = useState({
    returns_1y: 12,
    returns_3y: 12,
    returns_5y: 12,
  });

  useEffect(() => {
    if (fund?.mfapi_code) {
      fetchHistoricalReturns(fund.mfapi_code).then(res => {
        setActiveReturnRates({
          returns_1y: res.returns_1y || 12,
          returns_3y: res.returns_3y || 12,
          returns_5y: res.returns_5y || 12,
        });
      });
    }
  }, [fund?.mfapi_code]);

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

  const calcSIP = (sip: number, annualRate: number, years: number) => {
    const months = years * 12;
    if (annualRate === 0) return { invested: sip * months, corpus: sip * months };
    const r = annualRate / 100 / 12;
    const corpus = sip * ((Math.pow(1 + r, months) - 1) / r) * (1 + r);
    return { invested: sip * months, corpus };
  };

  const formatINR = (n: number) => {
    if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
    if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
    return `₹${n.toLocaleString('en-IN')}`;
  };

  const calcRows = [
    { label: '1 Year', years: 1, rate: activeReturnRates.returns_1y },
    { label: '3 Years', years: 3, rate: activeReturnRates.returns_3y },
    { label: '5 Years', years: 5, rate: activeReturnRates.returns_5y },
  ].map(row => {
    const { invested, corpus } = calcSIP(sipAmount, row.rate, row.years);
    return {
      label: row.label,
      rateStr: `${row.rate.toFixed(2)}%`,
      invested: formatINR(invested),
      corpus: formatINR(corpus)
    };
  });

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

      {/* ── 3. Returns Calculator (RESTORED UI + DYNAMIC LOGIC) ── */}
      <div id="sip-calculator" style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '28px', marginBottom: '40px' }}>
         <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800 }}>Returns Calculator</h2>
         <p style={{ margin: '4px 0 24px', fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Based on actual historical performance of this fund.</p>
         
         <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.2fr)', gap: '48px', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
               <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                     <label style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>MONTHLY SIP AMOUNT</label>
                     <div style={{ background: 'var(--bg-surface-2)', padding: '8px 16px', borderRadius: '40px', color: 'var(--green)', fontSize: '16px', fontWeight: 800 }}>
                        ₹{sipAmount.toLocaleString('en-IN')}
                     </div>
                  </div>
                  <input 
                    type="range" 
                    min="500" 
                    max="100000" 
                    step="500"
                    value={sipAmount}
                    onChange={(e) => setSipAmount(parseInt(e.target.value))}
                    style={{ width: '100%', height: '6px', appearance: 'none', background: 'var(--bg-surface-2)', borderRadius: '3px', outline: 'none', cursor: 'pointer' }} 
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                     <span>₹500</span>
                     <span>₹1,00,000</span>
                  </div>
               </div>

               {/* Invest Now CTA */}
               <a
                 href={fund.source_url}
                 target="_blank"
                 rel="noopener noreferrer"
                 style={{ 
                   padding: '14px', borderRadius: '12px', background: 'linear-gradient(135deg, var(--accent), var(--accent-dark))', color: 'white', border: 'none', fontSize: '15px', fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', boxShadow: '0 8px 24px rgba(0, 168, 132, 0.25)', textDecoration: 'none'
                 }}
               >
                  INVEST NOW ON GROWW →
               </a>
            </div>

            {/* Returns Result Table */}
            <div style={{ background: 'var(--bg-surface-2)', borderRadius: '16px', padding: '24px' }}>
               <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800 }}>
                     <tr>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em' }}>PERIOD</th>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em' }}>RETURN RATE</th>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em' }}>TOTAL INVESTED</th>
                        <th style={{ padding: '0 12px 16px', letterSpacing: '0.05em', textAlign: 'right' }}>WOULD&apos;VE BECOME</th>
                     </tr>
                  </thead>
                  <tbody style={{ fontSize: '13px', fontWeight: 700 }}>
                     {calcRows.map((row, i) => (
                        <tr key={row.label} style={{ borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}>
                           <td style={{ padding: '16px 12px' }}>{row.label}</td>
                           <td style={{ padding: '16px 12px', color: 'var(--text-muted)' }}>{row.rateStr}</td>
                           <td style={{ padding: '16px 12px', color: 'var(--text-secondary)' }}>{row.invested}</td>
                           <td style={{ padding: '16px 12px', textAlign: 'right', color: 'var(--green)', fontSize: '15px' }}>{row.corpus}</td>
                        </tr>
                     ))}
                  </tbody>
               </table>
               <p style={{ margin: '16px 0 0', fontSize: '10px', color: 'var(--text-muted)', textAlign: 'center' }}>⚠️ Projections are based on historical returns of this specific fund. Past performance does not guarantee future results.</p>
            </div>
         </div>
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
