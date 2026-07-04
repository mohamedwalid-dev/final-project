export interface FAQItem {
  id: string;
  question: string;
  answer: string;
}

export const faqs: FAQItem[] = [
  {
    id: "faq-1",
    question: "What is an ERP System?",
    answer: "Enterprise Resource Planning (ERP) is centralized software designed to manage and automate all core business processes. It integrates Finance, Human Resources, Supply Chain, Manufacturing, Sales, Projects, and Customer Relations into a unified single source of truth, eliminating information silos."
  },
  {
    id: "faq-2",
    question: "How does Artificial Intelligence improve ERP operations?",
    answer: "Traditional ERP systems only record transactions in hindsight. Prime acts with foresight. By incorporating machine learning algorithms, it automatically forecasts revenue runway, flags anomalous account postings, schedules predictive maintenance for machinery, drafts intelligent response tickets, and scores lead priority."
  },
  {
    id: "faq-3",
    question: "Can we migrate our existing system data into this platform?",
    answer: "Absolutely. We provide integrated data-mapping wizard templates for popular systems like SAP, Oracle, NetSuite, QuickBooks, and Salesforce. Our technical migration tools automatically map ledgers, employee records, vendor contacts, and inventory catalogs, ensuring high data integrity with zero operational downtime."
  },
  {
    id: "faq-4",
    question: "Is our business data secure on your system?",
    answer: "Security is our highest architectural priority. All data is encrypted in transit using TLS 1.3 and at rest with AES-256 encryption. We implement standard Role-Based Access Control (RBAC), multi-factor authentication (MFA), SAML SSO, and immutable audit logs. Our hosting environment maintains SOC 2 Type II, ISO 27001, and GDPR compliance."
  },
  {
    id: "faq-5",
    question: "Do you offer localized cloud hosting options?",
    answer: "Yes, we host our platform on multi-region, highly redundant cloud nodes in AWS, Google Cloud, and Azure. Clients can select exactly where their databases and applications reside (e.g., US East, EU West, Asia Pacific) to comply with local data-residency laws like GDPR and CCPA, maintaining a high 99.99% uptime SLA."
  },
  {
    id: "faq-6",
    question: "Can I integrate third-party software with Prime?",
    answer: "Yes, our modern API gateway exposes developer-friendly, fully documented RESTful and GraphQL endpoints. We support out-of-the-box native integrations for popular tools including Slack, Salesforce, Microsoft 365, HubSpot, Jira, Shopify, and various payment portals (such as Stripe)."
  }
];
