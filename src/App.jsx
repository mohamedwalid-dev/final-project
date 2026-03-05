// ─── App.jsx ──────────────────────────────────────────────────────────────────
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Finance from "./Pages/Finance";
import CreateInvoicePage from "./Pages/CreateInvoicePage";
import InvoicesManagement from "./Pages/InvoicesManagement";
import HRPage from "./Pages/HRPage";


function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"             element={<Navigate to="/finance" replace />} />
        <Route path="/finance"      element={<Finance />} />
        <Route path="/invoices/new" element={<CreateInvoicePage />} />
        <Route path="/invoices" element={<InvoicesManagement />} />
        <Route path="/hr" element={<HRPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;