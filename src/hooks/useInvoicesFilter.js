// ─── hooks/useInvoicesFilter.js ────────────────────────────────────────────────
import { useState, useMemo, useCallback } from "react";

export const PAGE_SIZE = 10;

export const INVOICE_STATUSES = ["All", "Paid", "Pending", "Overdue"];

export default function useInvoicesFilter(invoices = []) {
  const [activeFilter,  setActiveFilter]  = useState("All");
  const [searchQuery,   setSearchQuery]   = useState("");
  const [currentPage,   setCurrentPage]   = useState(1);

  const filtered = useMemo(() => {
    return invoices.filter((inv) => {
      const matchStatus =
        activeFilter === "All" || inv.status === activeFilter;
      const q = searchQuery.toLowerCase();
      const matchSearch =
        !q ||
        inv.customer?.toLowerCase().includes(q) ||
        inv.id?.toString().toLowerCase().includes(q);
      return matchStatus && matchSearch;
    });
  }, [invoices, activeFilter, searchQuery]);

  const totalFiltered = filtered.length;
  const totalPages    = Math.max(1, Math.ceil(totalFiltered / PAGE_SIZE));

  const paginatedInvoices = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  // Reset to page 1 when filter/search changes
  const handleSetActiveFilter = useCallback((f) => {
    setActiveFilter(f);
    setCurrentPage(1);
  }, []);

  const handleSetSearchQuery = useCallback((q) => {
    setSearchQuery(q);
    setCurrentPage(1);
  }, []);

  const handleSetCurrentPage = useCallback((p) => {
    setCurrentPage((prev) => {
      const next = typeof p === "function" ? p(prev) : p;
      return Math.max(1, Math.min(next, totalPages));
    });
  }, [totalPages]);

  return {
    activeFilter,
    searchQuery,
    currentPage,
    totalPages,
    totalFiltered,
    paginatedInvoices,
    setActiveFilter:  handleSetActiveFilter,
    setSearchQuery:   handleSetSearchQuery,
    setCurrentPage:   handleSetCurrentPage,
  };
}