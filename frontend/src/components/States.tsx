import { AlertCircle, LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading research…" }: { label?: string }) {
  return <div className="state"><LoaderCircle className="spin" /><p>{label}</p></div>;
}

export function ErrorNotice({ message }: { message: string }) {
  return <div className="error-notice" role="alert"><AlertCircle size={18} /><span>{message}</span></div>;
}
