import { FlaskConical, History, LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth-context";
import { Logo } from "./Logo";

export function AppShell() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const links = [
    { to: "/dashboard", label: "Overview", icon: BarIcon },
    { to: "/research/new", label: "New research", icon: FlaskConical },
    { to: "/backtests", label: "Saved backtests", icon: History },
  ];
  return <div className="app-shell">
    <aside className={open ? "sidebar open" : "sidebar"}>
      <div className="sidebar-head"><Logo to="/dashboard" /><button className="icon-btn mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation"><X /></button></div>
      <nav aria-label="Primary">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setOpen(false)}><Icon size={18} />{label}</NavLink>)}</nav>
      <div className="sidebar-foot"><div className="user-badge"><span>{user?.email.slice(0, 1).toUpperCase()}</span><div><strong>{user?.email.split("@")[0]}</strong><small>{user?.email}</small></div></div><button className="ghost-btn" onClick={logout}><LogOut size={16} />Log out</button></div>
    </aside>
    <div className="workspace"><header className="mobile-header"><button className="icon-btn" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu /></button><Logo to="/dashboard" /></header><main><Outlet /></main></div>
  </div>;
}

function BarIcon({ size = 18 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="M3 14V8m4 6V4m4 10V6m4 8V2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>;
}
