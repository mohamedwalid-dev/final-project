// ─── src/api/auth.js ──────────────────────────────────────────────────────────
// Token storage + Auth service
// Handles login, logout, refresh, and current user fetch.
//
// Token storage uses localStorage by default.
// Switch to httpOnly cookies by removing localStorage calls and relying
// on your backend to set the cookie automatically.

import { http } from "./client";
import { ENDPOINTS } from "./config";

// ── Token storage helpers ─────────────────────────────────────────────────────
const KEYS = {
  ACCESS:  "synergy_access_token",
  REFRESH: "synergy_refresh_token",
  USER:    "synergy_user",
};

export const tokenStorage = {
  getAccessToken:  ()      => localStorage.getItem(KEYS.ACCESS),
  getRefreshToken: ()      => localStorage.getItem(KEYS.REFRESH),
  getUser:         ()      => { try { return JSON.parse(localStorage.getItem(KEYS.USER)); } catch { return null; } },

  setTokens: (access, refresh) => {
    localStorage.setItem(KEYS.ACCESS,  access);
    if (refresh) localStorage.setItem(KEYS.REFRESH, refresh);
  },

  setUser: (user) => {
    localStorage.setItem(KEYS.USER, JSON.stringify(user));
  },

  clear: () => {
    localStorage.removeItem(KEYS.ACCESS);
    localStorage.removeItem(KEYS.REFRESH);
    localStorage.removeItem(KEYS.USER);
  },

  isLoggedIn: () => !!localStorage.getItem(KEYS.ACCESS),
};

// ── Auth service ──────────────────────────────────────────────────────────────
const authService = {
  /**
   * Login with email + password.
   * 🔌 REAL: POST /auth/login → { access, refresh, user }
   *
   * @param {{ email: string, password: string }} credentials
   * @returns {{ data: { user, access, refresh }, error }}
   */
  login: async ({ email, password }) => {
    // 🔌 SWAP mock with:
    // const result = await http.post(ENDPOINTS.AUTH.LOGIN, { email, password });
    // if (result.data) {
    //   tokenStorage.setTokens(result.data.access, result.data.refresh);
    //   tokenStorage.setUser(result.data.user);
    // }
    // return result;

    // ── MOCK ──
    await new Promise((r) => setTimeout(r, 600));
    if (email === "admin@synergy.io" && password === "password") {
      const mockUser = { id: 1, name: "Alex Sterling", role: "Executive Admin", email };
      tokenStorage.setTokens("mock_access_token", "mock_refresh_token");
      tokenStorage.setUser(mockUser);
      return { data: { user: mockUser, access: "mock_access_token" }, error: null };
    }
    return { data: null, error: "Invalid credentials" };
  },

  /**
   * Logout — clears tokens and notifies backend.
   * 🔌 REAL: POST /auth/logout
   */
  logout: async () => {
    // 🔌 SWAP mock with:
    // await http.post(ENDPOINTS.AUTH.LOGOUT);
    tokenStorage.clear();
    return { data: { success: true }, error: null };
  },

  /**
   * Fetch current authenticated user profile.
   * 🔌 REAL: GET /auth/me
   *
   * @returns {{ data: User, error }}
   */
  getMe: () => {
    // 🔌 SWAP mock with:
    // return http.get(ENDPOINTS.AUTH.ME);

    // ── MOCK ──
    const user = tokenStorage.getUser();
    if (user) return Promise.resolve({ data: user, error: null });
    return Promise.resolve({ data: null, error: "Not authenticated" });
  },

  /**
   * Request a password reset email.
   * 🔌 REAL: POST /auth/reset-password
   *
   * @param {string} email
   * @returns {{ data: { message: string }, error }}
   */
  resetPassword: (email) => {
    // 🔌 SWAP mock with:
    // return http.post(ENDPOINTS.AUTH.RESET_PASSWORD, { email });

    return Promise.resolve({ data: { message: "Password reset email sent" }, error: null });
  },
};

export default authService;
