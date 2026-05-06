import { useState, useRef, useEffect } from "react";
import "./NotificationBell.css";

const NOTIFICATIONS = [
  { id: 1, unread: true,  icon: "📄", title: "New invoice approved",    desc: "Invoice #INV-2024-089 approved by Finance",       time: "2 min ago"  },
  { id: 2, unread: true,  icon: "👤", title: "New employee onboarded",  desc: "Sarah Johnson joined the Engineering team",       time: "18 min ago" },
  { id: 3, unread: true,  icon: "⚠️", title: "Low inventory alert",     desc: "Item SKU-4421 is below minimum stock threshold",  time: "1 hr ago"   },
  { id: 4, unread: false, icon: "✅", title: "Payroll processed",        desc: "Monthly payroll for May 2025 completed",          time: "3 hr ago"   },
  { id: 5, unread: false, icon: "❌", title: "Server error detected",    desc: "API gateway returned 502 on /finance/reports",    time: "Yesterday"  },
  { id: 6, unread: false, icon: "✉️", title: "Message from HR",         desc: "Updated leave policy document is available",      time: "2 days ago" },
];

export default function NotificationBell() {
  const [open, setOpen]     = useState(false);
  const [notifs, setNotifs] = useState(NOTIFICATIONS);
  const wrapRef             = useRef(null);

  const unreadCount = notifs.filter(n => n.unread).length;

  // إغلاق لما يضغط برا
  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const markAsRead = (id) =>
    setNotifs(prev => prev.map(n => n.id === id ? { ...n, unread: false } : n));

  const markAllRead = () =>
    setNotifs(prev => prev.map(n => ({ ...n, unread: false })));

  return (
    <div className="notif-wrap" ref={wrapRef}>
      <button
        className={`notif-bell-btn ${open ? "active" : ""}`}
        onClick={() => setOpen(v => !v)}
        aria-label="Notifications"
        aria-expanded={open}
      >
        🔔
        {unreadCount > 0 && (
          <span className="notif-badge">{unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-panel__head">
            <span className="notif-panel__title">
              Notifications
              {unreadCount > 0 && (
                <span className="notif-panel__count"> ({unreadCount} unread)</span>
              )}
            </span>
            <button className="notif-panel__mark-all" onClick={markAllRead}>
              Mark all as read
            </button>
          </div>

          <div className="notif-panel__list">
            {notifs.length === 0 ? (
              <div className="notif-panel__empty">No notifications</div>
            ) : (
              notifs.map(n => (
                <div
                  key={n.id}
                  className={`notif-item ${n.unread ? "notif-item--unread" : ""}`}
                  onClick={() => markAsRead(n.id)}
                >
                  <div className="notif-item__icon">{n.icon}</div>
                  <div className="notif-item__body">
                    <div className="notif-item__title">{n.title}</div>
                    <div className="notif-item__desc">{n.desc}</div>
                    <div className="notif-item__time">{n.time}</div>
                  </div>
                  {n.unread && <div className="notif-item__dot" />}
                </div>
              ))
            )}
          </div>

          <div className="notif-panel__foot">
            <button className="notif-panel__see-all">View all notifications</button>
          </div>
        </div>
      )}
    </div>
  );
}