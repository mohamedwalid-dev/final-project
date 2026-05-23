// ─── Pages/CreateInvoicePage.jsx ─────────────────────────────────────────────
// ✅ Pure JS — no TypeScript
// ✅ 4-step wizard: Billing Info → Line Items → Calculations → Finalize
// ✅ Live Summary sidebar (updates in real time)
// ✅ Same structure as Finance.jsx (Sidebar + Header + main content)
// ✅ All styles from CreateInvoice.module.css — no inline styles except layout glue
// ✅ useCreateInvoice hook for all state/logic

import { useState, useEffect, useRef } from "react";
import invoicesService from "../utils/invoicesService";
import { useNavigate } from "react-router-dom";
import useCreateInvoice, { STEPS, TAX_OPTIONS } from "../hooks/useCreateInvoice";
import { formatCurrency } from "../utils/formatters";
import s from "../components/Finance/CreateInvoice.module.css";
import shell from "../styles/AppShell.module.css";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header from "../components/Finance/Layout/Header";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Building2,
  Calculator,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Keyboard,
  Rocket,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";

export const INVOICE_STATUS_OPTIONS = ["Paid", "Pending", "Overdue"];

const STEP_ICONS = {
  billing: Building2,
  "line-items": FileText,
  calculations: Calculator,
  finalize: ClipboardCheck,
};

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function Stepper({ currentStep, goToStep }) {
  return (
    <div className={s.stepper} role="list" aria-label="Invoice creation steps">
      {STEPS.map((step, idx) => {
        const isDone = idx < currentStep;
        const isActive = idx === currentStep;
        const Icon = STEP_ICONS[step.icon] ?? FileText;

        return (
          <div key={step.id} style={{ display: "flex", alignItems: "center" }}>
            <div
              className={s.stepItem}
              role="listitem"
              aria-current={isActive ? "step" : undefined}
            >
              <button
                className={`${s.stepCircle} ${
                  isDone
                    ? s.stepCircleDone
                    : isActive
                    ? s.stepCircleActive
                    : s.stepCircleInactive
                }`}
                onClick={() => goToStep(idx)}
                aria-label={`Step ${idx + 1}: ${step.label}`}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  cursor: idx < currentStep ? "pointer" : "default",
                }}
              >
                {isDone ? (
                  <CheckCircle2 className={s.stepIconSvg} aria-hidden="true" />
                ) : (
                  <Icon className={s.stepIconSvg} aria-hidden="true" />
                )}
              </button>

              <span className={`${s.stepLabel} ${isActive ? s.stepLabelActive : ""}`}>
                {step.label}
              </span>
            </div>

            {idx < STEPS.length - 1 && (
              <div
                className={`${s.stepConnector} ${
                  idx < currentStep ? s.stepConnectorActive : ""
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function LiveSummary({ summary }) {
  const { subtotal, taxRate, taxAmount, discountAmt, grandTotal } = summary;

  return (
    <aside>
      <div className={s.summaryCard}>
        <h3 className={s.summaryTitle}>
          <BarChart3 className={s.inlineIcon} aria-hidden="true" />
          Live Summary
        </h3>

        <div className={s.summaryRow}>
          <span className={s.summaryLabel}>Subtotal</span>
          <span className={s.summaryValue}>{formatCurrency(subtotal)}</span>
        </div>

        <div className={s.summaryRow}>
          <span className={s.summaryLabel}>Tax ({taxRate.toFixed(0)}%)</span>
          <span className={s.summaryTax}>+{formatCurrency(taxAmount)}</span>
        </div>

        <div className={s.summaryRow}>
          <span className={s.summaryLabel}>Discount</span>
          <span className={s.summaryDiscount}>-{formatCurrency(discountAmt)}</span>
        </div>

        <hr className={s.summaryDivider} />

        <div className={s.summaryTotal}>
          <span className={s.summaryTotalLabel}>Grand Total</span>
          <span className={s.summaryTotalValue}>{formatCurrency(grandTotal)}</span>
        </div>

        <p className={s.summaryNote}>
          Invoice will be generated in USD. You can change currency in the final review step.
        </p>
      </div>

      <div className={s.helpBox}>
        <p className={s.helpTitle}>Need Help?</p>
        <p className={s.helpText}>
          Our AI can suggest descriptions based on your previous 10 invoices.
        </p>
        <button className={s.helpBtn}>
          <Sparkles className={s.inlineIcon} aria-hidden="true" />
          Use AI Suggestions
        </button>
      </div>
    </aside>
  );
}

function StepBillingInfo({ form, setField, errors }) {
  return (
    <>
      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon} aria-hidden="true">
            <Building2 className={s.sectionIconSvg} />
          </div>
          <div>
            <h2 className={s.sectionTitle}>Client Information</h2>
            <p className={s.sectionSub}>
              Select or add a new customer for this billing cycle.
            </p>
          </div>
        </div>

        <div className={s.formGrid}>
          <div className={s.formGroup}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="customerName">
              Customer Name
            </label>
            <input
              id="customerName"
              className={`${s.input} ${errors.customerName ? s.hasError : ""}`}
              value={form.customerName}
              onChange={(e) => setField("customerName", e.target.value)}
              placeholder="Search client directory..."
            />
            {errors.customerName && (
              <p className={s.fieldError}>{errors.customerName}</p>
            )}
          </div>

          <div className={s.formGroup}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="billingEmail">
              Billing Email
            </label>
            <input
              id="billingEmail"
              type="email"
              className={`${s.input} ${errors.billingEmail ? s.hasError : ""}`}
              value={form.billingEmail}
              onChange={(e) => setField("billingEmail", e.target.value)}
              placeholder="finance@clientcorp.com"
            />
            {errors.billingEmail && (
              <p className={s.fieldError}>{errors.billingEmail}</p>
            )}
          </div>

          <div className={`${s.formGroup} ${s.formGridFull}`}>
            <label
              className={`${s.label} ${s.labelRequired}`}
              htmlFor="billingAddress"
            >
              Billing Address
            </label>
            <textarea
              id="billingAddress"
              className={`${s.textarea} ${errors.billingAddress ? s.hasError : ""}`}
              value={form.billingAddress}
              onChange={(e) => setField("billingAddress", e.target.value)}
              placeholder="123 Enterprise Way, Suite 400, Silicon Valley, CA 94043"
            />
            {errors.billingAddress && (
              <p className={s.fieldError}>{errors.billingAddress}</p>
            )}
          </div>
        </div>
      </section>

      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon} aria-hidden="true">
            <CalendarDays className={s.sectionIconSvg} />
          </div>
          <div>
            <h2 className={s.sectionTitle}>Invoice Timeline</h2>
            <p className={s.sectionSub}>
              Set issue date, due date, PO reference, currency, and invoice status.
            </p>
          </div>
        </div>

        <div className={s.formGrid}>
          <div className={s.formGroup}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="issueDate">
              Issue Date
            </label>
            <input
              id="issueDate"
              type="date"
              className={`${s.input} ${errors.issueDate ? s.hasError : ""}`}
              value={form.issueDate}
              onChange={(e) => setField("issueDate", e.target.value)}
            />
            {errors.issueDate && <p className={s.fieldError}>{errors.issueDate}</p>}
          </div>

          <div className={s.formGroup}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="dueDate">
              Due Date
            </label>
            <input
              id="dueDate"
              type="date"
              className={`${s.input} ${errors.dueDate ? s.hasError : ""}`}
              value={form.dueDate}
              onChange={(e) => setField("dueDate", e.target.value)}
            />
            {errors.dueDate && <p className={s.fieldError}>{errors.dueDate}</p>}
          </div>

          <div className={s.formGroup}>
            <label className={s.label} htmlFor="poNumber">
              PO Number
            </label>
            <input
              id="poNumber"
              className={s.input}
              value={form.poNumber}
              onChange={(e) => setField("poNumber", e.target.value)}
              placeholder="PO-8829-X"
            />
          </div>

          <div className={s.formGroup}>
            <label className={s.label} htmlFor="currency">
              Currency
            </label>
            <select
              id="currency"
              className={s.select}
              value={form.currency}
              onChange={(e) => setField("currency", e.target.value)}
            >
              <option value="USD">USD — US Dollar</option>
              <option value="EGP">EGP — Egyptian Pound</option>
              <option value="SAR">SAR — Saudi Riyal</option>
            </select>
          </div>

          <div className={s.formGroup}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="status">
              Invoice Status
            </label>
            <select
              id="status"
              name="status"
              className={`${s.select} ${errors.status ? s.hasError : ""}`}
              value={form.status}
              onChange={(e) => setField("status", e.target.value)}
            >
              {INVOICE_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
            {errors.status && <p className={s.fieldError}>{errors.status}</p>}
          </div>
        </div>
      </section>
    </>
  );
}

function StepLineItems({
  lineItems,
  addLineItem,
  removeLineItem,
  updateLineItem,
  errors,
}) {
  return (
    <section className={s.sectionCard}>
      <div className={s.lineItemsHeader}>
        <div className={s.sectionHeader} style={{ marginBottom: 0 }}>
          <div className={s.sectionIcon} aria-hidden="true">
            <FileText className={s.sectionIconSvg} />
          </div>
          <div>
            <h2 className={s.sectionTitle}>Line Items</h2>
            <p className={s.sectionSub}>Add products or services to this invoice.</p>
          </div>
        </div>
      </div>

      {errors._lineItems && (
        <p className={s.fieldError} style={{ marginBottom: 12 }}>
          {errors._lineItems}
        </p>
      )}

      <div style={{ overflowX: "auto" }}>
        <table className={s.lineItemsTable} aria-label="Line items">
          <thead>
            <tr>
              <th className={s.lineItemTh} style={{ width: "40%" }}>
                Description
              </th>
              <th className={s.lineItemTh} style={{ width: "12%" }}>
                Qty
              </th>
              <th className={s.lineItemTh} style={{ width: "18%" }}>
                Unit Price
              </th>
              <th className={s.lineItemTh} style={{ width: "18%" }}>
                Total
              </th>
              <th className={s.lineItemTh} style={{ width: "12%" }}></th>
            </tr>
          </thead>

          <tbody>
            {lineItems.map((item, idx) => {
              const rowTotal =
                (parseFloat(item.qty) || 0) * (parseFloat(item.unitPrice) || 0);

              return (
                <tr key={item.id} className={s.lineItemTr}>
                  <td className={s.lineItemTd}>
                    <input
                      className={s.lineItemInput}
                      value={item.description}
                      onChange={(e) =>
                        updateLineItem(item.id, "description", e.target.value)
                      }
                      placeholder="e.g. Web Development Services"
                      aria-label={`Description for item ${idx + 1}`}
                      style={errors[`desc_${idx}`] ? { borderColor: "#c0392b" } : {}}
                    />
                    {errors[`desc_${idx}`] && (
                      <p className={s.fieldError}>{errors[`desc_${idx}`]}</p>
                    )}
                  </td>

                  <td className={s.lineItemTd}>
                    <input
                      type="number"
                      min="0"
                      className={s.lineItemInput}
                      value={item.qty}
                      onChange={(e) => updateLineItem(item.id, "qty", e.target.value)}
                      aria-label={`Quantity for item ${idx + 1}`}
                      style={{ width: 64 }}
                    />
                  </td>

                  <td className={s.lineItemTd}>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className={s.lineItemInput}
                      value={item.unitPrice}
                      onChange={(e) =>
                        updateLineItem(item.id, "unitPrice", e.target.value)
                      }
                      aria-label={`Unit price for item ${idx + 1}`}
                    />
                  </td>

                  <td className={s.lineItemTd}>
                    <span className={s.lineItemTotal}>
                      {formatCurrency(rowTotal)}
                    </span>
                  </td>

                  <td className={s.lineItemTd}>
                    <button
                      className={s.btnDanger}
                      onClick={() => removeLineItem(item.id)}
                      aria-label={`Remove item ${idx + 1}`}
                      disabled={lineItems.length === 1}
                    >
                      <Trash2 className={s.iconOnly} aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <button className={s.addLineBtn} onClick={addLineItem} aria-label="Add line item">
        + Add Line Item
      </button>
    </section>
  );
}

function StepCalculations({ form, setField, errors }) {
  return (
    <>
      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon} aria-hidden="true">
            <Calculator className={s.sectionIconSvg} />
          </div>
          <div>
            <h2 className={s.sectionTitle}>Tax Configuration</h2>
            <p className={s.sectionSub}>
              System will apply client tax rules automatically.
            </p>
          </div>
        </div>

        <div className={s.calcGrid}>
          {TAX_OPTIONS.map((opt) => {
            const isActive = form.taxOption === opt.id;

            return (
              <div
                key={opt.id}
                className={`${s.taxOption} ${isActive ? s.taxOptionActive : ""}`}
                onClick={() => setField("taxOption", opt.id)}
                role="radio"
                aria-checked={isActive}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && setField("taxOption", opt.id)}
              >
                <div className={`${s.taxRadio} ${isActive ? s.taxRadioActive : ""}`}>
                  {isActive && <div className={s.taxRadioDot} />}
                </div>

                <div>
                  <p className={s.taxOptionLabel}>{opt.label}</p>
                  <p className={s.taxOptionSub}>{opt.sub}</p>
                </div>
              </div>
            );
          })}
        </div>

        {form.taxOption === "custom" && (
          <div className={s.formGroup} style={{ marginTop: 16 }}>
            <label
              className={`${s.label} ${s.labelRequired}`}
              htmlFor="customTaxRate"
            >
              Custom Tax Rate (%)
            </label>
            <input
              id="customTaxRate"
              type="number"
              min="0"
              max="100"
              step="0.1"
              className={`${s.input} ${errors.customTaxRate ? s.hasError : ""}`}
              value={form.customTaxRate}
              onChange={(e) => setField("customTaxRate", e.target.value)}
              placeholder="e.g. 7.5"
              style={{ maxWidth: 200 }}
            />
            {errors.customTaxRate && (
              <p className={s.fieldError}>{errors.customTaxRate}</p>
            )}
          </div>
        )}
      </section>

      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon} aria-hidden="true">
            <Calculator className={s.sectionIconSvg} />
          </div>
          <div>
            <h2 className={s.sectionTitle}>Discount & Notes</h2>
            <p className={s.sectionSub}>
              Apply a flat discount and add internal notes.
            </p>
          </div>
        </div>

        <div className={s.formGrid}>
          <div className={s.formGroup}>
            <label className={s.label} htmlFor="discount">
              Discount Amount (USD)
            </label>
            <input
              id="discount"
              type="number"
              min="0"
              step="0.01"
              className={`${s.input} ${errors.discount ? s.hasError : ""}`}
              value={form.discount}
              onChange={(e) => setField("discount", e.target.value)}
              placeholder="e.g. 500"
            />
            {errors.discount && <p className={s.fieldError}>{errors.discount}</p>}
          </div>

          <div className={`${s.formGroup} ${s.formGridFull}`}>
            <label className={s.label} htmlFor="notes">
              Internal Notes
            </label>
            <textarea
              id="notes"
              className={s.textarea}
              value={form.notes}
              onChange={(e) => setField("notes", e.target.value)}
              placeholder="Payment terms, special instructions, internal remarks..."
            />
          </div>
        </div>
      </section>
    </>
  );
}

function StepFinalize({
  form,
  lineItems,
  summary,
  submitting,
  submitted,
  handleSubmit,
  reset,
  navigate,
}) {
  if (submitted) {
    return (
      <div className={s.finalCard}>
        <div className={s.finalIcon} aria-hidden="true">
          <CheckCircle2 className={s.finalIconSvg} />
        </div>
        <h2 className={s.finalTitle}>Invoice Created Successfully!</h2>
        <p className={s.finalSub}>Your invoice has been saved and is ready to send.</p>

        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <button className={`${s.btn} ${s.btnOutline}`} onClick={reset}>
            + Create Another
          </button>
          <button className={`${s.btn} ${s.btnPrimary}`} onClick={() => navigate("/finance")}>
            <ArrowLeft className={s.inlineIcon} aria-hidden="true" />
            Back to Finance
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={s.finalCard}>
      <div className={s.finalIcon} aria-hidden="true">
        <ClipboardCheck className={s.finalIconSvg} />
      </div>
      <h2 className={s.finalTitle}>Review & Finalize</h2>
      <p className={s.finalSub}>Please review your invoice before generating it.</p>

      <div className={s.finalSummaryGrid}>
        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Customer</p>
          <p className={s.finalSummaryValue}>{form.customerName || "—"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Billing Email</p>
          <p className={s.finalSummaryValue}>{form.billingEmail || "—"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Issue Date</p>
          <p className={s.finalSummaryValue}>{form.issueDate || "—"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Due Date</p>
          <p className={s.finalSummaryValue}>{form.dueDate || "—"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Status</p>
          <p className={s.finalSummaryValue}>{form.status || "Pending"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Line Items</p>
          <p className={s.finalSummaryValue}>
            {lineItems.length} item{lineItems.length !== 1 ? "s" : ""}
          </p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Currency</p>
          <p className={s.finalSummaryValue}>{form.currency}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>PO Number</p>
          <p className={s.finalSummaryValue}>{form.poNumber || "—"}</p>
        </div>

        <div className={s.finalSummaryItem}>
          <p className={s.finalSummaryLabel}>Grand Total</p>
          <p className={s.finalSummaryValue} style={{ color: "#3B5BDB", fontSize: 18 }}>
            {formatCurrency(summary.grandTotal)}
          </p>
        </div>
      </div>

      <button
        className={`${s.btn} ${s.btnPrimary}`}
        onClick={handleSubmit}
        disabled={submitting}
        style={{ fontSize: 14, padding: "12px 32px" }}
      >
        {submitting ? (
          "Generating..."
        ) : (
          <>
            <Rocket className={s.inlineIcon} aria-hidden="true" />
            Generate Invoice
          </>
        )}
      </button>
    </div>
  );
}

  export default function CreateInvoicePage({
    mode = "create",
    invoiceId = null,
    initialInvoice = null,
  }) {
    const [activeNav, setActiveNav] = useState("finance");
    const isEditMode = mode === "edit";
    const didPrefillRef = useRef(false);

  let navigate;

  try {
    navigate = useNavigate();
  } catch {
    navigate = (path) => {
      window.location.href = path;
    };
  }

  const handleSubmit = async (payload) => {
  try {
    const { form, lineItems } = payload;

    const invoiceData = {
      clientInformation: {
        customerName: form.customerName,
        billingEmail: form.billingEmail,
        billingAddress: form.billingAddress,
      },
      invoiceTimeline: {
        issueDate: new Date(form.issueDate),
        dueDate: new Date(form.dueDate),
        poNumber: form.poNumber || null,
        currency: form.currency || "USD",
      },
      lineItems: lineItems.map((item) => ({
        description: item.description,
        quantity: parseInt(item.qty) || 1,
        unitPrice: parseFloat(item.unitPrice) || 0,
        total: (parseFloat(item.qty) || 0) * (parseFloat(item.unitPrice) || 0),
      })),
      taxConfiguration: {
        customTaxRate:
          form.taxOption === "custom"
            ? parseFloat(form.customTaxRate) || 0
            : TAX_OPTIONS.find((o) => o.id === form.taxOption)?.rate || 0,
      },
      discountAndNotes: {
        discountAmountUSD: parseFloat(form.discount) || 0,
        internalNotes: form.notes || "",
      },
      status: form.status || "Pending",
    };

    const result = isEditMode
      ? await invoicesService.updateInvoice(invoiceId, invoiceData)
      : await invoicesService.createInvoice(invoiceData);

    if (result.error) {
      alert(result.error);
      return;
    }

    alert(isEditMode ? "Invoice updated successfully!" : "Invoice created successfully!");
    navigate("/invoices");
  } catch (err) {
    console.error("Invoice submit error:", err);
    alert(isEditMode ? "Failed to update invoice." : "Failed to create invoice.");
  }
};

  const {
  currentStep,
  form,
  lineItems,
  errors,
  submitting,
  submitted,
  summary,
  setField,
  addLineItem,
  removeLineItem,
  updateLineItem,
  replaceLineItems,
  goNext,
  goBack,
  goToStep,
  handleSubmit: submit,
  reset,
} = useCreateInvoice({ onSubmit: handleSubmit }); 

  const isLastStep = currentStep === STEPS.length - 1;
   useEffect(() => {
  if (!isEditMode || !initialInvoice || didPrefillRef.current) return;

  didPrefillRef.current = true;

  setField("customerName", initialInvoice.clientInformation?.customerName || "");
  setField("billingEmail", initialInvoice.clientInformation?.billingEmail || "");
  setField("billingAddress", initialInvoice.clientInformation?.billingAddress || "");

  setField(
    "issueDate",
    initialInvoice.invoiceTimeline?.issueDate
      ? initialInvoice.invoiceTimeline.issueDate.slice(0, 10)
      : ""
  );

  setField(
    "dueDate",
    initialInvoice.invoiceTimeline?.dueDate
      ? initialInvoice.invoiceTimeline.dueDate.slice(0, 10)
      : ""
  );

  setField("poNumber", initialInvoice.invoiceTimeline?.poNumber || "");
  setField("currency", initialInvoice.invoiceTimeline?.currency || "USD");
  setField("status", initialInvoice.status || "Pending");

  const customTaxRate = initialInvoice.taxConfiguration?.customTaxRate ?? 0;
  setField("taxOption", customTaxRate > 0 ? "custom" : "none");
  setField("customTaxRate", String(customTaxRate));

  setField(
    "discount",
    String(initialInvoice.discountAndNotes?.discountAmountUSD || 0)
  );

  setField(
    "notes",
    initialInvoice.discountAndNotes?.internalNotes || ""
  );

  if (typeof replaceLineItems === "function") {
    replaceLineItems(
      Array.isArray(initialInvoice.lineItems)
        ? initialInvoice.lineItems.map((item) => ({
            id: item._id || crypto.randomUUID(),
            description: item.description || "",
            qty: String(item.quantity || 1),
            unitPrice: String(item.unitPrice || 0),
          }))
        : []
    );
  }
}, [isEditMode, initialInvoice, setField, replaceLineItems]);
  return (
    <div className={shell.appShell}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      <div className={shell.mainArea}>
        <Header breadcrumbs={["Prime ERP", "Finance", "Invoices", "Create New Record"]} />

        <main className={s.page}>
          <header className={s.pageHeader}>
            <div>
              <h1 className={s.pageTitle}>Create New Invoice</h1>
              <p className={s.pageSub}>
                Complete the steps below to generate a professional invoice.
                System will automatically apply client tax rules.
              </p>
            </div>

            <div className={s.headerActions}>
              <button className={`${s.btn} ${s.btnOutline}`} aria-label="Shortcuts">
                <Keyboard className={s.inlineIcon} aria-hidden="true" />
                Shortcuts
              </button>

              <button
                className={`${s.btn} ${s.btnPrimary}`}
                onClick={goNext}
                aria-label="Save as draft"
              >
                <Save className={s.inlineIcon} aria-hidden="true" />
                Save Draft
              </button>
            </div>
          </header>

          <Stepper currentStep={currentStep} goToStep={goToStep} />

          <div className={s.formLayout}>
            <div className={s.formMain}>
              {currentStep === 0 && (
                <StepBillingInfo form={form} setField={setField} errors={errors} />
              )}

              {currentStep === 1 && (
                <StepLineItems
                  lineItems={lineItems}
                  addLineItem={addLineItem}
                  removeLineItem={removeLineItem}
                  updateLineItem={updateLineItem}
                  errors={errors}
                />
              )}

              {currentStep === 2 && (
                <StepCalculations form={form} setField={setField} errors={errors} />
              )}

              {currentStep === 3 && (
                <StepFinalize
                  form={form}
                  lineItems={lineItems}
                  summary={summary}
                  submitting={submitting}
                  submitted={submitted}
                  handleSubmit={submit}
                  reset={reset}
                  navigate={navigate}
                />
              )}

              {!submitted && (
                <div className={s.stepFooter}>
                  <span className={s.stepCount}>
                    Step {currentStep + 1} of {STEPS.length}
                  </span>

                  <div className={s.footerActions}>
                    <button
                      className={s.btnGhost}
                      onClick={goBack}
                      disabled={currentStep === 0}
                      aria-label="Go back"
                    >
                      <ArrowLeft className={s.inlineIcon} aria-hidden="true" />
                      Back
                    </button>

                    {!isLastStep && (
                      <button
                        className={`${s.btn} ${s.btnPrimary}`}
                        onClick={goNext}
                        aria-label="Continue to next step"
                      >
                        Continue
                        <ArrowRight className={s.inlineIcon} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className={s.formSide}>
              <LiveSummary summary={summary} />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
