import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Header from "../components/Finance/Layout/Header";
import Sidebar from "../components/Finance/Layout/Sidebar";
import {
  closeSupportChat,
  getAllSupportChats,
  getMySupportChat,
  getSupportChatById,
  markSupportChatAsRead,
  reopenSupportChat,
  sendMySupportMessage,
  sendSupportReply,
} from "../api/supportChatApi";
import s from "../styles/SupportChatPage.module.css";

const FILTERS = ["All", "Open", "Pending", "Closed", "Unread"];

const getStoredUser = () => {
  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser) return {};
    const parsedUser = JSON.parse(rawUser);
    return parsedUser && typeof parsedUser === "object" ? parsedUser : {};
  } catch {
    return {};
  }
};

const getData = (payload) => payload?.data || payload;

const getUserId = (user) => user?._id || user?.id || "";

const getDisplayName = (user) =>
  user?.name ||
  [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() ||
  user?.email ||
  "User";

const getInitials = (name = "User") =>
  name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "U";

const formatTime = (date) => {
  if (!date) return "";
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  }).format(new Date(date));
};

const statusClassName = (status) => {
  if (status === "closed") return s.statusClosed;
  if (status === "pending") return s.statusPending;
  return s.statusOpen;
};

const sortChats = (chatList) =>
  [...chatList].sort(
    (firstChat, secondChat) =>
      new Date(secondChat.lastMessageAt || secondChat.updatedAt || 0) -
      new Date(firstChat.lastMessageAt || firstChat.updatedAt || 0)
  );

export default function SupportChatPage() {
  const [activeNav, setActiveNav] = useState("supportChat");
  const [currentUser] = useState(() => getStoredUser());
  const [chats, setChats] = useState([]);
  const [activeChat, setActiveChat] = useState(null);
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState(null);
  const messagesEndRef = useRef(null);

  const isSupportUser = ["support", "admin"].includes(currentUser?.role);
  const currentUserId = getUserId(currentUser);

  const showToast = useCallback((message, type = "success") => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 2800);
  }, []);

  const replaceChat = useCallback((updatedChat) => {
    if (!updatedChat?._id) return;

    setChats((currentChats) => {
      const exists = currentChats.some((chat) => chat._id === updatedChat._id);
      const nextChats = exists
        ? currentChats.map((chat) => (chat._id === updatedChat._id ? updatedChat : chat))
        : [updatedChat, ...currentChats];

      return sortChats(nextChats);
    });

    setActiveChat((currentChat) =>
      currentChat?._id === updatedChat._id || !currentChat ? updatedChat : currentChat
    );
  }, []);

  const loadMyChat = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await getMySupportChat();
      const chat = getData(payload);
      setActiveChat(chat);
      setChats(chat ? [chat] : []);
      if (chat?._id) {
        const readPayload = await markSupportChatAsRead(chat._id);
        replaceChat(getData(readPayload));
      }
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoading(false);
    }
  }, [replaceChat, showToast]);

  const loadAllChats = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await getAllSupportChats();
      const chatList = Array.isArray(payload?.data) ? payload.data : [];
      const sortedChats = sortChats(chatList);
      setChats(sortedChats);
      setActiveChat((currentChat) => {
        if (currentChat?._id) {
          return sortedChats.find((chat) => chat._id === currentChat._id) || sortedChats[0] || null;
        }
        return sortedChats[0] || null;
      });
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const handleSelectChat = async (chatId) => {
    try {
      const payload = await getSupportChatById(chatId);
      const chat = getData(payload);
      setActiveChat(chat);
      replaceChat(chat);

      const readPayload = await markSupportChatAsRead(chatId);
      replaceChat(getData(readPayload));
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  const handleSendMessage = async () => {
    const text = draft.trim();
    if (!text || sending) return;

    setSending(true);
    try {
      const payload = isSupportUser
        ? await sendSupportReply(activeChat._id, text)
        : await sendMySupportMessage(text);
      const updatedChat = getData(payload);
      replaceChat(updatedChat);
      setDraft("");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSending(false);
    }
  };

  const handleComposerKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleCloseChat = async () => {
    if (!activeChat?._id) return;

    try {
      const payload = await closeSupportChat(activeChat._id);
      replaceChat(getData(payload));
      showToast("Chat closed.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  const handleReopenChat = async () => {
    if (!activeChat?._id) return;

    try {
      const payload = await reopenSupportChat(activeChat._id);
      replaceChat(getData(payload));
      showToast("Chat reopened.");
    } catch (error) {
      showToast(error.message, "error");
    }
  };

  useEffect(() => {
    if (isSupportUser) {
      loadAllChats();
      const intervalId = window.setInterval(loadAllChats, 15000);
      return () => window.clearInterval(intervalId);
    }

    loadMyChat();
    return undefined;
  }, [isSupportUser, loadAllChats, loadMyChat]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages]);

  const filteredChats = useMemo(() => {
    const query = search.trim().toLowerCase();
    const normalizedFilter = filter.toLowerCase();

    return chats.filter((chat) => {
      const matchesSearch =
        !query ||
        [chat.userName, chat.userEmail, chat.lastMessage]
          .filter(Boolean)
          .some((value) => value.toLowerCase().includes(query));

      const matchesFilter =
        filter === "All" ||
        chat.status === normalizedFilter ||
        (filter === "Unread" && Number(chat.unreadBySupport) > 0);

      return matchesSearch && matchesFilter;
    });
  }, [chats, filter, search]);

  const activeChatUserName = activeChat?.userName || getDisplayName(currentUser);
  const activeChatEmail = activeChat?.userEmail || currentUser?.email || "";

  return (
    <div className={s.page}>
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
      <main className={s.mainArea}>
        <Header breadcrumbs={["Synergy ERP", "Support Chat"]} />

        <section className={`${s.chatShell} ${!isSupportUser ? s.chatShellSingle : ""}`}>
          {isSupportUser && (
            <aside className={s.inbox}>
              <div className={s.inboxHeader}>
                <h1 className={s.inboxTitle}>Support Inbox</h1>
                <input
                  className={s.inboxSearch}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search by user, email, message..."
                />

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

              <div className={s.chatList}>
                {loading && <div className={s.emptyState}>Loading support chats...</div>}
                {!loading &&
                  filteredChats.map((chat) => (
                    <button
                      type="button"
                      key={chat._id}
                      className={`${s.chatCard} ${
                        activeChat?._id === chat._id ? s.chatCardActive : ""
                      }`}
                      onClick={() => handleSelectChat(chat._id)}
                    >
                      <div className={s.chatAvatar}>{getInitials(chat.userName || chat.userEmail)}</div>
                      <div className={s.chatCardBody}>
                        <div className={s.chatCardTop}>
                          <span className={s.chatName}>{chat.userName || "User"}</span>
                          <span className={s.chatTime}>{formatTime(chat.lastMessageAt)}</span>
                        </div>
                        <span className={s.chatEmail}>{chat.userEmail}</span>
                        <p className={s.chatPreview}>{chat.lastMessage || "No messages yet."}</p>
                        <div className={s.chatCardTop}>
                          <span className={`${s.statusBadge} ${statusClassName(chat.status)}`}>
                            {chat.status}
                          </span>
                          {Number(chat.unreadBySupport) > 0 && (
                            <span className={s.unreadBadge}>{chat.unreadBySupport}</span>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                {!loading && !filteredChats.length && (
                  <div className={s.emptyState}>No support chats found.</div>
                )}
              </div>
            </aside>
          )}

          <section className={s.conversation}>
            {activeChat ? (
              <>
                <div className={s.conversationHeader}>
                  <div className={s.conversationUser}>
                    <div className={s.chatAvatar}>{getInitials(activeChatUserName)}</div>
                    <div>
                      <h2 className={s.conversationTitle}>
                        {isSupportUser ? activeChatUserName : "Support Chat"}
                      </h2>
                      <p className={s.conversationSub}>
                        {isSupportUser
                          ? activeChatEmail
                          : "We usually reply shortly. Tell us what you need help with."}
                      </p>
                    </div>
                  </div>

                  <div className={s.conversationActions}>
                    <span className={`${s.statusBadge} ${statusClassName(activeChat.status)}`}>
                      {activeChat.status}
                    </span>
                    {isSupportUser &&
                      (activeChat.status === "closed" ? (
                        <button type="button" onClick={handleReopenChat}>
                          Reopen
                        </button>
                      ) : (
                        <button type="button" onClick={handleCloseChat}>
                          Close
                        </button>
                      ))}
                  </div>
                </div>

                <div className={s.messages}>
                  {activeChat.messages?.map((message) => {
                    const isMine = message.senderId?.toString() === currentUserId?.toString();

                    if (message.messageType === "system") {
                      return (
                        <div key={message._id || message.createdAt} className={s.systemMessage}>
                          {message.text}
                        </div>
                      );
                    }

                    return (
                      <div
                        key={message._id || message.createdAt}
                        className={`${s.messageRow} ${isMine ? s.messageRowMine : ""}`}
                      >
                        <div
                          className={`${s.messageBubble} ${
                            isMine ? s.messageBubbleMine : ""
                          }`}
                        >
                          <p>{message.text}</p>
                          <div className={s.messageMeta}>
                            {message.senderName || "User"} - {formatTime(message.createdAt)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {!activeChat.messages?.length && (
                    <div className={s.emptyState}>
                      Start the conversation with the support team.
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <div className={s.composer}>
                  <textarea
                    className={s.messageInput}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                    placeholder="Type a message..."
                    rows={2}
                  />
                  <button
                    type="button"
                    className={s.sendButton}
                    onClick={handleSendMessage}
                    disabled={!draft.trim() || sending || !activeChat}
                  >
                    {sending ? "Sending..." : "Send"}
                  </button>
                </div>
              </>
            ) : (
              <div className={s.emptyState}>
                {isSupportUser
                  ? "Select a user conversation from the inbox."
                  : "Opening your support chat..."}
              </div>
            )}
          </section>
        </section>
      </main>

      {toast && <div className={`${s.toast} ${s[`toast_${toast.type}`] || ""}`}>{toast.message}</div>}
    </div>
  );
}
