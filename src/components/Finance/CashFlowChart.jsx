// ─── components/Finance/CashFlowChart.jsx ────────────────────────────────────
import { memo, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import s from "./Finance.module.css";

const RANGES = ["6 Months", "1 Year"];

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className={s.tooltip}>
      <p className={s.tooltipTitle}>{label}</p>
      {payload.map((e) => (
        <p key={e.name} className={s.tooltipRow} style={{ color: e.color }}>
          {e.name}: <strong>${e.value.toLocaleString()}</strong>
        </p>
      ))}
    </div>
  );
};

const CashFlowChart = memo(({ data = [] }) => {
  const [range, setRange] = useState("6 Months");

  return (
    <div className={`${s.chartCard} ${s.chartMain}`}>
      <div className={s.chartHeader}>
        <div>
          <h3 className={s.chartTitle}>Cash Flow Analysis</h3>
          <p className={s.chartSub}>Fiscal Year 2024 Trends</p>
        </div>
        <div className={s.rangeGroup} role="group" aria-label="Time range">
          {RANGES.map((opt) => (
            <button
              key={opt}
              onClick={() => setRange(opt)}
              aria-pressed={range === opt}
              className={`${s.rangeBtn} ${range === opt ? s.rangeActive : s.rangeInactive}`}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 20, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="gradRev" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#3B5BDB" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#3B5BDB" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradExp" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#4DABF7" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#4DABF7" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F3F5" />
          <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#ADB5BD" }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 11, fill: "#ADB5BD" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v / 1000}k`}
          />
          <Tooltip content={<ChartTooltip />} />
          <Area type="monotone" dataKey="revenue"  name="Revenue"  stroke="#3B5BDB" strokeWidth={2.5} fill="url(#gradRev)" dot={false} />
          <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#4DABF7" strokeWidth={2.5} fill="url(#gradExp)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>

      <div className={s.chartLegend}>
        {[{ label: "Revenue", color: "#3B5BDB" }, { label: "Expenses", color: "#4DABF7" }].map((l) => (
          <div key={l.label} className={s.legendItem}>
            <span className={s.legendDot} style={{ background: l.color }} aria-hidden="true" />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  );
});

CashFlowChart.displayName = "CashFlowChart";
export default CashFlowChart;