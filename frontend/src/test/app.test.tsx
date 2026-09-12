import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { api, ApiError, session } from "../api";
import { AuthProvider } from "../auth-context";
import { MetricGrid } from "../components/MetricGrid";
import { NewResearch } from "../pages/NewResearch";
import { SavedBacktests } from "../pages/SavedBacktests";
import type { Metrics } from "../types";
import { parseOhlcvCsv } from "../csv";

const user = { id: "u1", email: "analyst@example.com", created_at: "2024-01-01T00:00:00Z", updated_at: "2024-01-01T00:00:00Z" };
const metrics: Metrics = { total_return:.1, cumulative_return:.1, annualized_return:.12, cagr:.11, sharpe_ratio:1.2, sortino_ratio:1.8, volatility:.14, maximum_drawdown:-.08, win_rate:.6, profit_factor:1.7, trade_count:4, exposure:.5, turnover:2.2 };
const json = (body: unknown, status = 200) => Promise.resolve(new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

afterEach(() => vi.restoreAllMocks());

describe("critical user flow", () => {
  it("parses standards-compliant quoted CSV fields", () => {
    const parsed = parseOhlcvCsv('"timestamp","open","high","low","close","volume"\n"January 1, 2024 00:00 UTC","100","102","99","101","1000"');
    expect(parsed).toEqual([{ timestamp:"January 1, 2024 00:00 UTC", open:100, high:102, low:99, close:101, volume:1000 }]);
  });
  it("redirects unauthenticated users from protected routes", async () => {
    render(<MemoryRouter initialEntries={["/dashboard"]}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Sign in to QuantLab" })).toBeInTheDocument();
  });

  it("registers, logs in, and opens the workspace", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => json(user, 201))
      .mockImplementationOnce(() => json({ access_token: "token" }))
      .mockImplementationOnce(() => json(user))
      .mockImplementationOnce(() => json([])));
    render(<MemoryRouter initialEntries={["/register"]}><AuthProvider><App/></AuthProvider></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Email"), user.email);
    await userEvent.type(screen.getByLabelText("Password"), "correct-horse-123");
    await userEvent.click(screen.getByRole("button", { name: /create workspace/i }));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(session.get()).toBe("token");
  });

  it("clears an expired session and exposes a useful API error", async () => {
    session.set("expired");
    const unauthorized = vi.fn(); window.addEventListener("quantlab:unauthorized", unauthorized);
    vi.stubGlobal("fetch", vi.fn(() => json({ detail: "Invalid or expired token" }, 401)));
    await expect(api.me()).rejects.toEqual(expect.objectContaining({ status: 401, message: "Invalid or expired token" }));
    expect(session.get()).toBeNull(); expect(unauthorized).toHaveBeenCalled();
  });

  it("uploads CSV and runs a configured backtest", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/strategies")) return json([{ name:"moving_average_crossover", description:"Causal crossover", parameters:{ fast_window:"positive", slow_window:"larger" } }]);
      if (url.endsWith("/datasets")) return json({ dataset_id:"d1", rows:2, start:"2024-01-01T00:00:00Z", end:"2024-01-02T00:00:00Z" }, 201);
      if (url.endsWith("/backtests") && init?.method === "POST") return json({ backtest_id:"b1", dataset_id:"d1", strategy:{ name:"moving_average_crossover", parameters:{ fast_window:20, slow_window:50 } }, metrics }, 201);
      return json({ detail:"unexpected" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/research/new"]}><Routes><Route path="/research/new" element={<NewResearch/>}/><Route path="/backtests/:id" element={<h1>Result opened</h1>}/></Routes></MemoryRouter>);
    const file = new File(["timestamp,open,high,low,close,volume\n2024-01-01,100,102,99,101,1000\n2024-01-02,101,103,100,102,1100"], "bars.csv", { type:"text/csv" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve("timestamp,open,high,low,close,volume\n2024-01-01,100,102,99,101,1000\n2024-01-02,101,103,100,102,1100") });
    await userEvent.upload(screen.getByLabelText(/choose ohlcv csv/i), file);
    await userEvent.click(await screen.findByRole("button", { name: /validate & store/i }));
    expect(await screen.findByText("Dataset validated")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /run backtest/i }));
    expect(await screen.findByRole("heading", { name:"Result opened" })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/backtests"));
    expect(JSON.parse(String(request?.[1]?.body)).strategy.parameters).toEqual({ fast_window:20, slow_window:50 });
  });

  it("renders metrics and deletes an owned saved result", async () => {
    render(<MetricGrid metrics={metrics}/>);
    expect(screen.getByText("+10.00%")).toBeInTheDocument();
    expect(screen.getByText("−8.00%")).toBeInTheDocument();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => json([{ backtest_id:"b1", dataset_id:"d1", strategy:{ name:"moving_average_crossover", parameters:{ fast_window:20, slow_window:50 } }, created_at:"2024-01-01T00:00:00Z", updated_at:"2024-01-01T00:00:00Z" }]))
      .mockImplementationOnce(() => json(null, 204)));
    render(<MemoryRouter><SavedBacktests/></MemoryRouter>);
    expect(await screen.findByText("Moving average crossover")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name:"Delete backtest" }));
    await waitFor(() => expect(screen.queryByText("Moving average crossover")).not.toBeInTheDocument());
  });
});
