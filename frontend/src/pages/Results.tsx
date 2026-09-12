import { ArrowLeft, CalendarDays, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../api";
import { MetricGrid } from "../components/MetricGrid";
import { ErrorNotice, Loading } from "../components/States";
import type { Backtest, DrawdownPoint, EquityPoint, Trade } from "../types";

export function Results() {
  const { id = "" } = useParams();
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [drawdown, setDrawdown] = useState<DrawdownPoint[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api.backtest(id), api.equity(id), api.drawdown(id), api.trades(id)]).then(([b, e, d, t]) => { setBacktest(b); setEquity(e); setDrawdown(d); setTrades(t); }).catch((reason) => setError(reason instanceof ApiError ? reason.message : "Unable to load results.")); }, [id]);
  if (error) return <div className="page"><ErrorNotice message={error}/><Link className="text-link" to="/backtests"><ArrowLeft size={15}/>Back to saved research</Link></div>;
  if (!backtest) return <Loading label="Loading backtest results…"/>;
  const series = equity.map((point, index) => ({ date: point.timestamp.slice(0, 10), equity: point.equity, drawdown: drawdown[index]?.drawdown * 100 }));
  return <div className="page results-page"><header className="page-header"><div><Link className="back-link" to="/backtests"><ArrowLeft size={15}/>Saved research</Link><span className="eyebrow">COMPLETED BACKTEST</span><h1>Moving average crossover</h1><p className="run-meta"><CheckCircle2/>Validated · MA {backtest.strategy.parameters.fast_window}/{backtest.strategy.parameters.slow_window} <span>·</span> <code>{id.slice(0, 8)}</code></p></div></header><MetricGrid metrics={backtest.metrics}/>
    <section className="chart-grid"><ChartPanel title="Equity curve" caption="Account value after fills and costs" data={series} dataKey="equity" color="#74f0c4" formatter={(value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}/><ChartPanel title="Drawdown" caption="Decline from prior equity peak" data={series} dataKey="drawdown" color="#ff7c7c" formatter={(value) => `${Number(value).toFixed(2)}%`}/></section>
    <section className="panel"><div className="panel-heading"><div><span className="eyebrow">EXECUTION LEDGER</span><h2>Completed trades</h2></div><span className="muted"><CalendarDays size={15}/>{trades.length} closed</span></div>{trades.length ? <div className="table-wrap"><table><thead><tr><th>Side</th><th>Entry</th><th>Exit</th><th>Quantity</th><th>Entry price</th><th>Exit price</th><th>Commission</th><th className="right">Net P&amp;L</th></tr></thead><tbody>{trades.map((trade, index) => <tr key={`${trade.entry_time}-${index}`}><td><span className={trade.side === 1 ? "side long" : "side short"}>{trade.side === 1 ? "LONG" : "SHORT"}</span></td><td>{date(trade.entry_time)}</td><td>{date(trade.exit_time)}</td><td>{trade.quantity.toFixed(3)}</td><td>{money(trade.entry_price)}</td><td>{money(trade.exit_price)}</td><td>{money(trade.commission)}</td><td className={`right pnl ${trade.pnl < 0 ? "negative" : "positive"}`}>{money(trade.pnl)}</td></tr>)}</tbody></table></div> : <div className="empty compact"><h3>No completed trades</h3><p>The strategy held no position through a full entry-to-exit cycle.</p></div>}</section>
  </div>;
}

function ChartPanel({ title, caption, data, dataKey, color, formatter }: { title: string; caption: string; data: object[]; dataKey: string; color: string; formatter: (value: unknown) => string }) {
  return <section className="panel chart-panel"><div className="panel-heading"><div><h2>{title}</h2><p>{caption}</p></div></div><div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}><CartesianGrid stroke="#1a2e29" vertical={false}/><XAxis dataKey="date" tick={{ fill: "#758d86", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={48}/><YAxis tick={{ fill: "#758d86", fontSize: 11 }} tickLine={false} axisLine={false} width={56} tickFormatter={(v) => formatter(v)}/><Tooltip contentStyle={{ background: "#0c1916", border: "1px solid #29453d", borderRadius: 8 }} labelStyle={{ color: "#91aaa2" }} formatter={(v) => [formatter(v), title]}/><Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: color }}/></LineChart></ResponsiveContainer></div></section>;
}

const date = (value: string) => new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
const money = (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
