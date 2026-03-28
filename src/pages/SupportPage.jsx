// ─── Pages/SupportPage.jsx ────────────────────────────────────────────────────
// ✅ Full Support / Ticket Management page
// ✅ Inbound queue with search, filters (All, Urgent, Pending)
// ✅ Ticket detail chat panel with real-time message simulation
// ✅ AI Suggestions with quick-action chips
// ✅ Canned Responses, Call, Verify Identity actions
// ✅ New Ticket modal, animations throughout

import { useState, useEffect, useCallback, useRef } from "react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header  from "../components/Finance/Layout/Header";
import s from "../styles/SupportPage.module.css";

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
const TICKETS = [
  {
    id: "TK-4821",
    name: "Sarah Jenkins",
    avatar: "SJ",
    avatarColor: "#4A6FDC",
    time: "12m ago",
    subject: "Issue with license key renewal",
    preview: "I tried the key you sent but it says 'Invalid Format'...",
    tags: ["urgent", "#TK-4821"],
    tagColors: ["#FA5252", "#868E96"],
    priority: "urgent",
    status: "open",
    location: "San Francisco, CA",
    lastSeen: "Last active 2m ago",
    messages: [
      {
        id: "m1", from: "customer", text: "Hi support team, I'm trying to renew my enterprise license but the checkout page keeps refreshing.", time: "10:14 AM",
      },
      {
        id: "m2", from: "agent", text: "Hello Sarah! I'm sorry for the frustration. Let me check the payment logs for your account. One moment please.", time: "10:15 AM",
      },
      {
        id: "m3", system: true, text: "AGENT ALEX STERLING JOINED THE CONVERSATION", time: "10:17 AM",
      },
      {
        id: "m4", from: "agent", text: "I've generated a direct payment link for you to bypass the checkout page refresh issue. Here is a manual key to use as well: SYNERGY-PRO-2024-X0GL", time: "10:30 AM",
      },
      {
        id: "m5", from: "customer", text: "I tried the key you sent but it says 'Invalid Format' when I paste it into the dashboard.", time: "10:22 AM",
      },
    ],
  },
  {
    id: "TK-4789",
    name: "Marcus Thorne",
    avatar: "MT",
    avatarColor: "#7048E8",
    time: "45m ago",
    subject: "Data export taking too long",
    preview: "Is there a limit on the CSV export size?",
    tags: ["high", "#TK-4789"],
    tagColors: ["#F59F00", "#868E96"],
    priority: "high",
    status: "pending",
    location: "Austin, TX",
    lastSeen: "Last active 45m ago",
    messages: [
      { id: "m1", from: "customer", text: "I've been trying to export a large dataset but it keeps timing out after 5 minutes.", time: "9:30 AM" },
      { id: "m2", from: "agent", text: "Hi Marcus! Our CSV export is limited to 50,000 rows per request. Could you tell me how many rows you're trying to export?", time: "9:42 AM" },
      { id: "m3", from: "customer", text: "I need about 200,000 rows. Is there a workaround?", time: "9:45 AM" },
    ],
  },
  {
    id: "TK-4785",
    name: "Elena Rodriguez",
    avatar: "ER",
    avatarColor: "#0CA678",
    time: "2h ago",
    subject: "Invoice #INV-2024-001 Query",
    preview: "I see a duplicate charge on my statement.",
    tags: ["medium", "#TK-4785"],
    tagColors: ["#3B5BDB", "#868E96"],
    priority: "medium",
    status: "pending",
    location: "Miami, FL",
    lastSeen: "Last active 2h ago",
    messages: [
      { id: "m1", from: "customer", text: "Hello! I received two charges for the same invoice INV-2024-001. Please help.", time: "8:00 AM" },
      { id: "m2", from: "agent", text: "Hi Elena, I can see the duplicate charge on our end. I'm initiating a refund for the extra charge now.", time: "8:15 AM" },
    ],
  },
  {
    id: "TK-4780",
    name: "David Kim",
    avatar: "DK",
    avatarColor: "#E67700",
    time: "3h ago",
    subject: "Access denied to HR module",
    preview: "Urgent: I need to process payroll by EOD.",
    tags: ["urgent", "#TK-4780"],
    tagColors: ["#FA5252", "#868E96"],
    priority: "urgent",
    status: "open",
    location: "Seattle, WA",
    lastSeen: "Last active 3h ago",
    messages: [
      { id: "m1", from: "customer", text: "I can't access the HR module. I get 'Permission Denied'. I need to run payroll today!", time: "7:00 AM" },
    ],
  },
];

const AI_SUGGESTIONS = ["Verify License Key", "Reset Password Link", "Billing FAQ", "Escalate to L2", "Request Screenshot"];

const CANNED_RESPONSES = [
  { id: "c1", label: "License Key Help", text: "Here is a fresh license key for your account: SYNERGY-PRO-2024-XXXX. Please try pasting it without any spaces." },
  { id: "c2", label: "Refund Initiated", text: "I've initiated a full refund for the duplicate charge. You should see it reflected within 3–5 business days." },
  { id: "c3", label: "Escalation Notice", text: "I'm escalating this ticket to our Level 2 technical team. They will contact you within 30 minutes." },
  { id: "c4", label: "Follow-up", text: "Just following up to see if the issue has been resolved. Please let us know if you need any further assistance!" },
];

const PRIORITY_MAP = {
  urgent: { color: "#FA5252", bg: "#FFF5F5", label: "urgent" },
  high:   { color: "#F59F00", bg: "#FFF9DB", label: "high" },
  medium: { color: "#3B5BDB", bg: "#EEF2FF", label: "medium" },
  low:    { color: "#2F9E44", bg: "#EBFBEE", label: "low" },
};

function useAnimateIn(delay = 0) {
  const [v, setV] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const t = setTimeout(() => setV(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return {
    ref,
    style: {
      opacity: v ? 1 : 0,
      transform: v ? "translateY(0)" : "translateY(14px)",
      transition: `opacity 0.4s ease ${delay}ms, transform 0.4s ease ${delay}ms`,
    },
  };
}

// ─── NEW TICKET MODAL ─────────────────────────────────────────────────────────
function NewTicketModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({ name: "", email: "", subject: "", priority: "medium", message: "" });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const fn = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) { setForm({ name: "", email: "", subject: "", priority: "medium", message: "" }); setErrors({}); }
  }, [isOpen]);

  const validate = () => {
    const e = {};
    if (!form.name.trim())    e.name    = "Name is required";
    if (!form.email.trim())   e.email   = "Email is required";
    if (!form.subject.trim()) e.subject = "Subject is required";
    if (!form.message.trim()) e.message = "Message is required";
    return e;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 700));
    const initials = form.name.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2);
    const colors   = ["#4A6FDC", "#7048E8", "#0CA678", "#E67700", "#C92A2A"];
    const color    = colors[Math.floor(Math.random() * colors.length)];
    onCreate({
      id:         `TK-${4800 + Math.floor(Math.random() * 100)}`,
      name:       form.name.trim(),
      avatar:     initials,
      avatarColor: color,
      time:       "just now",
      subject:    form.subject.trim(),
      preview:    form.message.trim().slice(0, 60) + "...",
      tags:       [form.priority, `#TK-NEW`],
      tagColors:  [PRIORITY_MAP[form.priority]?.color ?? "#868E96", "#868E96"],
      priority:   form.priority,
      status:     "open",
      location:   "Unknown",
      lastSeen:   "Last active just now",
      messages:   [{ id: "m1", from: "customer", text: form.message.trim(), time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }],
    });
    setLoading(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className={s.modalOverlay} ref={overlayRef} onClick={(e) => { if (e.target === overlayRef.current) onClose(); }} role="dialog" aria-modal="true">
      <div className={s.modal}>
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon}>🎫</div>
            <div>
              <h2 className={s.modalTitle}>New Support Ticket</h2>
              <p className={s.modalSub}>Fill in customer details and the issue description.</p>
            </div>
          </div>
          <button className={s.modalClose} onClick={onClose}>✕</button>
        </div>

        <div className={s.modalBody}>
          <div className={s.formGrid}>
            <div className={s.formGroup}>
              <label className={s.formLabel}>Customer Name <span className={s.required}>*</span></label>
              <input
                className={`${s.formInput} ${errors.name ? s.formInputError : ""}`}
                value={form.name} onChange={(e) => { setForm((p) => ({ ...p, name: e.target.value })); setErrors((p) => { const n={...p}; delete n.name; return n; }); }}
                placeholder="e.g. Alex Johnson" autoFocus
              />
              {errors.name && <p className={s.fieldError}>{errors.name}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.formLabel}>Email Address <span className={s.required}>*</span></label>
              <input
                type="email" className={`${s.formInput} ${errors.email ? s.formInputError : ""}`}
                value={form.email} onChange={(e) => { setForm((p) => ({ ...p, email: e.target.value })); setErrors((p) => { const n={...p}; delete n.email; return n; }); }}
                placeholder="e.g. alex@example.com"
              />
              {errors.email && <p className={s.fieldError}>{errors.email}</p>}
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel}>Subject <span className={s.required}>*</span></label>
              <input
                className={`${s.formInput} ${errors.subject ? s.formInputError : ""}`}
                value={form.subject} onChange={(e) => { setForm((p) => ({ ...p, subject: e.target.value })); setErrors((p) => { const n={...p}; delete n.subject; return n; }); }}
                placeholder="Brief description of the issue"
              />
              {errors.subject && <p className={s.fieldError}>{errors.subject}</p>}
            </div>

            <div className={s.formGroup}>
              <label className={s.formLabel}>Priority</label>
              <select className={s.formSelect} value={form.priority} onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}>
                {["urgent", "high", "medium", "low"].map((p) => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
              </select>
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel}>Message <span className={s.required}>*</span></label>
              <textarea
                className={`${s.formTextarea} ${errors.message ? s.formInputError : ""}`}
                value={form.message} onChange={(e) => { setForm((p) => ({ ...p, message: e.target.value })); setErrors((p) => { const n={...p}; delete n.message; return n; }); }}
                placeholder="Describe the customer's issue in detail..." rows={4}
              />
              {errors.message && <p className={s.fieldError}>{errors.message}</p>}
            </div>
          </div>
        </div>

        <div className={s.modalFooter}>
          <p className={s.modalFooterNote}>🎫 Ticket will appear in the inbound queue immediately.</p>
          <div className={s.modalFooterActions}>
            <button className={s.btnGhost} onClick={onClose}>Cancel</button>
            <button className={`${s.btn} ${s.btnPrimary}`} onClick={handleSubmit} disabled={loading}>
              {loading ? <><span className={s.spinner} /> Creating...</> : "✓ Create Ticket"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── TICKET CARD ──────────────────────────────────────────────────────────────
function TicketCard({ ticket, isActive, onClick, delay }) {
  const anim = useAnimateIn(delay);
  const pm   = PRIORITY_MAP[ticket.priority] ?? PRIORITY_MAP.medium;
  return (
    <div
      ref={anim.ref}
      className={`${s.ticketCard} ${isActive ? s.ticketCardActive : ""}`}
      style={anim.style}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-selected={isActive}
    >
      <div className={s.ticketCardTop}>
        <div className={s.ticketAvatar} style={{ background: ticket.avatarColor }}>
          {ticket.avatar}
        </div>
        <div className={s.ticketMeta}>
          <span className={s.ticketName}>{ticket.name}</span>
          <span className={s.ticketTime}>{ticket.time}</span>
        </div>
      </div>
      <p className={s.ticketSubject}>{ticket.subject}</p>
      <p className={s.ticketPreview}>{ticket.preview}</p>
      <div className={s.ticketTags}>
        <span className={s.ticketTag} style={{ background: pm.bg, color: pm.color }}>{ticket.tags[0]}</span>
        <span className={s.ticketTagGray}>{ticket.id}</span>
      </div>
    </div>
  );
}

// ─── CHAT BUBBLE ─────────────────────────────────────────────────────────────
function ChatBubble({ msg, agentName }) {
  const anim = useAnimateIn(0);
  if (msg.system) {
    return (
      <div ref={anim.ref} className={s.systemMsg} style={anim.style}>
        <span>{msg.text}</span>
      </div>
    );
  }
  const isAgent = msg.from === "agent";
  return (
    <div ref={anim.ref} className={`${s.bubbleWrap} ${isAgent ? s.bubbleWrapRight : ""}`} style={anim.style}>
      <div className={`${s.bubble} ${isAgent ? s.bubbleAgent : s.bubbleCustomer}`}>
        <p className={s.bubbleText}>{msg.text}</p>
      </div>
      <span className={s.bubbleTime}>{msg.time}</span>
    </div>
  );
}

// ─── CANNED RESPONSES DROPDOWN ────────────────────────────────────────────────
function CannedDropdown({ onSelect }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const fn = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  return (
    <div className={s.cannedWrap} ref={ref}>
      <button className={s.cannedBtn} onClick={() => setOpen((p) => !p)} title="Canned Responses">
        📋 Canned Responses
      </button>
      {open && (
        <div className={s.cannedDropdown}>
          <p className={s.cannedTitle}>Quick Responses</p>
          {CANNED_RESPONSES.map((r) => (
            <button
              key={r.id}
              className={s.cannedItem}
              onClick={() => { onSelect(r.text); setOpen(false); }}
            >
              <span className={s.cannedLabel}>{r.label}</span>
              <span className={s.cannedPreview}>{r.text.slice(0, 55)}…</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function SupportPage() {
  const [activeNav,      setActiveNav]      = useState("support");
  const [tickets,        setTickets]        = useState(TICKETS);
  const [activeTicketId, setActiveTicketId] = useState("TK-4821");
  const [filter,         setFilter]         = useState("All");
  const [search,         setSearch]         = useState("");
  const [draft,          setDraft]          = useState("");
  const [showNewTicket,  setShowNewTicket]  = useState(false);
  const [calling,        setCalling]        = useState(false);
  const [verifying,      setVerifying]      = useState(false);
  const [sending,        setSending]        = useState(false);
  const [toast,          setToast]          = useState(null);
  const [newNotif,       setNewNotif]       = useState(true);
  const chatEndRef  = useRef(null);
  const textareaRef = useRef(null);
  const headerAnim  = useAnimateIn(0);

  const activeTicket = tickets.find((t) => t.id === activeTicketId) ?? tickets[0];

  // scroll to bottom on message change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeTicket?.messages?.length]);

  const showToast = useCallback((msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // ── Filter tickets
  const filteredTickets = tickets.filter((t) => {
    const q = search.toLowerCase();
    const matchSearch = !q || t.name.toLowerCase().includes(q) || t.subject.toLowerCase().includes(q) || t.id.toLowerCase().includes(q);
    const matchFilter =
      filter === "All"     ? true :
      filter === "Urgent"  ? t.priority === "urgent" :
      filter === "Pending" ? t.status   === "pending" : true;
    return matchSearch && matchFilter;
  });

  const urgentCount  = tickets.filter((t) => t.priority === "urgent").length;
  const pendingCount = tickets.filter((t) => t.status === "pending").length;

  // ── Send message
  const handleSend = useCallback(async () => {
    if (!draft.trim() || !activeTicket) return;
    setSending(true);
    const newMsg = {
      id:   "m" + Date.now(),
      from: "agent",
      text: draft.trim(),
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    await new Promise((r) => setTimeout(r, 400));
    setTickets((prev) =>
      prev.map((t) => t.id === activeTicketId ? { ...t, messages: [...t.messages, newMsg], time: "just now", preview: draft.trim().slice(0, 60) } : t)
    );
    setDraft("");
    setSending(false);
  }, [draft, activeTicket, activeTicketId]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── Call
  const handleCall = useCallback(() => {
    setCalling(true);
    showToast(`📞 Calling ${activeTicket?.name}...`, "info");
    setTimeout(() => { setCalling(false); showToast("📞 Call ended.", "success"); }, 3000);
  }, [activeTicket, showToast]);

  // ── Verify Identity
  const handleVerify = useCallback(() => {
    setVerifying(true);
    setTimeout(() => {
      setVerifying(false);
      showToast(`✅ Identity verified for ${activeTicket?.name}`, "success");
    }, 1800);
  }, [activeTicket, showToast]);

  // ── AI suggestion chip click
  const handleSuggestion = useCallback((chip) => {
    const responses = {
      "Verify License Key":    "I'd be happy to verify your license key. Could you please share the key you received so I can look it up in our system?",
      "Reset Password Link":   "I've sent a password reset link to your registered email address. Please check your inbox (and spam folder) within the next 5 minutes.",
      "Billing FAQ":           "For billing questions, you can refer to our FAQ at help.synergy.io/billing. If you need a specific invoice or refund, I can assist you directly here.",
      "Escalate to L2":        "I'm escalating your ticket to our Level 2 technical support team who will contact you within 30 minutes.",
      "Request Screenshot":    "Could you please take a screenshot of the error message you're seeing and share it here? This will help us diagnose the issue faster.",
    };
    setDraft(responses[chip] ?? chip);
    textareaRef.current?.focus();
  }, []);

  // ── Create ticket from modal
  const handleCreateTicket = useCallback((ticket) => {
    setTickets((prev) => [ticket, ...prev]);
    setActiveTicketId(ticket.id);
    setNewNotif(true);
    showToast("🎫 New ticket created!", "success");
  }, [showToast]);

  return (
    <>
      <style>{`
        @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        @keyframes modalIn{from{opacity:0;transform:scale(0.95) translateY(12px)}to{opacity:1;transform:scale(1) translateY(0)}}
        @keyframes slideIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
        @keyframes toastIn{from{opacity:0;transform:translateY(20px) scale(0.95)}to{opacity:1;transform:translateY(0) scale(1)}}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes typing{0%,80%,100%{transform:scale(0.8); opacity:0.5}40%{transform:scale(1);opacity:1}}
        *{box-sizing:border-box}
      `}</style>

      <div className={s.appShell}>
        <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
        <div className={s.mainArea}>
          <Header breadcrumbs={["Synergy ERP", "Support", "Ticket Detail", activeTicket?.id ?? ""]} />
          <main className={s.page} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

            {/* Toast */}
            {toast && (
              <div className={`${s.toast} ${s[`toast_${toast.type}`]}`}>
                {toast.msg}
              </div>
            )}

            <div className={s.supportLayout} style={{ flex: 1, overflow: 'hidden' }}>

              {/* ───── LEFT: Inbound Queue ───── */}
              <aside className={s.queue}>
                <div ref={headerAnim.ref} className={s.queueHeader} style={headerAnim.style}>
                  <div className={s.queueTitleRow}>
                    <h2 className={s.queueTitle}>Inbound Queue</h2>
                    <button className={s.filterIconBtn} title="Filter">▼</button>
                  </div>

                  {/* Search */}
                  <div className={s.searchWrap}>
                    <span className={s.searchIcon}>🔍</span>
                    <input
                      className={s.searchInput}
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search tickets..."
                      aria-label="Search tickets"
                    />
                  </div>

                  {/* Filter tabs */}
                  <div className={s.filterTabs}>
                    {[`All (${tickets.length})`, `Urgent (${urgentCount})`, `Pending (${pendingCount})`].map((tab) => {
                      const key = tab.split(" ")[0];
                      return (
                        <button
                          key={tab}
                          className={`${s.filterTab} ${filter === key ? s.filterTabActive : ""}`}
                          onClick={() => setFilter(key)}
                          role="tab"
                          aria-selected={filter === key}
                        >
                          {tab}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Ticket list */}
                <div className={s.ticketList}>
                  {filteredTickets.length === 0 ? (
                    <div className={s.emptyQueue}>
                      <p>🎉</p>
                      <p>No tickets found</p>
                      <p>Try different filters</p>
                    </div>
                  ) : (
                    filteredTickets.map((t, i) => (
                      <TicketCard
                        key={t.id}
                        ticket={t}
                        isActive={t.id === activeTicketId}
                        onClick={() => { setActiveTicketId(t.id); setNewNotif(false); }}
                        delay={i * 60}
                      />
                    ))
                  )}
                </div>
              </aside>

              {/* ───── RIGHT: Chat Panel ───── */}
              {activeTicket && (
                <div className={s.chatPanel} key={activeTicketId}>

                  {/* Chat Header */}
                  <div className={s.chatHeader}>
                    <div className={s.chatHeaderLeft}>
                      <div className={s.chatAvatar} style={{ background: activeTicket.avatarColor }}>
                        {activeTicket.avatar}
                        <span className={s.onlineDot} />
                      </div>
                      <div>
                        <div className={s.chatName}>
                          {activeTicket.name}
                          <span className={s.proTag}>Pro Account</span>
                        </div>
                        <div className={s.chatMeta}>
                          <span>🕐 {activeTicket.lastSeen}</span>
                          <span>•</span>
                          <span>📍 {activeTicket.location}</span>
                        </div>
                      </div>
                    </div>

                    <div className={s.chatHeaderActions}>
                      <button
                        className={`${s.headerActionBtn} ${calling ? s.headerActionBtnActive : ""}`}
                        onClick={handleCall}
                        disabled={calling}
                        title="Call customer"
                      >
                        {calling ? <span className={s.callingDots}><span/><span/><span/></span> : "📞"} Call
                      </button>
                      <button
                        className={`${s.headerActionBtn} ${verifying ? s.headerActionBtnActive : ""}`}
                        onClick={handleVerify}
                        disabled={verifying}
                        title="Verify customer identity"
                      >
                        {verifying ? <span className={s.spinner}/> : "🔐"} Verify identity
                      </button>
                      <button className={s.moreBtn} title="More options">•••</button>
                    </div>
                  </div>

                  {/* Messages */}
                  <div className={s.messages}>
                    <div className={s.ticketCreatedTag}>
                      Ticket created on Oct 24, 2024 at 10:14 AM<br />
                      <strong>Subject: {activeTicket.subject}</strong>
                    </div>

                    {activeTicket.messages.map((msg) => (
                      <ChatBubble key={msg.id} msg={msg} agentName="Alex Sterling" />
                    ))}
                    <div ref={chatEndRef} />
                  </div>

                  {/* AI Suggestions */}
                  <div className={s.aiSuggestions}>
                    <div className={s.aiLabel}>
                      <span className={s.aiIcon}>✦</span>
                      <span>AI SUGGESTIONS</span>
                    </div>
                    <div className={s.aiChips}>
                      {AI_SUGGESTIONS.map((chip) => (
                        <button
                          key={chip}
                          className={s.aiChip}
                          onClick={() => handleSuggestion(chip)}
                          title={`Use AI suggestion: ${chip}`}
                        >
                          {chip}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Input area */}
                  <div className={s.inputArea}>
                    <textarea
                      ref={textareaRef}
                      className={s.messageInput}
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Type a message or use '/' for internal notes..."
                      rows={3}
                      aria-label="Message input"
                    />
                    <div className={s.inputActions}>
                      <div className={s.inputActionsLeft}>
                        <button className={s.iconBtn} title="Attach file">📎</button>
                        <button className={s.iconBtn} title="Emoji">🙂</button>
                        <CannedDropdown onSelect={(text) => { setDraft(text); textareaRef.current?.focus(); }} />
                      </div>
                      <button
                        className={`${s.sendBtn} ${draft.trim() ? s.sendBtnActive : ""}`}
                        onClick={handleSend}
                        disabled={!draft.trim() || sending}
                        aria-label="Send reply"
                      >
                        {sending ? <span className={s.spinner} /> : "Send Reply"} {!sending && "✈"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </main>

          {/* New Ticket notification banner */}
          {newNotif && (
            <div className={s.newTicketBanner} onClick={() => { setActiveTicketId(tickets[0].id); setNewNotif(false); }}>
              <span className={s.newTicketBannerIcon}>📬</span>
              <div>
                <p className={s.newTicketBannerTitle}>New Ticket Received</p>
                <p className={s.newTicketBannerSub}>{tickets[0].subject.slice(0, 35)}…</p>
              </div>
              <button className={s.newTicketBannerView}>VIEW</button>
            </div>
          )}

          {/* Header New Ticket button rendered via portal-like absolute */}
          <footer className={s.footer}>
            <span>© 2024 Synergy ERP Systems. All rights reserved.</span>
            <div className={s.footerRight}>
              <a href="#" className={s.footerLink}>Privacy Policy</a>
              <a href="#" className={s.footerLink}>Terms of Service</a>
              <span className={s.statusDot}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#2F9E44", display: "inline-block", marginRight: 5 }} />System Status: Operational</span>
            </div>
          </footer>
        </div>
      </div>

      {/* Floating New Ticket button */}
      <button className={s.fabBtn} onClick={() => setShowNewTicket(true)} title="Create new ticket" aria-label="Create new ticket">
        + New Ticket
      </button>

      <NewTicketModal
        isOpen={showNewTicket}
        onClose={() => setShowNewTicket(false)}
        onCreate={handleCreateTicket}
      />
    </>
  );
}
