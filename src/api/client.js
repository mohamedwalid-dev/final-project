// ─── src/api/client.js ────────────────────────────────────────────────────────
// Central HTTP client — drop-in axios wrapper.
// All services import from THIS file, never from axios directly.
//
// Features:
//  ✅ Auto-attach JWT token from localStorage
//  ✅ 401 → auto refresh token → retry once
//  ✅ Request timeout
//  ✅ { data, error } response contract (matches existing mock pattern)
//  ✅ AbortController / signal support
//  ✅ File upload helper with progress tracking
//
// HOW TO ACTIVATE:
//   1. npm install axios
//   2. Set VITE_API_BASE_URL=http://your-backend.com/api in .env.local
//   3. Set VITE_USE_MOCK=false in .env.local
//   4. Each service already has 🔌 SWAP comments showing what to change

import axios from "axios";
import { API_CONFIG, API_BASE } from "./config";
import { tokenStorage } from "./auth";

// ── Axios instance ────────────────────────────────────────────────────────────
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: API_CONFIG.DEFAULT_TIMEOUT_MS,
  headers: {
    "Content-Type": "application/json",
    "Accept":       "application/json",
  },
});

// ── Request interceptor → attach token ───────────────────────────────────────
apiClient.interceptors.request.use(
  (config) => {
    const token = tokenStorage.getAccessToken();
    if (token) {
      config.headers[API_CONFIG.AUTH_HEADER] = `${API_CONFIG.AUTH_PREFIX} ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor → handle 401 / refresh ──────────────────────────────
let _refreshing = false;
let _queue       = [];

const processQueue = (error, token = null) => {
  _queue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)));
  _queue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    // If 401 and we haven't retried yet
    if (error.response?.status === 401 && !original._retry) {
      if (_refreshing) {
        // Queue requests while refresh is in progress
        return new Promise((resolve, reject) => {
          _queue.push({ resolve, reject });
        })
          .then((token) => {
            original.headers[API_CONFIG.AUTH_HEADER] = `${API_CONFIG.AUTH_PREFIX} ${token}`;
            return apiClient(original);
          })
          .catch(Promise.reject.bind(Promise));
      }

      original._retry = true;
      _refreshing      = true;

      try {
        const refreshToken = tokenStorage.getRefreshToken();
        if (!refreshToken) throw new Error("No refresh token");

        const { data } = await axios.post(
          `${API_BASE}/auth/refresh`,
          { refresh: refreshToken },
          { timeout: 10_000 }
        );

        const newAccessToken = data.access ?? data.accessToken ?? data.token;
        tokenStorage.setTokens(newAccessToken, data.refresh ?? refreshToken);
        processQueue(null, newAccessToken);

        original.headers[API_CONFIG.AUTH_HEADER] = `${API_CONFIG.AUTH_PREFIX} ${newAccessToken}`;
        return apiClient(original);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokenStorage.clear();
        // Optional: redirect to login
        window.dispatchEvent(new CustomEvent("synergy:unauthorized"));
        return Promise.reject(refreshError);
      } finally {
        _refreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── Normalize errors ──────────────────────────────────────────────────────────
const normalizeError = (err) => {
  if (err?.name === "AbortError" || err?.name === "CanceledError") return null;
  if (err?.response?.data?.detail)  return err.response.data.detail;
  if (err?.response?.data?.message) return err.response.data.message;
  if (err?.response?.data?.error)   return err.response.data.error;
  if (err?.message)                 return err.message;
  return "An unexpected error occurred";
};

// ── Core fetchSafe wrapper ────────────────────────────────────────────────────
// Matches the EXACT contract used by all existing services:
//   { data: T | null, error: string | null }
export async function fetchSafe(fn) {
  try {
    const data = await fn();
    return { data, error: null };
  } catch (err) {
    const error = normalizeError(err);
    if (!error) return { data: null, error: null }; // aborted
    return { data: null, error };
  }
}

// ── HTTP verbs ────────────────────────────────────────────────────────────────
// These are the helpers your services call instead of axios directly.
// They all return { data, error } automatically.

export const http = {
  get: (url, params = {}, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.get(url, { params, signal });
      return res.data;
    }),

  post: (url, body = {}, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.post(url, body, { signal });
      return res.data;
    }),

  put: (url, body = {}, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.put(url, body, { signal });
      return res.data;
    }),

  patch: (url, body = {}, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.patch(url, body, { signal });
      return res.data;
    }),

  delete: (url, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.delete(url, { signal });
      return res.data;
    }),

  // File upload with progress callback
  upload: (url, formData, onProgress, signal) =>
    fetchSafe(async () => {
      const res = await apiClient.post(url, formData, {
        signal,
        timeout: API_CONFIG.UPLOAD_TIMEOUT_MS,
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) {
            onProgress(Math.round((e.loaded * 100) / e.total));
          }
        },
      });
      return res.data;
    }),
};

export default apiClient;
