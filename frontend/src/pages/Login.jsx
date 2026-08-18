import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Equalizer, RadioIcon } from "../components/Icons.jsx";

export default function Login() {
  const { login } = useAuth();
  const [phone, setPhone] = useState("+919876500000");
  const [code, setCode] = useState("");
  const [debugCode, setDebugCode] = useState(null);
  const [stage, setStage] = useState("phone");
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
    <div className="login-wrap page">
      <div className="login-mark">
        <RadioIcon size={17} />
        <span className="kicker" style={{ color: "var(--live)" }}>On air</span>
        <Equalizer active />
      </div>
      <h1 className="display">
        Rooms worth
        <br />
        <em>listening</em> to.
      </h1>
      <p className="dim" style={{ margin: "14px 0 30px", maxWidth: 320 }}>
        Live audio rooms — host, talk, and send gifts. Log in with just your
        phone number.
      </p>

      <div className="card stack">
        {stage === "phone" ? (
          <form onSubmit={requestOtp} className="stack">
            <label className="kicker">Phone number</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919876500000"
              autoFocus
            />
            <button disabled={busy}>{busy ? "Sending…" : "Send code"}</button>
          </form>
        ) : (
          <form onSubmit={verifyOtp} className="stack">
            <label className="kicker">Code sent to {phone}</label>
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
            <button disabled={busy}>{busy ? "Verifying…" : "Enter"}</button>
            <button type="button" className="ghost" onClick={() => setStage("phone")}>
              Change number
            </button>
          </form>
        )}
        {error && <div className="error">{error}</div>}
      </div>

      <p className="faint" style={{ marginTop: 18 }}>
        Demo accounts: +919876500000 – 11 · any new number creates an account.
      </p>
    </div>
  );
}
