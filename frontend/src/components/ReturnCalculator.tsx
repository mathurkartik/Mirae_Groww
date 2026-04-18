"use client";

import { useState, useMemo } from "react";

// The returns object passed from the fund detail page looks like:
// { "6M": "8.5%", "1Y": "15.2%", "3Y": "22.1%", "5Y": "18.4%" }
interface ReturnCalculatorProps {
  returns: Record<string, string>;
}

const PERIODS = [
  { label: "6M", years: 0.5 },
  { label: "1Y", years: 1 },
  { label: "3Y", years: 3 },
  { label: "5Y", years: 5 },
];

function formatInr(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function ReturnCalculator({ returns }: ReturnCalculatorProps) {
  const [mode, setMode] = useState<"sip" | "lumpsum">("sip");
  const [amount, setAmount] = useState<number>(5000);
  const [activePeriod, setActivePeriod] = useState<string>("3Y");

  // Validate available periods from the fund's returns
  const availablePeriods = PERIODS.filter((p) => returns[p.label]);
  // If 3Y isn't available, default to the first available period
  const currentPeriod = useMemo(() => {
    if (availablePeriods.length === 0) return null;
    const found = availablePeriods.find(p => p.label === activePeriod);
    return found ? found.label : availablePeriods[availablePeriods.length - 1].label;
  }, [availablePeriods, activePeriod]);

  // Calculations
  const calcData = useMemo(() => {
    if (!currentPeriod || availablePeriods.length === 0) return [];
    
    return availablePeriods.map((p) => {
      const cagrStr = returns[p.label];
      const cagr = cagrStr ? parseFloat(cagrStr.replace("%", "")) : 0;
      
      let invested = 0;
      let finalValue = 0;

      if (mode === "lumpsum") {
        invested = amount;
        finalValue = amount * Math.pow(1 + cagr / 100, p.years);
      } else {
        invested = amount * 12 * p.years;
        const R = cagr / 100 / 12;
        const N = p.years * 12;
        if (R === 0) {
          finalValue = invested;
        } else {
          finalValue = amount * ((Math.pow(1 + R, N) - 1) / R) * (1 + R);
        }
      }

      return {
        label: p.label,
        invested: Math.round(invested),
        finalValue: Math.round(finalValue),
        cagrStr
      };
    });
  }, [mode, amount, returns, currentPeriod, availablePeriods]);

  if (availablePeriods.length === 0) {
    return null; // Don't render if no return data exists
  }

  const activeData = calcData.find((d) => d.label === currentPeriod) || calcData[0];
  
  // For the chart scaling, find the absolute maximum value across all periods
  const maxValue = Math.max(...calcData.map(d => d.finalValue));

  return (
    <div className="w-full bg-white border border-gray-200 rounded-2xl p-6 shadow-sm font-sans mb-8">
      {/* Header Toggle */}
      <div className="flex justify-center mb-8">
        <div className="bg-gray-100 p-1 rounded-full flex gap-1">
          <button
            onClick={() => setMode("sip")}
            className={`px-6 py-2 text-sm font-semibold rounded-full transition-colors ${
              mode === "sip" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Monthly SIP
          </button>
          <button
            onClick={() => setMode("lumpsum")}
            className={`px-6 py-2 text-sm font-semibold rounded-full transition-colors ${
              mode === "lumpsum" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
            }`}
          >
            One-time
          </button>
        </div>
      </div>

      {/* Amount Display & Slider */}
      <div className="text-center mb-10">
        <p className="text-gray-500 text-sm mb-1 font-medium">
          {mode === "sip" ? "Monthly investment" : "Total investment"}
        </p>
        <p className="text-4xl font-bold text-gray-900 tracking-tight mb-6">
          {formatInr(amount)}
        </p>
        
        <div className="px-4 max-w-sm mx-auto">
          <input
            type="range"
            min={mode === "sip" ? 500 : 5000}
            max={mode === "sip" ? 100000 : 1000000}
            step={mode === "sip" ? 500 : 5000}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#00b386]"
          />
        </div>
      </div>

      {/* Interactive Bar Chart */}
      <div className="h-48 flex items-end justify-center gap-8 border-b border-gray-100 pb-4 mb-2">
        {calcData.map((data) => {
          const isSelected = data.label === currentPeriod;
          const investedHeight = `${(data.invested / maxValue) * 100}%`;
          const finalHeight = `${(data.finalValue / maxValue) * 100}%`;

          return (
            <div 
              key={data.label} 
              className="flex flex-col items-center gap-3 relative h-full justify-end"
            >
              <div className="flex items-end gap-1.5 h-full w-14 justify-center" onClick={() => setActivePeriod(data.label)}>
                {/* Invested Bar */}
                <div 
                  className={`w-3.5 rounded-t-sm transition-all duration-300 ${isSelected ? 'bg-indigo-300' : 'bg-gray-200'}`}
                  style={{ height: investedHeight }}
                ></div>
                {/* Final Value Bar */}
                <div 
                  className={`w-3.5 rounded-t-sm transition-all duration-300 ${isSelected ? 'bg-indigo-500' : 'bg-gray-300'}`}
                  style={{ height: finalHeight }}
                ></div>
              </div>
              
              {/* X-Axis Button */}
              <button 
                onClick={() => setActivePeriod(data.label)}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full transition-all ${
                  isSelected 
                    ? "border border-gray-900 text-gray-900 bg-gray-50" 
                    : "border border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {data.label}
              </button>
            </div>
          );
        })}
      </div>

      {/* Summary Footer */}
      <div className="max-w-md mx-auto pt-6">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-300"></div>
            <span className="text-gray-600 text-sm font-medium">Total Investment</span>
          </div>
          <span className="text-gray-900 font-bold whitespace-nowrap">{formatInr(activeData.invested)}</span>
        </div>
        
        <div className="flex justify-between items-center pb-5 border-b border-gray-100 border-dashed">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500"></div>
            <span className="text-gray-600 text-sm font-medium">Would&apos;ve Become</span>
          </div>
          <span className="text-gray-900 font-bold whitespace-nowrap">{formatInr(activeData.finalValue)}</span>
        </div>
        
        <div className="flex justify-between items-center mt-5">
          <span className="text-gray-600 text-sm">{activeData.label} returns</span>
          <span className="text-[#00b386] font-bold">+{activeData.cagrStr}</span>
        </div>
      </div>
    </div>
  );
}
