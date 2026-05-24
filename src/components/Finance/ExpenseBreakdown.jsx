// ─── components/Finance/ExpenseBreakdown.jsx ─────────────────────────────────
import { memo, useEffect, useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip } from "recharts";
import invoicesService from "../../utils/invoicesService";
import s from "./Finance.module.css";

const STATUS_COLORS = {
  Paid: "#3B5BDB",
  Pending: "#4DABF7",
  Overdue: "#FA5252",
};

const getInvoiceAmount = (invoice) => {
  const directAmount =
    invoice?.calculations?.grandTotal ??
    invoice?.summary?.grandTotal ??
    invoice?.grandTotal ??
    invoice?.totalAmount ??
    invoice?.amount ??
    invoice?.total;

  if (directAmount !== undefined && directAmount !== null) {
    const value = Number(directAmount);
    return Number.isNaN(value) ? 0 : value;
  }

  if (Array.isArray(invoice?.lineItems)) {
    const subtotal = invoice.lineItems.reduce((sum, item) => {
      const total =
        Number(item.total) ||
        Number(item.quantity || item.qty || 0) * Number(item.unitPrice || 0);

      return sum + total;
    }, 0);

    const taxRateRaw = Number(invoice?.taxConfiguration?.customTaxRate || 0);
    const taxRate = taxRateRaw > 1 ? taxRateRaw / 100 : taxRateRaw;

    const taxAmount = subtotal * taxRate;
    const discount = Number(invoice?.discountAndNotes?.discountAmountUSD || 0);

    return Math.max(subtotal + taxAmount - discount, 0);
  }

  return 0;
};

const normalizeStatus = (status) => {
  if (["Paid", "Pending", "Overdue"].includes(status)) return status;
  return "Pending";
};

const buildBreakdownData = (invoices = []) => {
  const totals = {
    Paid: 0,
    Pending: 0,
    Overdue: 0,
  };

  invoices.forEach((invoice) => {
    const status = normalizeStatus(invoice?.status);
    totals[status] += getInvoiceAmount(invoice);
  });

  const grandTotal = Object.values(totals).reduce((sum, value) => sum + value, 0);

  if (grandTotal <= 0) {
    return [];
  }

  return Object.entries(totals)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({
      name,
      amount: value,
      value: Math.round((value / grandTotal) * 100),
      color: STATUS_COLORS[name] || "#ADB5BD",
    }));
};

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;

  const item = payload[0]?.payload;

  return (
    <div className={s.tooltip}>
      <p className={s.tooltipTitle}>{item.name}</p>
      <p className={s.tooltipRow}>
        Amount: <strong>EGP {Number(item.amount || 0).toLocaleString()}</strong>
      </p>
      <p className={s.tooltipRow}>
        Share: <strong>{item.value}%</strong>
      </p>
    </div>
  );
};

const ExpenseBreakdown = memo(() => {
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

  const data = useMemo(() => buildBreakdownData(invoices), [invoices]);

  return (
    <div className={`${s.chartCard} ${s.chartSide}`}>
      <h3 className={s.chartTitle}>Invoice Breakdown</h3>
      <p className={s.chartSub}>By invoice status from real data</p>

      {loading ? (
        <div style={{ height: 160, display: "grid", placeItems: "center" }}>
          Loading breakdown...
        </div>
      ) : error ? (
        <div
          style={{
            height: 160,
            display: "grid",
            placeItems: "center",
            color: "#c92a2a",
            textAlign: "center",
          }}
        >
          {error}
        </div>
      ) : data.length === 0 ? (
        <div
          style={{
            height: 160,
            display: "grid",
            placeItems: "center",
            color: "#868e96",
            textAlign: "center",
          }}
        >
          No invoice data available.
        </div>
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
            <PieChart width={160} height={160}>
              <Pie
                data={data}
                cx={75}
                cy={75}
                innerRadius={50}
                outerRadius={75}
                paddingAngle={3}
                dataKey="value"
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>

              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </div>

          <ul className={s.expLegend}>
            {data.map((item) => (
              <li key={item.name} className={s.expItem}>
                <div className={s.expItemLeft}>
                  <span
                    className={s.expDot}
                    style={{ background: item.color }}
                    aria-hidden="true"
                  />
                  <span className={s.expName}>{item.name}</span>
                </div>

                <span className={s.expVal}>{item.value}%</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
});

ExpenseBreakdown.displayName = "ExpenseBreakdown";

export default ExpenseBreakdown;