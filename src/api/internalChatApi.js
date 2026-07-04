const API_BASE = "http://localhost:5005/v1/chats";

const getAuthHeaders = () => {
  const token = localStorage.getItem("token");

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const parseResponse = async (response) => {
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.message || payload.error || "Internal chat request failed");
  }

  return payload;
};

const request = async (path = "", options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
  });

  return parseResponse(response);
};

export const getInternalChatsByTicket = (ticketId) => request(`/ticket/${ticketId}`);

export const addInternalChatMessage = (chatId, { text, attachments = [] }) =>
  request(`/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify({ text, attachments }),
  });
