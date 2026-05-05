// ─── components/Finance/Layout/Sidebar.jsx ───────────────────────────────────
// ✅ useNavigate — كل nav item بيعمل navigate للصفحة الصح
// ✅ activeNav بيتحدد تلقائياً من الـ URL الحالي
// ✅ collapse يشتغل زي ما كان

import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "./Sidebar.css";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard",     icon: "⊞", path: "/dashboard"  },
  { id: "finance",   label: "Finance",       icon: "◈", path: "/finance"    },
  { id: "hr",        label: "HR & People",   icon: "👤", path: "/hr"         },
  { id: "sales",     label: "Sales & CRM",   icon: "◎", path: "/sales"      },
  { id: "inventory", label: "Inventory",     icon: "▤", path: "/inventory"  },
  { id: "support",   label: "Support",       icon: "◌", path: "/support"    },
  { id: "design",    label: "Design System", icon: "✦", path: "/design"     },
];

export default function Sidebar({ activeNav, onNavChange }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate  = useNavigate();
  const location  = useLocation();

  // ── تحديد الـ active item من الـ URL تلقائياً ──────────────────────────────
  // مثلاً /invoices أو /invoices/new → يظهر Finance active
  const currentPath = location.pathname;
  const resolvedActive = NAV_ITEMS.find((item) =>
    currentPath === item.path || currentPath.startsWith(item.path + "/")
  )?.id ?? activeNav ?? "finance";

  const handleNavClick = (item) => {
    onNavChange?.(item.id);   // للتوافق مع الكود القديم
    navigate(item.path);
  };

  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>

      {/* ── Logo ── */}
      <div
        className="sidebar-logo"
        style={{ cursor: "pointer" }}
        onClick={() => navigate("/finance")}
        role="link"
        aria-label="Go to Finance home"
      >
        <div className="logo-icon">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        {!collapsed && <span className="logo-text">Synergy</span>}
      </div>

      {/* ── Nav ── */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item${resolvedActive === item.id ? " active" : ""}`}
            onClick={() => handleNavClick(item)}
            aria-label={item.label}
            aria-current={resolvedActive === item.id ? "page" : undefined}
          >
            <span className="nav-icon">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* ── Bottom ── */}
      <div className="sidebar-bottom">
        <button
          className="collapse-btn"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="nav-icon">{collapsed ? "▶" : "◀"}</span>
          {!collapsed && <span>Collapse Menu</span>}
        </button>

        {!collapsed && (
          <div className="storage-box">
            <div className="storage-label">Synergy Cloud</div>
            <div className="storage-sub">Enterprise Storage: 84% full</div>
            <div className="storage-bar">
              <div className="storage-fill" />
            </div>
          </div>
        )}
      </div>

    </aside>
  );
}