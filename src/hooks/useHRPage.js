// ─── hooks/useHRPage.js ───────────────────────────────────────────────────────
// ✅ Pure JS — all state & logic for HRPage
// ✅ Employee filtering by dept + search + view toggle
// ✅ Leave request approve/decline with optimistic UI
// ✅ Add Employee modal state
// ✅ AbortController cleanup

import { useState, useEffect, useCallback, useMemo } from "react";
import hrService from "../utils/hrService";

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
      hrService.fetchEmployees({}, signal),
      hrService.fetchDepartments(signal),
    ]).then(([emp, depts]) => {
      if (emp.error) setError(emp.error);
      else setEmployees(emp.data ?? []);
      if (!depts.error) setDepartments(depts.data ?? []);
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

  // ── Add Employee ──────────────────────────────────────────────────────────────
  const handleAddEmployee = useCallback(async (formData) => {
    const { data, error } = await hrService.addEmployee(formData);
    if (!error && data) {
      const colors = ["#3B5BDB","#F59F00","#2F9E44","#845EF7","#FA5252","#4DABF7"];
      const newEmp = {
        ...data,
        avatar: formData.name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2),
        color:  colors[Math.floor(Math.random() * colors.length)],
        status: "active",
      };
      setEmployees((prev) => [newEmp, ...prev]);
      setShowAddEmployee(false);
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
    reload: loadAll,
  };
}