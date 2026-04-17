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
  { label: "Dashboard", icon: "📊", href: "/" },
  { label: "Mutual Funds", icon: "💰", href: "/" },
  { label: "Explore", icon: "🔍", href: "/" },
];

const TOP_LINKS = [
  { label: "Explore", href: "/" },
  { label: "Investments", href: "/" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [chatOpen, setChatOpen] = useState(false);

  const toggleChat = useCallback(() => setChatOpen((v) => !v), []);

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
              {TOP_LINKS.map((link) => (
                <Link
                  key={link.label}
                  href={link.href}
                  className={`top-navbar-link ${
                    pathname === link.href ? "top-navbar-link--active" : ""
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>

          <div className="top-navbar-right">
            <div className="top-navbar-search" id="search-bar">
              <span className="top-navbar-search-icon">🔍</span>
              <input type="text" placeholder="Search funds..." />
            </div>
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
