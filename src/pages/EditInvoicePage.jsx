// ─── pages/EditInvoicePage.jsx ────────────────────────────────────────────────

import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import CreateInvoicePage from "./CreateInvoicePage";
import invoicesService from "../utils/invoicesService";

export default function EditInvoicePage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [invoice, setInvoice] = useState(location.state?.invoice || null);
  const [loading, setLoading] = useState(!location.state?.invoice);
  const [error, setError] = useState("");

  useEffect(() => {
    if (location.state?.invoice) {
      console.log("Invoice loaded from route state:", location.state.invoice);
      return;
    }

    const controller = new AbortController();

    const loadInvoice = async () => {
      try {
        setLoading(true);
        setError("");

        console.log("Fetching invoice by id:", id);

        const result = await invoicesService.fetchInvoiceById(
          id,
          controller.signal
        );

        console.log("Fetch invoice result:", result);

        if (result.error) {
          setError(result.error);
          setLoading(false);
          return;
        }

        if (!result.data) {
          setError("Invoice not found");
          setLoading(false);
          return;
        }

        setInvoice(result.data);
        setLoading(false);
      } catch (err) {
        console.error("Edit invoice load failed:", err);
        setError(err.message || "Failed to load invoice");
        setLoading(false);
      }
    };

    loadInvoice();

    return () => controller.abort();
  }, [id, location.state]);

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#f7f8fa",
          color: "#111827",
          display: "grid",
          placeItems: "center",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <h2>Loading invoice...</h2>
          <p>Invoice ID: {id}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#f7f8fa",
          color: "#111827",
          display: "grid",
          placeItems: "center",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div
          style={{
            width: "420px",
            padding: "24px",
            background: "#fff",
            borderRadius: "16px",
            boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
            textAlign: "center",
          }}
        >
          <h2>Failed to load invoice</h2>
          <p style={{ color: "#dc2626" }}>{error}</p>
          <p style={{ fontSize: "13px", color: "#6b7280" }}>
            Invoice ID: {id}
          </p>

          <button
            onClick={() => navigate("/invoices")}
            style={{
              marginTop: "16px",
              padding: "10px 16px",
              border: "0",
              borderRadius: "10px",
              background: "#4f46e5",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            Back to invoices
          </button>
        </div>
      </div>
    );
  }

  return (
    <CreateInvoicePage
      mode="edit"
      invoiceId={id}
      initialInvoice={invoice}
    />
  );
}