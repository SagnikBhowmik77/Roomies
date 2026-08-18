import { useCallback, useEffect, useState } from "react";
import { api, idempotencyKey } from "../api.js";
import { timeAgo, useToast } from "../components/helpers.jsx";
import { CoinIcon } from "../components/Icons.jsx";

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

  if (!wallet) return <div className="skeleton" />;

  return (
    <div className="page stack" style={{ gap: 14 }}>
      <div>
        <div className="kicker" style={{ marginBottom: 8 }}>Your wallet</div>
        <h1 className="display">Every coin, <em>accounted.</em></h1>
        <p className="dim" style={{ marginTop: 10, maxWidth: 460 }}>
          The balance is a cached sum of an append-only double-entry ledger —
          every movement below is immutable.
        </p>
      </div>

      <div className="card row between wrap" style={{ padding: 28 }}>
        <div>
          <div className="kicker" style={{ marginBottom: 10 }}>Balance</div>
          <div className="row" style={{ gap: 10, color: "var(--amber)" }}>
            <CoinIcon size={30} />
            <span className="num">{wallet.balance_coins}</span>
          </div>
        </div>
        <form onSubmit={topup} className="row wrap">
          {[100, 500, 1000].map((v) => (
            <button key={v} type="button" className="ghost" onClick={() => setAmount(v)}>
              +{v}
            </button>
          ))}
          <input
            type="number"
            min="1"
            max="1000000"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={{ width: 110 }}
          />
          <button disabled={busy}>{busy ? "Adding…" : "Top up"}</button>
        </form>
      </div>

      <div className="card stack">
        <h2>Ledger</h2>
        {wallet.recent_entries.length === 0 ? (
          <p className="dim">No transactions yet.</p>
        ) : (
          <table className="ledger">
            <tbody>
              {wallet.recent_entries.map((e) => (
                <tr key={e.id}>
                  <td style={{ fontWeight: 600 }}>{REASON_LABEL[e.reason] || e.reason}</td>
                  <td className={e.delta_coins >= 0 ? "delta-pos" : "delta-neg"}>
                    {e.delta_coins >= 0 ? "+" : ""}{e.delta_coins}
                  </td>
                  <td className="faint" style={{ textAlign: "right" }}>{timeAgo(e.created_at)}</td>
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
