import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, session } from "./api";
import type { User } from "./types";
import { registerResearchTools } from "./webmcp";

type AuthState = {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const invalidate = () => setUser(null);
    window.addEventListener("quantlab:unauthorized", invalidate);
    if (session.get()) api.me().then(setUser).catch(() => session.clear()).finally(() => setLoading(false));
    else setLoading(false);
    return () => window.removeEventListener("quantlab:unauthorized", invalidate);
  }, []);

  useEffect(() => user ? registerResearchTools() : undefined, [user]);

  async function login(email: string, password: string) {
    const result = await api.login(email, password);
    session.set(result.access_token);
    setUser(await api.me());
  }

  async function register(email: string, password: string) {
    await api.register(email, password);
    await login(email, password);
  }

  function logout() { session.clear(); setUser(null); }

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required");
  return value;
}
