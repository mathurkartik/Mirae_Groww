/**
 * page.tsx — Home Page (Fund Explorer)
 * Replaces the original Chat interface with the "Discover Mutual Funds" landing page.
 */
"use client";

import { AppShell } from "@/components/AppShell";
import { CategoryCard } from "@/components/CategoryCard";
import { useCategories, useFunds } from "@/hooks/useFundData";

export default function Home() {
  const { categories, isLoading: catsLoading } = useCategories();

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
        <button className="filter-pill filter-pill--active">All Categories</button>
        <button className="filter-pill">High Return</button>
        <button className="filter-pill">Top Rated</button>
        <button className="filter-pill">SIP with ₹500</button>
      </div>

      <div className="category-grid">
        {catsLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton skeleton-card" />
            ))
          : categories.map((cat) => (
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
      </div>

      <section className="promo-section">
        <div className="promo-banner">
          <h2>Invest in Better Tomorrow</h2>
          <p>
            Our curator tool helps you find the perfect fund based on your risk 
            profile and goal timeline.
          </p>
          <button className="promo-banner-btn">Start Curator Survey</button>
          <div className="promo-banner-sparkle">✨</div>
        </div>

        <div className="promo-tiles">
          <div className="promo-tile">
            <div className="promo-tile-icon">🚀</div>
            <div>
              <h3>Top 10</h3>
              <p>Active Funds</p>
            </div>
          </div>
          <div className="promo-tile">
            <div className="promo-tile-icon">⚡</div>
            <div>
              <h3>New</h3>
              <p>Fund Offers</p>
            </div>
          </div>
          <div className="promo-tile">
             <div style={{ display:'flex', alignItems:'center', gap: 12, width:'100%' }}>
                <span style={{ fontSize: 18 }}>🕒</span>
                <span style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>Watchlist History</span>
                <span>›</span>
             </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
