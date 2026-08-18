import { useMemo, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Equalizer, RadioIcon } from "../components/Icons.jsx";

function Wave({ className, seed = 1 }) {
  // deterministic pseudo-random ridge line
  const d = useMemo(() => {
    let path = "M0 90";
    let y = 90;
    for (let x = 0; x <= 1200; x += 24) {
      const r = Math.abs(Math.sin(x * 0.045 * seed) * Math.cos(x * 0.013 + seed));
      y = 90 - r * 78;
      path += ` L${x} ${y.toFixed(1)}`;
    }
    return path + " L1200 120 L0 120 Z";
  }, [seed]);
  return (
    <svg className={className} viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden>
      <path d={d} fill="currentColor" />
    </svg>
  );
}

function Backdrop() {
  const dots = useMemo(
    () =>
      [...Array(16)].map((_, i) => ({
        left: `${(i * 61) % 100}%`,
        size: 3 + ((i * 7) % 6),
        duration: 14 + ((i * 13) % 12),
        delay: -((i * 5) % 20),
      })),
    []
  );
  return (
    <div className="hero-bg" aria-hidden>
      <div className="scene studio" />
      <div className="scene onair" />
      <div className="scene crowd" />
      <Wave className="wave" seed={1.3} />
      <Wave className="wave w2" seed={2.1} />
      <div className="dotfield">
        {dots.map((d, i) => (
          <i
            key={i}
            style={{
              left: d.left,
              bottom: "-10px",
              width: d.size,
              height: d.size,
              animationDuration: `${d.duration}s`,
              animationDelay: `${d.delay}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

const QUOTES = [
  { text: <>"Found my people at <em>2 a.m.</em> in a lofi room."</>, who: "Meera · Mumbai" },
  { text: <>"Went on air with <em>12 listeners.</em> Ended with 200."</>, who: "Kabir · host" },
  { text: <>"The gifts pay for my <em>coffee habit.</em>"</>, who: "Sana · cricket talk" },
];

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
    <>
      <Backdrop />
      <div className="login-grid page">
        <div>
          <div className="login-mark">
            <RadioIcon size={17} />
            <span className="kicker" style={{ color: "var(--live)" }}>On air</span>
            <Equalizer active />
          </div>
          <h1 className="display" style={{ fontSize: 54 }}>
            Rooms worth
            <br />
            <em>listening</em> to.
          </h1>
          <p className="dim" style={{ margin: "14px 0 28px", maxWidth: 330 }}>
            Live audio rooms — host, talk, react, and send gifts that actually
            count. Log in with just your phone number.
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

          <p className="faint" style={{ marginTop: 16 }}>
            Demo accounts: +919876500000 – 11 · any new number creates an account.
          </p>
        </div>

        <div className="login-showcase" aria-hidden>
          {QUOTES.map((q, i) => (
            <div className="quote" key={i}>
              {q.text}
              <small>{q.who}</small>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
