import { Navigate, Route, Routes } from "react-router-dom";
import { lazy, Suspense } from "react";
import { useAuth } from "./auth-context";
import { AppShell } from "./components/AppShell";
import { Loading } from "./components/States";
import { AuthPage } from "./pages/AuthPage";
import { Landing } from "./pages/Landing";

const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default:module.Dashboard })));
const NewResearch = lazy(() => import("./pages/NewResearch").then((module) => ({ default:module.NewResearch })));
const Results = lazy(() => import("./pages/Results").then((module) => ({ default:module.Results })));
const SavedBacktests = lazy(() => import("./pages/SavedBacktests").then((module) => ({ default:module.SavedBacktests })));

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Opening workspace…"/>;
  return user ? <AppShell/> : <Navigate to="/login" replace/>;
}

export default function App() {
  return <Suspense fallback={<Loading/>}><Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<AuthPage mode="login"/>}/><Route path="/register" element={<AuthPage mode="register"/>}/><Route element={<Protected/>}><Route path="/dashboard" element={<Dashboard/>}/><Route path="/research/new" element={<NewResearch/>}/><Route path="/backtests" element={<SavedBacktests/>}/><Route path="/backtests/:id" element={<Results/>}/></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes></Suspense>;
}
