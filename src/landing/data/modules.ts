export interface ERPModule {
  id: string;
  name: string;
  iconName: string;
  description: string;
  stats: { label: string; value: string };
  highlights: string[];
}

export const erpModules: ERPModule[] = [
  {
    id: "finance",
    name: "Finance & Accounting",
    iconName: "Wallet",
    description: "Enterprise-grade general ledger, automated invoicing, multi-entity consolidation, tax management, and intelligent cash runway projections.",
    stats: { label: "Transactions Processed", value: "99.8%" },
    highlights: ["Automated Reconciliation", "Tax Compliance Routing", "Dynamic Cost Analytics"]
  },
  {
    id: "hr",
    name: "Human Resources",
    iconName: "UserCheck",
    description: "Manage global recruitment, dynamic talent onboarding, automated performance tracking, shifts, and localized compliance payroll.",
    stats: { label: "Onboarding Speedup", value: "12x Faster" },
    highlights: ["Global Payroll System", "Employee Directory", "Performance Scoring"]
  },
  {
    id: "sales",
    name: "Sales Force Automation",
    iconName: "Percent",
    description: "Optimize deals, manage quotes, configure pricing models, automate lead routing, and calculate automated commission calculations.",
    stats: { label: "Conversion Lift", value: "+28% YoY" },
    highlights: ["Interactive Quotation", "Custom Deal Flows", "Territory Mapping"]
  },
  {
    id: "crm",
    name: "Customer Relationship",
    iconName: "HeartHandshake",
    description: "Unified 360° view of clients, sentiment analysis, contact timelines, integrated communication channels, and life-cycle valuation.",
    stats: { label: "CSAT Score Improved", value: "4.9/5" },
    highlights: ["Sentiment Tracking", "Omnichannel Inbox", "Interaction Timeline"]
  },
  {
    id: "inventory",
    name: "Smart Warehouse & Inventory",
    iconName: "Boxes",
    description: "Multi-location inventory tracking, automated stock forecasting, barcode/RFID integration, and smart order fulfillment routes.",
    stats: { label: "Stockout Incidents", value: "-94%" },
    highlights: ["Dynamic Safety Stock", "Bin-Level Tracking", "Shipment Monitoring"]
  },
  {
    id: "procurement",
    name: "Procurement & Sourcing",
    iconName: "ShieldAlert",
    description: "Automate purchase orders, evaluate suppliers based on historical speed and cost, track RFP portals, and optimize supply-chain costs.",
    stats: { label: "Sourcing Savings", value: "18% Avg" },
    highlights: ["Supplier Ratings", "Auto Purchase Orders", "Contract Repository"]
  },
  {
    id: "projects",
    name: "Project Management",
    iconName: "Briefcase",
    description: "Collaborative Gantt charts, agile sprints, time tracking, resource loading heatmaps, and budget variance tracking.",
    stats: { label: "On-time Delivery", value: "98.2%" },
    highlights: ["Visual Gantt & Sprints", "Time Sheet Logging", "Resource Heatmaps"]
  },
  {
    id: "manufacturing",
    name: "Manufacturing & MRP",
    iconName: "Cpu",
    description: "Bill of Materials (BOM), work-order scheduling, production routing, quality control checks, and machine telemetry integration.",
    stats: { label: "OEE Score Avg", value: "88.4%" },
    highlights: ["Dynamic BOM Builder", "Machine Telemetry", "Quality Auditing"]
  },
  {
    id: "support",
    name: "Service & Support Desk",
    iconName: "Headphones",
    description: "Automated ticket categorization, canned AI draft replies, customer knowledge base search, SLA breach alerts, and customer surveys.",
    stats: { label: "SLA Adherence", value: "99.9%" },
    highlights: ["AI Ticket Auto-Reply", "SLA Management", "Feedback Loop"]
  },
  {
    id: "analytics",
    name: "Enterprise Analytics",
    iconName: "BarChart3",
    description: "Run custom SQL queries in natural language, schedule reports, generate interactive dashboards, and share board-ready PDFs.",
    stats: { label: "Report Run Time", value: "<1.2s" },
    highlights: ["Natural Language SQL", "Automated PDF Delivery", "Custom Pivot Widgets"]
  },
  {
    id: "administration",
    name: "Governance & Security",
    iconName: "ShieldCheck",
    description: "Role-Based Access Control (RBAC), multi-factor authentication, enterprise audit logs, GDPR/HIPAA compliance templates, and SSO.",
    stats: { label: "Security Incidents", value: "0 Logs" },
    highlights: ["MFA & SAML SSO", "Immutability Logs", "Permission Auditing"]
  }
];
