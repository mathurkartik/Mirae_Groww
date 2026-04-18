/**
 * category/[slug]/page.tsx — Category Fund List (Emerald Ledger)
 * Displays a list of funds for a specific category with filtering and sorting.
 */
"use client";

import { use } from "react";
import { AppShell } from "@/components/AppShell";
import { FundCard } from "@/components/FundCard";
import { useCategoryDetail } from "@/hooks/useFundData";
import { useState, useMemo } from "react";

export default function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { data, isLoading, error } = useCategoryDetail(slug);
  const [sortBy, setSortBy] = useState("returns");

  const sortedFunds = useMemo(() => {
    if (!data?.funds) return [];
    const funds = [...data.funds];
    
    if (sortBy === "returns") {
      return funds.sort((a, b) => {
        const valA = parseFloat((a.returns_3y_annualized || "0").replace("%", "").replace("+", ""));
        const valB = parseFloat((b.returns_3y_annualized || "0").replace("%", "").replace("+", ""));
        return valB - valA;
      });
    } else if (sortBy === "aum") {
      return funds.sort((a, b) => {
        const valA = parseFloat((a.aum || "0").replace(",", "").replace(" Cr", ""));
        const valB = parseFloat((b.aum || "0").replace(",", "").replace(" Cr", ""));
        return valB - valA;
      });
    } else if (sortBy === "name") {
      return funds.sort((a, b) => a.scheme_name.localeCompare(b.scheme_name));
    }
    
    return funds;
  }, [data, sortBy]);

  return (
    <AppShell>
      <div className="category-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          INVESTMENTS / <span style={{ color: 'var(--accent)' }}>{slug.replace('-', ' ')} MUTUAL FUNDS</span>
        </div>
        {isLoading ? (
          <div className="skeleton" style={{ height: 40, width: 300, marginBottom: 8 }} />
        ) : (
          <h1 style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '12px' }}>
            {data?.category.display_name} Mutual Funds
          </h1>
        )}
        
        {isLoading ? (
          <div className="skeleton" style={{ height: 48, width: "100%", maxWidth: 600 }} />
        ) : (
          <p style={{ fontSize: '15px', color: 'var(--text-secondary)', maxWidth: '650px', lineHeight: '1.7' }}>
            {data?.category.description || "Curated high-growth equity portfolios for long-term wealth appreciation through surgical asset allocation."}
          </p>
        )}
      </div>

      {/* Market Sentiment Banner */}
      <section style={{ 
        background: 'rgba(5, 150, 105, 0.08)', 
        border: '1px solid rgba(5, 150, 105, 0.2)', 
        borderRadius: 'var(--radius-lg)', 
        padding: '32px', 
        marginTop: '32px', 
        marginBottom: '32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '40px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ 
            width: '48px', 
            height: '48px', 
            borderRadius: '12px', 
            background: 'var(--accent-light)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            fontSize: '24px'
          }}>📈</div>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: 'var(--accent-dark)' }}>Market Sentiment: Bullish •</h2>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '450px' }}>
              Institutional flows indicate strong momentum in Large-cap and specialized Technology sectors.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '48px' }}>
          <div>
            <p style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 4px' }}>NIFTY 50</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px', fontWeight: 800 }}>22,356.10</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--green)' }}>+1.45%</span>
            </div>
          </div>
          <div>
            <p style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 4px' }}>SENSEX</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px', fontWeight: 800 }}>73,651.35</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--green)' }}>+1.32%</span>
            </div>
          </div>
        </div>
      </section>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '12px', 
            fontWeight: 700, 
            background: 'var(--bg-dark-green)', 
            color: 'white', 
            border: 'none',
            cursor: 'pointer'
          }}>MIRAE ASSET PICKS</button>
          <button style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '12px', 
            fontWeight: 700, 
            background: 'var(--bg-surface-2)', 
            color: 'var(--text-secondary)', 
            border: 'none',
            cursor: 'pointer'
          }}>LARGE CAP</button>
          <button style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '12px', 
            fontWeight: 700, 
            background: 'var(--bg-surface-2)', 
            color: 'var(--text-secondary)', 
            border: 'none',
            cursor: 'pointer'
          }}>MID CAP</button>
          <button style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '12px', 
            fontWeight: 700, 
            background: 'var(--bg-surface-2)', 
            color: 'var(--text-secondary)', 
            border: 'none',
            cursor: 'pointer'
          }}>SMALL CAP</button>
          <button style={{ 
            padding: '8px 16px', 
            borderRadius: '20px', 
            fontSize: '12px', 
            fontWeight: 700, 
            background: 'var(--bg-surface-2)', 
            color: 'var(--text-secondary)', 
            border: 'none',
            cursor: 'pointer'
          }}>TAX SAVER (ELSS)</button>
        </div>
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
           <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>SORT BY:</span>
           <select 
             className="sort-select" 
             value={sortBy} 
             onChange={(e) => setSortBy(e.target.value)}
             style={{ 
               padding: '8px 12px', 
               borderRadius: '8px', 
               border: '1px solid var(--border)', 
               fontSize: '13px', 
               fontWeight: 600,
               background: 'var(--bg-white)',
               color: 'var(--text-primary)',
               outline: 'none',
               cursor: 'pointer'
             }}
           >
             <option value="returns">Best 3Y Returns</option>
             <option value="aum">Largest AUM</option>
             <option value="name">Alphabetical</option>
           </select>
        </div>
      </div>

      <div className="fund-grid">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="skeleton skeleton-card" style={{ height: '300px' }} />
            ))
          : sortedFunds.map((fund) => (
              <FundCard key={fund.slug} fund={fund} />
            ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', marginTop: '48px', marginBottom: '64px' }}>
         <button style={{ 
           padding: '12px 32px', 
           borderRadius: '30px', 
           border: '1px solid var(--border)', 
           background: 'var(--bg-white)', 
           fontSize: '13px', 
           fontWeight: 700,
           color: 'var(--text-primary)',
           cursor: 'pointer',
           display: 'flex',
           alignItems: 'center',
           gap: '8px'
         }}>
           LOAD MORE PICKS <span>⌄</span>
         </button>
      </div>

      {error && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--red)' }}>
           <h3>Error loading category</h3>
           <p>{error}</p>
        </div>
      )}

      {!isLoading && sortedFunds.length === 0 && !error && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
           <h3>No funds found in this category</h3>
        </div>
      )}
    </AppShell>
  );
}
