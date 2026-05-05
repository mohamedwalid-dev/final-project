import axios from "axios";

export const apiBaseUrl = "http://localhost:5005/v1";

const client = axios.create({
  baseURL: apiBaseUrl,
  withCredentials: true,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

const normalizeError = (err) => {
  const status = err?.response?.status ?? null;

  const message =
    err?.response?.data?.message ||
    err?.response?.data?.error ||
    err?.message ||
    "Request failed";

  const data = err?.response?.data?.data ?? [];

  return { status, message, data };
};

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;

    if (status === 401) {
      const currentPath = window.location.pathname;

      if (currentPath !== "/login") {
        window.location.replace("/login");
      }
    }

    return Promise.reject(error);
  }
);

export async function requestSafe(fn) {
  try {
    const res = await fn();

    return {
      data: res.data,
      error: null,
      status: res.status,
    };
  } catch (err) {
    if (err?.name === "CanceledError") {
      return { data: null, error: null };
    }

    const normalized = normalizeError(err);

    return {
      data: null,
      error: normalized.message,
      errorData: Array.isArray(normalized.data) ? normalized.data : [],
      status: normalized.status,
    };
  }
}

export const http = {
  get: (url, config) => requestSafe(() => client.get(url, config)),
  post: (url, data, config) => requestSafe(() => client.post(url, data, config)),
  patch: (url, data, config) => requestSafe(() => client.patch(url, data, config)),
  put: (url, data, config) => requestSafe(() => client.put(url, data, config)),
  delete: (url, config) => requestSafe(() => client.delete(url, config)),
};

export default client;