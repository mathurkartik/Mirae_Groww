/**
 * SectorChart.tsx
 * Donut chart showing asset allocation by sector from fund holdings.
 */
"use client";

import { useMemo } from "react";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";

interface Holding {
  name: string;
  sector: string;
  instrument: string;
  allocation: string;
}

interface SectorChartProps {
  holdings: Holding[];
}

const COLORS = [
  'var(--accent)',
  'var(--bg-dark-green)',
  '#10b981', // emerald-500
  '#34d399', // emerald-400
  '#065f46', // emerald-800
  '#0f766e', // teal-700
  '#fb923c', // orange-400
  '#1e293b'  // slate-800
];

export function SectorChart({ holdings }: SectorChartProps) {
  const data = useMemo(() => {
    if (!holdings) return [];
    
    // Aggregate by sector
    const sectorMap = new Map<string, number>();
    holdings.forEach(h => {
      // Parse allocation e.g. "8.20%" -> 8.20
      const val = parseFloat(h.allocation.replace('%', ''));
      if (!isNaN(val)) {
        sectorMap.set(h.sector || 'Other', (sectorMap.get(h.sector || 'Other') || 0) + val);
      }
    });

    const results = Array.from(sectorMap.entries()).map(([name, value]) => ({
      name,
      value: Number(value.toFixed(2))
    }));
    
    // Sort descending by value
    results.sort((a, b) => b.value - a.value);
    
    // Maybe take top 7 and group the rest into 'Others' if too many
    if (results.length > 7) {
       const top = results.slice(0, 6);
       const others = results.slice(6).reduce((acc, curr) => acc + curr.value, 0);
       if (others > 0) {
          top.push({ name: 'Others', value: Number(others.toFixed(2)) });
       }
       return top;
    }

    return results;
  }, [holdings]);

  if (!data || data.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
        No sector data available.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="45%"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={2}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip 
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            formatter={(value: any) => [`${value}%`, 'Allocation']}
            contentStyle={{ borderRadius: 8, border: 'none', boxShadow: 'var(--shadow-md)', fontSize: '12px', fontWeight: 600 }}
            itemStyle={{ color: 'var(--accent-dark)' }}
          />
          <Legend 
             verticalAlign="bottom" 
             height={36}
             iconType="circle"
             wrapperStyle={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
