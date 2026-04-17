/**
 * AppShell.tsx — Main layout shell
 * Renders: Left sidebar nav + Top navbar + Content area + Chat FAB
 */
"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useState, useCallback } from "react";
import { ChatWidget } from "./ChatWidget";

const NAV_ITEMS = [
  { label: "Home", icon: "🏠", href: "/" },
  { label: "Equity Funds", icon: "📈", href: "/category/equity" },
  { label: "Debt Funds", icon: "🛡️", href: "/category/debt" },
];

const TOP_LINKS: {label: string, href: string}[] = [];

import { useRouter } from "next/navigation";
import * as api from "@/lib/api";

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
        // Navigate to the first matching fund
        router.push(`/fund/${results.funds[0].slug}`);
        setSearchQuery("");
      }
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="app-layout">
      {/* ── Left Sidebar ─────────────────────────────────────── */}
      <aside className="nav-sidebar" id="sidebar-nav">
        <div className="nav-sidebar-brand">
          <div className="nav-sidebar-brand-dot">M</div>
          <div className="nav-sidebar-brand-name">
            Mirae<span>Explorer</span>
          </div>
        </div>

        <nav className="nav-sidebar-links">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`nav-link ${
                pathname === item.href && item.label === "Mutual Funds"
                  ? "nav-link--active"
                  : ""
              }`}
            >
              <span className="nav-link-icon">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="nav-sidebar-footer">
          <p className="nav-sidebar-footer-text">
            Data sourced from Groww.in
            <br />
            Facts-only. No investment advice.
          </p>
        </div>
      </aside>

      {/* ── Main area ────────────────────────────────────────── */}
      <div className="main-content">
        {/* Top Navbar */}
        <header className="top-navbar" id="top-navbar">
          <div className="top-navbar-left">
            <div className="top-navbar-links">
            </div>
          </div>

          <div className="top-navbar-right">
            <form className="top-navbar-search" id="search-bar" onSubmit={handleSearch}>
              <span className="top-navbar-search-icon">{isSearching ? "⏳" : "🔍"}</span>
              <input 
                type="text" 
                placeholder="Search funds (e.g. Health, Midcap)..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </form>
            <button className="top-navbar-icon-btn" aria-label="Notifications">
              🔔
            </button>
            <button className="top-navbar-icon-btn" aria-label="Profile">
              👤
            </button>
          </div>
        </header>

        {/* Disclaimer */}
        <div className="disclaimer-bar">
          ⚠️ <strong>Disclaimer:</strong> Mutual fund investments are subject to
          market risks. This is an info-only tool — not investment advice.
        </div>

        {/* Page content */}
        <main className="page-content">{children}</main>

        {/* Footer */}
        <footer className="site-footer">
          <div className="site-footer-brand">MiraeExplorer</div>
          <div className="site-footer-links">
            <a href="#">Terms of Service</a>
            <a href="#">Privacy Policy</a>
            <a href="#">Regulatory Disclosures</a>
            <a href="#">Help Center</a>
          </div>
          <p className="site-footer-copy">
            © 2026 MiraeExplorer. Data source: Groww.in &amp; MFAPI.in. Not
            affiliated with Mirae Asset Investment Managers.
          </p>
        </footer>
      </div>

      {/* ── Chat Widget ──────────────────────────────────────── */}
      <ChatWidget isOpen={chatOpen} onToggle={toggleChat} />
    </div>
  );
}
