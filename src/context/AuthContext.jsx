import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ENDPOINTS } from "../api/endpoints";
import { http } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    setLoading(true);
    const result = await http.get(ENDPOINTS.AUTH.ME);
    if (result.error) {
      setUser(null);
      setLoading(false);
      return { user: null, error: result.error, errorData: result.errorData ?? [] };
    }
    // Backend returns { status: "success", data: [user], message: "..." }
    // Extract first user from data array
    const me = Array.isArray(result.data?.data) && result.data.data.length > 0 
      ? result.data.data[0] 
      : null;
    setUser(me);
    setLoading(false);
    return { user: me, error: null, errorData: [] };
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback(async (credentials) => {
    const result = await http.post(ENDPOINTS.AUTH.LOGIN, credentials);
    if (result.error) return result;
    // Re-check auth to get full user data
    await checkAuth();
    return result;
  }, [checkAuth]);

  const register = useCallback(async (payload) => {
    const result = await http.post(ENDPOINTS.AUTH.REGISTER, payload);
    if (result.error) return result;
    // Re-check auth to get full user data
    await checkAuth();
    return result;
  }, [checkAuth]);

  const logout = useCallback(async () => {
    const result = await http.post(ENDPOINTS.AUTH.LOGOUT, {});
    setUser(null);
    return result;
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, checkAuth }),
    [user, loading, login, register, logout, checkAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

