// ─── components/Finance/InvoicesTable.jsx ────────────────────────────────────
import { memo } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
// ✅ صح
import useInvoicesFilter, { INVOICE_STATUSES, PAGE_SIZE } from "../../hooks/useInvoicesFilter";import { formatCurrency } from "../../utils/formatters";
import s from "./Finance.module.css";

// ── Status Badge ──────────────────────────────────────────────────────────────
const BADGE_META = {
  Paid:    { cls: s.badgePaid,    dot: "#22863a" },
  Pending: { cls: s.badgePending, dot: "#b07d00" },
  Overdue: { cls: s.badgeOverdue, dot: "#c0392b" },
};

const StatusBadge = memo(({ status }) => {
  const { cls, dot } = BADGE_META[status] ?? BADGE_META.Pending;
  return (
    <span className={`${s.badge} ${cls}`}>
      <span className={s.badgeDot} style={{ background: dot }} aria-hidden="true" />
      {status}
    </span>
  );
});

// ── Windowed pagination helper ────────────────────────────────────────────────
// Shows: 1 … 4 [5] 6 … 12  — never renders 100 buttons
function getWindowedPages(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [];
  const addPage = (p) => { if (p >= 1 && p <= total && !pages.includes(p)) pages.push(p); };
  const addEllipsis = () => { if (pages[pages.length - 1] !== "…") pages.push("…"); };

  addPage(1);
  if (current > 3) addEllipsis();
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) addPage(i);
  if (current < total - 2) addEllipsis();
  addPage(total);

  return pages;
}

// ── Table cols ────────────────────────────────────────────────────────────────
const TABLE_COLS = ["Invoice ID", "Customer", "Status", "Created Date", "Due Date", "Amount"];

// ── Component ─────────────────────────────────────────────────────────────────
const InvoicesTable = memo(({ invoices = [] }) => {
  const {
    activeFilter, searchQuery, currentPage, totalPages,
    paginatedInvoices, totalFiltered,
    setActiveFilter, setSearchQuery, setCurrentPage,
  } = useInvoicesFilter(invoices);

  const pageStart = Math.min((currentPage - 1) * PAGE_SIZE + 1, totalFiltered);
  const pageEnd   = Math.min(currentPage * PAGE_SIZE, totalFiltered);
  const windowedPages = getWindowedPages(currentPage, totalPages);

  return (
    <section className={s.tableCard} aria-label="Invoices Management">
      {/* Header */}
      <div className={s.tableHeader}>
        <div>
          <h2 className={s.tableTitle}>Invoices Management</h2>
          <p className={s.tableSub}>Track and manage your customer billing cycle.</p>
        </div>
        <div className={s.tableActions}>
          <div className={s.searchBox}>
            <Search className={s.searchIcon} aria-hidden="true" />
            <input
              className={s.searchInput}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search invoices..."
              aria-label="Search invoices by name or ID"
            />
          </div>
          <button className={`${s.btn} ${s.btnOutline}`} aria-label="Filter invoices">
            <SlidersHorizontal className={s.btnIcon} aria-hidden="true" />
            Filter
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className={s.filterTabs} role="tablist" aria-label="Invoice status filter">
        {Object.values(INVOICE_STATUSES).map((f) => (
          <button
            key={f}
            role="tab"
            aria-selected={activeFilter === f}
            onClick={() => setActiveFilter(f)}
            className={`${s.filterTab} ${activeFilter === f ? s.tabActive : s.tabInactive}`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table className={s.table} aria-label="Invoices list">
          <thead>
            <tr>
              {TABLE_COLS.map((c) => (
                <th key={c} className={s.th} scope="col">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedInvoices.length === 0 ? (
              <tr>
                <td colSpan={6} className={s.empty}>No invoices found</td>
              </tr>
            ) : (
              paginatedInvoices.map((inv) => (
                <tr key={inv.id} className={s.tr}>
                  <td className={s.td}>
                    <button className={s.invoiceId}>{inv.id}</button>
                  </td>
                  <td className={s.td}>
                    <p className={s.custName}>{inv.customer}</p>
                    <p className={s.custCorp}>{inv.corpId}</p>
                  </td>
                  <td className={s.td}><StatusBadge status={inv.status} /></td>
                  <td className={s.td}><span className={s.dateText}>{inv.created}</span></td>
                  <td className={s.td}><span className={s.dateText}>{inv.due}</span></td>
                  <td className={s.td}><span className={s.amountText}>{formatCurrency(inv.amount)}</span></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination — windowed, never renders 100 buttons */}
      <div className={s.pagination}>
        <span className={s.paginationInfo}>
          {totalFiltered === 0
            ? "No results"
            : `Showing ${pageStart}–${pageEnd} of ${totalFiltered} invoices`}
        </span>
        <nav className={s.pageGroup} aria-label="Pagination">
          <button
            className={`${s.pageBtn} ${s.pageBtnNav}`}
            onClick={() => setCurrentPage(currentPage - 1)}
            disabled={currentPage === 1}
            aria-label="Previous page"
          >‹</button>

          {windowedPages.map((p, idx) =>
            p === "…" ? (
              <span
                key={`ellipsis-${idx}`}
                className={s.pageBtn}
                style={{ cursor: "default", border: "none", background: "transparent" }}
                aria-hidden="true"
              >…</span>
            ) : (
              <button
                key={p}
                className={`${s.pageBtn} ${p === currentPage ? s.pageBtnActive : s.pageBtnInactive}`}
                onClick={() => setCurrentPage(p)}
                aria-label={`Page ${p}`}
                aria-current={p === currentPage ? "page" : undefined}
              >{p}</button>
            )
          )}

          <button
            className={`${s.pageBtn} ${s.pageBtnNav}`}
            onClick={() => setCurrentPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            aria-label="Next page"
          >›</button>
        </nav>
      </div>
    </section>
  );
});

InvoicesTable.displayName = "InvoicesTable";
export default InvoicesTable;
