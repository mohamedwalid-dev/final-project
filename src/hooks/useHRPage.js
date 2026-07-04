// ─── hooks/useHRPage.js ───────────────────────────────────────────────────────
// ✅ Pure JS — all state & logic for HRPage
// ✅ Employee filtering by dept + search + view toggle
// ✅ Leave request approve/decline with optimistic UI
// ✅ Add Employee modal state
// ✅ AbortController cleanup

import { useState, useEffect, useCallback, useMemo } from "react";
import hrService from "../utils/hrService";
import employeeService from "../utils/employeeService";

export const VIEW_MODES = ["grid", "list"];

export default function useHRPage() {
  // ── Data State ───────────────────────────────────────────────────────────────
  const [employees,     setEmployees]     = useState([]);
  const [leaveRequests, setLeaveRequests] = useState([]);
  const [teamCapacity,  setTeamCapacity]  = useState([]);
  const [departments,   setDepartments]   = useState(["All Departments"]);
  const [statCards,     setStatCards]     = useState([]);

  // ── Loading / Error ──────────────────────────────────────────────────────────
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [loadingStats,     setLoadingStats]     = useState(true);
  const [loadingSidebar,   setLoadingSidebar]   = useState(true);
  const [error,            setError]            = useState(null);

  // ── UI State ─────────────────────────────────────────────────────────────────
  const [viewMode,        setViewMode]       = useState("grid");       // "grid" | "list"
  const [activeDept,      setActiveDept]     = useState("All Departments");
  const [activeStatus,    setActiveStatus]   = useState("All");        // "All" | "Active" | "On Leave"
  const [searchQuery,     setSearchQuery]    = useState("");
  const [showAddEmployee, setShowAddEmployee]= useState(false);
  const [leaveResponding, setLeaveResponding]= useState({});           // { [id]: "approving"|"declining" }

  // ── Load All Data ─────────────────────────────────────────────────────────────
  const loadAll = useCallback(() => {
    const controller = new AbortController();
    const { signal } = controller;

    setError(null);
    setLoadingEmployees(true);
    setLoadingStats(true);
    setLoadingSidebar(true);

    // Stats
    hrService.fetchStatCards(signal).then(({ data, error }) => {
      if (error) setError(error);
      else setStatCards(data ?? []);
      setLoadingStats(false);
    });

    // Employees + departments
    Promise.all([
      employeeService.fetchEmployees(signal),
      hrService.fetchDepartments(signal),
    ]).then(([emp, depts]) => {
      if (emp.error) setError(emp.error);
      else {
        const mappedEmployees = (Array.isArray(emp.data) ? emp.data : []).map((item) => buildEmployeeViewModel(item));
        const mappedLeaveRequests = mappedEmployees.flatMap((employee) => {
          const requests = Array.isArray(employee.leaveRequests) ? employee.leaveRequests : [];
          return requests.map((request) => buildLeaveRequestViewModel(request, employee));
        });

        setEmployees(mappedEmployees);
        setLeaveRequests(mappedLeaveRequests.sort((a, b) => new Date(b.startDate) - new Date(a.startDate)));

        const departmentNames = ["All Departments", ...new Set(
          [
            ...(Array.isArray(depts?.data) ? depts.data : []),
            ...mappedEmployees.map((employee) => employee.dept).filter(Boolean),
          ].filter(Boolean)
        )];
        setDepartments(departmentNames);
      }
      setLoadingEmployees(false);
    });

    // Sidebar (leave + capacity)
    Promise.all([
      employeeService.fetchTeamCapacity(signal),
    ]).then(([capacity]) => {
      if (!capacity.error) setTeamCapacity(capacity.data ?? []);
      setLoadingSidebar(false);
    });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const cleanup = loadAll();
    return cleanup;
  }, [loadAll]);

  // ── Filtered Employees ────────────────────────────────────────────────────────
  const filteredEmployees = useMemo(() => {
    return employees.filter((emp) => {
      const matchDept   = activeDept === "All Departments" || emp.dept === activeDept;
      const matchStatus =
        activeStatus === "All"      ? true :
        activeStatus === "Active"   ? emp.status === "active" :
        activeStatus === "On Leave" ? emp.status === "leave"  : true;
      const q = searchQuery.toLowerCase();
      const matchSearch =
        !q ||
        emp.name.toLowerCase().includes(q)  ||
        emp.title.toLowerCase().includes(q) ||
        emp.dept.toLowerCase().includes(q)  ||
        emp.location.toLowerCase().includes(q);
      return matchDept && matchStatus && matchSearch;
    });
  }, [employees, activeDept, activeStatus, searchQuery]);

  // ── Leave Actions ─────────────────────────────────────────────────────────────
  const handleLeaveAction = useCallback(async (id, action) => {
    setLeaveResponding((prev) => ({ ...prev, [id]: action === "approve" ? "approving" : "declining" }));

    const nextStatus = action === "approve" ? "Approved" : "Rejected";
    setLeaveRequests((prev) => prev.map((request) => (request.id === id ? { ...request, status: nextStatus } : request)));

    setLeaveResponding((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  const buildEmployeeViewModel = useCallback((data, fallbackName = "") => {
    const colors = ["#3B5BDB", "#F59F00", "#2F9E44", "#845EF7", "#FA5252", "#4DABF7"];
    const name = data?.fullName || data?.name || fallbackName || "Employee";
    const normalized = {
      ...data,
      id: data?._id || data?.id,
      name,
      fullName: data?.fullName || name,
      dept: data?.department || data?.dept || "Engineering",
      title: data?.jobTitle || data?.title || "Employee",
      location: data?.location || "Unknown",
      email: data?.workEmail || data?.email || "",
      salary: data?.salary,
      phoneNumber: data?.phoneNumber || "",
      startDate: data?.startDate || "",
      dateOfBirth: data?.dateOfBirth || "",
      gender: data?.gender || "",
      employeeId: data?.employeeId || "",
      leaveRequests: Array.isArray(data?.leaveRequests) ? data.leaveRequests : [],
      avatar: (name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2) || "EM"),
      color: colors[Math.floor(Math.random() * colors.length)],
      status: data?.status || "active",
    };

    return normalized;
  }, []);

  const buildLeaveRequestViewModel = useCallback((data, employee = null) => {
    const colors = ["#3B5BDB", "#F59F00", "#2F9E44", "#845EF7", "#FA5252", "#4DABF7"];
    const memberName = employee?.fullName || employee?.name || data?.fullName || "Employee";
    const startDate = data?.leaveStartDate ? new Date(data.leaveStartDate) : null;
    const endDate = data?.leaveEndDate ? new Date(data.leaveEndDate) : null;

    const formatDate = (value) => {
      if (!value || Number.isNaN(value.getTime())) return "TBD";
      const month = value.toLocaleString("en", { month: "short" });
      return `${month} ${value.getDate()}`;
    };

    const getDayCount = (from, to) => {
      if (!from || !to || Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return 1;
      const diff = Math.round((to - from) / 86400000);
      return Math.max(1, diff + 1);
    };

    return {
      ...data,
      id: data?._id || data?.id,
      employeeId: data?.employeeId || employee?.employeeId || "",
      name: memberName,
      fullName: data?.fullName || memberName,
      type: data?.leaveType || "Leave",
      balance: data?.leaveBalance ?? 0,
      days: getDayCount(startDate, endDate),
      from: formatDate(startDate),
      to: formatDate(endDate),
      status: data?.status || "Pending",
      startDate: data?.leaveStartDate || "",
      endDate: data?.leaveEndDate || "",
      reason: data?.reason || "",
      avatar: (memberName.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2) || "EM"),
      color: colors[Math.abs((memberName || "").split("").reduce((acc, char) => acc + char.charCodeAt(0), 0)) % colors.length],
    };
  }, []);

  // ── Add Employee ──────────────────────────────────────────────────────────────
  const handleAddEmployee = useCallback(async (formData) => {
    const { data, error } = await employeeService.createEmployee(formData);
    if (!error && data) {
      const normalized = buildEmployeeViewModel(data, formData.fullName || formData.name);
      setEmployees((prev) => [normalized, ...prev]);
      setShowAddEmployee(false);
      loadAll();
      return { error: null };
    }
    return { error };
  }, [buildEmployeeViewModel, loadAll]);

  const handleUpdateEmployee = useCallback(async (id, formData) => {
    const { data, error } = await employeeService.updateEmployee(id, formData);
    if (!error && data) {
      const normalized = buildEmployeeViewModel(data, formData.fullName || formData.name);
      setEmployees((prev) => prev.map((item) => (item.id === id || item._id === id ? normalized : item)));
      loadAll();
      return { error: null };
    }
    return { error };
  }, [buildEmployeeViewModel, loadAll]);

  const handleDeleteEmployee = useCallback(async (id) => {
    const { error } = await employeeService.deleteEmployee(id);
    if (!error) {
      setEmployees((prev) => prev.filter((item) => item.id !== id && item._id !== id));
      loadAll();
      return { error: null };
    }
    return { error };
  }, [loadAll]);

  const handleAddLeaveRequest = useCallback(async (employeeId, formData) => {
    const { data, error } = await employeeService.createLeaveRequest(employeeId, formData);
    if (!error && data) {
      const normalized = buildLeaveRequestViewModel(data);
      setLeaveRequests((prev) => [normalized, ...prev]);
      setEmployees((prev) => prev.map((item) => {
        const itemId = item.id || item._id;
        if (itemId !== employeeId) return item;
        return {
          ...item,
          leaveRequests: [...(item.leaveRequests || []), data],
        };
      }));
      loadAll();
      return { error: null };
    }
    return { error };
  }, [buildLeaveRequestViewModel, loadAll]);

  const handleUpdateLeaveRequest = useCallback(async (employeeId, leaveRequestId, formData) => {
    const { data, error } = await employeeService.updateLeaveRequest(employeeId, leaveRequestId, formData);
    if (!error && data) {
      loadAll();
      return { error: null };
    }
    return { error };
  }, [loadAll]);

  const handleDeleteLeaveRequest = useCallback(async (employeeId, leaveRequestId) => {
    const { error } = await employeeService.deleteLeaveRequest(employeeId, leaveRequestId);
    if (!error) {
      setLeaveRequests((prev) => prev.filter((item) => item.id !== leaveRequestId && item._id !== leaveRequestId));
      loadAll();
      return { error: null };
    }
    return { error };
  }, [loadAll]);

  return {
    // Data
    employees:       filteredEmployees,
    allEmployees:    employees,
    leaveRequests,
    teamCapacity,
    statCards,
    departments,
    // Loading
    loadingEmployees,
    loadingStats,
    loadingSidebar,
    error,
    // UI State
    viewMode,        setViewMode,
    activeDept,      setActiveDept,
    activeStatus,    setActiveStatus,
    searchQuery,     setSearchQuery,
    showAddEmployee, setShowAddEmployee,
    leaveResponding,
    // Actions
    handleLeaveAction,
    handleAddEmployee,
    handleUpdateEmployee,
    handleDeleteEmployee,
    handleAddLeaveRequest,
    handleUpdateLeaveRequest,
    handleDeleteLeaveRequest,
    reload: loadAll,
  };
}