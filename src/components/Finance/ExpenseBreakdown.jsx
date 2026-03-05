// ─── components/Finance/ExpenseBreakdown.jsx ─────────────────────────────────
import { memo } from "react";
import { PieChart, Pie, Cell } from "recharts";
import s from "./Finance.module.css";

const ExpenseBreakdown = memo(({ data = [] }) => (
  <div className={`${s.chartCard} ${s.chartSide}`}>
    <h3 className={s.chartTitle}>Expense Breakdown</h3>
    <p className={s.chartSub}>By category this month</p>
    <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
      <PieChart width={160} height={160}>
        <Pie
          data={data}
          cx={75} cy={75}
          innerRadius={50} outerRadius={75}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((entry, i) => <Cell key={i} fill={entry.color} />)}
        </Pie>
      </PieChart>
    </div>
    <ul className={s.expLegend}>
      {data.map((item) => (
        <li key={item.name} className={s.expItem}>
          <div className={s.expItemLeft}>
            <span className={s.expDot} style={{ background: item.color }} aria-hidden="true" />
            <span className={s.expName}>{item.name}</span>
          </div>
          <span className={s.expVal}>{item.value}%</span>
        </li>
      ))}
    </ul>
  </div>
));

ExpenseBreakdown.displayName = "ExpenseBreakdown";
export default ExpenseBreakdown;