// ─── utils/formatters.js ──────────────────────────────────────────────────────
// Business formatting helpers — testable, reusable, single source of truth

export const formatCurrency = (amount, locale = "en-US", currency = "EGP") =>
  new Intl.NumberFormat(locale, { style: "currency", currency }).format(amount);

export const formatDate = (dateStr, locale = "en-US") =>
  new Date(dateStr).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

export const normalizeError = (err) => {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  return "An unexpected error occurred";
};