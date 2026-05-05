// ─── Pages/Finance.jsx ───────────────────────────────────────────────────────
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Download,
  Plus,
  ReceiptText,
  RefreshCcw,
} from "lucide-react";
import financeService from "../utils/financeService";
import StatCard, { SkeletonStatCard } from "../components/Finance/StatCard";
import CashFlowChart from "../components/Finance/CashFlowChart";
import ExpenseBreakdown from "../components/Finance/ExpenseBreakdown";
import InvoicesTable from "../components/Finance/InvoicesTable";
import ExportReportsModal from "../components/Finance/ExportReportsModal";
import s from "../components/Finance/Finance.module.css";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";

const ErrorCard = ({ message, onRetry }) => (
  <div className={s.errorCard} role="alert">
    <div className={s.errorIconBadge} aria-hidden="true">
      <AlertTriangle className={s.errorIconSvg} />
    </div>
    <p className={s.errorTitle}>Failed to load data</p>
    <p className={s.errorMsg}>{message}</p>
    <button className={s.btnRetry} onClick={onRetry}>
      <RefreshCcw className={s.btnIcon} aria-hidden="true" />
      Retry
    </button>
  </div>
);

export default function Finance() {
  const [pageData,   setPageData]   = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [activeNav,  setActiveNav]  = useState("finance");
  const [showExport, setShowExport] = useState(false);

  const navigate = useNavigate();

  const loadData = useCallback(() => {
    const controller = new AbortController();
    const { signal } = controller;
    setLoading(true);
    setError(null);

    Promise.all([
      financeService.fetchStatCards(signal),
      financeService.fetchCashFlow(signal),
      financeService.fetchExpenseBreakdown(signal),
      financeService.fetchInvoices(signal),
    ]).then(([statCards, cashFlow, expenseBreakdown, invoices]) => {
      const firstError = [statCards, cashFlow, expenseBreakdown, invoices]
        .find((r) => r.error)?.error;
      if (firstError) {
        setError(firstError);
      } else {
        setPageData({
          statCards:        statCards.data,
          cashFlow:         cashFlow.data,
          expenseBreakdown: expenseBreakdown.data,
          invoices:         invoices.data,
        });
      }
      setLoading(false);
    });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const cleanup = loadData();
    return cleanup;
  }, [loadData]);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#F8F9FA" }}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      <div style={{ marginLeft: 220, flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Header breadcrumbs={["Synergy ERP", "Finance", "Overview"]} />

        <main className={s.page}>

          <header className={s.pageHeader}>
            <div>
              <h1 className={s.pageTitle}>Finance Overview</h1>
              <p className={s.pageSub}>Comprehensive visibility into your company's fiscal performance.</p>
            </div>
            <div className={s.headerActions}>

              <button
                className={`${s.btn} ${s.btnOutline}`}
                aria-label="Export reports"
                onClick={() => setShowExport(true)}
                disabled={loading || !!error}
              >
                <Download className={s.btnIcon} aria-hidden="true" />
                Export Reports
              </button>

              <button
                className={`${s.btn} ${s.btnOutline}`}
                onClick={() => navigate("/invoices")}
                aria-label="View all invoices"
              >
                <ReceiptText className={s.btnIcon} aria-hidden="true" />
                All Invoices
              </button>

              <button
                className={`${s.btn} ${s.btnPrimary}`}
                onClick={() => navigate("/invoices/new")}
                aria-label="Create new invoice"
              >
                <Plus className={s.btnIcon} aria-hidden="true" />
                New Invoice
              </button>
            </div>
          </header>

          {error && <ErrorCard message={error} onRetry={loadData} />}

          {!error && (
            <div className={s.statGrid}>
              {loading
                ? Array.from({ length: 4 }, (_, i) => <SkeletonStatCard key={i} />)
                : pageData.statCards.map((c) => <StatCard key={c.id} {...c} />)
              }
            </div>
          )}

          {!loading && !error && (
            <div className={s.chartsRow}>
              <CashFlowChart />
              <ExpenseBreakdown />
            </div>
          )}

          {!loading && !error && (
            <div>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
                <h2 style={{ fontSize:16, fontWeight:700, color:"#1A1D23", margin:0 }}>
                  Recent Invoices
                </h2>
                <button
                  onClick={() => navigate("/invoices")}
                  style={{
                    display:"inline-flex", alignItems:"center", gap:6,
                    padding:"7px 14px", borderRadius:8,
                    border:"1.5px solid #D0D7DE", background:"#fff",
                    color:"#3B5BDB", fontSize:13, fontWeight:600, cursor:"pointer",
                  }}
                  aria-label="View all invoices"
                >
                  <ReceiptText size={15} aria-hidden="true" />
                  View All Invoices
                </button>
              </div>
              <InvoicesTable invoices={pageData.invoices} />
            </div>
          )}

        </main>
      </div>

      <ExportReportsModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        pageData={pageData}
      />

    </div>
  );
}
