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
  MoreHorizontal,
  Package,
  PackagePlus,
  Pencil,
  Plus,
  RadioTower,
  Search,
  SlidersHorizontal,
  Warehouse,
  X,
} from "lucide-react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import s from "../styles/InventoryPage.module.css";

// ─────────────────────────────────────────────────────────────────────────────
// ── MOCK DATA
// ─────────────────────────────────────────────────────────────────────────────
const INITIAL_STATS = [
  { id:"assets",   label:"Total Assets",   value:"$2,845,000", change:"+12.8%", changeType:"up",   sub:"Current market value of all stocked items across all warehouses." },
  { id:"turnover", label:"Stock Turnover", value:"4.2x",       change:"+0.8%",  changeType:"up",   sub:"Inventory turnover ratio for the current fiscal quarter." },
  { id:"util",     label:"Utilization",    value:"78.4%",      change:"-2.1%",  changeType:"down", sub:"Average warehouse capacity utilized nationwide." },
  { id:"lowstock", label:"Low Stock",      value:"14 Items",   change:"+3",     changeType:"down", sub:"Products that have fallen below the critical threshold." },
];

const STAT_ICONS = {
  assets: CircleDollarSign,
  turnover: ArrowLeftRight,
  util: Boxes,
  lowstock: AlertTriangle,
};

const INITIAL_PRODUCTS = [
  { id:"p1", name:"Quantum Processor X1",  category:"Electronics", sku:"SYN-Q100", location:"Warehouse A-12", stockPct:85, status:"Healthy",  units:850, threshold:100 },
  { id:"p2", name:"Nebula Glass Screen",   category:"Electronics", sku:"SYN-N550", location:"Warehouse B-04", stockPct:12, status:"Critical", units:12,  threshold:50  },
  { id:"p3", name:"Titanium Chassis V2",   category:"Electronics", sku:"SYN-T600", location:"Central Hub",    stockPct:45, status:"Warning",  units:225, threshold:80  },
  { id:"p4", name:"Optic Fiber Bundle",    category:"Electronics", sku:"SYN-F80",  location:"Warehouse A-10", stockPct:92, status:"Healthy",  units:920, threshold:100 },
  { id:"p5", name:"Fusion Cell Unit",      category:"Electronics", sku:"SYN-FC01", location:"Secure Vault",   stockPct:8,  status:"Low",      units:8,   threshold:20  },
  { id:"p6", name:"Neural Interface Chip", category:"Electronics", sku:"SYN-NI22", location:"Warehouse A-12", stockPct:61, status:"Healthy",  units:610, threshold:100 },
  { id:"p7", name:"Liquid Coolant X-9",    category:"Consumables", sku:"SYN-LC99", location:"Warehouse B-04", stockPct:0,  status:"Out",      units:0,   threshold:10  },
  { id:"p8", name:"Power Relay Module",    category:"Electronics", sku:"SYN-PR77", location:"Central Hub",    stockPct:34, status:"Warning",  units:170, threshold:200 },
];

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
const PAGE_SIZE      = 5;

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

// ─────────────────────────────────────────────────────────────────────────────
// ── EXPORT REPORT MODAL
// ─────────────────────────────────────────────────────────────────────────────
function ExportReportModal({ isOpen, onClose, products }) {
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
      filename:`synergy-inventory-products-${today()}`,
      rows:() => products.map(p => ({ "Product Name":p.name, Category:p.category, SKU:p.sku, Location:p.location, "Stock %":p.stockPct+"%", Units:p.units, Threshold:p.threshold, Status:p.status })),
    },
    {
      id:"kpis", icon:ChartNoAxesCombined, label:"Inventory KPIs",
      desc:"Total assets, turnover ratio, utilization & low stock count",
      filename:`synergy-inventory-kpis-${today()}`,
      rows:() => INITIAL_STATS.map(s => ({ Metric:s.label, Value:s.value, Change:s.change, Trend:s.changeType })),
    },
    {
      id:"alerts", icon:AlertTriangle, label:"Critical Alerts",
      desc:"Products below minimum threshold requiring replenishment",
      filename:`synergy-inventory-alerts-${today()}`,
      rows:() => CRITICAL_ALERTS.map(a => ({ "Product Name":a.name, SKU:a.sku, "Units Left":a.unitsLeft, Threshold:a.threshold, Status:a.unitsLeft===0?"Out of Stock":"Critical" })),
    },
    {
      id:"warehouses", icon:Warehouse, label:"Warehouse Report",
      desc:"Capacity, item count and status per warehouse",
      filename:`synergy-inventory-warehouses-${today()}`,
      rows:() => WAREHOUSES.map(w => ({ Warehouse:w.name, Tag:w.tag, "Capacity %":w.capacity+"%", "Total Items":w.items, Delta:w.delta })),
    },
  ], [products]);

  const handleExport = useCallback(async item => {
    setStatuses(p => ({ ...p, [item.id]:"loading" }));
    await new Promise(r => setTimeout(r, 400));
    try {
      const rows = item.rows();
      format === "csv"
        ? downloadFile(toCSV(rows), `${item.filename}.csv`, "text/csv;charset=utf-8;")
        : downloadFile(JSON.stringify(rows, null, 2), `${item.filename}.json`, "application/json");
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
            {["csv","json"].map(f => (
              <button key={f} className={`${s.formatBtn} ${format===f?s.formatBtnActive:""}`} onClick={()=>{ setFormat(f); setStatuses({}); }}>
                {f==="csv" ? <><FileText className={s.inlineIcon} aria-hidden="true" />CSV</> : "{ } JSON"}
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
const EMPTY_FORM = { name:"", category:"Electronics", sku:"", location:"Warehouse A-12", units:"", threshold:"", status:"Healthy" };

function AddProductModal({ isOpen, onClose, onAdd }) {
  const [form,    setForm]    = useState(EMPTY_FORM);
  const [errors,  setErrors]  = useState({});
  const [loading, setLoading] = useState(false);
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const fn = e => { if (e.key==="Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [isOpen, onClose]);

  useEffect(() => { if (isOpen) { setForm(EMPTY_FORM); setErrors({}); } }, [isOpen]);

  const setField = (field, value) => {
    setForm(p => ({ ...p, [field]:value }));
    setErrors(p => { const n={...p}; delete n[field]; return n; });
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim())                             e.name      = "Product name is required";
    if (!form.sku.trim())                              e.sku       = "SKU is required";
    if (!form.units || isNaN(form.units) || Number(form.units)<0)  e.units     = "Valid unit count required";
    if (!form.threshold || isNaN(form.threshold) || Number(form.threshold)<0) e.threshold = "Valid threshold required";
    return e;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setLoading(true);
    await new Promise(r => setTimeout(r, 600));
    const units     = Number(form.units);
    const threshold = Number(form.threshold);
    const stockPct  = threshold > 0 ? Math.min(100, Math.round((units / (threshold*2))*100)) : 100;
    onAdd({ id:"p"+Date.now(), name:form.name.trim(), category:form.category, sku:form.sku.trim().toUpperCase(), location:form.location, units, threshold, stockPct, status:form.status });
    setLoading(false);
    onClose();
  };

  if (!isOpen) return null;

  const Field = ({ id, label, required, error, children }) => (
    <div className={s.formGroup}>
      <label className={s.formLabel} htmlFor={id}>{label}{required && <span className={s.required}> *</span>}</label>
      {children}
      {error && <p className={s.fieldError}>{error}</p>}
    </div>
  );

  return (
    <div className={s.modalOverlay} ref={overlayRef} onClick={e=>{ if(e.target===overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal}>
        {/* Header */}
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon} aria-hidden="true">
              <PackagePlus className={s.modalTitleIconSvg} />
            </div>
            <div>
              <h2 className={s.modalTitle}>Add New Product</h2>
              <p className={s.modalSub}>Fill in the details to add a product to inventory.</p>
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
              <label className={s.formLabel} htmlFor="ap-name">Product Name <span className={s.required}>*</span></label>
              <input id="ap-name" className={`${s.formInput} ${errors.name?s.formInputError:""}`}
                value={form.name} onChange={e=>setField("name",e.target.value)}
                placeholder="e.g. Quantum Processor X2" autoFocus />
              {errors.name && <p className={s.fieldError}>{errors.name}</p>}
            </div>

            {/* SKU */}
            <Field id="ap-sku" label="SKU" required error={errors.sku}>
              <input id="ap-sku" className={`${s.formInput} ${errors.sku?s.formInputError:""}`}
                value={form.sku} onChange={e=>setField("sku",e.target.value)} placeholder="e.g. SYN-Q200" />
            </Field>

            {/* Category */}
            <Field id="ap-cat" label="Category">
              <select id="ap-cat" className={s.formSelect} value={form.category} onChange={e=>setField("category",e.target.value)}>
                {CATEGORIES.map(c=><option key={c}>{c}</option>)}
              </select>
            </Field>

            {/* Location */}
            <Field id="ap-loc" label="Location">
              <select id="ap-loc" className={s.formSelect} value={form.location} onChange={e=>setField("location",e.target.value)}>
                {LOCATIONS.map(l=><option key={l}>{l}</option>)}
              </select>
            </Field>

            {/* Status */}
            <Field id="ap-st" label="Initial Status">
              <select id="ap-st" className={s.formSelect} value={form.status} onChange={e=>setField("status",e.target.value)}>
                {STATUS_OPTIONS.map(st=><option key={st}>{st}</option>)}
              </select>
            </Field>

            {/* Units */}
            <Field id="ap-units" label="Unit Count" required error={errors.units}>
              <input id="ap-units" type="number" min="0" className={`${s.formInput} ${errors.units?s.formInputError:""}`}
                value={form.units} onChange={e=>setField("units",e.target.value)} placeholder="e.g. 500" />
            </Field>

            {/* Threshold */}
            <Field id="ap-thr" label="Low Stock Threshold" required error={errors.threshold}>
              <input id="ap-thr" type="number" min="0" className={`${s.formInput} ${errors.threshold?s.formInputError:""}`}
                value={form.threshold} onChange={e=>setField("threshold",e.target.value)} placeholder="e.g. 50" />
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
            <button className={`${s.btn} ${s.btnPrimary}`} onClick={handleSubmit} disabled={loading}>
              {loading ? <><span className={s.exportSpinner}/> Adding...</> : <><CheckCircle2 className={s.btnIcon} aria-hidden="true" />Add Product</>}
            </button>
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
      <div className={`${s.statIconBadge} ${stat.id==="assets"?s.statIconBadgeActive:s.statIconBadgeNeutral}`} aria-hidden="true">
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
function ProductRow({ product, delay=0 }) {
  const [drawn, setDrawn] = useState(false);
  const anim = useAnimateIn(delay);
  const sm = getStatusMeta(product.status);
  useEffect(() => { const t=setTimeout(()=>setDrawn(true), delay+200); return ()=>clearTimeout(t); }, [delay]);
  return (
    <tr ref={anim.ref} className={s.tableRow} style={anim.style}>
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
      <td className={s.td}>
        <div className={s.stockCell}>
          <div className={s.stockBarTrack}>
            <div className={s.stockBarFill} style={{ width:drawn?`${product.stockPct}%`:"0%", background:sm.barColor, transition:"width 0.9s cubic-bezier(0.22,1,0.36,1)" }} />
          </div>
          <span className={s.stockPct}>{product.stockPct}%</span>
          <span className={s.statusBadge} style={{ background:sm.bg, color:sm.color }}>{product.status}</span>
        </div>
      </td>
      <td className={s.td}>
        <div className={s.rowActions}>
          <button className={s.actionBtn} aria-label={`View ${product.name}`} title="View">
            <Eye aria-hidden="true" />
          </button>
          <button className={s.actionBtn} aria-label={`Edit ${product.name}`} title="Edit">
            <Pencil aria-hidden="true" />
          </button>
          <button className={s.actionBtn} aria-label={`More actions for ${product.name}`} title="More actions">
            <MoreHorizontal aria-hidden="true" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ── SIDE PANELS
// ─────────────────────────────────────────────────────────────────────────────
const CriticalAlertsPanel = memo(({ loading }) => {
  const anim = useAnimateIn(200);
  const [pulse, setPulse] = useState(true);
  useEffect(() => { const id=setInterval(()=>setPulse(p=>!p),1100); return ()=>clearInterval(id); }, []);
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardHeader}>
        <div className={s.sideCardTitleRow}>
          <AlertTriangle className={`${s.sideIconSvg} ${s.alertIcon}`} aria-hidden="true" />
          <h3 className={s.sideCardTitle}>Critical Alerts</h3>
        </div>
        <span className={s.liveBadge}><span style={{ width:6,height:6,borderRadius:"50%",background:"#FA5252",opacity:pulse?1:0.3,transition:"opacity 0.4s",display:"inline-block",marginRight:5 }}/>LIVE</span>
      </div>
      <p className={s.sideCardSub}>Immediate action required for 14 items.</p>
      {loading ? <div style={{ display:"flex",flexDirection:"column",gap:10,marginTop:12 }}>{[1,2,3].map(i=><div key={i} style={{ display:"flex",gap:10 }}><Skeleton w={32} h={32} style={{ borderRadius:8,flexShrink:0 }}/><div style={{ flex:1 }}><Skeleton w="70%" h={12} style={{ marginBottom:5 }}/><Skeleton w="45%" h={10}/></div></div>)}</div>
      : <div className={s.alertList}>{CRITICAL_ALERTS.map(a=>(
          <div key={a.id} className={s.alertItem}>
            <div className={s.alertDot} style={{ background:a.color+"22",color:a.color }} aria-hidden="true">
              <AlertTriangle className={s.alertDotIcon} />
            </div>
            <div className={s.alertInfo}><p className={s.alertName}>{a.name}</p><p className={s.alertSku}>{a.sku}</p></div>
            <div className={s.alertRight}>
              <span className={s.alertUnits} style={{ color:a.unitsLeft===0?"#C92A2A":"#E67700" }}>{a.unitsLeft} units left</span>
              <span className={s.alertThreshold}>Threshold: {a.threshold}</span>
            </div>
          </div>
        ))}</div>}
      <button className={s.sideCardLink}>View all replenishment needs</button>
    </div>
  );
});
CriticalAlertsPanel.displayName = "CriticalAlertsPanel";

const WarehouseMapPanel = memo(({ loading }) => {
  const anim = useAnimateIn(350);
  const [expanded, setExpanded] = useState({ w1:true, w2:false });
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardTitleRow} style={{ marginBottom:14 }}>
        <Warehouse className={s.sideIconSvg} aria-hidden="true" />
        <h3 className={s.sideCardTitle}>Warehouse Map</h3>
      </div>
      {loading ? <><Skeleton h={80} style={{ borderRadius:10,marginBottom:12 }}/><Skeleton h={50} style={{ borderRadius:10 }}/></> :
        WAREHOUSES.map(wh => {
          const isOpen = expanded[wh.id];
          return (
            <div key={wh.id} className={s.warehouseCard}>
              <div className={s.warehouseHeader} onClick={()=>setExpanded(p=>({...p,[wh.id]:!p[wh.id]}))} role="button" tabIndex={0} onKeyDown={e=>e.key==="Enter"&&setExpanded(p=>({...p,[wh.id]:!p[wh.id]}))}>
                <div className={s.warehouseLeft}>
                  <div className={s.warehouseIconSmall} style={{ background:wh.color+"18",color:wh.color }} aria-hidden="true">
                    <Warehouse className={s.warehouseIconSvg} />
                  </div>
                  <div>
                    <p className={s.warehouseName}>{wh.name}</p>
                    <span className={s.warehouseTag} style={{ background:wh.color==="#3B5BDB"?"#EEF2FF":"#FFF3BF",color:wh.color }}>{wh.tag}</span>
                  </div>
                </div>
                <span className={s.expandChevron}>{isOpen?"▲":"▼"}</span>
              </div>
              {isOpen && (
                <div className={s.warehouseBody}>
                  <div className={s.warehouseStats}>
                    <div className={s.warehouseStat}><p className={s.whStatLabel}>CAPACITY</p><p className={s.whStatValue}>{wh.capacity}%</p><div className={s.whBarTrack}><div className={s.whBarFill} style={{ width:`${wh.capacity}%`,background:wh.color }}/></div></div>
                    <div className={s.warehouseStat}><p className={s.whStatLabel}>ITEMS</p><p className={s.whStatValue}>{wh.items.toLocaleString()}</p><p className={s.whStatDelta} style={{ color:"#2F9E44" }}>{wh.delta}</p></div>
                  </div>
                  <button className={s.manageBtn}>Manage Warehouse Inventory</button>
                </div>
              )}
            </div>
          );
        })
      }
    </div>
  );
});
WarehouseMapPanel.displayName = "WarehouseMapPanel";

const LiveFeedPanel = memo(({ loading }) => {
  const anim = useAnimateIn(500);
  return (
    <div ref={anim.ref} className={s.sideCard} style={anim.style}>
      <div className={s.sideCardTitleRow} style={{ marginBottom:4 }}>
        <RadioTower className={s.sideIconSvg} aria-hidden="true" />
        <h3 className={s.sideCardTitle}>Live Feed</h3>
      </div>
      <p className={s.sideCardSub} style={{ marginBottom:14 }}>Real-time asset movement tracking.</p>
      {loading ? <div style={{ display:"flex",flexDirection:"column",gap:14 }}>{[1,2,3,4].map(i=><div key={i} style={{ display:"flex",gap:10 }}><Skeleton w={28} h={28} style={{ borderRadius:7,flexShrink:0 }}/><div style={{ flex:1 }}><Skeleton w="75%" h={12} style={{ marginBottom:5 }}/><Skeleton w="50%" h={10}/></div><Skeleton w={50} h={10}/></div>)}</div>
      : <div className={s.feedList}>{LIVE_FEED.map(item=>{
          const FeedIcon = FEED_ICONS[item.direction] || ArrowLeftRight;
          return (
          <div key={item.id} className={s.feedItem}>
            <div className={s.feedDot} style={{ background:item.iconColor+"18",color:item.iconColor }} aria-hidden="true">
              <FeedIcon className={s.feedIconSvg} />
            </div>
            <div className={s.feedInfo}><p className={s.feedProduct}>{item.product}</p><p className={s.feedAction}>{item.action} · <span style={{ fontWeight:700,color:item.iconColor }}>{item.qty}</span></p><p className={s.feedLocation}>{item.location}</p></div>
            <span className={s.feedTime}>{item.ago}</span>
          </div>
        )})}</div>}
      <button className={s.sideCardLink}>Open Audit Trail ↗</button>
    </div>
  );
});
LiveFeedPanel.displayName = "LiveFeedPanel";

// ─────────────────────────────────────────────────────────────────────────────
// ── MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function InventoryPage() {
  const [activeNav,      setActiveNav]      = useState("inventory");
  const [activeFilter,   setActiveFilter]   = useState("All Stock");
  const [searchQuery,    setSearchQuery]    = useState("");
  const [currentPage,    setCurrentPage]    = useState(1);
  const [loading,        setLoading]        = useState(true);
  const [products,       setProducts]       = useState(INITIAL_PRODUCTS);
  const [showExport,     setShowExport]     = useState(false);   // Export modal
  const [showAddProduct, setShowAddProduct] = useState(false);   // Add modal

  useEffect(() => { const t=setTimeout(()=>setLoading(false),800); return ()=>clearTimeout(t); }, []);

  const handleAddProduct = useCallback(p => setProducts(prev=>[p,...prev]), []);

  const filteredProducts = useMemo(() => products.filter(p => {
    const matchFilter = activeFilter==="All Stock" || (activeFilter==="Low Health" && ["Warning","Critical","Low"].includes(p.status)) || (activeFilter==="Out of Stock" && p.status==="Out");
    const q = searchQuery.toLowerCase();
    const matchSearch = !q || p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || p.location.toLowerCase().includes(q);
    return matchFilter && matchSearch;
  }), [products, activeFilter, searchQuery]);

  const totalPages        = Math.max(1, Math.ceil(filteredProducts.length/PAGE_SIZE));
  const paginatedProducts = filteredProducts.slice((currentPage-1)*PAGE_SIZE, currentPage*PAGE_SIZE);
  const titleAnim         = useAnimateIn(0);

  return (
    <>
      <style>{`@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}@keyframes modalIn{from{opacity:0;transform:scale(0.96) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}*{box-sizing:border-box}`}</style>

      <div className={s.appShell}>
        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
        <div className={s.mainArea}>
          <Header breadcrumbs={["Synergy ERP","Inventory","Stock Management"]} />
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
                ? Array.from({length:4}).map((_,i)=><StatCard key={i} loading delay={i*70}/>)
                : INITIAL_STATS.map((stat,i)=><StatCard key={stat.id} stat={stat} delay={i*70}/>)
              }
            </div>

            {/* Content */}
            <div className={s.contentLayout}>

              {/* Table */}
              <div className={s.tableSection}>
                <div className={s.toolbar}>
                  <div className={s.searchWrap}>
                    <Search className={s.searchIcon} aria-hidden="true" />
                    <input className={s.searchInput} value={searchQuery} onChange={e=>{ setSearchQuery(e.target.value); setCurrentPage(1); }} placeholder="Search products, SKUs, or locations..." aria-label="Search"/>
                  </div>
                  <button className={s.filterIconBtn} aria-label="Filter inventory">
                    <SlidersHorizontal className={s.btnIcon} aria-hidden="true" />
                    Filter
                  </button>
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
                        {["Product Name","SKU","Location","Stock Level","Actions"].map(h=><th key={h} className={s.th}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {loading
                        ? Array.from({length:5}).map((_,i)=><tr key={i} className={s.tableRow}>{[160,80,110,140,90].map((w,j)=><td key={j} className={s.td}><Skeleton w={w+"px"} h={12}/></td>)}</tr>)
                        : paginatedProducts.length===0
                          ? <tr><td colSpan={5}><div className={s.emptyState}><FolderOpen className={s.emptyIcon} aria-hidden="true" /><p className={s.emptyTitle}>No products found</p><p className={s.emptySub}>Try adjusting your filters or search.</p></div></td></tr>
                          : paginatedProducts.map((p,i)=><ProductRow key={p.id} product={p} delay={i*50}/>)
                      }
                    </tbody>
                  </table>
                </div>

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
                <CriticalAlertsPanel loading={loading}/>
                <WarehouseMapPanel   loading={loading}/>
                <LiveFeedPanel       loading={loading}/>
              </aside>
            </div>
          </main>

          <footer className={s.footer}>
            <span>© 2024 Synergy ERP Systems. All rights reserved.</span>
            <div className={s.footerRight}>
              <a href="#" className={s.footerLink}>Privacy Policy</a>
              <a href="#" className={s.footerLink}>Terms of Service</a>
              <span className={s.statusDot}><span style={{ width:7,height:7,borderRadius:"50%",background:"#2F9E44",display:"inline-block",marginRight:5 }}/>System Status: Operational</span>
              <span>v2.4.0-stable</span>
            </div>
          </footer>
        </div>
      </div>

      <ExportReportModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        products={products}
      />

      <AddProductModal
        isOpen={showAddProduct}
        onClose={() => setShowAddProduct(false)}
        onAdd={handleAddProduct}
      />
    </>
  );
}
