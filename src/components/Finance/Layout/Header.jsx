import { useNavigate } from "react-router-dom";
import "./Header.css";
import NotificationBell from "./NotificationBell";

export default function Header({ breadcrumbs = [] }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    navigate("/login", { replace: true });
  };

  return (
    <header className="top-header">
      <div className="breadcrumb">
        {breadcrumbs.map((crumb, i) => (
          <span key={i} className="bc-item">
            {i > 0 && <span className="bc-sep">›</span>}
            <span className={i === breadcrumbs.length - 1 ? "bc-active" : ""}>{crumb}</span>
          </span>
        ))}
      </div>

      <div className="hdr-search">
        <span className="hdr-search-icon">🔍</span>
        <input placeholder="Search everything..." />
      </div>

      <div className="hdr-right">
        <NotificationBell />

        <div className="user-section">
          <div className="user-info">
            <div className="user-avatar">AS</div>
            <div className="user-texts">
              <span className="user-name">Alex Sterling</span>
              <span className="user-role">Executive Admin</span>
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            ⎋ Logout
          </button>
        </div>
      </div>
    </header>
  );
}