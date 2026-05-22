const API_BASE = "http://localhost:5005/v1/tickets";

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
    throw new Error(payload.message || payload.error || "Ticket request failed");
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

export const getTickets = () => request();

export const getTicketById = (ticketId) => request(`/${ticketId}`);

export const createTicket = (ticketData) =>
  request("", {
    method: "POST",
    body: JSON.stringify(ticketData),
  });

export const addTicketMessage = (ticketId, messageData) =>
  request(`/${ticketId}/messages`, {
    method: "POST",
    body: JSON.stringify(messageData),
  });

export const updateTicketStatus = (ticketId, status) =>
  request(`/${ticketId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

export const assignTicketToSupportAgent = (ticketId, agentId) =>
  request(`/${ticketId}/assign`, {
    method: "PATCH",
    body: JSON.stringify({ agentId }),
  });

export const updateTicketDepartment = (ticketId, relatedDepartment) =>
  request(`/${ticketId}/department`, {
    method: "PATCH",
    body: JSON.stringify({ relatedDepartment }),
  });
