import { CheckCircle2, FileSpreadsheet, Play, UploadCloud } from "lucide-react";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { MAX_CSV_BYTES, parseOhlcvCsv } from "../csv";
import { ErrorNotice } from "../components/States";
import type { Dataset, OhlcvBar, Strategy } from "../types";

export function NewResearch() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [bars, setBars] = useState<OhlcvBar[]>([]);
  const [fileName, setFileName] = useState("");
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState("");
  const [validating, setValidating] = useState(false);
  const [running, setRunning] = useState(false);
  const [fast, setFast] = useState(20);
  const [slow, setSlow] = useState(50);
  const [capital, setCapital] = useState(10000);
  const [commission, setCommission] = useState(5);
  const [slippage, setSlippage] = useState(2);
  useEffect(() => { api.strategies().then(setStrategies).catch(() => setError("Unable to load strategy catalog.")); }, []);

  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setDataset(null); setError(""); setFileName(file.name);
    if (file.size > MAX_CSV_BYTES) { setBars([]); setError("CSV must be 10 MB or smaller."); return; }
    try { setBars(parseOhlcvCsv(await file.text())); }
    catch (reason) { setBars([]); setError(reason instanceof Error ? reason.message : "Unable to read CSV."); }
  }
  async function validateData() {
    setValidating(true); setError("");
    try { setDataset(await api.upload(bars)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Validation failed."); }
    finally { setValidating(false); }
  }
  async function run(event: FormEvent) {
    event.preventDefault(); if (!dataset) return;
    setRunning(true); setError("");
    try {
      const result = await api.run({ dataset_id: dataset.dataset_id, strategy: { name: "moving_average_crossover", parameters: { fast_window: fast, slow_window: slow } }, backtest: { initial_capital: capital, transaction_cost_bps: commission, slippage_bps: slippage, periods_per_year: 252 } });
      navigate(`/backtests/${result.backtest_id}`);
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Backtest failed."); }
    finally { setRunning(false); }
  }
  return <div className="page"><header className="page-header"><div><span className="eyebrow">NEW EXPERIMENT</span><h1>Backtest builder</h1><p>Data first. Assumptions second. Results last.</p></div><div className="stepper"><span className={dataset ? "done" : "active"}>1</span><i/><span className={dataset ? "active" : ""}>2</span><i/><span>3</span></div></header>{error && <ErrorNotice message={error}/>}<form onSubmit={run} className="builder-grid">
    <section className="panel form-section"><div className="section-title"><span>01</span><div><h2>Market data</h2><p>Daily OHLCV CSV with timestamp, open, high, low, close, volume.</p></div></div><label className="dropzone"><input type="file" accept=".csv,text/csv" onChange={chooseFile}/>{fileName ? <><FileSpreadsheet/><strong>{fileName}</strong><small>{bars.length ? `${bars.length.toLocaleString()} rows parsed locally` : "Review the error above"}</small></> : <><UploadCloud/><strong>Choose OHLCV CSV</strong><small>or drop a file here</small></>}</label>{bars.length > 0 && !dataset && <button type="button" className="secondary-btn full" onClick={validateData} disabled={validating}>{validating ? "Validating…" : "Validate & store dataset"}</button>}{dataset && <div className="validation-success"><CheckCircle2/><div><strong>Dataset validated</strong><span>{dataset.rows.toLocaleString()} bars · {new Date(dataset.start).toLocaleDateString()} — {new Date(dataset.end).toLocaleDateString()}</span></div></div>}</section>
    <section className={dataset ? "panel form-section" : "panel form-section disabled-section"}><div className="section-title"><span>02</span><div><h2>Strategy</h2><p>{strategies[0]?.description || "Select a research model."}</p></div></div><label>Strategy<select disabled={!dataset}><option>Moving average crossover</option></select></label><div className="field-pair"><label>Fast window<input type="number" min="1" value={fast} onChange={(e) => setFast(Number(e.target.value))} disabled={!dataset}/><small>Trading days</small></label><label>Slow window<input type="number" min="2" value={slow} onChange={(e) => setSlow(Number(e.target.value))} disabled={!dataset}/><small>Must exceed fast</small></label></div></section>
    <section className={dataset ? "panel form-section" : "panel form-section disabled-section"}><div className="section-title"><span>03</span><div><h2>Execution</h2><p>Explicit next-open fills with costs charged to capital.</p></div></div><label>Initial capital<input type="number" min="1" value={capital} onChange={(e) => setCapital(Number(e.target.value))} disabled={!dataset}/><small>Account currency units</small></label><div className="field-pair"><label>Commission<input type="number" min="0" max="9999" step="0.1" value={commission} onChange={(e) => setCommission(Number(e.target.value))} disabled={!dataset}/><small>Basis points / fill</small></label><label>Slippage<input type="number" min="0" max="9999" step="0.1" value={slippage} onChange={(e) => setSlippage(Number(e.target.value))} disabled={!dataset}/><small>Basis points / fill</small></label></div><button className="button full run-button" disabled={!dataset || running}>{running ? <><span className="spinner"/>Running validated ledger…</> : <><Play size={17}/>Run backtest</>}</button></section>
  </form></div>;
}
