const API_BASE = "http://localhost:5005/v1/auth/users";

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
    throw new Error(payload.message || payload.error || "User request failed");
  }

  return payload;
};

const request = async (path = "") => {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: getAuthHeaders(),
  });

  return parseResponse(response);
};

export const getUsers = () => request();

export const getInternalUsers = () => request("/internal");

export const getUsersByRole = (role) => request(`/role/${role}`);

export const getUsersByDepartment = (department) => request(`/department/${department}`);
