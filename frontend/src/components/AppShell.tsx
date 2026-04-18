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
];

const FUND_SIDEBAR_NAV = [
  { label: "OVERVIEW", icon: "📊", target: "top" },
  { label: "PERFORMANCE", icon: "📈", target: "top", active: true },
  { label: "HOLDINGS", icon: "🥧", target: "holdings" },
  { label: "RISK METRICS", icon: "🛡️", target: "risk" },
  { label: "CALCULATORS", icon: "🧮", target: "sip-calculator" },
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
        <header style={{ height: '60px', background: 'var(--bg-white)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 32px', position: 'sticky', top: 0, zIndex: 40 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
            <Link href="/" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--accent-dark)', textDecoration: 'none', letterSpacing: '-0.02em' }}>Emerald Ledger</Link>
            <Link href="/" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--accent)', textDecoration: 'none' }}>Funds</Link>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button onClick={toggleChat} style={{ background: 'none', border: '1px solid var(--border)', padding: '6px 14px', borderRadius: '30px', fontSize: '13px', fontWeight: 600, cursor: 'pointer', color: 'var(--text-secondary)' }}>✨ AI Advisor</button>
          </div>
        </header>

        {/* Content Wrapper */}
        <div style={{ display: 'flex', flex: 1, position: 'relative' }}>
          {/* Specialized fund sidebar */}
          <aside style={{ width: '220px', background: 'var(--bg-white)', borderRight: '1px solid var(--border)', padding: '24px 0', display: 'flex', flexDirection: 'column', position: 'fixed', top: '60px', bottom: 0, overflowY: 'auto' }}>
             <div style={{ padding: '0 20px', marginBottom: '24px' }}>
                <div style={{ width: '32px', height: '32px', background: 'var(--bg-surface-2)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '12px', marginBottom: '10px', color: 'var(--accent-dark)' }}>MA</div>
                <h3 style={{ margin: '0 0 2px', fontSize: '15px', fontWeight: 800 }}>Mirae Asset</h3>
                <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-muted)', fontWeight: 800, letterSpacing: '0.05em' }}>FUND ANALYSIS</p>
             </div>
             
             <nav style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {FUND_SIDEBAR_NAV.map((item) => (
                  <div
                    key={item.label}
                    onClick={() => {
                      const el = document.getElementById(item.target);
                      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 20px',
                      fontSize: '11px', fontWeight: 700, cursor: 'pointer',
                      color: item.active ? 'var(--accent)' : 'var(--text-secondary)',
                      background: item.active ? 'var(--accent-light)' : 'transparent',
                      borderRight: item.active ? '3px solid var(--accent)' : '3px solid transparent',
                    }}
                  >
                    <span style={{ fontSize: '14px' }}>{item.icon}</span>
                    {item.label}
                  </div>
                ))}
             </nav>

             <div style={{ marginTop: 'auto', padding: '0 16px' }}>
                <div style={{ background: 'var(--bg-dark-green)', borderRadius: '12px', padding: '16px', color: 'white' }}>
                   <p style={{ margin: '0 0 8px', fontSize: '10px', fontWeight: 800, letterSpacing: '0.05em' }}>AI RECOMMENDATION</p>
                   <p style={{ margin: '0 0 12px', fontSize: '11px', color: '#e2e8f0', lineHeight: 1.5 }}>Get AI insights on this fund.</p>
                   <button style={{ width: '100%', padding: '8px', border: 'none', background: 'var(--accent)', color: 'white', borderRadius: '6px', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }} onClick={toggleChat}>AI ADVISOR</button>
                </div>
             </div>
          </aside>

          <main style={{ marginLeft: '220px', flex: 1, padding: '32px 40px', maxWidth: '1100px' }}>
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
          <Link href="/" className="nav-sidebar-brand-name" style={{ color: 'var(--accent-dark)', fontSize: '18px', textDecoration: 'none' }}>
            Emerald Ledger
          </Link>
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
        </div>

        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '12px' }}>
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
                 placeholder="Search direct funds..." 
                 value={searchQuery}
                 onChange={(e) => setSearchQuery(e.target.value)}
                 style={{ background: 'transparent' }}
               />
             </form>
          </div>

          <div className="top-navbar-right" style={{ gap: '16px' }}>
            <span style={{ fontSize: '16px', color: 'var(--text-secondary)', cursor: 'pointer' }}>🔔</span>
            <button style={{ background: 'var(--accent)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '30px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>Invest Now</button>
          </div>
        </header>

        <main className="page-content">{children}</main>

      </div>

      <ChatWidget isOpen={chatOpen} onToggle={toggleChat} />
    </div>
  );
}
