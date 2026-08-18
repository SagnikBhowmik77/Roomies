import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { CoinIcon, LogoutIcon } from "./Icons.jsx";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [balance, setBalance] = useState(null);
  const [hasNews, setHasNews] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const w = await api("/api/v1/wallet/");
        if (alive) setBalance(w.balance_coins);
        const n = await api("/api/v1/notifications/");
        const newest = n.results[0]?.created_at;
        const lastSeen = localStorage.getItem("notif_seen") || "";
        if (alive) setHasNews(Boolean(newest && newest > lastSeen));
      } catch {
        /* transient */
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <nav className="nav">
      <Link to="/" className="brand">
        room<em>ies</em>
      </Link>
      <div className="links">
        <NavLink to="/" end>Rooms</NavLink>
        <NavLink to="/wallet">Wallet</NavLink>
        <NavLink to="/notifications">
          Alerts
          {hasNews && <span className="dot" />}
        </NavLink>
        <NavLink to="/me">Profile</NavLink>
      </div>
      <Link to="/wallet" className="coins">
        <CoinIcon size={14} />
        {balance ?? "…"}
      </Link>
      <span className="who">{user.display_name || user.phone}</span>
      <button className="ghost icon-btn" onClick={logout} title="Log out">
        <LogoutIcon size={15} />
      </button>
    </nav>
  );
}
