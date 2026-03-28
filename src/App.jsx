// ─── App.jsx ──────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardPage      from "./Pages/Dashboardpage";
import Finance            from "./Pages/Finance";
import CreateInvoicePage  from "./Pages/CreateInvoicePage";
import InvoicesManagement from "./Pages/InvoicesManagement";
import HRPage             from "./Pages/HRPage";
import SalesPage          from "./Pages/SalesPage";
import InventoryPage      from "./Pages/InventoryPage";   // ✅ NEW
import SupportPage        from "./Pages/SupportPage";       // ✅ NEW
import DesignSystemPage   from "./Pages/DesignSystemPage";   // ✅ NEW

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"             element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard"    element={<DashboardPage />} />
        <Route path="/finance"      element={<Finance />} />
        <Route path="/invoices/new" element={<CreateInvoicePage />} />
        <Route path="/invoices"     element={<InvoicesManagement />} />
        <Route path="/hr"           element={<HRPage />} />
        <Route path="/sales"        element={<SalesPage />} />
        <Route path="/inventory"    element={<InventoryPage />} />   {/* ✅ NEW */}
        <Route path="/support"      element={<SupportPage />} />     {/* ✅ NEW */}
        <Route path="/design"       element={<DesignSystemPage />} />{/* ✅ NEW */}
      </Routes>
    </BrowserRouter>
  );
}

export default App;