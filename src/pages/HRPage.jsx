// ─── Pages/HRPage.jsx ────────────────────────────────────────────────────────
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import useHRPage from "../hooks/useHRPage";
import ComplianceModal from "../components/HR/ComplianceModal";
import SmartHRPanel    from "../components/HR/SmartHRPanel";
import s from "../styles/HRPage.module.css";
import shell from "../styles/AppShell.module.css";
import {
  AlertTriangle,
  Banknote,
  Building2,
  CalendarCheck,
  CalendarX,
  CheckCircle2,
  Clock3,
  FileText,
  FolderOpen,
  PencilLine,
  Search,
  Trash2,
  TrendingUp,
  UserPlus,
  Users,
  X,
} from "lucide-react";

const STAT_ICONS = {
  workforce: Users,
  active: CheckCircle2,
  activeEmployees: CheckCircle2,
  departments: Building2,
  teams: Building2,
  attendance: CalendarCheck,
  payroll: Banknote,
  salary: Banknote,
  recruiting: UserPlus,
  hiring: UserPlus,
  performance: TrendingUp,
  leave: CalendarX,
  timeOff: Clock3,
  documents: FileText,
  warnings: AlertTriangle,
  retention: TrendingUp,
};

function StatCard({ id, label, value, change, changeType, loading }) {
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
  const Icon = STAT_ICONS[id] ?? Users;
  const isFeatured = id === "workforce";

  return (
    <div className={s.statCard}>
      <div className={s.statCardHeader}>
        <div
          className={`${s.statIconBadge} ${isFeatured ? s.statIconBadgeActive : s.statIconBadgeNeutral}`}
          aria-hidden="true"
        >
          <Icon className={s.statIconSvg} strokeWidth={2.2} />
        </div>
        <p className={s.statLabel}>{label}</p>
      </div>
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

function EmployeeCard({ emp, onEdit, onDelete }) {
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
        {emp.employeeId ? <p className={s.empTitle} style={{ color: "#868E96", fontWeight: 600 }}>{emp.employeeId}</p> : null}
        <p className={s.empTitle} style={{ color: deptColors[emp.dept] ?? "#6C757D" }}>
          {emp.title}
        </p>
        <div className={s.empMeta}>
          <span className={s.empDept}>{emp.dept}</span>
          <span className={s.empLocation}>{emp.location}</span>
        </div>
      </div>
      <div className={s.empActions}>
        <button className={s.empActionBtn} onClick={() => onEdit(emp)} aria-label={`Edit ${emp.name}`}>
          Edit
        </button>
        <button className={s.empActionBtn} onClick={() => onDelete(emp)} aria-label={`Delete ${emp.name}`}>
          Delete
        </button>
      </div>
    </div>
  );
}

function EmployeeRow({ emp, onEdit, onDelete }) {
  const statusLabel = emp.status === "active" ? "Active" : emp.status === "leave" ? "On Leave" : "Inactive";
  const statusClass = emp.status === "active" ? s.badgeActive : emp.status === "leave" ? s.badgeLeave : s.badgeInactive;

  return (
    <tr className={s.tableRow}>
      <td className={s.td}>
        <div className={s.tableEmpCell}>
          <Avatar emp={emp} size={36} />
          <div>
            <p className={s.empName} style={{ fontSize: 13.5 }}>{emp.name}</p>
            {emp.employeeId ? <p className={s.empTitle} style={{ fontSize: 12, color: "#868E96" }}>{emp.employeeId}</p> : null}
            <p className={s.empTitle} style={{ fontSize: 12, color: "#868E96" }}>{emp.title}</p>
          </div>
        </div>
      </td>
      <td className={s.td}><span className={s.tdText}>{emp.dept}</span></td>
      <td className={s.td}><span className={s.tdText}>{emp.location}</span></td>
      <td className={s.td}><span className={`${s.badge} ${statusClass}`}>{statusLabel}</span></td>
      <td className={s.td}>
        <div className={s.rowActionBtns}>
          <button className={s.empActionBtn} onClick={() => onEdit(emp)} aria-label={`Edit ${emp.name}`}>Edit</button>
          <button className={s.empActionBtn} onClick={() => onDelete(emp)} aria-label={`Delete ${emp.name}`}>Delete</button>
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

function LeaveCard({ request, onEdit, onDelete, responding }) {
  const isBusy = Boolean(responding);

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
          onClick={() => onEdit(request)}
          disabled={isBusy}
          aria-label={`Edit leave for ${request.name}`}
        >
          {isBusy ? <span className={s.miniSpinner} /> : <PencilLine className={s.btnIcon} aria-hidden="true" />}
          Edit
        </button>
        <button
          className={s.declineBtn}
          onClick={() => onDelete(request)}
          disabled={isBusy}
          aria-label={`Delete leave for ${request.name}`}
        >
          {isBusy ? <span className={s.miniSpinner} /> : <Trash2 className={s.btnIcon} aria-hidden="true" />}
          Delete
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

function AddLeaveRequestModal({ onClose, onSubmit, employees = [], initialEmployee = null, initialLeaveRequest = null, submitLabel = "Submit Leave Request", title = "New Leave Request" }) {
  const isEditing = Boolean(initialLeaveRequest);
  const initialForm = {
    employeeId: initialEmployee?.employeeId || initialLeaveRequest?.employeeId || "",
    fullName: initialEmployee?.fullName || initialEmployee?.name || initialLeaveRequest?.fullName || "",
    leaveType: initialLeaveRequest?.type || initialLeaveRequest?.leaveType || "Annual Leave",
    leaveBalance: initialLeaveRequest?.balance ?? initialLeaveRequest?.leaveBalance ?? "",
    leaveStartDate: initialLeaveRequest?.startDate || initialLeaveRequest?.leaveStartDate ? (initialLeaveRequest?.startDate || initialLeaveRequest?.leaveStartDate).slice(0, 10) : "",
    leaveEndDate: initialLeaveRequest?.endDate || initialLeaveRequest?.leaveEndDate ? (initialLeaveRequest?.endDate || initialLeaveRequest?.leaveEndDate).slice(0, 10) : "",
    reason: initialLeaveRequest?.reason || "",
  };

  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [employeeQuery, setEmployeeQuery] = useState(initialEmployee?.fullName || initialEmployee?.name || initialLeaveRequest?.fullName || "");
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const overlayRef = useRef(null);
  const autocompleteRef = useRef(null);

  const normalizeText = (value = "") => String(value || "").trim().toLowerCase();

  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    const nextName = initialEmployee?.fullName || initialEmployee?.name || initialLeaveRequest?.fullName || "";
    setForm({
      employeeId: initialEmployee?.employeeId || initialLeaveRequest?.employeeId || "",
      fullName: nextName,
      leaveType: initialLeaveRequest?.type || initialLeaveRequest?.leaveType || "Annual Leave",
      leaveBalance: initialLeaveRequest?.balance ?? initialLeaveRequest?.leaveBalance ?? "",
      leaveStartDate: initialLeaveRequest?.startDate || initialLeaveRequest?.leaveStartDate ? (initialLeaveRequest?.startDate || initialLeaveRequest?.leaveStartDate).slice(0, 10) : "",
      leaveEndDate: initialLeaveRequest?.endDate || initialLeaveRequest?.leaveEndDate ? (initialLeaveRequest?.endDate || initialLeaveRequest?.leaveEndDate).slice(0, 10) : "",
      reason: initialLeaveRequest?.reason || "",
    });
    setEmployeeQuery(nextName);
    setSelectedEmployee(null);
    setShowSuggestions(false);
    setHighlightedIndex(-1);
  }, [initialEmployee, initialLeaveRequest]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target)) {
        setShowSuggestions(false);
        setHighlightedIndex(-1);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const setField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => { const next = { ...prev }; delete next[field]; return next; });
  };

  const filteredSuggestions = useMemo(() => {
    if (isEditing || selectedEmployee) return [];
    const query = normalizeText(employeeQuery);
    if (query.length < 2) return [];

    return employees
      .filter((employee) => {
        const name = normalizeText(employee.fullName || employee.name || "");
        const id = normalizeText(employee.employeeId || "");
        return name.includes(query) || id.includes(query);
      })
      .slice(0, 6);
  }, [employees, employeeQuery, selectedEmployee, isEditing]);

  const handleEmployeeInputChange = (value) => {
    setEmployeeQuery(value);
    setErrors((prev) => ({ ...prev, employeeId: undefined, fullName: undefined }));

    if (selectedEmployee && value !== (selectedEmployee.fullName || selectedEmployee.name || "")) {
      setSelectedEmployee(null);
      setForm((prev) => ({ ...prev, fullName: "", employeeId: "", leaveBalance: "" }));
    }

    setShowSuggestions(value.trim().length >= 2);
    setHighlightedIndex(-1);
  };

  const selectEmployee = (employee) => {
    const name = employee.fullName || employee.name || "";
    setSelectedEmployee(employee);
    setEmployeeQuery(name);
    setForm((prev) => ({
      ...prev,
      fullName: name,
      employeeId: employee.employeeId || "",
      leaveBalance: employee.leaveBalance ?? employee.leave_balance ?? prev.leaveBalance,
    }));
    setShowSuggestions(false);
    setHighlightedIndex(-1);
    setErrors((prev) => ({ ...prev, employeeId: undefined, fullName: undefined }));
  };

  const handleEmployeeKeyDown = (event) => {
    if (isEditing) return;

    if (!showSuggestions || filteredSuggestions.length === 0) {
      if (event.key === "Escape") {
        event.preventDefault();
        setShowSuggestions(false);
        setHighlightedIndex(-1);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % filteredSuggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev <= 0 ? filteredSuggestions.length - 1 : prev - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (highlightedIndex >= 0) {
        selectEmployee(filteredSuggestions[highlightedIndex]);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      setShowSuggestions(false);
      setHighlightedIndex(-1);
    }
  };

  const validate = () => {
    const errs = {};
    const query = employeeQuery.trim();
    if (!query) {
      errs.employeeId = "Employee is required";
      return { errs, matchedEmployee: null };
    }

    const matchedEmployee = employees.find((employee) => {
      const name = normalizeText(employee.fullName || employee.name || "");
      const id = normalizeText(employee.employeeId || "");
      return name === normalizeText(query) || id === normalizeText(query);
    });

    if (!matchedEmployee) {
      errs.employeeId = "Please select an existing employee";
      return { errs, matchedEmployee: null };
    }

    setSelectedEmployee(matchedEmployee);
    setEmployeeQuery(matchedEmployee.fullName || matchedEmployee.name || query);
    setForm((prev) => ({
      ...prev,
      fullName: matchedEmployee.fullName || matchedEmployee.name || prev.fullName,
      employeeId: matchedEmployee.employeeId || prev.employeeId,
      leaveBalance: matchedEmployee.leaveBalance ?? matchedEmployee.leave_balance ?? prev.leaveBalance,
    }));

    if (!form.fullName.trim()) errs.fullName = "Employee name is required";
    if (!form.leaveType) errs.leaveType = "Leave type is required";
    if (form.leaveBalance === "" || Number(form.leaveBalance) < 0) errs.leaveBalance = "Leave balance is required";
    if (!form.leaveStartDate) errs.leaveStartDate = "Start date is required";
    if (!form.leaveEndDate) errs.leaveEndDate = "End date is required";
    if (form.leaveEndDate && form.leaveStartDate && new Date(form.leaveEndDate) < new Date(form.leaveStartDate)) {
      errs.leaveEndDate = "End date cannot be earlier than start date";
    }
    if (!form.reason.trim()) errs.reason = "Reason is required";
    return { errs, matchedEmployee };
  };

  const handleSubmit = async () => {
    const { errs, matchedEmployee } = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setLoading(true);
    const payload = {
      fullName: matchedEmployee ? (matchedEmployee.fullName || matchedEmployee.name || form.fullName.trim()) : form.fullName.trim(),
      employeeId: matchedEmployee ? (matchedEmployee.employeeId || form.employeeId.trim()) : form.employeeId.trim(),
      leaveType: form.leaveType,
      leaveBalance: Number(matchedEmployee?.leaveBalance ?? matchedEmployee?.leave_balance ?? form.leaveBalance),
      leaveStartDate: form.leaveStartDate,
      leaveEndDate: form.leaveEndDate,
      reason: form.reason.trim(),
    };

    const { error } = await onSubmit(payload);
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
      aria-label="Leave request"
    >
      <div className={s.modal}>
        <div className={s.modalHeader}>
          <h2 className={s.modalTitle}>{title}</h2>
          <button className={s.modalClose} onClick={onClose} aria-label="Close">
            <X className={s.btnIcon} aria-hidden="true" />
          </button>
        </div>

        <div className={s.modalBody}>
          {errors._form && <p className={s.formError}>{errors._form}</p>}
          <div className={s.formGrid}>
            <div className={s.formGroup}>
              <label className={s.label}>Employee</label>
              {isEditing ? (
                <input className={s.input} value={form.fullName} readOnly aria-readonly="true" />
              ) : (
                <div className={s.autocompleteWrap} ref={autocompleteRef}>
                  <input
                    className={`${s.input} ${errors.employeeId ? s.inputError : ""}`}
                    value={employeeQuery}
                    onChange={(e) => handleEmployeeInputChange(e.target.value)}
                    onFocus={() => setShowSuggestions(employeeQuery.trim().length >= 2)}
                    onKeyDown={handleEmployeeKeyDown}
                    placeholder="Type employee name"
                    autoComplete="off"
                  />
                  {showSuggestions && filteredSuggestions.length > 0 && (
                    <ul className={s.autocompleteList} role="listbox">
                      {filteredSuggestions.map((employee, index) => (
                        <li
                          key={employee.id || employee._id}
                          className={`${s.autocompleteItem} ${index === highlightedIndex ? s.autocompleteItemActive : ""}`}
                          role="option"
                          aria-selected={index === highlightedIndex}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            selectEmployee(employee);
                          }}
                        >
                          {employee.fullName || employee.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {errors.employeeId && <p className={s.fieldError}>{errors.employeeId}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Employee ID</label>
              {isEditing ? (
                <input className={s.input} value={form.employeeId} readOnly aria-readonly="true" />
              ) : (
                <input className={s.input} value={form.employeeId} readOnly aria-readonly="true" placeholder="Select an employee" />
              )}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Leave Type</label>
              <select className={s.input} value={form.leaveType} onChange={(e) => setField("leaveType", e.target.value)}>
                <option value="Annual Leave">Annual Leave</option>
                <option value="Sick Leave">Sick Leave</option>
                <option value="Emergency Leave">Emergency Leave</option>
                <option value="Unpaid Leave">Unpaid Leave</option>
                <option value="Maternity Leave">Maternity Leave</option>
                <option value="Paternity Leave">Paternity Leave</option>
                <option value="Other">Other</option>
              </select>
              {errors.leaveType && <p className={s.fieldError}>{errors.leaveType}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Leave Balance</label>
              <input type="number" min="0" className={`${s.input} ${errors.leaveBalance ? s.inputError : ""}`} value={form.leaveBalance} onChange={(e) => setField("leaveBalance", e.target.value)} placeholder="Balance" />
              {errors.leaveBalance && <p className={s.fieldError}>{errors.leaveBalance}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Start Date</label>
              <input type="date" className={`${s.input} ${errors.leaveStartDate ? s.inputError : ""}`} value={form.leaveStartDate} onChange={(e) => setField("leaveStartDate", e.target.value)} />
              {errors.leaveStartDate && <p className={s.fieldError}>{errors.leaveStartDate}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>End Date</label>
              <input type="date" className={`${s.input} ${errors.leaveEndDate ? s.inputError : ""}`} value={form.leaveEndDate} onChange={(e) => setField("leaveEndDate", e.target.value)} />
              {errors.leaveEndDate && <p className={s.fieldError}>{errors.leaveEndDate}</p>}
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>Reason</label>
              <textarea className={`${s.input} ${errors.reason ? s.inputError : ""}`} rows="3" value={form.reason} onChange={(e) => setField("reason", e.target.value)} placeholder="Briefly describe the leave request" />
              {errors.reason && <p className={s.fieldError}>{errors.reason}</p>}
            </div>
          </div>
        </div>

        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={loading}>
            {loading ? <><span className={s.miniSpinner} /> {isEditing ? "Updating..." : "Submitting..."}</> : submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function AddEmployeeModal({ onClose, onSubmit, initialEmployee = null, submitLabel = "Add Employee", title = "Add New Employee" }) {
  const initialForm = {
    name: "",
    employeeId: "",
    title: "",
    dept: "Engineering",
    location: "",
    email: "",
    salary: "",
    phoneNumber: "",
    startDate: "",
    dateOfBirth: "",
    gender: "",
  };

  const [form, setForm] = useState(() => {
    if (!initialEmployee) return initialForm;
    return {
      name: initialEmployee.fullName || initialEmployee.name || "",
      employeeId: initialEmployee.employeeId || "",
      title: initialEmployee.jobTitle || initialEmployee.title || "",
      dept: initialEmployee.department || initialEmployee.dept || "Engineering",
      location: initialEmployee.location || "",
      email: initialEmployee.workEmail || initialEmployee.email || "",
      salary: initialEmployee.salary ?? "",
      phoneNumber: initialEmployee.phoneNumber || "",
      startDate: initialEmployee.startDate ? initialEmployee.startDate.slice(0, 10) : "",
      dateOfBirth: initialEmployee.dateOfBirth ? initialEmployee.dateOfBirth.slice(0, 10) : "",
      gender: initialEmployee.gender || "",
    };
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!initialEmployee) {
      setForm(initialForm);
      return;
    }
    setForm({
      name: initialEmployee.fullName || initialEmployee.name || "",
      employeeId: initialEmployee.employeeId || "",
      title: initialEmployee.jobTitle || initialEmployee.title || "",
      dept: initialEmployee.department || initialEmployee.dept || "Engineering",
      location: initialEmployee.location || "",
      email: initialEmployee.workEmail || initialEmployee.email || "",
      salary: initialEmployee.salary ?? "",
      phoneNumber: initialEmployee.phoneNumber || "",
      startDate: initialEmployee.startDate ? initialEmployee.startDate.slice(0, 10) : "",
      dateOfBirth: initialEmployee.dateOfBirth ? initialEmployee.dateOfBirth.slice(0, 10) : "",
      gender: initialEmployee.gender || "",
    });
  }, [initialEmployee]);

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
    if (!form.name.trim()) errs.name = "Name is required";
    if (!form.employeeId.trim()) errs.employeeId = "Employee ID is required";
    else if (form.employeeId.trim().length > 30) errs.employeeId = "Employee ID must be at most 30 characters";
    if (!form.title.trim()) errs.title = "Job title is required";
    if (!form.location.trim()) errs.location = "Location is required";
    if (!form.email.trim()) errs.email = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(form.email)) errs.email = "Invalid email";
    if (form.salary === "" || form.salary === null) errs.salary = "Salary is required";
    else if (Number(form.salary) < 0) errs.salary = "Salary must be greater than or equal to 0";
    if (!form.phoneNumber.trim()) errs.phoneNumber = "Phone number is required";
    else if (!/^\+?[0-9\s()-]{7,15}$/.test(form.phoneNumber)) errs.phoneNumber = "Invalid phone number";
    if (!form.startDate) errs.startDate = "Start date is required";
    if (!form.dateOfBirth) errs.dateOfBirth = "Date of birth is required";
    if (!form.gender) errs.gender = "Gender is required";
    return errs;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setLoading(true);
    const payload = {
      fullName: form.name.trim(),
      employeeId: form.employeeId.trim(),
      jobTitle: form.title.trim(),
      department: form.dept,
      location: form.location.trim(),
      workEmail: form.email.trim(),
      salary: Number(form.salary),
      phoneNumber: form.phoneNumber.trim(),
      startDate: form.startDate,
      dateOfBirth: form.dateOfBirth,
      gender: form.gender,
    };
    const { error } = await onSubmit(payload);
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
          <h2 className={s.modalTitle}>{title}</h2>
          <button className={s.modalClose} onClick={onClose} aria-label="Close">
            <X className={s.btnIcon} aria-hidden="true" />
          </button>
        </div>

        <div className={s.modalBody}>
          {errors._form && <p className={s.formError}>{errors._form}</p>}

          <div className={s.formGrid}>
            <div className={s.formGroup}>
              <label className={s.label}>Full Name</label>
              <input className={`${s.input} ${errors.name ? s.inputError : ""}`}
                value={form.name} onChange={(e) => setField("name", e.target.value)}
                placeholder="Full Name" />
              {errors.name && <p className={s.fieldError}>{errors.name}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Employee ID</label>
              <input className={`${s.input} ${errors.employeeId ? s.inputError : ""}`}
                value={form.employeeId} onChange={(e) => setField("employeeId", e.target.value)}
                placeholder="Personal ID" />
              {errors.employeeId && <p className={s.fieldError}>{errors.employeeId}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Job Title</label>
              <input className={`${s.input} ${errors.title ? s.inputError : ""}`}
                value={form.title} onChange={(e) => setField("title", e.target.value)}
                placeholder="Job Title" />
              {errors.title && <p className={s.fieldError}>{errors.title}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Department</label>
              <select className={s.input} value={form.dept} onChange={(e) => setField("dept", e.target.value)}>
                {DEPT_OPTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Location</label>
              <input className={`${s.input} ${errors.location ? s.inputError : ""}`}
                value={form.location} onChange={(e) => setField("location", e.target.value)}
                placeholder="Location" />
              {errors.location && <p className={s.fieldError}>{errors.location}</p>}
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.label}>Work Email *</label>
              <input type="email" className={`${s.input} ${errors.email ? s.inputError : ""}`}
                value={form.email} onChange={(e) => setField("email", e.target.value)}
                placeholder="Email" />
              {errors.email && <p className={s.fieldError}>{errors.email}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Salary</label>
              <input type="number" min="0" className={`${s.input} ${errors.salary ? s.inputError : ""}`}
                value={form.salary} onChange={(e) => setField("salary", e.target.value)}
                placeholder="EG" />
              {errors.salary && <p className={s.fieldError}>{errors.salary}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Phone Number</label>
              <input type="tel" className={`${s.input} ${errors.phoneNumber ? s.inputError : ""}`}
                value={form.phoneNumber} onChange={(e) => setField("phoneNumber", e.target.value)}
                placeholder="+20 " />
              {errors.phoneNumber && <p className={s.fieldError}>{errors.phoneNumber}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Start Date</label>
              <input type="date" className={`${s.input} ${errors.startDate ? s.inputError : ""}`}
                value={form.startDate} onChange={(e) => setField("startDate", e.target.value)} />
              {errors.startDate && <p className={s.fieldError}>{errors.startDate}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Date of Birth</label>
              <input type="date" className={`${s.input} ${errors.dateOfBirth ? s.inputError : ""}`}
                value={form.dateOfBirth} onChange={(e) => setField("dateOfBirth", e.target.value)} />
              {errors.dateOfBirth && <p className={s.fieldError}>{errors.dateOfBirth}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.label}>Gender</label>
              <select className={`${s.input} ${errors.gender ? s.inputError : ""}`} value={form.gender} onChange={(e) => setField("gender", e.target.value)}>
                <option value="">Select gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
              {errors.gender && <p className={s.fieldError}>{errors.gender}</p>}
            </div>
          </div>
        </div>

        <div className={s.modalFooter}>
          <button className={s.btnGhost} onClick={onClose}>Cancel</button>
          <button className={s.btnPrimary} onClick={handleSubmit} disabled={loading}>
            {loading ? <><span className={s.miniSpinner} /> {submitLabel === "Update Employee" ? "Updating..." : "Adding..."}</> : submitLabel}
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
  const [year,     setYear]     = useState(today.getFullYear());
  const [month,    setMonth]    = useState(today.getMonth());
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
            <button className={s.calSelectedClose} onClick={() => setSelected(null)} aria-label="Close">
              <X className={s.btnIcon} aria-hidden="true" />
            </button>
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
  const [showCompliance, setShowCompliance] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [employeeNotice, setEmployeeNotice] = useState("");
  const [showLeaveRequestModal, setShowLeaveRequestModal] = useState(false);
  const [editingLeaveRequest, setEditingLeaveRequest] = useState(null);
  const navigate = useNavigate();

  const {
    employees, allEmployees, leaveRequests, teamCapacity, statCards, departments,
    loadingEmployees, loadingStats, loadingSidebar, error,
    viewMode,      setViewMode,
    activeDept,    setActiveDept,
    activeStatus,  setActiveStatus,
    searchQuery,   setSearchQuery,
    showAddEmployee, setShowAddEmployee,
    leaveResponding,
    handleLeaveAction,
    handleAddEmployee,
    handleUpdateEmployee,
    handleDeleteEmployee,
    handleAddLeaveRequest,
    handleUpdateLeaveRequest,
    handleDeleteLeaveRequest,
    reload,
  } = useHRPage();

  const openEmployeeModal = () => {
    setEditingEmployee(null);
    setEmployeeNotice("");
    setShowAddEmployee(true);
  };

  const handleEmployeeSubmit = async (payload) => {
    if (editingEmployee) {
      const result = await handleUpdateEmployee(editingEmployee.id || editingEmployee._id, payload);
      if (!result.error) {
        setEmployeeNotice("Employee updated successfully");
        setEditingEmployee(null);
        setShowAddEmployee(false);
        return { error: null };
      }
      return result;
    }

    const result = await handleAddEmployee(payload);
    if (!result.error) {
      setEmployeeNotice("Employee created successfully");
      setShowAddEmployee(false);
      return { error: null };
    }
    return result;
  };

  const handleEmployeeDelete = async (emp) => {
    const confirmed = window.confirm(`Delete ${emp.name || emp.fullName}?`);
    if (!confirmed) return;
    const result = await handleDeleteEmployee(emp.id || emp._id);
    if (!result.error) {
      setEmployeeNotice("Employee deleted successfully");
    } else {
      setEmployeeNotice(result.error);
    }
  };

  const handleLeaveRequestSubmit = async (payload, leaveRequest = null) => {
    const employee = allEmployees.find((item) => item.employeeId === payload.employeeId);
    if (!employee) {
      return { error: "Please select a valid employee" };
    }

    if (leaveRequest) {
      const result = await handleUpdateLeaveRequest(employee.id || employee._id, leaveRequest.id || leaveRequest._id, payload);
      if (!result.error) {
        setEmployeeNotice("Leave request updated successfully");
        setEditingLeaveRequest(null);
        setShowLeaveRequestModal(false);
        return { error: null };
      }
      return result;
    }

    const result = await handleAddLeaveRequest(employee.id || employee._id, payload);
    if (!result.error) {
      setEmployeeNotice("Leave request submitted successfully");
      setShowLeaveRequestModal(false);
      return { error: null };
    }
    return result;
  };

  const handleLeaveRequestEdit = (request) => {
    setEditingLeaveRequest(request);
    setShowLeaveRequestModal(true);
  };

  const handleLeaveRequestDelete = async (request) => {
    const confirmed = window.confirm(`Delete leave request for ${request.name || request.fullName}?`);
    if (!confirmed) return;

    const employee = allEmployees.find((item) => item.employeeId === request.employeeId);
    if (!employee) {
      setEmployeeNotice("Unable to find the selected leave request");
      return;
    }

    const result = await handleDeleteLeaveRequest(employee.id || employee._id, request.id || request._id);
    if (!result.error) {
      setEmployeeNotice("Leave request deleted successfully");
    } else {
      setEmployeeNotice(result.error);
    }
  };

  useEffect(() => {
    if (!employeeNotice) return;
    const timeout = window.setTimeout(() => setEmployeeNotice(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [employeeNotice]);

  return (
    <div className={shell.appShell}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      <div className={shell.mainArea}>
        <Header breadcrumbs={["Prime ERP", "Human Resources", "Employee Directory"]} />

        <main className={s.page}>

          {employeeNotice && (
            <div className={s.errorCard} role="status" style={{ background: "#ECFDF3", borderColor: "#A7F3D0", color: "#0F766E" }}>
              <span>{employeeNotice}</span>
            </div>
          )}

          {error && (
            <div className={s.errorCard} role="alert">
              <AlertTriangle className={s.btnIcon} aria-hidden="true" />
              <span>{error}</span>
              <button className={s.btnOutline} onClick={reload}>Retry</button>
            </div>
          )}

          <div className={s.statGrid}>
            {loadingStats
              ? Array.from({ length: 4 }).map((_, i) => <StatCard key={i} loading />)
              : statCards.map((c) => <StatCard key={c.id} {...c} />)
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
                    onClick={openEmployeeModal}
                    aria-label="Add new employee"
                  >
                    <UserPlus className={s.btnIcon} aria-hidden="true" />
                    Add Employee
                  </button>
                  <button
                    className={s.btnOutline}
                    onClick={() => {
                      setEditingLeaveRequest(null);
                      setShowLeaveRequestModal(true);
                    }}
                    aria-label="Create leave request"
                  >
                    <CalendarCheck className={s.btnIcon} aria-hidden="true" />
                    Leave Request
                  </button>
                </div>
              </div>

              <div className={s.filterBar}>
                <div className={s.searchWrap}>
                  <Search className={s.searchIcon} aria-hidden="true" />
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
                          <FolderOpen className={s.emptyIcon} aria-hidden="true" />
                          <p className={s.emptyTitle}>No employees found</p>
                          <p className={s.emptySub}>Try adjusting your filters or search query.</p>
                        </div>
                      )
                      : employees.map((emp) => <EmployeeCard key={emp.id || emp._id} emp={emp} onEdit={(selected) => { setEditingEmployee(selected); setEmployeeNotice(""); setShowAddEmployee(true); }} onDelete={handleEmployeeDelete} />)
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
                        : employees.map((emp) => <EmployeeRow key={emp.id || emp._id} emp={emp} onEdit={(selected) => { setEditingEmployee(selected); setEmployeeNotice(""); setShowAddEmployee(true); }} onDelete={handleEmployeeDelete} />)
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
                      onEdit={handleLeaveRequestEdit}
                      onDelete={handleLeaveRequestDelete}
                      responding={leaveResponding[req.id]}
                    />
                  ))
                )}

              </div>

              <div className={s.sideCard}>
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
                  teamCapacity.length > 0 ? (
                    <>
                      <CapacityBar dept={teamCapacity[0].dept} pct={teamCapacity[0].pct} color={teamCapacity[0].color} />
                      <div className={s.capSummary}>
                        <div className={s.capSummaryItem}>
                          <span className={s.capSummaryLabel}>Total</span>
                          <strong>{teamCapacity[0].totalEmployees ?? 0}</strong>
                        </div>
                        <div className={s.capSummaryItem}>
                          <span className={s.capSummaryLabel}>On Leave</span>
                          <strong>{teamCapacity[0].onLeaveEmployees ?? 0}</strong>
                        </div>
                        <div className={s.capSummaryItem}>
                          <span className={s.capSummaryLabel}>Available</span>
                          <strong>{teamCapacity[0].availableEmployees ?? 0}</strong>
                        </div>
                      </div>
                    </>
                  ) : (
                    <p className={s.emptyNote}>No capacity data available</p>
                  )
                )}
              </div>

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

          {leaveRequests.length > 0 && (
            <div style={{ scrollMarginTop: 24 }}>
              <AbsenceCalendar leaveRequests={leaveRequests} />
            </div>
          )}

        </main>
      </div>

      {showAddEmployee && (
        <AddEmployeeModal
          onClose={() => {
            setShowAddEmployee(false);
            setEditingEmployee(null);
          }}
          onSubmit={handleEmployeeSubmit}
          initialEmployee={editingEmployee}
          submitLabel={editingEmployee ? "Update Employee" : "Add Employee"}
          title={editingEmployee ? "Edit Employee" : "Add New Employee"}
        />
      )}

      {showLeaveRequestModal && (
        <AddLeaveRequestModal
          onClose={() => {
            setShowLeaveRequestModal(false);
            setEditingLeaveRequest(null);
          }}
          onSubmit={handleLeaveRequestSubmit}
          employees={allEmployees}
          initialEmployee={allEmployees[0]}
          initialLeaveRequest={editingLeaveRequest}
          submitLabel={editingLeaveRequest ? "Update Leave Request" : "Submit Leave Request"}
          title={editingLeaveRequest ? "Edit Leave Request" : "New Leave Request"}
        />
      )}

      <ComplianceModal
        isOpen={showCompliance}
        onClose={() => setShowCompliance(false)}
      />

    </div>
  );
}
