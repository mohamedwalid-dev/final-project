const API_URL = "http://localhost:5005/v1/support-chats";

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
    throw new Error(payload.message || payload.error || "Support chat request failed");
  }

  return payload;
};

const request = async (path = "", options = {}) => {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
  });

  return parseResponse(response);
};

export const getMySupportChat = () => request("/me");

export const sendMySupportMessage = (text) =>
  request("/me/messages", {
    method: "POST",
    body: JSON.stringify({ text }),
  });

export const getAllSupportChats = () => request();

export const getSupportChatById = (chatId) => request(`/${chatId}`);

export const sendSupportReply = (chatId, text) =>
  request(`/${chatId}/reply`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });

export const markSupportChatAsRead = (chatId) =>
  request(`/${chatId}/read`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });

export const closeSupportChat = (chatId) =>
  request(`/${chatId}/close`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });

export const reopenSupportChat = (chatId) =>
  request(`/${chatId}/reopen`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });
