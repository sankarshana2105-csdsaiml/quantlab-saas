export type User = { id: string; email: string; created_at: string; updated_at: string };
export type Dataset = { dataset_id: string; rows: number; start: string; end: string };
export type Strategy = { name: string; description: string; parameters: Record<string, string> };
export type StrategyConfig = { name: string; parameters: Record<string, number> };
export type Metrics = {
  total_return: number; cumulative_return: number; annualized_return: number; cagr: number | null;
  sharpe_ratio: number | null; sortino_ratio: number | null; volatility: number | null;
  maximum_drawdown: number; win_rate: number; profit_factor: number | null;
  trade_count: number; exposure: number; turnover: number;
};
export type Backtest = { backtest_id: string; dataset_id: string; strategy: StrategyConfig; metrics: Metrics };
export type BacktestSummary = Omit<Backtest, "metrics"> & { created_at: string; updated_at: string };
export type EquityPoint = { timestamp: string; equity: number };
export type DrawdownPoint = { timestamp: string; drawdown: number };
export type Trade = { entry_time: string; exit_time: string; side: -1 | 1; quantity: number; entry_price: number; exit_price: number; commission: number; pnl: number };
export type Comparison = { results: Array<{ backtest_id: string; metrics: Metrics }> };
export type OhlcvBar = { timestamp: string; open: number; high: number; low: number; close: number; volume: number };
