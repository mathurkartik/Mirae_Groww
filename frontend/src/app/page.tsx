/**
 * page.tsx — Home Page (Fund Explorer)
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
        <h1>Discover Mutual Funds</h1>
        <p>
          Curated investment categories designed for your financial goals. 
          Smart data meets editorial precision.
        </p>
      </section>

      <div className="filter-pills">
        <button 
          className={`filter-pill ${activeTab === "categories" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("categories")}
        >
          All Categories
        </button>
        <button 
          className={`filter-pill ${activeTab === "high_return" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("high_return")}
        >
          High Return
        </button>
        <button 
          className={`filter-pill ${activeTab === "top_rated" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("top_rated")}
        >
          Top Rated
        </button>
        <button 
          className={`filter-pill ${activeTab === "sip_500" ? "filter-pill--active" : ""}`}
          onClick={() => setActiveTab("sip_500")}
        >
          SIP with ₹500
        </button>
      </div>

      <div className={activeTab === "categories" ? "category-grid" : "fund-grid"}>
        {(catsLoading || discLoading) ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={`skeleton ${activeTab === "categories" ? "skeleton-card" : "skeleton-card-slim"}`} style={{ height: activeTab === "categories" ? 220 : 160 }} />
          ))
        ) : activeTab === "categories" ? (
          categories.length === 0 ? (
            <div className="error-state" style={{ gridColumn: '1/-1', textAlign: 'center', padding: '40px 0' }}>
              <p style={{ color: 'var(--text-secondary)' }}>No categories found.</p>
            </div>
          ) : (
            categories.map((cat) => (
              <CategoryCard
                key={cat.slug}
                slug={cat.slug}
                displayName={cat.display_name}
                description={cat.description}
                icon={cat.icon}
                color={cat.color}
                fundCount={cat.fund_count}
              />
            ))
          )
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

      <section className="promo-section" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
        <div className="promo-tiles">
          <div className="promo-tile" style={{ cursor: 'pointer' }} onClick={() => setActiveTab("high_return")}>
            <div className="promo-tile-icon">🚀</div>
            <div>
              <h3>Top 10</h3>
              <p>Active Funds</p>
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {discovery?.top_10_active.slice(0, 3).map(f => (
                      <span key={f.slug} style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>• {f.scheme_name}</span>
                  ))}
              </div>
            </div>
          </div>
          <div className="promo-tile" style={{ cursor: 'pointer' }} onClick={() => setActiveTab("new_funds")}>
            <div className="promo-tile-icon">⚡</div>
            <div>
              <h3>New</h3>
              <p>Fund Offers</p>
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {discovery?.new_funds.slice(0, 3).map(f => (
                      <span key={f.slug} style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>• {f.scheme_name}</span>
                  ))}
              </div>
            </div>
          </div>
          <div className="promo-tile" onClick={() => {/* Future: Route to Watchlist page */}} style={{ cursor: 'pointer' }}>
             <div style={{ display:'flex', alignItems:'center', gap: 12, width:'100%' }}>
                <span style={{ fontSize: 18 }}>⭐</span>
                <div style={{ flex: 1 }}>
                    <h3 style={{ margin: 0, fontSize: 15 }}>Watchlist</h3>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)' }}>{watchlist.length} saved funds</p>
                </div>
                <span>›</span>
             </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
