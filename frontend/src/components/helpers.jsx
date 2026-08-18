import { useCallback, useState } from "react";

// Deterministic per-user hue: the same person is always the same colour,
// everywhere in the app.
function hueOf(name) {
  let h = 0;
  for (const c of name || "?") h = (h * 31 + c.codePointAt(0)) % 360;
  return h;
}

export function Avatar({ name, sm, lg, children }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  const size = sm ? " sm" : lg ? " lg" : "";
  return (
    <div className={`avatar${size}`} style={{ "--hue": hueOf(name) }}>
      {initial}
      {children}
    </div>
  );
}

export function useToast() {
  const [toast, setToast] = useState(null);
  const show = useCallback((message, isError = false) => {
    setToast({ message, isError });
    setTimeout(() => setToast(null), 3000);
  }, []);
  const node = toast ? (
    <div className={`toast${toast.isError ? " err" : ""}`}>{toast.message}</div>
  ) : null;
  return [node, show];
}

export const timeAgo = (iso) => {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso)) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
};

export const GIFT_EMOJI = { Rose: "🌹", Clap: "👏", Rocket: "🚀", Crown: "👑" };
