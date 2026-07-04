export interface Feature {
  id: string;
  title: string;
  description: string;
  iconName: string;
  badge?: string;
  gradient: string;
}

export const features: Feature[] = [
  {
    id: "ai-analytics",
    title: "AI Analytics & Forecasting",
    description: "Predict customer demand, financial performance, and market trends with advanced machine learning algorithms tailored to your business.",
    iconName: "Brain",
    badge: "Advanced AI",
    gradient: "from-cyan-500 to-blue-600"
  },
  {
    id: "finance",
    title: "Finance & Automated Ledger",
    description: "Automate accounting entries, manage multi-currency ledgers, predict cash flow runway, and run complex financial consolidations instantly.",
    iconName: "DollarSign",
    gradient: "from-blue-600 to-indigo-600"
  },
  {
    id: "hr-management",
    title: "Intelligent HR & Payroll",
    description: "Automate talent acquisition, optimize payroll across multiple jurisdictions, monitor employee engagement, and manage global workforce scheduling.",
    iconName: "Users",
    gradient: "from-indigo-600 to-violet-600"
  },
  {
    id: "sales-crm",
    title: "Hyper-Personalized CRM",
    description: "Score leads with AI precision, track sales pipelines in real-time, generate automated email follow-ups, and elevate your customer relations.",
    iconName: "TrendingUp",
    badge: "Highly Rated",
    gradient: "from-violet-600 to-fuchsia-600"
  },
  {
    id: "inventory",
    title: "Smart Inventory & Supply",
    description: "Prevent stockouts with automated reordering, optimize warehouse layout, track shipments in real-time, and manage inventory dynamically.",
    iconName: "Package",
    gradient: "from-fuchsia-600 to-pink-600"
  },
  {
    id: "procurement",
    title: "Automated Procurement",
    description: "Streamline purchase requests, evaluate vendors automatically, analyze spending patterns, and negotiate better terms with smart intelligence.",
    iconName: "ShoppingCart",
    gradient: "from-pink-600 to-rose-600"
  },
  {
    id: "customer-support",
    title: "AI Customer Support",
    description: "Resolve tier-1 support tickets instantly using AI agents trained on your product docs, while routing complex issues to live agents.",
    iconName: "MessageSquare",
    badge: "24/7 Autopilot",
    gradient: "from-cyan-500 to-teal-500"
  },
  {
    id: "reporting",
    title: "Unified Reporting Hub",
    description: "Generate boardroom-ready executive summaries, customize interactive tables, and build pixel-perfect operational dashboards instantly.",
    iconName: "LayoutDashboard",
    gradient: "from-emerald-500 to-teal-600"
  }
];
