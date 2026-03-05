// ─── Pages/CreateInvoicePage.jsx ─────────────────────────────────────────────
// ✅ Pure JS — no TypeScript
// ✅ 4-step wizard: Billing Info → Line Items → Calculations → Finalize
// ✅ Live Summary sidebar (updates in real time)
// ✅ Same structure as Finance.jsx (Sidebar + Header + main content)
// ✅ All styles from CreateInvoice.module.css — no inline styles except layout glue
// ✅ useCreateInvoice hook for all state/logic

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useCreateInvoice, { STEPS, TAX_OPTIONS } from "../hooks/useCreateInvoice";
import { formatCurrency } from "../utils/formatters";
import s from "../components/Finance/CreateInvoice.module.css";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components (kept in same file — same pattern as Finance.jsx)
// ─────────────────────────────────────────────────────────────────────────────

// ── Stepper ───────────────────────────────────────────────────────────────────
function Stepper({ currentStep, goToStep }) {
  return (
    <div className={s.stepper} role="list" aria-label="Invoice creation steps">
      {STEPS.map((step, idx) => {
        const isDone   = idx < currentStep;
        const isActive = idx === currentStep;

        return (
          <div key={step.id} style={{ display: "flex", alignItems: "center" }}>
            <div
              className={s.stepItem}
              role="listitem"
              aria-current={isActive ? "step" : undefined}
            >
              <button
                className={`${s.stepCircle} ${
                  isDone   ? s.stepCircleDone    :
                  isActive ? s.stepCircleActive  :
                             s.stepCircleInactive
                }`}
                onClick={() => goToStep(idx)}
                aria-label={`Step ${idx + 1}: ${step.label}`}
                style={{ background: "none", border: "none", padding: 0, cursor: idx < currentStep ? "pointer" : "default" }}
              >
                {isDone ? "✓" : step.icon}
              </button>
              <span className={`${s.stepLabel} ${isActive ? s.stepLabelActive : ""}`}>
                {step.label}
              </span>
            </div>

            {idx < STEPS.length - 1 && (
              <div className={`${s.stepConnector} ${idx < currentStep ? s.stepConnectorActive : ""}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Live Summary Sidebar ──────────────────────────────────────────────────────
function LiveSummary({ summary }) {
  const { subtotal, taxRate, taxAmount, discountAmt, grandTotal } = summary;

  return (
    <aside>
      <div className={s.summaryCard}>
        <h3 className={s.summaryTitle}>📊 Live Summary</h3>

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
        <button className={s.helpBtn}>✨ Use AI Suggestions</button>
      </div>
    </aside>
  );
}

// ── Step 1: Billing Info ──────────────────────────────────────────────────────
function StepBillingInfo({ form, setField, errors }) {
  return (
    <>
      {/* Client Information */}
      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon}>🏢</div>
          <div>
            <h2 className={s.sectionTitle}>Client Information</h2>
            <p className={s.sectionSub}>Select or add a new customer for this billing cycle.</p>
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
            {errors.customerName && <p className={s.fieldError}>{errors.customerName}</p>}
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
            {errors.billingEmail && <p className={s.fieldError}>{errors.billingEmail}</p>}
          </div>

          <div className={`${s.formGroup} ${s.formGridFull}`}>
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="billingAddress">
              Billing Address
            </label>
            <textarea
              id="billingAddress"
              className={s.textarea}
              value={form.billingAddress}
              onChange={(e) => setField("billingAddress", e.target.value)}
              placeholder="123 Enterprise Way, Suite 400, Silicon Valley, CA 94043"
            />
            {errors.billingAddress && <p className={s.fieldError}>{errors.billingAddress}</p>}
          </div>
        </div>
      </section>

      {/* Invoice Timeline */}
      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon}>📅</div>
          <div>
            <h2 className={s.sectionTitle}>Invoice Timeline</h2>
            <p className={s.sectionSub}>Set issue date, due date, and PO reference.</p>
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
            <label className={s.label} htmlFor="poNumber">PO Number</label>
            <input
              id="poNumber"
              className={s.input}
              value={form.poNumber}
              onChange={(e) => setField("poNumber", e.target.value)}
              placeholder="PO-8829-X"
            />
          </div>

          <div className={s.formGroup}>
            <label className={s.label} htmlFor="currency">Currency</label>
            <select
              id="currency"
              className={s.select}
              value={form.currency}
              onChange={(e) => setField("currency", e.target.value)}
            >
              <option value="USD">USD — US Dollar</option>
              <option value="EUR">EUR — Euro</option>
              <option value="GBP">GBP — British Pound</option>
              <option value="EGP">EGP — Egyptian Pound</option>
              <option value="SAR">SAR — Saudi Riyal</option>
            </select>
          </div>
        </div>
      </section>
    </>
  );
}

// ── Step 2: Line Items ────────────────────────────────────────────────────────
function StepLineItems({ lineItems, addLineItem, removeLineItem, updateLineItem, errors }) {
  return (
    <section className={s.sectionCard}>
      <div className={s.lineItemsHeader}>
        <div className={s.sectionHeader} style={{ marginBottom: 0 }}>
          <div className={s.sectionIcon}>📄</div>
          <div>
            <h2 className={s.sectionTitle}>Line Items</h2>
            <p className={s.sectionSub}>Add products or services to this invoice.</p>
          </div>
        </div>
      </div>

      {errors._lineItems && (
        <p className={s.fieldError} style={{ marginBottom: 12 }}>{errors._lineItems}</p>
      )}

      <div style={{ overflowX: "auto" }}>
        <table className={s.lineItemsTable} aria-label="Line items">
          <thead>
            <tr>
              <th className={s.lineItemTh} style={{ width: "40%" }}>Description</th>
              <th className={s.lineItemTh} style={{ width: "12%" }}>Qty</th>
              <th className={s.lineItemTh} style={{ width: "18%" }}>Unit Price</th>
              <th className={s.lineItemTh} style={{ width: "18%" }}>Total</th>
              <th className={s.lineItemTh} style={{ width: "12%" }}></th>
            </tr>
          </thead>
          <tbody>
            {lineItems.map((item, idx) => {
              const rowTotal = (parseFloat(item.qty) || 0) * (parseFloat(item.unitPrice) || 0);
              return (
                <tr key={item.id} className={s.lineItemTr}>
                  <td className={s.lineItemTd}>
                    <input
                      className={s.lineItemInput}
                      value={item.description}
                      onChange={(e) => updateLineItem(item.id, "description", e.target.value)}
                      placeholder="e.g. Web Development Services"
                      aria-label={`Description for item ${idx + 1}`}
                      style={errors[`desc_${idx}`] ? { borderColor: "#c0392b" } : {}}
                    />
                    {errors[`desc_${idx}`] && <p className={s.fieldError}>{errors[`desc_${idx}`]}</p>}
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
                      onChange={(e) => updateLineItem(item.id, "unitPrice", e.target.value)}
                      aria-label={`Unit price for item ${idx + 1}`}
                    />
                  </td>
                  <td className={s.lineItemTd}>
                    <span className={s.lineItemTotal}>{formatCurrency(rowTotal)}</span>
                  </td>
                  <td className={s.lineItemTd}>
                    <button
                      className={s.btnDanger}
                      onClick={() => removeLineItem(item.id)}
                      aria-label={`Remove item ${idx + 1}`}
                      disabled={lineItems.length === 1}
                    >
                      ✕
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

// ── Step 3: Calculations ──────────────────────────────────────────────────────
function StepCalculations({ form, setField, errors }) {
  return (
    <>
      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon}>🧮</div>
          <div>
            <h2 className={s.sectionTitle}>Tax Configuration</h2>
            <p className={s.sectionSub}>System will apply client tax rules automatically.</p>
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
            <label className={`${s.label} ${s.labelRequired}`} htmlFor="customTaxRate">
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
            {errors.customTaxRate && <p className={s.fieldError}>{errors.customTaxRate}</p>}
          </div>
        )}
      </section>

      <section className={s.sectionCard}>
        <div className={s.sectionHeader}>
          <div className={s.sectionIcon}>💸</div>
          <div>
            <h2 className={s.sectionTitle}>Discount & Notes</h2>
            <p className={s.sectionSub}>Apply a flat discount and add internal notes.</p>
          </div>
        </div>

        <div className={s.formGrid}>
          <div className={s.formGroup}>
            <label className={s.label} htmlFor="discount">Discount Amount (USD)</label>
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
            <label className={s.label} htmlFor="notes">Internal Notes</label>
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

// ── Step 4: Finalize ──────────────────────────────────────────────────────────
function StepFinalize({ form, lineItems, summary, submitting, submitted, handleSubmit, reset, navigate }) {
  if (submitted) {
    return (
      <div className={s.finalCard}>
        <div className={s.finalIcon}>✅</div>
        <h2 className={s.finalTitle}>Invoice Created Successfully!</h2>
        <p className={s.finalSub}>Your invoice has been saved and is ready to send.</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <button className={`${s.btn} ${s.btnOutline}`} onClick={reset}>
            + Create Another
          </button>
          <button className={`${s.btn} ${s.btnPrimary}`} onClick={() => navigate("/finance")}>
            ← Back to Finance
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={s.finalCard}>
        <div className={s.finalIcon}>📋</div>
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
            <p className={s.finalSummaryLabel}>Line Items</p>
            <p className={s.finalSummaryValue}>{lineItems.length} item{lineItems.length !== 1 ? "s" : ""}</p>
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
          {submitting ? "⏳ Generating..." : "🚀 Generate Invoice"}
        </button>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────
export default function CreateInvoicePage() {
  const [activeNav, setActiveNav] = useState("finance");

  // In real app: useNavigate from react-router-dom
  // Fallback stub if router isn't set up yet
  let navigate;
  try {
    navigate = useNavigate();          // eslint-disable-line
  } catch {
    navigate = (path) => { window.location.href = path; };
  }

  // Stub: replace with real API call
  const handleSubmit = async (payload) => {
    console.log("Invoice Payload:", payload);
    await new Promise((r) => setTimeout(r, 1000)); // simulate API
  };

  const {
    currentStep, form, lineItems, errors, submitting, submitted, summary,
    setField, addLineItem, removeLineItem, updateLineItem,
    goNext, goBack, goToStep, handleSubmit: submit, reset,
  } = useCreateInvoice({ onSubmit: handleSubmit });

  const isLastStep = currentStep === STEPS.length - 1;

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#F8F9FA" }}>

      {/* ── Sidebar ── */}
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      {/* ── Main Area ── */}
      <div style={{ marginLeft: 220, flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>

        {/* ── Header ── */}
        <Header breadcrumbs={["Synergy ERP", "Finance", "Invoices", "Create New Record"]} />

        {/* ── Page Content ── */}
        <main className={s.page}>

          {/* Page Header */}
          <header className={s.pageHeader}>
            <div>
              <h1 className={s.pageTitle}>Create New Invoice</h1>
              <p className={s.pageSub}>
                Complete the steps below to generate a professional invoice.
                System will automatically apply client tax rules.
              </p>
            </div>
            <div className={s.headerActions}>
              <button
                className={`${s.btn} ${s.btnOutline}`}
                aria-label="Shortcuts"
              >
                ⌨ Shortcuts
              </button>
              <button
                className={`${s.btn} ${s.btnPrimary}`}
                onClick={goNext}
                aria-label="Save as draft"
              >
                💾 Save Draft
              </button>
            </div>
          </header>

          {/* Stepper */}
          <Stepper currentStep={currentStep} goToStep={goToStep} />

          {/* Form + Sidebar */}
          <div className={s.formLayout}>

            {/* ── Step Content ── */}
            <div className={s.formMain}>
              {currentStep === 0 && (
                <StepBillingInfo
                  form={form}
                  setField={setField}
                  errors={errors}
                />
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
                <StepCalculations
                  form={form}
                  setField={setField}
                  errors={errors}
                />
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

              {/* Step Footer (navigation) */}
              {!submitted && (
                <div className={s.stepFooter}>
                  <span className={s.stepCount}>Step {currentStep + 1} of {STEPS.length}</span>
                  <div className={s.footerActions}>
                    <button
                      className={s.btnGhost}
                      onClick={goBack}
                      disabled={currentStep === 0}
                      aria-label="Go back"
                    >
                      ← Back
                    </button>
                    {!isLastStep && (
                      <button
                        className={`${s.btn} ${s.btnPrimary}`}
                        onClick={goNext}
                        aria-label="Continue to next step"
                      >
                        Continue →
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* ── Live Summary Sidebar ── */}
            <div className={s.formSide}>
              <LiveSummary summary={summary} />
            </div>
          </div>

        </main>
      </div>
    </div>
  );
}