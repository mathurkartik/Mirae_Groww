/**
 * AppShell.tsx — Emerald Ledger Layout
 * Renders Dual Layout based on context:
 * 1. Global View (Home, Explore)
 * 2. Fund Detail View (Specialized sidebar + top nav)
 */
"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useState, useCallback } from "react";
import { ChatWidget } from "./ChatWidget";
import * as api from "@/lib/api";

const GLOBAL_NAV = [
  { label: "Explore", icon: "🌐", href: "/" },
  { label: "Investments", icon: "🏛️", href: "#" },
  { label: "SIP Dashboard", icon: "📅", href: "#" },
  { label: "Watchlist", icon: "🔖", href: "#" },
  { label: "Reports", icon: "📊", href: "#" },
];

const FUND_SIDEBAR_NAV = [
  { label: "OVERVIEW", icon: "📊" },
  { label: "PERFORMANCE", icon: "📈", active: true },
  { label: "HOLDINGS", icon: "🥧" },
  { label: "RISK METRICS", icon: "🛡️" },
  { label: "CALCULATORS", icon: "🧮" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [chatOpen, setChatOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  const toggleChat = useCallback(() => setChatOpen((v) => !v), []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await api.searchFunds(searchQuery);
      if (results.funds.length > 0) {
        router.push(`/fund/${results.funds[0].slug}`);
        setSearchQuery("");
      }
    } finally {
      setIsSearching(false);
    }
  };

  const isFundPage = pathname.includes('/fund/');

  if (isFundPage) {
    return (
      <div className="app-layout" style={{ flexDirection: 'column' }}>
        {/* Full Width Top Nav */}
        <header style={{ height: '64px', background: 'var(--bg-white)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', position: 'sticky', top: 0, zIndex: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--accent-dark)', letterSpacing: '-0.02em' }}>Emerald Ledger</div>
            <div style={{ display: 'flex', gap: '20px', fontSize: '14px', fontWeight: 500, color: 'var(--text-secondary)' }}>
              <span style={{ cursor: 'pointer' }}>Markets</span>
              <span style={{ cursor: 'pointer', color: 'var(--accent)', borderBottom: '2px solid var(--accent)' }}>Funds</span>
              <span style={{ cursor: 'pointer' }}>Insights</span>
              <span style={{ cursor: 'pointer' }}>Institutional</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer' }}>Support</span>
            <button style={{ background: 'var(--accent)', color: 'white', border: 'none', padding: '8px 20px', borderRadius: '30px', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>Invest Now</button>
          </div>
        </header>

        {/* Content Wrapper */}
        <div style={{ display: 'flex', flex: 1, position: 'relative' }}>
          {/* specialized fund sidebar */}
          <aside style={{ width: '240px', background: 'var(--bg-white)', borderRight: '1px solid var(--border)', padding: '24px 0', display: 'flex', flexDirection: 'column', position: 'fixed', top: '64px', bottom: 0 }}>
             <div style={{ padding: '0 24px', marginBottom: '32px' }}>
                <div style={{ width: '32px', height: '32px', background: 'var(--bg-surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '12px', marginBottom: '12px', color: 'var(--accent-dark)' }}>MA</div>
                <h3 style={{ margin: '0 0 4px', fontSize: '16px', fontWeight: 800 }}>Mirae Asset</h3>
                <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800, letterSpacing: '0.05em' }}>DEEP DIVE ANALYST</p>
             </div>
             
             <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {FUND_SIDEBAR_NAV.map((item) => (
                  <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 24px', fontSize: '12px', fontWeight: 700, cursor: 'pointer', color: item.active ? 'var(--accent)' : 'var(--text-secondary)', background: item.active ? 'var(--accent-light)' : 'transparent', borderRight: item.active ? '3px solid var(--accent)' : '3px solid transparent' }}>
                    <span style={{ fontSize: '16px' }}>{item.icon}</span>
                    {item.label}
                  </div>
                ))}
             </nav>

             <div style={{ marginTop: 'auto', padding: '0 20px' }}>
                <div style={{ background: 'var(--bg-dark-green)', borderRadius: '12px', padding: '20px', color: 'white' }}>
                   <p style={{ margin: '0 0 8px', fontSize: '10px', fontWeight: 800, letterSpacing: '0.05em' }}>AI RECOMMENDATION</p>
                   <p style={{ margin: '0 0 16px', fontSize: '12px', color: '#e2e8f0' }}>Optimize your tax-saving portfolio for FY 24-25.</p>
                   <button style={{ width: '100%', padding: '8px', border: 'none', background: 'var(--accent)', color: 'white', borderRadius: '6px', fontSize: '12px', fontWeight: 700, cursor: 'pointer' }} onClick={toggleChat}>AI ADVISOR</button>
                </div>
                <div style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px', paddingLeft: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', cursor: 'pointer' }}><span>📄</span> REPORTS</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', cursor: 'pointer' }}><span>⚙️</span> SETTINGS</div>
                </div>
             </div>
          </aside>

          <main style={{ marginLeft: '240px', flex: 1, padding: '40px 48px', maxWidth: '1200px' }}>
             {children}
          </main>
        </div>

        <ChatWidget isOpen={chatOpen} onToggle={toggleChat} />
      </div>
    );
  }

  // GLOBAL LAYOUT
  return (
    <div className="app-layout">
      {/* ── Left Sidebar ─────────────────────────────────────── */}
      <aside className="nav-sidebar" id="sidebar-nav" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="nav-sidebar-brand" style={{ flexDirection: 'column', alignItems: 'flex-start', borderBottom: 'none', padding: '24px' }}>
          <div className="nav-sidebar-brand-name" style={{ color: 'var(--accent-dark)', fontSize: '18px' }}>
            Emerald Ledger
          </div>
          <p style={{ margin: '4px 0 0', fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800, letterSpacing: '0.05em' }}>SOVEREIGN ANALYST</p>
        </div>

        <nav className="nav-sidebar-links" style={{ marginTop: '16px' }}>
          {GLOBAL_NAV.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`nav-link ${pathname === item.href || (pathname.includes('/category/') && item.label==='Explore') ? "nav-link--active" : ""}`}
              style={pathname === item.href || (pathname.includes('/category/') && item.label==='Explore') ? { borderRight: '3px solid var(--accent)', borderRadius: '0' } : {}}
            >
              <span className="nav-link-icon">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div style={{ marginTop: 'auto', padding: '20px' }}>
           <button onClick={toggleChat} style={{ width: '100%', padding: '12px', background: 'var(--accent)', color: 'white', borderRadius: '30px', border: 'none', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: 'pointer', marginBottom: '24px' }}>
             ✨ AI Assistant
           </button>
           <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingLeft: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', cursor: 'pointer' }}><span>⚙️</span> Settings</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', cursor: 'pointer' }}><span>❓</span> Support</div>
           </div>
        </div>

        <div style={{ padding: '20px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '12px' }}>
           <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: 'var(--accent-dark)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>👨‍💼</div>
           <div>
              <p style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>Alex Mercer</p>
              <p style={{ margin: 0, fontSize: '11px', color: 'var(--accent)', fontWeight: 800 }}>PRO TIER</p>
           </div>
        </div>
      </aside>

      {/* ── Main area ────────────────────────────────────────── */}
      <div className="main-content">
        {/* Top Navbar */}
        <header className="top-navbar" id="top-navbar" style={{ padding: '0 24px' }}>
          <div className="top-navbar-left">
             <form className="top-navbar-search" id="search-bar" onSubmit={handleSearch} style={{ width: '300px', background: 'var(--bg-surface-2)', borderRadius: '30px', border: 'none' }}>
               <span className="top-navbar-search-icon">{isSearching ? "⏳" : "🔍"}</span>
               <input 
                 type="text" 
                 placeholder="Search direct funds, ETFs, or gold..." 
                 value={searchQuery}
                 onChange={(e) => setSearchQuery(e.target.value)}
                 style={{ background: 'transparent' }}
               />
             </form>
          </div>

          <div className="top-navbar-right" style={{ gap: '24px' }}>
            <div className="top-navbar-links" style={{ display: 'flex', gap: '20px', fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
               <span style={{ color: 'var(--text-primary)', borderBottom: '2px solid var(--accent)', paddingBottom: '23px', marginBottom: '-24px', cursor: 'pointer' }}>DIRECT FUNDS</span>
               <span style={{ cursor: 'pointer' }}>ETFS</span>
               <span style={{ cursor: 'pointer' }}>GOLD</span>
               <span style={{ cursor: 'pointer' }}>FIXED INCOME</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginLeft: '16px' }}>
               <span style={{ fontSize: '16px', color: 'var(--text-secondary)', cursor: 'pointer' }}>🔔</span>
               <span style={{ fontSize: '16px', color: 'var(--text-secondary)', cursor: 'pointer' }}>📺</span>
               <button style={{ background: 'var(--accent)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '30px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>Invest Now</button>
            </div>
          </div>
        </header>

        <main className="page-content">{children}</main>

      </div>

      <ChatWidget isOpen={chatOpen} onToggle={toggleChat} />
    </div>
  );
}
