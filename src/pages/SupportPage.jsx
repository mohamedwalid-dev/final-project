import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header from "../components/Finance/Layout/Header";
import {
  addTicketMessage,
  createTicket,
  getTickets,
  updateTicketStatus,
} from "../api/ticketApi";
import s from "../styles/SupportPage.module.css";
import shell from "../styles/AppShell.module.css";

const FILTERS = [
  "All",
  "Urgent",
  "Open",
  "Pending",
  "Resolved",
  "Closed",
  "Invoice",
  "Payment",
  "Technical",
];

const PRIORITIES = ["urgent", "high", "medium", "low"];
const STATUSES = ["open", "pending", "resolved", "closed"];
const CATEGORIES = ["invoice", "payment", "hr", "technical", "sales", "general"];
const DEPARTMENTS = [
  "support",
  "finance",
  "accounting",
  "hr",
  "sales",
  "management",
  "admin",
];

const titleCase = (value = "") =>
  value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ") : "-";

const getList = (payload) => {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload)) return payload;
  return [];
};

const getItem = (payload) => {
  if (Array.isArray(payload?.data)) return payload.data[0];
  return payload?.data || payload;
};

const formatDate = (date) => {
  if (!date) return "Just now";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
};

const initialsFor = (name = "") =>
  name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "ST";

const getStoredUser = () => {
  try {
    const parsedUser = JSON.parse(localStorage.getItem("user") || "null");
    return parsedUser && typeof parsedUser === "object" ? parsedUser : null;
  } catch {
    return null;
  }
};

const isSupportOrAdmin = (user) =>
  user?.role === "admin" || (user?.role === "support" && user?.department === "support");

function NewTicketModal({ isOpen, onClose, onCreate, loading }) {
  const [form, setForm] = useState({
    clientName: "",
    clientEmail: "",
    subject: "",
    description: "",
    priority: "medium",
    category: "general",
    relatedDepartment: "support",
  });
  const [errors, setErrors] = useState({});
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    setForm({
      clientName: "",
      clientEmail: "",
      subject: "",
      description: "",
      priority: "medium",
      category: "general",
      relatedDepartment: "support",
    });
    setErrors({});
  }, [isOpen]);

  if (!isOpen) return null;

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      const nextErrors = { ...current };
      delete nextErrors[field];
      return nextErrors;
    });
  };

  const validate = () => {
    const nextErrors = {};
    if (!form.clientName.trim()) nextErrors.clientName = "Client name is required";
    if (!form.clientEmail.trim()) nextErrors.clientEmail = "Client email is required";
    if (!form.subject.trim()) nextErrors.subject = "Subject is required";
    if (!form.description.trim()) nextErrors.description = "Description is required";
    return nextErrors;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const nextErrors = validate();
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    await onCreate(form);
  };

  return (
    <div
      ref={overlayRef}
      className={s.modalOverlay}
      onClick={(event) => {
        if (event.target === overlayRef.current) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <form className={s.modal} onSubmit={handleSubmit}>
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon}>T</div>
            <div>
              <h2 className={s.modalTitle}>New Support Ticket</h2>
              <p className={s.modalSub}>Create a customer-facing ticket.</p>
            </div>
          </div>
          <button type="button" className={s.modalClose} onClick={onClose}>
            ×
          </button>
        </div>

        <div className={s.modalBody}>
          <div className={s.formGrid}>
            <div className={s.formGroup}>
              <label className={s.formLabel}>
                Client name <span className={s.required}>*</span>
              </label>
              <input
                className={`${s.formInput} ${errors.clientName ? s.formInputError : ""}`}
                value={form.clientName}
                onChange={(event) => updateField("clientName", event.target.value)}
                autoFocus
              />
              {errors.clientName && <span className={s.fieldError}>{errors.clientName}</span>}
            </div>

            <div className={s.formGroup}>
              <label className={s.formLabel}>
                Client email <span className={s.required}>*</span>
              </label>
              <input
                className={`${s.formInput} ${errors.clientEmail ? s.formInputError : ""}`}
                type="email"
                value={form.clientEmail}
                onChange={(event) => updateField("clientEmail", event.target.value)}
              />
              {errors.clientEmail && <span className={s.fieldError}>{errors.clientEmail}</span>}
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel}>
                Subject <span className={s.required}>*</span>
              </label>
              <input
                className={`${s.formInput} ${errors.subject ? s.formInputError : ""}`}
                value={form.subject}
                onChange={(event) => updateField("subject", event.target.value)}
              />
              {errors.subject && <span className={s.fieldError}>{errors.subject}</span>}
            </div>

            <div className={s.formGroup}>
              <label className={s.formLabel}>Priority</label>
              <select
                className={s.formSelect}
                value={form.priority}
                onChange={(event) => updateField("priority", event.target.value)}
              >
                {PRIORITIES.map((priority) => (
                  <option key={priority} value={priority}>
                    {titleCase(priority)}
                  </option>
                ))}
              </select>
            </div>

            <div className={s.formGroup}>
              <label className={s.formLabel}>Category</label>
              <select
                className={s.formSelect}
                value={form.category}
                onChange={(event) => updateField("category", event.target.value)}
              >
                {CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {titleCase(category)}
                  </option>
                ))}
              </select>
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel}>Related department</label>
              <select
                className={s.formSelect}
                value={form.relatedDepartment}
                onChange={(event) => updateField("relatedDepartment", event.target.value)}
              >
                {DEPARTMENTS.map((department) => (
                  <option key={department} value={department}>
                    {titleCase(department)}
                  </option>
                ))}
              </select>
            </div>

            <div className={`${s.formGroup} ${s.formGroupFull}`}>
              <label className={s.formLabel}>
                Description <span className={s.required}>*</span>
              </label>
              <textarea
                className={`${s.formTextarea} ${errors.description ? s.formInputError : ""}`}
                value={form.description}
                onChange={(event) => updateField("description", event.target.value)}
                rows={4}
              />
              {errors.description && <span className={s.fieldError}>{errors.description}</span>}
            </div>
          </div>
        </div>

        <div className={s.modalFooter}>
          <p className={s.modalFooterNote}>Only customer-facing messages go on the ticket.</p>
          <div className={s.modalFooterActions}>
            <button type="button" className={s.btnGhost} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={loading}>
              {loading ? "Creating..." : "Create ticket"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function TicketCard({ ticket, active, onSelect }) {
  return (
    <button
      type="button"
      className={`${s.ticketCard} ${active ? s.ticketCardActive : ""}`}
      onClick={() => onSelect(ticket._id)}
    >
      <div className={s.ticketCardTop}>
        <div className={s.ticketAvatar}>{initialsFor(ticket.clientName)}</div>
        <div className={s.ticketMeta}>
          <span className={s.ticketName}>{ticket.clientName}</span>
          <span className={s.ticketTime}>{formatDate(ticket.updatedAt)}</span>
        </div>
      </div>
      <p className={s.ticketSubject}>{ticket.subject}</p>
      <p className={s.ticketPreview}>{ticket.preview || ticket.description}</p>
      <div className={s.ticketTags}>
        <span className={s.priorityBadge}>{titleCase(ticket.priority)}</span>
        <span className={s.ticketTagGray}>{ticket.ticketCode}</span>
      </div>
    </button>
  );
}

function CustomerMessage({ message }) {
  const isSupport = message.senderType === "support" || message.senderType === "system";

  if (message.senderType === "system") {
    return (
      <div className={s.systemMsg}>
        <span>{message.text}</span>
      </div>
    );
  }

  return (
    <div className={`${s.bubbleWrap} ${isSupport ? s.bubbleWrapRight : ""}`}>
      <div className={`${s.bubble} ${isSupport ? s.bubbleAgent : s.bubbleCustomer}`}>
        <p className={s.bubbleText}>{message.text}</p>
      </div>
      <span className={s.bubbleTime}>
        {message.senderName} • {formatDate(message.createdAt)}
      </span>
    </div>
  );
}

export default function SupportPage() {
  const [activeNav, setActiveNav] = useState("support");
  const [currentUser] = useState(() => getStoredUser());
  const [tickets, setTickets] = useState([]);
  const [activeTicketId, setActiveTicketId] = useState("");
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [loadingTickets, setLoadingTickets] = useState(false);
  const [savingTicket, setSavingTicket] = useState(false);
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [toast, setToast] = useState(null);
  const messagesEndRef = useRef(null);

  const canCreateTicket = isSupportOrAdmin(currentUser);

  const visibleTickets = useMemo(
    () =>
      tickets.filter((ticket) => {
        if (canCreateTicket) return true;
        return ticket.relatedDepartment === currentUser?.department;
      }),
    [canCreateTicket, currentUser?.department, tickets]
  );

  const activeTicket = useMemo(
    () =>
      visibleTickets.find((ticket) => ticket._id === activeTicketId) ||
      visibleTickets[0] ||
      null,
    [activeTicketId, visibleTickets]
  );

  const showToast = useCallback((message, type = "success") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2600);
  }, []);

  const loadTickets = useCallback(async () => {
    setLoadingTickets(true);
    try {
      const payload = await getTickets();
      const ticketList = getList(payload);
      setTickets(ticketList);
      setActiveTicketId((current) => current || ticketList[0]?._id || "");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoadingTickets(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeTicket?.messages]);

  const filteredTickets = useMemo(() => {
    const query = search.trim().toLowerCase();

    return visibleTickets.filter((ticket) => {
      const matchesSearch =
        !query ||
        [ticket.ticketCode, ticket.clientName, ticket.clientEmail, ticket.subject]
          .filter(Boolean)
          .some((value) => value.toLowerCase().includes(query));

      const normalizedFilter = filter.toLowerCase();
      const matchesFilter =
        filter === "All" ||
        ticket.priority === normalizedFilter ||
        ticket.status === normalizedFilter ||
        ticket.category === normalizedFilter;

      return matchesSearch && matchesFilter;
    });
  }, [filter, search, visibleTickets]);

  const replaceTicket = (updatedTicket) => {
    if (!updatedTicket?._id) return;
    setTickets((current) =>
      current.map((ticket) => (ticket._id === updatedTicket._id ? updatedTicket : ticket))
    );
  };

  const handleCreateTicket = async (ticketData) => {
    if (!canCreateTicket) {
      showToast("Only support users can create tickets.", "error");
      return;
    }

    setSavingTicket(true);
    try {
      const payload = await createTicket(ticketData);
      const newTicket = getItem(payload);
      setTickets((current) => [newTicket, ...current]);
      setActiveTicketId(newTicket._id);
      setShowNewTicket(false);
      showToast("Ticket created successfully.");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSavingTicket(false);
    }
  };

  const handleReply = async (event) => {
    event.preventDefault();
    if (!reply.trim() || !activeTicket) return;

    try {
      const payload = await addTicketMessage(activeTicket._id, {
        senderType: "support",
        senderName: "Support Team",
        text: reply.trim(),
      });
      replaceTicket(getItem(payload));
      setReply("");
      showToast("Reply sent to client.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  const handleStatusChange = async (status) => {
    if (!activeTicket) return;

    try {
      const payload = await updateTicketStatus(activeTicket._id, status);
      replaceTicket(getItem(payload));
      showToast("Ticket status updated.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  return (
    <div className={shell.appShell}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
      <div className={shell.mainArea}>
        <Header breadcrumbs={["ERP", "Support"]} />

        <main className={s.page}>
          <div className={s.supportLayout}>
            <aside className={s.queue}>
              <div className={s.queueHeader}>
                <div className={s.queueTitleRow}>
                  <h1 className={s.queueTitle}>Ticket Queue</h1>
                  <button type="button" className={s.filterIconBtn} onClick={loadTickets}>
                    Refresh
                  </button>
                </div>
                {/* {!canCreateTicket && currentUser?.department && (
                  <p className={s.departmentScopeNote}>
                    Showing tickets for your department: {titleCase(currentUser.department)}
                  </p>
                )} */}

                <div className={s.searchWrap}>
                  <span className={s.searchIcon}>⌕</span>
                  <input
                    className={s.searchInput}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search ticket, client, email..."
                  />
                </div>

                <div className={s.filterTabs}>
                  {FILTERS.map((filterName) => (
                    <button
                      type="button"
                      key={filterName}
                      className={`${s.filterTab} ${
                        filter === filterName ? s.filterTabActive : ""
                      }`}
                      onClick={() => setFilter(filterName)}
                    >
                      {filterName}
                    </button>
                  ))}
                </div>
              </div>

              <div className={s.ticketList}>
                {loadingTickets && <p className={s.emptyQueue}>Loading tickets...</p>}
                {!loadingTickets &&
                  filteredTickets.map((ticket) => (
                    <TicketCard
                      key={ticket._id}
                      ticket={ticket}
                      active={activeTicket?._id === ticket._id}
                      onSelect={setActiveTicketId}
                    />
                  ))}
                {!loadingTickets && !filteredTickets.length && (
                  <p className={s.emptyQueue}>No tickets match this view.</p>
                )}
              </div>
            </aside>

            <section className={s.chatPanel}>
              {activeTicket ? (
                <>
                  <div className={s.chatHeader}>
                    <div className={s.chatHeaderLeft}>
                      <div className={s.chatAvatar}>{initialsFor(activeTicket.clientName)}</div>
                      <div>
                        <h2 className={s.chatName}>
                          {activeTicket.ticketCode} · {activeTicket.subject}
                        </h2>
                        <div className={s.chatMeta}>
                          <span>{activeTicket.clientName}</span>
                          <span>•</span>
                          <span>{activeTicket.clientEmail}</span>
                        </div>
                        <div className={s.ticketTags}>
                          <span className={s.priorityBadge}>{titleCase(activeTicket.priority)}</span>
                          <span className={s.categoryBadge}>{titleCase(activeTicket.category)}</span>
                          <span className={s.departmentBadge}>
                            {titleCase(activeTicket.relatedDepartment)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className={s.chatHeaderActions}>
                      <select
                        className={s.statusSelect}
                        value={activeTicket.status || "open"}
                        onChange={(event) => handleStatusChange(event.target.value)}
                        disabled={!canCreateTicket}
                        title={
                          canCreateTicket
                            ? "Update ticket status"
                            : "Only support users can update ticket status"
                        }
                      >
                        {STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {titleCase(status)}
                          </option>
                        ))}
                      </select>
                      {canCreateTicket && (
                        <button
                          className={s.newTicketHeaderBtn}
                          onClick={() => setShowNewTicket(true)}
                          type="button"
                        >
                          + New Ticket
                        </button>
                      )}
                    </div>
                  </div>

                  <div className={s.ticketCreatedTag}>
                    <strong>{activeTicket.status.toUpperCase()}</strong> ticket created{" "}
                    {formatDate(activeTicket.createdAt)}
                  </div>

                  <div className={s.messages}>
                    {activeTicket.messages?.map((message) => (
                      <CustomerMessage key={message._id || message.createdAt} message={message} />
                    ))}
                    <div ref={messagesEndRef} />
                  </div>

                  <form className={s.inputArea} onSubmit={handleReply}>
                    <textarea
                      className={s.messageInput}
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                      placeholder="Reply to client..."
                      rows={3}
                    />
                    <div className={s.inputActions}>
                      <span className={s.modalFooterNote}>
                        This reply is customer-facing and stored on Ticket.messages.
                      </span>
                      <button
                        type="submit"
                        className={`${s.sendBtn} ${reply.trim() ? s.sendBtnActive : ""}`}
                        disabled={!reply.trim()}
                      >
                        Send reply
                      </button>
                    </div>
                  </form>
                </>
              ) : (
                <p className={s.emptyQueue}>Select or create a support ticket.</p>
              )}
            </section>
          </div>
        </main>
      </div>

      {canCreateTicket && (
        <NewTicketModal
          isOpen={showNewTicket}
          onClose={() => setShowNewTicket(false)}
          onCreate={handleCreateTicket}
          loading={savingTicket}
        />
      )}

      {toast && (
        <div className={`${s.toast} ${s[`toast_${toast.type}`] || s.toast_success}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
