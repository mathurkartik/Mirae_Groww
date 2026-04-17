/**
 * NavChart.tsx — Interactive NAV Chart
 * Uses Recharts to display historical price series with period toggles.
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
      <div className="nav-chart-error" style={{ height: 300, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-secondary)', background:'var(--bg-surface-2)', borderRadius: 12 }}>
         <p>NAV history data currently unavailable</p>
      </div>
    );
  }

  return (
    <div className="nav-chart-container" style={{ background: 'var(--bg-white)', padding: 24, borderRadius: 16, border: '1px solid var(--border)', marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Growth of ₹10,000</h3>
        <div className="filter-pills" style={{ margin: 0 }}>
          {PERIODS.map((p) => (
            <button
              key={p.value}
              className={`filter-pill ${period === p.value ? "filter-pill--active" : ""}`}
              onClick={() => setPeriod(p.value)}
              style={{ padding: '4px 12px', fontSize: 12 }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ width: "100%", height: 320 }}>
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
              <XAxis 
                dataKey="date" 
                hide 
              />
              <YAxis 
                hide 
                domain={['auto', 'auto']}
              />
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

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
         <span>{history[0]?.date ? new Date(history[0].date).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : ''}</span>
         <span>Current</span>
      </div>
    </div>
  );
}
