import { ArrowRight, FlaskConical, History, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { ErrorNotice, Loading } from "../components/States";
import type { BacktestSummary } from "../types";

export function Dashboard() {
  const [items, setItems] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { api.list().then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load research.")).finally(() => setLoading(false)); }, []);
  return <div className="page"><header className="page-header"><div><span className="eyebrow">RESEARCH WORKSPACE</span><h1>Overview</h1><p>Build, inspect, and compare reproducible strategy tests.</p></div><Link className="button" to="/research/new"><FlaskConical size={17}/>New backtest</Link></header>
    {error && <ErrorNotice message={error}/>}<section className="quick-grid"><Link className="quick-card primary-card" to="/research/new"><div className="icon-tile"><TrendingUp/></div><div><small>START HERE</small><h2>Run a new experiment</h2><p>Validate OHLCV data and configure execution assumptions.</p></div><ArrowRight/></Link><Link className="quick-card" to="/backtests"><div className="icon-tile"><History/></div><div><small>SAVED RESEARCH</small><h2>{items.length} backtest{items.length === 1 ? "" : "s"}</h2><p>Reopen results or compare experiments side by side.</p></div><ArrowRight/></Link></section>
    <section className="panel"><div className="panel-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Saved backtests</h2></div><Link className="text-link" to="/backtests">View all <ArrowRight size={15}/></Link></div>{loading ? <Loading/> : items.length ? <div className="run-list">{items.slice(-5).reverse().map((item) => <Link to={`/backtests/${item.backtest_id}`} key={item.backtest_id} className="run-row"><span className="strategy-chip">MA</span><div><strong>Moving average crossover</strong><small>{new Date(item.created_at).toLocaleString()} · {item.strategy.parameters.fast_window}/{item.strategy.parameters.slow_window}</small></div><code>{item.backtest_id.slice(0, 8)}</code><ArrowRight size={16}/></Link>)}</div> : <div className="empty"><FlaskConical/><h3>No experiments yet</h3><p>Your validated backtests will appear here.</p><Link className="text-link" to="/research/new">Create the first one <ArrowRight size={15}/></Link></div>}</section>
  </div>;
}
