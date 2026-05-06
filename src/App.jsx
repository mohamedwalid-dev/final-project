// ─── App.jsx ──────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import LoginPage          from "./Pages/LoginPage";        // ← سواء عندك في Pages أو root غيّر المسار
import DashboardPage      from "./Pages/Dashboardpage";
import Finance            from "./Pages/Finance";
import FinanceDashboard   from "./Pages/FinanceDashboard";
import CreateInvoicePage  from "./Pages/CreateInvoicePage";
import InvoicesManagement from "./Pages/InvoicesManagement";
import HRPage             from "./Pages/HRPage";
import SalesPage          from "./Pages/SalesPage";
import InventoryPage      from "./Pages/InventoryPage";
import SupportPage        from "./Pages/SupportPage";
import DesignSystemPage   from "./Pages/DesignSystemPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── الـ root يروح للـ login أولاً ── */}
        <Route path="/"        element={<Navigate to="/login" replace />} />
        <Route path="/login"   element={<LoginPage />} />

        <Route path="/dashboard"           element={<DashboardPage />} />
        <Route path="/finance"             element={<Finance />} />
        <Route path="/finance/dashboard"   element={<FinanceDashboard />} />
        <Route path="/invoices/new"        element={<CreateInvoicePage />} />
        <Route path="/invoices"            element={<InvoicesManagement />} />
        <Route path="/hr"                  element={<HRPage />} />
        <Route path="/sales"               element={<SalesPage />} />
        <Route path="/inventory"           element={<InventoryPage />} />
        <Route path="/support"             element={<SupportPage />} />
        <Route path="/design"             element={<DesignSystemPage />} />
        <Route path="/FinanceDashboard"    element={<FinanceDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;