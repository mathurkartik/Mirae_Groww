/**
 * category/[slug]/page.tsx — Category Fund List
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
        {isLoading ? (
          <div className="skeleton" style={{ height: 32, width: 240, marginBottom: 8 }} />
        ) : (
          <h1>{data?.category.display_name} Mutual Funds</h1>
        )}
        
        {isLoading ? (
          <div className="skeleton" style={{ height: 48, width: "100%", maxWidth: 600 }} />
        ) : (
          <p>{data?.category.description}</p>
        )}
      </div>

      <div className="category-controls">
        <div className="category-count">
          {isLoading ? (
            <span className="skeleton" style={{ display: 'inline-block', width: 80, height: 18 }} />
          ) : (
            <>Explore our top Mirae Asset picks with <strong>{data?.funds.length} funds</strong></>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
           <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sort by:</span>
           <select 
             className="sort-select" 
             value={sortBy} 
             onChange={(e) => setSortBy(e.target.value)}
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
              <div key={i} className="skeleton skeleton-card" />
            ))
          : sortedFunds.map((fund) => (
              <FundCard key={fund.slug} fund={fund} />
            ))}
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

      {/* Market Sentiment Banner from Mockup */}
      <section className="promo-banner" style={{ marginTop: 40, height: 180, justifyContent: 'center' }}>
         <h2>Market Sentiment: Bullish</h2>
         <p>The large-cap segment is showing strong resistance levels with technical indicators suggesting growth.</p>
         <div style={{ display:'flex', gap: 24, marginTop: 12 }}>
            <div>
               <p style={{ fontSize: 11, opacity: 0.7, textTransform:'uppercase' }}>NIFTY 50</p>
               <p style={{ fontWeight: 700 }}>+1.24%</p>
            </div>
            <div>
               <p style={{ fontSize: 11, opacity: 0.7, textTransform:'uppercase' }}>SENSEX</p>
               <p style={{ fontWeight: 700 }}>+0.98%</p>
            </div>
         </div>
      </section>
    </AppShell>
  );
}
