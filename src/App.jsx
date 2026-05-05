// ─── App.jsx ──────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import DashboardPage      from "./pages/Dashboardpage";
import Finance            from "./pages/Finance";
import CreateInvoicePage  from "./pages/CreateInvoicePage";
import InvoicesManagement from "./pages/InvoicesManagement";
import HRPage             from "./pages/HRPage";
import SalesPage          from "./pages/SalesPage";
import InventoryPage      from "./pages/InventoryPage";
import SupportPage        from "./pages/SupportPage";
import DesignSystemPage   from "./pages/DesignSystemPage";
import EditInvoicePage from "./pages/EditInvoicePage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/finance" element={<Finance />} />

            {/* Invoices routes */}
            <Route path="/invoices" element={<InvoicesManagement />} />
            <Route path="/invoices/new" element={<CreateInvoicePage />} />
            <Route path="/invoices/:id/edit" element={<EditInvoicePage />} />

            <Route path="/hr" element={<HRPage />} />
            <Route path="/sales" element={<SalesPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/design" element={<DesignSystemPage />} />
          </Route>

          {/* 404 fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;