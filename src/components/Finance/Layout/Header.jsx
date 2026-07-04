import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Search } from "lucide-react";
import { useAuth } from "../../../context/AuthContext";
import s from "./Header.module.css";

function getStoredUser() {
  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser) return {};
    const parsedUser = JSON.parse(rawUser);
    return parsedUser && typeof parsedUser === "object" ? parsedUser : {};
  } catch {
    return {};
  }
}

function getDisplayName(user) {
  return (
    user.name ||
    `${user.first_name || ""} ${user.last_name || ""}`.trim() ||
    user.email ||
    "User"
  );
}

function getInitials(name) {
  return (
    name
      .split(" ")
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "U"
  );
}

function formatRole(value = "user") {
  return value
    .toString()
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .trim()
    .toUpperCase();
}

export default function Header({ breadcrumbs = [] }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const [storedUser, setStoredUser] = useState(() => getStoredUser());
  const profileRef = useRef(null);
  const navigate = useNavigate();
  const { user: authUser, logout } = useAuth();

  const displayName = getDisplayName(storedUser);
  const initials = getInitials(displayName);
  const role = storedUser.role || "user";
  const department = storedUser.department || "";

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const handleStorage = () => setStoredUser(getStoredUser());
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    setStoredUser(authUser || getStoredUser());
  }, [authUser]);

  const handleLogout = async () => {
    await logout();
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("auth");
    localStorage.removeItem("authUser");
    setStoredUser({});
    setProfileOpen(false);
    navigate("/login", { replace: true });
  };

  return (
    <header className={s.topHeader}>
      <div className={s.breadcrumb}>
        {breadcrumbs.map((crumb, index) => (
          <span key={crumb} className={s.bcItem}>
            {index > 0 && <span className={s.bcSep}>›</span>}
            <span className={index === breadcrumbs.length - 1 ? s.bcActive : ""}>
              {crumb}
            </span>
          </span>
        ))}
      </div>

      <div className={s.hdrSearch}>
        <Search className={s.hdrSearchIcon} aria-hidden="true" />
        <input placeholder="Search everything..." />
      </div>

      <div className={s.hdrRight}>
        <div className={s.hdrBell}>
          <Bell className={s.hdrBellIcon} aria-hidden="true" />
          <span className={s.bellDot} />
        </div>

        <div className={s.userProfile} ref={profileRef}>
          <button
            className={s.userProfileButton}
            onClick={() => setProfileOpen((previousValue) => !previousValue)}
            type="button"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
          >
            <div className={s.userAvatar}>{initials}</div>

            <div className={s.userInfo}>
              <span className={s.userName}>{displayName}</span>
              <span className={s.userRole}>{formatRole(role)}</span>
            </div>

            <span className={s.dropdownArrow}>▾</span>
          </button>

          {profileOpen && (
            <div className={s.profileDropdown} role="menu">
              <div className={s.profileDropdownHeader}>
                <div className={s.profileDropdownName}>{displayName}</div>
                {storedUser.email && (
                  <div className={s.profileDropdownEmail}>{storedUser.email}</div>
                )}
                <div className={s.profileDropdownMeta}>
                  {formatRole(role)}
                  {department ? ` • ${formatRole(department)}` : ""}
                </div>
              </div>

              <div className={s.profileDropdownDivider} />

              <button
                className={s.logoutButton}
                onClick={handleLogout}
                type="button"
                role="menuitem"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
