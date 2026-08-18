import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Navbar() {
  const { user, logout } = useAuth();
  const [balance, setBalance] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api("/api/v1/wallet/").then((w) => alive && setBalance(w.balance_coins)).catch(() => {});
    load();
    // keep the coin count fresh as gifts get sent from any page
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
        <NavLink to="/notifications">Notifications</NavLink>
        <NavLink to="/me">Profile</NavLink>
      </div>
      <Link to="/wallet" className="coins">🪙 {balance ?? "…"}</Link>
      <span className="dim">{user.display_name || user.phone}</span>
      <button className="ghost" onClick={logout}>Log out</button>
    </nav>
  );
}
