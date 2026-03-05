// ─── components/Finance/ExportReportsModal.jsx ───────────────────────────────
// ✅ Pure JS — no TypeScript
// ✅ Export: CSV + JSON for each dataset
// ✅ Animated modal with backdrop close + Escape key
// ✅ Per-item progress feedback (downloading → done)
// ✅ Zero dependencies beyond React

import { useState, useEffect, useRef, useCallback } from "react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import s from "./ExportReportsModal.module.css";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Triggers a browser file download */
function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement("a"), {
    href:     url,
    download: filename,
  });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Converts array-of-objects to CSV string */
function toCSV(rows) {
  if (!rows?.length) return "";
  const headers = Object.keys(rows[0]);
  const lines   = rows.map((row) =>
    headers.map((h) => {
      const val = row[h] ?? "";
      // Wrap in quotes if value contains comma, quote, or newline
      const str = String(val);
      return str.includes(",") || str.includes('"') || str.includes("\n")
        ? `"${str.replace(/"/g, '""')}"`
        : str;
    }).join(",")
  );
  return [headers.join(","), ...lines].join("\n");
}

/** Returns today's date as YYYY-MM-DD for filenames */
function today() {
  return new Date().toISOString().slice(0, 10);
}

// ─────────────────────────────────────────────────────────────────────────────
// Export configs — each item knows how to transform data → rows
// ─────────────────────────────────────────────────────────────────────────────
function buildExportItems(pageData) {
  return [
    {
      id:       "stat_cards",
      icon:     "📊",
      label:    "Finance KPIs",
      desc:     "Total revenue, net profit, expenses & unpaid invoices",
      filename: `synergy-kpis-${today()}`,
      rows: () =>
        (pageData?.statCards ?? []).map((c) => ({
          Metric:  c.label,
          Value:   c.value,
          Change:  c.change,
          Trend:   c.changeType,
        })),
    },
    {
      id:       "cash_flow",
      icon:     "📈",
      label:    "Cash Flow",
      desc:     "Monthly revenue vs expenses — Fiscal Year 2024",
      filename: `synergy-cashflow-${today()}`,
      rows: () =>
        (pageData?.cashFlow ?? []).map((r) => ({
          Month:    r.month,
          Revenue:  r.revenue,
          Expenses: r.expenses,
          Net:      r.revenue - r.expenses,
        })),
    },
    {
      id:       "expense_breakdown",
      icon:     "🍩",
      label:    "Expense Breakdown",
      desc:     "Expense split by category this month",
      filename: `synergy-expenses-${today()}`,
      rows: () =>
        (pageData?.expenseBreakdown ?? []).map((e) => ({
          Category:   e.name,
          Percentage: `${e.value}%`,
        })),
    },
    {
      id:       "invoices",
      icon:     "🧾",
      label:    "Invoices",
      desc:     "All recent invoices with status & amounts",
      filename: `synergy-invoices-${today()}`,
      rows: () =>
        (pageData?.invoices ?? []).map((inv) => ({
          "Invoice ID":   inv.id,
          Customer:       inv.customer,
          "Corp ID":      inv.corpId ?? "",
          Status:         inv.status,
          "Date Issued":  formatDate(inv.created),
          "Due Date":     formatDate(inv.due),
          Amount:         formatCurrency(inv.amount),
          "Amount (Raw)": inv.amount,
        })),
    },
  ];
}

// ─────────────────────────────────────────────────────────────────────────────
// ExportCard — single dataset row
// ─────────────────────────────────────────────────────────────────────────────
function ExportCard({ item, format, onExport, status }) {
  const isLoading = status === "loading";
  const isDone    = status === "done";

  return (
    <div className={`${s.exportCard} ${isDone ? s.exportCardDone : ""}`}>
      <div className={s.exportCardLeft}>
        <span className={s.exportCardIcon} aria-hidden="true">{item.icon}</span>
        <div>
          <p className={s.exportCardLabel}>{item.label}</p>
          <p className={s.exportCardDesc}>{item.desc}</p>
        </div>
      </div>

      <button
        className={`${s.exportBtn} ${isDone ? s.exportBtnDone : ""}`}
        onClick={() => onExport(item)}
        disabled={isLoading}
        aria-label={`Export ${item.label} as ${format.toUpperCase()}`}
      >
        {isLoading ? (
          <span className={s.spinner} aria-label="Downloading" />
        ) : isDone ? (
          <>✓ Downloaded</>
        ) : (
          <>⬇ {format.toUpperCase()}</>
        )}
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Modal
// ─────────────────────────────────────────────────────────────────────────────
export default function ExportReportsModal({ isOpen, onClose, pageData }) {
  const [format,    setFormat]    = useState("csv");
  const [statuses,  setStatuses]  = useState({});   // { [id]: "loading" | "done" }
  const overlayRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Reset statuses when modal opens
  useEffect(() => {
    if (isOpen) setStatuses({});
  }, [isOpen]);

  // Close on backdrop click
  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose();
  };

  const exportItems = buildExportItems(pageData);

  // ── Handle single export ────────────────────────────────────────────────────
  const handleExport = useCallback(async (item) => {
    setStatuses((prev) => ({ ...prev, [item.id]: "loading" }));

    // Small delay to show spinner (feels more responsive)
    await new Promise((r) => setTimeout(r, 350));

    try {
      const rows = item.rows();

      if (format === "csv") {
        const csv = toCSV(rows);
        downloadFile(csv, `${item.filename}.csv`, "text/csv;charset=utf-8;");
      } else {
        const json = JSON.stringify(rows, null, 2);
        downloadFile(json, `${item.filename}.json`, "application/json");
      }

      setStatuses((prev) => ({ ...prev, [item.id]: "done" }));
    } catch (err) {
      console.error("Export failed:", err);
      setStatuses((prev) => ({ ...prev, [item.id]: "error" }));
    }
  }, [format]);

  // ── Export All ──────────────────────────────────────────────────────────────
  const handleExportAll = useCallback(async () => {
    for (const item of exportItems) {
      if (statuses[item.id] === "done") continue;
      await handleExport(item);
      // stagger downloads slightly so browser doesn't block them
      await new Promise((r) => setTimeout(r, 200));
    }
  }, [exportItems, statuses, handleExport]);

  const allDone = exportItems.every((item) => statuses[item.id] === "done");

  if (!isOpen) return null;

  return (
    <div
      className={s.overlay}
      ref={overlayRef}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Export Reports"
    >
      <div className={s.modal}>

        {/* ── Modal Header ── */}
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <span className={s.modalTitleIcon} aria-hidden="true">⬇</span>
            <div>
              <h2 className={s.modalTitle}>Export Reports</h2>
              <p className={s.modalSub}>Download finance data for external use or archiving.</p>
            </div>
          </div>
          <button className={s.closeBtn} onClick={onClose} aria-label="Close export modal">✕</button>
        </div>

        {/* ── Format Toggle ── */}
        <div className={s.formatRow}>
          <span className={s.formatLabel}>Export Format</span>
          <div className={s.formatToggle} role="radiogroup" aria-label="Export format">
            {["csv", "json"].map((f) => (
              <button
                key={f}
                role="radio"
                aria-checked={format === f}
                className={`${s.formatBtn} ${format === f ? s.formatBtnActive : ""}`}
                onClick={() => { setFormat(f); setStatuses({}); }}
              >
                {f === "csv" ? "📄 CSV" : "{ } JSON"}
              </button>
            ))}
          </div>
        </div>

        {/* ── Export Items ── */}
        <div className={s.exportList}>
          {exportItems.map((item) => (
            <ExportCard
              key={item.id}
              item={item}
              format={format}
              status={statuses[item.id]}
              onExport={handleExport}
            />
          ))}
        </div>

        {/* ── Footer ── */}
        <div className={s.modalFooter}>
          <p className={s.footerNote}>
            📁 Files are saved to your default Downloads folder.
          </p>
          <div className={s.footerActions}>
            <button className={s.btnGhost} onClick={onClose}>
              Cancel
            </button>
            <button
              className={`${s.btnPrimary} ${allDone ? s.btnSuccess : ""}`}
              onClick={handleExportAll}
              disabled={allDone}
              aria-label="Export all reports"
            >
              {allDone ? "✓ All Downloaded" : `⬇ Export All as ${format.toUpperCase()}`}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}