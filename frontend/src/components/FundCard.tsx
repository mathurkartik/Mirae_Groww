/**
 * FundCard.tsx — Fund summary card
 * Displays key metrics: name, category, 3Y return, expense ratio, AUM, risk.
 * Links to fund detail page and Groww for "Invest Now".
 */
import Link from "next/link";

export interface FundSummary {
  slug: string;
  scheme_name: string;
  category: string;
  category_slug: string;
  source_url: string;
  mfapi_code: number | null;
  nav: number | null;
  nav_date: string | null;
  nav_change_1d: string | null;
  aum: string | null;
  expense_ratio: string | null;
  rating: number | null;
  min_sip: string | null;
  risk_level: string | null;
  returns_3y_annualized: string | null;
  returns: Record<string, string>;
}

interface FundCardProps {
  fund: FundSummary;
}

export function FundCard({ fund }: FundCardProps) {
  const ret3y = fund.returns_3y_annualized;
  const isPositive = ret3y ? !ret3y.startsWith("-") : true;

  return (
    <div className="fund-card" id={`fund-${fund.slug}`}>
      <Link
        href={`/fund/${fund.slug}`}
        style={{ textDecoration: "none", color: "inherit" }}
      >
        <div className="fund-card-header">
          <div className="fund-card-info">
            <h3 className="fund-card-name">{fund.scheme_name}</h3>
            <p className="fund-card-category">
              {fund.category} • Direct Plan
            </p>
          </div>
          <div className="fund-card-return">
            <p
              className={`fund-card-return-value ${
                isPositive ? "positive" : "negative"
              }`}
            >
              {ret3y || "—"}
            </p>
            <span className="fund-card-return-label">3Y Annualised</span>
          </div>
        </div>

        <div className="fund-card-metrics">
          <div className="fund-card-metric">
            <p className="fund-card-metric-label">Expense Ratio</p>
            <p className="fund-card-metric-value">
              {fund.expense_ratio || "—"}
            </p>
          </div>
          <div className="fund-card-metric">
            <p className="fund-card-metric-label">AUM</p>
            <p className="fund-card-metric-value">
              {fund.aum ? `₹${fund.aum}` : "—"}
            </p>
          </div>
          <div className="fund-card-metric">
            <p className="fund-card-metric-label">Risk Level</p>
            <p className="fund-card-metric-value">
              {fund.risk_level || "—"}
            </p>
          </div>
        </div>
      </Link>

      <div className="fund-card-footer">
        <div className="fund-card-rating">
          {fund.rating && fund.rating > 0 ? (
            <span
              className="fund-card-rating-badge"
              style={{
                background: "#e6f9f3",
                color: "#00b386",
              }}
            >
              ★ {fund.rating}
            </span>
          ) : (
            <span style={{ fontSize: 12, color: "#94a3b8" }}>—</span>
          )}
        </div>
        <a
          href={fund.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="fund-card-invest-btn"
          onClick={(e) => e.stopPropagation()}
        >
          Invest Now
        </a>
      </div>
    </div>
  );
}
