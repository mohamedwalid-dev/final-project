import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "../components/Finance/Layout/Sidebar";
import Header from "../components/Finance/Layout/Header";
import {
  addTicketMessage,
  createTicket,
  getTickets,
  updateTicketStatus,
} from "../api/ticketApi";
import {
  addInternalChatMessage,
  closeInternalChat,
  createInternalDepartmentChat,
  getInternalChatsByTicketId,
} from "../api/chatApi";
import { getUsersByDepartment, getUsersByRole } from "../api/userApi";
import s from "../styles/SupportPage.module.css";

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
const ROLES = ["support", "accountant", "hr", "sales", "manager", "admin"];

const titleCase = (value = "") =>
  value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ") : "—";

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
            <div className={s.modalTitleIcon}>🎫</div>
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
            <label className={s.formGroup}>
              <span className={s.formLabel}>Client name *</span>
              <input
                className={`${s.formInput} ${errors.clientName ? s.formInputError : ""}`}
                value={form.clientName}
                onChange={(event) => updateField("clientName", event.target.value)}
                autoFocus
              />
              {errors.clientName && <span className={s.fieldError}>{errors.clientName}</span>}
            </label>

            <label className={s.formGroup}>
              <span className={s.formLabel}>Client email *</span>
              <input
                className={`${s.formInput} ${errors.clientEmail ? s.formInputError : ""}`}
                type="email"
                value={form.clientEmail}
                onChange={(event) => updateField("clientEmail", event.target.value)}
              />
              {errors.clientEmail && <span className={s.fieldError}>{errors.clientEmail}</span>}
            </label>

            <label className={`${s.formGroup} ${s.formGroupFull}`}>
              <span className={s.formLabel}>Subject *</span>
              <input
                className={`${s.formInput} ${errors.subject ? s.formInputError : ""}`}
                value={form.subject}
                onChange={(event) => updateField("subject", event.target.value)}
              />
              {errors.subject && <span className={s.fieldError}>{errors.subject}</span>}
            </label>

            <label className={s.formGroup}>
              <span className={s.formLabel}>Priority</span>
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
            </label>

            <label className={s.formGroup}>
              <span className={s.formLabel}>Category</span>
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
            </label>

            <label className={`${s.formGroup} ${s.formGroupFull}`}>
              <span className={s.formLabel}>Related department</span>
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
            </label>

            <label className={`${s.formGroup} ${s.formGroupFull}`}>
              <span className={s.formLabel}>Description *</span>
              <textarea
                className={`${s.formTextarea} ${errors.description ? s.formInputError : ""}`}
                value={form.description}
                onChange={(event) => updateField("description", event.target.value)}
                rows={4}
              />
              {errors.description && <span className={s.fieldError}>{errors.description}</span>}
            </label>
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

function DepartmentModal({ isOpen, onClose, onCreate, ticket }) {
  const [form, setForm] = useState({
    requestedDepartment: "accounting",
    requestedRole: "accountant",
    title: "",
    summary: "",
  });
  const [users, setUsers] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    setForm({
      requestedDepartment: ticket?.relatedDepartment || "accounting",
      requestedRole: "accountant",
      title: ticket ? `Help needed for ${ticket.ticketCode}` : "",
      summary: ticket?.subject || "",
    });
    setSelectedUsers([]);
    setError("");
  }, [isOpen, ticket]);

  useEffect(() => {
    if (!isOpen) return;

    const loadUsers = async () => {
      setLoadingUsers(true);
      setError("");
      try {
        const payload = form.requestedRole
          ? await getUsersByRole(form.requestedRole)
          : await getUsersByDepartment(form.requestedDepartment);
        setUsers(getList(payload));
      } catch (requestError) {
        setUsers([]);
        setError(requestError.message);
      } finally {
        setLoadingUsers(false);
      }
    };

    loadUsers();
  }, [form.requestedDepartment, form.requestedRole, isOpen]);

  if (!isOpen) return null;

  const toggleUser = (userId) => {
    setSelectedUsers((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId]
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.title.trim()) {
      setError("Title is required.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await onCreate({
        ticketId: ticket._id,
        requestedDepartment: form.requestedDepartment,
        requestedRole: form.requestedRole,
        title: form.title,
        summary: form.summary,
        participants: selectedUsers,
        priority: ticket.priority || "medium",
      });
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      ref={overlayRef}
      className={s.departmentModalOverlay}
      onClick={(event) => {
        if (event.target === overlayRef.current) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <form className={s.departmentModal} onSubmit={handleSubmit}>
        <div className={s.modalHeader}>
          <div className={s.modalTitleRow}>
            <div className={s.modalTitleIcon}>🏢</div>
            <div>
              <h2 className={s.modalTitle}>Ask Department</h2>
              <p className={s.modalSub}>Start an internal chat linked to this ticket.</p>
            </div>
          </div>
          <button type="button" className={s.modalClose} onClick={onClose}>
            ×
          </button>
        </div>

        <div className={s.modalBody}>
          {error && <div className={s.toast_error}>{error}</div>}
          <div className={s.departmentFormGrid}>
            <label className={s.formGroup}>
              <span className={s.formLabel}>Department</span>
              <select
                className={s.formSelect}
                value={form.requestedDepartment}
                onChange={(event) =>
                  setForm((current) => ({ ...current, requestedDepartment: event.target.value }))
                }
              >
                {DEPARTMENTS.map((department) => (
                  <option key={department} value={department}>
                    {titleCase(department)}
                  </option>
                ))}
              </select>
            </label>

            <label className={s.formGroup}>
              <span className={s.formLabel}>Role</span>
              <select
                className={s.formSelect}
                value={form.requestedRole}
                onChange={(event) =>
                  setForm((current) => ({ ...current, requestedRole: event.target.value }))
                }
              >
                <option value="">Any role in department</option>
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {titleCase(role)}
                  </option>
                ))}
              </select>
            </label>

            <label className={`${s.formGroup} ${s.formGroupFull}`}>
              <span className={s.formLabel}>Title</span>
              <input
                className={s.formInput}
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </label>

            <label className={`${s.formGroup} ${s.formGroupFull}`}>
              <span className={s.formLabel}>Summary</span>
              <textarea
                className={s.formTextarea}
                value={form.summary}
                onChange={(event) =>
                  setForm((current) => ({ ...current, summary: event.target.value }))
                }
                rows={3}
              />
            </label>
          </div>

          <div className={s.departmentUserList}>
            {loadingUsers && <p className={s.modalSub}>Loading internal users...</p>}
            {!loadingUsers &&
              users.map((user) => {
                const selected = selectedUsers.includes(user._id);
                return (
                  <button
                    type="button"
                    key={user._id}
                    className={`${s.departmentUserItem} ${
                      selected ? s.departmentUserSelected : ""
                    }`}
                    onClick={() => toggleUser(user._id)}
                  >
                    <strong>{user.name || `${user.first_name || ""} ${user.last_name || ""}`}</strong>
                    <span>
                      {titleCase(user.role)} • {titleCase(user.department)}
                    </span>
                  </button>
                );
              })}
            {!loadingUsers && !users.length && (
              <p className={s.modalSub}>No matching internal users found.</p>
            )}
          </div>
        </div>

        <div className={s.modalFooter}>
          <p className={s.modalFooterNote}>Clients never see this internal chat.</p>
          <div className={s.modalFooterActions}>
            <button type="button" className={s.btnGhost} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={`${s.btn} ${s.btnPrimary}`} disabled={submitting}>
              {submitting ? "Creating..." : "Create chat"}
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

function InternalChatPanel({
  chats,
  activeChat,
  activeChatId,
  onSelectChat,
  onSendMessage,
  onCloseChat,
  loading,
}) {
  const [draft, setDraft] = useState("");

  useEffect(() => {
    setDraft("");
  }, [activeChatId]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!draft.trim() || !activeChat) return;
    await onSendMessage(draft.trim());
    setDraft("");
  };

  return (
    <aside className={s.internalChatPanel}>
      <div className={s.internalChatHeader}>
        <div>
          <h3>Internal department chats</h3>
          <p>Private collaboration linked to this ticket.</p>
        </div>
        {activeChat && activeChat.status !== "closed" && (
          <button type="button" className={s.btnGhost} onClick={() => onCloseChat(activeChat._id)}>
            Close
          </button>
        )}
      </div>

      <div className={s.internalChatList}>
        {loading && <p className={s.modalSub}>Loading internal chats...</p>}
        {!loading &&
          chats.map((chat) => (
            <button
              type="button"
              key={chat._id}
              className={`${s.internalChatCard} ${
                chat._id === activeChatId ? s.internalChatCardActive : ""
              }`}
              onClick={() => onSelectChat(chat._id)}
            >
              <strong>{chat.title}</strong>
              <span>
                {titleCase(chat.requestedDepartment)} • {titleCase(chat.status)}
              </span>
              {chat.summary && <small>{chat.summary}</small>}
            </button>
          ))}
        {!loading && !chats.length && (
          <p className={s.emptyQueue}>
            No internal department chats yet. Ask a department for help.
          </p>
        )}
      </div>

      <div className={s.internalMessages}>
        {activeChat?.messages?.map((message) => (
          <div key={message._id || message.createdAt} className={s.internalMessage}>
            <div className={s.internalMessageMeta}>
              <strong>{message.senderName}</strong>
              <span>
                {titleCase(message.senderRole)} • {titleCase(message.senderDepartment)} •{" "}
                {formatDate(message.createdAt)}
              </span>
            </div>
            <div className={s.internalMessageBubble}>{message.text}</div>
          </div>
        ))}
        {activeChat && !activeChat.messages?.length && (
          <p className={s.modalSub}>No internal messages yet.</p>
        )}
      </div>

      <form className={s.internalComposer} onSubmit={handleSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={activeChat ? "Write an internal note..." : "Select an internal chat"}
          disabled={!activeChat || activeChat.status === "closed"}
          rows={3}
        />
        <button
          type="submit"
          className={`${s.sendBtn} ${draft.trim() ? s.sendBtnActive : ""}`}
          disabled={!draft.trim() || !activeChat || activeChat.status === "closed"}
        >
          Send internal
        </button>
      </form>
    </aside>
  );
}

export default function SupportPage() {
  const [activeNav, setActiveNav] = useState("support");
  const [tickets, setTickets] = useState([]);
  const [activeTicketId, setActiveTicketId] = useState("");
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [loadingTickets, setLoadingTickets] = useState(false);
  const [savingTicket, setSavingTicket] = useState(false);
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [showDepartmentModal, setShowDepartmentModal] = useState(false);
  const [internalChats, setInternalChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [loadingChats, setLoadingChats] = useState(false);
  const [toast, setToast] = useState(null);
  const messagesEndRef = useRef(null);

  const activeTicket = useMemo(
    () => tickets.find((ticket) => ticket._id === activeTicketId) || tickets[0] || null,
    [activeTicketId, tickets]
  );

  const activeChat = useMemo(
    () => internalChats.find((chat) => chat._id === activeChatId) || internalChats[0] || null,
    [activeChatId, internalChats]
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

  const loadInternalChats = useCallback(
    async (ticketId) => {
      if (!ticketId) {
        setInternalChats([]);
        setActiveChatId("");
        return;
      }

      setLoadingChats(true);
      try {
        const payload = await getInternalChatsByTicketId(ticketId);
        const chats = getList(payload);
        setInternalChats(chats);
        setActiveChatId(chats[0]?._id || "");
      } catch (error) {
        setInternalChats([]);
        setActiveChatId("");
        showToast(error.message, "error");
      } finally {
        setLoadingChats(false);
      }
    },
    [showToast]
  );

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    loadInternalChats(activeTicket?._id);
  }, [activeTicket?._id, loadInternalChats]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeTicket?.messages]);

  const filteredTickets = useMemo(() => {
    const query = search.trim().toLowerCase();

    return tickets.filter((ticket) => {
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
  }, [filter, search, tickets]);

  const replaceTicket = (updatedTicket) => {
    if (!updatedTicket?._id) return;
    setTickets((current) =>
      current.map((ticket) => (ticket._id === updatedTicket._id ? updatedTicket : ticket))
    );
  };

  const replaceChat = (updatedChat) => {
    if (!updatedChat?._id) return;
    setInternalChats((current) =>
      current.map((chat) => (chat._id === updatedChat._id ? updatedChat : chat))
    );
  };

  const handleCreateTicket = async (ticketData) => {
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

  const handleCreateInternalChat = async (chatData) => {
    const payload = await createInternalDepartmentChat(chatData);
    const chat = getItem(payload);
    setInternalChats((current) => [chat, ...current]);
    setActiveChatId(chat._id);
    showToast("Internal department chat created.");
  };

  const handleSendInternalMessage = async (text) => {
    if (!activeChat) return;

    try {
      const payload = await addInternalChatMessage(activeChat._id, {
        text,
        isInternalNote: true,
      });
      replaceChat(getItem(payload));
      showToast("Internal message sent.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  const handleCloseInternalChat = async (chatId) => {
    try {
      const payload = await closeInternalChat(chatId);
      replaceChat(getItem(payload));
      showToast("Internal chat closed.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  return (
    <div className={s.appShell}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
      <main className={s.mainArea}>
        <Header breadcrumbs={["ERP", "Support"]} />

        <section className={s.page}>
          <button type="button" className={s.fabBtn} onClick={() => setShowNewTicket(true)}>
            + New Ticket
          </button>

          <div className={s.supportLayout}>
            <aside className={s.queue}>
              <div className={s.queueHeader}>
                <div className={s.queueTitleRow}>
                  <h1 className={s.queueTitle}>Ticket Queue</h1>
                  <button type="button" className={s.filterIconBtn} onClick={loadTickets}>
                    Refresh
                  </button>
                </div>

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
                        value={activeTicket.status}
                        onChange={(event) => handleStatusChange(event.target.value)}
                      >
                        {STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {titleCase(status)}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className={s.askDepartmentBtn}
                        onClick={() => setShowDepartmentModal(true)}
                      >
                        Ask Department
                      </button>
                    </div>
                  </div>

                  <div className={s.splitConversationLayout}>
                    <div className={s.customerConversationPanel}>
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
                    </div>

                    <InternalChatPanel
                      chats={internalChats}
                      activeChat={activeChat}
                      activeChatId={activeChat?._id || ""}
                      onSelectChat={setActiveChatId}
                      onSendMessage={handleSendInternalMessage}
                      onCloseChat={handleCloseInternalChat}
                      loading={loadingChats}
                    />
                  </div>
                </>
              ) : (
                <p className={s.emptyQueue}>Select or create a support ticket.</p>
              )}
            </section>
          </div>
        </section>
      </main>

      <NewTicketModal
        isOpen={showNewTicket}
        onClose={() => setShowNewTicket(false)}
        onCreate={handleCreateTicket}
        loading={savingTicket}
      />

      <DepartmentModal
        isOpen={showDepartmentModal}
        onClose={() => setShowDepartmentModal(false)}
        onCreate={handleCreateInternalChat}
        ticket={activeTicket}
      />

      {toast && (
        <div className={`${s.toast} ${s[`toast_${toast.type}`] || s.toast_success}`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
