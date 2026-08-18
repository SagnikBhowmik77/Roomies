import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login } = useAuth();
  const [phone, setPhone] = useState("+919876500000");
  const [code, setCode] = useState("");
  const [debugCode, setDebugCode] = useState(null);
  const [stage, setStage] = useState("phone"); // phone -> otp
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const requestOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api("/api/v1/auth/request-otp/", {
        method: "POST",
        body: { phone },
      });
      setDebugCode(res.debug_code || null);
      if (res.debug_code) setCode(res.debug_code);
      setStage("otp");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api("/api/v1/auth/verify-otp/", {
        method: "POST",
        body: { phone, code },
      });
      login(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap stack">
      <div>
        <h1>
          room<span style={{ color: "var(--accent)" }}>ies</span>
        </h1>
        <p className="dim">Live audio rooms. Log in with your phone.</p>
      </div>

      <div className="card stack">
        {stage === "phone" ? (
          <form onSubmit={requestOtp} className="stack">
            <label className="dim">Phone number</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919876500000"
              autoFocus
            />
            <button disabled={busy}>{busy ? "Sending…" : "Send OTP"}</button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="stack">
            <label className="dim">Enter the 6-digit code sent to {phone}</label>
            {debugCode && (
              <div className="otp-hint">
                Dev mode — your code is <b>{debugCode}</b> (pre-filled)
              </div>
            )}
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
              autoFocus
            />
            <button disabled={busy}>{busy ? "Verifying…" : "Verify & log in"}</button>
            <button type="button" className="ghost" onClick={() => setStage("phone")}>
              Change number
            </button>
          </form>
        )}
        {error && <div className="error">{error}</div>}
      </div>

      <p className="dim">
        Demo accounts: +919876500000 … +919876500011 · new numbers create a fresh
        account automatically.
      </p>
    </div>
  );
}
