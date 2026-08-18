import { useCallback, useState } from "react";

export function Avatar({ name, sm }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  return <div className={`avatar${sm ? " sm" : ""}`}>{initial}</div>;
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
