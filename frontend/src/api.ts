import type { Backtest, BacktestSummary, Comparison, Dataset, DrawdownPoint, EquityPoint, Metrics, OhlcvBar, Strategy, Trade, User } from "./types";

const API_URL = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
const TOKEN_KEY = "quantlab_token";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const session = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = session.get();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!response.ok) {
    if (response.status === 401 && token) {
      session.clear();
      window.dispatchEvent(new Event("quantlab:unauthorized"));
    }
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("; ") : body.detail;
    throw new ApiError(response.status, detail || "Request failed. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export const api = {
  register: (email: string, password: string) => request<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<User>("/auth/me"),
  strategies: () => request<Strategy[]>("/strategies"),
  upload: (bars: OhlcvBar[]) => request<Dataset>("/datasets", { method: "POST", body: JSON.stringify({ bars }) }),
  run: (body: object) => request<Backtest>("/backtests", { method: "POST", body: JSON.stringify(body) }),
  list: () => request<BacktestSummary[]>("/backtests"),
  backtest: (id: string) => request<Backtest>(`/backtests/${id}`),
  metrics: (id: string) => request<Metrics>(`/backtests/${id}/metrics`),
  equity: (id: string) => request<EquityPoint[]>(`/backtests/${id}/equity`),
  drawdown: (id: string) => request<DrawdownPoint[]>(`/backtests/${id}/drawdown`),
  trades: (id: string) => request<Trade[]>(`/backtests/${id}/trades`),
  compare: (ids: string[]) => request<Comparison>("/backtests/compare", { method: "POST", body: JSON.stringify({ backtest_ids: ids }) }),
  delete: (id: string) => request<void>(`/backtests/${id}`, { method: "DELETE" }),
};
