// ─── components/Finance/CashFlowChart.jsx ────────────────────────────────────
import { memo, useEffect, useMemo, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import invoicesService from "../../utils/invoicesService";
import s from "./Finance.module.css";

const RANGES = ["6 Months", "1 Year"];

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;

  return (
    <div className={s.tooltip}>
      <p className={s.tooltipTitle}>{label}</p>
      {payload.map((e) => (
        <p key={e.name} className={s.tooltipRow} style={{ color: e.color }}>
          {e.name}: <strong>EGP {Number(e.value || 0).toLocaleString()}</strong>
        </p>
      ))}
    </div>
  );
};

const getInvoiceDate = (invoice) => {
  return (
    invoice?.invoiceTimeline?.issueDate ||
    invoice?.issueDate ||
    invoice?.createdAt ||
    invoice?.updatedAt ||
    null
  );
};

const getLineItemsTotal = (invoice) => {
  if (!Array.isArray(invoice?.lineItems)) return 0;

  return invoice.lineItems.reduce((sum, item) => {
    const total =
      Number(item.total) ||
      (Number(item.quantity || item.qty || 0) * Number(item.unitPrice || 0));

    return sum + total;
  }, 0);
};

const getInvoiceRevenue = (invoice) => {
  const directTotal =
    invoice?.calculations?.grandTotal ??
    invoice?.summary?.grandTotal ??
    invoice?.grandTotal ??
    invoice?.totalAmount ??
    invoice?.amount ??
    invoice?.total;

  if (directTotal !== undefined && directTotal !== null) {
    const value = Number(directTotal);
    return Number.isNaN(value) ? 0 : value;
  }

  const subtotal = getLineItemsTotal(invoice);

  const taxRateRaw = Number(invoice?.taxConfiguration?.customTaxRate || 0);
  const taxRate = taxRateRaw > 1 ? taxRateRaw / 100 : taxRateRaw;

  const taxAmount = subtotal * taxRate;
  const discount = Number(invoice?.discountAndNotes?.discountAmountUSD || 0);

  return Math.max(subtotal + taxAmount - discount, 0);
};

const getInvoiceExpenses = (invoice) => {
  const possibleExpense =
    invoice?.expenses ??
    invoice?.expenseAmount ??
    invoice?.cost ??
    invoice?.totalCost ??
    0;

  const value = Number(possibleExpense);
  return Number.isNaN(value) ? 0 : value;
};

const getMonthKey = (date) => {
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

const getMonthLabel = (date) => {
  return new Date(date).toLocaleDateString("en-US", {
    month: "short",
    year: "2-digit",
  });
};

const buildEmptyMonths = (range) => {
  const count = range === "1 Year" ? 12 : 6;
  const now = new Date();

  return Array.from({ length: count }).map((_, index) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (count - 1 - index), 1);

    return {
      key: getMonthKey(d),
      month: getMonthLabel(d),
      revenue: 0,
      expenses: 0,
    };
  });
};

const buildCashFlowData = (invoices, range) => {
  const months = buildEmptyMonths(range);
  const monthMap = new Map(months.map((m) => [m.key, m]));

  invoices.forEach((invoice) => {
    const date = getInvoiceDate(invoice);
    if (!date) return;

    const parsedDate = new Date(date);
    if (Number.isNaN(parsedDate.getTime())) return;

    const key = getMonthKey(parsedDate);
    const bucket = monthMap.get(key);

    if (!bucket) return;

    bucket.revenue += getInvoiceRevenue(invoice);
    bucket.expenses += getInvoiceExpenses(invoice);
  });

  return months.map((m) => ({
    ...m,
    revenue: Math.round(m.revenue),
    expenses: Math.round(m.expenses),
  }));
};

const CashFlowChart = memo(() => {
  const [range, setRange] = useState("6 Months");
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    const loadInvoices = async () => {
      setLoading(true);
      setError("");

      const result = await invoicesService.fetchInvoices({}, controller.signal);

      if (result.error) {
        setError(result.error);
        setLoading(false);
        return;
      }

      const invoicesArray = Array.isArray(result.data)
        ? result.data
        : Array.isArray(result.data?.data)
          ? result.data.data
          : [];

      setInvoices(invoicesArray);
      setLoading(false);
    };

    loadInvoices();

    return () => controller.abort();
  }, []);

  const chartData = useMemo(() => {
    return buildCashFlowData(invoices, range);
  }, [invoices, range]);

  const hasData = chartData.some((item) => item.revenue > 0 || item.expenses > 0);

  return (
    <div className={`${s.chartCard} ${s.chartMain}`}>
      <div className={s.chartHeader}>
        <div>
          <h3 className={s.chartTitle}>Cash Flow Analysis</h3>
          <p className={s.chartSub}>
            Real invoice data — {range === "1 Year" ? "last 12 months" : "last 6 months"}
          </p>
        </div>

        <div className={s.rangeGroup} role="group" aria-label="Time range">
          {RANGES.map((opt) => (
            <button
              key={opt}
              onClick={() => setRange(opt)}
              aria-pressed={range === opt}
              className={`${s.rangeBtn} ${
                range === opt ? s.rangeActive : s.rangeInactive
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ height: 220, display: "grid", placeItems: "center" }}>
          Loading cash flow...
        </div>
      ) : error ? (
        <div style={{ height: 220, display: "grid", placeItems: "center", color: "#c92a2a" }}>
          {error}
        </div>
      ) : !hasData ? (
        <div style={{ height: 220, display: "grid", placeItems: "center", color: "#868e96" }}>
          No invoice data available for this range.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart
            data={chartData}
            margin={{ top: 20, right: 10, left: -10, bottom: 0 }}
          >
            <defs>
              <linearGradient id="gradRev" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3B5BDB" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#3B5BDB" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradExp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4DABF7" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#4DABF7" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#F1F3F5" />

            <XAxis
              dataKey="month"
              tick={{ fontSize: 11, fill: "#ADB5BD" }}
              axisLine={false}
              tickLine={false}
            />

            <YAxis
              tick={{ fontSize: 11, fill: "#ADB5BD" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `EGP ${v / 1000}k`}
            />

            <Tooltip content={<ChartTooltip />} />

            <Area
              type="monotone"
              dataKey="revenue"
              name="Revenue"
              stroke="#3B5BDB"
              strokeWidth={2.5}
              fill="url(#gradRev)"
              dot={false}
            />

            <Area
              type="monotone"
              dataKey="expenses"
              name="Expenses"
              stroke="#4DABF7"
              strokeWidth={2.5}
              fill="url(#gradExp)"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}

      <div className={s.chartLegend}>
        {[
          { label: "Revenue", color: "#3B5BDB" },
          { label: "Expenses", color: "#4DABF7" },
        ].map((l) => (
          <div key={l.label} className={s.legendItem}>
            <span
              className={s.legendDot}
              style={{ background: l.color }}
              aria-hidden="true"
            />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  );
});

CashFlowChart.displayName = "CashFlowChart";

export default CashFlowChart;