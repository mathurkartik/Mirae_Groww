/**
 * SipCalculator.tsx — Groww-style Step-Up SIP & One-time Investment Calculator
 *
 * DROP INTO: frontend/src/components/SipCalculator.tsx
 *
 * Features:
 *  - Monthly SIP / One-time toggle (pill style matching Groww)
 *  - Slider + direct input for investment amount
 *  - Expected return rate slider (editable)
 *  - Period tabs: 3M · 6M · 1Y · 3Y · 5Y
 *  - Grouped bar chart (Total Invested vs Would've Become) using recharts
 *  - Live summary: Total Investment, Would've Become, Returns %
 *  - Pure math — no API calls, no fund name in output
 *  - Mandatory disclaimer
 *
 * Math:
 *  Monthly SIP →  FV = SIP × ((1 + r/12)^n – 1) / (r/12) × (1 + r/12)
 *  One-time    →  FV = Amount × (1 + r/100)^years
 *
 * Dependencies: recharts (already in package.json)
 */

"use client";

import { useState, useCallback } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type Mode = "sip" | "onetime";

interface Period {
  label: string;
  months: number;
  years: number;
}

const PERIODS: Period[] = [
  { label: "3M",  months: 3,  years: 0.25 },
  { label: "6M",  months: 6,  years: 0.5  },
  { label: "1Y",  months: 12, years: 1    },
  { label: "3Y",  months: 36, years: 3    },
  { label: "5Y",  months: 60, years: 5    },
];

// ─────────────────────────────────────────────────────────────────────────────
// Math helpers
// ─────────────────────────────────────────────────────────────────────────────

function calcSIP(sip: number, annualRate: number, months: number) {
  if (annualRate === 0) return { invested: sip * months, corpus: sip * months };
  const r = annualRate / 100 / 12;
  const corpus = sip * ((Math.pow(1 + r, months) - 1) / r) * (1 + r);
  return { invested: sip * months, corpus };
}

function calcOnetime(amount: number, annualRate: number, years: number) {
  const corpus = amount * Math.pow(1 + annualRate / 100, years);
  return { invested: amount, corpus };
}

function formatINR(n: number): string {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000)    return `₹${(n / 1_00_000).toFixed(2)} L`;
  if (n >= 1_000)       return `₹${(n / 1_000).toFixed(1)}K`;
  return `₹${Math.round(n)}`;
}

function formatINRFull(n: number): string {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

function pct(invested: number, corpus: number): string {
  const gain = ((corpus - invested) / invested) * 100;
  return (gain >= 0 ? "+" : "") + gain.toFixed(2) + "%";
}

// ─────────────────────────────────────────────────────────────────────────────
// Custom bar chart tooltip
// ─────────────────────────────────────────────────────────────────────────────

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#1c1c1e",
      border: "1px solid #2c2c2e",
      borderRadius: 10,
      padding: "10px 14px",
      fontSize: 12,
    }}>
      <p style={{ color: "#8e8e93", marginBottom: 6, fontWeight: 600 }}>{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.fill === "#5856d6" ? "#9d9bf7" : "#34c759", margin: "3px 0" }}>
          {p.name}: {formatINRFull(p.value)}
        </p>
      ))}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export default function SipCalculator() {
  const [mode, setMode]           = useState<Mode>("sip");
  const [amount, setAmount]       = useState(5000);
  const [returnRate, setReturnRate] = useState(12);
  const [activePeriod, setActivePeriod] = useState<string>("3Y");

  // ── Derived chart data ─────────────────────────────────────────────────────
  const chartData = PERIODS.map((p) => {
    const { invested, corpus } =
      mode === "sip"
        ? calcSIP(amount, returnRate, p.months)
        : calcOnetime(amount, returnRate, p.years);
    return { period: p.label, "Total Invested": Math.round(invested), "Would've Become": Math.round(corpus) };
  });

  // ── Active period summary ──────────────────────────────────────────────────
  const activePeriodObj = PERIODS.find((p) => p.label === activePeriod)!;
  const { invested: activeInvested, corpus: activeCorpus } =
    mode === "sip"
      ? calcSIP(amount, returnRate, activePeriodObj.months)
      : calcOnetime(amount, returnRate, activePeriodObj.years);
  const returnsPct = pct(activeInvested, activeCorpus);
  const isGain = activeCorpus >= activeInvested;

  // ── Amount slider limits ───────────────────────────────────────────────────
  const sipMin = 500, sipMax = 1_00_000, sipStep = 500;
  const otMin  = 5_000, otMax  = 50_00_000, otStep  = 5_000;
  const sliderMin  = mode === "sip" ? sipMin  : otMin;
  const sliderMax  = mode === "sip" ? sipMax  : otMax;
  const sliderStep = mode === "sip" ? sipStep : otStep;

  const sliderPct = ((amount - sliderMin) / (sliderMax - sliderMin)) * 100;

  const handleModeSwitch = (m: Mode) => {
    setMode(m);
    setAmount(m === "sip" ? 5000 : 50_000);
  };

  // ── Styles (all inline — no Tailwind required) ────────────────────────────
  const S = {
    wrapper: {
      background: "#000",
      minHeight: "100%",
      display: "flex",
      flexDirection: "column" as const,
      alignItems: "center",
      justifyContent: "flex-start",
      padding: "24px 16px 40px",
      gap: 0,
    },
    card: {
      background: "#111113",
      border: "1px solid #2c2c2e",
      borderRadius: 24,
      width: "100%",
      maxWidth: 420,
      padding: "24px 20px",
      display: "flex",
      flexDirection: "column" as const,
      gap: 0,
    },
    toggleRow: {
      display: "flex",
      background: "#1c1c1e",
      borderRadius: 40,
      padding: 4,
      marginBottom: 28,
      gap: 4,
    },
    toggleBtn: (active: boolean): React.CSSProperties => ({
      flex: 1,
      padding: "9px 0",
      borderRadius: 36,
      border: "none",
      fontSize: 14,
      fontWeight: 600,
      cursor: "pointer",
      transition: "all 0.2s ease",
      background: active ? "#00b386" : "transparent",
      color: active ? "#fff" : "#8e8e93",
    }),
    amountLabel: {
      fontSize: 13,
      color: "#8e8e93",
      textAlign: "center" as const,
      marginBottom: 8,
      letterSpacing: "0.3px",
    },
    amountDisplay: {
      fontSize: 40,
      fontWeight: 700,
      color: "#fff",
      textAlign: "center" as const,
      letterSpacing: "-1px",
      marginBottom: 20,
      fontVariantNumeric: "tabular-nums",
    },
    sliderWrap: {
      position: "relative" as const,
      marginBottom: 24,
      padding: "0 4px",
    },
    sliderTrack: {
      height: 4,
      borderRadius: 2,
      background: `linear-gradient(to right, #00b386 ${sliderPct}%, #2c2c2e ${sliderPct}%)`,
    },
    slider: {
      width: "100%",
      appearance: "none" as const,
      background: "transparent",
      height: 4,
      outline: "none",
      cursor: "pointer",
      position: "absolute" as const,
      top: 0,
      left: 0,
    },
    rateRow: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 20,
      gap: 12,
    },
    rateLabel: {
      fontSize: 12,
      color: "#8e8e93",
      whiteSpace: "nowrap" as const,
    },
    rateInput: {
      width: 64,
      background: "#1c1c1e",
      border: "1px solid #3a3a3c",
      borderRadius: 8,
      color: "#fff",
      fontSize: 14,
      fontWeight: 600,
      padding: "5px 10px",
      textAlign: "right" as const,
      outline: "none",
    },
    rateSlider: {
      flex: 1,
      appearance: "none" as const,
      height: 3,
      borderRadius: 2,
      outline: "none",
      cursor: "pointer",
    },
    chartWrap: {
      height: 180,
      marginBottom: 0,
    },
    periodRow: {
      display: "flex",
      justifyContent: "space-around",
      alignItems: "center",
      borderTop: "1px solid #2c2c2e",
      paddingTop: 12,
      marginBottom: 20,
      marginLeft: 40,
    },
    periodBtn: (active: boolean): React.CSSProperties => ({
      padding: "4px 10px",
      borderRadius: 20,
      border: active ? "2px solid #fff" : "2px solid transparent",
      background: "transparent",
      color: active ? "#fff" : "#8e8e93",
      fontSize: 13,
      fontWeight: active ? 600 : 400,
      cursor: "pointer",
      transition: "all 0.15s ease",
    }),
    divider: {
      height: 1,
      background: "#2c2c2e",
      margin: "0 0 16px",
    },
    summaryRow: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: 12,
    },
    summaryLeft: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      fontSize: 14,
      color: "#8e8e93",
    },
    dot: (color: string): React.CSSProperties => ({
      width: 10,
      height: 10,
      borderRadius: "50%",
      background: color,
      flexShrink: 0,
    }),
    summaryValue: {
      fontSize: 15,
      fontWeight: 600,
      color: "#fff",
    },
    returnsRow: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      paddingTop: 14,
      borderTop: "1px solid #2c2c2e",
    },
    returnsLabel: {
      fontSize: 14,
      color: "#8e8e93",
    },
    returnsValue: (positive: boolean): React.CSSProperties => ({
      fontSize: 16,
      fontWeight: 700,
      color: positive ? "#34c759" : "#ff3b30",
    }),
    disclaimer: {
      maxWidth: 420,
      width: "100%",
      marginTop: 16,
      padding: "12px 16px",
      background: "#1a1206",
      border: "1px solid #3d2e0a",
      borderRadius: 12,
      fontSize: 11,
      color: "#a08030",
      lineHeight: 1.6,
      textAlign: "center" as const,
    },
  };

  return (
    <div style={S.wrapper}>
      <div style={S.card}>

        {/* ── Mode toggle ─────────────────────────────────────────────────── */}
        <div style={S.toggleRow}>
          <button style={S.toggleBtn(mode === "sip")} onClick={() => handleModeSwitch("sip")}>
            Monthly SIP
          </button>
          <button style={S.toggleBtn(mode === "onetime")} onClick={() => handleModeSwitch("onetime")}>
            One-time
          </button>
        </div>

        {/* ── Amount display ──────────────────────────────────────────────── */}
        <p style={S.amountLabel}>
          {mode === "sip" ? "Monthly investment" : "One-time investment"}
        </p>
        <div style={S.amountDisplay}>
          ₹{amount.toLocaleString("en-IN")}
        </div>

        {/* ── Amount slider ───────────────────────────────────────────────── */}
        <div style={S.sliderWrap}>
          <div style={S.sliderTrack} />
          <style>{`
            input[type=range].sip-slider::-webkit-slider-thumb {
              -webkit-appearance: none;
              width: 22px;
              height: 22px;
              border-radius: 50%;
              background: #00b386;
              border: 3px solid #000;
              box-shadow: 0 0 0 2px #00b386;
              cursor: pointer;
              margin-top: -9px;
            }
            input[type=range].sip-slider::-webkit-slider-runnable-track {
              height: 4px;
              background: transparent;
            }
            input[type=range].rate-slider::-webkit-slider-thumb {
              -webkit-appearance: none;
              width: 16px;
              height: 16px;
              border-radius: 50%;
              background: #00b386;
              border: 2px solid #000;
              cursor: pointer;
              margin-top: -6.5px;
            }
            input[type=range].rate-slider::-webkit-slider-runnable-track {
              height: 3px;
              background: linear-gradient(to right, #00b386, #00b386);
            }
          `}</style>
          <input
            type="range"
            className="sip-slider"
            style={S.slider}
            min={sliderMin}
            max={sliderMax}
            step={sliderStep}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
          {/* invisible spacer so wrapper has height */}
          <div style={{ height: 4 }} />
        </div>

        {/* ── Return rate ─────────────────────────────────────────────────── */}
        <div style={S.rateRow}>
          <span style={S.rateLabel}>Expected return</span>
          <input
            type="range"
            className="rate-slider"
            style={{
              ...S.rateSlider,
              background: `linear-gradient(to right, #00b386 ${((returnRate - 1) / 39) * 100}%, #2c2c2e ${((returnRate - 1) / 39) * 100}%)`,
            }}
            min={1}
            max={40}
            step={0.5}
            value={returnRate}
            onChange={(e) => setReturnRate(Number(e.target.value))}
          />
          <input
            type="number"
            style={S.rateInput}
            value={returnRate}
            min={1}
            max={40}
            step={0.5}
            onChange={(e) => setReturnRate(Math.min(40, Math.max(1, Number(e.target.value))))}
          />
          <span style={{ fontSize: 13, color: "#8e8e93" }}>%</span>
        </div>

        {/* ── Bar chart ───────────────────────────────────────────────────── */}
        <div style={S.chartWrap}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              barGap={3}
              barCategoryGap="30%"
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <XAxis
                dataKey="period"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "transparent", fontSize: 0 }}
              />
              <YAxis hide />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
              />
              <Bar dataKey="Total Invested" radius={[4, 4, 0, 0]} maxBarSize={22}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.period}
                    fill={entry.period === activePeriod ? "#3634a3" : "#2c2c6a"}
                  />
                ))}
              </Bar>
              <Bar dataKey="Would've Become" radius={[4, 4, 0, 0]} maxBarSize={22}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.period}
                    fill={entry.period === activePeriod ? "#7c7af7" : "#4e4cbb"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Period selector ─────────────────────────────────────────────── */}
        <div style={S.periodRow}>
          {PERIODS.map((p) => (
            <button
              key={p.label}
              style={S.periodBtn(activePeriod === p.label)}
              onClick={() => setActivePeriod(p.label)}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* ── Divider ─────────────────────────────────────────────────────── */}
        <div style={S.divider} />

        {/* ── Summary rows ────────────────────────────────────────────────── */}
        <div style={S.summaryRow}>
          <div style={S.summaryLeft}>
            <div style={S.dot("#3634a3")} />
            Total Investment
          </div>
          <span style={S.summaryValue}>{formatINRFull(activeInvested)}</span>
        </div>

        <div style={{ ...S.summaryRow, marginBottom: 16 }}>
          <div style={S.summaryLeft}>
            <div style={S.dot("#7c7af7")} />
            Would&apos;ve Become
          </div>
          <span style={S.summaryValue}>{formatINRFull(activeCorpus)}</span>
        </div>

        {/* ── Returns row ─────────────────────────────────────────────────── */}
        <div style={S.returnsRow}>
          <span style={S.returnsLabel}>
            {activePeriod} returns
          </span>
          <span style={S.returnsValue(isGain)}>{returnsPct}</span>
        </div>
      </div>

      {/* ── Disclaimer ──────────────────────────────────────────────────────── */}
      <div style={S.disclaimer}>
        ⚠️ This uses your entered return rate — not actual fund performance.
        Mathematical estimate only. Past performance does not guarantee future returns.
        Not investment advice.
      </div>
    </div>
  );
}