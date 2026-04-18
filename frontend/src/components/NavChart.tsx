/**
 * NavChart.tsx — Interactive NAV Chart
 * Uses Recharts to display historical price series with period toggles.
 * No duplicate title — parent controls the heading.
 */
"use client";

import { useState } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import { useNavHistory } from "@/hooks/useFundData";

interface NavChartProps {
  slug: string;
}

const PERIODS = [
  { label: "1M", value: "1M" },
  { label: "6M", value: "6M" },
  { label: "1Y", value: "1Y" },
  { label: "3Y", value: "3Y" },
  { label: "5Y", value: "5Y" },
  { label: "All", value: "ALL" },
];

export function NavChart({ slug }: NavChartProps) {
  const [period, setPeriod] = useState("1Y");
  const { history, isLoading, error } = useNavHistory(slug, period);

  if (error) {
    return (
      <div style={{ height: 300, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-secondary)', background:'var(--bg-surface-2)', borderRadius: 12 }}>
         <p>NAV history data currently unavailable</p>
      </div>
    );
  }

  return (
    <div>
      {/* Period Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px' }}>
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            style={{
              padding: '4px 12px',
              fontSize: '11px',
              fontWeight: 700,
              borderRadius: '20px',
              border: 'none',
              cursor: 'pointer',
              background: period === p.value ? 'var(--bg-dark-green)' : 'var(--bg-surface-2)',
              color: period === p.value ? 'white' : 'var(--text-secondary)',
              transition: 'all 0.15s ease',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div style={{ width: "100%", height: 280 }}>
        {isLoading ? (
          <div className="skeleton" style={{ height: "100%", width: "100%" }} />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history}>
              <defs>
                <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.15}/>
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-light)" />
              <XAxis dataKey="date" hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip 
                contentStyle={{ borderRadius: 8, border: 'none', boxShadow: 'var(--shadow-md)' }}
                labelFormatter={(val) => new Date(val).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(val: any) => [`₹${Number(val || 0).toFixed(2)}`, "NAV"]}
              />
              <Area 
                type="monotone" 
                dataKey="nav" 
                stroke="var(--accent)" 
                strokeWidth={3}
                fillOpacity={1} 
                fill="url(#colorNav)" 
                animationDuration={1000}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Date Range */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.03em' }}>
         <span>{history[0]?.date ? new Date(history[0].date).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : ''}</span>
         <span>Current</span>
      </div>
    </div>
  );
}
