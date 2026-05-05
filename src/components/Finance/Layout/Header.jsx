// ─── components/Layout/Header.jsx ────────────────────────────────────────────

import "./Header.css";
import { Bell, Search } from "lucide-react";

export default function Header({ breadcrumbs = [] }) {
  return (
    <header className="top-header">
      {/* Breadcrumb */}
      <div className="breadcrumb">
        {breadcrumbs.map((crumb, i) => (
          <span key={i} className="bc-item">
            {i > 0 && <span className="bc-sep">›</span>}
            <span className={i === breadcrumbs.length - 1 ? "bc-active" : ""}>
              {crumb}
            </span>
          </span>
        ))}
      </div>

      {/* Search */}
      <div className="hdr-search">
        <Search className="hdr-search-icon" aria-hidden="true" />
        <input placeholder="Search everything..." />
      </div>

      {/* Right side */}
      <div className="hdr-right">
        <div className="hdr-bell">
          <Bell className="hdr-bell-icon" aria-hidden="true" />
          <span className="bell-dot" />
        </div>
        <div className="user-profile">
          <div className="user-avatar">AS</div>
          <div>
            <div className="user-name">Alex Sterling</div>
            <div className="user-role">Executive Admin</div>
          </div>
        </div>
      </div>
    </header>
  );
}
