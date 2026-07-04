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
        setEmployees(mappedEmployees);

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
      hrService.fetchLeaveRequests(signal),
      hrService.fetchTeamCapacity(signal),
    ]).then(([leave, capacity]) => {
      if (!leave.error)    setLeaveRequests(leave.data    ?? []);
      if (!capacity.error) setTeamCapacity(capacity.data  ?? []);
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

    const { error } = await hrService.respondToLeave(id, action);

    if (!error) {
      // Optimistic removal from list
      setLeaveRequests((prev) => prev.filter((r) => r.id !== id));
    }
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
      avatar: (name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2) || "EM"),
      color: colors[Math.floor(Math.random() * colors.length)],
      status: data?.status || "active",
    };

    return normalized;
  }, []);

  // ── Add Employee ──────────────────────────────────────────────────────────────
  const handleAddEmployee = useCallback(async (formData) => {
    const { data, error } = await employeeService.createEmployee(formData);
    if (!error && data) {
      const normalized = buildEmployeeViewModel(data, formData.fullName || formData.name);
      setEmployees((prev) => [normalized, ...prev]);
      setShowAddEmployee(false);
      return { error: null };
    }
    return { error };
  }, [buildEmployeeViewModel]);

  const handleUpdateEmployee = useCallback(async (id, formData) => {
    const { data, error } = await employeeService.updateEmployee(id, formData);
    if (!error && data) {
      const normalized = buildEmployeeViewModel(data, formData.fullName || formData.name);
      setEmployees((prev) => prev.map((item) => (item.id === id || item._id === id ? normalized : item)));
      return { error: null };
    }
    return { error };
  }, [buildEmployeeViewModel]);

  const handleDeleteEmployee = useCallback(async (id) => {
    const { error } = await employeeService.deleteEmployee(id);
    if (!error) {
      setEmployees((prev) => prev.filter((item) => item.id !== id && item._id !== id));
      return { error: null };
    }
    return { error };
  }, []);

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
    reload: loadAll,
  };
}