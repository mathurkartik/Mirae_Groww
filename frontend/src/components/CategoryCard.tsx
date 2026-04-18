/**
 * CategoryCard.tsx — Category grid card (Emerald Ledger Redesign)
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
      <div className="category-card" id={`category-${slug}`} style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: '16px', padding: '28px', cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: `${color}15`,
            color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '22px',
          }}
        >
          {ICON_MAP[icon] || "📁"}
        </div>
        <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)' }}>{displayName}</h3>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, flex: 1 }}>{description}</p>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)' }}>
            <strong style={{ fontSize: '16px', color: 'var(--text-primary)', fontWeight: 800 }}>{fundCount}</strong> FUNDS
          </span>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            VIEW ALL <span>→</span>
          </span>
        </div>
      </div>
    </Link>
  );
}
