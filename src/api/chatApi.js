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

export const getInternalChats = () => request();

export const getInternalChatById = (chatId) => request(`/${chatId}`);

export const getInternalChatsByTicketId = (ticketId) => request(`/ticket/${ticketId}`);

export const createInternalDepartmentChat = (chatData) =>
  request("/internal", {
    method: "POST",
    body: JSON.stringify(chatData),
  });

export const addInternalChatMessage = (chatId, messageData) =>
  request(`/${chatId}/messages`, {
    method: "POST",
    body: JSON.stringify(messageData),
  });

export const addParticipantToInternalChat = (chatId, participantId) =>
  request(`/${chatId}/participants`, {
    method: "PATCH",
    body: JSON.stringify({ participantId }),
  });

export const closeInternalChat = (chatId) =>
  request(`/${chatId}/close`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });
