import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

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
        room<span>ies</span>
      </Link>
      <div className="links">
        <NavLink to="/" end>Rooms</NavLink>
        <NavLink to="/wallet">Wallet</NavLink>
        <NavLink to="/notifications">
          Notifications
          {hasNews && <span className="dot" />}
        </NavLink>
        <NavLink to="/me">Profile</NavLink>
      </div>
      <Link to="/wallet" className="coins">🪙 {balance ?? "…"}</Link>
      <span className="dim">{user.display_name || user.phone}</span>
      <button className="ghost" onClick={logout}>Log out</button>
    </nav>
  );
}
