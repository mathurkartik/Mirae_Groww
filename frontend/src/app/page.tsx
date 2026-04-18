/**
 * page.tsx — Home Page (Emerald Ledger Explorer)
 * Data-driven discovery UI with filter pills and curated lists.
 */
"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { CategoryCard } from "@/components/CategoryCard";
import { FundCard } from "@/components/FundCard";
import { useCategories, useDiscoveryFunds } from "@/hooks/useFundData";
import { useWatchlist } from "@/hooks/useWatchlist";

type Tab = "categories" | "high_return" | "top_rated" | "sip_500" | "new_funds";

export default function Home() {
  const { categories, isLoading: catsLoading } = useCategories();
  const { data: discovery, isLoading: discLoading } = useDiscoveryFunds();
  const { watchlist } = useWatchlist();
  
  const [activeTab, setActiveTab] = useState<Tab>("categories");

  return (
    <AppShell>
      <section className="home-hero">
        <h1 style={{ color: 'var(--bg-dark-green)' }}>Discover Mutual Funds</h1>
        <p>
          Curated collections of high-performance funds tailored for institutional-grade portfolios and sovereign wealth strategies.
        </p>
      </section>

      <div className="filter-pills">
        <button 
          className={`filter-pill ${activeTab === "categories" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("categories")}
        >
          ALL CATEGORIES
        </button>
        <button 
          className={`filter-pill ${activeTab === "high_return" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("high_return")}
        >
          HIGH RETURN
        </button>
        <button 
          className={`filter-pill ${activeTab === "top_rated" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("top_rated")}
        >
          TOP RATED
        </button>
        <button 
          className={`filter-pill ${activeTab === "sip_500" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("sip_500")}
        >
          SIP WITH ₹500
        </button>
      </div>

      <div className={activeTab === "categories" ? "category-grid" : "fund-grid"}>
        {(catsLoading || discLoading) ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={`skeleton ${activeTab === "categories" ? "skeleton-card" : "skeleton-card-slim"}`} style={{ height: activeTab === "categories" ? 220 : 160 }} />
          ))
        ) : activeTab === "categories" ? (
          <>
            {categories.map((cat) => (
              <CategoryCard
                key={cat.slug}
                slug={cat.slug}
                displayName={cat.display_name}
                description={cat.description}
                icon={cat.icon}
                color={cat.color}
                fundCount={cat.fund_count}
              />
            ))}
            
            {/* AI Advisor Card */}
            <div style={{ background: 'var(--bg-dark-green)', color: 'white', padding: '24px', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
               <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 800 }}>Can&apos;t decide where to invest?</h3>
               <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.6, color: '#d1fae5' }}>Let our AI Analyst analyze your risk profile and goals to recommend the perfect mix.</p>
               <button 
                  style={{ background: 'white', color: 'var(--bg-dark-green)', padding: '10px 20px', borderRadius: '30px', border: 'none', fontWeight: 700, fontSize: '13px', cursor: 'pointer', marginTop: 'auto', alignSelf: 'flex-start' }}
                  onClick={() => {
                     const fab = document.querySelector('.chat-fab') as HTMLButtonElement | null;
                     if (fab) fab.click();
                  }}
               >
                 ASK ASSISTANT
               </button>
            </div>
          </>
        ) : (
          /* Render Fund Cards for other tabs */
          (activeTab === "high_return" ? discovery?.high_return : 
           activeTab === "top_rated" ? discovery?.top_rated : 
           activeTab === "sip_500" ? discovery?.sip_affordable : 
           activeTab === "new_funds" ? discovery?.new_funds : [])?.map(fund => (
            <FundCard key={fund.slug} fund={fund} />
          ))
        )}
      </div>

      {activeTab === "categories" && (
        <section style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: '40px', marginTop: '48px' }}>
          {/* Left Column: Top 10 Active Funds */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
               <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800 }}>Top 10 Active Funds</h3>
               <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', cursor: 'pointer', letterSpacing: '0.05em' }}>FULL PERFORMANCE LIST</span>
            </div>

            <div style={{ background: 'var(--bg-white)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', overflow: 'hidden' }}>
               <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead style={{ background: 'var(--bg-surface-2)', fontSize: '11px', color: 'var(--text-muted)' }}>
                     <tr>
                        <th style={{ padding: '12px 20px', fontWeight: 700, letterSpacing: '0.05em' }}>FUND NAME</th>
                        <th style={{ padding: '12px 20px', fontWeight: 700, letterSpacing: '0.05em' }}>RATING</th>
                        <th style={{ padding: '12px 20px', fontWeight: 700, letterSpacing: '0.05em', textAlign: 'right' }}>3Y RETURNS</th>
                     </tr>
                  </thead>
                  <tbody>
                     {discovery?.top_10_active.slice(0, 5).map((fund, i) => (
                        <tr key={fund.slug} style={{ borderTop: i > 0 ? '1px solid var(--border-light)' : 'none' }}>
                           <td style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--accent-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: '12px' }}>📈</div>
                              <span style={{ fontSize: '14px', fontWeight: 600 }}>{fund.scheme_name}</span>
                           </td>
                           <td style={{ padding: '16px 20px' }}>
                             <div style={{ display: 'flex', gap: '2px', color: '#fb923c' }}>★★★★★</div>
                           </td>
                           <td style={{ padding: '16px 20px', textAlign: 'right', fontWeight: 700, color: 'var(--green)' }}>
                             +{fund.returns['3Y'] || '18.2%'}
                           </td>
                        </tr>
                     ))}
                  </tbody>
               </table>
            </div>

            {/* Footer Links */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginTop: '64px', fontSize: '13px', color: 'var(--text-secondary)' }}>
               <div>
                 <h4 style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '16px', letterSpacing: '0.05em' }}>INVESTMENTS</h4>
                 <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <span>Direct Equity</span><span>Mutual Funds</span><span>Digital Gold</span>
                 </div>
               </div>
               <div>
                 <h4 style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '16px', letterSpacing: '0.05em' }}>INSIGHTS</h4>
                 <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <span>Daily Market View</span><span>Analyst Reports</span><span>Wealth Academy</span>
                 </div>
               </div>
               <div>
                 <h4 style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '16px', letterSpacing: '0.05em' }}>COMPANY</h4>
                 <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                    <span>About Us</span><span>Careers</span><span>Media Kit</span>
                 </div>
               </div>
               <div>
                 <h4 style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '16px', letterSpacing: '0.05em' }}>LEGAL</h4>
                 <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
                    <span>Privacy Policy</span><span>Terms of Use</span><span>SEBI Disclosure</span>
                 </div>
               </div>
            </div>

            <div style={{ marginTop: '40px', padding: '24px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius)', fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.6 }}>
               Disclaimer: Mutual Fund investments are subject to market risks, read all scheme related documents carefully. Past performance is not an indicator of future returns. The "Emerald Ledger" AI Assistant provides automated analytical data based on historical patterns and does not constitute official financial advice.
               <div style={{ marginTop: '16px', fontWeight: 700, color: 'var(--accent-dark)', fontSize: '14px' }}>Emerald Ledger</div>
               <div>© 2024 Emerald Ledger Capital Management Ltd.</div>
            </div>

          </div>

          {/* Right Column: NFO & Watchlist */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
             
             <div>
                <h3 style={{ margin: '0 0 16px', fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>NEW FUND OFFERS (NFO)</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px', background: 'var(--bg-white)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                     <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--accent)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✓</div>
                     <div style={{ flex: 1 }}>
                        <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>Nexus Tech Advantage</h4>
                        <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)' }}>Open until Oct 15</p>
                     </div>
                     <span style={{ fontSize: '18px', color: 'var(--text-muted)' }}>›</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px', background: 'var(--bg-white)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                     <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--text-secondary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🏛️</div>
                     <div style={{ flex: 1 }}>
                        <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>ESG Sovereign Lead...</h4>
                        <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)' }}>Open until Oct 28</p>
                     </div>
                     <span style={{ fontSize: '18px', color: 'var(--text-muted)' }}>›</span>
                  </div>
                </div>
             </div>

             <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                   <h3 style={{ margin: 0, fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>WATCHLIST</h3>
                   <span style={{ width: '20px', height: '20px', borderRadius: '50%', background: 'var(--bg-surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', cursor: 'pointer' }}>+</span>
                </div>
                <div style={{ background: 'var(--bg-white)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                   {watchlist.length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)' }}>Your watchlist is empty</div>
                   ) : (
                      watchlist.map((fw, i) => (
                         <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', borderBottom: i < watchlist.length - 1 ? '1px solid var(--border-light)' : 'none' }}>
                            <div>
                               <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>{fw.scheme_name || "HDFC Top 100"}</h4>
                               <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-secondary)' }}>{fw.category || "Equity: Large Cap"}</p>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                               <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>₹{fw.nav || "248.42"}</h4>
                               <p style={{ margin: 0, fontSize: '11px', color: 'var(--green)', fontWeight: 700 }}>{fw.nav_change_1d || "+1.2%"}</p>
                            </div>
                         </div>
                      ))
                   )}
                </div>
             </div>
          </div>
        </section>
      )}
    </AppShell>
  );
}
