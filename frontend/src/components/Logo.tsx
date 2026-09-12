import { BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";

export function Logo({ to = "/" }: { to?: string }) {
  return <Link className="logo" to={to} aria-label="QuantLab home"><span className="logo-mark"><BarChart3 size={19} /></span><span>Quant<span>Lab</span></span></Link>;
}
