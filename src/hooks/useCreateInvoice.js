// ─── hooks/useCreateInvoice.js ────────────────────────────────────────────────
// ✅ Pure JS — no TypeScript
// ✅ 4-step wizard state machine
// ✅ Live summary calculation (subtotal / tax / discount / grand total)
// ✅ Field validation per step
// ✅ Consistent with Finance.jsx patterns (useState, useCallback)

import { useState, useCallback, useMemo } from "react";

// ── Constants ─────────────────────────────────────────────────────────────────
export const STEPS = [
  { id: "billing",      label: "Billing Info",  icon: "👤" },
  { id: "line-items",   label: "Line Items",    icon: "📄" },
  { id: "calculations", label: "Calculations",  icon: "🧮" },
  { id: "finalize",     label: "Finalize",      icon: "✅" },
];

export const TAX_OPTIONS = [
  { id: "none",    label: "No Tax",     rate: 0,    sub: "0%  — Tax exempt" },
  { id: "vat5",    label: "VAT 5%",     rate: 0.05, sub: "5%  — Reduced rate" },
  { id: "vat10",   label: "VAT 10%",    rate: 0.10, sub: "10% — Standard reduced" },
  { id: "vat15",   label: "VAT 15%",    rate: 0.15, sub: "15% — Standard rate" },
  { id: "vat20",   label: "VAT 20%",    rate: 0.20, sub: "20% — Full rate" },
  { id: "custom",  label: "Custom",     rate: null, sub: "Enter custom %" },
];

const EMPTY_LINE = () => ({
  id:          Date.now() + Math.random(),
  description: "",
  qty:         1,
  unitPrice:   0,
});

const INITIAL_FORM = {
  // Billing Info
  customerName:   "",
  billingEmail:   "",
  billingAddress: "",
  // Invoice Timeline
  issueDate:      new Date().toISOString().slice(0, 10),
  dueDate:        "",
  poNumber:       "",
  // Calculations
  taxOption:      "vat15",
  customTaxRate:  "",
  discount:       "",
  currency:       "USD",
  notes:          "",
};

// ── Validators ────────────────────────────────────────────────────────────────
function validateStep(step, form, lineItems) {
  const errs = {};

  if (step === 0) {
    if (!form.customerName.trim())   errs.customerName   = "Customer name is required";
    if (!form.billingEmail.trim())   errs.billingEmail   = "Billing email is required";
    else if (!/\S+@\S+\.\S+/.test(form.billingEmail)) errs.billingEmail = "Invalid email address";
    if (!form.billingAddress.trim()) errs.billingAddress = "Billing address is required";
    if (!form.issueDate)             errs.issueDate      = "Issue date is required";
    if (!form.dueDate)               errs.dueDate        = "Due date is required";
  }

  if (step === 1) {
    if (lineItems.length === 0) {
      errs._lineItems = "Add at least one line item";
    } else {
      lineItems.forEach((item, i) => {
        if (!item.description.trim()) errs[`desc_${i}`]  = "Description required";
        if (!item.qty || item.qty <= 0) errs[`qty_${i}`] = "Qty > 0";
        if (item.unitPrice < 0)         errs[`price_${i}`] = "Price ≥ 0";
      });
    }
  }

  if (step === 2) {
    if (form.taxOption === "custom") {
      const r = parseFloat(form.customTaxRate);
      if (isNaN(r) || r < 0 || r > 100) errs.customTaxRate = "Enter a valid % (0–100)";
    }
    if (form.discount !== "") {
      const d = parseFloat(form.discount);
      if (isNaN(d) || d < 0) errs.discount = "Discount must be ≥ 0";
    }
  }

  return errs;
}

// ── Hook ──────────────────────────────────────────────────────────────────────
export default function useCreateInvoice({ onSubmit } = {}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [form,        setForm]        = useState(INITIAL_FORM);
  const [lineItems,   setLineItems]   = useState([EMPTY_LINE()]);
  const [errors,      setErrors]      = useState({});
  const [submitting,  setSubmitting]  = useState(false);
  const [submitted,   setSubmitted]   = useState(false);

  // ── Field helpers ────────────────────────────────────────────────────────
  const setField = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => { const next = { ...prev }; delete next[field]; return next; });
  }, []);

  // ── Line Items ───────────────────────────────────────────────────────────
  const addLineItem = useCallback(() => {
    setLineItems((prev) => [...prev, EMPTY_LINE()]);
  }, []);

  const removeLineItem = useCallback((id) => {
    setLineItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const updateLineItem = useCallback((id, field, value) => {
    setLineItems((prev) =>
      prev.map((item) => item.id === id ? { ...item, [field]: value } : item)
    );
    setErrors((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((k) => { if (k.startsWith("desc_") || k.startsWith("qty_") || k.startsWith("price_")) delete next[k]; });
      return next;
    });
  }, []);

  // ── Live Summary ─────────────────────────────────────────────────────────
  const summary = useMemo(() => {
    const subtotal = lineItems.reduce(
      (sum, item) => sum + (parseFloat(item.qty) || 0) * (parseFloat(item.unitPrice) || 0),
      0
    );

    const taxOption = TAX_OPTIONS.find((o) => o.id === form.taxOption);
    const taxRate   = form.taxOption === "custom"
      ? (parseFloat(form.customTaxRate) || 0) / 100
      : (taxOption?.rate ?? 0);

    const taxAmount     = subtotal * taxRate;
    const discountAmt   = parseFloat(form.discount) || 0;
    const grandTotal    = Math.max(0, subtotal + taxAmount - discountAmt);

    return {
      subtotal,
      taxRate: taxRate * 100,
      taxAmount,
      discountAmt,
      grandTotal,
    };
  }, [lineItems, form.taxOption, form.customTaxRate, form.discount]);

  // ── Navigation ───────────────────────────────────────────────────────────
  const goNext = useCallback(() => {
    const errs = validateStep(currentStep, form, lineItems);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return false;
    }
    setErrors({});
    setCurrentStep((s) => Math.min(s + 1, STEPS.length - 1));
    return true;
  }, [currentStep, form, lineItems]);

  const goBack = useCallback(() => {
    setErrors({});
    setCurrentStep((s) => Math.max(s - 1, 0));
  }, []);

  const goToStep = useCallback((idx) => {
    if (idx < currentStep) {
      setErrors({});
      setCurrentStep(idx);
    }
  }, [currentStep]);

  // ── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    const payload = { form, lineItems, summary };
    try {
      if (onSubmit) await onSubmit(payload);
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }, [form, lineItems, summary, onSubmit]);

  const reset = useCallback(() => {
    setCurrentStep(0);
    setForm(INITIAL_FORM);
    setLineItems([EMPTY_LINE()]);
    setErrors({});
    setSubmitted(false);
    setSubmitting(false);
  }, []);

  return {
    // State
    currentStep,
    form,
    lineItems,
    errors,
    submitting,
    submitted,
    summary,
    // Actions
    setField,
    addLineItem,
    removeLineItem,
    updateLineItem,
    goNext,
    goBack,
    goToStep,
    handleSubmit,
    reset,
  };
}