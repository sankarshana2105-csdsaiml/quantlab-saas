import type { Metrics } from "../types";

const items: Array<[keyof Metrics, string, "percent" | "number" | "integer"]> = [
  ["cumulative_return", "Cumulative return", "percent"], ["annualized_return", "Annualized return", "percent"],
  ["sharpe_ratio", "Sharpe ratio", "number"], ["sortino_ratio", "Sortino ratio", "number"],
  ["volatility", "Volatility", "percent"], ["maximum_drawdown", "Maximum drawdown", "percent"],
  ["win_rate", "Win rate", "percent"], ["profit_factor", "Profit factor", "number"],
  ["turnover", "Turnover", "number"], ["trade_count", "Completed trades", "integer"], ["exposure", "Exposure", "percent"],
];

export function formatMetric(value: number | null, type: string) {
  if (value === null) return "—";
  if (type === "percent") return `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value * 100).toFixed(2)}%`;
  if (type === "integer") return String(value);
  return Number.isFinite(value) ? value.toFixed(2) : "∞";
}

export function MetricGrid({ metrics }: { metrics: Metrics }) {
  return <div className="metric-grid">{items.map(([key, label, type]) => <article key={key}><small>{label}</small><strong className={typeof metrics[key] === "number" && (metrics[key] as number) < 0 ? "negative" : ""}>{formatMetric(metrics[key] as number | null, type)}</strong></article>)}</div>;
}
