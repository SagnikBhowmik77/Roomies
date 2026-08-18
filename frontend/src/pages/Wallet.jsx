import { useCallback, useEffect, useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { timeAgo, useToast } from "../components/helpers.jsx";

const REASON_LABEL = {
  topup: "Top-up",
  gift_sent: "Gift sent",
  gift_received: "Gift received",
};

export default function Wallet() {
  const [wallet, setWallet] = useState(null);
  const [amount, setAmount] = useState(500);
  const [busy, setBusy] = useState(false);
  const [toastNode, toast] = useToast();

  const load = useCallback(
    () => api("/api/v1/wallet/").then(setWallet).catch(() => {}),
    []
  );
  useEffect(() => {
    load();
  }, [load]);

  const topup = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/api/v1/wallet/topup/", {
        method: "POST",
        body: { coins: Number(amount) },
        headers: { "Idempotency-Key": idempotencyKey() },
      });
      toast(`Added ${amount} coins.`);
      await load();
    } catch (err) {
      toast(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  if (!wallet) return <p className="dim">Loading wallet…</p>;

  return (
    <div className="stack">
      <div>
        <h1>Wallet</h1>
        <p className="dim">
          Balance is a cached sum of the ledger — every movement below is an
          immutable double-entry row.
        </p>
      </div>

      <div className="card row between">
        <div>
          <div className="dim">Current balance</div>
          <div style={{ fontSize: 34, fontWeight: 800, color: "var(--gold)" }}>
            🪙 {wallet.balance_coins}
          </div>
        </div>
        <form onSubmit={topup} className="row">
          <input
            type="number"
            min="1"
            max="1000000"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={{ width: 120 }}
          />
          <button disabled={busy}>{busy ? "Adding…" : "Top up"}</button>
        </form>
      </div>

      <div className="card stack">
        <h2>Recent ledger entries</h2>
        {wallet.recent_entries.length === 0 ? (
          <p className="dim">No transactions yet.</p>
        ) : (
          <table className="ledger">
            <tbody>
              {wallet.recent_entries.map((e) => (
                <tr key={e.id}>
                  <td>{REASON_LABEL[e.reason] || e.reason}</td>
                  <td className={e.delta_coins >= 0 ? "delta-pos" : "delta-neg"}>
                    {e.delta_coins >= 0 ? "+" : ""}{e.delta_coins}
                  </td>
                  <td className="dim">{timeAgo(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {toastNode}
    </div>
  );
}
