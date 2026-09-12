import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth-context";
import { Logo } from "../components/Logo";
import { ErrorNotice } from "../components/States";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await (mode === "login" ? login(email, password) : register(email, password)); navigate("/dashboard"); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Unable to continue."); }
    finally { setBusy(false); }
  }
  const registering = mode === "register";
  return <div className="auth-page"><div className="auth-brand"><Logo /><div><span className="eyebrow">QUANTITATIVE RESEARCH</span><h1>Evidence over instinct.</h1><p>A disciplined workspace for testing strategies against clean data and explicit execution assumptions.</p></div><small>Validated accounting · Private by default</small></div><div className="auth-panel"><form onSubmit={submit}><span className="eyebrow">{registering ? "CREATE ACCOUNT" : "WELCOME BACK"}</span><h2>{registering ? "Build your research workspace" : "Sign in to QuantLab"}</h2><p>{registering ? "Start with your own data in under a minute." : "Continue your saved experiments."}</p>{error && <ErrorNotice message={error} />}<label>Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label><label>Password<input required minLength={registering ? 12 : 1} maxLength={128} type="password" autoComplete={registering ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={registering ? "At least 12 characters" : "Your password"} /></label><button className="button full" disabled={busy}>{busy ? "Please wait…" : registering ? "Create workspace" : "Sign in"}<ArrowRight size={17}/></button><div className="auth-switch">{registering ? "Already have an account?" : "New to QuantLab?"} <Link to={registering ? "/login" : "/register"}>{registering ? "Sign in" : "Create an account"}</Link></div></form></div></div>;
}
