// ─── components/HR/ComplianceModal.jsx ───────────────────────────────────────
import { useState, useEffect, useRef, useMemo } from "react";
import s from "./ComplianceModal.module.css";

// ─────────────────────────────────────────────────────────────────────────────
// MOCK DATA
// ─────────────────────────────────────────────────────────────────────────────

const CURRENT_USER = { name: "Alex Sterling", role: "HR Admin", id: "u_admin" };

const EMPLOYEES_COMPLIANCE = [
  {
    id: "e1", name: "Sarah Jenkins",   avatar: "SJ", color: "#3B5BDB", dept: "Design",
    title: "Sr. Product Designer", hired: "2021-03-15", status: "Active",
    contractType: "Full-time", contractEnd: "2025-12-31", contractStatus: "Active",
    addedBy: "Elena Rodriguez", lastEditedBy: "Alex Sterling", lastEditedAt: "2024-09-01",
    salary: 95000,
    leaveBalance: { annual: 18, sick: 10, personal: 3 },
    leaveUsed:    { annual: 7,  sick: 2,  personal: 1 },
    trainings: [
      { name: "Data Privacy & GDPR",   status: "Completed", due: "2024-01-31", score: 92,  mandatory: true,  certExpiry: "2025-01-31" },
      { name: "Anti-Harassment",        status: "Completed", due: "2024-03-31", score: 100, mandatory: true,  certExpiry: "2025-03-31" },
      { name: "Information Security",   status: "Pending",   due: "2024-11-30", score: null,mandatory: true,  certExpiry: null         },
    ],
  },
  {
    id: "e2", name: "Marcus Thompson", avatar: "MT", color: "#F59F00", dept: "Engineering",
    title: "Fullstack Engineer", hired: "2020-07-01", status: "Active",
    contractType: "Full-time", contractEnd: "2026-06-30", contractStatus: "Active",
    addedBy: "Elena Rodriguez", lastEditedBy: "Elena Rodriguez", lastEditedAt: "2024-06-15",
    salary: 120000,
    leaveBalance: { annual: 20, sick: 10, personal: 3 },
    leaveUsed:    { annual: 12, sick: 0,  personal: 2 },
    trainings: [
      { name: "Information Security",   status: "Completed", due: "2024-04-30", score: 88,  mandatory: true,  certExpiry: "2025-04-30" },
      { name: "Code of Conduct",        status: "Completed", due: "2024-01-31", score: 95,  mandatory: true,  certExpiry: null         },
      { name: "Data Privacy & GDPR",    status: "Overdue",   due: "2024-09-30", score: null,mandatory: true,  certExpiry: null         },
    ],
  },
  {
    id: "e3", name: "Elena Rodriguez",  avatar: "ER", color: "#2F9E44", dept: "HR",
    title: "HR Manager", hired: "2019-01-10", status: "Active",
    contractType: "Full-time", contractEnd: "2025-03-31", contractStatus: "Expiring Soon",
    addedBy: "System", lastEditedBy: "Alex Sterling", lastEditedAt: "2024-08-20",
    salary: 88000,
    leaveBalance: { annual: 18, sick: 10, personal: 3 },
    leaveUsed:    { annual: 3,  sick: 5,  personal: 0 },
    trainings: [
      { name: "Anti-Harassment",        status: "Completed", due: "2024-03-31", score: 100, mandatory: true,  certExpiry: "2025-03-31" },
      { name: "Data Privacy & GDPR",    status: "Completed", due: "2024-02-28", score: 96,  mandatory: true,  certExpiry: "2025-02-28" },
      { name: "Code of Conduct",        status: "Completed", due: "2024-01-31", score: 91,  mandatory: true,  certExpiry: null         },
    ],
  },
  {
    id: "e4", name: "David Chen",       avatar: "DC", color: "#845EF7", dept: "Finance",
    title: "Financial Analyst", hired: "2022-05-01", status: "Active",
    contractType: "Part-time", contractEnd: "2025-01-31", contractStatus: "Expiring Soon",
    addedBy: "Elena Rodriguez", lastEditedBy: "Elena Rodriguez", lastEditedAt: "2024-07-01",
    salary: 105000,
    leaveBalance: { annual: 12, sick: 8, personal: 2 },
    leaveUsed:    { annual: 9,  sick: 3, personal: 2 },
    trainings: [
      { name: "Information Security",   status: "Completed", due: "2024-04-30", score: 84,  mandatory: true,  certExpiry: "2025-04-30" },
      { name: "Anti-Harassment",        status: "Pending",   due: "2024-11-30", score: null,mandatory: true,  certExpiry: null         },
      { name: "Data Privacy & GDPR",    status: "Overdue",   due: "2024-08-31", score: null,mandatory: true,  certExpiry: null         },
    ],
  },
  {
    id: "e5", name: "Sophie Alistair",  avatar: "SA", color: "#2F9E44", dept: "Marketing",
    title: "Marketing Specialist", hired: "2023-01-15", status: "Active",
    contractType: "Full-time", contractEnd: "2026-08-31", contractStatus: "Active",
    addedBy: "Elena Rodriguez", lastEditedBy: "Elena Rodriguez", lastEditedAt: "2024-01-20",
    salary: 78000,
    leaveBalance: { annual: 18, sick: 10, personal: 3 },
    leaveUsed:    { annual: 5,  sick: 1,  personal: 1 },
    trainings: [
      { name: "Social Media Guidelines",status: "Completed", due: "2024-09-30", score: 78,  mandatory: false, certExpiry: null         },
      { name: "Code of Conduct",        status: "Completed", due: "2024-01-31", score: 89,  mandatory: true,  certExpiry: null         },
      { name: "Anti-Harassment",        status: "Pending",   due: "2024-12-31", score: null,mandatory: true,  certExpiry: null         },
    ],
  },
  {
    id: "e6", name: "Julian Voss",      avatar: "JV", color: "#FA5252", dept: "Engineering",
    title: "DevOps Engineer", hired: "2021-09-01", status: "Suspended",
    contractType: "Contractor", contractEnd: "2024-12-31", contractStatus: "Expiring Soon",
    addedBy: "Elena Rodriguez", lastEditedBy: "Alex Sterling", lastEditedAt: "2024-10-01",
    salary: 115000,
    leaveBalance: { annual: 10, sick: 5, personal: 1 },
    leaveUsed:    { annual: 4,  sick: 0, personal: 0 },
    trainings: [
      { name: "Information Security",   status: "Overdue",   due: "2024-07-31", score: null,mandatory: true,  certExpiry: null         },
      { name: "Code of Conduct",        status: "Overdue",   due: "2024-01-31", score: null,mandatory: true,  certExpiry: null         },
      { name: "Data Privacy & GDPR",    status: "Pending",   due: "2024-11-30", score: null,mandatory: true,  certExpiry: null         },
    ],
  },
];

const PAYROLL_HISTORY = {
  e1: [
    { id:"p1", version:3, basicSalary:90000, allowances:5000, deductions:2000, tax:11550, insurance:1800, net:79650, effectiveDate:"2024-01-01", approvedBy:"Alex Sterling", approvedAt:"2023-12-20", status:"Locked", changeReason:"Annual raise", changedBy:"Elena Rodriguez" },
    { id:"p2", version:2, basicSalary:85000, allowances:4000, deductions:1800, tax:10890, insurance:1700, net:74610, effectiveDate:"2023-01-01", approvedBy:"Alex Sterling", approvedAt:"2022-12-15", status:"Locked", changeReason:"Performance bonus", changedBy:"Elena Rodriguez" },
    { id:"p3", version:1, basicSalary:80000, allowances:3000, deductions:1500, tax:10200, insurance:1600, net:69700, effectiveDate:"2021-03-15", approvedBy:"Alex Sterling", approvedAt:"2021-03-10", status:"Locked", changeReason:"Initial", changedBy:"System" },
  ],
  e2: [
    { id:"p4", version:2, basicSalary:115000, allowances:6000, deductions:2500, tax:14790, insurance:2200, net:101510, effectiveDate:"2024-01-01", approvedBy:"Alex Sterling", approvedAt:"2023-12-18", status:"Locked", changeReason:"Annual raise", changedBy:"Elena Rodriguez" },
    { id:"p5", version:1, basicSalary:105000, allowances:5000, deductions:2000, tax:13470, insurance:2000, net:92530, effectiveDate:"2020-07-01", approvedBy:"Alex Sterling", approvedAt:"2020-06-28", status:"Locked", changeReason:"Initial", changedBy:"System" },
  ],
  e3: [
    { id:"p6", version:2, basicSalary:85000, allowances:4000, deductions:2000, tax:10890, insurance:1700, net:74410, effectiveDate:"2024-03-01", approvedBy:"Alex Sterling", approvedAt:"2024-02-25", status:"Locked", changeReason:"Promotion", changedBy:"Alex Sterling" },
    { id:"p7", version:1, basicSalary:75000, allowances:3500, deductions:1800, tax:9630,  insurance:1500, net:65570, effectiveDate:"2019-01-10", approvedBy:"CEO",           approvedAt:"2019-01-08", status:"Locked", changeReason:"Initial", changedBy:"System" },
  ],
};

const LEAVE_REQUESTS = [
  { id:"l1", empId:"e1", empName:"Sarah Jenkins",   avatar:"SJ", color:"#3B5BDB", type:"Annual",    from:"2024-10-20", to:"2024-10-25", days:6, reason:"Family vacation",    status:"Approved",  submittedAt:"2024-10-01", approvedBy:"Elena Rodriguez", approvedAt:"2024-10-03", attachments:false },
  { id:"l2", empId:"e2", empName:"Marcus Thompson", avatar:"MT", color:"#F59F00", type:"Sick",      from:"2024-10-10", to:"2024-10-11", days:2, reason:"Illness",            status:"Approved",  submittedAt:"2024-10-10", approvedBy:"Elena Rodriguez", approvedAt:"2024-10-10", attachments:true  },
  { id:"l3", empId:"e4", empName:"David Chen",      avatar:"DC", color:"#845EF7", type:"Annual",    from:"2024-11-01", to:"2024-11-05", days:5, reason:"Personal travel",    status:"Pending",   submittedAt:"2024-10-15", approvedBy:null,             approvedAt:null,         attachments:false },
  { id:"l4", empId:"e5", empName:"Sophie Alistair", avatar:"SA", color:"#2F9E44", type:"Personal",  from:"2024-11-08", to:"2024-11-08", days:1, reason:"Personal errand",   status:"Pending",   submittedAt:"2024-10-18", approvedBy:null,             approvedAt:null,         attachments:false },
  { id:"l5", empId:"e3", empName:"Elena Rodriguez", avatar:"ER", color:"#2F9E44", type:"Sick",      from:"2024-09-05", to:"2024-09-07", days:3, reason:"Medical procedure",  status:"Approved",  submittedAt:"2024-09-04", approvedBy:"Alex Sterling",  approvedAt:"2024-09-04", attachments:true  },
  { id:"l6", empId:"e6", empName:"Julian Voss",     avatar:"JV", color:"#FA5252", type:"Annual",    from:"2024-08-15", to:"2024-08-20", days:6, reason:"Vacation",           status:"Rejected",  submittedAt:"2024-08-01", approvedBy:"Elena Rodriguez", approvedAt:"2024-08-05", attachments:false },
];

const ATTENDANCE = [
  { id:"a1", empId:"e1", empName:"Sarah Jenkins",   avatar:"SJ", color:"#3B5BDB", date:"2024-10-28", checkIn:"09:02", checkOut:"17:45", hours:8.72, overtime:0.72, status:"Present",  manualOverride:false, overrideBy:null,             overrideReason:null },
  { id:"a2", empId:"e2", empName:"Marcus Thompson", avatar:"MT", color:"#F59F00", date:"2024-10-28", checkIn:"08:45", checkOut:"19:30", hours:10.75,overtime:2.75, status:"Overtime", manualOverride:false, overrideBy:null,             overrideReason:null },
  { id:"a3", empId:"e3", empName:"Elena Rodriguez", avatar:"ER", color:"#2F9E44", date:"2024-10-28", checkIn:"09:00", checkOut:"17:00", hours:8.0,  overtime:0,    status:"Present",  manualOverride:false, overrideBy:null,             overrideReason:null },
  { id:"a4", empId:"e4", empName:"David Chen",      avatar:"DC", color:"#845EF7", date:"2024-10-28", checkIn:null,   checkOut:null,   hours:0,    overtime:0,    status:"Absent",   manualOverride:true,  overrideBy:"Elena Rodriguez", overrideReason:"Medical appointment documented" },
  { id:"a5", empId:"e5", empName:"Sophie Alistair", avatar:"SA", color:"#2F9E44", date:"2024-10-28", checkIn:"09:15", checkOut:"17:10", hours:7.92, overtime:0,    status:"Present",  manualOverride:false, overrideBy:null,             overrideReason:null },
  { id:"a6", empId:"e6", empName:"Julian Voss",     avatar:"JV", color:"#FA5252", date:"2024-10-28", checkIn:null,   checkOut:null,   hours:0,    overtime:0,    status:"Suspended",manualOverride:false, overrideBy:null,             overrideReason:null },
];

const ACCESS_ROLES = [
  { id:"r1", role:"HR Admin",         users:["Alex Sterling","Elena Rodriguez"], permissions:["view_all","edit_employees","manage_payroll","approve_leave","manage_policies","view_audit","manage_roles"] },
  { id:"r2", role:"Finance Manager",  users:["David Chen"],                      permissions:["view_payroll","approve_payroll","view_reports"] },
  { id:"r3", role:"Department Manager",users:["Marcus Thompson"],                permissions:["approve_leave_team","view_team_training","view_team_attendance"] },
  { id:"r4", role:"Employee",          users:["Sarah Jenkins","Sophie Alistair","Julian Voss"], permissions:["view_own","submit_leave","view_own_payslip"] },
];

const PERMISSION_LABELS = {
  view_all:              "View All Employee Data",
  edit_employees:        "Edit Employee Records",
  manage_payroll:        "Manage Payroll",
  approve_leave:         "Approve Leave Requests",
  manage_policies:       "Manage Policies",
  view_audit:            "View Audit Logs",
  manage_roles:          "Manage Access Roles",
  view_payroll:          "View Payroll Data",
  approve_payroll:       "Approve Payroll",
  view_reports:          "View Compliance Reports",
  approve_leave_team:    "Approve Team Leave",
  view_team_training:    "View Team Training",
  view_team_attendance:  "View Team Attendance",
  view_own:              "View Own Profile",
  submit_leave:          "Submit Leave Requests",
  view_own_payslip:      "View Own Payslip",
};

const AUDIT_LOGS = [
  { id:"au1",  user:"Alex Sterling",    action:"UPDATE",  entity:"Employee",    entityId:"e6", field:"status",          oldVal:"Active",    newVal:"Suspended",   at:"2024-10-01 14:22:10", ip:"192.168.1.10", reason:"Policy violation" },
  { id:"au2",  user:"Elena Rodriguez",  action:"APPROVE", entity:"Leave",       entityId:"l2", field:"status",          oldVal:"Pending",   newVal:"Approved",    at:"2024-10-10 09:05:33", ip:"192.168.1.14", reason:null },
  { id:"au3",  user:"Alex Sterling",    action:"UPDATE",  entity:"Payroll",     entityId:"p6", field:"basicSalary",     oldVal:"EGP 75,000",   newVal:"EGP 85,000",     at:"2024-02-25 11:30:00", ip:"192.168.1.10", reason:"Promotion" },
  { id:"au4",  user:"Elena Rodriguez",  action:"CREATE",  entity:"Employee",    entityId:"e5", field:"—",               oldVal:null,        newVal:"Sophie Alistair",at:"2023-01-15 10:00:00",ip:"192.168.1.14", reason:null },
  { id:"au5",  user:"Elena Rodriguez",  action:"APPROVE", entity:"Leave",       entityId:"l1", field:"status",          oldVal:"Pending",   newVal:"Approved",    at:"2024-10-03 10:15:22", ip:"192.168.1.14", reason:null },
  { id:"au6",  user:"Elena Rodriguez",  action:"REJECT",  entity:"Leave",       entityId:"l6", field:"status",          oldVal:"Pending",   newVal:"Rejected",    at:"2024-08-05 13:44:01", ip:"192.168.1.14", reason:"Insufficient leave balance" },
  { id:"au7",  user:"Elena Rodriguez",  action:"OVERRIDE",entity:"Attendance",  entityId:"a4", field:"status",          oldVal:"Absent",    newVal:"Excused",     at:"2024-10-28 18:00:00", ip:"192.168.1.14", reason:"Medical appointment documented" },
  { id:"au8",  user:"Alex Sterling",    action:"UPDATE",  entity:"Policy",      entityId:"p_6",field:"status",          oldVal:"Active",    newVal:"Draft",       at:"2024-10-15 09:00:00", ip:"192.168.1.10", reason:"Under revision" },
  { id:"au9",  user:"System",           action:"LOCK",    entity:"Payroll",     entityId:"p4", field:"payroll_record",  oldVal:"Approved",  newVal:"Locked",      at:"2024-01-31 23:59:59", ip:"system",       reason:"Monthly payroll run complete" },
  { id:"au10", user:"Marcus Thompson",  action:"SUBMIT",  entity:"Leave",       entityId:"l_x",field:"status",          oldVal:null,        newVal:"Submitted",   at:"2024-10-20 08:30:00", ip:"192.168.1.22", reason:null },
];

const POLICIES = [
  { id:"po1", title:"Code of Conduct",          category:"General",    status:"Active", updated:"Jan 2024", acknowledged:94,  mandatoryTraining:true  },
  { id:"po2", title:"Anti-Harassment Policy",   category:"HR",         status:"Active", updated:"Mar 2024", acknowledged:100, mandatoryTraining:true  },
  { id:"po3", title:"Data Privacy & GDPR",      category:"Legal",      status:"Active", updated:"Feb 2024", acknowledged:87,  mandatoryTraining:true  },
  { id:"po4", title:"Remote Work Policy",       category:"Operations", status:"Active", updated:"Jun 2024", acknowledged:76,  mandatoryTraining:false },
  { id:"po5", title:"Information Security",     category:"IT",         status:"Active", updated:"Apr 2024", acknowledged:91,  mandatoryTraining:true  },
  { id:"po6", title:"Travel & Expenses Policy", category:"Finance",    status:"Draft",  updated:"Oct 2024", acknowledged:0,   mandatoryTraining:false },
  { id:"po7", title:"Whistleblower Protection", category:"Legal",      status:"Active", updated:"Jan 2024", acknowledged:88,  mandatoryTraining:false },
  { id:"po8", title:"Social Media Guidelines",  category:"Marketing",  status:"Review", updated:"Sep 2024", acknowledged:62,  mandatoryTraining:false },
];

const DOCUMENTS = [
  { id:"d1", name:"Employee Handbook 2024",        type:"PDF",  size:"2.4 MB", updated:"Jan 2024", category:"General"   },
  { id:"d2", name:"Benefits Summary Sheet",        type:"PDF",  size:"1.1 MB", updated:"Mar 2024", category:"HR"        },
  { id:"d3", name:"Organizational Chart",          type:"PDF",  size:"0.8 MB", updated:"Jun 2024", category:"General"   },
  { id:"d4", name:"Q3 2024 Payroll Report",        type:"XLSX", size:"3.2 MB", updated:"Sep 2024", category:"Finance"   },
  { id:"d5", name:"GDPR Compliance Audit Report",  type:"PDF",  size:"5.6 MB", updated:"May 2024", category:"Legal"     },
  { id:"d6", name:"Health & Safety Manual",        type:"PDF",  size:"1.9 MB", updated:"Feb 2024", category:"Operations"},
  { id:"d7", name:"Performance Review Template",   type:"DOCX", size:"0.4 MB", updated:"Apr 2024", category:"HR"        },
  { id:"d8", name:"Incident Report Log 2024",      type:"XLSX", size:"0.9 MB", updated:"Oct 2024", category:"Legal"     },
];

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
const fmt  = (n) => new Intl.NumberFormat("en-US",{ style:"currency", currency:"USD", maximumFractionDigits:0 }).format(n);
const fmtD = (s) => s ? new Date(s).toLocaleDateString("en-GB",{ day:"2-digit", month:"short", year:"numeric" }) : "—";

const TABS = [
  { id:"overview",    label:"Overview"        },
  { id:"employees",   label:"Employees"       },
  { id:"payroll",     label:"Payroll"         },
  { id:"leave",       label:"Leave"           },
  { id:"attendance",  label:"Attendance"      },
  { id:"training",    label:"Training"        },
  { id:"policies",    label:"Policies"        },
  { id:"documents",   label:"Documents"       },
  { id:"access",      label:"Access Control"  },
  { id:"audit",       label:"Audit Logs"      },
  { id:"reports",     label:"Reports"         },
];

// ─────────────────────────────────────────────────────────────────────────────
// SHARED COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    "Active":"badgeActive","Completed":"badgeActive","Approved":"badgeActive","Present":"badgeActive",
    "Draft":"badgeDraft","Optional":"badgeDraft",
    "Review":"badgeReview","Overtime":"badgeReview",
    "Pending":"badgePending","Submitted":"badgePending",
    "Overdue":"badgeOverdue","Rejected":"badgeOverdue","Absent":"badgeOverdue","Suspended":"badgeOverdue","Terminated":"badgeOverdue",
    "Expiring Soon":"badgeExpiring","Locked":"badgeLocked",
  };
  return <span className={`${s.badge} ${s[map[status]||"badgeDraft"]}`}>{status}</span>;
}

function ProgressBar({ value, max, color="#3B5BDB" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value/max)*100)) : 0;
  return (
    <div className={s.progressWrap}>
      <div className={s.progressTrack}><div className={s.progressFill} style={{ width:`${pct}%`, background:color }} /></div>
      <span className={s.progressLabel}>{value}/{max}</span>
    </div>
  );
}

function EmpAvatar({ emp, size=32 }) {
  return <div className={s.empMiniAvatar} style={{ background:emp.color, width:size, height:size, fontSize:size*0.33, borderRadius:size*0.22 }}>{emp.avatar}</div>;
}

function TabSearch({ value, onChange, placeholder="Search..." }) {
  return <input className={s.tabSearch} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder} />;
}

function SectionTitle({ children }) {
  return <h4 className={s.sectionTitle}>{children}</h4>;
}

function InfoGrid({ items }) {
  return (
    <div className={s.infoGrid}>
      {items.map(item => (
        <div key={item.label} className={s.infoItem}>
          <p className={s.infoLabel}>{item.label}</p>
          <p className={s.infoValue}>{item.value}</p>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: OVERVIEW
// ─────────────────────────────────────────────────────────────────────────────
function OverviewTab({ onTab }) {
  const totalTrainings     = EMPLOYEES_COMPLIANCE.flatMap(e=>e.trainings);
  const completed          = totalTrainings.filter(t=>t.status==="Completed").length;
  const overdue            = totalTrainings.filter(t=>t.status==="Overdue").length;
  const expiringContracts  = EMPLOYEES_COMPLIANCE.filter(e=>e.contractStatus==="Expiring Soon").length;
  const activePolicies     = POLICIES.filter(p=>p.status==="Active").length;
  const ackedPolicies      = POLICIES.filter(p=>p.acknowledged>0);
  const avgAck             = ackedPolicies.length ? Math.round(ackedPolicies.reduce((a,p)=>a+p.acknowledged,0)/ackedPolicies.length) : 0;
  const totalPayroll       = EMPLOYEES_COMPLIANCE.reduce((a,e)=>a+e.salary,0)/12;
  const pendingLeave       = LEAVE_REQUESTS.filter(l=>l.status==="Pending").length;
  const overdueTrainees    = new Set(EMPLOYEES_COMPLIANCE.filter(e=>e.trainings.some(t=>t.status==="Overdue")).map(e=>e.id)).size;

  const kpis = [
    { label:"Active Policies",       value:activePolicies,       sub:`${POLICIES.length-activePolicies} in draft/review`,  tab:"policies"   },
    { label:"Training Completion",   value:`${Math.round(completed/totalTrainings.length*100)}%`, sub:`${completed} of ${totalTrainings.length} completed`, tab:"training" },
    { label:"Overdue Trainings",     value:overdue,              sub:`${overdueTrainees} employees affected`,               tab:"training"   },
    { label:"Expiring Contracts",    value:expiringContracts,    sub:"Within next 3 months",                                tab:"employees"  },
    { label:"Policy Acknowledgment", value:`${avgAck}%`,         sub:"Average across all policies",                        tab:"policies"   },
    { label:"Total Payroll (mo.)",   value:fmt(totalPayroll),    sub:"All employees combined",                              tab:"payroll"    },
    { label:"Pending Leave",         value:pendingLeave,         sub:"Awaiting approval",                                   tab:"leave"      },
    { label:"Access Roles",          value:ACCESS_ROLES.length,  sub:`${EMPLOYEES_COMPLIANCE.length} employees covered`,    tab:"access"     },
    { label:"Audit Events Today",    value:AUDIT_LOGS.length,    sub:"Click to view full log",                              tab:"audit"      },
  ];

  const attention = EMPLOYEES_COMPLIANCE.filter(e=>
    e.contractStatus==="Expiring Soon" ||
    e.trainings.some(t=>t.status==="Overdue") ||
    e.status==="Suspended"
  );

  return (
    <div>
      <div className={s.overviewGrid}>
        {kpis.map(k => (
          <div key={k.label} className={s.kpiCard} onClick={()=>onTab(k.tab)} role="button" tabIndex={0} title={`Go to ${k.tab}`}>
            <p className={s.kpiValue}>{k.value}</p>
            <p className={s.kpiLabel}>{k.label}</p>
            <p className={s.kpiSub}>{k.sub}</p>
          </div>
        ))}
      </div>

      <SectionTitle>Employees Requiring Attention</SectionTitle>
      <div className={s.attentionList}>
        {attention.map(emp => (
          <div key={emp.id} className={s.attentionItem}>
            <EmpAvatar emp={emp} size={34} />
            <div className={s.attentionInfo}>
              <p className={s.attentionName}>{emp.name}</p>
              <p className={s.attentionSub}>{emp.dept}</p>
            </div>
            <div className={s.attentionTags}>
              {emp.status==="Suspended"                            && <StatusBadge status="Suspended"     />}
              {emp.contractStatus==="Expiring Soon"                && <StatusBadge status="Expiring Soon" />}
              {emp.trainings.some(t=>t.status==="Overdue")         && <StatusBadge status="Overdue"       />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: EMPLOYEES
// ─────────────────────────────────────────────────────────────────────────────
function EmployeesTab() {
  const [search,   setSearch]   = useState("");
  const [selected, setSelected] = useState(null);
  const filtered = useMemo(() => EMPLOYEES_COMPLIANCE.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.dept.toLowerCase().includes(search.toLowerCase())
  ), [search]);

  return (
    <div className={s.splitLayout}>
      <div className={s.splitList}>
        <TabSearch value={search} onChange={setSearch} placeholder="Search employees..." />
        {filtered.map(emp => (
          <div key={emp.id}
            className={`${s.splitRow} ${selected?.id===emp.id ? s.splitRowActive:""}`}
            onClick={()=>setSelected(emp)} role="button" tabIndex={0}>
            <EmpAvatar emp={emp} size={34} />
            <div style={{flex:1}}>
              <p className={s.splitName}>{emp.name}</p>
              <p className={s.splitSub}>{emp.dept} · {emp.contractType}</p>
            </div>
            <StatusBadge status={emp.status} />
          </div>
        ))}
      </div>

      <div className={s.splitDetail}>
        {!selected ? (
          <div className={s.splitEmpty}><p>Select an employee</p></div>
        ) : (
          <div>
            <div className={s.detailHeader}>
              <EmpAvatar emp={selected} size={44} />
              <div>
                <h4 className={s.detailName}>{selected.name}</h4>
                <p className={s.detailDept}>{selected.title} · {selected.dept}</p>
              </div>
              <StatusBadge status={selected.status} />
            </div>

            <div className={s.detailSection}>
              <h5 className={s.detailSectionTitle}>Basic Information</h5>
              <InfoGrid items={[
                { label:"Hire Date",      value:fmtD(selected.hired)       },
                { label:"Contract Type",  value:selected.contractType      },
                { label:"Contract End",   value:fmtD(selected.contractEnd) },
                { label:"Contract Status",value:<StatusBadge status={selected.contractStatus} /> },
                { label:"Added By",       value:selected.addedBy           },
                { label:"Last Edited By", value:selected.lastEditedBy      },
                { label:"Last Edited At", value:fmtD(selected.lastEditedAt)},
                { label:"Status",         value:<StatusBadge status={selected.status} /> },
              ]} />
            </div>

            {selected.status === "Suspended" || selected.status === "Terminated" ? (
              <div className={s.lockedBanner}>
                This employee's record is locked. Editing requires special HR Admin permission.
              </div>
            ) : (
              <div className={s.detailActions}>
                <button className={s.btnOutlineSm}>Edit Record</button>
                <button className={s.btnOutlineSm}>Export Profile</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: PAYROLL
// ─────────────────────────────────────────────────────────────────────────────
function PayrollTab() {
  const [search,   setSearch]   = useState("");
  const [selected, setSelected] = useState(null);
  const [showNew,  setShowNew]  = useState(false);
  const [newSalary,setNewSalary]= useState({ basicSalary:"", allowances:"", deductions:"", tax:"", insurance:"", reason:"" });

  const filtered = useMemo(() => EMPLOYEES_COMPLIANCE.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.dept.toLowerCase().includes(search.toLowerCase())
  ), [search]);

  const history = selected ? (PAYROLL_HISTORY[selected.id] || []) : [];
  const current = history[0];

  const handleNewRecord = () => {
    alert(`New payroll record submitted for ${selected.name}.\nStatus: Draft — Pending Approval\n\nOld records remain locked and immutable.`);
    setShowNew(false);
    setNewSalary({ basicSalary:"", allowances:"", deductions:"", tax:"", insurance:"", reason:"" });
  };

  return (
    <div className={s.splitLayout}>
      <div className={s.splitList}>
        <TabSearch value={search} onChange={setSearch} placeholder="Search employees..." />
        {filtered.map(emp => {
          const cur = (PAYROLL_HISTORY[emp.id]||[])[0];
          return (
            <div key={emp.id}
              className={`${s.splitRow} ${selected?.id===emp.id ? s.splitRowActive:""}`}
              onClick={()=>{ setSelected(emp); setShowNew(false); }} role="button" tabIndex={0}>
              <EmpAvatar emp={emp} size={34} />
              <div style={{flex:1}}>
                <p className={s.splitName}>{emp.name}</p>
                <p className={s.splitSub}>{emp.dept}</p>
              </div>
              <span className={s.salaryTag}>{cur ? fmt(cur.net) : "—"}</span>
            </div>
          );
        })}
      </div>

      <div className={s.splitDetail}>
        {!selected ? (
          <div className={s.splitEmpty}><p>Select an employee</p></div>
        ) : (
          <div>
            <div className={s.detailHeader}>
              <EmpAvatar emp={selected} size={40} />
              <div><h4 className={s.detailName}>{selected.name}</h4><p className={s.detailDept}>{selected.dept}</p></div>
              {current && <StatusBadge status={current.status} />}
            </div>

            {current && (
              <div className={s.detailSection}>
                <h5 className={s.detailSectionTitle}>Current Payroll — v{current.version} <span className={s.lockedTag}>Locked</span></h5>
                <InfoGrid items={[
                  { label:"Basic Salary",    value:fmt(current.basicSalary) },
                  { label:"Allowances",      value:fmt(current.allowances)  },
                  { label:"Deductions",      value:fmt(current.deductions)  },
                  { label:"Tax",             value:fmt(current.tax)         },
                  { label:"Insurance",       value:fmt(current.insurance)   },
                  { label:"Net Salary",      value:<strong style={{color:"#2F9E44"}}>{fmt(current.net)}</strong> },
                  { label:"Effective Date",  value:fmtD(current.effectiveDate) },
                  { label:"Approved By",     value:current.approvedBy       },
                  { label:"Approved At",     value:fmtD(current.approvedAt) },
                  { label:"Change Reason",   value:current.changeReason     },
                ]} />
                <div className={s.lockedBanner}>This payroll record is locked. No direct edits allowed. Create a new record below.</div>
              </div>
            )}

            <div className={s.detailSection}>
              <h5 className={s.detailSectionTitle}>Salary History (Immutable)</h5>
              {history.map((rec, i) => (
                <div key={rec.id} className={`${s.historyRow} ${i===0 ? s.historyRowCurrent:""}`}>
                  <div>
                    <span className={s.historyVersion}>v{rec.version}</span>
                    <span className={s.historyDate}>{fmtD(rec.effectiveDate)}</span>
                    <span className={s.historyReason}>{rec.changeReason}</span>
                  </div>
                  <div className={s.historyRight}>
                    <span className={s.historyNet}>{fmt(rec.net)}</span>
                    <span className={s.historyBy}>by {rec.changedBy}</span>
                    <StatusBadge status={rec.status} />
                  </div>
                </div>
              ))}
            </div>

            {!showNew ? (
              <div className={s.detailActions}>
                <button className={s.btnPrimarySm} onClick={()=>setShowNew(true)}>+ New Payroll Record</button>
                <button className={s.btnOutlineSm} onClick={()=>{}}>Download Payslip</button>
              </div>
            ) : (
              <div className={s.detailSection}>
                <h5 className={s.detailSectionTitle}>New Payroll Record (Draft)</h5>
                <div className={s.newPayrollGrid}>
                  {[["Basic Salary","basicSalary"],["Allowances","allowances"],["Deductions","deductions"],["Tax","tax"],["Insurance","insurance"]].map(([label,field])=>(
                    <div key={field} className={s.formGroup}>
                      <label className={s.fLabel}>{label} ($)</label>
                      <input className={s.fInput} type="number" value={newSalary[field]} onChange={e=>setNewSalary(p=>({...p,[field]:e.target.value}))} placeholder="0" />
                    </div>
                  ))}
                  <div className={`${s.formGroup} ${s.formGroupFull}`}>
                    <label className={s.fLabel}>Change Reason * (required)</label>
                    <input className={s.fInput} value={newSalary.reason} onChange={e=>setNewSalary(p=>({...p,reason:e.target.value}))} placeholder="e.g. Annual raise, promotion..." />
                  </div>
                </div>
                <div className={s.detailActions}>
                  <button className={s.btnGhostSm} onClick={()=>setShowNew(false)}>Cancel</button>
                  <button className={s.btnPrimarySm} onClick={handleNewRecord} disabled={!newSalary.reason.trim()}>Submit for Approval</button>
                </div>
                <p className={s.formHint}>This will create a new versioned record. Old records remain immutable.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: LEAVE
// ─────────────────────────────────────────────────────────────────────────────
function LeaveTab() {
  const [filter,    setFilter]    = useState("All");
  const [requests,  setRequests]  = useState(LEAVE_REQUESTS);
  const [rejectId,  setRejectId]  = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const filtered = useMemo(() =>
    filter==="All" ? requests : requests.filter(r=>r.status===filter), [filter, requests]);

  const handleApprove = (id) => {
    setRequests(prev => prev.map(r => r.id===id
      ? { ...r, status:"Approved", approvedBy:CURRENT_USER.name, approvedAt:new Date().toISOString() }
      : r));
  };
  const handleReject = (id) => {
    if (!rejectReason.trim()) return;
    setRequests(prev => prev.map(r => r.id===id
      ? { ...r, status:"Rejected", approvedBy:CURRENT_USER.name, approvedAt:new Date().toISOString() }
      : r));
    setRejectId(null); setRejectReason("");
  };

  const counts = { All:requests.length, Pending:requests.filter(r=>r.status==="Pending").length, Approved:requests.filter(r=>r.status==="Approved").length, Rejected:requests.filter(r=>r.status==="Rejected").length };

  return (
    <div>
      <SectionTitle>Leave Balances</SectionTitle>
      <div className={s.leaveBalancesGrid}>
        {EMPLOYEES_COMPLIANCE.map(emp => (
          <div key={emp.id} className={s.leaveBalanceCard}>
            <div className={s.leaveBalanceHeader}>
              <EmpAvatar emp={emp} size={28} />
              <p className={s.leaveBalanceName}>{emp.name}</p>
            </div>
            {[
              { type:"Annual",   bal:emp.leaveBalance.annual,   used:emp.leaveUsed.annual   },
              { type:"Sick",     bal:emp.leaveBalance.sick,     used:emp.leaveUsed.sick     },
              { type:"Personal", bal:emp.leaveBalance.personal, used:emp.leaveUsed.personal },
            ].map(lb=>(
              <div key={lb.type} className={s.leaveBalanceRow}>
                <span className={s.leaveBalanceType}>{lb.type}</span>
                <ProgressBar value={lb.bal-lb.used} max={lb.bal} color={lb.bal-lb.used<lb.bal*0.2?"#FA5252":"#3B5BDB"} />
                <span className={s.leaveBalanceLeft}>{lb.bal-lb.used}d left</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className={s.leaveRequestsHeader}>
        <SectionTitle>Leave Requests</SectionTitle>
        <div className={s.filterChips}>
          {Object.entries(counts).map(([k,v])=>(
            <button key={k} className={`${s.chip} ${filter===k?s.chipActive:""}`} onClick={()=>setFilter(k)}>
              {k} <span className={s.chipCount}>{v}</span>
            </button>
          ))}
        </div>
      </div>

      <div className={s.listStack}>
        {filtered.map(req => {
          const isPending  = req.status==="Pending";
          const isRejecting = rejectId===req.id;
          return (
            <div key={req.id} className={s.leaveRow}>
              <EmpAvatar emp={req} size={34} />
              <div className={s.leaveInfo}>
                <p className={s.leaveName}>{req.empName}</p>
                <p className={s.leaveMeta}>{req.type} · {fmtD(req.from)} – {fmtD(req.to)} · {req.days}d · {req.reason}</p>
                {req.approvedBy && <p className={s.leaveApprover}>{req.status} by {req.approvedBy} on {fmtD(req.approvedAt)}</p>}
                {req.attachments && <span className={s.attachBadge}>Doc attached</span>}
              </div>
              <StatusBadge status={req.status} />
              {isPending && !isRejecting && (
                <div className={s.leaveActionBtns}>
                  <button className={s.approveBtn} onClick={()=>handleApprove(req.id)}>Approve</button>
                  <button className={s.rejectBtn}  onClick={()=>setRejectId(req.id)}>Reject</button>
                </div>
              )}
              {isRejecting && (
                <div className={s.rejectWrap}>
                  <input className={s.fInput} style={{width:160}} value={rejectReason} onChange={e=>setRejectReason(e.target.value)} placeholder="Reason for rejection *" />
                  <button className={s.rejectBtn} onClick={()=>handleReject(req.id)} disabled={!rejectReason.trim()}>Confirm</button>
                  <button className={s.btnGhostSm} onClick={()=>setRejectId(null)}>Cancel</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className={s.formHint}>Compliance enforced: No self-approval · Reject requires reason · Approved leaves auto-lock</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: ATTENDANCE
// ─────────────────────────────────────────────────────────────────────────────
function AttendanceTab() {
  return (
    <div>
      <SectionTitle>Daily Attendance — Oct 28, 2024</SectionTitle>
      <div className={s.listStack}>
        {ATTENDANCE.map(rec => (
          <div key={rec.id} className={s.attendanceRow}>
            <EmpAvatar emp={{ avatar:rec.avatar, color:rec.color }} size={34} />
            <div className={s.attendanceInfo}>
              <p className={s.attendanceName}>{rec.empName}</p>
              <p className={s.attendanceMeta}>
                {rec.checkIn ? `In: ${rec.checkIn}` : "—"} {rec.checkOut ? `· Out: ${rec.checkOut}` : ""}
                {rec.hours>0 ? ` · ${rec.hours.toFixed(1)}h` : ""}
                {rec.overtime>0 ? <span style={{color:"#F59F00"}}> · OT: {rec.overtime.toFixed(1)}h</span> : ""}
              </p>
              {rec.manualOverride && (
                <p className={s.overrideNote}>Manual override by {rec.overrideBy}: "{rec.overrideReason}"</p>
              )}
            </div>
            <StatusBadge status={rec.status} />
            {!rec.manualOverride && rec.status!=="Suspended" && (
              <button className={s.btnOutlineSm} onClick={()=>alert("Override logged to Audit trail")}>Override</button>
            )}
          </div>
        ))}
      </div>
      <p className={s.formHint}>All manual overrides are logged to the Audit trail with reason and user.</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: TRAINING
// ─────────────────────────────────────────────────────────────────────────────
function TrainingTab() {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => EMPLOYEES_COMPLIANCE.filter(e =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.dept.toLowerCase().includes(search.toLowerCase())
  ), [search]);

  return (
    <div>
      <div className={s.tabToolbar}><TabSearch value={search} onChange={setSearch} placeholder="Search employees..." /></div>
      <div className={s.listStack}>
        {filtered.map(emp => {
          const done  = emp.trainings.filter(t=>t.status==="Completed").length;
          const total = emp.trainings.length;
          const hasOverdue = emp.trainings.some(t=>t.status==="Overdue");
          return (
            <div key={emp.id} className={s.trainingCard}>
              <div className={s.trainingEmpRow}>
                <EmpAvatar emp={emp} size={34} />
                <div><p className={s.trainingEmpName}>{emp.name}</p><p className={s.trainingEmpDept}>{emp.dept}</p></div>
                <div className={s.trainingProgress}>
                  <ProgressBar value={done} max={total} color={hasOverdue?"#FA5252":done===total?"#2F9E44":"#3B5BDB"} />
                </div>
              </div>
              <div className={s.trainingList}>
                {emp.trainings.map((t,i) => (
                  <div key={i} className={s.trainingItem}>
                    <span className={s.trainingName}>{t.name}</span>
                    <span className={s.trainingMandatory}>{t.mandatory ? "Mandatory" : "Optional"}</span>
                    <span className={s.trainingDue}>Due: {fmtD(t.due)}</span>
                    {t.score!==null && <span className={s.trainingScore}>Score: {t.score}%</span>}
                    {t.certExpiry && <span className={s.trainCertExpiry}>Cert expires: {fmtD(t.certExpiry)}</span>}
                    <StatusBadge status={t.status} />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className={s.formHint}>Mandatory training overdue = access restrictions apply. History records are permanent.</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: POLICIES
// ─────────────────────────────────────────────────────────────────────────────
function PoliciesTab() {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => POLICIES.filter(p =>
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    p.category.toLowerCase().includes(search.toLowerCase())
  ), [search]);

  return (
    <div>
      <div className={s.tabToolbar}>
        <TabSearch value={search} onChange={setSearch} placeholder="Search policies..." />
        <button className={s.btnOutlineSm}>+ New Policy</button>
      </div>
      <div className={s.listStack}>
        {filtered.map(p => (
          <div key={p.id} className={s.policyRow}>
            <div className={s.policyInfo}>
              <p className={s.policyTitle}>{p.title}</p>
              <p className={s.policySub}>{p.category} · Updated {p.updated} {p.mandatoryTraining && <span className={s.mandatoryTag}>Mandatory Training</span>}</p>
            </div>
            <div className={s.policyMeta}>
              {p.acknowledged>0 && (
                <div className={s.ackWrap}>
                  <span className={s.ackLabel}>Acknowledged</span>
                  <ProgressBar value={p.acknowledged} max={100} color={p.acknowledged===100?"#2F9E44":"#3B5BDB"} />
                </div>
              )}
              <StatusBadge status={p.status} />
              <button className={s.iconActionBtn} title="Download">Download</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: DOCUMENTS
// ─────────────────────────────────────────────────────────────────────────────
function DocumentsTab() {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => DOCUMENTS.filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.category.toLowerCase().includes(search.toLowerCase())
  ), [search]);

  return (
    <div>
      <div className={s.tabToolbar}>
        <TabSearch value={search} onChange={setSearch} placeholder="Search documents..." />
        <button className={s.btnOutlineSm}>Upload</button>
      </div>
      <div className={s.listStack}>
        {filtered.map(doc => (
          <div key={doc.id} className={s.docRow}>
            <span className={s.docTypeIcon}>{doc.type}</span>
            <div className={s.docInfo}>
              <p className={s.docName}>{doc.name}</p>
              <p className={s.docSub}>{doc.type} · {doc.size} · Updated {doc.updated}</p>
            </div>
            <span className={s.docCategory}>{doc.category}</span>
            <button className={s.iconActionBtn} onClick={()=>alert(`Downloading: ${doc.name}`)}>Download</button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: ACCESS CONTROL
// ─────────────────────────────────────────────────────────────────────────────
function AccessTab() {
  const [selected, setSelected] = useState(null);
  return (
    <div>
      <div className={s.accessInfo}>
        <p className={s.formHint}>Role-based access control. Separation of duties enforced. Salary approver is not salary editor.</p>
      </div>
      <div className={s.splitLayout} style={{minHeight:360}}>
        <div className={s.splitList}>
          {ACCESS_ROLES.map(role => (
            <div key={role.id}
              className={`${s.splitRow} ${selected?.id===role.id?s.splitRowActive:""}`}
              onClick={()=>setSelected(role)} role="button" tabIndex={0}>
              <div style={{flex:1}}>
                <p className={s.splitName}>{role.role}</p>
                <p className={s.splitSub}>{role.users.length} user{role.users.length!==1?"s":""}</p>
              </div>
              <span className={s.permCount}>{role.permissions.length} perms</span>
            </div>
          ))}
        </div>
        <div className={s.splitDetail}>
          {!selected ? (
            <div className={s.splitEmpty}><p>Select a role</p></div>
          ) : (
            <div>
              <h4 className={s.detailName}>{selected.role}</h4>
              <div className={s.detailSection}>
                <h5 className={s.detailSectionTitle}>Assigned Users</h5>
                {selected.users.map(u=>(
                  <div key={u} className={s.userRow}><span className={s.userDot}/>{u}</div>
                ))}
              </div>
              <div className={s.detailSection}>
                <h5 className={s.detailSectionTitle}>Permissions</h5>
                <div className={s.permGrid}>
                  {selected.permissions.map(p=>(
                    <div key={p} className={s.permItem}>
                      <span className={s.permCheck}>+</span>
                      <span className={s.permLabel}>{PERMISSION_LABELS[p]||p}</span>
                    </div>
                  ))}
                </div>
                {ACCESS_ROLES.filter(r=>r.id!==selected.id).flatMap(r=>r.permissions).filter((p,i,a)=>a.indexOf(p)===i && !selected.permissions.includes(p)).length > 0 && (
                  <div className={s.deniedPerms}>
                    <p className={s.deniedLabel}>No access to:</p>
                    {ACCESS_ROLES.filter(r=>r.id!==selected.id).flatMap(r=>r.permissions).filter((p,i,a)=>a.indexOf(p)===i && !selected.permissions.includes(p)).map(p=>(
                      <div key={p} className={s.permItem} style={{opacity:0.5}}>
                        <span style={{color:"#FA5252"}}>-</span>
                        <span className={s.permLabel}>{PERMISSION_LABELS[p]||p}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: AUDIT LOGS
// ─────────────────────────────────────────────────────────────────────────────
function AuditTab() {
  const [search, setSearch] = useState("");
  const [filterAction, setFilterAction] = useState("All");
  const actions = ["All","CREATE","UPDATE","APPROVE","REJECT","OVERRIDE","LOCK","SUBMIT"];

  const filtered = useMemo(() => AUDIT_LOGS.filter(log => {
    const matchSearch = !search || log.user.toLowerCase().includes(search.toLowerCase()) || log.entity.toLowerCase().includes(search.toLowerCase()) || log.action.toLowerCase().includes(search.toLowerCase());
    const matchAction = filterAction==="All" || log.action===filterAction;
    return matchSearch && matchAction;
  }), [search, filterAction]);

  const actionColor = { CREATE:"#2F9E44", UPDATE:"#3B5BDB", APPROVE:"#2F9E44", REJECT:"#FA5252", OVERRIDE:"#F59F00", LOCK:"#845EF7", SUBMIT:"#4DABF7" };

  return (
    <div>
      <div className={s.tabToolbar}>
        <TabSearch value={search} onChange={setSearch} placeholder="Search user, entity, action..." />
        <div className={s.filterChips} style={{marginBottom:0}}>
          {actions.map(a=>(
            <button key={a} className={`${s.chip} ${filterAction===a?s.chipActive:""}`} onClick={()=>setFilterAction(a)}>{a}</button>
          ))}
        </div>
      </div>
      <p className={s.formHint}>Audit logs are immutable. No deletion or modification allowed.</p>
      <div className={s.auditList}>
        {filtered.map(log => (
          <div key={log.id} className={s.auditRow}>
            <div className={s.auditAction} style={{ color: actionColor[log.action]||"#495057" }}>{log.action}</div>
            <div className={s.auditBody}>
              <p className={s.auditMain}>
                <strong>{log.user}</strong> — {log.entity}
                {log.oldVal && <><span className={s.auditOld}> {log.oldVal}</span> — <span className={s.auditNew}>{log.newVal}</span></>}
                {!log.oldVal && log.newVal && <span className={s.auditNew}> {log.newVal}</span>}
              </p>
              {log.reason && <p className={s.auditReason}>Reason: {log.reason}</p>}
              <p className={s.auditMeta}>{log.at} · IP: {log.ip}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: REPORTS
// ─────────────────────────────────────────────────────────────────────────────
function ReportsTab() {
  const reports = [
    { id:"r1", title:"Salary Changes Report",       desc:"All payroll version changes with before/after values, approvers, and timestamps.", lastRun:"Oct 28, 2024" },
    { id:"r2", title:"Training Compliance Report",  desc:"Completion rates per employee, overdue mandatory trainings, expiring certificates.", lastRun:"Oct 25, 2024" },
    { id:"r3", title:"Attendance Anomalies Report", desc:"Late arrivals, early departures, manual overrides, overtime summaries.", lastRun:"Oct 28, 2024" },
    { id:"r4", title:"User Activity Report",        desc:"All HR system actions per user — login, edits, approvals.", lastRun:"Oct 27, 2024" },
    { id:"r5", title:"Leave Balance Report",        desc:"Leave taken vs. remaining per employee and department.", lastRun:"Oct 20, 2024" },
    { id:"r6", title:"Contract Expiry Report",      desc:"Employees with contracts expiring in the next 30/60/90 days.", lastRun:"Oct 28, 2024" },
    { id:"r7", title:"Access Control Audit",        desc:"Current role assignments, permission changes, separation of duties check.", lastRun:"Oct 15, 2024" },
    { id:"r8", title:"Payroll Compliance Summary",  desc:"Total payroll, deductions, tax, insurance breakdown by department.", lastRun:"Oct 28, 2024" },
  ];

  return (
    <div>
      <p className={s.formHint}>Reports are generated on demand. All data is role-gated — salary data masked for non-HR/Finance roles.</p>
      <div className={s.reportsGrid}>
        {reports.map(r => (
          <div key={r.id} className={s.reportCard}>
            <div className={s.reportInfo}>
              <p className={s.reportTitle}>{r.title}</p>
              <p className={s.reportDesc}>{r.desc}</p>
              <p className={s.reportLastRun}>Last run: {r.lastRun}</p>
            </div>
            <div className={s.reportActions}>
              <button className={s.btnPrimarySm} onClick={()=>alert(`Generating: ${r.title}`)}>Run</button>
              <button className={s.btnOutlineSm} onClick={()=>alert(`Exporting: ${r.title}`)}>Export</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN MODAL
// ─────────────────────────────────────────────────────────────────────────────
export default function ComplianceModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState("overview");
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key==="Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  useEffect(() => { if (isOpen) setActiveTab("overview"); }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className={s.overlay} ref={overlayRef} onClick={e=>{ if (e.target===overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal}>

        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div>
              <h2 className={s.modalTitle}>HR Compliance Center</h2>
              <p className={s.modalSub}>Employees · Payroll · Leave · Attendance · Training · Policies · Audit · Reports</p>
            </div>
          </div>
          <div className={s.headerRight}>
            <span className={s.currentUser}>{CURRENT_USER.name} · {CURRENT_USER.role}</span>
            <button className={s.closeBtn} onClick={onClose}>x</button>
          </div>
        </div>

        <div className={s.tabBar} role="tablist">
          {TABS.map(tab => (
            <button key={tab.id} role="tab" aria-selected={activeTab===tab.id}
              className={`${s.tab} ${activeTab===tab.id?s.tabActive:""}`}
              onClick={()=>setActiveTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </div>

        <div className={s.tabContent} key={activeTab}>
          {activeTab==="overview"   && <OverviewTab   onTab={setActiveTab} />}
          {activeTab==="employees"  && <EmployeesTab  />}
          {activeTab==="payroll"    && <PayrollTab    />}
          {activeTab==="leave"      && <LeaveTab      />}
          {activeTab==="attendance" && <AttendanceTab />}
          {activeTab==="training"   && <TrainingTab   />}
          {activeTab==="policies"   && <PoliciesTab   />}
          {activeTab==="documents"  && <DocumentsTab  />}
          {activeTab==="access"     && <AccessTab     />}
          {activeTab==="audit"      && <AuditTab      />}
          {activeTab==="reports"    && <ReportsTab    />}
        </div>

      </div>
    </div>
  );
}