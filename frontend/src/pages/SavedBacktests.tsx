import { ArrowRight, GitCompareArrows, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { formatMetric } from "../components/MetricGrid";
import { ErrorNotice, Loading } from "../components/States";
import type { BacktestSummary, Comparison } from "../types";

export function SavedBacktests() {
  const [items, setItems] = useState<BacktestSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => api.list().then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load backtests.")).finally(() => setLoading(false));
  useEffect(() => {
    load();
    window.addEventListener("quantlab:backtests-changed", load);
    return () => window.removeEventListener("quantlab:backtests-changed", load);
  }, []);
  async function remove(id: string) {
    if (!window.confirm("Delete this backtest permanently?")) return;
    try { await api.delete(id); setItems((current) => current.filter((item) => item.backtest_id !== id)); setSelected((current) => current.filter((value) => value !== id)); setComparison(null); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Delete failed."); }
  }
  async function compare() {
    setError("");
    try { setComparison(await api.compare(selected)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Comparison failed."); }
  }
  return <div className="page"><header className="page-header"><div><span className="eyebrow">EXPERIMENT LIBRARY</span><h1>Saved backtests</h1><p>Open a result or select two or more runs to compare.</p></div><Link className="button" to="/research/new">New backtest <ArrowRight size={17}/></Link></header>{error && <ErrorNotice message={error}/>} {loading ? <Loading/> : items.length ? <><section className="panel saved-panel"><div className="saved-toolbar"><span>{items.length} saved experiment{items.length === 1 ? "" : "s"}</span><button className="secondary-btn" disabled={selected.length < 2} onClick={compare}><GitCompareArrows size={16}/>Compare {selected.length > 0 && `(${selected.length})`}</button></div><div className="saved-list">{items.slice().reverse().map((item) => <article key={item.backtest_id}><label className="check"><input type="checkbox" checked={selected.includes(item.backtest_id)} onChange={(e) => setSelected((current) => e.target.checked ? [...current, item.backtest_id] : current.filter((id) => id !== item.backtest_id))}/><span/></label><div className="strategy-chip">MA</div><div className="saved-main"><strong>Moving average crossover</strong><small>{new Date(item.created_at).toLocaleString()} · Windows {item.strategy.parameters.fast_window}/{item.strategy.parameters.slow_window}</small></div><code>{item.backtest_id.slice(0, 8)}</code><Link className="icon-btn" to={`/backtests/${item.backtest_id}`} aria-label="Open backtest"><ArrowRight size={18}/></Link><button className="icon-btn danger" onClick={() => remove(item.backtest_id)} aria-label="Delete backtest"><Trash2 size={17}/></button></article>)}</div></section>{comparison && <ComparisonTable comparison={comparison}/>}</> : <section className="panel empty"><GitCompareArrows/><h2>No saved backtests</h2><p>Run your first experiment to build a comparable research history.</p><Link className="button" to="/research/new">Build a backtest</Link></section>}</div>;
}

function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const metrics = [["cumulative_return", "Total return", "percent"], ["sharpe_ratio", "Sharpe", "number"], ["maximum_drawdown", "Max drawdown", "percent"], ["volatility", "Volatility", "percent"], ["trade_count", "Trades", "integer"]] as const;
  return <section className="panel comparison"><div className="panel-heading"><div><span className="eyebrow">SIDE BY SIDE</span><h2>Comparison</h2></div></div><div className="table-wrap"><table><thead><tr><th>Metric</th>{comparison.results.map((item) => <th key={item.backtest_id}><Link to={`/backtests/${item.backtest_id}`}>{item.backtest_id.slice(0, 8)}</Link></th>)}</tr></thead><tbody>{metrics.map(([key, label, type]) => <tr key={key}><td>{label}</td>{comparison.results.map((item) => <td key={item.backtest_id}>{formatMetric(item.metrics[key], type)}</td>)}</tr>)}</tbody></table></div></section>;
}
