// Pages/InventoryPage.jsx
// Pure JS - no TypeScript
// Export Report modal - CSV/JSON download (Products, KPIs, Alerts, Warehouses)
// Add New Product modal - full form validation + optimistic add to table
// Stat cards, Product table with animated stock bars
// Critical Alerts, Warehouse Map, Live Feed sidebars
// Shimmer skeleton loading, filter tabs, pagination
// Same Sidebar + Header structure as all other pages

import { useState, useEffect, useCallback, useRef, memo, useMemo } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeftRight,
  ArrowRight,
  ArrowUp,
  Boxes,
  ChartNoAxesCombined,
  CheckCircle2,
  CircleDollarSign,
  Download,
  Eye,
  FileText,
  FolderOpen,
  Package,
  PackagePlus,
  Pencil,
  Plus,
  RadioTower,
  Search,
  Trash2,
  Upload,
  Warehouse,
  X,
} from "lucide-react";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import "../assets/fonts/NotoSansArabic-Regular-normal";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import s from "../styles/InventoryPage.module.css";
import shell from "../styles/AppShell.module.css";
import { formatCurrency } from "../utils/formatters";
import {
  getInventoryProducts,
  getInventoryStats,
  createInventoryProduct,
  updateInventoryProduct,
  deleteInventoryProduct,
  importInventoryProductsCsv,
} from "../services/inventoryApi";

// ─────────────────────────────────────────────────────────────────────────────
// ── MOCK DATA
// ─────────────────────────────────────────────────────────────────────────────
const INITIAL_STATS = [
  { id:"assets",   label:"Total Assets",   value:"EGP 2,845,000", change:"+12.8%", changeType:"up",   sub:"Current market value of all stocked items across all warehouses." },
  { id:"turnover", label:"Stock Turnover", value:"4.2x",       change:"+0.8%",  changeType:"up",   sub:"Inventory turnover ratio for the current fiscal quarter." },
  { id:"util",     label:"Utilization",    value:"78.4%",      change:"-2.1%",  changeType:"down", sub:"Average warehouse capacity utilized nationwide." },
  { id:"lowstock", label:"Low Stock",      value:"14 Items",   change:"+3",     changeType:"down", sub:"Products that have fallen below the critical threshold." },
];

const STAT_ICONS = {
  products: Package,
  units: Boxes,
  totalSum: CircleDollarSign,
  lowstock: AlertTriangle,
};


const CRITICAL_ALERTS = [
  { id:"a1", name:"Nebula Glass Screen", sku:"SKU: SYN-N550", unitsLeft:12, threshold:50,  color:"#FA5252" },
  { id:"a2", name:"Fusion Cell Unit",    sku:"SKU: SYN-FC01", unitsLeft:8,  threshold:20,  color:"#FA5252" },
  { id:"a3", name:"Liquid Coolant X-9",  sku:"SKU: SYN-LC99", unitsLeft:0,  threshold:10,  color:"#C92A2A" },
];

const WAREHOUSES = [
  { id:"w1", name:"North Logistics Hub", tag:"Optimized", capacity:92, items:12450, delta:"+120 today", color:"#3B5BDB" },
  { id:"w2", name:"South Coast Depot",   tag:"Near Full", capacity:87, items:9830,  delta:"+45 today",  color:"#F59F00" },
];

const LIVE_FEED = [
  { id:"f1", product:"Quantum Processor X1",  action:"Received",    qty:"+ 500 units",   location:"WH-A-12",     ago:"12m ago", direction:"in",       iconColor:"#2F9E44" },
  { id:"f2", product:"Titanium Chassis V2",   action:"Dispatched",  qty:"- 120 units",   location:"HUB-CENTRAL", ago:"45m ago", direction:"out",      iconColor:"#FA5252" },
  { id:"f3", product:"Optic Fiber Bundle",    action:"Transferred", qty:"→ 2000m",        location:"A-10 → B-04", ago:"2h ago",  direction:"transfer", iconColor:"#3B5BDB" },
  { id:"f4", product:"Neural Interface Chip", action:"Received",    qty:"+ 10,000 units", location:"SECURE-91",   ago:"4h ago",  direction:"in",       iconColor:"#2F9E44" },
];

const FEED_ICONS = {
  in: ArrowDown,
  out: ArrowUp,
  transfer: ArrowRight,
};

const CATEGORIES     = ["Electronics","Consumables","Hardware","Software","Components"];
const LOCATIONS      = ["Warehouse A-12","Warehouse A-10","Warehouse B-04","Central Hub","Secure Vault"];
const STATUS_OPTIONS = ["Healthy","Warning","Critical","Low","Out"];
const PAGE_SIZE      = 8;

// ─────────────────────────────────────────────────────────────────────────────
// ── HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function useAnimateIn(delay = 0) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return { ref, style: { opacity: visible?1:0, transform: visible?"translateY(0)":"translateY(16px)", transition:`opacity 0.45s ease ${delay}ms,transform 0.45s ease ${delay}ms` } };
}

const Skeleton = ({ w="100%", h=14, style={} }) => (
  <div style={{ width:w, height:h, borderRadius:6, background:"linear-gradient(90deg,#F0F0F0 25%,#E0E0E0 50%,#F0F0F0 75%)", backgroundSize:"200% 100%", animation:"shimmer 1.4s infinite", ...style }} />
);

function getStatusMeta(status) {
  const map = { Healthy:{color:"#2F9E44",bg:"#EBFBEE",barColor:"#2F9E44"}, Warning:{color:"#E67700",bg:"#FFF3BF",barColor:"#F59F00"}, Critical:{color:"#C92A2A",bg:"#FFE3E3",barColor:"#FA5252"}, Low:{color:"#C92A2A",bg:"#FFF5F5",barColor:"#FA5252"}, Out:{color:"#868E96",bg:"#F1F3F5",barColor:"#CED4DA"} };
  return map[status] ?? { color:"#868E96", bg:"#F1F3F5", barColor:"#E9ECEF" };
}

function today() { return new Date().toISOString().slice(0,10); }

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement("a"), { href:url, download:filename });
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
}

function toCSV(rows) {
  if (!rows?.length) return "";
  const headers = Object.keys(rows[0]);
  return [headers.join(","), ...rows.map(r => headers.map(h => { const v=String(r[h]??""); return v.includes(",")||v.includes('"')?`"${v.replace(/"/g,'""')}"`:v; }).join(","))].join("\n");
}

function containsArabic(value) {
  return /[\u0600-\u06FF]/.test(String(value ?? ""));
}

function prepareArabicText(value) {
  const text = String(value ?? "");

  if (containsArabic(text) && typeof jsPDF.API.processArabic === "function") {
    return jsPDF.API.processArabic(text);
  }

  return text;
}

function parseCSVLine(line) {
  const result = [];
  let current = "";
  let insideQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (char === '"' && insideQuotes && nextChar === '"') {
      current += '"';
      i++;
    } else if (char === '"') {
      insideQuotes = !insideQuotes;
    } else if (char === "," && !insideQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  if (insideQuotes) {
    throw new Error("CSV contains an unterminated quoted value.");
  }

  result.push(current.trim());
  return result;
}

function parseRequiredCsvNumber(value, rowNumber, label) {
  if (value === "" || value == null) {
    throw new Error(`Row ${rowNumber}: ${label} must be a valid number.`);
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue) || numberValue < 0) {
    throw new Error(`Row ${rowNumber}: ${label} must be a valid number.`);
  }

  return numberValue;
}

function parseProductsCsv(csvText) {
  const lines = csvText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) {
    throw new Error("CSV file must contain a header row and at least one product row.");
  }

  const headers = parseCSVLine(lines[0]).map((header) =>
    header.replace(/^\uFEFF/, "").trim().toLowerCase()
  );

  const requiredHeaders = [
    "name",
    "category",
    "sku",
    "location",
    "price",
    "units",
    "threshold",
  ];

  const missingHeaders = requiredHeaders.filter(
    (header) => !headers.includes(header)
  );

  if (missingHeaders.length > 0) {
    throw new Error(`Missing required CSV headers: ${missingHeaders.join(", ")}`);
  }

  const seenSkus = new Set();

  return lines.slice(1).map((line, index) => {
    const rowNumber = index + 2;
    const values = parseCSVLine(line);
    const row = {};

    headers.forEach((header, headerIndex) => {
      row[header] = values[headerIndex]?.trim() ?? "";
    });

    const sku = row.sku.toUpperCase();

    if (!row.name) throw new Error(`Row ${rowNumber}: Product name is required.`);
    if (!row.category) throw new Error(`Row ${rowNumber}: Category is required.`);
    if (!row.sku) throw new Error(`Row ${rowNumber}: SKU is required.`);
    if (!row.location) throw new Error(`Row ${rowNumber}: Location is required.`);
    if (!CATEGORIES.includes(row.category)) {
      throw new Error(`Row ${rowNumber}: Category must be one of ${CATEGORIES.join(", ")}.`);
    }
    if (!LOCATIONS.includes(row.location)) {
      throw new Error(`Row ${rowNumber}: Location must be one of ${LOCATIONS.join(", ")}.`);
    }

    const price = parseRequiredCsvNumber(row.price, rowNumber, "Price");
    const units = parseRequiredCsvNumber(row.units, rowNumber, "Units");
    const threshold = parseRequiredCsvNumber(row.threshold, rowNumber, "Threshold");

    if (seenSkus.has(sku)) {
      throw new Error(`Row ${rowNumber}: Duplicate SKU "${sku}" in CSV file.`);
    }

    seenSkus.add(sku);

    return {
      name: row.name,
      category: row.category,
      sku,
      location: row.location,
      price,
      units,
      threshold,
    };
  });
}

function generatePDFReport({ title, subtitle, rows, filename }) {
  const doc = new jsPDF({
    orientation: "landscape",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();

  const primary = [59, 91, 219];
  const dark = [15, 23, 42];
  const muted = [100, 116, 139];
  const lightBg = [248, 250, 252];

  const generatedAt = new Date().toLocaleString();

  // Header background
  doc.setFillColor(...primary);
  doc.roundedRect(36, 30, pageWidth - 72, 86, 14, 14, "F");

  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.text(title, 58, 66);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(subtitle || "Inventory management report", 58, 88);

  doc.setFontSize(9);
  doc.text(`Generated: ${generatedAt}`, pageWidth - 58, 88, {
    align: "right",
  });

  // Summary cards
  const totalRecords = rows.length;
  const cardY = 136;
  const cardW = 170;
  const cardH = 54;

  const cards = [
    { label: "Report Type", value: title },
    { label: "Records", value: String(totalRecords) },
    { label: "Generated By", value: "Prime ERP" },
  ];

  cards.forEach((card, index) => {
    const x = 36 + index * (cardW + 14);

    doc.setFillColor(...lightBg);
    doc.roundedRect(x, cardY, cardW, cardH, 12, 12, "F");

    doc.setTextColor(...muted);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    doc.text(card.label.toUpperCase(), x + 14, cardY + 20);

    doc.setTextColor(...dark);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text(String(card.value).slice(0, 28), x + 14, cardY + 39);
  });

  if (!rows || rows.length === 0) {
    doc.setTextColor(...muted);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(13);
    doc.text("No data available for this report.", 36, 230);
    doc.save(`${filename}.pdf`);
    return;
  }

  const headers = Object.keys(rows[0]);
  const body = rows.map((row) =>
    headers.map((header) => String(row[header] ?? ""))
  );

  autoTable(doc, {
    startY: 216,
    head: [headers],
    body,
    theme: "grid",
    styles: {
      font: "helvetica",
      fontSize: 8.5,
      cellPadding: 8,
      overflow: "linebreak",
      valign: "middle",
      lineColor: [226, 232, 240],
      lineWidth: 0.5,
    },
    headStyles: {
      fillColor: primary,
      textColor: [255, 255, 255],
      fontStyle: "bold",
      halign: "left",
    },
    alternateRowStyles: {
      fillColor: [248, 250, 252],
    },
    bodyStyles: {
      textColor: dark,
    },
    margin: {
      left: 36,
      right: 36,
    },
    didParseCell: function (data) {
      const rawValue = data.cell.raw;
      const textValue = Array.isArray(rawValue)
        ? rawValue.join(" ")
        : String(rawValue ?? "");

      if (containsArabic(textValue)) {
        data.cell.styles.font = "NotoSansArabic";
        data.cell.styles.fontStyle = "normal";
        data.cell.styles.halign = "right";
        data.cell.text = [prepareArabicText(textValue)];
      } else {
        data.cell.styles.font = "helvetica";
        data.cell.styles.halign = "left";
      }
    },
    didDrawPage: function () {
      const currentPage = doc.internal.getNumberOfPages();

      doc.setTextColor(...muted);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);

      doc.text("Prime ERP - Inventory Report", 36, pageHeight - 24);
      doc.text(`Page ${currentPage}`, pageWidth - 36, pageHeight - 24, {
        align: "right",
      });
    },
  });

  doc.save(`${filename}.pdf`);
}

function formatTimeAgo(dateValue) {
  if (!dateValue) return "Just now";
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return "Just now";
  const now = new Date();
  const diffMs = now - date;
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

// ─────────────────────────────────────────────────────────────────────────────
// ── EXPORT REPORT MODAL
// ─────────────────────────────────────────────────────────────────────────────
function ExportReportModal({ isOpen, onClose, products, stats, criticalAlerts, warehouseSummary }) {
  const [format,   setFormat]   = useState("csv");
  const [statuses, setStatuses] = useState({});
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const fn = e => { if (e.key==="Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [isOpen, onClose]);

  useEffect(() => { if (isOpen) setStatuses({}); }, [isOpen]);

  const exportItems = useMemo(() => [
    {
      id:"products", icon:Package, label:"Products List",
      desc:"All inventory items with SKU, location, stock & status",
      filename:`Prime-inventory-products-${today()}`,
      rows:() => products.map(p => ({ "Product Name": p.name || "-", Category: p.category || "-", SKU: p.sku || "-", Location: p.location || "-", Price: `EGP ${Number(p.price || 0).toLocaleString()}`, "Stock %": `${p.stockPct ?? 0}%`, Units: p.units ?? 0, Threshold: p.threshold ?? 0, Status: p.status || "-" })),
    },
    {
      id:"kpis", icon:ChartNoAxesCombined, label:"Inventory KPIs",
      desc:"Total assets, turnover ratio, utilization & low stock count",
      filename:`Prime-inventory-kpis-${today()}`,
      rows:() => [
        { Metric: "Total Products", Value: stats?.totalProducts ?? products.length, Description: "Total number of products stored in inventory." },
        { Metric: "Total Units", Value: stats?.totalUnits ?? products.reduce((sum, item) => sum + Number(item.units || 0), 0), Description: "Total stock units available across all products." },
        { Metric: "Average Stock", Value: `${stats?.averageStock ?? 0}%`, Description: "Average stock percentage across inventory items." },
        { Metric: "Low Stock", Value: `${stats?.lowStockItems ?? criticalAlerts.length} Items`, Description: "Products that are below threshold or out of stock." },
      ],
    },
    {
      id:"alerts", icon:AlertTriangle, label:"Critical Alerts",
      desc:"Products below minimum threshold requiring replenishment",
      filename:`Prime-inventory-alerts-${today()}`,
      rows:() => criticalAlerts.map(p => ({ "Product Name": p.name || "-", SKU: p.sku || "-", "Units Left": p.units ?? 0, Threshold: p.threshold ?? 0, Status: p.status || "-", Location: p.location || "-" })),
    },
    {
      id:"warehouses", icon:Warehouse, label:"Warehouse Report",
      desc:"Capacity, item count and status per warehouse",
      filename:`Prime-inventory-warehouses-${today()}`,
      rows:() => warehouseSummary.map(w => ({ Warehouse: w.name || "-", Tag: w.tag || "-", "Capacity %": `${w.capacity ?? 0}%`, "Total Items": w.items ?? 0, Products: w.productsCount ?? 0, "Low Stock": w.lowStockCount ?? 0 })),
    },
  ], [products, stats, criticalAlerts, warehouseSummary]);

  const handleExport = useCallback(async item => {
    setStatuses(p => ({ ...p, [item.id]:"loading" }));
    await new Promise(r => setTimeout(r, 400));
    try {
      const rows = item.rows();
      if (format === "csv") {
        downloadFile(toCSV(rows), `${item.filename}.csv`, "text/csv;charset=utf-8;");
      } else if (format === "json") {
        downloadFile(JSON.stringify(rows, null, 2), `${item.filename}.json`, "application/json");
      } else if (format === "pdf") {
        generatePDFReport({
          title: item.label,
          subtitle: item.desc,
          rows,
          filename: item.filename,
        });
      }
      setStatuses(p => ({ ...p, [item.id]:"done" }));
    } catch {
      setStatuses(p => ({ ...p, [item.id]:"error" }));
    }
  }, [format]);

  const handleExportAll = useCallback(async () => {
    for (const item of exportItems) {
      if (statuses[item.id]==="done") continue;
      await handleExport(item);
      await new Promise(r => setTimeout(r, 180));
    }
  }, [exportItems, statuses, handleExport]);

  const allDone = exportItems.every(item => statuses[item.id]==="done");

  if (!isOpen) return null;

  return (
    <div className={s.modalOverlay} ref={overlayRef} onClick={e=>{ if(e.target===overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal}>
        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon} aria-hidden="true">
              <Download className={s.modalTitleIconSvg} />
            </div>
            <div>
              <h2 className={s.modalTitle}>Export Inventory Report</h2>
              <p className={s.modalSub}>Download inventory data for external use or archiving.</p>
            </div>
          </div>
          <button className={s.modalClose} onClick={onClose} aria-label="Close export report modal" title="Close">
            <X aria-hidden="true" />
          </button>
        </div>

        {/* Format Toggle */}
        <div className={s.formatRow}>
          <span className={s.formatLabel}>Export Format</span>
          <div className={s.formatToggle}>
            {["csv","json","pdf"].map(f => (
              <button key={f} className={`${s.formatBtn} ${format===f?s.formatBtnActive:""}`} onClick={()=>{ setFormat(f); setStatuses({}); }}>
                {f==="csv" ? <><FileText className={s.inlineIcon} aria-hidden="true" />CSV</> : f==="json" ? "{ } JSON" : <><FileText className={s.inlineIcon} aria-hidden="true" />PDF</>}
              </button>
            ))}
          </div>
        </div>

        {/* Items */}
        <div className={s.exportList}>
          {exportItems.map(item => {
            const st = statuses[item.id];
            const Icon = item.icon;
            return (
              <div key={item.id} className={`${s.exportCard} ${st==="done"?s.exportCardDone:""}`}>
                <div className={s.exportCardLeft}>
                  <span className={s.exportCardIcon} aria-hidden="true">
                    <Icon className={s.exportCardIconSvg} />
                  </span>
                  <div>
                    <p className={s.exportCardLabel}>{item.label}</p>
                    <p className={s.exportCardDesc}>{item.desc}</p>
                  </div>
                </div>
                <button className={`${s.exportBtn} ${st==="done"?s.exportBtnDone:""}`} onClick={()=>handleExport(item)} disabled={st==="loading"}>
                  {st==="loading" ? <span className={s.exportSpinner}/> : st==="done" ? <><CheckCircle2 className={s.inlineIcon} aria-hidden="true" />Downloaded</> : <><Download className={s.inlineIcon} aria-hidden="true" />{format.toUpperCase()}</>}
                </button>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className={s.modalFooter}>
          <p className={s.modalFooterNote}>
            <FolderOpen className={s.inlineIcon} aria-hidden="true" />
            Files saved to your default Downloads folder.
          </p>
          <div className={s.modalFooterActions}>
            <button className={s.btnGhost} onClick={onClose}>Cancel</button>
            <button className={`${s.btn} ${s.btnPrimary} ${allDone?s.btnSuccess:""}`} onClick={handleExportAll} disabled={allDone}>
              {allDone ? <><CheckCircle2 className={s.btnIcon} aria-hidden="true" />All Downloaded</> : <><Download className={s.btnIcon} aria-hidden="true" />Export All as {format.toUpperCase()}</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── ADD NEW PRODUCT MODAL
// ─────────────────────────────────────────────────────────────────────────────
const EMPTY_FORM = { name:"", category:"Electronics", sku:"", location:"Warehouse A-12", price:"", units:"", threshold:"" };

function AddProductModal({ isOpen, onClose, onAdd, onUpdate, product = null, submitting = false }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const overlayRef = useRef(null);
  const mode = product ? "edit" : "add";

  useEffect(() => {
    if (!isOpen) return;
    const fn = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) return;
    setErrors({});
    setForm(
      product
        ? {
            name: product.name ?? "",
            category: product.category ?? "Electronics",
            sku: product.sku ?? "",
            location: product.location ?? "Warehouse A-12",
            price: product.price != null ? String(product.price) : "",
            units: product.units != null ? String(product.units) : "",
            threshold: product.threshold != null ? String(product.threshold) : "",
          }
        : EMPTY_FORM
    );
  }, [isOpen, product]);

  const setField = (field, value) => {
    setForm((p) => ({ ...p, [field]: value }));
    setErrors((p) => {
      const next = { ...p };
      delete next[field];
      return next;
    });
  };

  const validate = () => {
    const e = {};
    const isValidNumber = (value) =>
      value !== "" && !Number.isNaN(Number(value)) && Number(value) >= 0;

    if (!form.name.trim()) e.name = "Product name is required";
    if (!form.sku.trim()) e.sku = "SKU is required";
    if (!isValidNumber(form.price)) e.price = "Valid price required";
    if (!isValidNumber(form.units)) e.units = "Valid unit count required";
    if (!isValidNumber(form.threshold)) e.threshold = "Valid threshold required";
    return e;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    const payload = {
      name: form.name.trim(),
      category: form.category,
      sku: form.sku.trim().toUpperCase(),
      location: form.location,
      price: Number(form.price),
      units: Number(form.units),
      threshold: Number(form.threshold),
    };

    if (mode === "edit") {
      await onUpdate(product._id || product.id, payload);
      return;
    }

    await onAdd(payload);
  };

  if (!isOpen) return null;

  const Field = ({ id, label, required, error, children }) => (
    <div className={s.formGroup}>
      <label className={s.formLabel} htmlFor={id}>
        {label}
        {required && <span className={s.required}> *</span>}
      </label>
      {children}
      {error && <p className={s.fieldError}>{error}</p>}
    </div>
  );

  return (
    <div className={s.modalOverlay} ref={overlayRef} onClick={(e) => { if (e.target === overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal}>
        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon} aria-hidden="true">
              <PackagePlus className={s.modalTitleIconSvg} />
            </div>
            <div>
              <h2 className={s.modalTitle}>{mode === "edit" ? "Edit Product" : "Add New Product"}</h2>
              <p className={s.modalSub}>
                {mode === "edit"
                  ? "Update product details and send them to inventory."
                  : "Fill in the details to add a product to inventory."}
              </p>
            </div>
          </div>
          <button className={s.modalClose} onClick={onClose} aria-label="Close add product modal" title="Close">
            <X aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className={s.modalBody}>
          <div className={s.addProductGrid}>

            {/* Product Name — full width */}
            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel} htmlFor="ap-name">
                Product Name <span className={s.required}>*</span>
              </label>
              <input
                id="ap-name"
                className={`${s.formInput} ${errors.name ? s.formInputError : ""}`}
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="e.g. Quantum Processor X2"
                autoFocus
              />
              {errors.name && <p className={s.fieldError}>{errors.name}</p>}
            </div>

            {/* SKU */}
            <Field id="ap-sku" label="SKU" required error={errors.sku}>
              <input
                id="ap-sku"
                type="text"
                className={`${s.formInput} ${errors.sku ? s.formInputError : ""}`}
                value={form.sku}
                onChange={(e) => setField("sku", e.target.value)}
                placeholder="e.g. SYN-Q200"
              />
            </Field>

            {/* Category */}
            <Field id="ap-cat" label="Category">
              <select
                id="ap-cat"
                className={s.formSelect}
                value={form.category}
                onChange={(e) => setField("category", e.target.value)}
              >
                {CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>

            {/* Location */}
            <Field id="ap-loc" label="Location">
              <select
                id="ap-loc"
                className={s.formSelect}
                value={form.location}
                onChange={(e) => setField("location", e.target.value)}
              >
                {LOCATIONS.map((l) => (
                  <option key={l}>{l}</option>
                ))}
              </select>
            </Field>

            {/* Price */}
            <Field id="ap-price" label="Price" required error={errors.price}>
              <input
                id="ap-price"
                type="text"
                inputMode="decimal"
                pattern="^\d*(\.\d{0,2})?$"
                className={`${s.formInput} ${errors.price ? s.formInputError : ""}`}
                value={form.price}
                onChange={(e) => setField("price", e.target.value)}
                placeholder="e.g. 1250.00"
              />
            </Field>

            {/* Units */}
            <Field id="ap-units" label="Unit Count" required error={errors.units}>
              <input
                id="ap-units"
                type="text"
                inputMode="numeric"
                className={`${s.formInput} ${errors.units ? s.formInputError : ""}`}
                value={form.units}
                onChange={(e) => setField("units", e.target.value)}
                placeholder="e.g. 500"
              />
            </Field>

            {/* Threshold */}
            <Field id="ap-thr" label="Low Stock Threshold" required error={errors.threshold}>
              <input
                id="ap-thr"
                type="text"
                inputMode="numeric"
                className={`${s.formInput} ${errors.threshold ? s.formInputError : ""}`}
                value={form.threshold}
                onChange={(e) => setField("threshold", e.target.value)}
                placeholder="e.g. 50"
              />
            </Field>

          </div>
        </div>

        {/* Footer */}
        <div className={s.modalFooter}>
          <p className={s.modalFooterNote}>
            <FileText className={s.inlineIcon} aria-hidden="true" />
            Product will appear in the inventory table immediately.
          </p>
          <div className={s.modalFooterActions}>
            <button className={s.btnGhost} onClick={onClose}>Cancel</button>
            <button className={`${s.btn} ${s.btnPrimary}`} onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <><span className={s.exportSpinner} /> {mode === "edit" ? "Saving..." : "Adding..."}</>
              ) : (
                <><CheckCircle2 className={s.btnIcon} aria-hidden="true" />{mode === "edit" ? "Save Changes" : "Add Product"}</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ViewProductModal({ isOpen, product, onClose }) {
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const fn = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [isOpen, onClose]);

  if (!isOpen || !product) return null;

  const createdAt = product.createdAt ? new Date(product.createdAt).toLocaleString() : null;
  const updatedAt = product.updatedAt ? new Date(product.updatedAt).toLocaleString() : null;

  return (
    <div className={s.modalOverlay} ref={overlayRef} onClick={(e) => { if (e.target === overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal} style={{ maxWidth: "560px" }}>
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon} aria-hidden="true">
              <Eye className={s.modalTitleIconSvg} />
            </div>
            <div>
              <h2 className={s.modalTitle}>Product Details</h2>
              <p className={s.modalSub}>Review inventory item details and stock health.</p>
            </div>
          </div>
          <button className={s.modalClose} onClick={onClose} aria-label="Close view product modal" title="Close">
            <X aria-hidden="true" />
          </button>
        </div>

        <div className={s.modalBody}>
          <div className={s.modalDetailGrid}>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Product Name</p>
              <p className={s.modalDetailValue}>{product.name}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>SKU</p>
              <p className={s.modalDetailValue}>{product.sku}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Category</p>
              <p className={s.modalDetailValue}>{product.category}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Location</p>
              <p className={s.modalDetailValue}>{product.location}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Price</p>
              <p className={s.modalDetailValue}>{formatCurrency(product.price || 0)}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Units</p>
              <p className={s.modalDetailValue}>{product.units}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Threshold</p>
              <p className={s.modalDetailValue}>{product.threshold}</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Stock Percentage</p>
              <p className={s.modalDetailValue}>{product.stockPct}%</p>
            </div>
            <div className={s.modalDetailItem}>
              <p className={s.modalDetailLabel}>Status</p>
              <p className={s.modalDetailValue}>{product.status}</p>
            </div>
            {createdAt && (
              <div className={s.modalDetailItem}>
                <p className={s.modalDetailLabel}>Created</p>
                <p className={s.modalDetailValue}>{createdAt}</p>
              </div>
            )}
            {updatedAt && (
              <div className={s.modalDetailItem}>
                <p className={s.modalDetailLabel}>Updated</p>
                <p className={s.modalDetailValue}>{updatedAt}</p>
              </div>
            )}
          </div>
        </div>

        <div className={s.modalFooter}>
          <div className={s.modalFooterActions}>
            <button className={s.btnGhost} onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── STAT CARD
// ─────────────────────────────────────────────────────────────────────────────
const StatCard = memo(({ stat, loading, delay=0 }) => {
  const anim = useAnimateIn(delay);
  const changeColor = stat?.changeType==="up" ? "#2F9E44" : "#C92A2A";
  const changeBg    = stat?.changeType==="up" ? "#EBFBEE" : "#FFF5F5";
  const Icon = stat ? (STAT_ICONS[stat.id] || Package) : Package;
  if (loading) return (
    <div className={s.statCard} style={anim.style}>
      <Skeleton w={40} h={40} style={{ borderRadius:10, marginBottom:10 }} />
      <Skeleton w="55%" h={12} style={{ marginBottom:6 }} />
      <Skeleton w="75%" h={24} style={{ marginBottom:6 }} />
      <Skeleton w="40%" h={12} />
    </div>
  );
  return (
    <div ref={anim.ref} className={s.statCard} style={anim.style}>
      <div className={`${s.statIconBadge} ${stat.id==="products"?s.statIconBadgeActive:s.statIconBadgeNeutral}`} aria-hidden="true">
        <Icon className={s.statIconSvg} strokeWidth={2.2} />
      </div>
      <p className={s.statLabel}>{stat.label}</p>
      <p className={s.statValue}>{stat.value}</p>
      <span className={s.changeBadge} style={{ background:changeBg, color:changeColor }}>
        {stat.changeType==="up"?"▲":"▼"} {stat.change}
      </span>
      <p className={s.statSub}>{stat.sub}</p>
    </div>
  );
});
StatCard.displayName = "StatCard";

// ─────────────────────────────────────────────────────────────────────────────
// ── PRODUCT ROW
// ─────────────────────────────────────────────────────────────────────────────
function ProductRow({ product, delay = 0, onSelect = () => {} }) {
  const [drawn, setDrawn] = useState(false);
  const anim = useAnimateIn(delay);
  const sm = getStatusMeta(product.status);
  useEffect(() => { const t = setTimeout(() => setDrawn(true), delay + 200); return () => clearTimeout(t); }, [delay]);
  return (
    <tr
      ref={anim.ref}
      className={s.tableRow}
      style={anim.style}
      onClick={(e) => onSelect(product, e)}
      onContextMenu={(e) => { e.preventDefault(); onSelect(product, e); }}
    >
      <td className={s.td}>
        <div className={s.productCell}>
          <div className={s.productIconWrap} aria-hidden="true">
            <Package className={s.productIconSvg} />
          </div>
          <div><p className={s.productName}>{product.name}</p><p className={s.productCategory}>{product.category}</p></div>
        </div>
      </td>
      <td className={s.td}><span className={s.skuBadge}>{product.sku}</span></td>
      <td className={s.td}><span className={s.locationText}>{product.location}</span></td>
      <td className={s.td}><span className={s.priceText}>{formatCurrency(product.price || 0)}</span></td>
      <td className={s.td}>
        <div className={s.stockCell}>
          <div className={s.stockBarTrack}>
            <div className={s.stockBarFill} style={{ width: drawn ? `${product.stockPct}%` : "0%", background: sm.barColor, transition: "width 0.9s cubic-bezier(0.22,1,0.36,1)" }} />
          </div>
          <span className={s.stockPct}>{product.stockPct}%</span>
          <span className={s.statusBadge} style={{ background: sm.bg, color: sm.color }}>{product.status}</span>
        </div>
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── SIDE PANELS
// ─────────────────────────────────────────────────────────────────────────────
const CriticalAlertsPanel = memo(({ loading, alerts = [] }) => {
  const anim = useAnimateIn(200);
  const [pulse, setPulse] = useState(true);
  useEffect(() => { const id = setInterval(() => setPulse((p) => !p), 1100); return () => clearInterval(id); }, []);
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardHeader}>
        <div className={s.sideCardTitleRow}>
          <AlertTriangle className={`${s.sideIconSvg} ${s.alertIcon}`} aria-hidden="true" />
          <h3 className={s.sideCardTitle}>Critical Alerts</h3>
        </div>
        <span className={s.liveBadge}>
          <span style={{ width:6,height:6,borderRadius:"50%",background:"#FA5252",opacity:pulse?1:0.3,transition:"opacity 0.4s",display:"inline-block",marginRight:5 }} />LIVE
        </span>
      </div>
      <p className={s.sideCardSub}>Immediate action required for {alerts.length} items.</p>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ display: "flex", gap: 10 }}>
              <Skeleton w={32} h={32} style={{ borderRadius: 8, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <Skeleton w="70%" h={12} style={{ marginBottom: 5 }} />
                <Skeleton w="45%" h={10} />
              </div>
            </div>
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className={s.emptyState} style={{ padding: "24px 12px" }}>
          <p className={s.emptyTitle}>No critical stock alerts.</p>
        </div>
      ) : (
        <div className={s.alertList}>
          {alerts.map((product) => (
            <div key={product._id || product.id} className={s.alertItem}>
              <div className={s.alertDot} style={{ background: product.status === "Out" ? "#C92A2A22" : "#FA525222", color: product.status === "Out" ? "#C92A2A" : "#E67700" }} aria-hidden="true">
                <AlertTriangle className={s.alertDotIcon} />
              </div>
              <div className={s.alertInfo}>
                <p className={s.alertName}>{product.name}</p>
                <p className={s.alertSku}>{product.sku}</p>
              </div>
              <div className={s.alertRight}>
                <span className={s.alertUnits} style={{ color: product.units === 0 ? "#C92A2A" : "#E67700" }}>
                  {product.units} units left
                </span>
                <span className={s.alertThreshold}>Threshold: {product.threshold}</span>
                <span className={s.statusBadge} style={{ display: "inline-block", marginTop: 6, background: getStatusMeta(product.status).bg, color: getStatusMeta(product.status).color }}>
                  {product.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
      <button className={s.sideCardLink}>View all replenishment needs</button>
    </div>
  );
});
CriticalAlertsPanel.displayName = "CriticalAlertsPanel";

const WarehouseMapPanel = memo(({ loading, warehouses = [] }) => {
  const anim = useAnimateIn(350);
  const [expanded, setExpanded] = useState({});
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardTitleRow} style={{ marginBottom: 14 }}>
        <Warehouse className={s.sideIconSvg} aria-hidden="true" />
        <h3 className={s.sideCardTitle}>Warehouse Map</h3>
      </div>
      {loading ? (
        <><Skeleton h={80} style={{ borderRadius: 10, marginBottom: 12 }} /><Skeleton h={50} style={{ borderRadius: 10 }} /></>
      ) : warehouses.length === 0 ? (
        <div className={s.emptyState} style={{ padding: "24px 12px" }}>
          <p className={s.emptyTitle}>No warehouse data available.</p>
        </div>
      ) : (
        warehouses.map((wh) => {
          const isOpen = expanded[wh.id];
          return (
            <div key={wh.id} className={s.warehouseCard}>
              <div className={s.warehouseHeader} onClick={() => setExpanded((p) => ({ ...p, [wh.id]: !p[wh.id] }))} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setExpanded((p) => ({ ...p, [wh.id]: !p[wh.id] }))}>
                <div className={s.warehouseLeft}>
                  <div className={s.warehouseIconSmall} style={{ background: "#E9ECEF", color: "#3B5BDB" }} aria-hidden="true">
                    <Warehouse className={s.warehouseIconSvg} />
                  </div>
                  <div>
                    <p className={s.warehouseName}>{wh.name}</p>
                    <span className={s.warehouseTag} style={{ background: wh.capacity >= 80 ? "#EEF2FF" : wh.capacity >= 50 ? "#FFF3BF" : "#FFE3E3", color: wh.capacity >= 80 ? "#3B5BDB" : wh.capacity >= 50 ? "#F59F00" : "#C92A2A" }}>
                      {wh.tag}
                    </span>
                  </div>
                </div>
                <span className={s.expandChevron}>{isOpen ? "▲" : "▼"}</span>
              </div>
              {isOpen && (
                <div className={s.warehouseBody}>
                  <div className={s.warehouseStats}>
                    <div className={s.warehouseStat}>
                      <p className={s.whStatLabel}>CAPACITY</p>
                      <p className={s.whStatValue}>{wh.capacity}%</p>
                      <div className={s.whBarTrack}>
                        <div className={s.whBarFill} style={{ width: `${wh.capacity}%`, background: wh.capacity >= 80 ? "#3B5BDB" : wh.capacity >= 50 ? "#F59F00" : "#C92A2A" }} />
                      </div>
                    </div>
                    <div className={s.warehouseStat}>
                      <p className={s.whStatLabel}>ITEMS</p>
                      <p className={s.whStatValue}>{wh.items.toLocaleString()}</p>
                      <p className={s.whStatDelta} style={{ color: "#2F9E44" }}>{wh.productsCount} products</p>
                    </div>
                  </div>
                  <div className={s.warehouseStats} style={{ gap: 10 }}>
                    <div className={s.warehouseStat}>
                      <p className={s.whStatLabel}>LOW STOCK</p>
                      <p className={s.whStatValue}>{wh.lowStockCount}</p>
                    </div>
                    <div className={s.warehouseStat}>
                      <p className={s.whStatLabel}>PRODUCTS</p>
                      <p className={s.whStatValue}>{wh.productsCount}</p>
                    </div>
                  </div>
                  <button className={s.manageBtn}>Manage Warehouse Inventory</button>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
});
WarehouseMapPanel.displayName = "WarehouseMapPanel";

const LiveFeedPanel = memo(({ loading, feed = [] }) => {
  const anim = useAnimateIn(500);
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardTitleRow} style={{ marginBottom: 4 }}>
        <RadioTower className={s.sideIconSvg} aria-hidden="true" />
        <h3 className={s.sideCardTitle}>Live Feed</h3>
      </div>
      <p className={s.sideCardSub} style={{ marginBottom: 14 }}>Real-time asset movement tracking.</p>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", gap: 10 }}>
              <Skeleton w={28} h={28} style={{ borderRadius: 7, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <Skeleton w="75%" h={12} style={{ marginBottom: 5 }} />
                <Skeleton w="50%" h={10} />
              </div>
              <Skeleton w={50} h={10} />
            </div>
          ))}
        </div>
      ) : feed.length === 0 ? (
        <div className={s.emptyState} style={{ padding: "24px 12px" }}>
          <p className={s.emptyTitle}>No recent inventory activity.</p>
        </div>
      ) : (
        <div className={s.feedList}>
          {feed.map((item) => {
            const FeedIcon = FEED_ICONS[item.direction] || ArrowLeftRight;
            return (
              <div key={item.id} className={s.feedItem}>
                <div className={s.feedDot} style={{ background: item.iconColor + "18", color: item.iconColor }} aria-hidden="true">
                  <FeedIcon className={s.feedIconSvg} />
                </div>
                <div className={s.feedInfo}>
                  <p className={s.feedProduct}>{item.product}</p>
                  <p className={s.feedAction}>
                    {item.action} · <span style={{ fontWeight: 700, color: item.iconColor }}>{item.qty}</span>
                  </p>
                  <p className={s.feedLocation}>{item.location}</p>
                </div>
                <span className={s.feedTime}>{item.ago}</span>
              </div>
            );
          })}
        </div>
      )}
      <button className={s.sideCardLink}>Open Audit Trail ↗</button>
    </div>
  );
});
LiveFeedPanel.displayName = "LiveFeedPanel";

// ─────────────────────────────────────────────────────────────────────────────
// ── MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function InventoryPage() {
  const [activeNav,       setActiveNav]       = useState("inventory");
  const [activeFilter,    setActiveFilter]    = useState("All Stock");
  const [searchQuery,     setSearchQuery]     = useState("");
  const [currentPage,     setCurrentPage]     = useState(1);
  const [loading,         setLoading]         = useState(true);
  const [products,        setProducts]        = useState([]);
  const [stats,           setStats]           = useState(null);
  const [error,           setError]           = useState("");
  const [success,         setSuccess]         = useState("");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [showViewProduct, setShowViewProduct] = useState(false);
  const [showEditProduct, setShowEditProduct] = useState(false);
  const [showExport,      setShowExport]      = useState(false);   // Export modal
  const [showAddProduct,  setShowAddProduct]  = useState(false);   // Add modal
  const [submitting,      setSubmitting]      = useState(false);
  const [importingCsv,    setImportingCsv]    = useState(false);
  const [rowMenu,         setRowMenu]         = useState({ open:false, product:null, top:0, left:0 });
  const csvInputRef = useRef(null);
  const rowMenuRef = useRef(null);

  const clearMessages = useCallback(() => {
    setError("");
    setSuccess("");
  }, []);

  const fetchProducts = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getInventoryProducts();
      setProducts(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to fetch inventory products:", error);
      setError(error.message || "Failed to load inventory products.");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const data = await getInventoryStats();
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch inventory stats:", error);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
    fetchStats();
  }, [fetchProducts, fetchStats]);

  const handleAddProduct = useCallback(
    async (productData) => {
      try {
        setSubmitting(true);
        clearMessages();

        const createdProduct = await createInventoryProduct(productData);

        setProducts((prev) => [createdProduct, ...prev]);
        setSuccess("Product added successfully");
        await fetchStats();

        setShowAddProduct(false);
      } catch (error) {
        console.error("Failed to add product:", error);
        setError(error.message || "Failed to add product.");
      } finally {
        setSubmitting(false);
      }
    },
    [fetchStats, clearMessages]
  );

  const handleUpdateProduct = useCallback(
    async (id, productData) => {
      try {
        setSubmitting(true);
        clearMessages();

        const updatedProduct = await updateInventoryProduct(id, productData);

        setProducts((prev) =>
          prev.map((product) =>
            (product._id || product.id) === id ? updatedProduct : product
          )
        );

        setSuccess("Product updated successfully");
        await fetchStats();

        setShowEditProduct(false);
        setSelectedProduct(null);
      } catch (error) {
        console.error("Failed to update product:", error);
        setError(error.message || "Failed to update product.");
      } finally {
        setSubmitting(false);
      }
    },
    [fetchStats, clearMessages]
  );

  const handleDeleteProduct = useCallback(
    async (id) => {
      const confirmDelete = window.confirm(
        "Are you sure you want to delete this product?"
      );
      if (!confirmDelete) return;

      try {
        clearMessages();
        await deleteInventoryProduct(id);
        setProducts((prev) =>
          prev.filter((product) => (product._id || product.id) !== id)
        );
        setSuccess("Product deleted successfully");
        await fetchStats();
      } catch (error) {
        console.error("Failed to delete product:", error);
        setError(error.message || "Failed to delete product.");
      }
    },
    [fetchStats, clearMessages]
  );

  const handleImportCsv = useCallback(
    async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;

      try {
        setImportingCsv(true);
        clearMessages();

        const csvText = await file.text();
        const parsedProducts = parseProductsCsv(csvText);
        const result = await importInventoryProductsCsv(parsedProducts);

        setSuccess(
          result?.message ||
            `${parsedProducts.length} products imported successfully`
        );

        setCurrentPage(1);
        await fetchProducts();
        await fetchStats();
      } catch (error) {
        console.error("Failed to import CSV:", error);
        setError(error.message || "Failed to import CSV file.");
      } finally {
        setImportingCsv(false);
        event.target.value = "";
      }
    },
    [fetchProducts, fetchStats, clearMessages]
  );

  const handleViewProduct = useCallback((product) => {
    setSelectedProduct(product);
    setShowViewProduct(true);
  }, []);

  const handleEditProduct = useCallback((product) => {
    setSelectedProduct(product);
    setShowEditProduct(true);
  }, []);

  const openRowMenu = useCallback((product, event) => {
    event.preventDefault();
    event.stopPropagation();

    const menuWidth = 210;
    const menuHeight = 142;
    const offset = 8;
    const top = Math.min(event.clientY + offset, window.innerHeight - menuHeight - offset);
    const left = Math.min(event.clientX + offset, window.innerWidth - menuWidth - offset);

    setRowMenu({ open:true, product, top: Math.max(8, top), left: Math.max(8, left) });
  }, []);

  const closeRowMenu = useCallback(() => {
    setRowMenu({ open:false, product:null, top:0, left:0 });
  }, []);

  const handleRowMenuAction = useCallback((action) => {
    if (!rowMenu.product) return;

    if (action === "view") {
      handleViewProduct(rowMenu.product);
    }
    if (action === "edit") {
      handleEditProduct(rowMenu.product);
    }
    if (action === "delete") {
      handleDeleteProduct(rowMenu.product._id || rowMenu.product.id);
    }

    closeRowMenu();
  }, [rowMenu.product, handleViewProduct, handleEditProduct, handleDeleteProduct, closeRowMenu]);

  useEffect(() => {
    if (!rowMenu.open) return;

    const handleClickOutside = (event) => {
      if (rowMenuRef.current && !rowMenuRef.current.contains(event.target)) {
        setRowMenu({ open:false, product:null, top:0, left:0 });
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setRowMenu({ open:false, product:null, top:0, left:0 });
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [rowMenu.open]);

  const criticalAlerts = useMemo(() => {
    return products
      .filter((product) => {
        const units = Number(product.units || 0);
        const threshold = Number(product.threshold || 0);

        return (
          product.status === "Critical" ||
          product.status === "Low" ||
          product.status === "Out" ||
          units <= threshold
        );
      })
      .sort((a, b) => {
        if (a.status === "Out" && b.status !== "Out") return -1;
        if (b.status === "Out" && a.status !== "Out") return 1;

        const unitsA = Number(a.units || 0);
        const unitsB = Number(b.units || 0);
        if (unitsA !== unitsB) return unitsA - unitsB;

        return Number(a.stockPct || 0) - Number(b.stockPct || 0);
      })
      .slice(0, 5);
  }, [products]);

  const warehouseSummary = useMemo(() => {
    const grouped = products.reduce((acc, product) => {
      const location = product.location || "Unknown Location";
      if (!acc[location]) acc[location] = [];
      acc[location].push(product);
      return acc;
    }, {});

    return Object.entries(grouped)
      .map(([location, items]) => {
        const totalUnits = items.reduce((sum, item) => sum + Number(item.units || 0), 0);
        const averageStock = items.length
          ? Math.round(items.reduce((sum, item) => sum + Number(item.stockPct || 0), 0) / items.length)
          : 0;
        const lowStockCount = items.filter((item) => {
          const units = Number(item.units || 0);
          const threshold = Number(item.threshold || 0);
          return (
            item.status === "Critical" ||
            item.status === "Low" ||
            item.status === "Out" ||
            units <= threshold
          );
        }).length;

        return {
          id: location,
          name: location,
          capacity: averageStock,
          items: totalUnits,
          productsCount: items.length,
          lowStockCount,
          tag:
            averageStock >= 80
              ? "Optimized"
              : averageStock >= 50
              ? "Stable"
              : "Needs Attention",
        };
      })
      .sort((a, b) => {
        if (b.lowStockCount !== a.lowStockCount) return b.lowStockCount - a.lowStockCount;
        return b.items - a.items;
      })
      .slice(0, 3);
  }, [products]);

  const liveFeed = useMemo(() => {
    return [...products]
      .sort((a, b) => {
        const dateA = new Date(a.updatedAt || a.createdAt || 0).getTime();
        const dateB = new Date(b.updatedAt || b.createdAt || 0).getTime();
        return dateB - dateA;
      })
      .slice(0, 5)
      .map((product) => {
        const units = Number(product.units || 0);
        const threshold = Number(product.threshold || 0);
        const timestamp = product.updatedAt || product.createdAt;
        const ago = formatTimeAgo(timestamp);

        if (units === 0 || product.status === "Out") {
          return {
            id: product._id || product.id,
            product: product.name,
            action: "Out of Stock",
            qty: "0 units",
            location: product.location || "Unknown Location",
            ago,
            direction: "out",
            iconColor: "#C92A2A",
          };
        }

        if (units <= threshold || product.status === "Critical" || product.status === "Low") {
          return {
            id: product._id || product.id,
            product: product.name,
            action: "Low Stock Alert",
            qty: `${units} units left`,
            location: product.location || "Unknown Location",
            ago,
            direction: "out",
            iconColor: "#FA5252",
          };
        }

        if (product.status === "Healthy") {
          return {
            id: product._id || product.id,
            product: product.name,
            action: "Stock Available",
            qty: `${units} units`,
            location: product.location || "Unknown Location",
            ago,
            direction: "in",
            iconColor: "#2F9E44",
          };
        }

        return {
          id: product._id || product.id,
          product: product.name,
          action: "Inventory Updated",
          qty: `${units} units`,
          location: product.location || "Unknown Location",
          ago,
          direction: "transfer",
          iconColor: "#3B5BDB",
        };
      });
  }, [products]);

  const filteredProducts = useMemo(() => products.filter((p) => {
    const matchFilter =
      activeFilter === "All Stock" ||
      (activeFilter === "Low Health" && ["Warning", "Critical", "Low"].includes(p.status)) ||
      (activeFilter === "Out of Stock" && p.status === "Out");

    const q = searchQuery.toLowerCase();
    const matchSearch =
      !q ||
      p.name?.toLowerCase().includes(q) ||
      p.sku?.toLowerCase().includes(q) ||
      p.location?.toLowerCase().includes(q);

    return matchFilter && matchSearch;
  }), [products, activeFilter, searchQuery]);

  const totalPages        = Math.max(1, Math.ceil(filteredProducts.length / PAGE_SIZE));
  const paginatedProducts = filteredProducts.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const titleAnim         = useAnimateIn(0);

  const dynamicStats = [
    {
      id: "products",
      label: "Total Products",
      value: stats ? stats.totalProducts : 0,
      change: "Live",
      changeType: "up",
      sub: "Total number of products stored in inventory.",
    },
    {
      id: "units",
      label: "Total Units",
      value: stats ? stats.totalUnits : 0,
      change: "Live",
      changeType: "up",
      sub: "Total stock units available across all products.",
    },
    {
      id: "totalSum",
      label: "Total Sum",
      value: stats
        ? formatCurrency(stats.totalSum || 0)
        : formatCurrency(products.reduce((sum, product) => sum + Number(product.price || 0), 0)),
      change: "Live",
      changeType: "up",
      sub: "Total sum of all product prices in inventory.",
    },
    {
      id: "lowstock",
      label: "Low Stock",
      value: stats ? `${stats.lowStockItems} Items` : "0 Items",
      change: stats ? `${stats.outOfStockItems} Out` : "0 Out",
      changeType: "down",
      sub: "Products that are below threshold or out of stock.",
    },
  ];

  return (
    <>
      <style>{`@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}@keyframes modalIn{from{opacity:0;transform:scale(0.96) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}*{box-sizing:border-box}`}</style>

      <div className={shell.appShell}>
        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
        <div className={shell.mainArea}>
          <Header breadcrumbs={["Prime ERP","Inventory","Stock Management"]} />
          <main className={s.page}>

            {/* Page Header */}
            <header ref={titleAnim.ref} className={s.pageHeader} style={titleAnim.style}>
              <div>
                <h1 className={s.pageTitle}>Stock Overview</h1>
                <p className={s.pageSub}>Monitor real-time inventory health and warehouse operations.</p>
              </div>
              <div className={s.headerActions}>
                <button
                  className={`${s.btn} ${s.btnOutline}`}
                  onClick={() => setShowExport(true)}
                  disabled={loading}
                  aria-label="Export inventory report"
                >
                  <Download className={s.btnIcon} aria-hidden="true" />
                  Export Report
                </button>
                <button
                  className={`${s.btn} ${s.btnOutline}`}
                  onClick={() => csvInputRef.current?.click()}
                  disabled={loading || importingCsv}
                  aria-label="Import products from CSV"
                >
                  <Upload className={s.btnIcon} aria-hidden="true" />
                  {importingCsv ? "Importing..." : "Import CSV"}
                </button>
                <input
                  ref={csvInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  style={{ display: "none" }}
                  onChange={handleImportCsv}
                />
                <button
                  className={`${s.btn} ${s.btnPrimary}`}
                  onClick={() => setShowAddProduct(true)}
                  aria-label="Add new product"
                >
                  <Plus className={s.btnIcon} aria-hidden="true" />
                  Add New Product
                </button>
              </div>
            </header>

            {/* Stat Cards */}
            <div className={s.statGrid}>
              {loading
                ? Array.from({ length: 4 }).map((_, i) => <StatCard key={i} loading delay={i * 70} />)
                : dynamicStats.map((stat, i) => <StatCard key={stat.id} stat={stat} delay={i * 70} />)
              }
            </div>

            {error && (
              <div className={s.messageBoxError}>{error}</div>
            )}
            {success && (
              <div className={s.messageBoxSuccess}>{success}</div>
            )}

            {/* Content */}
            <div className={s.contentLayout}>

              {/* Table */}
              <div className={s.tableSection}>
                <div className={s.toolbar}>
                  <div className={s.searchWrap}>
                    <Search className={s.searchIcon} aria-hidden="true" />
                    <input className={s.searchInput} value={searchQuery} onChange={e=>{ setSearchQuery(e.target.value); setCurrentPage(1); }} placeholder="Search products, SKUs, or locations..." aria-label="Search"/>
                  </div>
                </div>

                <div className={s.filterTabs}>
                  {["All Stock","Low Health","Out of Stock"].map(tab=>(
                    <button key={tab} role="tab" aria-selected={activeFilter===tab}
                      className={`${s.filterTab} ${activeFilter===tab?s.filterTabActive:""}`}
                      onClick={()=>{ setActiveFilter(tab); setCurrentPage(1); }}>
                      {tab}
                    </button>
                  ))}
                </div>

                <div className={s.tableWrap}>
                  <table className={s.table} aria-label="Inventory products">
                    <thead>
                      <tr>
                        {["Product Name","SKU","Location","Price","Stock Level"].map(h=><th key={h} className={s.th}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {loading
                        ? Array.from({length:8}).map((_,i)=><tr key={i} className={s.tableRow}>{[160,80,110,90,140].map((w,j)=><td key={j} className={s.td}><Skeleton w={w+"px"} h={12}/></td>)}</tr>)
                        : paginatedProducts.length===0
                          ? <tr><td colSpan={5}><div className={s.emptyState}><FolderOpen className={s.emptyIcon} aria-hidden="true" /><p className={s.emptyTitle}>No products found</p><p className={s.emptySub}>Try adjusting your filters or search.</p></div></td></tr>
                          : paginatedProducts.map((p,i)=>(
                              <ProductRow
                                key={p._id || p.id}
                                product={p}
                                delay={i*50}
                                onSelect={openRowMenu}
                              />
                            ))
                      }
                    </tbody>
                  </table>
                </div>

                {rowMenu.open && (
                  <div
                    ref={rowMenuRef}
                    className={s.rowMenu}
                    style={{ top: rowMenu.top, left: rowMenu.left }}
                  >
                    <button className={s.rowMenuItem} onClick={() => handleRowMenuAction("view")}>
                      <Eye className={s.rowMenuIcon} aria-hidden="true" />
                      View
                    </button>
                    <button className={s.rowMenuItem} onClick={() => handleRowMenuAction("edit")}>
                      <Pencil className={s.rowMenuIcon} aria-hidden="true" />
                      Edit
                    </button>
                    <button className={`${s.rowMenuItem} ${s.rowMenuDelete}`} onClick={() => handleRowMenuAction("delete")}> 
                      <Trash2 className={s.rowMenuIcon} aria-hidden="true" />
                      Delete
                    </button>
                  </div>
                )}

                {!loading && filteredProducts.length > 0 && (
                  <div className={s.pagination}>
                    <span className={s.paginationInfo}>
                      Showing {Math.min((currentPage-1)*PAGE_SIZE+1, filteredProducts.length)}–{Math.min(currentPage*PAGE_SIZE, filteredProducts.length)} of {filteredProducts.length} products
                    </span>
                    <div className={s.paginationControls}>
                      <button className={s.pageBtn} onClick={()=>setCurrentPage(p=>p-1)} disabled={currentPage===1}>‹</button>
                      {Array.from({length:totalPages},(_,i)=>i+1).map(p=>(
                        <button key={p} className={`${s.pageBtn} ${p===currentPage?s.pageBtnActive:""}`} onClick={()=>setCurrentPage(p)} aria-current={p===currentPage?"page":undefined}>{p}</button>
                      ))}
                      <button className={s.pageBtn} onClick={()=>setCurrentPage(p=>p+1)} disabled={currentPage===totalPages}>›</button>
                    </div>
                  </div>
                )}
              </div>

              {/* Right sidebar */}
              <aside className={s.rightSidebar}>
                <CriticalAlertsPanel loading={loading} alerts={criticalAlerts} />
                <WarehouseMapPanel loading={loading} warehouses={warehouseSummary} />
                <LiveFeedPanel loading={loading} feed={liveFeed} />
              </aside>
            </div>
          </main>

          <footer className={s.footer}>
            <span>© 2026 Prime ERP Systems. All rights reserved.</span>
            <div className={s.footerRight}>
              <a href="#" className={s.footerLink}>Privacy Policy</a>
              <a href="#" className={s.footerLink}>Terms of Service</a>
              <span className={s.statusDot}><span style={{ width:7,height:7,borderRadius:"50%",background:"#2F9E44",display:"inline-block",marginRight:5 }}/>System Status: Operational</span>
              <span>v1-stable</span>
            </div>
          </footer>
        </div>
      </div>

      <ExportReportModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        products={products}
        stats={stats}
        criticalAlerts={criticalAlerts}
        warehouseSummary={warehouseSummary}
      />

      <ViewProductModal
        isOpen={showViewProduct}
        product={selectedProduct}
        onClose={() => setShowViewProduct(false)}
      />

      <AddProductModal
        isOpen={showAddProduct}
        onClose={() => setShowAddProduct(false)}
        onAdd={handleAddProduct}
        submitting={submitting}
      />

      <AddProductModal
        isOpen={showEditProduct}
        product={selectedProduct}
        onClose={() => {
          setShowEditProduct(false);
          setSelectedProduct(null);
        }}
        onUpdate={handleUpdateProduct}
        submitting={submitting}
      />
    </>
  );
}
