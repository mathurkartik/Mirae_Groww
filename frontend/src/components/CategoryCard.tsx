/**
 * CategoryCard.tsx — Category grid card
 * Displays a fund category with icon, description, fund count, and "View All" link.
 */
import Link from "next/link";

interface CategoryCardProps {
  slug: string;
  displayName: string;
  description: string;
  icon: string;
  color: string;
  fundCount: number;
}

const ICON_MAP: Record<string, string> = {
  "trending-up": "📈",
  layers: "🏗️",
  "bar-chart": "📊",
  shield: "🛡️",
  calendar: "📅",
};

export function CategoryCard({
  slug,
  displayName,
  description,
  icon,
  color,
  fundCount,
}: CategoryCardProps) {
  return (
    <Link href={`/category/${slug}`} style={{ textDecoration: "none" }}>
      <div className="category-card" id={`category-${slug}`}>
        <div
          className="category-card-icon"
          style={{ background: `${color}15`, color }}
        >
          {ICON_MAP[icon] || "📁"}
        </div>
        <h3 className="category-card-title">{displayName}</h3>
        <p className="category-card-desc">{description}</p>
        <div className="category-card-footer">
          <div className="category-card-count">
            <strong>{fundCount}</strong>
            <br />
            FUNDS
          </div>
          <span className="category-card-link">
            View All <span>→</span>
          </span>
        </div>
      </div>
    </Link>
  );
}
