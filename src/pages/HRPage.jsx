// ─── Pages/HRPage.jsx ────────────────────────────────────────────────────────
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import useHRPage from "../hooks/useHRPage";
import ComplianceModal from "../components/HR/ComplianceModal";
import SmartHRPanel    from "../components/HR/SmartHRPanel";
import s from "../styles/HRPage.module.css";

function StatCard({ icon, label, value, change, changeType, loading }) {
  if (loading) {
    return (
      <div className={s.statCard}>
        <div className={s.skeletonCircle} />
        <div className={s.skeletonText} style={{ width: "55%", marginTop: 10 }} />
        <div className={s.skeletonText} style={{ width: "70%", height: 20 }} />
        <div className={s.skeletonText} style={{ width: "40%" }} />
      </div>
    );
  }

  const changeClass = changeType === "up" ? s.changeUp : changeType === "down" ? s.changeDown : s.changeNeutral;

  return (
    <div className={s.statCard}>
      {/* إذا كانت الأيقونة فارغة لن يظهر هذا الجزء */}
      {icon && (
        <div className={s.statIconWrap}>
          <span className={s.statIcon}>{icon}</span>
        </div>
      )}
      <p className={s.statLabel}>{label}</p>
      <p className={s.statValue}>{value}</p>
      <span className={`${s.statBadge} ${changeClass}`}>{change}</span>
    </div>
  );
}

function Avatar({ emp, size = 56 }) {
  const statusColor = emp.status === "active" ? "#2F9E44" : emp.status === "leave" ? "#F59F00" : "#ADB5BD";
  return (
    <div className={s.avatarWrap} style={{ width: size, height: size }}>
      <div
        className={s.avatar}
        style={{ background: emp.color, width: size, height: size, fontSize: size * 0.3 }}
        aria-hidden="true"
      >
        {emp.avatar}
      </div>
      <span className={s.statusDot} style={{ background: statusColor }} aria-label={`Status: ${emp.status}`} />
    </div>
  );
}

function EmployeeCard({ emp }) {
  const deptColors = {
    Engineering: "#3B5BDB", Design: "#845EF7", Marketing: "#F59F00",
    Finance: "#2F9E44", HR: "#FA5252", Sales: "#4DABF7",
    Support: "#ADB5BD", Product: "#F76707",
  };

  return (
    <div className={s.empCard}>
      <Avatar emp={emp} size={52} />
      <div className={s.empInfo}>
        <p className={s.empName}>{emp.name}</p>
        <p className={s.empTitle} style={{ color: deptColors[emp.dept] ?? "#6C757D" }}>
          {emp.title}
        </p>
        <div className={s.empMeta}>
          <span className={s.empDept}>{emp.dept}</span>
          <span className={s.empLocation}>{emp.location}</span>
        </div>
      </div>
      <div className={s.empActions}>
        <button className={s.empActionBtn} onClick={() => {}} aria-label={`Message ${emp.name}`}>
          Message
        </button>
        <button className={s.empActionBtn} onClick={() => {}} aria-label={`Schedule with ${emp.name}`}>
          Schedule
        </button>
      </div>
    </div>
  );
}

function EmployeeRow({ emp }) {
  const statusLabel = emp.status === "active" ? "Active" : emp.status === "leave" ? "On Leave" : "Inactive";
  const statusClass = emp.status === "active" ? s.badgeActive : emp.status === "leave" ? s.badgeLeave : s.badgeInactive;

  return (
    <tr className={s.tableRow}>
      <td className={s.td}>
        <div className={s.tableEmpCell}>
          <Avatar emp={emp} size={36} />
          <div>
            <p className={s.empName} style={{ fontSize: 13.5 }}>{emp.name}</p>
            <p className={s.empTitle} style={{ fontSize: 12, color: "#868E96" }}>{emp.title}</p>
          </div>
        </div>
      </td>
      <td className={s.td}><span className={s.tdText}>{emp.dept}</span></td>
      <td className={s.td}><span className={s.tdText}>{emp.location}</span></td>
      <td className={s.td}><span className={`${s.badge} ${statusClass}`}>{statusLabel}</span></td>
      <td className={s.td}>
        <div className={s.rowActionBtns}>
          <button className={s.empActionBtn} onClick={() => {}} aria-label={`Message ${emp.name}`}>Message</button>
          <button className={s.empActionBtn} onClick={() => {}} aria-label={`Schedule with ${emp.name}`}>Schedule</button>
        </div>
      </td>
    </tr>
  );
}

function SkeletonCard() {
  return (
    <div className={s.empCard}>
      <div className={s.skeletonCircle} style={{ width: 52, height: 52 }} />
      <div className={s.empInfo}>
        <div className={s.skeletonText} style={{ width: "70%" }} />
        <div className={s.skeletonText} style={{ width: "55%" }} />
        <div className={s.skeletonText} style={{ width: "45%", marginTop: 6 }} />
      </div>
    </div>
  );
}

function LeaveCard({ request, onAction, responding }) {
  const isApproving  = responding === "approving";
  const isDeclining  = responding === "declining";
  const isBusy       = isApproving || isDeclining;

  return (
    <div className={s.leaveCard}>
      <div className={s.leaveHeader}>
        <div className={s.leaveAvatar} style={{ background: request.color }}>
          {request.avatar}
        </div>
        <div className={s.leaveInfo}>
          <p className={s.leaveName}>{request.name}</p>
          <p className={s.leaveType}>{request.type} · {request.days} day{request.days !== 1 ? "s" : ""}</p>
        </div>
      </div>
      <p className={s.leaveDates}>{request.from} – {request.to}</p>
      <div className={s.leaveActions}>
        <button
          className={s.approveBtn}
          onClick={() => onAction(request.id, "approve")}
          disabled={isBusy}
          aria-label={`Approve leave for ${request.name}`}
        >
          {isApproving ? <span className={s.miniSpinner} /> : "+"} Approve
        </button>
        <button
          className={s.declineBtn}
          onClick={() => onAction(request.id, "decline")}
          disabled={isBusy}
          aria-label={`Decline leave for ${request.name}`}
        >
          {isDeclining ? <span className={s.miniSpinner} /> : "x"} Decline
        </button>
      </div>
    </div>
  );
}

function CapacityBar({ dept, pct, color }) {
  return (
    <div className={s.capRow}>
      <div className={s.capLabel}>
        <span className={s.capDept}>{dept.toUpperCase()}</span>
        <span className={s.capPct}>{pct}%</span>
      </div>
      <div className={s.capBarTrack}>
        <div
          className={s.capBarFill}
          style={{ width: `${pct}%`, background: color }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${dept} capacity: ${pct}%`}
        />
      </div>
    </div>
  );
}

const DEPT_OPTIONS = ["Engineering", "Design", "Marketing", "Finance", "HR", "Sales", "Support", "Product"];

function AddEmployeeModal({ onClose, onSubmit }) {
  const [form,      setForm]      = useState({ name: "", title: "", dept: "Engineering", location: "", email: "" });
  const [errors,    setErrors]    = useState({});
  const [loading,   setLoading]   = useState(false);
  const overlayRef = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const setField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => { const next = { ...prev }; delete next[field]; return next; });
  };

  const validate = () => {
    const errs = {};
    if (!form.name.trim())      errs.name      = "Name is required";
    if (!form.title.trim())     errs.title     = "Job title is required";
    if (!form.location.trim()) errs.location = "Location is required";
    if (!form.email.trim())     errs.email     = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(form.email)) errs.email = "Invalid email";
    return errs;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setLoading(true);
    const { error } = await onSubmit(form);
    if (error) setErrors({ _form: error });
    setLoading(false);
  };

  return (
    <div
      className={s.modalOverlay}
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Add new employee"
    >
      <div className={s.modal}>
        <div className={s.modalHeader}>
          <h2 className={s.modalTitle}>Add New Employee</h2>
          <button className={s.modalClose} onClick={onClose} aria-label="Close">x</button>
        </div>

        <div className={s.modalBody}>
          {errors._form && <p className={s.formError}>{errors._form}</p>}

          <div className={s.formGrid}>
            <div className={s.formGroup}>
              <label className={s.label}>Full Name *</label>
              <input className={`${s.input} ${errors.name ? s.inputError : ""}`}
                value={form.name} onChange={(e) => setField("name", e.target.value)}
                placeholder="e.g. Sarah Jenkins" />
              {errors.name && <p className={s.fieldError}>{errors.name}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Job Title *</label>
              <input className={`${s.input} ${errors.title ? s.inputError : ""}`}
                value={form.title} onChange={(e) => setField("title", e.target.value)}
                placeholder="e.g. Sr. Product Designer" />
              {errors.title && <p className={s.fieldError}>{errors.title}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Department *</label>
              <select className={s.input} value={form.dept} onChange={(e) => setField("dept", e.target.value)}>
                {DEPT_OPTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Location *</label>
              <input className={`${s.input} ${errors.location ? s.inputError : ""}`}
                value={form.location} onChange={(e) => setField("location", e.target.value)}
                placeholder="e.g. New York" />
              {errors.location && <p className={s.fieldError}>{errors.location}</p>}
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>Work Email *</label>
              <input type="email" className={`${s.input} ${errors.email ? s.inputError : ""}`}
                value={form.email} onChange={(e) => setField("email", e.target.value)}
                placeholder="e.g. sarah@synergy.com" />
              {errors.email && <p className={s.fieldError}>{errors.email}</p>}
            </div>
          </div>
        </div>

        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={loading}>
            {loading ? <><span className={s.miniSpinner} /> Adding...</> : "Add Employee"}
          </button>
        </div>
      </div>
    </div>
  );
}

const CAL_MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const CAL_DAYS   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
const LEAVE_COLORS = { "Sick Leave":"#FA5252", "Vacation":"#3B5BDB", "Personal Day":"#F59F00", "Maternity":"#845EF7", "Paternity":"#4DABF7" };
const getLeaveColor = (type) => LEAVE_COLORS[type] ?? "#868E96";

function parseLeaveDate(str, year) {
  const m = { Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11 };
  const [mon, day] = str.trim().split(" ");
  return new Date(year, m[mon], parseInt(day));
}

function buildLeaveMap(requests, year) {
  const map = {};
  requests.forEach((req) => {
    const from = parseLeaveDate(req.from, year);
    const to   = parseLeaveDate(req.to,   year);
    const cur  = new Date(from);
    while (cur <= to) {
      const key = `${cur.getFullYear()}-${cur.getMonth()}-${cur.getDate()}`;
      if (!map[key]) map[key] = [];
      map[key].push(req);
      cur.setDate(cur.getDate() + 1);
    }
  });
  return map;
}

function getMonthGrid(year, month) {
  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const grid = [];
  for (let i = 0; i < firstDay; i++) grid.push(null);
  for (let d = 1; d <= daysInMonth; d++) grid.push(d);
  return grid;
}

function AbsenceCalendar({ leaveRequests = [] }) {
  const today = new Date();
  const [year,      setYear]      = useState(today.getFullYear());
  const [month,     setMonth]     = useState(today.getMonth());
  const [selected, setSelected] = useState(null);

  const leaveMap  = useMemo(() => buildLeaveMap(leaveRequests, year), [leaveRequests, year]);
  const monthGrid = useMemo(() => getMonthGrid(year, month), [year, month]);

  const prevMonth = () => { if (month === 0) { setMonth(11); setYear(y => y-1); } else setMonth(m => m-1); };
  const nextMonth = () => { if (month === 11) { setMonth(0); setYear(y => y+1); } else setMonth(m => m+1); };

  const handleDay = (day) => {
    if (!day) return;
    const key  = `${year}-${month}-${day}`;
    const reqs = leaveMap[key] ?? [];
    setSelected(prev => prev?.day === day ? null : { day, requests: reqs });
  };

  const leaveTypes = [...new Set(leaveRequests.map(r => r.type))];

  return (
    <div className={s.calendarSection} id="absence-calendar" aria-label="Absence Calendar">
      <div className={s.calHeader}>
        <div>
          <h2 className={s.calTitle}>Absence Calendar</h2>
          <p className={s.calSub}>Track team leave and absences by date.</p>
        </div>
        {leaveTypes.length > 0 && (
          <div className={s.calLegend}>
            {leaveTypes.map(type => (
              <div key={type} className={s.calLegendItem}>
                <span className={s.calLegendDot} style={{ background: getLeaveColor(type) }} />
                <span className={s.calLegendLabel}>{type}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className={s.calMonthNav}>
        <button className={s.calNavBtn} onClick={prevMonth} aria-label="Previous month">&#8249;</button>
        <h3 className={s.calMonthTitle}>{CAL_MONTHS[month]} {year}</h3>
        <button className={s.calNavBtn} onClick={nextMonth} aria-label="Next month">&#8250;</button>
      </div>

      <div className={s.calGrid}>
        {CAL_DAYS.map(d => (
          <div key={d} className={s.calDayHeader}>{d}</div>
        ))}
        {monthGrid.map((day, i) => {
          if (!day) return <div key={`e-${i}`} className={s.calEmptyCell} />;
          const key      = `${year}-${month}-${day}`;
          const requests = leaveMap[key] ?? [];
          const isToday  = day === today.getDate() && month === today.getMonth() && year === today.getFullYear();
          const isSel    = selected?.day === day;
          return (
            <div
              key={key}
              className={`${s.calDayCell} ${isToday ? s.calDayCellToday : ""} ${isSel ? s.calDayCellSelected : ""} ${requests.length ? s.calDayCellHasLeave : ""}`}
              onClick={() => handleDay(day)}
              role="button" tabIndex={0}
              onKeyDown={e => e.key === "Enter" && handleDay(day)}
              aria-label={`${CAL_MONTHS[month]} ${day}${requests.length ? `, ${requests.length} on leave` : ""}`}
            >
              <span className={s.calDayNum}>{day}</span>
              <div className={s.calDots}>
                {requests.slice(0, 3).map((req, idx) => (
                  <span key={idx} className={s.calDot} style={{ background: getLeaveColor(req.type) }} title={`${req.name} — ${req.type}`} />
                ))}
                {requests.length > 3 && <span className={s.calDotMore}>+{requests.length - 3}</span>}
              </div>
            </div>
          );
        })}
      </div>

      {selected && (
        <div className={s.calSelectedPanel}>
          <div className={s.calSelectedHeader}>
            <h4 className={s.calSelectedTitle}>{CAL_MONTHS[month]} {selected.day}, {year}</h4>
            <button className={s.calSelectedClose} onClick={() => setSelected(null)} aria-label="Close">x</button>
          </div>
          {selected.requests.length === 0 ? (
            <p className={s.calSelectedEmpty}>No absences on this day</p>
          ) : (
            <div className={s.calSelectedList}>
              {selected.requests.map(req => (
                <div key={req.id} className={s.calSelectedItem}>
                  <div className={s.calSelectedAvatar} style={{ background: req.color }}>{req.avatar}</div>
                  <div>
                    <p className={s.calSelectedName}>{req.name}</p>
                    <p className={s.calSelectedType} style={{ color: getLeaveColor(req.type) }}>
                      {req.type} · {req.days} day{req.days !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <span className={s.calSelectedRange}>{req.from} – {req.to}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HRPage() {
  const [activeNav, setActiveNav] = useState("hr");
  const [showCalendar,    setShowCalendar]    = useState(false);
  const [showCompliance, setShowCompliance] = useState(false);
  const calendarRef = useRef(null);
  const navigate = useNavigate();

  const scrollToCalendar = () => {
    setShowCalendar(true);
    setTimeout(() => {
      calendarRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const {
    employees, leaveRequests, teamCapacity, statCards, departments,
    loadingEmployees, loadingStats, loadingSidebar, error,
    viewMode,       setViewMode,
    activeDept,     setActiveDept,
    activeStatus,   setActiveStatus,
    searchQuery,    setSearchQuery,
    showAddEmployee, setShowAddEmployee,
    leaveResponding,
    handleLeaveAction,
    handleAddEmployee,
    reload,
  } = useHRPage();

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#F8F9FA" }}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      <div style={{ marginLeft: 220, flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Header breadcrumbs={["Synergy ERP", "Human Resources", "Employee Directory"]} />

        <main className={s.page}>

          {error && (
            <div className={s.errorCard} role="alert">
              <span>{error}</span>
              <button className={s.btnOutline} onClick={reload}>Retry</button>
            </div>
          )}

          <div className={s.statGrid}>
            {loadingStats
              ? Array.from({ length: 4 }).map((_, i) => <StatCard key={i} loading />)
              /* التعديل هنا: إضافة icon="" لإخفاء الإيموجي من البطاقات */
              : statCards.map((c) => <StatCard key={c.id} {...c} icon="" />)
            }
          </div>

          <div className={s.contentLayout}>

            <section className={s.directorySection} aria-label="Employee directory">

              <div className={s.dirHeader}>
                <div>
                  <h2 className={s.dirTitle}>Employee Directory</h2>
                  <p className={s.dirSub}>Manage and track your global workforce.</p>
                </div>
                <div className={s.dirHeaderActions}>
                  <div className={s.viewToggle} role="group" aria-label="View mode">
                    <button
                      className={`${s.viewBtn} ${viewMode === "grid" ? s.viewBtnActive : ""}`}
                      onClick={() => setViewMode("grid")}
                      aria-label="Grid view" aria-pressed={viewMode === "grid"}
                    >
                      Grid
                    </button>
                    <button
                      className={`${s.viewBtn} ${viewMode === "list" ? s.viewBtnActive : ""}`}
                      onClick={() => setViewMode("list")}
                      aria-label="List view" aria-pressed={viewMode === "list"}
                    >
                      List
                    </button>
                  </div>

                  <button
                    className={s.btnPrimary}
                    onClick={() => setShowAddEmployee(true)}
                    aria-label="Add new employee"
                  >
                    + Add Employee
                  </button>
                </div>
              </div>

              <div className={s.filterBar}>
                <div className={s.searchWrap}>
                  <input
                    className={s.searchInput}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter by department, skills, location..."
                    aria-label="Search employees"
                  />
                </div>

                <div className={s.filterTabsScroll} role="tablist" aria-label="Filter by department">
                  {departments.map((dept) => (
                    <button
                      key={dept}
                      role="tab"
                      aria-selected={activeDept === dept}
                      className={`${s.filterTab} ${activeDept === dept ? s.filterTabActive : ""}`}
                      onClick={() => setActiveDept(dept)}
                    >
                      {dept}
                    </button>
                  ))}
                </div>

                <div className={s.filterTabs} role="group" aria-label="Filter by status">
                  {["All", "Active", "On Leave"].map((st) => (
                    <button
                      key={st}
                      className={`${s.filterTab} ${activeStatus === st ? s.filterTabActive : ""}`}
                      onClick={() => setActiveStatus(st)}
                      aria-pressed={activeStatus === st}
                    >
                      Status{st !== "All" ? `: ${st}` : ""}
                    </button>
                  ))}
                </div>
              </div>

              {!loadingEmployees && (
                <p className={s.empCount}>
                  Showing <strong>{employees.length}</strong> employee{employees.length !== 1 ? "s" : ""}
                  {activeDept !== "All Departments" ? ` in ${activeDept}` : ""}
                </p>
              )}

              {viewMode === "grid" && (
                <div className={s.empGrid}>
                  {loadingEmployees
                    ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
                    : employees.length === 0
                      ? (
                        <div className={s.emptyState}>
                          <p className={s.emptyTitle}>No employees found</p>
                          <p className={s.emptySub}>Try adjusting your filters or search query.</p>
                        </div>
                      )
                      : employees.map((emp) => <EmployeeCard key={emp.id} emp={emp} />)
                  }
                </div>
              )}

              {viewMode === "list" && (
                <div className={s.tableWrap}>
                  <table className={s.table} aria-label="Employee list">
                    <thead className={s.thead}>
                      <tr>
                        <th className={s.th}>Employee</th>
                        <th className={s.th}>Department</th>
                        <th className={s.th}>Location</th>
                        <th className={s.th}>Status</th>
                        <th className={s.th}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadingEmployees
                        ? Array.from({ length: 5 }).map((_, i) => (
                          <tr key={i} className={s.tableRow}>
                            {Array.from({ length: 5 }).map((_, j) => (
                              <td key={j} className={s.td}>
                                <div className={s.skeletonText} style={{ width: ["160px","80px","90px","70px","120px"][j] }} />
                              </td>
                            ))}
                          </tr>
                        ))
                        : employees.map((emp) => <EmployeeRow key={emp.id} emp={emp} />)
                      }
                    </tbody>
                  </table>
                </div>
              )}

            </section>

            <aside className={s.sidebarPanel}>

              {/* ── Smart HR Operations Center ── */}
              <SmartHRPanel employees={employees} />

              <div className={s.sideCard}>
                <div className={s.sideCardHeader}>
                  <h3 className={s.sideCardTitle}>Leave Requests</h3>
                  {!loadingSidebar && leaveRequests.length > 0 && (
                    <span className={s.pendingBadge}>{leaveRequests.length} Pending</span>
                  )}
                </div>

                {loadingSidebar ? (
                  Array.from({ length: 2 }).map((_, i) => (
                    <div key={i} className={s.leaveCard}>
                      <div className={s.skeletonText} style={{ width: "60%", height: 14 }} />
                      <div className={s.skeletonText} style={{ width: "40%", marginTop: 8 }} />
                    </div>
                  ))
                ) : leaveRequests.length === 0 ? (
                  <p className={s.emptyNote}>No pending leave requests</p>
                ) : (
                  leaveRequests.map((req) => (
                    <LeaveCard
                      key={req.id}
                      request={req}
                      onAction={handleLeaveAction}
                      responding={leaveResponding[req.id]}
                    />
                  ))
                )}

                <button
                  className={s.sideCardLink}
                  onClick={scrollToCalendar}
                  aria-label="View absence calendar"
                >
                  View Absence Calendar
                </button>
              </div>

              {/* <div className={s.sideCard}>
                <div className={s.sideCardHeader}>
                  <div>
                    <h3 className={s.sideCardTitle}>Team Capacity</h3>
                    <p className={s.sideCardSub}>Weekly resource utilization</p>
                  </div>
                </div>

                {loadingSidebar ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className={s.capRow}>
                      <div className={s.skeletonText} style={{ width: "100%", height: 10 }} />
                    </div>
                  ))
                ) : (
                  teamCapacity.map((tc) => (
                    <CapacityBar key={tc.dept} dept={tc.dept} pct={tc.pct} color={tc.color} />
                  ))
                )}

                <button
                  className={s.btnFullOutline}
                  onClick={() => {}}
                  aria-label="View resource report"
                >
                  View Resource Report
                </button>
              </div> */}

              <div className={s.quickActions}>
                <button
                  className={s.quickActionBtn}
                  onClick={() => navigate("/finance")}
                  aria-label="Run Payroll"
                >
                  <span className={s.qaLabel}>Run Payroll</span>
                </button>
                <button
                  className={s.quickActionBtn}
                  onClick={() => setShowCompliance(true)}
                  aria-label="Compliance"
                >
                  <span className={s.qaLabel}>Compliance</span>
                </button>
              </div>

            </aside>
          </div>

          {showCalendar && (
            <div ref={calendarRef} style={{ scrollMarginTop: 24 }}>
              <AbsenceCalendar leaveRequests={leaveRequests} />
            </div>
          )}

        </main>
      </div>

      {showAddEmployee && (
        <AddEmployeeModal
          onClose={() => setShowAddEmployee(false)}
          onSubmit={handleAddEmployee}
        />
      )}

      <ComplianceModal
        isOpen={showCompliance}
        onClose={() => setShowCompliance(false)}
      />

    </div>
  );
}